"""Circuit Breaker + Retry 모듈 단위 테스트.

⚡ 지훈: TDD RED → GREEN → REFACTOR
🔒 민수: Circuit Breaker 설정값 안전성 검증
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import (
    CircuitBreakerOpenError,
    EmbeddingServiceError,
    SearchServiceError,
)
from app.services.resilience import (
    CircuitBreaker,
    CircuitState,
    with_retry,
)

# 테스트용 UUID
_UUID1 = uuid.uuid4()
_UUID2 = uuid.uuid4()


# ──────────────────────────────────────────────────────
# CircuitBreaker 단위 테스트
# ──────────────────────────────────────────────────────

class TestCircuitBreaker:
    """Circuit Breaker 상태 전이 검증."""

    def test_initial_state_is_closed(self):
        """초기 상태는 CLOSED."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_on_success(self):
        """성공 호출 시 CLOSED 유지."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_opens_after_failure_threshold(self):
        """연속 실패가 threshold에 도달하면 OPEN."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_does_not_open_before_threshold(self):
        """threshold 미만에서는 CLOSED 유지."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        """성공 시 failure_count 초기화."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_open_circuit_denies_request(self):
        """OPEN 상태에서 allow_request()는 False."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        for _ in range(3):
            cb.record_failure()
        assert not cb.allow_request()

    def test_half_open_after_recovery_timeout(self):
        """recovery_timeout 이후 HALF_OPEN 전이."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        import time
        time.sleep(0.15)

        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request()  # HALF_OPEN에서는 1회 허용

    def test_half_open_success_closes_circuit(self):
        """HALF_OPEN에서 성공 시 CLOSED로 전이."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        for _ in range(3):
            cb.record_failure()

        import time
        time.sleep(0.15)

        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens_circuit(self):
        """HALF_OPEN에서 실패 시 다시 OPEN."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        for _ in range(3):
            cb.record_failure()

        import time
        time.sleep(0.15)

        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_circuit_breaker_name(self):
        """Circuit Breaker에 이름 설정."""
        cb = CircuitBreaker(name="openai", failure_threshold=5, recovery_timeout=30.0)
        assert cb.name == "openai"

    def test_circuit_breaker_stats(self):
        """통계 정보 반환."""
        cb = CircuitBreaker(name="openai", failure_threshold=5, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        stats = cb.stats()
        assert stats["name"] == "openai"
        assert stats["state"] == "CLOSED"
        assert stats["failure_count"] == 2
        assert stats["failure_threshold"] == 5


# ──────────────────────────────────────────────────────
# with_retry 데코레이터 테스트
# ──────────────────────────────────────────────────────

class TestWithRetry:
    """재시도 데코레이터 검증."""

    @pytest.mark.asyncio
    async def test_succeeds_without_retry(self):
        """정상 호출 시 재시도 없이 성공."""
        mock_fn = AsyncMock(return_value="ok")

        @with_retry(max_retries=3, retryable_exceptions=(Exception,))
        async def call():
            return await mock_fn()

        result = await call()
        assert result == "ok"
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable_exception(self):
        """재시도 가능한 예외 시 재시도 후 성공."""
        mock_fn = AsyncMock(
            side_effect=[SearchServiceError("rate limit"), "ok"]
        )

        @with_retry(
            max_retries=3,
            retryable_exceptions=(SearchServiceError,),
            base_delay=0.01,
        )
        async def call():
            return await mock_fn()

        result = await call()
        assert result == "ok"
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """max_retries 초과 시 최종 예외 발생."""
        mock_fn = AsyncMock(
            side_effect=SearchServiceError("always fails")
        )

        @with_retry(
            max_retries=3,
            retryable_exceptions=(SearchServiceError,),
            base_delay=0.01,
        )
        async def call():
            return await mock_fn()

        with pytest.raises(SearchServiceError, match="always fails"):
            await call()
        assert mock_fn.call_count == 4  # 1 initial + 3 retries

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_exception(self):
        """재시도 불가능한 예외 시 즉시 발생."""
        mock_fn = AsyncMock(
            side_effect=ValueError("bad input")
        )

        @with_retry(
            max_retries=3,
            retryable_exceptions=(SearchServiceError,),
            base_delay=0.01,
        )
        async def call():
            return await mock_fn()

        with pytest.raises(ValueError, match="bad input"):
            await call()
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker(self):
        """Circuit Breaker 연동 - OPEN 시 즉시 CircuitBreakerOpenError."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0)

        @with_retry(
            max_retries=3,
            retryable_exceptions=(SearchServiceError,),
            base_delay=0.01,
            circuit_breaker=cb,
        )
        async def call():
            raise SearchServiceError("fail")

        # 첫 호출: 4회 (1 + 3 retries) 시도 후 실패, CB failure_count = 1
        with pytest.raises(SearchServiceError):
            await call()
        assert cb.failure_count == 1

        # 두 번째 호출: 재시도 후 실패, CB failure_count = 2 → OPEN
        with pytest.raises(SearchServiceError):
            await call()
        assert cb.state == CircuitState.OPEN

        # 세 번째 호출: CB OPEN이므로 즉시 CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await call()


# ──────────────────────────────────────────────────────
# OpenAI 서비스 재시도 통합 테스트
# ──────────────────────────────────────────────────────

class TestOpenAIEmbeddingResilience:
    """OpenAI 임베딩 서비스 재시도 + Circuit Breaker 검증."""

    @pytest.mark.asyncio
    async def test_embedding_retries_on_rate_limit(self):
        """429 Rate Limit 시 재시도 후 성공."""
        from openai import RateLimitError
        from app.services.embedding.openai import OpenAIEmbedding

        embedder = OpenAIEmbedding(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.data = [AsyncMock(embedding=[0.1] * 1536)]

        with patch.object(
            embedder.client.embeddings, "create",
            new_callable=AsyncMock,
            side_effect=[
                RateLimitError(
                    message="Rate limit exceeded",
                    response=AsyncMock(status_code=429, headers={}),
                    body=None,
                ),
                mock_response,
            ],
        ):
            result = await embedder.embed_query("테스트 쿼리")
            assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_embedding_circuit_breaker_opens(self):
        """연속 실패 시 Circuit Breaker 열림."""
        from openai import APIError
        from app.services.embedding.openai import OpenAIEmbedding

        embedder = OpenAIEmbedding(api_key="test-key")
        # Circuit breaker 직접 검증
        embedder._circuit_breaker.failure_threshold = 2

        with patch.object(
            embedder.client.embeddings, "create",
            new_callable=AsyncMock,
            side_effect=APIError(
                message="Server error",
                request=AsyncMock(),
                body=None,
            ),
        ):
            # 첫 호출: 재시도 후 실패 → CB에 실패 기록
            for _ in range(2):
                with pytest.raises(EmbeddingServiceError):
                    await embedder.embed_query("test")

        # CB가 열려있으므로 즉시 차단
        with pytest.raises(CircuitBreakerOpenError):
            await embedder.embed_query("test")


class TestOpenAILLMResilience:
    """OpenAI LLM 서비스 재시도 + Circuit Breaker 검증."""

    @pytest.mark.asyncio
    async def test_llm_retries_on_server_error(self):
        """500/503 에러 시 재시도 후 성공."""
        from openai import APIStatusError
        from app.services.generation.openai import OpenAILLM

        llm = OpenAILLM(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(message=AsyncMock(content="답변 내용"))
        ]

        error_response = AsyncMock()
        error_response.status_code = 503
        error_response.headers = {}
        error_response.json.return_value = {"error": {"message": "Overloaded"}}

        with patch.object(
            llm.client.chat.completions, "create",
            new_callable=AsyncMock,
            side_effect=[
                APIStatusError(
                    message="Service unavailable",
                    response=error_response,
                    body=None,
                ),
                mock_response,
            ],
        ):
            result = await llm.generate("테스트 프롬프트")
            assert result == "답변 내용"


# ──────────────────────────────────────────────────────
# Elasticsearch 재시도 테스트
# ──────────────────────────────────────────────────────

class TestElasticsearchResilience:
    """Elasticsearch 키워드 검색 재시도 검증."""

    @pytest.mark.asyncio
    async def test_es_retries_on_connection_error(self):
        """ES 연결 실패 시 재시도 후 성공."""
        import httpx
        from app.services.search.keyword_es import ElasticsearchNoriEngine

        engine = ElasticsearchNoriEngine()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"hits": {"hits": []}})

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                httpx.ConnectError("Connection refused"),
                mock_response,
            ]
            results = await engine.search("테스트")
            assert results == []
            assert mock_post.call_count == 2


# ──────────────────────────────────────────────────────
# Graceful Degradation 테스트
# ──────────────────────────────────────────────────────

class TestGracefulDegradation:
    """파이프라인 단계별 실패 시 우아한 성능저하."""

    @pytest.mark.asyncio
    async def test_reranking_failure_returns_basic_results(self):
        """리랭킹 실패 → 기본 검색 결과 반환."""
        from app.services.search.hybrid import HybridSearchOrchestrator
        from app.models.schemas import SearchResult
        from app.config import RAGSettings

        # Mock 설정
        mock_embedder = AsyncMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1536)

        mock_vector = AsyncMock()
        mock_vector.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id=_UUID1, document_id=_UUID2,
                content="검색 결과", score=0.8,
            ),
        ])

        mock_keyword = AsyncMock()
        mock_keyword.search = AsyncMock(return_value=[])

        mock_reranker = AsyncMock()
        mock_reranker.rerank = AsyncMock(
            side_effect=Exception("리랭커 메모리 부족")
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="답변")

        mock_hyde = AsyncMock()
        mock_hyde.should_apply = lambda *a: False

        orchestrator = HybridSearchOrchestrator(
            embedder=mock_embedder,
            vector_engine=mock_vector,
            keyword_engine=mock_keyword,
            reranker=mock_reranker,
            hyde_generator=mock_hyde,
            llm=mock_llm,
        )

        settings = RAGSettings(
            reranking_enabled=True,
            search_mode="vector",
        )

        result = await orchestrator.search("테스트 쿼리", settings)

        # 리랭킹 실패해도 기본 검색 결과로 답변 생성
        assert len(result.documents) > 0
        assert result.answer == "답변"

        # 트레이스에서 리랭킹 실패 기록 확인
        reranking_step = next(
            (s for s in result.trace if s.name == "reranking"), None
        )
        assert reranking_step is not None
        assert not reranking_step.passed

    @pytest.mark.asyncio
    async def test_hyde_failure_uses_original_query(self):
        """HyDE 실패 → 원본 쿼리로 검색."""
        from app.services.search.hybrid import HybridSearchOrchestrator
        from app.models.schemas import SearchResult
        from app.config import RAGSettings

        mock_embedder = AsyncMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1536)

        mock_vector = AsyncMock()
        mock_vector.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id=_UUID1, document_id=_UUID2,
                content="결과", score=0.9,
            ),
        ])

        mock_keyword = AsyncMock()
        mock_keyword.search = AsyncMock(return_value=[])

        mock_reranker = AsyncMock()
        mock_hyde = AsyncMock()
        mock_hyde.should_apply = lambda *a: True
        mock_hyde.generate = AsyncMock(
            side_effect=Exception("HyDE LLM timeout")
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="답변")

        orchestrator = HybridSearchOrchestrator(
            embedder=mock_embedder,
            vector_engine=mock_vector,
            keyword_engine=mock_keyword,
            reranker=mock_reranker,
            hyde_generator=mock_hyde,
            llm=mock_llm,
        )

        settings = RAGSettings(
            hyde_enabled=True,
            search_mode="vector",
            reranking_enabled=False,
            multi_query_enabled=False,
            retrieval_quality_gate_enabled=False,
            injection_detection_enabled=False,
            pii_detection_enabled=False,
            faithfulness_enabled=False,
            hallucination_detection_enabled=False,
            numeric_verification_enabled=False,
        )

        result = await orchestrator.search("원본 쿼리", settings)

        # HyDE 실패해도 원본 쿼리로 검색 성공
        assert len(result.documents) > 0

        # embed_query가 원본 쿼리로 호출됨
        mock_embedder.embed_query.assert_called_with("원본 쿼리")

        # 트레이스에서 HyDE 실패 기록
        hyde_step = next(
            (s for s in result.trace if s.name == "hyde"), None
        )
        assert hyde_step is not None
        assert not hyde_step.passed

    @pytest.mark.asyncio
    async def test_langfuse_failure_continues_pipeline(self):
        """Langfuse 실패 → 로그만 남기고 파이프라인 계속."""
        from app.monitoring.langfuse import LangfuseMonitor

        monitor = LangfuseMonitor(
            public_key="test-pk",
            secret_key="test-sk",
        )
        # 강제 활성화 후 내부 langfuse 객체에서 에러 발생
        monitor.enabled = True
        monitor._langfuse = AsyncMock()
        monitor._langfuse.start_span.side_effect = Exception("Langfuse down")

        # create_trace에서 예외가 발생해도 _NoOp 반환
        result = monitor.create_trace("test-trace", "input")
        # NoOp이므로 어떤 메서드 호출도 안전
        result.update(output="test")
        result.end()
