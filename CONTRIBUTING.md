# 기여 가이드

UrstoryRAG는 한국어 특화 RAG 프로덕션 시스템입니다. 본 문서는 프로젝트에 기여하려는 개발자를 위한 가이드입니다.

## 1. 기여 가이드라인

### 기여 전 확인 사항

- CLAUDE.md를 읽고 프로젝트의 핵심 설계 원칙을 이해합니다
- docs/architecture/ 문서를 통해 시스템 아키텍처를 파악합니다
- docs/phases/00_development_roadmap.md에서 개발 로드맵을 확인합니다

### 기여 가능한 영역

1. **백엔드** (Python, FastAPI, Haystack 2.x)
   - RAG 파이프라인 개선
   - 임베딩/리랭킹/검색 최적화
   - API 엔드포인트 개발
   - 데이터베이스 스키마 개선

2. **프론트엔드** (Next.js 15, React 19, Tailwind CSS 4)
   - 사용자 인터페이스 개발
   - 관리자 대시보드 기능
   - 성능 최적화

3. **인프라** (Docker, PostgreSQL, Elasticsearch, Redis)
   - 컨테이너 구성 개선
   - 데이터베이스 마이그레이션
   - 모니터링/로깅 개선

4. **테스트 및 문서**
   - 통합 테스트 작성
   - E2E 테스트 추가
   - 문서 작성/개선

### 기여하는 방법

1. 이 저장소를 fork합니다
2. feature 브랜치를 생성합니다
3. 코드 변경 사항을 커밋합니다
4. Pull Request를 작성합니다
5. 코드 리뷰를 거쳐 merge됩니다

## 2. 개발 환경 설정

### 필수 사항

- Python 3.12 이상
- Node.js 20 이상
- Docker & Docker Compose
- Git

### 백엔드 설정

```bash
cd backend

# Python 가상환경 생성
python3.12 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 값 설정

# 데이터베이스 마이그레이션
alembic upgrade head

# 서버 실행
python -m uvicorn app.main:app --reload --port 8000
```

### 프론트엔드 설정

```bash
cd frontend

# 의존성 설치
npm install

# 환경 변수 설정
cp .env.example .env.local
# .env.local 파일을 편집하여 필요한 값 설정

# 개발 서버 실행
npm run dev
```

### 인프라 설정

```bash
cd infra

# Docker Compose로 의존성 서비스 실행
docker-compose up -d

# 서비스 상태 확인
docker-compose ps
```

### 환경 변수

필수 환경 변수:
- OPENAI_API_KEY: OpenAI API 키
- DATABASE_URL: PostgreSQL 연결 문자열
- ELASTICSEARCH_HOST: Elasticsearch 호스트
- REDIS_URL: Redis 연결 문자열
- LANGFUSE_API_KEY: Langfuse API 키
- ENCRYPTION_KEY: Langfuse용 암호화 키 (64자 hex)

## 3. 브랜치 전략

### 브랜치 명명 규칙

```
feature/xxx      - 새로운 기능 추가
fix/xxx          - 버그 수정
hotfix/xxx       - 긴급 수정 (프로덕션 핫픽스)
docs/xxx         - 문서 작성/수정
refactor/xxx     - 코드 리팩토링
test/xxx         - 테스트 추가/개선
chore/xxx        - 빌드, 의존성, 도구 설정
```

### 예시

```
feature/hybrid-search-improvement
fix/embedding-cache-issue
hotfix/security-vulnerability
docs/rag-architecture
refactor/pipeline-simplification
test/e2e-admin-dashboard
```

### 브랜치 생성 및 관리

1. main 브랜치에서 최신 코드 pull
   ```bash
   git checkout main
   git pull origin main
   ```

2. 새 브랜치 생성
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. 작업 완료 후 커밋 및 푸시
   ```bash
   git add .
   git commit -m "feat: your feature description"
   git push origin feature/your-feature-name
   ```

## 4. 커밋 컨벤션

Conventional Commits 규칙을 준수합니다.

### 커밋 메시지 형식

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

- **feat**: 새로운 기능 추가
- **fix**: 버그 수정
- **docs**: 문서 추가/수정
- **style**: 코드 스타일 변경 (포맷팅, 세미콜론 등)
- **refactor**: 코드 리팩토링
- **perf**: 성능 개선
- **test**: 테스트 추가/수정
- **ci**: CI/CD 설정 변경
- **chore**: 빌드, 의존성 등 기타 변경

### Scope

변경 영역 (선택):
- backend, frontend, infra, docs 등

