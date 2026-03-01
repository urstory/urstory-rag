"""Step 4.4: RRF (Reciprocal Rank Fusion) 단위 테스트 (RED → GREEN)."""
from __future__ import annotations

import uuid

import pytest

from app.models.schemas import SearchResult
from app.services.search.rrf import RRFCombiner


# 재사용 가능한 고정 UUID
UUID_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
UUID_B = uuid.UUID("00000000-0000-0000-0000-000000000002")
UUID_C = uuid.UUID("00000000-0000-0000-0000-000000000003")
UUID_D = uuid.UUID("00000000-0000-0000-0000-000000000004")
UUID_E = uuid.UUID("00000000-0000-0000-0000-000000000005")

DOC_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")


def _make_result(chunk_id: uuid.UUID, content: str, score: float = 0.0) -> SearchResult:
    """테스트용 SearchResult 생성 헬퍼."""
    return SearchResult(
        chunk_id=chunk_id,
        document_id=DOC_ID,
        content=content,
        score=score,
    )


class TestRRFCombiner:
    """RRF 결합 알고리즘 단위 테스트."""

    def setup_method(self):
        self.combiner = RRFCombiner()

    def test_rrf_combine_two_lists(self):
        """두 결과 리스트 → RRF 스코어로 결합."""
        vector_results = [
            _make_result(UUID_A, "벡터 결과 A", 0.95),
            _make_result(UUID_B, "벡터 결과 B", 0.80),
        ]
        keyword_results = [
            _make_result(UUID_C, "키워드 결과 C", 12.5),
            _make_result(UUID_D, "키워드 결과 D", 8.3),
        ]

        combined = self.combiner.combine(vector_results, keyword_results, k=60)

        # 총 4개의 고유 chunk → 결과 4개
        assert len(combined) == 4

        chunk_ids = [r.chunk_id for r in combined]
        assert UUID_A in chunk_ids
        assert UUID_B in chunk_ids
        assert UUID_C in chunk_ids
        assert UUID_D in chunk_ids

        # RRF 스코어가 부여되어야 함 (원래 스코어가 아닌 RRF 스코어)
        for r in combined:
            assert r.score > 0

    def test_rrf_dedup(self):
        """중복 chunk_id가 양쪽 리스트에 있으면 → 합산 스코어로 단일 항목."""
        vector_results = [
            _make_result(UUID_A, "벡터에서 A", 0.95),
            _make_result(UUID_B, "벡터에서 B", 0.80),
        ]
        keyword_results = [
            _make_result(UUID_A, "키워드에서 A", 15.0),  # UUID_A 중복
            _make_result(UUID_C, "키워드에서 C", 10.0),
        ]

        combined = self.combiner.combine(vector_results, keyword_results, k=60)

        # UUID_A는 한 번만 등장
        a_results = [r for r in combined if r.chunk_id == UUID_A]
        assert len(a_results) == 1

        # UUID_A의 RRF 스코어 = vector_weight/(k+0+1) + keyword_weight/(k+0+1)
        # 기본 weight 0.5/0.5, k=60 → 0.5/61 + 0.5/61 = 1.0/61
        expected_a_score = 0.5 / (60 + 0 + 1) + 0.5 / (60 + 0 + 1)
        assert abs(a_results[0].score - expected_a_score) < 1e-10

        # 총 고유 항목 3개
        assert len(combined) == 3

    def test_rrf_weight_adjustment(self):
        """vector_weight=0.7, keyword_weight=0.3 → 벡터 상위 결과에 더 높은 스코어."""
        vector_results = [
            _make_result(UUID_A, "벡터 1위", 0.99),
        ]
        keyword_results = [
            _make_result(UUID_B, "키워드 1위", 20.0),
        ]

        combined = self.combiner.combine(
            vector_results, keyword_results,
            k=60, vector_weight=0.7, keyword_weight=0.3,
        )

        a_result = next(r for r in combined if r.chunk_id == UUID_A)
        b_result = next(r for r in combined if r.chunk_id == UUID_B)

        # UUID_A: 0.7 / (60+0+1) = 0.7/61
        # UUID_B: 0.3 / (60+0+1) = 0.3/61
        expected_a = 0.7 / 61
        expected_b = 0.3 / 61

        assert abs(a_result.score - expected_a) < 1e-10
        assert abs(b_result.score - expected_b) < 1e-10

        # 벡터 가중치가 높으므로 A가 B보다 상위
        assert a_result.score > b_result.score

    def test_rrf_constant_k(self):
        """k 값이 달라지면 스코어 분포가 변경됨."""
        vector_results = [
            _make_result(UUID_A, "첫 번째", 0.9),
            _make_result(UUID_B, "두 번째", 0.5),
        ]
        keyword_results = []

        # k=60 (기본)
        result_k60 = self.combiner.combine(
            vector_results, keyword_results, k=60,
        )
        # k=1 (낮은 값 → rank 차이의 영향이 더 큼)
        result_k1 = self.combiner.combine(
            vector_results, keyword_results, k=1,
        )

        a_k60 = next(r for r in result_k60 if r.chunk_id == UUID_A)
        b_k60 = next(r for r in result_k60 if r.chunk_id == UUID_B)
        a_k1 = next(r for r in result_k1 if r.chunk_id == UUID_A)
        b_k1 = next(r for r in result_k1 if r.chunk_id == UUID_B)

        # k=60: 0.5/61 vs 0.5/62 → 비율 차이 작음
        ratio_k60 = a_k60.score / b_k60.score
        # k=1: 0.5/2 vs 0.5/3 → 비율 차이 큼
        ratio_k1 = a_k1.score / b_k1.score

        # k가 작을수록 순위 차이에 의한 스코어 격차가 커짐
        assert ratio_k1 > ratio_k60

        # 정확한 스코어 검증
        assert abs(a_k60.score - 0.5 / 61) < 1e-10
        assert abs(b_k60.score - 0.5 / 62) < 1e-10
        assert abs(a_k1.score - 0.5 / 2) < 1e-10
        assert abs(b_k1.score - 0.5 / 3) < 1e-10

    def test_rrf_empty_lists(self):
        """빈 입력 리스트 → 빈 결과."""
        combined = self.combiner.combine([], [])
        assert combined == []

    def test_rrf_single_list(self):
        """한쪽 리스트만 결과가 있어도 정상 동작."""
        vector_results = [
            _make_result(UUID_A, "벡터만 A", 0.9),
            _make_result(UUID_B, "벡터만 B", 0.7),
        ]

        # 키워드 결과 없음
        combined = self.combiner.combine(vector_results, [], k=60)

        assert len(combined) == 2

        a = next(r for r in combined if r.chunk_id == UUID_A)
        b = next(r for r in combined if r.chunk_id == UUID_B)

        # 벡터 결과만 있으므로 RRF 스코어 = 0.5 / (60 + rank + 1)
        assert abs(a.score - 0.5 / 61) < 1e-10
        assert abs(b.score - 0.5 / 62) < 1e-10

        # 순서: A가 B보다 높아야 함
        assert a.score > b.score

    def test_rrf_score_descending(self):
        """최종 결과는 RRF 스코어 내림차순 정렬."""
        vector_results = [
            _make_result(UUID_A, "벡터 A", 0.95),
            _make_result(UUID_B, "벡터 B", 0.80),
            _make_result(UUID_C, "벡터 C", 0.60),
        ]
        keyword_results = [
            _make_result(UUID_C, "키워드 C", 15.0),  # C가 키워드에서 1위 → 양쪽 스코어 합산
            _make_result(UUID_D, "키워드 D", 12.0),
            _make_result(UUID_E, "키워드 E", 8.0),
        ]

        combined = self.combiner.combine(vector_results, keyword_results, k=60)

        # 스코어가 내림차순인지 확인
        scores = [r.score for r in combined]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"결과가 내림차순이 아님: index {i} score={scores[i]} > "
                f"index {i+1} score={scores[i+1]}"
            )

        # UUID_C는 양쪽에 등장 → 합산 스코어가 가장 높아야 함
        # C의 RRF = 0.5/(60+2+1) + 0.5/(60+0+1) = 0.5/63 + 0.5/61
        assert combined[0].chunk_id == UUID_C

    def test_rrf_preserves_metadata(self):
        """RRF 결합 후에도 원본 metadata가 유지되는지 확인."""
        vector_results = [
            SearchResult(
                chunk_id=UUID_A,
                document_id=DOC_ID,
                content="메타데이터 포함",
                score=0.9,
                metadata={"source": "vector", "page": 1},
            ),
        ]
        keyword_results = []

        combined = self.combiner.combine(vector_results, keyword_results)

        assert combined[0].metadata == {"source": "vector", "page": 1}
        assert combined[0].content == "메타데이터 포함"
        assert combined[0].document_id == DOC_ID
