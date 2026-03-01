# Phase 1~9 상세 개발 계획 리뷰

## Findings

### 1. [높음] Phase 9의 컨테이너 healthcheck가 실제 이미지 구성과 맞지 않아 기본 배포에서 실패할 가능성이 큽니다

- 근거:
  - Phase 9는 `rag-api`와 `rag-frontend` healthcheck를 모두 `curl` 기반으로 정의합니다. (`docs/phases/09_deployment.md:47-48`, `docs/phases/09_deployment.md:69-70`)
  - 그런데 Phase 2의 백엔드 Dockerfile 예시는 `build-essential`만 설치하고 `curl`은 설치하지 않습니다. (`docs/phases/02_backend_foundation.md:357-366`)
  - Phase 7의 프론트엔드 런타임 이미지도 `node:22-alpine` 기반이며 `curl` 설치 단계가 없습니다. (`docs/phases/07_frontend.md:350-365`)
- 영향:
  - 서비스 자체는 떠도 healthcheck가 `curl: not found`로 실패할 수 있습니다.
  - `docker compose ps`, 배포 검증, 장애 판단 기준이 모두 왜곡됩니다.
- 권고:
  - healthcheck를 이미지에 기본 포함된 도구로 바꾸거나,
  - 두 이미지에 `curl` 또는 `wget`을 명시적으로 설치해야 합니다.

### 2. [높음] 배포 절차가 호스트 Python 환경에 의존해 "클린 배포" 시나리오와 충돌합니다

- 근거:
  - Phase 9의 `migrate`는 `cd backend && alembic upgrade head`로 정의되어 있습니다. (`docs/phases/09_deployment.md:193-195`)
  - 배포 검증 스크립트도 인프라만 띄운 뒤 바로 `make migrate`를 호출합니다. (`docs/phases/09_deployment.md:274-283`)
  - 완료 조건 역시 `make infra-up` 다음에 `make migrate`, 그 다음 `make app-up` 순서입니다. (`docs/phases/09_deployment.md:403-408`)
- 영향:
  - 호스트에 Python 의존성과 Alembic 환경이 없으면 "도커 기반 배포"가 문서대로 재현되지 않습니다.
  - 특히 새 머신에서 배포 검증 스크립트가 바로 실패할 수 있습니다.
- 권고:
  - 마이그레이션을 `docker compose run --rm rag-api alembic upgrade head` 또는 `docker compose exec rag-api ...` 방식으로 컨테이너 내부에서 실행하도록 바꾸는 편이 맞습니다.
  - 배포 검증 스크립트와 완료 조건도 같은 방식으로 맞춰야 합니다.

### 3. [높음] Celery 워커 실행 경로와 앱 객체 이름이 문서 내부에서 맞지 않습니다

- 근거:
  - Phase 3의 `worker.py` 예시는 Celery 앱 객체를 `celery_app = Celery("rag", ...)`로 정의합니다. (`docs/phases/03_document_pipeline.md:190-194`)
  - 그런데 Phase 9의 워커 실행 명령은 `celery -A app.worker worker ...`입니다. (`docs/phases/09_deployment.md:53-60`)
- 영향:
  - `app.worker` 모듈 안에 Celery가 자동 탐지할 기본 이름(`celery`, `app`)이 없으면 워커 부팅이 실패할 수 있습니다.
  - 인덱싱, 평가, 알림 같은 비동기 기능이 전부 연쇄적으로 막힙니다.
- 권고:
  - `worker.py`에서 객체명을 `celery`로 맞추거나,
  - 실행 명령을 `celery -A app.worker.celery_app worker ...`처럼 명시적으로 지정해야 합니다.

### 4. [높음] 문서 업로드의 핵심 비동기 경로에 정의되지 않은 값이 사용되어 구현 흐름이 끊깁니다

- 근거:
  - 업로드 API 흐름은 `index_document_task.delay(doc_id)`만 큐에 전달합니다. (`docs/phases/03_document_pipeline.md:234-238`)
  - 그런데 Celery 태스크 예시는 `processor.process(doc_id, file_path)`를 호출하는데 `file_path`가 어디서 오는지 정의되어 있지 않습니다. (`docs/phases/03_document_pipeline.md:197-205`)
- 영향:
  - 문서 업로드 직후 실제 인덱싱 태스크를 구현하는 시점에서 바로 인터페이스 충돌이 발생합니다.
  - 이 경로는 Phase 3 전체의 핵심이므로 실질적인 blocker입니다.
- 권고:
  - 태스크 인자로 `file_path`를 함께 넘기거나,
  - 태스크 내부에서 `doc_id`로 DB를 조회해 저장 경로를 복원하는 방식으로 계약을 먼저 고정해야 합니다.