### Subject

- 명령조 사용 (Add, Fix, Update 등)
- 50자 이하
- 마침표 금지
- 한글/영어 혼용 가능 (영어 권장)

### Body

- 72자 이하로 줄바꿈
- 무엇을 변경했는지 설명
- 왜 변경했는지 설명 (선택)

### Footer

- Breaking changes 표시: `BREAKING CHANGE: description`
- 이슈 연결: `Fixes #123`

### 예시

```
feat(backend): implement hybrid search with query expansion

Add HyDE-based query expansion and keyword search integration
to improve RAG retrieval quality for Korean documents.

- Implement HyDE question generator using GPT-4-mini
- Add BM25 keyword search integration with Elasticsearch
- Combine dense and sparse retrieval with reciprocal rank fusion
- Add comprehensive test cases

Fixes #42
```

## 5. PR 작성 규칙

### PR 제목

Conventional Commits 형식을 따릅니다.

```
feat(backend): implement hybrid search with query expansion
```

### PR 본문 템플릿

```markdown
## 개요
PR이 해결하는 문제나 구현하는 기능에 대한 설명

## 변경 사항
- 변경 1
- 변경 2
- 변경 3

## 테스트 결과
- [x] 단위 테스트 통과
- [x] 통합 테스트 통과
- [x] E2E 테스트 통과 (해당하는 경우)

## 체크리스트
- [x] 코드 스타일 검증 통과
- [x] 테스트 커버리지 확인
- [x] 문서 업데이트
- [x] Breaking change 없음

## 관련 이슈
Fixes #123
Related to #456
```

### PR 검토 기준

1. 코드 스타일 준수
2. 테스트 커버리지 (백엔드 75% 이상)
3. 성능 영향 평가
4. 문서 업데이트
5. Breaking change 없음

## 6. 코드 스타일

### Python 코드 스타일

**Linter/Formatter**: Ruff

```bash
# ruff 검사
ruff check backend/

# 자동 포맷팅
ruff format backend/
```

**코드 스타일 기준**:
- PEP 8 준수
- 최대 줄 길이: 100자
- 타입 힌트 필수
- 명확한 변수/함수 이름

예시:
```python
def retrieve_documents(
    query: str,
    top_k: int = 5,
    use_hybrid_search: bool = True,
) -> list[Document]:
    """문서 검색."""
    if not query:
        raise ValueError("Query must not be empty")

    results = []
    # 구현
    return results
```

### JavaScript/TypeScript 코드 스타일

**Linter**: ESLint
**Formatter**: Prettier

```bash
# ESLint 검사
npm run lint

# 자동 포맷팅
npm run format

# 빌드 검증
npm run build
```

**코드 스타일 기준**:
- 최대 줄 길이: 100자
- Trailing comma: ES5
- 세미콜론 필수
- 명확한 변수/함수 이름

예시:
```typescript
async function fetchDocuments(
  query: string,
  options: SearchOptions = {},
): Promise<Document[]> {
  if (!query.trim()) {
    throw new Error('Query must not be empty');
  }

  const results = await searchClient.search(query, options);
  return results;
}
```

## 7. 테스트 작성 규칙

### 백엔드 테스트 (TDD 필수)

**프레임워크**: pytest

```bash
# 테스트 실행
pytest backend/tests/ -v

# 커버리지 확인
pytest backend/tests/ --cov=backend/app --cov-report=html

# 특정 테스트 실행
pytest backend/tests/unit/test_pipeline.py -v
```

**TDD 사이클**:
1. RED: 실패하는 테스트 작성
2. GREEN: 최소한의 코드로 테스트 통과
3. REFACTOR: 코드 개선

**테스트 구조**:
```
tests/
├── unit/           - 단위 테스트 (함수/클래스)
├── integration/    - 통합 테스트 (여러 컴포넌트)
└── conftest.py     - 공용 fixtures
```

**테스트 작성 예시**:
```python
import pytest
from app.services.embedding import EmbeddingService
from app.models import Document

@pytest.fixture
def embedding_service():
    return EmbeddingService()

def test_embed_documents_returns_vectors(embedding_service):
    """문서 임베딩이 벡터를 반환한다."""
    # Arrange
    docs = [
        Document(content="한국어 문서 1"),
        Document(content="한국어 문서 2"),
    ]

    # Act
    embeddings = embedding_service.embed_documents(docs)

    # Assert
    assert len(embeddings) == 2
    assert all(len(emb) == 384 for emb in embeddings)

@pytest.mark.parametrize("query", ["", "  ", None])
def test_embed_query_raises_on_invalid_input(
    embedding_service,
    query,
):
    """잘못된 쿼리에 대해 ValueError를 발생한다."""
    with pytest.raises(ValueError):
        embedding_service.embed_query(query)
```

