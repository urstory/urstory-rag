"""Step 4.9 RED: Haystack 파이프라인 구성 단위 테스트.

build_search_pipeline 이 RAGSettings/Settings 에 따라
올바른 컴포넌트 그래프를 구성하는지 검증한다.

Haystack 컴포넌트는 __init__ 시 외부 연결을 하지 않으므로
DocumentStore 만 Mock 처리하고, 나머지는 실제 컴포넌트를 사용한다.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import RAGSettings, Settings
from app.pipelines.search import build_search_pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def env_settings() -> Settings:
    """테스트용 환경 설정."""
    return Settings(
        database_url="postgresql+asyncpg://admin:pw@localhost:5432/shared",
        elasticsearch_url="http://localhost:9200",
        ollama_url="http://localhost:11434",
    )


@pytest.fixture
def rag_settings_hybrid() -> RAGSettings:
    """하이브리드 모드 + 리랭킹 ON 기본 설정."""
    return RAGSettings(
        search_mode="hybrid",
        reranking_enabled=True,
        reranker_model="dragonkue/bge-reranker-v2-m3-ko",
        reranker_top_k=5,
        retriever_top_k=20,
        embedding_model="bge-m3",
        llm_model="qwen2.5:7b",
        llm_provider="ollama",
    )


@pytest.fixture
def rag_settings_vector() -> RAGSettings:
    """벡터 전용 모드 + 리랭킹 ON 설정."""
    return RAGSettings(
        search_mode="vector",
        reranking_enabled=True,
        reranker_model="dragonkue/bge-reranker-v2-m3-ko",
        reranker_top_k=5,
        retriever_top_k=20,
    )


@pytest.fixture
def rag_settings_keyword() -> RAGSettings:
    """키워드 전용 모드 + 리랭킹 ON 설정."""
    return RAGSettings(
        search_mode="keyword",
        reranking_enabled=True,
        reranker_model="dragonkue/bge-reranker-v2-m3-ko",
        reranker_top_k=5,
        retriever_top_k=20,
    )


# ---------------------------------------------------------------------------
# DocumentStore Mock (DB 연결 방지)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_document_stores():
    """DocumentStore 를 Mock 처리하여 실제 DB 연결을 방지한다.

    PgvectorDocumentStore 와 ElasticsearchDocumentStore 는
    __init__ 에서 연결을 시도할 수 있으므로 Mock 으로 대체.
    Retriever 는 store 의 타입만 검사하므로 spec 을 사용한다.
    """
    with (
        patch(
            "app.pipelines.search.PgvectorDocumentStore",
        ) as mock_pg_store_cls,
        patch(
            "app.pipelines.search.ElasticsearchDocumentStore",
        ) as mock_es_store_cls,
    ):
        # spec 기반 Mock 인스턴스 생성 (타입 검사 통과)
        from haystack_integrations.document_stores.pgvector import (
            PgvectorDocumentStore,
        )
        from haystack_integrations.document_stores.elasticsearch import (
            ElasticsearchDocumentStore,
        )

        pg_mock = MagicMock(spec=PgvectorDocumentStore)
        # PgvectorEmbeddingRetriever.__init__ 에서 참조하는 속성 설정
        pg_mock.vector_function = "cosine_similarity"
        mock_pg_store_cls.return_value = pg_mock

        mock_es_store_cls.return_value = MagicMock(spec=ElasticsearchDocumentStore)

        yield {
            "pg_store_cls": mock_pg_store_cls,
            "es_store_cls": mock_es_store_cls,
        }


# ---------------------------------------------------------------------------
# Helper: 파이프라인 그래프 검사 유틸
# ---------------------------------------------------------------------------

def _component_names(pipeline) -> set[str]:
    """파이프라인에 등록된 모든 컴포넌트 이름을 set 으로 반환."""
    return set(pipeline.graph.nodes)


def _has_edge(pipeline, sender: str, receiver: str) -> bool:
    """두 컴포넌트 간 연결(edge)이 존재하는지 확인."""
    for u, v, _key in pipeline.graph.edges:
        if u == sender and v == receiver:
            return True
    return False


# ---------------------------------------------------------------------------
# Tests: 리랭킹 ON/OFF
# ---------------------------------------------------------------------------


class TestBuildPipelineReranking:
    """리랭킹 ON/OFF 에 따른 파이프라인 구성 검증."""

    def test_build_pipeline_with_reranking(
        self, rag_settings_hybrid, env_settings
    ):
        """reranking_enabled=True → ranker 컴포넌트가 포함되어야 한다."""
        rag_settings_hybrid.reranking_enabled = True
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)

        names = _component_names(pipeline)
        assert "ranker" in names, (
            f"reranking_enabled=True 일 때 'ranker' 컴포넌트가 필요합니다. "
            f"현재 컴포넌트: {names}"
        )

    def test_build_pipeline_without_reranking(
        self, rag_settings_hybrid, env_settings
    ):
        """reranking_enabled=False → ranker 컴포넌트가 없어야 한다."""
        rag_settings_hybrid.reranking_enabled = False
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)

        names = _component_names(pipeline)
        assert "ranker" not in names, (
            f"reranking_enabled=False 일 때 'ranker' 컴포넌트가 없어야 합니다. "
            f"현재 컴포넌트: {names}"
        )


# ---------------------------------------------------------------------------
# Tests: 검색 모드 (vector / keyword / hybrid)
# ---------------------------------------------------------------------------


class TestBuildPipelineSearchMode:
    """search_mode 에 따른 retriever 구성 검증."""

    def test_build_pipeline_vector_mode(
        self, rag_settings_vector, env_settings
    ):
        """search_mode='vector' → vector_retriever만 포함, keyword_retriever 없음."""
        pipeline = build_search_pipeline(rag_settings_vector, env_settings)
        names = _component_names(pipeline)

        assert "query_embedder" in names, "벡터 모드에서 query_embedder 필수"
        assert "vector_retriever" in names, "벡터 모드에서 vector_retriever 필수"
        assert "keyword_retriever" not in names, (
            "벡터 모드에서 keyword_retriever 가 없어야 함"
        )
        assert "joiner" not in names, "벡터 모드에서 joiner 가 없어야 함"

    def test_build_pipeline_keyword_mode(
        self, rag_settings_keyword, env_settings
    ):
        """search_mode='keyword' → keyword_retriever만 포함, vector_retriever 없음."""
        pipeline = build_search_pipeline(rag_settings_keyword, env_settings)
        names = _component_names(pipeline)

        assert "keyword_retriever" in names, "키워드 모드에서 keyword_retriever 필수"
        assert "vector_retriever" not in names, (
            "키워드 모드에서 vector_retriever 가 없어야 함"
        )
        assert "query_embedder" not in names, (
            "키워드 모드에서 query_embedder 가 없어야 함"
        )
        assert "joiner" not in names, "키워드 모드에서 joiner 가 없어야 함"

    def test_build_pipeline_hybrid_mode(
        self, rag_settings_hybrid, env_settings
    ):
        """search_mode='hybrid' → 양쪽 retriever + joiner 포함."""
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)
        names = _component_names(pipeline)

        assert "query_embedder" in names, "하이브리드 모드에서 query_embedder 필수"
        assert "vector_retriever" in names, "하이브리드 모드에서 vector_retriever 필수"
        assert "keyword_retriever" in names, (
            "하이브리드 모드에서 keyword_retriever 필수"
        )
        assert "joiner" in names, "하이브리드 모드에서 joiner 필수"


# ---------------------------------------------------------------------------
# Tests: 공통 컴포넌트
# ---------------------------------------------------------------------------


class TestBuildPipelineCommonComponents:
    """모든 모드에 공통 포함되는 컴포넌트 검증."""

    def test_prompt_builder_always_present(
        self, rag_settings_hybrid, env_settings
    ):
        """모든 파이프라인에 prompt_builder 가 포함되어야 한다."""
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)
        names = _component_names(pipeline)
        assert "prompt_builder" in names

    def test_llm_generator_always_present(
        self, rag_settings_hybrid, env_settings
    ):
        """모든 파이프라인에 llm 제너레이터가 포함되어야 한다."""
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)
        names = _component_names(pipeline)
        assert "llm" in names


# ---------------------------------------------------------------------------
# Tests: 컴포넌트 연결 (edge) 검증
# ---------------------------------------------------------------------------


class TestBuildPipelineConnections:
    """컴포넌트 간 연결(edge) 검증."""

    def test_hybrid_embedder_to_vector_retriever(
        self, rag_settings_hybrid, env_settings
    ):
        """hybrid 모드에서 query_embedder → vector_retriever 연결 확인."""
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)
        assert _has_edge(pipeline, "query_embedder", "vector_retriever"), (
            "query_embedder → vector_retriever 연결이 필요합니다."
        )

    def test_hybrid_retrievers_to_joiner(
        self, rag_settings_hybrid, env_settings
    ):
        """hybrid 모드에서 양쪽 retriever → joiner 연결 확인."""
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)
        assert _has_edge(pipeline, "vector_retriever", "joiner"), (
            "vector_retriever → joiner 연결이 필요합니다."
        )
        assert _has_edge(pipeline, "keyword_retriever", "joiner"), (
            "keyword_retriever → joiner 연결이 필요합니다."
        )

    def test_hybrid_with_reranking_connections(
        self, rag_settings_hybrid, env_settings
    ):
        """hybrid + reranking 모드에서 joiner → ranker → prompt_builder 연결."""
        rag_settings_hybrid.reranking_enabled = True
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)

        assert _has_edge(pipeline, "joiner", "ranker"), (
            "joiner → ranker 연결이 필요합니다."
        )
        assert _has_edge(pipeline, "ranker", "prompt_builder"), (
            "ranker → prompt_builder 연결이 필요합니다."
        )

    def test_hybrid_without_reranking_connections(
        self, rag_settings_hybrid, env_settings
    ):
        """hybrid + reranking OFF → joiner → prompt_builder 직접 연결."""
        rag_settings_hybrid.reranking_enabled = False
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)

        assert _has_edge(pipeline, "joiner", "prompt_builder"), (
            "리랭킹 OFF 일 때 joiner → prompt_builder 직접 연결이 필요합니다."
        )

    def test_prompt_builder_to_llm(
        self, rag_settings_hybrid, env_settings
    ):
        """prompt_builder → llm 연결 확인."""
        pipeline = build_search_pipeline(rag_settings_hybrid, env_settings)
        assert _has_edge(pipeline, "prompt_builder", "llm"), (
            "prompt_builder → llm 연결이 필요합니다."
        )

    def test_vector_mode_connections(
        self, rag_settings_vector, env_settings
    ):
        """vector 모드에서 embedder → retriever → ranker → prompt → llm 연결."""
        pipeline = build_search_pipeline(rag_settings_vector, env_settings)

        assert _has_edge(pipeline, "query_embedder", "vector_retriever")
        # reranking ON 이므로 retriever → ranker → prompt_builder
        assert _has_edge(pipeline, "vector_retriever", "ranker")
        assert _has_edge(pipeline, "ranker", "prompt_builder")
        assert _has_edge(pipeline, "prompt_builder", "llm")

    def test_keyword_mode_connections(
        self, rag_settings_keyword, env_settings
    ):
        """keyword 모드에서 retriever → ranker → prompt → llm 연결."""
        pipeline = build_search_pipeline(rag_settings_keyword, env_settings)

        # reranking ON 이므로 retriever → ranker → prompt_builder
        assert _has_edge(pipeline, "keyword_retriever", "ranker")
        assert _has_edge(pipeline, "ranker", "prompt_builder")
        assert _has_edge(pipeline, "prompt_builder", "llm")
