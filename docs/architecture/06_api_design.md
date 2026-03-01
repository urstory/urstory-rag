# REST API 설계

## 기본 정보

- Base URL: `http://localhost:8000/api`
- 인증: 초기 버전은 API Key 기반 (헤더: `X-API-Key`)
- 응답 형식: JSON
- 에러 형식: `{"error": "ERROR_CODE", "message": "상세 메시지"}`

## 엔드포인트

### 시스템

```
GET  /api/health                    # 헬스체크
GET  /api/system/status             # 시스템 상태 (DB, ES, Ollama 연결, 모델 로드 상태)
POST /api/system/reindex-all        # 전체 재인덱싱 (비동기)
GET  /api/system/tasks/{task_id}    # 비동기 작업 상태 확인
```

### 문서 관리

```
GET    /api/documents                       # 문서 목록 (페이징, 필터, source별)
POST   /api/documents/upload                # 문서 업로드 (multipart/form-data)
GET    /api/documents/{id}                  # 문서 상세
DELETE /api/documents/{id}                  # 문서 삭제 (양쪽 인덱스에서 제거)
POST   /api/documents/{id}/reindex          # 단일 문서 재인덱싱
GET    /api/documents/{id}/chunks           # 문서의 청크 목록
```

### 디렉토리 감시 (Watcher)

```
GET  /api/watcher/status                    # 감시 상태 (running/stopped, 감시 디렉토리, 최근 이벤트)
POST /api/watcher/start                     # 감시 시작
POST /api/watcher/stop                      # 감시 중지
POST /api/watcher/scan                      # 수동 전체 스캔 (비동기)
GET  /api/watcher/files                     # 감시 중인 파일 목록 (페이징)
```

#### 감시 상태 응답

```json
{
  "status": "running",
  "directories": ["/data/documents", "/data/reports"],
  "mode": "event",
  "watched_file_count": 234,
  "last_event": {
    "type": "created",
    "path": "/data/documents/새규정.pdf",
    "timestamp": "2026-03-01T14:30:00Z"
  },
  "stats": {
    "total_synced": 230,
    "pending": 4,
    "failed": 0
  }
}
```

### 검색

```
POST /api/search                    # 검색 (답변 생성 포함)
POST /api/search/debug              # 검색 디버그 (파이프라인 단계별 결과)
```

#### 검색 요청

```json
{
  "query": "연차 신청 절차가 어떻게 되나요?",
  "top_k": 5,
  "search_mode": "hybrid",
  "use_hyde": true,
  "use_reranking": true,
  "generate_answer": true
}
```

#### 검색 응답

```json
{
  "answer": "연차 신청은 다음 절차로 진행됩니다...",
  "documents": [
    {
      "id": "chunk_001",
      "content": "연차 신청은 사내 포털...",
      "score": 0.94,
      "meta": {
        "doc_id": "doc_001",
        "doc_name": "회사규정.txt",
        "chunk_index": 3
      }
    }
  ],
  "trace_id": "langfuse-trace-xxx"
}
```

#### 디버그 검색 응답

```json
{
  "answer": "...",
  "documents": [...],
  "pipeline_trace": {
    "guardrail_input": {
      "passed": true,
      "duration_ms": 12
    },
    "hyde": {
      "enabled": true,
      "generated_document": "연차 신청은 사내 포털에서...",
      "duration_ms": 450
    },
    "vector_search": {
      "results_count": 20,
      "duration_ms": 85
    },
    "keyword_search": {
      "results_count": 18,
      "duration_ms": 32
    },
    "rrf_fusion": {
      "input_count": 28,
      "output_count": 20
    },
    "reranking": {
      "input_count": 20,
      "output_count": 5,
      "duration_ms": 230
    },
    "guardrail_pii": {
      "passed": true,
      "duration_ms": 5
    },
    "generation": {
      "model": "qwen2.5:7b",
      "duration_ms": 1200,
      "tokens": { "prompt": 1024, "completion": 256 }
    },
    "guardrail_hallucination": {
      "passed": true,
      "confidence": 0.92,
      "duration_ms": 800
    },
    "total_duration_ms": 2100
  },
  "trace_id": "langfuse-trace-xxx"
}
```

