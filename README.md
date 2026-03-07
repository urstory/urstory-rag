# UrstoryRAG - 한국어 RAG 프로덕션 시스템

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](https://www.python.org/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-000000.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Haystack 2.x](https://img.shields.io/badge/Haystack-2.x-1DB954.svg)](https://haystack.deepset.ai/)

---

## 소개

UrstoryRAG는 **한국어에 최적화된 프로덕션 레벨 RAG(Retrieval-Augmented Generation) 시스템**이다.

일반적인 RAG 프로젝트와 달리, UrstoryRAG는 다음을 처음부터 모두 포함한다:

- **한국어 형태소 분석 기반 하이브리드 검색**: PGVector 벡터 검색과 Elasticsearch+Nori 키워드 검색을 결합하여 한국어 문서에서 높은 검색 정확도를 달성한다.
- **한국어 특화 리랭커**: 영어 중심 리랭커 대신 한국어 AutoRAG 벤치마크 F1=0.9123 1위인 `bge-reranker-v2-m3-ko`를 사용한다.
- **프로덕션 가드레일**: PII 마스킹, 프롬프트 인젝션 차단, 할루시네이션 탐지를 내장하여 안전한 답변을 생성한다.
- **관리자 UI에서 모든 기능 ON/OFF 제어**: 리랭킹, HyDE, 가드레일, 검색 전략 등을 코드 변경 없이 관리자 UI에서 실시간 토글할 수 있다.
- **자동 품질 평가**: RAGAS + LLM-as-Judge로 검색/생성 품질을 자동 측정하고, Langfuse로 전체 파이프라인을 모니터링한다.

공개 테스트 데이터셋(68개 Q&A, 10개 공공 문서)에서 **LLM Judge 평균 90.3점, GOOD 비율 95.2%**를 달성했다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **하이브리드 검색** | PGVector 벡터 검색 + Elasticsearch+Nori 키워드 검색 결합. 가중치 조절 가능 |
| **한국어 리랭커** | `dragonkue/bge-reranker-v2-m3-ko` -- 한국어 AutoRAG F1=0.9123 전체 1위 |
| **HyDE** | Hypothetical Document Embeddings -- LLM이 가상 문서를 생성하여 검색 정확도 향상 |
| **Query Expansion + Cascading Search** | 쿼리 확장 및 단계별 검색으로 recall 극대화 |
| **가드레일** | PII 마스킹, 프롬프트 인젝션 차단, 할루시네이션 탐지 (임계값 설정 가능) |
| **Contextual Chunking** | LLM 기반 문맥 인식 청킹으로 의미 단위 분할 |
| **RAGAS 자동 품질 평가** | Faithfulness, Relevancy, Context Precision 등 자동 측정 |
| **Langfuse 모니터링** | v3 풀 스택 (Web + Worker + ClickHouse + Redis + MinIO) 통합 |
| **관리자 UI** | Next.js 15 + React 19 + shadcn/ui 기반 대시보드 |
| **문서 자동 감시** | Watchdog 기반 파일 변경 감지 및 자동 인덱싱 |

---

## 아키텍처

```
                        +------------------+
                        |   관리자 UI      |
                        |  (Next.js 15)    |
                        |  localhost:3500   |
                        +--------+---------+
                                 |
                                 | REST API
                                 v
                        +------------------+
                        |   FastAPI 백엔드  |
                        |  (Haystack 2.x)  |
                        |  localhost:8000   |
                        +--------+---------+
                                 |
              +------------------+------------------+
              |                  |                  |
              v                  v                  v
     +--------+------+  +-------+-------+  +-------+-------+
     | PostgreSQL    |  | Elasticsearch |  | Redis         |
     | + PGVector    |  | + Nori        |  | (Celery 큐)   |
     | (벡터 저장소) |  | (키워드 검색) |  |               |
     +---------------+  +---------------+  +---------------+

              +------------------+------------------+
              |                  |                  |
              v                  v                  v
     +--------+------+  +-------+-------+  +-------+-------+
     | OpenAI API    |  | 한국어 리랭커  |  | Langfuse v3   |
     | - 임베딩      |  | bge-reranker  |  | (모니터링)    |
     | - LLM 생성    |  | -v2-m3-ko     |  | localhost:3100|
     | - 평가 Judge  |  +---------------+  +---------------+
     +---------------+
```

---

## 기술 스택

| 구분 | 기술 | 버전 |
|------|------|------|
| **백엔드 프레임워크** | FastAPI | 0.115+ |
| **RAG 프레임워크** | Haystack | 2.9+ |
| **프론트엔드** | Next.js + React + shadcn/ui | 15 / 19 |
| **벡터 DB** | PostgreSQL + PGVector | PG 17 |
| **키워드 검색** | Elasticsearch + Nori | 8.x |
| **작업 큐** | Celery + Redis | 5.4+ / 7 |
| **임베딩** | OpenAI text-embedding-3-small | 1536차원 |
| **LLM** | OpenAI gpt-4.1-mini | -- |
| **평가 Judge** | OpenAI gpt-4o | -- |
| **리랭커** | dragonkue/bge-reranker-v2-m3-ko | -- |
| **NLP** | kiwipiepy (한국어 형태소 분석) | 0.18+ |
| **모니터링** | Langfuse v3 | 3.x |
| **품질 평가** | RAGAS | 0.2+ |
| **CSS** | Tailwind CSS | 4.x |

---

## Quick Start

### 사전 요구사항

- Docker / Docker Compose
- Python 3.12+
- Node.js 20+ / pnpm
- OpenAI API Key

### Step 1: 프로젝트 클론

```bash
git clone https://github.com/urstory/urstory-rag.git
cd urstory-rag
```

### Step 2: 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열고 다음 값을 설정한다:

```dotenv
# 필수: OpenAI API 키
OPENAI_API_KEY=sk-your-openai-api-key

# 필수: PostgreSQL 비밀번호 (원하는 값으로 변경)
POSTGRES_PASSWORD=changeme_strong_password

# 선택: Langfuse 암호화 키 (64자 hex, 프로덕션에서는 반드시 변경)
LANGFUSE_ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000
```

### Step 3: 공유 인프라 실행

PostgreSQL+PGVector, Elasticsearch+Nori, Redis를 실행한다.

```bash
make infra-up
```

또는 직접:

```bash
cd infra && docker compose up -d
```

정상 실행 확인:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# shared-postgres     Up ...
# shared-elasticsearch Up ...
# shared-redis        Up ...
```

### Step 4: 백엔드 설정

```bash
cd backend

# 가상 환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -e ".[dev]"

# DB 마이그레이션
alembic upgrade head

# 백엔드 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: 프론트엔드 설정

```bash
cd frontend

# 의존성 설치
pnpm install

# 개발 서버 실행
pnpm dev
```

### Step 6: Langfuse 모니터링 (선택)

프로젝트 루트에서 Langfuse v3 풀 스택을 실행한다.

```bash
# 프로젝트 루트에서
docker compose up -d
```

Langfuse 초기 설정:

1. http://localhost:3100 에 접속하여 계정을 생성한다 (Sign Up).
2. Organization과 Project를 생성한다.
3. Project Settings > API Keys에서 API 키를 발급받는다.
4. 발급받은 키를 `.env`와 `backend/.env`에 설정한다:

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx
```

5. 백엔드를 재시작하면 검색 파이프라인의 트레이싱이 자동으로 시작된다.

> Langfuse 키가 설정되지 않아도 RAG 파이프라인은 정상 동작한다 (no-op 모드).

### Step 7: 접속 확인

| 서비스 | URL |
|--------|-----|
| 백엔드 API (Swagger) | http://localhost:8000/docs |
| 프론트엔드 관리자 UI | http://localhost:3500 |
| Langfuse 대시보드 | http://localhost:3100 |

---

## 프로젝트 구조

```
urstory-rag/
├── backend/                    # Python 백엔드
│   ├── app/
│   │   ├── api/                # FastAPI 라우터 (search, documents, health, ...)
│   │   ├── models/             # SQLAlchemy 모델 + Pydantic 스키마
│   │   ├── pipelines/          # Haystack RAG 파이프라인
│   │   ├── services/           # 비즈니스 로직
│   │   │   ├── chunking/       #   LLM 기반 Contextual Chunking
│   │   │   ├── document/       #   문서 파싱 (PDF, DOCX, MD)
│   │   │   ├── embedding/      #   OpenAI 임베딩
│   │   │   ├── evaluation/     #   RAGAS 평가
│   │   │   ├── generation/     #   LLM 답변 생성
│   │   │   ├── guardrails/     #   가드레일 (PII, 인젝션, 할루시네이션)
│   │   │   ├── hyde/           #   HyDE (가상 문서 임베딩)
│   │   │   ├── reranking/      #   한국어 리랭커
│   │   │   ├── search/         #   하이브리드 검색 (벡터 + 키워드)
│   │   │   └── watcher/        #   파일 감시 및 자동 인덱싱
│   │   ├── monitoring/         # Langfuse 연동
│   │   ├── tasks/              # Celery 비동기 작업
│   │   ├── config.py           # 설정 관리
│   │   ├── main.py             # FastAPI 앱 진입점
│   │   └── worker.py           # Celery 워커
│   ├── alembic/                # DB 마이그레이션
│   ├── tests/                  # 단위/통합 테스트
│   └── pyproject.toml
├── frontend/                   # Next.js 관리자 UI
│   ├── src/
│   │   ├── app/                # Next.js App Router 페이지
│   │   ├── components/         # React 컴포넌트 (shadcn/ui)
│   │   ├── hooks/              # Custom React Hooks
│   │   ├── lib/                # 유틸리티
│   │   └── types/              # TypeScript 타입
│   ├── e2e/                    # Playwright E2E 테스트
│   └── package.json
├── infra/                      # 공유 인프라 (다른 프로젝트와 공유 가능)
│   ├── docker-compose.yml      # PostgreSQL + Elasticsearch + Redis
│   ├── Dockerfile.elasticsearch # Nori 플러그인 포함
│   └── init-db.sql             # DB 초기화 (pgvector 확장)
├── docs/                       # 아키텍처 문서
│   └── architecture/           # 10개 아키텍처 문서
├── test_files/                 # RAG 품질 테스트
│   ├── public_dataset/         #   공개 테스트 데이터셋 (공공누리 제1유형 PDF + MD)
│   ├── run_quality_test.py     #   품질 테스트 스크립트
│   └── q_a_public.txt          #   68개 Q&A 쌍
├── docker-compose.yml          # 앱 서비스 (API + Langfuse v3)
├── Makefile                    # 개발 편의 명령어
└── .env.example                # 환경 변수 템플릿
```

---

## RAG 품질 테스트

이 프로젝트는 **공개 테스트 데이터셋**을 포함하고 있어, 누구나 동일한 조건에서 RAG 품질을 재현할 수 있다.

### 공개 테스트 데이터셋

`test_files/public_dataset/`에 저작권 없는 공공 문서 10개와 68개 Q&A가 포함되어 있다:

- **Markdown 5개**: 한글 창제, 한국 지리, 유네스코 유산, 발효 식품, 우주 개발 (직접 작성)
- **PDF 5개**: 한국은행, 기상청, 통계청 공공 보고서 (공공누리 제1유형)
- **Q&A 68개**: `test_files/q_a_public.txt` (Markdown 32문제 + PDF 36문제)

자세한 내용은 [`test_files/public_dataset/README.md`](test_files/public_dataset/README.md) 참조.

### 테스트 실행

```bash
# 1. 공개 데이터셋 문서를 관리자 UI에서 업로드
# 2. 인덱싱 완료 대기
# 3. 품질 테스트 실행
cd backend
.venv/bin/python ../test_files/run_quality_test.py
```

### 평가 방식

| 평가 방법 | 역할 | 설명 |
|-----------|------|------|
| LLM-as-Judge (GPT-4o) | 메인 지표 | 의미적 정확도를 0~100점으로 판정 |
| 키워드 재현율 | 보조 지표 | 숫자/고유명사 exact match |

### 품질 테스트 결과 (2026-03-07)

공개 데이터셋 68개 Q&A, 10개 문서(2,239 청크) 기준:

| 지표 | 결과 |
|------|------|
| LLM Judge 평균 점수 | **90.3 / 100** |
| GOOD (70점 이상) | **60 / 63 (95.2%)** |
| FAIL (40점 미만) | 3 / 63 (4.8%) |
| 키워드 재현율 | 60.8% |

상세 분석은 [`docs/rag_quality_test_report_public_20260307.md`](docs/rag_quality_test_report_public_20260307.md) 참조.

---

## Makefile 명령어

```bash
make infra-up        # 공유 인프라 실행 (PostgreSQL, Elasticsearch, Redis)
make infra-down      # 공유 인프라 중지
make app-up          # 앱 서비스 실행 (API + Langfuse)
make app-down        # 앱 서비스 중지
make dev-backend     # 백엔드 개발 서버 실행
make migrate-local   # 로컬 DB 마이그레이션
make test            # 백엔드 테스트 실행
```

---

## 블로그 시리즈

이 프로젝트의 설계 배경과 구현 과정을 다룬 블로그 시리즈:

**"소규모 기업을 위한 제대로 된 RAG 시스템"**

| 편 | 제목 | 링크 |
|----|------|------|
| 1/4 | 왜 당신의 RAG는 실패하는가 - 온톨로지, 지식 그래프, 그리고 제대로 된 아키텍처의 조건 | [읽기](https://www.fullstackfamily.com/@urstory/posts/13981) |
| 2/4 | 데이터가 전부입니다 - 문서를 지식으로 바꾸는 파이프라인 | [읽기](https://www.fullstackfamily.com/@urstory/posts/13982) |
| 3/4 | 검색, 평가, 그리고 신뢰할 수 있는 시스템 | [읽기](https://www.fullstackfamily.com/@urstory/posts/13983) |
| 4/4 | MCP로 완성하기 - Claude가 회사 지식을 쓰게 만들기 | [읽기](https://www.fullstackfamily.com/@urstory/posts/13984) |

---

## 라이선스

이 프로젝트는 [MIT License](LICENSE)로 배포된다.

---

## 만든 사람

**김성박** (Sungpark Kim)

- Email: urstory@fullstackfamily.com
- GitHub: [@urstory](https://github.com/urstory)
