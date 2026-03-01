# 인프라 계층

공유 인프라는 `infra/` 디렉토리에서 독립적으로 관리합니다. 다른 프로젝트에서도 동일한 PostgreSQL과 Elasticsearch를 사용할 수 있습니다.

## docker-compose.yml (infra)

```yaml
# infra/docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg17
    container_name: shared-postgres
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-admin}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-shared}
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-admin}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  elasticsearch:
    build:
      context: .
      dockerfile: Dockerfile.elasticsearch
    container_name: shared-elasticsearch
    ports:
      - "${ES_PORT:-9200}:9200"
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped

volumes:
  pg_data:
  es_data:

networks:
  default:
    name: shared-infra
```

## Dockerfile.elasticsearch

```dockerfile
# infra/Dockerfile.elasticsearch
FROM docker.elastic.co/elasticsearch/elasticsearch:8.17.0
RUN bin/elasticsearch-plugin install --batch analysis-nori
```

## init-db.sql

```sql
-- infra/init-db.sql
CREATE EXTENSION IF NOT EXISTS vector;

-- RAG 시스템용 스키마
CREATE SCHEMA IF NOT EXISTS rag;

-- Langfuse용 스키마
CREATE SCHEMA IF NOT EXISTS langfuse;

-- 다른 프로젝트용 스키마 추가 가능
-- CREATE SCHEMA IF NOT EXISTS other_project;
```

## Elasticsearch Nori 인덱스 템플릿

인프라 기동 후 한 번 실행하여 한국어 분석기가 적용된 인덱스 템플릿을 생성합니다.

```json
// infra/elasticsearch/nori-index-template.json
{
  "index_patterns": ["rag_*"],
  "settings": {
    "analysis": {
      "tokenizer": {
        "nori_mixed": {
          "type": "nori_tokenizer",
          "decompound_mode": "mixed"
        }
      },
      "analyzer": {
        "korean": {
          "type": "custom",
          "tokenizer": "nori_mixed",
          "filter": ["nori_readingform", "lowercase", "nori_part_of_speech"]
        }
      },
      "filter": {
        "nori_part_of_speech": {
          "type": "nori_part_of_speech",
          "stoptags": ["E", "J", "SC", "SE", "SF", "SP", "SSC", "SSO", "SY", "VCN", "VCP", "VSV", "VX", "XPN", "XSA", "XSN", "XSV"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "content": {
        "type": "text",
        "analyzer": "korean"
      },
      "meta": {
        "type": "object",
        "enabled": true
      }
    }
  }
}
```

## 환경 변수

```bash
# infra/.env.example
POSTGRES_USER=admin
POSTGRES_PASSWORD=changeme_strong_password
POSTGRES_DB=shared
POSTGRES_PORT=5432
ES_PORT=9200
```

## 운영 커맨드

```bash
# 인프라 시작
cd infra && docker compose up -d

# 상태 확인
docker compose ps
curl http://localhost:9200/_cluster/health?pretty
docker exec shared-postgres pg_isready -U admin

# Nori 인덱스 템플릿 적용 (최초 1회)
curl -X PUT "http://localhost:9200/_index_template/rag_template" \
  -H "Content-Type: application/json" \
  -d @elasticsearch/nori-index-template.json

# 인프라 중지 (데이터 유지)
docker compose down

# 인프라 완전 초기화 (데이터 삭제)
docker compose down -v
```

## 네트워크

`shared-infra` 네트워크를 사용합니다. 이 네트워크는 docker-compose에서 자동 생성되며, 앱 계층의 docker-compose에서도 동일한 네트워크에 접속합니다.

Mac (Docker Desktop) 환경에서는 `host.docker.internal`로도 접근 가능하지만, 네트워크 공유 방식이 환경 독립적이므로 `shared-infra` 네트워크 방식을 기본으로 사용합니다.

## 다른 프로젝트에서 사용

다른 프로젝트의 docker-compose에서 같은 네트워크에 참여하면 됩니다:

```yaml
# 다른 프로젝트의 docker-compose.yml
services:
  my-app:
    # ...
    environment:
      DATABASE_URL: postgresql://admin:password@shared-postgres:5432/shared
    networks:
      - shared-infra

networks:
  shared-infra:
    external: true
```

또는 호스트 포트를 통해 접근할 수도 있습니다:
```
postgresql://admin:password@localhost:5432/shared
http://localhost:9200
```