### 5. [중간] 테스트 전략이 PGVector/PostgreSQL 전제를 SQLite로 대체해 스키마 문제를 놓칠 가능성이 큽니다

- 근거:
  - Phase 2 모델은 `chunks.embedding(Vector(1024))`, `metadata(JSONB)` 등 PostgreSQL/pgvector 지향 필드를 전제로 합니다. (`docs/phases/02_backend_foundation.md:133-138`)
  - 그런데 테스트 인프라는 `in-memory SQLite 또는 테스트 DB`를 제안합니다. (`docs/phases/02_backend_foundation.md:399-403`)
- 영향:
  - SQLite로는 pgvector 타입, JSONB 동작, 실제 마이그레이션 차이를 제대로 검증하지 못합니다.
  - 초기 테스트는 통과해도 실제 PostgreSQL 연결 후 첫 통합 단계에서 깨질 수 있습니다.
- 권고:
  - 최소한 모델/마이그레이션 검증은 PostgreSQL 테스트 DB 기준으로 통일하는 편이 안전합니다.
  - SQLite는 순수 서비스 로직 테스트에만 제한하는 것이 좋습니다.

### 6. [중간] Phase 6의 평가 태스크 예시가 서비스 시그니처와 맞지 않습니다

- 근거:
  - `RAGASEvaluator.evaluate()` 예시는 `evaluate(self, dataset_id: str) -> EvaluationResult` 시그니처를 가집니다. (`docs/phases/06_evaluation_monitoring.md:241-261`)
  - 그런데 Celery 태스크 예시는 `evaluator.evaluate(dataset_id, run_id)`를 호출합니다. (`docs/phases/06_evaluation_monitoring.md:274-280`)
- 영향:
  - 구현자가 문서 그대로 따르면 태스크 연결 시점에서 함수 시그니처 충돌이 발생합니다.
  - 평가 실행 API와 비동기 태스크 계약이 문서상 불명확합니다.
- 권고:
  - `evaluate(dataset_id, run_id)`로 시그니처를 확장할지,
  - `run_id`를 evaluator 내부에서 생성할지 한쪽으로 통일해야 합니다.

### 7. [중간] Phase 8의 Playwright 실행 방식은 Docker Desktop에서 추가 설정이 필요하지만 문서에 전제가 빠져 있습니다

- 근거:
  - Phase 8은 E2E 실행을 `docker run --rm --network host ...`에 전적으로 의존합니다. (`docs/phases/08_integration_e2e_test.md:121-127`, `docs/phases/08_integration_e2e_test.md:397-402`)
  - 이 저장소 문서는 Mac Studio 환경을 명시적으로 다룹니다. (`docs/phases/09_deployment.md:300-314`)
  - Docker 공식 문서에 따르면 Docker Desktop에서 host networking은 4.34+에서 지원되며 Settings에서 별도 활성화가 필요합니다. https://docs.docker.com/engine/network/drivers/host/
- 영향:
  - Mac Studio 기본 환경에서는 문서 그대로 실행해도 E2E가 실패할 수 있습니다.
  - QA 단계 실패 원인이 테스트 코드가 아니라 Docker 설정일 수 있는데, 현재 문서만으로는 구분이 어렵습니다.
- 권고:
  - Phase 8 사전 조건에 "Docker Desktop host networking 활성화"를 추가하거나,
  - `host.docker.internal` 기반 구성으로 바꿔 Docker Desktop 의존성을 낮추는 편이 낫습니다.

### 8. [낮음] Phase 8의 성능 테스트를 일반 `pytest tests/` 게이트에 포함하면 회귀 테스트가 과도하게 불안정해질 수 있습니다

- 근거:
  - 성능 테스트는 절대 시간 기준(`검색 응답 시간 5초 이내`)과 동시성 측정을 포함합니다. (`docs/phases/08_integration_e2e_test.md:279-305`)
  - 완료 조건은 `cd backend && pytest tests/ -v --tb=short`로 전체 테스트 디렉토리를 한 번에 실행합니다. (`docs/phases/08_integration_e2e_test.md:394-395`)
- 영향:
  - 머신 성능, Ollama 상태, 로컬 부하에 따라 테스트가 쉽게 흔들릴 수 있습니다.
  - 기능 회귀와 성능 회귀가 같은 게이트에 섞여 원인 분석이 어려워집니다.
- 권고:
  - `tests/performance/`는 별도 마커나 별도 명령으로 분리하는 편이 좋습니다.
  - 기본 완료 조건은 기능 테스트 중심으로 두고, 성능은 baseline 측정/추세 비교로 분리하는 것이 안전합니다.

## 1차 리뷰 반영 상태

