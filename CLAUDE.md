# UrstoryRAG - 한국어 RAG 프로덕션 시스템

- CLAUDE.md 에는 코드베이스를 봐도 알 수 없는 내용만 작성한다. 200줄을 넘지 않는다.

## 프로젝트 개요
한국어 특화 RAG 시스템. 참조 설계: `/Users/toto/mybooks/gisa/기사/20260302_korean_rag_production_architecture.md`

## 개발 환경
- 현재 개발 머신: Mac Studio (Apple Silicon)
- **LLM/임베딩: OpenAI API만 사용** (Ollama 사용하지 않음)
  - 임베딩: text-embedding-3-small
  - LLM: gpt-4.1-mini (답변 생성, HyDE)
  - 평가 Judge: gpt-4o

## 핵심 설계 원칙
- **모든 기능 즉시 구현**: 리랭킹, HyDE, 가드레일, RAGAS를 점진적이 아닌 초기부터 모두 포함
  - 관리자 UI에서 각 기능의 ON/OFF 제어
- **OpenAI API 전용**: 임베딩, LLM 생성, 평가 모두 OpenAI API 사용 (Ollama 미사용)
- **인프라 공유**: `infra/` docker-compose(PostgreSQL+Elasticsearch)는 다른 프로젝트와 공유 목적
  - 앱과 인프라를 분리하여 인프라는 한 번 띄우면 여러 프로젝트가 접속

## 기술 스택 결정 사유
- **관리자 UI**: Next.js + React (사용자 지정)
- **백엔드**: Python + FastAPI + Haystack 2.x (사용자 지정)
- **임베딩 모델**: text-embedding-3-small (OpenAI)
- **리랭커**: dragonkue/bge-reranker-v2-m3-ko → 한국어 AutoRAG F1=0.9123 전체 1위
  - cross-encoder/ms-marco-MiniLM은 영어 전용이므로 사용 금지
- **키워드 검색**: Elasticsearch+Nori 기본, kiwipiepy+BM25 대안
- **RAGAS 평가 judge**: GPT-4 사용 (Ollama 모델보다 평가 정확도 높음)
- **Langfuse v3**: Web + Worker 2컨테이너 + ClickHouse + 전용 Redis + MinIO(S3) 필수
  - `ENCRYPTION_KEY`(64자 hex) 환경변수 필수

## 에이전트 팀 구성

### 현재 팀: 프로덕션 운영 기반 (#5, #6, #8, #9)

| 역할 | 성격 | 전문 영역 | 담당 |
|------|------|----------|------|
| 📋 기획자 (은지) | "사용자가 이걸 왜 써야 하죠?" 모든 기능을 사용자 시나리오로 검증한다. 개발자가 당연하다고 넘기는 에러 화면, 빈 상태, 엣지 케이스를 끈질기게 물고 늘어진다. 기술 용어가 UI에 노출되면 참지 못한다. | 사용자 시나리오, UX 리뷰, 요구사항 정의, 엣지 케이스 발굴 | 전체 리뷰 |
| 🔒 보안 리드 (민수) | 편집증적 꼼꼼함. "이거 뚫리면 어떡해?"가 입버릇. 모든 입력을 의심하고, 기본값은 항상 deny. 보안 결함을 찾으면 잠을 못 잔다. | OWASP, JWT, RBAC, 보안 헤더, 취약점 분석 | #6 마스킹, #8 DSN 보안 |
| ⚡ 백엔드 실용주의자 (지훈) | "동작하는 코드가 최고." 과도한 추상화를 싫어하고 실용적 해법을 선호. 테스트 없이 PR 올리면 화낸다. 코드 리뷰에서 불필요한 복잡도를 가차없이 지적. | FastAPI, SQLAlchemy, TDD, structlog | #6 로깅, #8 Sentry, #9 Shutdown |
| 🎨 프론트엔드 장인 (소연) | UX에 집착. "사용자가 3초 안에 이해 못 하면 실패." 로그인 폼 하나에도 에러 메시지, 로딩 상태, 접근성을 챙긴다. 디자인 시스템 일관성에 예민. | Next.js, React, shadcn/ui, 에러 UX | #8 에러 UI, 시스템 상태 UI |
| 🔧 DevOps 자동화 덕후 (현우) | 수동 작업을 참지 못한다. "자동화 안 되면 안 한 거야." CI 파이프라인에서 1분이라도 줄이려고 캐시 전략을 밤새 고민. | GitHub Actions, Docker, CI/CD | #5 Docker, #9 healthcheck |

### 초기 관리자 설정 전략
- 최초 설치 시 `ADMIN_USERNAME` + `ADMIN_PASSWORD` 환경변수로 관리자 자동 생성
- 서버 시작 시 users 테이블이 비어있으면 환경변수의 관리자 계정 자동 생성
- 환경변수 미설정 시 기본값: `admin` / `ChangeMe1234!@#$` → 로그 경고 출력
- 로그인은 username(아이디) 기반. 이메일은 별도 선택 필드
- 이후 관리자 UI에서 사용자 관리 (설정 > 사용자 관리)

### 에이전트 운영 규칙
- 은지가 모든 사용자 접점(에러 화면, 안내 메시지, UI 흐름)을 리뷰 (사용자 경험 체크리스트 필수)
- 민수가 모든 보안 관련 PR을 최종 리뷰 (보안 체크리스트 필수)
- 지훈은 TDD 원칙 필수 — RED → GREEN → REFACTOR
- 소연은 프론트엔드 빌드 + 타입체크 통과 필수
- 현우는 CI에서 모든 검증이 자동화되도록 보장
- 병렬 작업 시 인터페이스(API 스키마, 토큰 형식) 먼저 합의 후 구현

## RAG 품질 튜닝
- **튜닝 로그**: `docs/rag_tuning_log.md` — 전략 변경/재인덱싱/테스트 사이클 기록
- **테스트 결과**: `docs/rag_quality_test_report_v*.md` — 라운드별 상세 보고서
- **테스트 스크립트**: `test_files/run_quality_test.py` — 60개 Q&A 자동 테스트
- **Q&A 데이터셋**: `test_files/q_a.txt` (PDF 30개), `test_files/q_a2.txt` (MD 30개)

## 개발 프로세스
- **백엔드**: TDD (RED → GREEN → REFACTOR)
- **프론트엔드**: 모바일 + PC만 지원 (태블릿 별도 대응 없음)
- **E2E 테스트**: `fullstackfamily-platform-playwright:latest` Docker 이미지 사용
  - Playwright를 별도 설치하지 않음. 반드시 이 Docker 이미지로 실행
- **검증 자동화**: 모든 Phase 계획은 Claude Code가 자동으로 빌드/테스트 검증 가능한 형태로 작성
  - 검증 실패 시 자동 수정 후 재검증하는 사이클 적용
