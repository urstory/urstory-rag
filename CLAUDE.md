# UrstoryRAG - 한국어 RAG 프로덕션 시스템

- CLAUDE.md 에는 코드베이스를 봐도 알 수 없는 내용만 작성한다. 200줄을 넘지 않는다.

## 프로젝트 개요
한국어 특화 RAG 시스템. 참조 설계: `/Users/toto/mybooks/gisa/기사/20260302_korean_rag_production_architecture.md`

## 개발 환경
- 현재 개발 머신: Mac Studio (Apple Silicon)
- Ollama가 호스트에 설치/실행 중 (http://localhost:11434)
  - Docker 내 Ollama는 Metal GPU 미사용으로 5-6배 느림 → 반드시 호스트에서 실행
- Ollama 모델: bge-m3 (임베딩), qwen2.5:7b (HyDE/답변 생성)

## 핵심 설계 원칙
- **모든 기능 즉시 구현**: 리랭킹, HyDE, 가드레일, RAGAS를 점진적이 아닌 초기부터 모두 포함
  - 관리자 UI에서 각 기능의 ON/OFF 제어
- **저사양 대응**: Ollama를 쓸 수 없는 환경에서는 OpenAI/Claude 등 외부 API로 전환 가능
- **인프라 공유**: `infra/` docker-compose(PostgreSQL+Elasticsearch)는 다른 프로젝트와 공유 목적
  - 앱과 인프라를 분리하여 인프라는 한 번 띄우면 여러 프로젝트가 접속

## 기술 스택 결정 사유
- **관리자 UI**: Next.js + React (사용자 지정)
- **백엔드**: Python + FastAPI + Haystack 2.x (사용자 지정)
- **임베딩 모델**: bge-m3 → MIRACL 한국어 nDCG@10=69.9 다국어 1위
- **리랭커**: dragonkue/bge-reranker-v2-m3-ko → 한국어 AutoRAG F1=0.9123 전체 1위
  - cross-encoder/ms-marco-MiniLM은 영어 전용이므로 사용 금지
- **키워드 검색**: Elasticsearch+Nori 기본, kiwipiepy+BM25 대안
- **RAGAS 평가 judge**: GPT-4 사용 (Ollama 모델보다 평가 정확도 높음)
- **Langfuse v3**: Web + Worker 2컨테이너 + ClickHouse + 전용 Redis + MinIO(S3) 필수
  - `ENCRYPTION_KEY`(64자 hex) 환경변수 필수

## 에이전트 팀 구성

| 역할 | 전문 영역 | 담당 Phase |
|------|----------|-----------|
| 리드 아키텍트 | 설계 검증, 크로스커팅, 코드 리뷰 | 전체 (감독) |
| 인프라 엔지니어 | Docker, PostgreSQL, Elasticsearch, 네트워크 | 1, 9 |
| 백엔드 엔지니어 | FastAPI, SQLAlchemy, Alembic, Celery, TDD | 2, 3 |
| RAG/ML 엔지니어 | Haystack 2.x, 임베딩, 검색, 리랭킹, HyDE, 가드레일, RAGAS | 4, 5, 6 |
| 프론트엔드 엔지니어 | Next.js 15, React 19, Tailwind CSS 4, shadcn/ui | 7 |
| QA 엔지니어 | Playwright E2E, 통합 테스트, 성능 테스트 | 8 |

### 에이전트 운영 규칙
- 각 Phase 시작 시 담당 에이전트가 상세 계획 수립 → 리드 아키텍트가 리뷰
- Phase 간 인수인계: 이전 Phase의 API 계약(엔드포인트, 스키마)을 다음 에이전트에 전달
- 병렬 작업 시 인터페이스(Protocol, API 명세) 먼저 합의 후 각자 구현
- 모든 에이전트는 TDD 원칙 준수 (백엔드), 빌드 검증 필수 (프론트엔드)

## 개발 프로세스
- **백엔드**: TDD (RED → GREEN → REFACTOR)
- **프론트엔드**: 모바일 + PC만 지원 (태블릿 별도 대응 없음)
- **E2E 테스트**: `fullstackfamily-platform-playwright:latest` Docker 이미지 사용
  - Playwright를 별도 설치하지 않음. 반드시 이 Docker 이미지로 실행
- **검증 자동화**: 모든 Phase 계획은 Claude Code가 자동으로 빌드/테스트 검증 가능한 형태로 작성
  - 검증 실패 시 자동 수정 후 재검증하는 사이클 적용
