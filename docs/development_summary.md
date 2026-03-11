# UrstoryRAG 개발 이력 요약

12개 이슈 처리 및 IBM Docling PDF 파싱 도입까지의 개발 과정을 정리한다.

---

## 처리된 이슈 (12건)

### Phase 12: 보안 강화 — 이슈 #1, #2, #3, #4

| 이슈 | 제목 | 핵심 구현 |
|:---:|------|------|
| #1 | JWT 인증/인가 시스템 | bcrypt + HS256 JWT (access 30분 / refresh 7일), RBAC (admin/user), Redis 토큰 블랙리스트, 초기 관리자 자동 생성 |
| #2 | CORS 화이트리스트 및 보안 헤더 | 환경변수 기반 오리진 관리, X-Content-Type-Options, X-Frame-Options, CSP 등 보안 미들웨어 |
| #3 | Rate Limiting | slowapi + Redis 연동, 로그인 5/min, 검색 30/min, 업로드 10/min |
| #4 | GitHub Actions CI 파이프라인 | pytest + ruff lint + Alembic 마이그레이션 + 프론트엔드 빌드 + Docker 이미지 검증 |

**커밋**: `ce9e541`, PR #22로 머지

---

### Phase 13: 프로덕션 운영 기반 — 이슈 #5, #6, #8, #9

| 이슈 | 제목 | 핵심 구현 |
|:---:|------|------|
| #5 | Docker 이미지 최적화 | 멀티스테이지 빌드, non-root 사용자, standalone 모드 (Next.js), GHCR 자동 푸시 |
| #6 | 구조화된 로깅 (structlog) | JSON/Console 포맷 전환, 민감 정보 마스킹 (API Key, JWT, 비밀번호), request_id 추적 |
| #8 | 에러 추적 (Sentry) | Sentry SDK 통합, PII 전송 차단, Authorization/Cookie 헤더 제거, 사용자 에러 화면에 request_id 표시 |
| #9 | Graceful Shutdown + Health Probe | Liveness/Readiness/Startup 프로브, SIGTERM 시 30초 정리, 셧다운 중 503 + Retry-After 응답 |

**커밋**: `fcfd6a3`, PR #23으로 머지

---

### Langfuse v3 모니터링 — 이슈 #7

| 이슈 | 제목 | 핵심 구현 |
|:---:|------|------|
| #7 | Langfuse v3 모니터링 검증 및 안정화 | Web + Worker + ClickHouse + Redis + MinIO 풀 스택 통합, 검색 파이프라인 트레이싱, no-op 모드 지원 |

**커밋**: `0253eca`

---

### Phase 14: Redis 응답 캐싱 레이어 — 이슈 #10

| 이슈 | 제목 | 핵심 구현 |
|:---:|------|------|
| #10 | Redis 응답 캐싱 | SHA-256 키 해싱, 설정/문서 변경 시 자동 무효화, X-Cache 헤더, 3-tier 설정 캐시, maxmemory 256MB + allkeys-lru |

**커밋**: `76993c4`, PR #24로 머지

---

### Circuit Breaker — 이슈 #12

| 이슈 | 제목 | 핵심 구현 |
|:---:|------|------|
| #12 | Circuit Breaker 및 재시도 로직 | 연속 5회 실패 시 30초 차단 (OPEN → HALF_OPEN → CLOSED), Exponential Backoff 재시도 (3회), Graceful Degradation |

**커밋**: `0500185`, PR #25로 머지

---

### 공개 테스트 데이터셋 — 이슈 #21

| 이슈 | 제목 | 핵심 구현 |
|:---:|------|------|
| #21 | 공개 테스트 데이터셋 | 공공누리 제1유형 PDF 5개 + 직접 작성 MD 5개, 68개 Q&A, LLM-as-Judge + 키워드 재현율 자동 평가 |

**커밋**: `c191907`

---

## Phase 15: IBM Docling PDF 레이아웃 인식 파싱