**테스트 커버리지**:
- 최소 75% 이상
- Critical path 100%
- Edge case 포함

### 프론트엔드 테스트

**빌드 검증 필수**:
```bash
npm run build
```

**E2E 테스트**: Playwright (Docker 이미지 사용)

```bash
# Docker 이미지를 사용한 E2E 테스트 실행
docker run --rm \
  -v $(pwd):/app \
  -w /app/frontend \
  fullstackfamily-platform-playwright:latest \
  npx playwright test

# 로컬 테스트 (Docker 사용, Playwright 직접 설치 금지)
docker run --rm \
  -v $(pwd):/app \
  -w /app/frontend \
  fullstackfamily-platform-playwright:latest \
  bash -c "npm install && npx playwright test"
```

**E2E 테스트 작성 예시**:
```typescript
import { test, expect } from '@playwright/test';

test('관리자가 문서를 검색할 수 있다', async ({ page }) => {
  // Arrange
  await page.goto('http://localhost:3000/admin/documents');

  // Act
  await page.fill('input[placeholder="검색"]', '한국어');
  await page.click('button[type="submit"]');

  // Assert
  await expect(page.locator('text=검색 결과')).toBeVisible();
  const results = await page.locator('.document-item').count();
  expect(results).toBeGreaterThan(0);
});

test('모바일 화면에서 반응형 레이아웃이 정상 작동한다', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto('http://localhost:3000');

  // 모바일 네비게이션 확인
  await expect(page.locator('.mobile-menu')).toBeVisible();
});
```

**주의사항**:
- Playwright를 직접 설치하지 말 것
- 반드시 fullstackfamily-platform-playwright:latest Docker 이미지 사용
- 모바일(375x667)과 PC(1920x1080) 해상도만 테스트

## 8. 이슈 등록 가이드

### 버그 보고

```markdown
## 문제 설명
버그가 무엇인지 명확하게 설명

## 재현 방법
1. 단계 1
2. 단계 2
3. 단계 3

## 예상 동작
어떻게 동작해야 하는가

## 실제 동작
실제로 어떻게 동작하는가

## 환경
- OS: macOS 14.0
- Python: 3.12.1
- Node.js: 20.10.0

## 추가 정보
로그, 스크린샷, 에러 메시지 등
```

### 기능 요청

```markdown
## 기능 설명
원하는 기능에 대한 설명

## 배경
이 기능이 필요한 이유

## 해결책
어떻게 구현할 수 있을지 제안 (선택)

## 대안
다른 해결 방법 (선택)

## 추가 정보
참고 자료, 다른 PR/이슈 링크 등
```

### 라벨 사용

- `bug`: 버그 보고
- `enhancement`: 기능 개선
- `documentation`: 문서 작성
- `question`: 질문
- `backend`, `frontend`, `infra`: 영역 표시
- `high`, `medium`, `low`: 우선순위

## 코드 리뷰 프로세스

### 리뷰어 역할

1. 코드 스타일/품질 검증
2. 테스트 커버리지 확인
3. 성능 영향 검토
4. 문서/API 변경 확인
5. 보안 취약점 확인

### 저자 역할

1. PR 작성 시 자세한 설명 제공
2. 리뷰 의견에 적극 응답
3. 요청사항 반영 후 재요청
4. 승인 후 merge 전담

## 기타 지침

### 성능 최적화

- 검색 응답 시간: < 1초
- 프론트엔드 빌드 시간: < 60초
- 번들 크기: < 200KB (gzip)

### 보안

- API 키는 환경 변수에만 저장
- 민감한 정보는 로깅하지 않음
- 정기적인 의존성 업데이트
- 입력 값 검증 필수

### 문서

- 모든 공개 API에 docstring 필수
- 복잡한 로직은 주석 추가
- README 및 CLAUDE.md 최신화

## 질문 및 지원

- 이슈 페이지에서 질문 등록
- 토론 포럼 이용 (있는 경우)
- 핵심 멤버에게 직접 연락 (긴급 시)

## 라이선스

이 프로젝트에 기여함으로써 귀하의 코드가 프로젝트의 라이선스 하에 배포되는 것에 동의합니다.

---

감사합니다! 프로젝트에 기여해주세요.