### 설정

```
GET   /api/settings                 # 현재 설정 조회
PATCH /api/settings                 # 설정 업데이트 (부분 업데이트)
GET   /api/settings/models          # 사용 가능한 모델 목록 (Ollama 모델 + API 모델)
```

#### 설정 스키마

```json
{
  "chunking": {
    "strategy": "recursive",
    "chunk_size": 512,
    "chunk_overlap": 50
  },
  "embedding": {
    "provider": "ollama",
    "model": "bge-m3"
  },
  "search": {
    "mode": "hybrid",
    "keyword_engine": "elasticsearch",
    "rrf_constant": 60,
    "vector_weight": 0.5,
    "keyword_weight": 0.5
  },
  "reranking": {
    "enabled": true,
    "model": "dragonkue/bge-reranker-v2-m3-ko",
    "top_k": 5,
    "retriever_top_k": 20
  },
  "hyde": {
    "enabled": true,
    "model": "qwen2.5:7b",
    "apply_mode": "all"
  },
  "guardrails": {
    "pii_detection": true,
    "injection_detection": true,
    "hallucination_detection": true
  },
  "generation": {
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "system_prompt": "당신은 사내 문서를 기반으로 질문에 답변하는 AI 어시스턴트입니다.",
    "temperature": 0.1,
    "max_tokens": 1024
  },
  "watcher": {
    "enabled": false,
    "directories": [],
    "use_polling": false,
    "polling_interval": 60,
    "auto_delete": false,
    "file_patterns": ["*.pdf", "*.docx", "*.txt", "*.md"]
  }
}
```

### RAGAS 평가

```
GET  /api/evaluation/datasets                   # 평가 데이터셋 목록
POST /api/evaluation/datasets                   # 데이터셋 생성 (QA 쌍 업로드)
GET  /api/evaluation/datasets/{id}              # 데이터셋 상세
POST /api/evaluation/run                        # 평가 실행 (비동기)
GET  /api/evaluation/runs                       # 평가 실행 기록
GET  /api/evaluation/runs/{id}                  # 평가 결과 상세
GET  /api/evaluation/runs/{id1}/compare/{id2}   # 두 실행 결과 비교
```

#### 평가 결과

```json
{
  "id": "run_001",
  "dataset_id": "ds_001",
  "status": "completed",
  "settings_snapshot": { "..." },
  "metrics": {
    "faithfulness": 0.82,
    "answer_relevancy": 0.76,
    "context_precision": 0.89,
    "context_recall": 0.81
  },
  "per_question_results": [
    {
      "question": "연차 신청 절차가 어떻게 되나요?",
      "ground_truth": "...",
      "answer": "...",
      "faithfulness": 0.9,
      "answer_relevancy": 0.85,
      "context_precision": 0.95,
      "context_recall": 0.88
    }
  ],
  "created_at": "2026-03-01T12:00:00Z"
}
```

### 모니터링

```
GET /api/monitoring/stats               # 집계 통계 (총 문서, 총 청크, 오늘 쿼리 수)
GET /api/monitoring/traces              # Langfuse 트레이스 목록 (프록시)
GET /api/monitoring/traces/{id}         # 트레이스 상세
GET /api/monitoring/costs               # 비용 추적 (기간별)
```

## 공통 패턴

### 페이징

```
GET /api/documents?page=1&size=20&sort=created_at&order=desc&source=all
```

`source` 필터: `all`(기본), `upload`, `watcher`

```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "size": 20,
  "pages": 8
}
```

### 비동기 작업

시간이 오래 걸리는 작업 (인덱싱, 재인덱싱, RAGAS 평가)은 비동기로 처리합니다.

```json
// POST 응답
{
  "task_id": "task_xxx",
  "status": "pending"
}

// GET /api/system/tasks/{task_id}
{
  "task_id": "task_xxx",
  "status": "running",      // pending | running | completed | failed
  "progress": 45,           // 0-100
  "result": null,
  "error": null,
  "created_at": "...",
  "updated_at": "..."
}
```