### 도입 배경

기존 `pypdf`는 PDF에서 **텍스트만 추출**하여 다음 문제가 있었다:

- 테이블 구조 붕괴 (숫자가 뒤섞여 검색 불가)
- 헤더 감지가 줄 길이 휴리스틱에 의존 (오탐/미탐)
- 다단 컬럼이 하나의 텍스트 스트림으로 병합
- 스캔 PDF 미지원

Open-Parse (GitHub 3.2K stars)를 검토했으나 16개월간 업데이트 없이 방치 상태. **IBM Docling** (55K stars, MIT, 주간 릴리즈)을 선택했다.

### Docling이 해결하는 것

| 문제 | Before (pypdf) | After (Docling) |
|------|:---:|:---:|
| 테이블 정확도 | 0% (구조 손실) | 90%+ (TableFormer) |
| 헤더 감지 | 줄 길이 휴리스틱 | 레이아웃 모델 기반 |
| 다단 컬럼 | 텍스트 뒤섞임 | 읽기 순서 보존 |
| 스캔 PDF | 불가 | OCR 지원 (EasyOCR) |
| 출력 형식 | 평문 텍스트 | 구조화된 마크다운 |

### 아키텍처

```
[ Before ] PDF → PyPDFToDocument (텍스트) → SectionHeaderChunking (휴리스틱 헤더)
[ After  ] PDF → Docling (마크다운)        → SectionHeaderChunking (정확한 # 헤더)
```

기존 청킹 파이프라인(`SectionHeaderChunking`, `ContextualChunking`)은 수정 없이 재사용한다. Docling의 마크다운 출력에 `#` 헤더가 포함되므로 오히려 더 정확한 breadcrumb 계층이 생성된다.

### 핵심 구현

**DoclingPDFConverter** (`backend/app/services/document/docling_converter.py`)
- Docling `DocumentConverter`를 래핑
- **지연 초기화**: `_get_converter()` 호출 시에만 import (앱 시작 속도 보존)
- **자동 폴백**: Docling 실패 시 pypdf로 전환, 서비스 중단 없음
- 메타데이터에 `converter: "docling" | "pypdf_fallback"` 기록

**설정 제어** (`RAGSettings`)

```python
pdf_parser: str = "docling"         # docling | pypdf
ocr_enabled: bool = False
ocr_languages: list[str] = ["ko", "en"]
table_extraction_enabled: bool = True
```

관리자 UI에서 실시간 변경 가능. GPU가 없는 서버에서는 `pdf_parser=pypdf`로 전환하면 된다.

### GPU/CPU 호환성

Docling은 GPU 없이도 동작한다. PyTorch가 하드웨어를 자동 감지한다.

| 환경 | GPU 가속 | 비고 |
|------|:---:|------|
| Mac (Apple Silicon) | MPS | Celery `--pool=solo` 필요 (Metal은 fork 불가) |
| Linux + NVIDIA | CUDA | 가장 빠른 환경 |
| Linux CPU only | -- | 느리지만 정상 동작 |

**macOS 주의사항**: Celery의 기본 fork 기반 워커는 Metal/MPS와 호환되지 않는다 (SIGABRT 발생). `--pool=solo` 옵션으로 실행해야 MPS GPU를 사용할 수 있다.

```bash
celery -A app.worker:celery_app worker --pool=solo --loglevel=info
```

### Docling 모델 (첫 실행 시 자동 다운로드)

| 모델 | 용도 | 크기 | 디바이스 |
|------|------|:---:|---------|
| Layout (Heron) | 레이아웃 분석 | ~100MB | CPU/MPS/CUDA |
| TableFormer | 테이블 구조 인식 | ~100MB | CPU |
| Picture Classifier | 이미지 분류 | ~50MB | CPU/MPS/CUDA |
| EasyOCR ko+en | 한국어/영어 OCR | ~200MB | CPU/MPS/CUDA |

