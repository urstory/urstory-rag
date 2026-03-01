"""Step 4.3: kiwipiepy + BM25 대안 키워드 검색 엔진 단위 테스트 (RED → GREEN)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.schemas import SearchResult
from app.services.search.keyword_kiwi import KiwipieyyBM25Engine


# ---------------------------------------------------------------------------
# Mock helpers -- kiwipiepy.Kiwi 를 CI에서 로드하지 않기 위한 가짜 토큰/Kiwi
# ---------------------------------------------------------------------------

class FakeToken:
    """kiwipiepy Token 을 흉내내는 단순 객체."""

    def __init__(self, form: str, tag: str):
        self.form = form
        self.tag = tag


def _make_fake_kiwi():
    """예측 가능한 한국어 형태소 분석 결과를 반환하는 Mock Kiwi."""
    kiwi = MagicMock()

    def fake_tokenize(text: str):
        """간이 한국어 토큰화: 미리 정의된 매핑 + 기본 폴백."""
        token_map: dict[str, list[FakeToken]] = {
            "한국어 자연어 처리는 중요합니다": [
                FakeToken("한국어", "NNP"),
                FakeToken("자연어", "NNP"),
                FakeToken("처리", "NNG"),
                FakeToken("는", "JX"),
                FakeToken("중요", "XR"),
                FakeToken("하", "VV"),
                FakeToken("ㅂ니다", "EF"),
            ],
            "형태소 분석 엔진 테스트": [
                FakeToken("형태소", "NNG"),
                FakeToken("분석", "NNG"),
                FakeToken("엔진", "NNG"),
                FakeToken("테스트", "NNG"),
            ],
            "벡터 임베딩 검색 시스템": [
                FakeToken("벡터", "NNG"),
                FakeToken("임베딩", "NNG"),
                FakeToken("검색", "NNG"),
                FakeToken("시스템", "NNG"),
            ],
            "한국어 형태소 분석": [
                FakeToken("한국어", "NNP"),
                FakeToken("형태소", "NNG"),
                FakeToken("분석", "NNG"),
            ],
            "검색": [
                FakeToken("검색", "NNG"),
            ],
            "형태소": [
                FakeToken("형태소", "NNG"),
            ],
            "완전히 무관한 쿼리": [
                FakeToken("완전히", "MAG"),
                FakeToken("무관", "XR"),
                FakeToken("한", "XSA"),
                FakeToken("쿼리", "NNG"),
            ],
        }
        if text in token_map:
            return token_map[text]
        # 폴백: 공백 분리 후 모두 NNG 처리
        return [FakeToken(w, "NNG") for w in text.split()]

    kiwi.tokenize = fake_tokenize
    return kiwi


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_kiwi():
    return _make_fake_kiwi()


@pytest.fixture
def sample_documents():
    """검색 대상 샘플 문서 리스트."""
    return [
        {
            "chunk_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "document_id": uuid.UUID("aaaa0000-0000-0000-0000-000000000001"),
            "content": "한국어 자연어 처리는 중요합니다",
            "metadata": {"source": "doc1.pdf"},
        },
        {
            "chunk_id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
            "document_id": uuid.UUID("aaaa0000-0000-0000-0000-000000000001"),
            "content": "형태소 분석 엔진 테스트",
            "metadata": {"source": "doc1.pdf"},
        },
        {
            "chunk_id": uuid.UUID("00000000-0000-0000-0000-000000000003"),
            "document_id": uuid.UUID("bbbb0000-0000-0000-0000-000000000002"),
            "content": "벡터 임베딩 검색 시스템",
            "metadata": {"source": "doc2.pdf"},
        },
    ]


@pytest.fixture
def engine(fake_kiwi):
    """Mock Kiwi가 주입된 KiwipieyyBM25Engine 인스턴스."""
    with patch("app.services.search.keyword_kiwi.Kiwi", return_value=fake_kiwi):
        eng = KiwipieyyBM25Engine()
    return eng


# ===========================================================================
# 테스트
# ===========================================================================

class TestKiwiTokenize:
    """kiwipiepy 형태소 분석으로 명사/동사/형용사만 추출하는지 검증."""

    def test_kiwi_tokenize(self, engine):
        """명사(N*), 동사(V*), 형용사(XR)만 추출하고 조사/어미는 제외."""
        tokens = engine._tokenize("한국어 자연어 처리는 중요합니다")

        # 명사: 한국어, 자연어, 처리
        assert "한국어" in tokens
        assert "자연어" in tokens
        assert "처리" in tokens
        # 형용사 어근 XR: 중요
        assert "중요" in tokens
        # 동사: 하
        assert "하" in tokens
        # 조사(JX)와 어미(EF)는 제외
        assert "는" not in tokens
        assert "ㅂ니다" not in tokens

    def test_kiwi_tokenize_empty(self, engine):
        """빈 문자열 토큰화 시 빈 리스트 반환."""
        tokens = engine._tokenize("")
        assert tokens == []


class TestKiwiBM25Search:
    """인덱스 구축 후 BM25 검색 동작 검증."""

    @pytest.mark.asyncio
    async def test_kiwi_bm25_search(self, engine, sample_documents):
        """인덱스 빌드 후 검색 시 결과가 반환되는지 확인."""
        engine.build_index(sample_documents)

        results = await engine.search("한국어 형태소 분석", top_k=5)

        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)
        # 쿼리와 가장 관련 높은 문서(형태소 분석 포함)가 결과에 존재
        chunk_ids = [r.chunk_id for r in results]
        assert uuid.UUID("00000000-0000-0000-0000-000000000002") in chunk_ids

    @pytest.mark.asyncio
    async def test_kiwi_bm25_top_k(self, engine, sample_documents):
        """top_k 파라미터가 결과 수를 제한하는지 확인."""
        engine.build_index(sample_documents)

        results = await engine.search("검색", top_k=1)

        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_kiwi_bm25_empty_index(self, engine):
        """빈 인덱스에서 검색 시 빈 결과 반환."""
        # build_index를 호출하지 않음
        results = await engine.search("한국어 형태소 분석")
        assert results == []

    @pytest.mark.asyncio
    async def test_kiwi_bm25_empty_documents(self, engine):
        """빈 문서 리스트로 인덱스 빌드 후 검색 시 빈 결과 반환."""
        engine.build_index([])
        results = await engine.search("한국어 형태소 분석")
        assert results == []

    @pytest.mark.asyncio
    async def test_kiwi_bm25_score_ordering(self, engine, sample_documents):
        """결과가 BM25 점수 내림차순으로 정렬되는지 확인."""
        engine.build_index(sample_documents)

        # "한국어 형태소 분석" → 토큰: 한국어, 형태소, 분석
        # doc1("한국어 자연어 처리는 중요합니다") → 한국어 매칭
        # doc2("형태소 분석 엔진 테스트") → 형태소, 분석 매칭
        # → 최소 2개 이상 매칭
        results = await engine.search("한국어 형태소 분석", top_k=10)

        assert len(results) >= 2
        # 점수가 내림차순인지 확인
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    @pytest.mark.asyncio
    async def test_kiwi_bm25_result_fields(self, engine, sample_documents):
        """SearchResult 필드가 올바르게 채워지는지 확인."""
        engine.build_index(sample_documents)

        results = await engine.search("형태소 분석 엔진 테스트", top_k=1)

        assert len(results) >= 1
        top = results[0]
        assert top.chunk_id == uuid.UUID("00000000-0000-0000-0000-000000000002")
        assert top.document_id == uuid.UUID("aaaa0000-0000-0000-0000-000000000001")
        assert top.content == "형태소 분석 엔진 테스트"
        assert top.score > 0.0
        assert top.metadata == {"source": "doc1.pdf"}

    @pytest.mark.asyncio
    async def test_kiwi_bm25_doc_id_filter(self, engine, sample_documents):
        """doc_id 필터로 특정 문서의 청크만 검색."""
        engine.build_index(sample_documents)

        doc_id = "bbbb0000-0000-0000-0000-000000000002"
        results = await engine.search("검색", top_k=10, doc_id=doc_id)

        # 필터된 문서의 청크만 반환
        for r in results:
            assert str(r.document_id) == doc_id

    @pytest.mark.asyncio
    async def test_kiwi_bm25_zero_score_excluded(self, engine, sample_documents):
        """BM25 점수가 0인 문서는 결과에서 제외."""
        engine.build_index(sample_documents)

        results = await engine.search("완전히 무관한 쿼리", top_k=10)

        # 점수가 0인 결과는 포함되지 않아야 함
        for r in results:
            assert r.score > 0.0
