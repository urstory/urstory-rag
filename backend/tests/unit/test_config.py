"""Step 2.2 RED: 설정 시스템 테스트."""
import os

import pytest


def test_settings_from_env(monkeypatch):
    """환경변수로 Settings 생성 확인."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://admin:pw@localhost:5432/shared")
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://localhost:9200")
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

    from app.config import Settings

    settings = Settings()
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
    assert rag.chunking_strategy == "recursive"
    assert rag.chunk_size == 512
    assert rag.chunk_overlap == 50
    assert rag.embedding_provider == "ollama"
    assert rag.embedding_model == "bge-m3"
    assert rag.search_mode == "hybrid"
    assert rag.keyword_engine == "elasticsearch"
    assert rag.rrf_constant == 60
    assert rag.reranking_enabled is True
    assert rag.reranker_model == "dragonkue/bge-reranker-v2-m3-ko"
    assert rag.reranker_top_k == 5
    assert rag.retriever_top_k == 20
    assert rag.hyde_enabled is True
    assert rag.hyde_model == "qwen2.5:7b"
    assert rag.pii_detection_enabled is True
    assert rag.injection_detection_enabled is True
    assert rag.hallucination_detection_enabled is True
    assert rag.llm_provider == "ollama"
    assert rag.llm_model == "qwen2.5:7b"


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
