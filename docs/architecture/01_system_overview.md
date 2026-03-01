# 시스템 전체 아키텍처

## 시스템 구성도

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 / 관리자                                │
│                    브라우저 (http://server:3000)                      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│  App Layer (docker-compose.yml)                                     │
│                                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ Next.js      │  │ FastAPI Backend   │  │ Langfuse v3          │  │
│  │ Admin UI     │──│ (Haystack 기반)    │  │ + ClickHouse         │  │
│  │ :3000        │  │ :8000             │  │ :3100                │  │
│  └──────────────┘  └───────┬──────────┘  └──────────────────────┘  │
│                            │                                        │
│                     ┌──────┴──────┐                                 │
│                     │   Redis     │                                 │
│                     │   :6379     │                                 │
│                     └─────────────┘                                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
┌─────────────▼──┐ ┌────────▼───────┐ ┌────▼─────────────────────┐
│ Ollama (호스트) │ │ Infra Layer    │ │ External APIs (선택)     │
│ Mac Studio     │ │ (docker-compose│ │ OpenAI / Claude          │
│ :11434         │ │  .infra.yml)   │ │                          │
│                │ │                │ │                          │
│ - bge-m3       │ │ ┌────────────┐ │ │ - text-embedding-3-large │
│ - qwen2.5:7b   │ │ │PostgreSQL  │ │ │ - gpt-4 (RAGAS 평가)     │
│ - bge-reranker │ │ │+ PGVector  │ │ │ - claude-sonnet          │
│                │ │ │:5432       │ │ │                          │
└────────────────┘ │ └────────────┘ │ └──────────────────────────┘
                   │ ┌────────────┐ │
                   │ │Elastic     │ │
                   │ │search+Nori │ │
                   │ │:9200       │ │
                   │ └────────────┘ │
                   └────────────────┘
```

## 기술 스택

### 인프라 계층 (공유, 독립 운영)
| 컴포넌트 | 기술 | 버전 | 역할 |
|----------|------|------|------|
| RDBMS + 벡터DB | PostgreSQL + PGVector | 17 | 문서 메타데이터, 벡터 임베딩 저장, Langfuse DB |
| 검색엔진 | Elasticsearch + Nori | 8.17 | 한국어 형태소 분석 기반 BM25 키워드 검색 |

### 애플리케이션 계층
| 컴포넌트 | 기술 | 역할 |
|----------|------|------|
| 백엔드 API | FastAPI (Python 3.12) | REST API, RAG 파이프라인 오케스트레이션 |
| RAG 프레임워크 | Haystack 2.x | 파이프라인 조립, 컴포넌트 추상화 |
| 관리자 UI | Next.js 15 + React 19 | 문서 관리, 설정, 모니터링 대시보드 |
| 캐시/큐 | Redis 7 | 쿼리 캐싱, 재인덱싱 작업 큐 |
| 모니터링 | Langfuse v3 + ClickHouse | LLM 트레이싱, 비용 추적 |

### LLM / ML 모델 계층
| 용도 | 모델 | 실행 환경 |
|------|------|-----------|
| 임베딩 | BAAI/bge-m3 (1024차원) | Ollama (Mac Studio) 또는 OpenAI API |
| 리랭킹 | dragonkue/bge-reranker-v2-m3-ko | Ollama 또는 HuggingFace Transformers |
| HyDE 생성 | Qwen2.5-7B | Ollama |
| 답변 생성 | Qwen2.5-7B / Claude / GPT-4 | Ollama 또는 외부 API |
| RAGAS 평가 | GPT-4 | OpenAI API |

## 데이터 흐름

### 인덱싱 흐름
```
문서 업로드 → 문서 타입 감지 → 청킹 전략 선택 → 청크 생성
    → 임베딩 생성 → PGVector 저장 (벡터 + 메타데이터)
    → Elasticsearch 인덱싱 (텍스트 + Nori 역색인)
```

### 검색 흐름
```
사용자 쿼리
    → [가드레일] 프롬프트 인젝션 검사
    → [HyDE] 가상 문서 생성 (ON일 때)
    → 쿼리 임베딩 생성
    → 벡터 검색 (PGVector) + 키워드 검색 (Elasticsearch)
    → RRF 결합
    → 리랭킹 (bge-reranker-v2-m3-ko)
    → [가드레일] PII 탐지
    → LLM 답변 생성
    → [가드레일] 할루시네이션 검증
    → 응답 반환
    → Langfuse 트레이스 기록
```

## 환경별 구성 차이

| 구성 요소 | Mac Studio (현재) | Linux GPU 서버 | API 전용 (저사양) |
|-----------|-------------------|---------------|------------------|
| Ollama | 호스트에서 직접 실행 | Docker 컨테이너 (GPU) | 사용 안 함 |
| 임베딩 | Ollama bge-m3 | Ollama bge-m3 | OpenAI API |
| 리랭킹 | HuggingFace local | HuggingFace local | Cohere API |
| LLM | Ollama Qwen2.5-7B | Ollama Qwen2.5-7B | Claude/GPT-4 API |
| 인프라 | Docker (PostgreSQL, ES) | Docker (전체) | Docker (전체) |
