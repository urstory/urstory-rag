from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """1단계: 환경 변수 기반 설정 (인프라 연결, API 키)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared"
    elasticsearch_url: str = "http://localhost:9200"
    ollama_url: str = "http://localhost:11434"
    redis_url: str = "redis://localhost:6379"

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3100"


class RAGSettings(BaseModel):
    """2단계: DB 런타임 설정 (관리자 UI에서 변경 가능)."""

    # 청킹
    chunking_strategy: str = "recursive"
    chunk_size: int = 512
    chunk_overlap: int = 50

    # 임베딩
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"

    # 검색
    search_mode: str = "hybrid"
    keyword_engine: str = "elasticsearch"
    rrf_constant: int = 60
    vector_weight: float = 0.5
    keyword_weight: float = 0.5

    # 리랭킹
    reranking_enabled: bool = True
    reranker_model: str = "dragonkue/bge-reranker-v2-m3-ko"
    reranker_top_k: int = 5
    retriever_top_k: int = 20

    # HyDE
    hyde_enabled: bool = True
    hyde_model: str = "qwen2.5:7b"

    # 가드레일
    pii_detection_enabled: bool = True
    injection_detection_enabled: bool = True
    hallucination_detection_enabled: bool = True

    # 답변 생성
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    system_prompt: str = (
        "당신은 한국어 문서 기반 질의응답 시스템입니다. "
        "제공된 컨텍스트만을 사용하여 정확하게 답변하세요. "
        "컨텍스트에 답이 없으면 '제공된 문서에서 해당 정보를 찾을 수 없습니다'라고 답하세요."
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
