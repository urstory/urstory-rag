# 롤백 가이드

배포 후 문제 발생 시 이전 버전으로 복구하는 절차입니다.

## 목차

- [앱 버전 롤백](#앱-버전-롤백)
- [DB 마이그레이션 롤백](#db-마이그레이션-롤백)
- [데이터 복구](#데이터-복구)
- [전체 복구 시나리오](#전체-복구-시나리오)

---

## 앱 버전 롤백

### Docker 이미지 기반 롤백

CI/CD가 GHCR에 커밋 SHA 태그로 이미지를 푸시하므로, 특정 버전으로 롤백할 수 있습니다.

```bash
# 1. 현재 배포된 이미지 확인
docker inspect rag-api --format='{{.Config.Image}}'

# 2. 이전 버전의 커밋 SHA 확인
git log --oneline -10

# 3. .env에서 TAG를 이전 버전으로 변경
TAG=이전커밋SHA

# 4. 이전 이미지로 재배포
docker compose -f docker-compose.prod.yml up -d
```

### Git 기반 롤백 (직접 빌드)

GHCR 이미지 대신 직접 빌드하는 경우:

```bash
# 1. 이전 커밋으로 체크아웃
git log --oneline -10
git checkout <이전_커밋_SHA>

# 2. 이미지 재빌드 및 배포
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 3. 확인 후 main 브랜치로 복귀
git checkout main
```

---

## DB 마이그레이션 롤백

### 한 단계 롤백

```bash
# 현재 마이그레이션 버전 확인
docker compose run --rm rag-api alembic current

# 한 단계 이전으로 다운그레이드
docker compose run --rm rag-api alembic downgrade -1

# 결과 확인
docker compose run --rm rag-api alembic current
```

### 특정 버전으로 롤백

```bash
# 마이그레이션 히스토리 확인
docker compose run --rm rag-api alembic history --verbose

# 특정 리비전으로 다운그레이드
docker compose run --rm rag-api alembic downgrade <리비전_ID>
```

### 주의사항

- `downgrade`가 가능하려면 마이그레이션 파일에 `downgrade()` 함수가 구현되어 있어야 합니다
- 데이터 삭제를 포함하는 다운그레이드는 **되돌릴 수 없습니다** (예: 컬럼 삭제 후 복구 불가)
- 마이그레이션 롤백 전 반드시 DB 백업을 수행하세요

---

## 데이터 복구

### PostgreSQL 백업

```bash
# 전체 데이터베이스 백업 (pg_dump)
docker exec shared-postgres pg_dump -U admin -d shared -F c -f /tmp/backup.dump
docker cp shared-postgres:/tmp/backup.dump ./backup_$(date +%Y%m%d_%H%M%S).dump

# SQL 텍스트 형식 백업
docker exec shared-postgres pg_dump -U admin -d shared > backup_$(date +%Y%m%d).sql
```

### PostgreSQL 복원

```bash
# 커스텀 형식 복원
docker cp backup.dump shared-postgres:/tmp/backup.dump
docker exec shared-postgres pg_restore -U admin -d shared --clean --if-exists /tmp/backup.dump

# SQL 텍스트 형식 복원
docker cp backup.sql shared-postgres:/tmp/backup.sql
docker exec shared-postgres psql -U admin -d shared -f /tmp/backup.sql
```

### 자동 백업 스케줄 (cron)

```bash
# crontab -e
# 매일 새벽 3시 백업, 7일 보관
0 3 * * * docker exec shared-postgres pg_dump -U admin -d shared -F c -f /tmp/backup.dump && docker cp shared-postgres:/tmp/backup.dump /backup/rag_$(date +\%Y\%m\%d).dump && find /backup -name "rag_*.dump" -mtime +7 -delete
```

### Elasticsearch 인덱스 복구

Elasticsearch 데이터가 손상되거나 유실된 경우, PostgreSQL에 원본 문서가 남아있으므로 재인덱싱으로 복구할 수 있습니다:

```bash
# 관리자 UI → 문서 관리 → 전체 재인덱싱
# 또는 API 호출
curl -X POST http://localhost:8000/api/admin/reindex \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Docker 볼륨 백업

```bash
# PostgreSQL 볼륨 전체 백업
docker run --rm -v infra_pg_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/pg_data_$(date +%Y%m%d).tar.gz -C /data .

# 복원
docker run --rm -v infra_pg_data:/data -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/pg_data_20240101.tar.gz"
```

---

## 전체 복구 시나리오

### 시나리오 1: 앱 업데이트 후 오류 (DB 변경 없음)

가장 흔한 경우입니다. 앱 코드만 변경되고 DB 스키마는 그대로일 때:

```bash
# 1. 이전 이미지로 롤백
TAG=이전커밋SHA docker compose -f docker-compose.prod.yml up -d

# 2. 헬스체크 확인
curl http://localhost:8000/api/health/ready
```

### 시나리오 2: 마이그레이션 포함 업데이트 후 오류

DB 스키마가 변경된 경우:

```bash
# 1. 앱 중지
docker compose -f docker-compose.prod.yml down

# 2. DB 마이그레이션 롤백
docker compose run --rm rag-api alembic downgrade -1

# 3. 이전 이미지로 재배포
TAG=이전커밋SHA docker compose -f docker-compose.prod.yml up -d

# 4. 확인
curl http://localhost:8000/api/health/ready
```

### 시나리오 3: 데이터 손상

PostgreSQL 데이터가 손상된 경우:

```bash
# 1. 앱 중지
docker compose -f docker-compose.prod.yml down

# 2. DB 백업에서 복원
docker cp backup.dump shared-postgres:/tmp/backup.dump
docker exec shared-postgres pg_restore -U admin -d shared --clean --if-exists /tmp/backup.dump

# 3. 마이그레이션 상태 확인 후 필요시 재실행
docker compose run --rm rag-api alembic current
docker compose run --rm rag-api alembic upgrade head

# 4. Elasticsearch 재인덱싱
# (관리자 UI 또는 API 호출)

# 5. 앱 재시작
docker compose -f docker-compose.prod.yml up -d
```

### 시나리오 4: 인프라 서버 교체

서버를 완전히 교체해야 하는 경우:

```bash
# === 기존 서버에서 ===
# 1. 앱 중지
docker compose -f docker-compose.prod.yml down
docker compose down  # Langfuse 사용 시

# 2. DB 백업
docker exec shared-postgres pg_dump -U admin -d shared -F c -f /tmp/backup.dump
docker cp shared-postgres:/tmp/backup.dump ./backup.dump

# 3. 환경변수 파일 백업
cp .env env_backup

# === 새 서버에서 ===
# 4. 코드 클론 및 환경변수 복원
git clone https://github.com/urstory/urstory-rag.git
cp env_backup .env

# 5. 인프라 시작
cd infra && docker compose up -d
# PostgreSQL, Elasticsearch, Redis 정상 기동 대기 (30초 정도)

# 6. DB 복원
docker cp backup.dump shared-postgres:/tmp/backup.dump
docker exec shared-postgres pg_restore -U admin -d shared -F c /tmp/backup.dump

# 7. 앱 배포
docker compose -f docker-compose.prod.yml up -d

# 8. 마이그레이션 확인
docker compose run --rm rag-api alembic current

# 9. Elasticsearch 재인덱싱 (관리자 UI에서 실행)

# 10. 헬스체크 확인
curl http://localhost:8000/api/health/ready
```
