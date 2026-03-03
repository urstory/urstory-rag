# 프로젝트 구조

## 디렉토리 레이아웃

```
urstory_rag/
├── docs/
│   └── architecture/              # 아키텍처 문서 (본 문서)
│
├── infra/                         # 공유 인프라 (독립 docker-compose)
│   ├── docker-compose.yml         # PostgreSQL + Elasticsearch
│   ├── Dockerfile.elasticsearch   # Nori 플러그인 포함
│   ├── init-db.sql                # PGVector 확장, 스키마 생성
│   ├── elasticsearch/
│   │   └── nori-index-template.json  # Nori 분석기 인덱스 템플릿
│   └── .env.example
│
├── backend/                       # Python FastAPI 백엔드
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI 앱 진입점
│   │   ├── config.py              # 설정 관리 (Pydantic Settings)
│   │   │
│   │   ├── api/                   # API 라우터
│   │   │   ├── __init__.py
│   │   │   ├── documents.py       # 문서 CRUD, 업로드
│   │   │   ├── search.py          # 검색 API
│   │   │   ├── settings.py        # 시스템 설정 API
│   │   │   ├── evaluation.py      # RAGAS 평가 API
│   │   │   └── monitoring.py      # 모니터링 API
│   │   │
│   │   ├── models/                # 데이터 모델
│   │   │   ├── __init__.py
│   │   │   ├── database.py        # SQLAlchemy 모델
│   │   │   └── schemas.py         # Pydantic 스키마
│   │   │
│   │   ├── services/              # 비즈니스 로직
│   │   │   ├── __init__.py
│   │   │   ├── chunking/          # 청킹 전략
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py        # ChunkingStrategy 인터페이스
│   │   │   │   ├── recursive.py   # 재귀적 문자 분할
│   │   │   │   ├── semantic.py    # 시맨틱 청킹
│   │   │   │   ├── contextual.py  # Contextual Retrieval 청킹
│   │   │   │   └── auto_detect.py # 파일 유형별 자동 전략 감지
│   │   │   │
│   │   │   ├── embedding/         # 임베딩 프로바이더
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py        # EmbeddingProvider 인터페이스
│   │   │   │   └── openai.py      # OpenAI API (text-embedding-3-small)
│   │   │   │
│   │   │   ├── search/            # 검색 엔진
│   │   │   │   ├── __init__.py
│   │   │   │   ├── hybrid.py      # 하이브리드 검색 오케스트레이터
│   │   │   │   ├── vector.py      # PGVector 벡터 검색
│   │   │   │   ├── keyword_es.py  # Elasticsearch + Nori BM25
│   │   │   │   ├── keyword_kiwi.py # kiwipiepy + rank-bm25 (대안)
│   │   │   │   ├── rrf.py         # Reciprocal Rank Fusion
│   │   │   │   ├── multi_query.py # 멀티쿼리 구조분해
│   │   │   │   ├── question_classifier.py # 질문 유형 분류
│   │   │   │   ├── query_expander.py     # 쿼리 확장
│   │   │   │   ├── cascading_evaluator.py # 캐스케이딩 품질 평가
│   │   │   │   └── document_scope.py     # 문서 범위 필터링
│   │   │   │
│   │   │   ├── reranking/         # 리랭킹
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py        # Reranker 인터페이스
│   │   │   │   └── korean.py      # bge-reranker-v2-m3-ko
│   │   │   │
│   │   │   ├── hyde/              # HyDE
│   │   │   │   ├── __init__.py
│   │   │   │   └── generator.py   # 가상 문서 생성
│   │   │   │
│   │   │   ├── generation/        # 답변 생성
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py        # LLMProvider 인터페이스
│   │   │   │   ├── openai.py      # OpenAI API
│   │   │   │   └── evidence_extractor.py # 정확 인용 근거 추출
│   │   │   │
│   │   │   ├── guardrails/        # 가드레일
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pii.py         # 한국어 PII 탐지
│   │   │   │   ├── injection.py   # 프롬프트 인젝션 방어
│   │   │   │   ├── hallucination.py # 할루시네이션 탐지
│   │   │   │   ├── faithfulness.py  # 충실도 검증 (LLM-as-Judge)
│   │   │   │   ├── retrieval_gate.py # 검색 품질 게이트
│   │   │   │   └── numeric_verifier.py # 숫자 검증
│   │   │   │
│   │   │   ├── evaluation/        # 품질 평가
│   │   │   │   ├── __init__.py
│   │   │   │   └── ragas.py       # RAGAS 메트릭 평가
│   │   │   │
│   │   │   ├── document/          # 문서 관리
│   │   │   │   ├── __init__.py
│   │   │   │   ├── processor.py   # 문서 처리 오케스트레이터
│   │   │   │   ├── indexer.py     # 듀얼 인덱싱 (PGVector + ES)
│   │   │   │   ├── converter.py   # 파일 형식 변환
│   │   │   │   └── watcher.py     # 디렉토리 감시 (watchdog)
│   │   │   │
│   │   │   └── watcher/           # 디렉토리 감시 서비스
│   │   │       ├── __init__.py
│   │   │       ├── handler.py     # 파일 이벤트 핸들러
│   │   │       └── scanner.py     # 초기/주기적 전체 스캔
│   │   │
│   │   ├── pipelines/             # Haystack 파이프라인
│   │   │   ├── __init__.py
│   │   │   ├── indexing.py        # 인덱싱 파이프라인
│   │   │   └── search.py          # 검색 파이프라인
│   │   │
│   │   └── monitoring/            # 모니터링
│   │       ├── __init__.py
│   │       └── langfuse.py        # Langfuse 통합
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   │
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic/                   # DB 마이그레이션
│       └── versions/
│
├── frontend/                      # Next.js 관리자 UI
│   ├── src/
│   │   ├── app/                   # App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx           # 대시보드
│   │   │   ├── documents/         # 문서 관리
│   │   │   ├── search/            # 검색 테스트
│   │   │   ├── settings/          # 시스템 설정
│   │   │   ├── evaluation/        # RAGAS 평가
│   │   │   └── monitoring/        # Langfuse 대시보드 연동
│   │   │
│   │   ├── components/            # React 컴포넌트
│   │   │   ├── ui/                # 공통 UI (shadcn/ui)
│   │   │   ├── documents/         # 문서 관련 컴포넌트
│   │   │   ├── search/            # 검색 관련 컴포넌트
│   │   │   ├── settings/          # 설정 관련 컴포넌트
│   │   │   └── layout/            # 레이아웃 컴포넌트
│   │   │
│   │   ├── lib/                   # 유틸리티
│   │   │   ├── api.ts             # API 클라이언트 (fetch wrapper)
│   │   │   └── utils.ts
│   │   │
│   │   └── types/                 # TypeScript 타입 정의
│   │       └── index.ts
│   │
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── docker-compose.yml             # 앱 계층 docker-compose
├── .env.example                   # 환경 변수 템플릿
├── Makefile                       # 개발/운영 커맨드
└── CLAUDE.md
```

