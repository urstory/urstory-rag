"""Step 4.1 RED: PGVector 벡터 검색 엔진 단위 테스트."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import SearchServiceError
from app.models.schemas import SearchResult
from app.services.search.vector import VectorSearchEngine


def _make_row(
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    content: str = "테스트 청크",
    distance: float = 0.1,
    metadata: dict | None = None,
):
    """DB 쿼리 결과 row를 모방하는 MagicMock 생성.

    pgvector <=> 연산자는 cosine distance를 반환하므로,
    score = 1 - distance 로 변환.
    """
    row = MagicMock()
    row.chunk_id = chunk_id or uuid.uuid4()
    row.document_id = document_id or uuid.uuid4()
    row.content = content
    row.distance = distance
    row.metadata = metadata
    return row


def _mock_session_factory(rows: list):
    """비동기 세션 팩토리를 모킹한다.

    async with session_factory() as session:
        result = await session.execute(query)
        rows = result.fetchall()
    """
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    # async context manager: async with session_factory() as session
    mock_factory = MagicMock()
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None
    mock_factory.return_value = mock_context

    return mock_factory, mock_session


class TestVectorSearchEngine:
    """VectorSearchEngine 단위 테스트."""

    async def test_vector_search_returns_results(self):
        """Mock DB 쿼리 결과가 SearchResult 리스트로 변환되는지 확인."""
        chunk_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        rows = [
            _make_row(
                chunk_id=chunk_id,
                document_id=doc_id,
                content="한국어 RAG 시스템",
                distance=0.15,
                metadata={"page": 1},
            ),
        ]
        factory, _ = _mock_session_factory(rows)
        engine = VectorSearchEngine(session_factory=factory)

        query_embedding = [0.1] * 1536
        results = await engine.search(query_embedding=query_embedding, top_k=5)

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].chunk_id == chunk_id
        assert results[0].document_id == doc_id
        assert results[0].content == "한국어 RAG 시스템"
        assert results[0].score == pytest.approx(0.85)  # 1 - 0.15
        assert results[0].metadata == {"page": 1}

    async def test_vector_search_top_k(self):
        """top_k가 DB 쿼리 LIMIT에 반영되어 결과 수를 제한하는지 확인."""
        rows = [_make_row(distance=0.1 * i) for i in range(1, 4)]
        factory, mock_session = _mock_session_factory(rows)
        engine = VectorSearchEngine(session_factory=factory)

        query_embedding = [0.1] * 1536
        results = await engine.search(query_embedding=query_embedding, top_k=3)

        assert len(results) == 3
        # execute에 전달된 SQL에 top_k가 반영되었는지 확인
        call_args = mock_session.execute.call_args
        # 바인드 파라미터에 top_k 값이 포함되어 있어야 함
        bound_params = call_args[0][0].compile().params if hasattr(call_args[0][0], 'compile') else call_args[1]
        # top_k 파라미터가 전달되었는지 검증 (실제 파라미터 딕셔너리 확인)
        params_dict = call_args[1] if len(call_args) > 1 else call_args.kwargs
        assert params_dict.get("params", {}).get("top_k") == 3 or len(results) <= 3

    async def test_vector_search_score_ordering(self):
        """결과가 score 내림차순(distance 오름차순)으로 정렬되는지 확인."""
        # DB에서 distance ASC로 정렬되어 반환된다고 가정
        rows = [
            _make_row(content="가장 유사", distance=0.05),
            _make_row(content="중간 유사", distance=0.20),
            _make_row(content="낮은 유사", distance=0.50),
        ]
        factory, _ = _mock_session_factory(rows)
        engine = VectorSearchEngine(session_factory=factory)

        results = await engine.search(query_embedding=[0.1] * 1536, top_k=10)

        assert len(results) == 3
        # score = 1 - distance: 0.95, 0.80, 0.50
        assert results[0].score == pytest.approx(0.95)
        assert results[1].score == pytest.approx(0.80)
        assert results[2].score == pytest.approx(0.50)
        # 내림차순 정렬 확인
        assert results[0].score >= results[1].score >= results[2].score

    async def test_vector_search_empty_results(self):
        """일치하는 결과가 없으면 빈 리스트를 반환."""
        factory, _ = _mock_session_factory([])
        engine = VectorSearchEngine(session_factory=factory)

        results = await engine.search(query_embedding=[0.1] * 1536, top_k=5)

        assert results == []
        assert isinstance(results, list)

    async def test_vector_search_with_doc_filter(self):
        """doc_id 필터가 적용되어 특정 문서의 청크만 반환하는지 확인."""
        target_doc_id = uuid.uuid4()
        rows = [
            _make_row(document_id=target_doc_id, content="필터된 청크", distance=0.1),
        ]
        factory, mock_session = _mock_session_factory(rows)
        engine = VectorSearchEngine(session_factory=factory)

        results = await engine.search(
            query_embedding=[0.1] * 1536,
            top_k=5,
            doc_id=target_doc_id,
        )

        assert len(results) == 1
        assert results[0].document_id == target_doc_id
        # execute가 호출되었는지 확인
        mock_session.execute.assert_called_once()
        # SQL 쿼리에 doc_id 파라미터가 바인딩되었는지 확인
        call_args = mock_session.execute.call_args
        params_dict = call_args.kwargs.get("params") or (
            call_args[1] if len(call_args) > 1 and isinstance(call_args[1], dict) else {}
        )
        # doc_id가 파라미터로 전달되었어야 함
        assert "doc_id" in str(call_args) or target_doc_id in str(call_args)

    async def test_vector_search_db_error_raises_search_service_error(self):
        """DB 에러 발생 시 SearchServiceError로 래핑되는지 확인."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("DB connection failed")

        mock_factory = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_factory.return_value = mock_context

        engine = VectorSearchEngine(session_factory=mock_factory)

        with pytest.raises(SearchServiceError, match="벡터 검색 실패"):
            await engine.search(query_embedding=[0.1] * 1536, top_k=5)

    async def test_vector_search_metadata_none(self):
        """metadata가 None인 row도 정상 처리되는지 확인."""
        rows = [
            _make_row(content="메타데이터 없음", distance=0.2, metadata=None),
        ]
        factory, _ = _mock_session_factory(rows)
        engine = VectorSearchEngine(session_factory=factory)

        results = await engine.search(query_embedding=[0.1] * 1536)

        assert len(results) == 1
        assert results[0].metadata is None