총 ~450MB, `~/.cache/docling/models/`에 캐시된다.

### 성능

| 항목 | pypdf | Docling (OCR 없음) | Docling (OCR 있음) |
|------|:---:|:---:|:---:|
| 변환 속도 | ~50 pages/sec | ~1.5 pages/sec | ~1 page/sec |
| 테이블 정확도 | 0% | ~90%+ | ~85%+ |
| 헤더 감지 | 휴리스틱 | 레이아웃 기반 | 레이아웃 기반 |

변환 속도가 느려지지만 Celery 비동기 처리이므로 사용자 대기에 영향 없다.

### 품질 측정 결과

공개 데이터셋 68개 Q&A, 12개 문서 기준:

| 지표 | 이전 (pypdf) | Docling 적용 후 |
|------|:---:|:---:|
| LLM Judge 평균 | 90.3 | **92.0** |
| GOOD (70점 이상) | 95.2% | **96%** |
| FAIL (40점 미만) | 4.8% | **3%** |
| 키워드 재현율 | 60.8% | **67.7%** |
| 검색 적중률 | -- | **100%** |

PDF 테이블이 포함된 문서에서 숫자/통계 검색 정확도가 크게 개선되었다.

### TDD 구현 순서

```
Step 0: docling >= 2.78 의존성 추가 + 환경 검증
Step 1: RAGSettings에 pdf_parser, ocr_enabled 등 설정 추가 (RED → GREEN)
Step 2: DoclingPDFConverter 구현 + pypdf 폴백 (RED → GREEN)
Step 3: DocumentConverter에 Docling 통합 (RED → GREEN)
Step 4: Processor/Task에서 RAGSettings → DocumentConverter 설정 전달 (RED → GREEN)
Step 5: 실제 PDF 통합 테스트 + 품질 검증
Step 6: 전체 테스트 회귀 확인 (517 단위 + 8 통합 테스트 통과)
```

### 테스트

- **단위 테스트**: 11개 (DoclingPDFConverter) + 8개 (DocumentConverter 통합) + RAGSettings + Processor
- **통합 테스트**: 8개 (실제 PDF 변환, 폴백, 설정 토글, 청킹 파이프라인)
- **품질 테스트**: 68개 Q&A LLM-as-Judge 자동 평가

---

## 전체 시스템 계층

12개 이슈 처리 후의 시스템 아키텍처:

```
사용자 → 프론트엔드 (Next.js 15)
  ↓
보안 헤더 미들웨어 (X-Content-Type-Options, X-Frame-Options, CSP)
  ↓
Rate Limiter (slowapi + Redis, 엔드포인트별 제한)
  ↓
JWT 인증 (access/refresh, RBAC)
  ↓
구조화된 로깅 (structlog, request_id 추적)
  ↓
Redis 응답 캐시 (SHA-256 키, 자동 무효화)
  ↓
Circuit Breaker (연속 실패 감지, 자동 차단/복구)
  ↓
문서 변환 (Docling PDF → 마크다운, pypdf 폴백)
  ↓
RAG 파이프라인 (Haystack, 하이브리드 검색, 리랭킹, HyDE)
  ↓
데이터베이스 (PostgreSQL+PGVector, Elasticsearch+Nori, Redis)
  ↓
모니터링 (Langfuse v3, Sentry)
```

---

## 남은 오픈 이슈

| 이슈 | 제목 | 우선순위 |
|:---:|------|:---:|
| #11 | 커넥션 풀링 최적화 | high |
| #13 | 프로덕션 배포 가이드 | high |
| #14 | API 문서 강화 | medium |
| #15 | 백엔드 테스트 커버리지 85% | medium |
| #16 | E2E 테스트 시나리오 확대 | medium |
| #17 | React Error Boundary 개선 | medium |
| #18 | 데이터 백업/복구 전략 | medium |
| #19 | 의존성 보안 스캔 자동화 | medium |
| #20 | 프론트엔드 접근성 개선 | medium |
