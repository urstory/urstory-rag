"""무중단 전체 재인덱싱 서비스."""
import uuid
from datetime import datetime


class ReindexService:
    """새 인덱스 생성 → 배치 인덱싱 → alias 전환."""

    def __init__(self, indexer=None):
        self.indexer = indexer

    async def start_reindex(self) -> str:
        """재인덱싱 시작, task_id 반환."""
        task_id = str(uuid.uuid4())
        # 실제 구현: Celery 태스크로 비동기 실행
        # 1. 새 ES 인덱스 생성 (rag_documents_{timestamp})
        # 2. 모든 문서를 새 인덱스에 배치 인덱싱
        # 3. alias 전환
        # 4. 이전 인덱스 정리
        return task_id
