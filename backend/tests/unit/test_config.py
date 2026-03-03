"""Step 2.2 RED: 설정 시스템 테스트."""
import os

import pytest


def test_settings_from_env(monkeypatch, tmp_path):
    """환경변수로 Settings 생성 확인."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://admin:pw@localhost:5432/shared")
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://localhost:9200")
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from app.config import Settings

    # .env 파일 읽기를 방지하기 위해 빈 env_file 사용
    settings = Settings(_env_file=tmp_path / ".env.empty")
    assert settings.database_url == "postgresql+asyncpg://admin:pw@localhost:5432/shared"
    assert settings.elasticsearch_url == "http://localhost:9200"
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.openai_api_key is None
    assert settings.anthropic_api_key is None


def test_settings_optional_api_keys(monkeypatch):
    """선택적 API 키 설정 확인."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://admin:pw@localhost:5432/shared")
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://localhost:9200")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    from app.config import Settings

    settings = Settings()
    assert settings.openai_api_key == "sk-test-key"
    assert settings.anthropic_api_key == "sk-ant-test"


def test_rag_settings_defaults():
    """RAGSettings 기본값 검증."""
    from app.config import RAGSettings

    rag = RAGSettings()
    assert rag.chunking_strategy == "auto"
    assert rag.chunk_size == 1024
    assert rag.chunk_overlap == 200
    assert rag.embedding_provider == "openai"
    assert rag.embedding_model == "text-embedding-3-small"
    assert rag.search_mode == "hybrid"
    assert rag.keyword_engine == "elasticsearch"
    assert rag.rrf_constant == 60
    assert rag.reranking_enabled is True
    assert rag.reranker_model == "dragonkue/bge-reranker-v2-m3-ko"
    assert rag.reranker_top_k == 8
    assert rag.retriever_top_k == 20
    assert rag.hyde_enabled is True
    assert rag.hyde_model == "gpt-4.1-mini"
    assert rag.pii_detection_enabled is True
    assert rag.injection_detection_enabled is True
    assert rag.hallucination_detection_enabled is True
    assert rag.llm_provider == "openai"
    assert rag.llm_model == "gpt-4.1-mini"


def test_rag_settings_custom_values():
    """RAGSettings 커스텀 값 설정."""
    from app.config import RAGSettings

    rag = RAGSettings(
        chunk_size=1024,
        reranking_enabled=False,
        hyde_enabled=False,
        llm_provider="openai",
    )
    assert rag.chunk_size == 1024
    assert rag.reranking_enabled is False
    assert rag.hyde_enabled is False
    assert rag.llm_provider == "openai"


def test_retrieval_gate_defaults():
    """RetrievalGateSettings 기본값 검증."""
    from app.config import RAGSettings

    rag = RAGSettings()
    assert rag.retrieval_quality_gate_enabled is True
    gate = rag.guardrails.retrieval_gate
    assert gate.enabled is True
    assert gate.min_top_score == 0.3
    assert gate.min_doc_count == 1
    assert gate.min_doc_score == 0.2
    assert "찾지 못했습니다" in gate.not_found_message


def test_retrieval_gate_flat_flag_sync():
    """플랫 플래그와 서브모델 양방향 동기화."""
    from app.config import RAGSettings

    # 플랫 플래그 → 서브모델 동기화
    rag = RAGSettings(retrieval_quality_gate_enabled=False)
    assert rag.guardrails.retrieval_gate.enabled is False

    # 서브모델 → 플랫 플래그 동기화
    rag2 = RAGSettings(
        guardrails={"retrieval_gate": {"enabled": False}},
    )
    assert rag2.retrieval_quality_gate_enabled is False


def test_faithfulness_defaults():
    """FaithfulnessSettings 기본값 검증."""
    from app.config import RAGSettings

    rag = RAGSettings()
    assert rag.faithfulness_enabled is True
    faith = rag.guardrails.faithfulness
    assert faith.enabled is True
    assert faith.action == "warn"
    assert faith.threshold == 0.9


def test_faithfulness_flat_flag_sync():
    """충실도 플랫 플래그 양방향 동기화."""
    from app.config import RAGSettings

    rag = RAGSettings(faithfulness_enabled=False)
    assert rag.guardrails.faithfulness.enabled is False

    rag2 = RAGSettings(
        guardrails={"faithfulness": {"enabled": False}},
    )
    assert rag2.faithfulness_enabled is False


def test_contextual_chunking_defaults():
    """Contextual Chunking 기본값 검증."""
    from app.config import RAGSettings

    rag = RAGSettings()
    assert rag.contextual_chunking_enabled is False
    assert rag.contextual_chunking_model == "gpt-4.1-mini"
    assert rag.contextual_chunking_max_doc_chars == 2000


def test_cascading_settings_defaults():
    """Cascading 검색 설정 기본값 검증."""
    from app.config import RAGSettings

    rag = RAGSettings()
    assert rag.cascading_bm25_threshold == 3.0
    assert rag.cascading_min_qualifying_docs == 3
    assert rag.cascading_min_doc_score == 1.0
    assert rag.cascading_fallback_vector_weight == 0.3
    assert rag.cascading_fallback_keyword_weight == 0.7
    assert rag.query_expansion_enabled is True
    assert rag.query_expansion_max_keywords == 10


def test_cascading_settings_custom():
    """Cascading 검색 설정 커스텀 값."""
    from app.config import RAGSettings

    rag = RAGSettings(
        search_mode="cascading",
        cascading_bm25_threshold=5.0,
        cascading_min_qualifying_docs=5,
        cascading_fallback_vector_weight=0.2,
        query_expansion_enabled=False,
    )
    assert rag.search_mode == "cascading"
    assert rag.cascading_bm25_threshold == 5.0
    assert rag.cascading_min_qualifying_docs == 5
    assert rag.cascading_fallback_vector_weight == 0.2
    assert rag.query_expansion_enabled is False


def test_cascading_mode_accepted():
    """search_mode에 'cascading' 값이 허용되어야 한다."""
    from app.config import RAGSettings

    rag = RAGSettings(search_mode="cascading")
    assert rag.search_mode == "cascading"


def test_cascading_settings_in_hybrid_mode_unchanged():
    """hybrid 모드에서 cascading 설정이 존재하지만 사용되지 않는다."""
    from app.config import RAGSettings

    rag = RAGSettings(search_mode="hybrid")
    assert rag.search_mode == "hybrid"
    # cascading 설정은 기본값으로 존재
    assert rag.cascading_bm25_threshold == 3.0


def test_multi_query_settings_defaults():
    """Phase 11 멀티쿼리/정확 인용/숫자 검증 설정 기본값 검증."""
    from app.config import RAGSettings

    rag = RAGSettings()
    assert rag.multi_query_enabled is True
    assert rag.multi_query_count == 4
    assert rag.multi_query_model == "gpt-4.1-mini"
    assert rag.exact_citation_enabled is True
    assert rag.numeric_verification_enabled is True


def test_multi_query_settings_custom():
    """Phase 11 설정 커스텀 값."""
    from app.config import RAGSettings

    rag = RAGSettings(
        multi_query_enabled=False,
        multi_query_count=6,
        exact_citation_enabled=False,
        numeric_verification_enabled=False,
    )
    assert rag.multi_query_enabled is False
    assert rag.multi_query_count == 6
    assert rag.exact_citation_enabled is False
    assert rag.numeric_verification_enabled is False
