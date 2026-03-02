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


class PIIDetectionSettings(BaseModel):
    """PII 탐지 설정."""
    enabled: bool = True
    action: str = "mask"  # mask, block
    patterns: list[str] = [
        "주민등록번호", "외국인등록번호", "휴대전화", "일반전화",
        "사업자등록번호", "여권번호", "운전면허번호", "이메일", "계좌번호",
    ]
    llm_verification: bool = True


class InjectionDetectionSettings(BaseModel):
    """프롬프트 인젝션 탐지 설정."""
    enabled: bool = True
    action: str = "block"  # block, warn
    block_message: str = "이 질문은 처리할 수 없습니다."


class HallucinationDetectionSettings(BaseModel):
    """할루시네이션 탐지 설정."""
    enabled: bool = True
    action: str = "warn"  # warn, block, regenerate
    threshold: float = 0.8
    judge_model: str = "gpt-4.1-mini"


class RetrievalGateSettings(BaseModel):
    """검색 품질 게이트 설정."""
    enabled: bool = True
    min_top_score: float = 0.05
    min_doc_count: int = 1
    min_doc_score: float = 0.1
    not_found_message: str = "관련 문서를 충분히 찾지 못했습니다. 다른 키워드로 검색해 주세요."


class FaithfulnessSettings(BaseModel):
    """충실도 검증 설정."""
    enabled: bool = True
    action: str = "warn"  # warn, block
    threshold: float = 0.9


class GuardrailsSettings(BaseModel):
    """가드레일 통합 설정."""
    pii_detection: PIIDetectionSettings = PIIDetectionSettings()
    injection_detection: InjectionDetectionSettings = InjectionDetectionSettings()
    hallucination_detection: HallucinationDetectionSettings = HallucinationDetectionSettings()
    retrieval_gate: RetrievalGateSettings = RetrievalGateSettings()
    faithfulness: FaithfulnessSettings = FaithfulnessSettings()


class RAGSettings(BaseModel):
    """2단계: DB 런타임 설정 (관리자 UI에서 변경 가능)."""

    # 청킹
    chunking_strategy: str = "auto"
    chunk_size: int = 1024
    chunk_overlap: int = 200
    contextual_chunking_enabled: bool = False
    contextual_chunking_model: str = "gpt-4.1-mini"
    contextual_chunking_max_doc_chars: int = 2000

    # 임베딩
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

    # 검색
    search_mode: str = "hybrid"
    keyword_engine: str = "elasticsearch"
    rrf_constant: int = 60
    vector_weight: float = 0.5
    keyword_weight: float = 0.5

    # 리랭킹
    reranking_enabled: bool = True
    reranker_model: str = "dragonkue/bge-reranker-v2-m3-ko"
    reranker_top_k: int = 8
    retriever_top_k: int = 20

    # HyDE
    hyde_enabled: bool = True
    hyde_model: str = "gpt-4.1-mini"

    # Cascading + Query Expansion
    cascading_bm25_threshold: float = 3.0
    cascading_min_qualifying_docs: int = 3
    cascading_min_doc_score: float = 1.0
    cascading_fallback_vector_weight: float = 0.3
    cascading_fallback_keyword_weight: float = 0.7
    query_expansion_enabled: bool = True
    query_expansion_max_keywords: int = 10

    # 가드레일 (세부 설정)
    guardrails: GuardrailsSettings = GuardrailsSettings()

    # 가드레일 플랫 플래그 (하위 호환성 + 파이프라인에서 빠른 참조용)
    pii_detection_enabled: bool = True
    injection_detection_enabled: bool = True
    hallucination_detection_enabled: bool = True
    retrieval_quality_gate_enabled: bool = True
    faithfulness_enabled: bool = True

    def model_post_init(self, __context) -> None:
        """플랫 플래그와 guardrails 서브모델 양방향 동기화.

        - 플랫 플래그가 명시적으로 설정됐으면 → 서브모델 업데이트
        - 그렇지 않으면 서브모델 값 → 플랫 플래그로 동기화
        """
        explicitly_set = self.model_fields_set

        for flat, sub_attr in [
            ("pii_detection_enabled", "pii_detection"),
            ("injection_detection_enabled", "injection_detection"),
            ("hallucination_detection_enabled", "hallucination_detection"),
            ("retrieval_quality_gate_enabled", "retrieval_gate"),
            ("faithfulness_enabled", "faithfulness"),
        ]:
            sub = getattr(self.guardrails, sub_attr)
            if flat in explicitly_set:
                sub.enabled = getattr(self, flat)
            else:
                object.__setattr__(self, flat, sub.enabled)

    # 답변 생성
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float = 0.3
    system_prompt: str = ""  # 비어있으면 prompts.py의 SYSTEM_PROMPT 사용


@lru_cache
def get_settings() -> Settings:
    return Settings()
