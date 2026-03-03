"""Step 4.5: 리랭킹 서비스 단위 테스트 (RED → GREEN)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.models.schemas import SearchResult
from app.services.reranking.base import Reranker
from app.services.reranking.korean import KoreanCrossEncoder


def _make_search_result(
    content: str = "테스트 문서",
    score: float = 0.5,
    metadata: dict | None = None,
) -> SearchResult:
    """테스트용 SearchResult 팩토리."""
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        score=score,
        metadata=metadata,
    )


@pytest.fixture
def mock_cross_encoder():
    """CrossEncoder 모델 Mock (실제 모델 로딩 방지)."""
    with patch(
        "app.services.reranking.korean.CrossEncoder"
    ) as mock_cls:
        mock_model = MagicMock()
        mock_cls.return_value = mock_model
        yield mock_model


class TestRerankerProtocol:
    """Reranker Protocol 준수 테스트."""

    def test_reranker_protocol(self, mock_cross_encoder):
        """KoreanCrossEncoder가 Reranker Protocol을 구현하는지 검증."""
        reranker = KoreanCrossEncoder()
        assert isinstance(reranker, Reranker)


class TestKoreanCrossEncoder:
    """KoreanCrossEncoder 구현 테스트."""

    @pytest.mark.asyncio
    async def test_korean_reranker_top_k(self, mock_cross_encoder):
        """20개 입력 문서 → top_k=5 → 5개 출력 확인."""
        # Arrange: 20개 문서 생성
        documents = [
            _make_search_result(content=f"한국어 문서 {i}", score=0.5)
            for i in range(20)
        ]
        # Mock: 20개 문서에 대해 서로 다른 점수 반환
        mock_cross_encoder.predict.return_value = np.arange(20, dtype=np.float32)

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(query="테스트 쿼리", documents=documents, top_k=5)

        # Assert
        assert len(results) == 5
        # predict가 20개 (query, content) 쌍으로 호출되었는지 확인
        mock_cross_encoder.predict.assert_called_once()
        pairs = mock_cross_encoder.predict.call_args[0][0]
        assert len(pairs) == 20
        assert all(pair[0] == "테스트 쿼리" for pair in pairs)

    @pytest.mark.asyncio
    async def test_korean_reranker_score_ordering(self, mock_cross_encoder):
        """출력이 리랭커 점수 기준 내림차순 정렬되는지 확인."""
        # Arrange: 5개 문서, 무작위 점수
        documents = [
            _make_search_result(content=f"문서 {i}", score=0.5)
            for i in range(5)
        ]
        # Mock: 역순 점수 (0번 문서가 가장 낮은 점수, 4번이 가장 높은 점수)
        mock_cross_encoder.predict.return_value = np.array(
            [0.1, 0.9, 0.3, 0.7, 0.5], dtype=np.float32
        )

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(
            query="쿼리", documents=documents, top_k=5, score_mode="replace",
        )

        # Assert: 내림차순 정렬 확인
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        # 가장 높은 점수가 첫 번째
        assert results[0].score == pytest.approx(0.9)
        assert results[-1].score == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_korean_reranker_preserves_metadata(self, mock_cross_encoder):
        """리랭킹 후 원본 메타데이터가 보존되는지 확인."""
        # Arrange: 고유한 메타데이터를 가진 문서
        metadata_list = [
            {"source": "wiki", "page": 1},
            {"source": "blog", "author": "김철수"},
            {"source": "paper", "doi": "10.1234/test"},
        ]
        documents = [
            _make_search_result(
                content=f"메타데이터 테스트 문서 {i}",
                score=0.5,
                metadata=metadata_list[i],
            )
            for i in range(3)
        ]
        # Mock: 역순 점수로 정렬 변경
        mock_cross_encoder.predict.return_value = np.array(
            [0.3, 0.1, 0.9], dtype=np.float32
        )

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(query="쿼리", documents=documents, top_k=3)

        # Assert: 가장 높은 점수(0.9)인 문서 2가 첫 번째
        assert results[0].metadata == {"source": "paper", "doi": "10.1234/test"}
        assert results[1].metadata == {"source": "wiki", "page": 1}
        assert results[2].metadata == {"source": "blog", "author": "김철수"}

        # chunk_id, document_id도 보존 확인
        result_chunk_ids = {r.chunk_id for r in results}
        original_chunk_ids = {d.chunk_id for d in documents}
        assert result_chunk_ids == original_chunk_ids

    @pytest.mark.asyncio
    async def test_korean_reranker_empty_input(self, mock_cross_encoder):
        """빈 입력 → 빈 출력 확인 (모델 호출 없음)."""
        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(query="쿼리", documents=[], top_k=5)

        assert results == []
        # 빈 입력일 때 모델이 호출되지 않아야 함
        mock_cross_encoder.predict.assert_not_called()


class TestKoreanCrossEncoderCalibrated:
    """Sigmoid 보정 + 점수 결합 테스트."""

    @pytest.mark.asyncio
    async def test_sigmoid_applied_scores_in_0_1(self, mock_cross_encoder):
        """calibrated 모드에서 최종 점수가 [0,1] 범위에 있는지 확인."""
        documents = [
            _make_search_result(content="문서 A", score=0.01),
            _make_search_result(content="문서 B", score=0.008),
        ]
        mock_cross_encoder.predict.return_value = np.array([0.0, 2.0], dtype=np.float32)

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(
            query="쿼리", documents=documents, top_k=2,
            score_mode="calibrated", alpha=0.7,
        )

        for r in results:
            assert 0.0 <= r.score <= 1.0

    @pytest.mark.asyncio
    async def test_calibrated_preserves_ce_ordering(self, mock_cross_encoder):
        """CE logit이 높은 문서가 상위에 위치."""
        documents = [
            _make_search_result(content="문서 A", score=0.01),
            _make_search_result(content="문서 B", score=0.008),
        ]
        # B(logit=2.0)가 A(logit=0.0)보다 높아야 함
        mock_cross_encoder.predict.return_value = np.array([0.0, 2.0], dtype=np.float32)

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(
            query="쿼리", documents=documents, top_k=2,
            score_mode="calibrated", alpha=0.7,
        )

        assert results[0].content == "문서 B"
        assert results[0].score > results[1].score

    @pytest.mark.asyncio
    async def test_rank_signal_breaks_tie(self, mock_cross_encoder):
        """CE 점수 동일 시 원래 CE rank가 높은 문서가 상위."""
        documents = [
            _make_search_result(content="문서 A", score=0.01),
            _make_search_result(content="문서 B", score=0.008),
        ]
        # 동일한 CE logit
        mock_cross_encoder.predict.return_value = np.array([0.0, 0.0], dtype=np.float32)

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(
            query="쿼리", documents=documents, top_k=2,
            score_mode="calibrated", alpha=0.7,
        )

        # 둘 다 sigmoid(0)=0.5이지만 rank_score가 다름
        # rank 0: 0.7*0.5 + 0.3*1.0 = 0.65
        # rank 1: 0.7*0.5 + 0.3*0.5 = 0.50
        assert results[0].score > results[1].score

    @pytest.mark.asyncio
    async def test_replace_mode_raw_logit(self, mock_cross_encoder):
        """replace 모드에서 raw logit 그대로 반환."""
        documents = [
            _make_search_result(content="문서 A", score=0.01),
        ]
        mock_cross_encoder.predict.return_value = np.array([0.037], dtype=np.float32)

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(
            query="쿼리", documents=documents, top_k=1,
            score_mode="replace", alpha=0.7,
        )

        assert results[0].score == pytest.approx(0.037)

    @pytest.mark.asyncio
    async def test_alpha_one_pure_sigmoid(self, mock_cross_encoder):
        """alpha=1이면 sigmoid(CE)만 사용, rank 무시."""
        documents = [
            _make_search_result(content="문서 A", score=0.01),
        ]
        mock_cross_encoder.predict.return_value = np.array([0.0], dtype=np.float32)

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(
            query="쿼리", documents=documents, top_k=1,
            score_mode="calibrated", alpha=1.0,
        )

        # sigmoid(0) = 0.5
        assert results[0].score == pytest.approx(0.5, abs=0.01)

    @pytest.mark.asyncio
    async def test_alpha_zero_pure_rank(self, mock_cross_encoder):
        """alpha=0이면 rank_score만 사용."""
        documents = [
            _make_search_result(content="문서 A", score=0.01),
            _make_search_result(content="문서 B", score=0.008),
        ]
        mock_cross_encoder.predict.return_value = np.array([5.0, -5.0], dtype=np.float32)

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(
            query="쿼리", documents=documents, top_k=2,
            score_mode="calibrated", alpha=0.0,
        )

        # CE로 정렬 후 rank_score만 사용: rank 0 → 1.0, rank 1 → 0.5
        assert results[0].score == pytest.approx(1.0)
        assert results[1].score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_fail_case_q29_passes_gate_threshold(self, mock_cross_encoder):
        """Q29 재현: CE raw=0.10 → calibrated 후 min_top_score(0.3) 통과."""
        documents = [
            _make_search_result(content="봉사활동 관련 문서", score=0.01),
        ]
        mock_cross_encoder.predict.return_value = np.array([0.10], dtype=np.float32)

        reranker = KoreanCrossEncoder()
        results = await reranker.rerank(
            query="봉사활동", documents=documents, top_k=1,
            score_mode="calibrated", alpha=0.7,
        )

        # sigmoid(0.10)≈0.525, rank_score=1.0
        # combined = 0.7*0.525 + 0.3*1.0 = 0.6675
        assert results[0].score > 0.3  # Gate min_top_score 통과
