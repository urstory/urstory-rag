# Phase 7: 관리자 프론트엔드 상세 개발 계획

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 7 |
| 담당 | 프론트엔드 엔지니어 |
| 의존성 | Phase 2 (API 명세 기반) |
| 병렬 가능 | Phase 3~6과 병렬 (빌드 검증만) |
| 참조 문서 | `docs/architecture/05_frontend.md`, `docs/architecture/06_api_design.md` |

## 사전 조건

- Phase 2 완료 (API 엔드포인트 명세, 응답 스키마)
- Node.js 22+, pnpm 설치

## 설계 원칙

- **반응형**: 모바일(≤768px), PC(>768px) — 태블릿 별도 대응 없음
- **API 연동**: 백엔드 API 미완성 구간은 mock 데이터로 개발, 빌드 검증만 수행
- **E2E 테스트는 Phase 8에서** — 이 Phase에서는 빌드/lint/type-check만

## 상세 구현 단계

### Step 7.1: 프로젝트 초기화

> **중요**: Tailwind CSS v4는 설정 방식이 근본적으로 변경되었습니다.
> - `tailwind.config.ts` 파일이 **폐지**됨 → CSS 파일에서 `@theme` 디렉티브로 설정
> - `postcss.config.js` → `postcss.config.mjs`로 변경, 플러그인은 `@tailwindcss/postcss`
> - `postcss-import`, `autoprefixer` 자동 처리 → 별도 설치 불필요
> - CSS에서 `@tailwind base/components/utilities` → `@import "tailwindcss"` 로 변경

#### 생성 파일
- `frontend/package.json`
- `frontend/next.config.ts`
- `frontend/tsconfig.json`
- `frontend/postcss.config.mjs` (v4: `@tailwindcss/postcss` 사용)
- `frontend/src/app/globals.css` (v4: `@import "tailwindcss"` + `@theme` 커스텀 토큰)
- `frontend/.eslintrc.json`

#### 구현 내용

```bash
pnpm create next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
cd frontend
pnpm add @tanstack/react-query@5 react-hook-form zod @hookform/resolvers
pnpm add lucide-react recharts
pnpm add -D @types/node
```

**Tailwind CSS v4 PostCSS 설정** (`postcss.config.mjs`):
```javascript
// v4: @tailwindcss/postcss 단일 플러그인 (postcss-import, autoprefixer 자동 처리)
export default {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
```

**CSS 파일** (`src/app/globals.css`):
```css
/* v4: @tailwind 디렉티브 대신 @import 사용 */
@import "tailwindcss";

/* v4: tailwind.config.ts 대신 @theme 디렉티브로 커스텀 토큰 정의 */
@theme {
  /* 필요 시 커스텀 색상, 폰트 등 추가 */
}
```

**shadcn/ui 초기화**:
```bash
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button card dialog form input select switch slider table tabs toast badge separator sheet
```

**next.config.ts**:
```typescript
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*` }];
  },
};

export default nextConfig;
```

#### 검증
```bash
pnpm lint && pnpm build
```

---

### Step 7.2: 레이아웃 컴포넌트

#### 생성 파일
- `frontend/src/components/layout/app-shell.tsx`
- `frontend/src/components/layout/sidebar.tsx`
- `frontend/src/components/layout/header.tsx`
- `frontend/src/app/layout.tsx`

#### 구현 내용

**app-shell.tsx**: 전체 레이아웃
- PC: 좌측 사이드바(240px) + 메인 콘텐츠
- 모바일: 상단 헤더 + 햄버거 메뉴 (Sheet 컴포넌트)

**sidebar.tsx**: 네비게이션
- 메뉴 항목: 대시보드, 문서관리, 검색테스트, 설정, 평가, 모니터링
- 현재 페이지 하이라이트
- 아이콘: Lucide React (FileText, Search, Settings, BarChart, Activity)

**header.tsx**: 상단 헤더
- 시스템 상태 표시 (연결 상태 뱃지)
- 모바일: 사이드바 토글 버튼

**layout.tsx**: Root Layout
- TanStack Query Provider 래핑
- 다크모드 미지원 (초기 버전)

#### 검증
```bash
pnpm lint && pnpm type-check && pnpm build
```

---

### Step 7.3: API 클라이언트 + TanStack Query

#### 생성 파일
- `frontend/src/lib/api.ts`
- `frontend/src/lib/utils.ts`
- `frontend/src/lib/queries.ts`
- `frontend/src/types/index.ts`

#### 구현 내용

**api.ts**: fetch 래퍼
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  documents: {
    list: (params?) => fetchJSON(`/api/documents`, { params }),
    upload: (file, metadata?) => fetchFormData(`/api/documents/upload`, file, metadata),
    get: (id) => fetchJSON(`/api/documents/${id}`),
    delete: (id) => fetchJSON(`/api/documents/${id}`, { method: "DELETE" }),
    reindex: (id) => fetchJSON(`/api/documents/${id}/reindex`, { method: "POST" }),
    chunks: (id) => fetchJSON(`/api/documents/${id}/chunks`),
  },
  search: {
    query: (params) => fetchJSON(`/api/search`, { method: "POST", body: params }),
    queryDebug: (params) => fetchJSON(`/api/search/debug`, { method: "POST", body: params }),
  },
  settings: {
    get: () => fetchJSON(`/api/settings`),
    update: (settings) => fetchJSON(`/api/settings`, { method: "PATCH", body: settings }),
    models: () => fetchJSON(`/api/settings/models`),
  },
  evaluation: {
    datasets: { list: () => ..., create: (data) => ..., get: (id) => ... },
    runs: { list: () => ..., get: (id) => ..., compare: (id1, id2) => ... },
    run: (datasetId) => fetchJSON(`/api/evaluation/run`, { method: "POST", body: { datasetId } }),
  },
  monitoring: {
    stats: () => fetchJSON(`/api/monitoring/stats`),
    traces: (params?) => fetchJSON(`/api/monitoring/traces`, { params }),
    costs: (params?) => fetchJSON(`/api/monitoring/costs`, { params }),
  },
  watcher: {
    status: () => fetchJSON(`/api/watcher/status`),
    start: () => fetchJSON(`/api/watcher/start`, { method: "POST" }),
    stop: () => fetchJSON(`/api/watcher/stop`, { method: "POST" }),
    scan: () => fetchJSON(`/api/watcher/scan`, { method: "POST" }),
    files: (params?) => fetchJSON(`/api/watcher/files`, { params }),
  },
  system: {
    health: () => fetchJSON(`/api/health`),
    status: () => fetchJSON(`/api/system/status`),
    reindexAll: () => fetchJSON(`/api/system/reindex-all`, { method: "POST" }),
  },
};
```

**queries.ts**: TanStack Query hooks
```typescript
export function useDocuments(params?) {
  return useQuery({ queryKey: ["documents", params], queryFn: () => api.documents.list(params) });
}
export function useSearch() {
  return useMutation({ mutationFn: (params) => api.search.queryDebug(params) });
}
// ...
```

**types/index.ts**: TypeScript 타입 정의
- Document (source: "upload" | "watcher" 필드 포함), Chunk, SearchRequest, SearchResponse, DebugSearchResponse
- RAGSettings, GuardrailSettings, WatcherSettings
- WatcherStatus, WatchedFile
- EvaluationDataset, EvaluationRun, EvaluationResult
- MonitoringStats, Trace

#### 검증
```bash
pnpm type-check
```

---

### Step 7.4: 대시보드 페이지

#### 생성 파일
- `frontend/src/app/page.tsx`

#### 구현 내용

대시보드 구성:
1. **시스템 상태 카드**: 총 문서 수, 총 청크 수, 오늘 쿼리 수 (useMonitoringStats)
2. **현재 활성 설정**: 임베딩 모델, 검색 모드, 리랭킹/HyDE/가드레일 ON/OFF (useSettings)
3. **RAGAS 점수 추이 차트**: Recharts BarChart (최근 5개 평가 실행)
4. **컴포넌트 연결 상태**: DB, ES, Ollama, Redis 연결 상태 뱃지

반응형:
- PC: 3열 카드 그리드
- 모바일: 1열 스택

---

### Step 7.5: 문서 관리 페이지

#### 생성 파일
- `frontend/src/app/documents/page.tsx`
- `frontend/src/app/documents/[id]/page.tsx`
- `frontend/src/components/documents/document-list.tsx`
- `frontend/src/components/documents/document-upload.tsx`
- `frontend/src/components/documents/chunk-viewer.tsx`
- `frontend/src/components/documents/indexing-status.tsx`

#### 구현 내용

**/documents**: 문서 목록
- 테이블: 파일명, 타입, 크기, 상태, 청크 수, 수집 소스(업로드/감시 뱃지), 생성일
- 정렬/필터/페이징 (source 필터: 전체/업로드/감시)
- 업로드 버튼 → 다이얼로그
- 삭제 버튼 (확인 다이얼로그)
- 재인덱싱 버튼

**document-upload.tsx**: 파일 업로드
- 드래그&드롭 영역
- 지원 형식 표시 (PDF, DOCX, TXT, MD)
- 업로드 진행률 표시

**/documents/[id]**: 문서 상세
- 메타데이터 (파일명, 타입, 크기, 상태)
- 청크 목록 (chunk-viewer)
- 인덱싱 상태 (indexing-status)

---

### Step 7.6: 검색 테스트 페이지

#### 생성 파일
- `frontend/src/app/search/page.tsx`
- `frontend/src/components/search/search-input.tsx`
- `frontend/src/components/search/search-results.tsx`
- `frontend/src/components/search/pipeline-trace.tsx`
- `frontend/src/components/search/answer-view.tsx`

#### 구현 내용

**/search**: 검색 테스트
- 쿼리 입력 + 검색 버튼
- 검색 옵션: 검색 모드, HyDE ON/OFF, 리랭킹 ON/OFF, top_k
- 디버그 모드 토글

**pipeline-trace.tsx**: 파이프라인 시각화
- 각 단계를 세로 타임라인으로 표시
- 단계별: 이름, 상태(통과/차단), 소요시간, 결과 수
- 접기/펼치기로 단계별 상세 확인

**answer-view.tsx**: 답변 표시
- 생성된 답변 (Markdown 렌더링)
- 참조 문서 목록 (점수, 문서명, 청크 내용 미리보기)

---

### Step 7.7: 설정 페이지

#### 생성 파일
- `frontend/src/app/settings/page.tsx`
- `frontend/src/app/settings/chunking/page.tsx`
- `frontend/src/app/settings/embedding/page.tsx`
- `frontend/src/app/settings/search/page.tsx`
- `frontend/src/app/settings/reranking/page.tsx`
- `frontend/src/app/settings/hyde/page.tsx`
- `frontend/src/app/settings/guardrails/page.tsx`
- `frontend/src/app/settings/generation/page.tsx`
- `frontend/src/app/settings/watcher/page.tsx`
- `frontend/src/components/settings/chunking-form.tsx`
- `frontend/src/components/settings/embedding-form.tsx`
- `frontend/src/components/settings/search-form.tsx`
- `frontend/src/components/settings/reranking-form.tsx`
- `frontend/src/components/settings/hyde-form.tsx`
- `frontend/src/components/settings/guardrails-form.tsx`
- `frontend/src/components/settings/generation-form.tsx`
- `frontend/src/components/settings/watcher-form.tsx`

#### 구현 내용

**/settings**: 설정 카테고리 목록 (Tabs 또는 서브 네비게이션)

각 설정 폼:
- **chunking-form**: 전략 선택(Select), chunk_size(Slider), chunk_overlap(Slider)
- **embedding-form**: 프로바이더 선택, 모델 선택
- **search-form**: 모드(hybrid/vector/keyword), 키워드 엔진, RRF k, 가중치 슬라이더
- **reranking-form**: ON/OFF(Switch), 모델, retriever_top_k, reranker_top_k
- **hyde-form**: ON/OFF(Switch), 모델, 적용 모드(all/long_query/complex)
- **guardrails-form**: 각 가드레일 ON/OFF(Switch), 액션 선택, 상세 설정
- **generation-form**: 프로바이더, 모델, system_prompt(Textarea), temperature, max_tokens
- **watcher-form**: ON/OFF(Switch), 감시 디렉토리 목록(동적 추가/삭제 가능한 Input 리스트), 감시 모드(이벤트/폴링 Select), 폴링 간격(Slider, 폴링 모드 시), 파일 삭제 시 자동 제거(Switch), 감시 상태 표시(running/stopped Badge), 시작/중지 버튼, 수동 스캔 버튼, 감시 파일 수 표시

공통:
- React Hook Form + Zod 검증
- PATCH /api/settings로 변경된 필드만 전송
- 저장 성공/실패 Toast 알림

---

### Step 7.8: 평가 페이지

#### 생성 파일
- `frontend/src/app/evaluation/page.tsx`
- `frontend/src/app/evaluation/datasets/page.tsx`
- `frontend/src/app/evaluation/runs/page.tsx`
- `frontend/src/app/evaluation/compare/page.tsx`

#### 구현 내용

**/evaluation/datasets**: 데이터셋 관리
- 목록 테이블 (이름, QA 쌍 수, 생성일)
- JSON 파일 업로드로 데이터셋 생성
- 데이터셋 상세: QA 쌍 목록

**/evaluation/runs**: 평가 실행
- 데이터셋 선택 → 평가 실행 버튼
- 실행 기록 테이블 (실행일, 데이터셋, 상태, 4개 메트릭 점수)
- 결과 상세: 질문별 점수 테이블

**/evaluation/compare**: 비교
- 두 실행 선택 → 메트릭 나란히 비교
- 차이점 하이라이트

---

### Step 7.9: 모니터링 페이지

#### 생성 파일
- `frontend/src/app/monitoring/page.tsx`
- `frontend/src/app/monitoring/traces/page.tsx`
- `frontend/src/app/monitoring/metrics/page.tsx`

#### 구현 내용

**/monitoring**: 모니터링 대시보드
- 통계 카드 (총 문서, 총 청크, 오늘 쿼리)
- 최근 트레이스 목록

**/monitoring/traces**: 트레이스 뷰
- 트레이스 목록 (시간, 쿼리, 총 소요시간, 상태)
- 트레이스 상세: span 타임라인 시각화

**/monitoring/metrics**: 시스템 메트릭
- 응답 시간 차트 (Recharts LineChart)
- 비용 차트
- 할루시네이션 점수 분포

---

### Step 7.10: Dockerfile

#### 생성 파일
- `frontend/Dockerfile`

#### 구현 내용

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV PORT=3000
EXPOSE 3000
CMD ["node", "server.js"]
```

## 생성 파일 전체 목록

| 카테고리 | 파일 수 | 주요 파일 |
|----------|---------|----------|
| 프로젝트 설정 | 5 | package.json, next.config.ts, postcss.config.mjs, globals.css(@theme) |
| 레이아웃 | 4 | app-shell, sidebar, header, layout.tsx |
| API/타입 | 4 | api.ts, queries.ts, utils.ts, types/index.ts |
| 대시보드 | 1 | app/page.tsx |
| 문서 관리 | 6 | documents 페이지 + 컴포넌트 4개 |
| 검색 테스트 | 5 | search 페이지 + 컴포넌트 4개 |
| 설정 | 17 | settings 페이지 8개 + 폼 컴포넌트 8개 + index |
| 평가 | 4 | evaluation 페이지 4개 |
| 모니터링 | 3 | monitoring 페이지 3개 |
| Docker | 1 | Dockerfile |

## 완료 조건 (자동 검증)

```bash
cd frontend && pnpm install && pnpm lint && pnpm type-check && pnpm build
```

E2E 테스트는 Phase 8에서 수행합니다.

## 인수인계 항목

Phase 8로 전달:
- 프론트엔드 URL: http://localhost:3000
- 페이지 구조 및 라우트 (E2E 테스트 시나리오 설계용)
- 검색 페이지 파이프라인 시각화 구조
- 설정 페이지 각 폼 요소 (셀렉터 참조)
