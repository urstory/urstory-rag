# UrstoryRAG 아키텍처 문서

한국어 RAG 프로덕션 시스템의 구현 아키텍처 문서입니다.

## 문서 목록

| 문서 | 설명 |
|------|------|
| [01_system_overview.md](01_system_overview.md) | 시스템 전체 아키텍처, 컴포넌트 구성, 기술 스택 |
| [02_project_structure.md](02_project_structure.md) | 디렉토리 구조, 모듈 구성 |
| [03_infrastructure.md](03_infrastructure.md) | 공유 인프라 docker-compose (PostgreSQL + Elasticsearch) |
| [04_backend.md](04_backend.md) | Python 백엔드 아키텍처 (FastAPI + Haystack) |
| [05_frontend.md](05_frontend.md) | Next.js 관리자 UI 아키텍처 |
| [06_api_design.md](06_api_design.md) | REST API 설계 |
| [07_rag_pipeline.md](07_rag_pipeline.md) | RAG 파이프라인 상세 (청킹, 임베딩, 검색, 리랭킹, HyDE, 생성) |
| [08_guardrails.md](08_guardrails.md) | 한국어 가드레일 (PII, 프롬프트 인젝션, 할루시네이션) |
| [09_evaluation_monitoring.md](09_evaluation_monitoring.md) | RAGAS 평가 + Langfuse 모니터링 |
| [10_deployment.md](10_deployment.md) | 배포 및 운영 가이드 |

## 핵심 설계 원칙

1. **모든 기능 즉시 구현**: 리랭킹, HyDE, 가드레일, RAGAS 평가를 모두 포함. 관리자 UI에서 ON/OFF 제어
2. **인프라 분리**: PostgreSQL + Elasticsearch는 독립 docker-compose로 운영하여 다른 프로젝트와 공유
3. **LLM 프로바이더 추상화**: Mac Studio의 Ollama(기본) 또는 외부 API(OpenAI/Claude) 전환 가능
4. **한국어 최적화**: Nori 형태소 분석, bge-m3 임베딩, bge-reranker-v2-m3-ko 리랭킹
