# UrstoryRAG 관리자 UI

한국어 RAG 시스템의 관리자 웹 인터페이스. 문서 관리, 검색 테스트, 시스템 설정, RAG 품질 평가를 통합 제공합니다.

## 기술 스택

- **Next.js 16**: 풀스택 프레임워크, App Router, SSR 지원
- **React 19**: UI 컴포넌트 및 상태 관리
- **Tailwind CSS 4**: 유틸리티 기반 스타일링
- **shadcn/ui**: 접근성 좋은 컴포넌트 라이브러리
- **TanStack React Query 5**: 백엔드 API 데이터 페칭 및 캐싱
- **React Hook Form**: 폼 상태 관리 및 검증 (Zod)
- **Recharts**: 차트 및 데이터 시각화
- **Lucide React**: 아이콘 라이브러리
- **next-themes**: 다크모드 지원

## 주요 화면

### 문서 관리 (`/documents`)
- 업로드된 문서 목록 조회
- 문서 상세 정보 및 임베딩 상태 확인
- 문서 삭제 및 일괄 관리
- 재인덱싱 작업 실행

### 검색 테스트 (`/search`)
- 쿼리 입력 후 RAG 응답 즉시 테스트
- 검색된 참조 문서 확인
- 생성된 답변과 메타데이터 조회
- 검색 성능 및 응답 시간 모니터링

### 시스템 설정 (`/settings`)
- **기본 설정**: 임베딩, 청킹, 검색 파라미터
- **리랭킹**: 드래곤크로 한국어 리랭커 설정
- **HyDE**: Hypothetical Document Embedding 활성화/비활성화
- **생성**: LLM 모델, 온도, 토큰 제한 설정
- **가드레일**: 입력/출력 검증 규칙 설정
- **Watcher**: 시스템 감시 및 알림 설정

### 품질 평가 대시보드 (`/evaluation`)
- **평가 실행**: RAGAS 메트릭 자동 평가 (Faithfulness, Answer Relevancy, Context Precision 등)
- **평가 결과**: 라운드별 상세 성적 및 메트릭 분석
- **평가 데이터셋**: Q&A 질문 관리 및 참조 답변 설정
- **비교 분석**: 여러 평가 라운드 간 성능 비교

### 모니터링 (`/monitoring`)
- **메트릭**: 시스템 성능 지표 (응답시간, 성공률, 캐시 히트율)
- **추적(Traces)**: Langfuse 통합으로 각 RAG 파이프라인 호출 추적
- 토큰 사용량, API 비용 모니터링

## 개발 환경 설정

### 필수 요구사항
- Node.js 20+
- pnpm 10.30+

### 설치

```bash
cd frontend
pnpm install
```

### 개발 서버 실행

```bash
pnpm run dev
```

개발 서버는 http://localhost:3500 에서 실행됩니다.

### 환경 변수 설정

프로젝트 루트에 `.env.local` 파일 생성:

```env
# 백엔드 API 주소
NEXT_PUBLIC_API_URL=http://localhost:8000

# OpenAI API 키 (선택사항: 프론트에서 직접 사용하는 경우)
NEXT_PUBLIC_OPENAI_API_KEY=sk-...

# Langfuse (모니터링)
NEXT_PUBLIC_LANGFUSE_PUBLIC_KEY=pk-...

# 기타 설정
NEXT_PUBLIC_APP_ENV=development
```

## 빌드 및 배포

### 프로덕션 빌드

```bash
pnpm run build
```

빌드 결과는 `.next` 디렉터리에 생성됩니다.

### 프로덕션 서버 실행

```bash
pnpm run start
```

프로덕션 서버는 http://localhost:3000 에서 실행됩니다.

## 프로젝트 구조

```
src/
├── app/                    # Next.js App Router
│   ├── documents/         # 문서 관리 페이지
│   ├── search/            # 검색 테스트 페이지
│   ├── settings/          # 시스템 설정 (임베딩, 리랭킹, HyDE, 생성, 가드레일, Watcher)
│   ├── evaluation/        # 품질 평가 대시보드
│   ├── monitoring/        # 모니터링 및 추적
│   └── layout.tsx         # 루트 레이아웃 및 네비게이션
├── components/            # 재사용 가능한 UI 컴포넌트
├── lib/                   # 유틸리티 함수 및 API 클라이언트
├── types/                 # TypeScript 타입 정의
└── hooks/                 # 커스텀 React Hooks
```

## 지원 브라우저

- Chrome/Edge (최신)
- Firefox (최신)
- Safari (최신)
- 모바일: iOS Safari, Android Chrome

태블릿은 별도 최적화 대상이 아닙니다.

## API 통신

모든 백엔드 통신은 TanStack React Query를 통해 관리됩니다:

- 자동 캐싱 및 재검증
- 에러 처리 및 재시도
- 로딩 상태 관리
- 낙관적 업데이트 (Optimistic Updates) 지원

## 개발 가이드

### 컴포넌트 추가

shadcn/ui 컴포넌트 추가:

```bash
npx shadcn-ui@latest add [component-name]
```

### ESLint 실행

```bash
pnpm run lint
```

### 타입 확인

```bash
pnpm tsc --noEmit
```

## 데이터 흐름

1. 사용자가 UI에서 작업 수행
2. React Hook Form으로 입력값 검증
3. React Query로 백엔드 API 호출
4. 응답 데이터는 React Query 캐시에 저장
5. UI 자동 업데이트 및 토스트 알림

## 주의사항

- 프론트엔드는 백엔드 API (`http://localhost:8000`)에 의존합니다. 백엔드가 실행 중이어야 합니다.
- 환경 변수 `NEXT_PUBLIC_*`는 클라이언트 번들에 포함되므로 민감 정보는 포함하지 마세요.
- Langfuse 추적이 필요한 경우 별도의 `NEXT_PUBLIC_LANGFUSE_PUBLIC_KEY` 설정이 필요합니다.