| # | 이슈 | 수정 상태 |
|---|------|----------|
| 1 | healthcheck curl 미설치 | ✅ 해결됨 — rag-api는 Python urllib, frontend는 wget 사용 |
| 2 | migrate 호스트 Python 의존 | ✅ 해결됨 — `docker compose run --rm rag-api alembic upgrade head` |
| 3 | Celery worker 앱 객체명 | ✅ 해결됨 — `celery -A app.worker.celery_app worker ...` |
| 4 | file_path 미정의 (Celery 태스크) | ✅ 해결됨 — `get_document_file_path()` DB 조회 추가 |
| 5 | SQLite 테스트 vs PostgreSQL | ✅ 해결됨 — PostgreSQL 테스트 DB 사용 명시 |
| 6 | RAGASEvaluator 시그니처 | ✅ 해결됨 — `evaluate(dataset_id, run_id)` 통일 |
| 7 | Docker Desktop host networking | ✅ 해결됨 — Phase 8 사전 조건에 추가 |
| 8 | 성능 테스트 분리 | ✅ 해결됨 — `@pytest.mark.performance` + `-m "not performance"` |

---

## 2차 리뷰 (Context7 MCP 기반 최신 라이브러리 검증)

### 9. [높음] Langfuse v3 셀프호스팅이 단일 컨테이너에서 불가능합니다 — ✅ 수정됨

- **근거**: Context7에서 Langfuse v3 공식 문서 확인 결과, v3는 `langfuse/langfuse:3` (Web) + `langfuse/langfuse-worker:3` (Worker) 2개 컨테이너 구성이 필수
- **추가 필수 의존성**: 전용 Redis(큐/캐시), MinIO(S3 호환 스토리지, 이벤트 업로드), `ENCRYPTION_KEY`(64자 hex)
- **수정 내용**:
  - Phase 6 (Step 6.1): `langfuse-web`, `langfuse-worker`, `langfuse-redis`, `langfuse-minio`, `rag-clickhouse` 5개 서비스로 확장
  - Phase 9 (Step 9.1): 동일하게 반영, `.env.example`에 `LANGFUSE_ENCRYPTION_KEY`, `CLICKHOUSE_USER/PASSWORD`, `LANGFUSE_REDIS_AUTH`, `MINIO_ROOT_USER/PASSWORD` 추가
  - Phase 00: 서비스 목록 업데이트

### 10. [높음] Tailwind CSS v4는 설정 방식이 근본적으로 변경되었습니다 — ✅ 수정됨

- **근거**: Context7에서 Tailwind CSS v4 공식 문서 확인 결과:
  - `tailwind.config.ts` 파일 **폐지** → CSS-first 설정 (`@theme` 디렉티브)
  - PostCSS 플러그인: `tailwindcss` → `@tailwindcss/postcss`로 변경
  - `postcss-import`, `autoprefixer` 자동 처리 (별도 설치 불필요)
  - CSS: `@tailwind base/components/utilities` → `@import "tailwindcss"`
- **수정 내용**:
  - Phase 7 (Step 7.1): `tailwind.config.ts` 제거, `postcss.config.mjs` + `@tailwindcss/postcss`, CSS 파일 `@import "tailwindcss"` + `@theme` 방식으로 변경
  - 생성 파일 목록 업데이트

### 11. [중간] RAGAS 최신 API는 클래스 기반 메트릭 초기화가 필수입니다 — ✅ 수정됨

- **근거**: Context7에서 RAGAS 최신 문서 확인 결과:
  - 메트릭이 pre-instantiated 인스턴스(`faithfulness`)에서 클래스 기반(`Faithfulness(llm=evaluator_llm)`)으로 변경
  - `AnswerRelevancy`는 `embeddings` 인자도 필수
  - LLM 래퍼: `ragas.llms.LangchainLLMWrapper` 사용
  - `langchain-openai` 패키지 의존성 추가 필요
- **수정 내용**:
  - Phase 6 (Step 6.5): `RAGASEvaluator` 코드를 클래스 기반 메트릭 API로 전면 수정
  - Phase 2 (Step 2.1): `pyproject.toml` 의존성에 `langchain-openai>=0.3` 추가

## 총평

1차 리뷰에서 발견된 8개 이슈는 모두 해결되었습니다. 2차 리뷰(Context7 MCP 기반)에서 외부 라이브러리의 최신 API/설정 변경사항 3건을 추가로 발견하여 수정 완료했습니다. 특히 Langfuse v3의 아키텍처 변경(단일→다중 컨테이너)과 Tailwind CSS v4의 설정 패러다임 전환(JS config→CSS-first)은 실제 구현 시 바로 막히는 중대 이슈였습니다.
