# 시스템 전체 아키텍처

## 시스템 구성도

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 / 관리자                                │
│              브라우저 (http://server:3500 dev / :3000 prod)           │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│  App Layer (docker-compose.yml)                                     │
│                                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │ Next.js      │  │ FastAPI Backend   │  │ Langfuse v3           │ │
│  │ Admin UI     │──│ (Haystack 기반)    │  │ ┌─────────────────┐  │ │
│  │ :3500 (dev)  │  │ :8000             │  │ │ Web    :3100    │  │ │
│  │ :3000 (prod) │  └───────┬──────────┘  │ │ Worker          │  │ │
│  └──────────────┘          │             │ │ ClickHouse      │  │ │
│                            │             │ │ Redis (전용)     │  │ │
│                     ┌──────┴──────┐      │ │ MinIO (S3)      │  │ │
│                     │ Redis       │      │ └─────────────────┘  │ │
│                     │ :6379       │      └───────────────────────┘ │
│                     │ (Celery)    │                                 │
│                     └─────────────┘                                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
              ┌──────────────────┼──────────────┐
              │                                 │
┌─────────────▼──────────┐      ┌───────────────▼──────────────┐
│ OpenAI API (Primary)   │      │ Infra Layer                  │
│                        │      │ (docker-compose.infra.yml)   │
│ - text-embedding-3     │      │                              │
│   -small (임베딩)       │      │ ┌────────────┐              │
│ - gpt-4.1-mini         │      │ │PostgreSQL  │              │
│   (HyDE, 답변 생성)     │      │ │+ PGVector  │              │
│ - gpt-4o               │      │ │:5432       │              │
│   (RAGAS 평가 Judge)    │      │ └────────────┘              │
│                        │      │ ┌────────────┐              │
└────────────────────────┘      │ │Elastic     │              │
                                │ │search+Nori │              │
┌────────────────────────┐      │ │:9200       │              │
│ 로컬 ML (HuggingFace)  │      │ └────────────┘              │
│                        │      └──────────────────────────────┘
│ - bge-reranker-v2      │
│   -m3-ko (리랭킹)      │
└────────────────────────┘
```

![대시보드](../images/r03.png)

## 기술 스택

### 인프라 계층 (공유, 독립 운영)
| 컴포넌트 | 기술 | 버전 | 역할 |
|----------|------|------|------|
| RDBMS + 벡터DB | PostgreSQL + PGVector | 17 | 문서 메타데이터, 벡터 임베딩 저장, Langfuse DB |
| 검색엔진 | Elasticsearch + Nori | 8.17 | 한국어 형태소 분석 기반 BM25 키워드 검색 |

### 애플리케이션 계층
| 컴포넌트 | 기술 | 포트 | 역할 |
|----------|------|------|------|
| 프론트엔드 | Next.js 15 + React 19 | :3500 (dev) / :3000 (prod) | 문서 관리, 설정, 모니터링 대시보드 |
| 백엔드 API | FastAPI (Python 3.12) | :8000 | REST API, RAG 파이프라인 오케스트레이션 |
| RAG 프레임워크 | Haystack 2.x | — | 파이프라인 조립, 컴포넌트 추상화 |
| 캐시/큐 | Redis 7 | :6379 | Celery 작업 큐 (재인덱싱 등) |
| 모니터링 | Langfuse v3 | :3100 | LLM 트레이싱, 비용 추적 |
| Langfuse 스토리지 | ClickHouse + 전용 Redis + MinIO | — | 이벤트 저장, 캐시, S3 호환 오브젝트 스토리지 |

### LLM / ML 모델 계층
| 용도 | 모델 | 실행 환경 |
|------|------|-----------|
| 임베딩 | text-embedding-3-small (1536차원) | OpenAI API |
| 리랭킹 | dragonkue/bge-reranker-v2-m3-ko | HuggingFace Transformers (로컬) |
| HyDE 생성 | gpt-4.1-mini | OpenAI API |
| 답변 생성 | gpt-4.1-mini | OpenAI API |
| RAGAS 평가 Judge | gpt-4o | OpenAI API |

## 데이터 흐름

### 인덱싱 흐름
```
문서 업로드 → 문서 타입 감지 → 청킹 전략 선택 → 청크 생성
    → 임베딩 생성 (text-embedding-3-small)
    → PGVector 저장 (벡터 + 메타데이터)
    → Elasticsearch 인덱싱 (텍스트 + Nori 역색인)
```

### 검색 흐름 (Phase 10-11 파이프라인)
```
사용자 쿼리
    → [가드레일] 프롬프트 인젝션 검사
    → [질문 유형 분류] extraction/regulatory/explanatory
    → [멀티쿼리] 구조분해 전략으로 변형 쿼리 생성 (ON일 때)
    → [HyDE] 가상 문서 생성 (ON일 때)
    → 벡터 검색 (PGVector) + 키워드 검색 (Elasticsearch)
    → RRF 결합
    → 문서 스코프 선택
    → 리랭킹 (bge-reranker-v2-m3-ko, sigmoid 캘리브레이션)
    → [검색 품질 게이트]
    → [가드레일] PII 탐지/마스킹
    → [근거 추출] 질문유형별 답변 생성 (CoT/단답추출/일반생성)
    → [숫자 검증] 정규식 기반 수치 검증
    → [가드레일] 할루시네이션 탐지
    → [가드레일] 충실도 검증
    → Langfuse 트레이스 기록
```

## 환경 구성

현재 시스템은 **OpenAI API 전용**으로 운영된다. 모든 LLM 및 임베딩 호출은 OpenAI API를 통해 처리되며, 리랭킹만 로컬 HuggingFace 모델을 사용한다.

| 구성 요소 | 실행 환경 | 비고 |
|-----------|-----------|------|
| 임베딩 (text-embedding-3-small) | OpenAI API | 1536차원, 한국어 성능 우수 |
| LLM (gpt-4.1-mini) | OpenAI API | HyDE 생성 + 답변 생성 겸용 |
| RAGAS Judge (gpt-4o) | OpenAI API | 평가 정확도를 위해 상위 모델 사용 |
| 리랭킹 (bge-reranker-v2-m3-ko) | HuggingFace Transformers (로컬) | AutoRAG 한국어 F1=0.9123 1위 |
| PostgreSQL + PGVector | Docker (infra) | 다른 프로젝트와 공유 |
| Elasticsearch + Nori | Docker (infra) | 다른 프로젝트와 공유 |
| Redis (Celery) | Docker (app) | 작업 큐 전용 |
| Langfuse v3 | Docker (app) | Web + Worker + ClickHouse + 전용 Redis + MinIO |
