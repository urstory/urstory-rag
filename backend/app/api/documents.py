"""문서 CRUD API 엔드포인트."""
import math
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, require_admin
from app.exceptions import DocumentNotFoundError
from app.models.database import Document, DocumentStatus, User, get_db

router = APIRouter(tags=["documents"])


async def _invalidate_document_caches() -> None:
    """문서 변경 시 관련 캐시 무효화."""
    from app.api.search import get_cache_service
    cache = get_cache_service()
    if cache:
        await cache.invalidate_search()
        await cache.invalidate_stats()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


@router.get("/documents")
async def list_documents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    source: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """문서 목록 (페이징)."""
    query = select(Document)

    if source:
        query = query.where(Document.source == source)

    # 정렬
    sort_col = getattr(Document, sort, Document.created_at)
    if order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # 전체 수
    count_query = select(func.count()).select_from(Document)
    if source:
        count_query = count_query.where(Document.source == source)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 페이징
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    result = await db.execute(query)
    docs = result.scalars().all()

    return {
        "items": [_doc_to_dict(d) for d in docs],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 0,
    }


@router.post("/documents/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """파일 업로드 → 즉시 응답 + 비동기 인덱싱."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 파일 저장
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "unknown")[1]
    saved_filename = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    file_size = len(content)
    file_type = ext.lstrip(".") if ext else "unknown"

    # DB 저장
    doc = Document(
        filename=file.filename or "unknown",
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        status=DocumentStatus.UPLOADED,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Celery 비동기 인덱싱 (import 지연 — Celery 미기동 시에도 API 작동)
    try:
        from app.tasks.indexing import index_document_task
        index_document_task.delay(str(doc.id))
        status = "indexing"
    except Exception:
        status = "uploaded"

    await _invalidate_document_caches()
    return {"id": str(doc.id), "status": status, "filename": doc.filename}


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    """문서 상세."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise DocumentNotFoundError(f"Document {doc_id} not found")
    return _doc_to_dict(doc)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    """문서 삭제."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise DocumentNotFoundError(f"Document {doc_id} not found")

    # 파일 삭제
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    await db.commit()
    await _invalidate_document_caches()
    return {"message": "deleted", "id": doc_id}


@router.post("/documents/{doc_id}/reindex")
async def reindex_document(doc_id: str, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    """단일 문서 재인덱싱."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise DocumentNotFoundError(f"Document {doc_id} not found")

    try:
        from app.tasks.indexing import index_document_task
        index_document_task.delay(str(doc.id))
    except Exception:
        pass

    await _invalidate_document_caches()
    return {"id": doc_id, "status": "reindexing"}


@router.get("/documents/{doc_id}/chunks")
async def get_document_chunks(doc_id: str, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    """청크 목록."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise DocumentNotFoundError(f"Document {doc_id} not found")

    from app.models.database import Chunk
    result = await db.execute(
        select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)
    )
    chunks = result.scalars().all()

    return {
        "document_id": str(doc.id),
        "chunks": [
            {
                "id": str(c.id),
                "chunk_index": c.chunk_index,
                "content": c.content,
                "metadata": c.metadata_,
            }
            for c in chunks
        ],
    }


def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_path": doc.file_path,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "status": doc.status if isinstance(doc.status, str) else doc.status.value,
        "chunk_count": doc.chunk_count,
        "source": getattr(doc, "source", "upload"),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }
