# 프론트엔드 아키텍처

## 기술 스택

| 항목 | 기술 | 용도 |
|------|------|------|
| 프레임워크 | Next.js 15 (App Router) | SSR, 라우팅, API 프록시 |
| UI 라이브러리 | React 19 | 컴포넌트 기반 UI |
| 스타일링 | Tailwind CSS 4 | 유틸리티 기반 스타일링 |
| UI 컴포넌트 | shadcn/ui | 재사용 가능한 컴포넌트 |
| 상태 관리 | TanStack Query v5 | 서버 상태 관리, 캐싱 |
| 폼 관리 | React Hook Form + Zod | 폼 검증 |
| 아이콘 | Lucide React | 아이콘 |
| 차트 | Recharts | 모니터링 차트 |
| 패키지 매니저 | pnpm | 의존성 관리 |

## 페이지 구조

```
/                          → 대시보드 (시스템 상태, 주요 지표)
/documents                 → 문서 관리
  /documents/upload        → 문서 업로드
  /documents/[id]          → 문서 상세 (청크 목록, 메타데이터)
/search                    → 검색 테스트 (쿼리 입력, 결과 확인, 파이프라인 시각화)
/settings                  → 시스템 설정
  /settings/chunking       → 청킹 설정
  /settings/embedding      → 임베딩 모델 설정
  /settings/search         → 검색 엔진 설정
  /settings/reranking      → 리랭킹 설정
  /settings/hyde           → HyDE 설정
  /settings/guardrails     → 가드레일 설정
  /settings/generation     → 답변 생성 설정
  /settings/watcher        → 디렉토리 감시 설정
/evaluation                → RAGAS 평가
  /evaluation/datasets     → 평가 데이터셋 관리
  /evaluation/runs         → 평가 실행 기록
  /evaluation/compare      → 설정별 비교
/monitoring                → 모니터링
  /monitoring/traces       → Langfuse 트레이스 뷰
  /monitoring/metrics      → 시스템 메트릭
```

## 대시보드 구성

```
┌──────────────────────────────────────────────────────────┐
│  UrstoryRAG 관리자                     [시스템 상태: 정상]  │
├────────┬─────────────────────────────────────────────────┤
│        │                                                 │
│ 📄 문서  │  시스템 상태 카드                                 │
│ 🔍 검색  │  ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│ ⚙️ 설정  │  │총 문서    │ │총 청크    │ │오늘 쿼리  │          │
│ 📊 평가  │  │  1,234   │ │  8,456   │ │   127    │          │
│ 📈 모니터│  └─────────┘ └─────────┘ └─────────┘          │
│         │                                                │
│         │  현재 활성 설정                                  │
│         │  ┌──────────────────────────────────────────┐  │
│         │  │ 임베딩: bge-m3 (Ollama)                    │  │
│         │  │ 검색: 하이브리드 (PGVector + ES Nori)       │  │
│         │  │ 리랭킹: ON (bge-reranker-v2-m3-ko)        │  │
│         │  │ HyDE: ON (Qwen2.5-7B)                     │  │
│         │  │ 가드레일: PII ✓ 인젝션 ✓ 할루시네이션 ✓      │  │
│         │  └──────────────────────────────────────────┘  │
│         │                                                │
│         │  최근 RAGAS 점수 추이 (차트)                     │
│         │  ┌──────────────────────────────────────────┐  │
│         │  │  Faithfulness  ████████░░  0.82           │  │
│         │  │  Relevancy     ███████░░░  0.76           │  │
│         │  │  Precision     █████████░  0.89           │  │
│         │  │  Recall        ████████░░  0.81           │  │
│         │  └──────────────────────────────────────────┘  │
│         │                                                │
└─────────┴────────────────────────────────────────────────┘
```

## 검색 테스트 페이지

관리자가 쿼리를 입력하고 전체 파이프라인의 결과를 단계별로 확인할 수 있습니다.

```
┌──────────────────────────────────────────────────────┐
│  검색 테스트                                          │
│                                                      │
│  쿼리: [연차 신청 절차가 어떻게 되나요?        ] [검색]  │
│                                                      │
│  ┌─ 파이프라인 실행 결과 ──────────────────────────┐  │
│  │                                                 │  │
│  │  1. 가드레일 (입력) ✅ 통과 (12ms)               │  │
│  │  2. HyDE 가상 문서 생성 (450ms)                  │  │
│  │     "연차 신청은 사내 포털에서..."                  │  │
│  │  3. 벡터 검색: 20건 (85ms)                       │  │
│  │  4. 키워드 검색 (Nori): 18건 (32ms)              │  │
│  │  5. RRF 결합: 28건 → 20건                        │  │
│  │  6. 리랭킹: 20건 → 5건 (230ms)                   │  │
│  │  7. 가드레일 (PII) ✅ 통과                        │  │
│  │  8. 답변 생성 (1200ms)                           │  │
│  │  9. 가드레일 (할루시네이션) ✅ 통과                 │  │
│  │                                                 │  │
│  │  총 소요시간: 2.1s                               │  │
│  └─────────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ 최종 답변 ─────────────────────────────────────┐  │
│  │  연차 신청은 다음 절차로 진행됩니다...              │  │
│  └─────────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ 참조 문서 (5건) ───────────────────────────────┐  │
│  │  1. 회사규정.txt (점수: 0.94) [청크 보기]          │  │
│  │  2. HR_매뉴얼.pdf (점수: 0.87) [청크 보기]        │  │
│  │  ...                                            │  │
│  └─────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## API 클라이언트

```typescript
// frontend/src/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  // 문서
  documents: {
    list: (params?: DocumentListParams) =>
      fetch(`${API_BASE}/api/documents`, { params }),
    upload: (file: File, metadata?: Record<string, string>) =>
      fetch(`${API_BASE}/api/documents/upload`, { method: "POST", body: formData }),
    get: (id: string) =>
      fetch(`${API_BASE}/api/documents/${id}`),
    delete: (id: string) =>
      fetch(`${API_BASE}/api/documents/${id}`, { method: "DELETE" }),
    reindex: (id: string) =>
      fetch(`${API_BASE}/api/documents/${id}/reindex`, { method: "POST" }),
  },

  // 검색
  search: {
    query: (params: SearchParams) =>
      fetch(`${API_BASE}/api/search`, { method: "POST", body: params }),
    queryDebug: (params: SearchParams) =>
      fetch(`${API_BASE}/api/search/debug`, { method: "POST", body: params }),
  },

  // 설정
  settings: {
    get: () => fetch(`${API_BASE}/api/settings`),
    update: (settings: Partial<RAGSettings>) =>
      fetch(`${API_BASE}/api/settings`, { method: "PATCH", body: settings }),
  },

  // 평가
  evaluation: {
    runRagas: (datasetId: string) =>
      fetch(`${API_BASE}/api/evaluation/run`, { method: "POST", body: { datasetId } }),
    getResults: (runId: string) =>
      fetch(`${API_BASE}/api/evaluation/runs/${runId}`),
    listRuns: () =>
      fetch(`${API_BASE}/api/evaluation/runs`),
  },

  // 디렉토리 감시
  watcher: {
    status: () => fetch(`${API_BASE}/api/watcher/status`),
    start: () => fetch(`${API_BASE}/api/watcher/start`, { method: "POST" }),
    stop: () => fetch(`${API_BASE}/api/watcher/stop`, { method: "POST" }),
    scan: () => fetch(`${API_BASE}/api/watcher/scan`, { method: "POST" }),
    files: (params?: PaginationParams) =>
      fetch(`${API_BASE}/api/watcher/files`, { params }),
  },

  // 시스템
  system: {
    health: () => fetch(`${API_BASE}/api/health`),
    status: () => fetch(`${API_BASE}/api/system/status`),
    reindexAll: () =>
      fetch(`${API_BASE}/api/system/reindex-all`, { method: "POST" }),
  },
};
```

## 컴포넌트 구조

```
components/
├── ui/                    # shadcn/ui 기반 공통 컴포넌트
│   ├── button.tsx
│   ├── card.tsx
│   ├── dialog.tsx
│   ├── form.tsx
│   ├── input.tsx
│   ├── select.tsx
│   ├── switch.tsx         # ON/OFF 토글 (가드레일, HyDE 등)
│   ├── slider.tsx         # 수치 조절 (chunk_size, top_k 등)
│   ├── table.tsx
│   └── tabs.tsx
│
├── layout/
│   ├── sidebar.tsx        # 좌측 네비게이션
│   ├── header.tsx         # 상단 헤더 (시스템 상태 표시)
│   └── app-shell.tsx      # 전체 레이아웃
│
├── documents/
│   ├── document-list.tsx  # 문서 목록 테이블 (수집 소스 뱃지: 업로드/감시)
│   ├── document-upload.tsx # 파일 업로드 (드래그&드롭)
│   ├── chunk-viewer.tsx   # 청크 내용 보기
│   └── indexing-status.tsx # 인덱싱 진행 상태
│
├── search/
│   ├── search-input.tsx   # 검색 입력
│   ├── search-results.tsx # 검색 결과 목록
│   ├── pipeline-trace.tsx # 파이프라인 단계별 결과
│   └── answer-view.tsx    # 생성된 답변 표시
│
└── settings/
    ├── chunking-form.tsx  # 청킹 설정 폼
    ├── embedding-form.tsx # 임베딩 설정 폼
    ├── search-form.tsx    # 검색 설정 폼
    ├── reranking-form.tsx # 리랭킹 설정 폼
    ├── hyde-form.tsx      # HyDE 설정 폼
    ├── guardrails-form.tsx # 가드레일 설정 폼
    ├── generation-form.tsx # 답변 생성 설정 폼
    └── watcher-form.tsx   # 디렉토리 감시 설정 폼
```

## 빌드 및 배포

```dockerfile
# frontend/Dockerfile
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