## 모듈 의존성

```
api/ ──→ services/ ──→ pipelines/ ──→ Haystack
  │         │
  │         ├── chunking/     (문서 → 청크)
  │         ├── embedding/    (청크 → 벡터)
  │         ├── search/       (쿼리 → 문서)
  │         ├── reranking/    (문서 → 정렬된 문서)
  │         ├── hyde/         (쿼리 → 가상 문서 → 검색)
  │         ├── generation/   (문서 + 쿼리 → 답변)
  │         ├── guardrails/   (입출력 검증)
  │         ├── evaluation/   (품질 측정)
  │         └── watcher/      (디렉토리 감시 → 자동 인덱싱)
  │
  └──→ models/ ──→ PostgreSQL
```

## 설정 관리

시스템 설정은 2단계로 관리합니다:

1. **환경 변수** (`.env`): 인프라 연결 정보, API 키 등 변경 빈도가 낮은 설정
2. **DB 설정 테이블**: 관리자 UI에서 변경하는 런타임 설정 (청킹 전략, 리랭킹 ON/OFF 등)

```python
# backend/app/config.py
class Settings(BaseSettings):
    # 인프라 (환경 변수)
    database_url: str
    elasticsearch_url: str
    redis_url: str = "redis://localhost:6379"

    # OpenAI API (필수)
    openai_api_key: str

    # 모니터링 (환경 변수)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
```

런타임 설정 (DB 저장):
```python
class RAGSettings:
    # 청킹
    chunking_strategy: str = "recursive"  # recursive | semantic | contextual | auto
    chunk_size: int = 512
    chunk_overlap: int = 50

    # 임베딩
    embedding_provider: str = "openai"  # openai
    embedding_model: str = "text-embedding-3-small"

    # 검색
    search_mode: str = "hybrid"  # vector | keyword | hybrid
    keyword_engine: str = "elasticsearch"  # elasticsearch | kiwipiepy
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
    hyde_model: str = "gpt-4.1-mini"

    # 가드레일
    pii_detection_enabled: bool = True
    injection_detection_enabled: bool = True
    hallucination_detection_enabled: bool = True

    # 답변 생성
    llm_provider: str = "openai"  # openai
    llm_model: str = "gpt-4.1-mini"
    system_prompt: str = "..."

    # 멀티쿼리 / 쿼리 확장
    multi_query_enabled: bool = True
    multi_query_max_sub_queries: int = 3
    query_expansion_enabled: bool = True
    query_expansion_synonyms: bool = True

    # 캐스케이딩 평가
    cascading_enabled: bool = True
    cascading_min_score: float = 0.3
    cascading_max_retries: int = 2

    # 정확 인용 / 숫자 검증
    exact_citation_enabled: bool = False
    numeric_verification_enabled: bool = True

    # Contextual Chunking
    contextual_chunking_enabled: bool = True
    contextual_chunking_model: str = "gpt-4.1-mini"

    # 문서 범위 필터링
    document_scope_enabled: bool = True
    document_scope_max_docs: int = 5

    # 리랭커 점수 모드
    reranker_score_mode: str = "calibrated"  # raw | calibrated
    reranker_alpha: float = 0.7  # sigmoid 캘리브레이션 + 순위 신호 결합 가중치
```
