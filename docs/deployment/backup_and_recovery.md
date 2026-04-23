# 백업 및 복구 전략

본 문서는 UrstoryRAG의 **PostgreSQL + PGVector** 및 **Elasticsearch (Nori)**
데이터 스토어에 대한 백업/복구 절차, 보관 정책, RTO/RPO 목표를 정의한다.

## 복구 목표

| 지표 | 목표 | 비고 |
|------|------|------|
| **RTO** (Recovery Time Objective) | **1시간 이내** | 단일 호스트 장애, 자동화된 복구 스크립트 기준 |
| **RPO** (Recovery Point Objective) | **1시간 이내** | 일일 스냅샷 + WAL 아카이빙 병행 시 |
| 스냅샷 주기 | 1일 (권장) / 1시간 (WAL) | 운영 환경에서는 `cron`으로 자동화 |
| 복원 검증 주기 | **월 1회** | `scripts/test-restore.sh` 정기 실행 |

## 보관 정책

| 계층 | 보관 기간 | 위치 |
|------|-----------|------|
| 일일 백업 | 7일 | `backups/postgres/YYYYMMDD/` |
| 주간 백업 (일요일) | 30일 | 일일 폴더 내에 보존 (자동 제외) |
| 오프사이트 (운영) | 90일 | S3 또는 NAS로 주기적 동기화 (별도 운영 작업) |

보관 기간은 환경변수로 조정할 수 있다.

```bash
BACKUP_DAILY_RETENTION=7
BACKUP_WEEKLY_RETENTION=30
```

## 전체 백업 실행

```bash
# 기본: PostgreSQL + Elasticsearch 모두 백업
./scripts/backup.sh

# PostgreSQL만
./scripts/backup.sh --postgres-only

# Elasticsearch만
./scripts/backup.sh --elasticsearch-only

# 백업 디렉토리 지정
BACKUP_DIR=/mnt/backup ./scripts/backup.sh
```

cron 예시:

```cron
# 매일 03:00 UTC 전체 백업
0 3 * * * /opt/urstory-rag/scripts/backup.sh >> /var/log/urstory_backup.log 2>&1

# 매달 1일 04:00 UTC 복원 검증
0 4 1 * * /opt/urstory-rag/scripts/test-restore.sh >> /var/log/urstory_restore_test.log 2>&1
```

## PostgreSQL 백업 상세

- 사용 도구: `pg_dump --format=plain | gzip`
- 대상 DB: `shared` (UrstoryRAG 본체), `langfuse` (모니터링)
- 저장 경로: `backups/postgres/YYYYMMDD/{db}_YYYYMMDD_HHMMSS.sql.gz`
- 무료 복구: `pg_restore` 또는 `psql -f` 로 임의 시점 복원

### WAL 아카이빙 (Point-in-Time Recovery)

운영 환경에서 RPO를 더 줄이려면 WAL 아카이빙을 활성화한다.

1. `postgresql.conf`:
    ```
    wal_level = replica
    archive_mode = on
    archive_command = 'gzip < %p > /var/lib/postgresql/wal_archive/%f.gz'
    archive_timeout = 300
    ```
2. `wal_archive` 디렉토리를 별도 볼륨/원격 스토리지로 미러링
3. 복원 시 `restore_command`를 사용하여 `pg_dump` 기반 풀 스냅샷 + WAL 롤포워드 수행

> UrstoryRAG 저장소는 단일 호스트 단순 배포를 기본으로 한다. 멀티 노드/HA가
> 필요한 경우 `pg_basebackup` + 복제 설정을 별도로 구성해야 한다.

## Elasticsearch 백업 상세

- 사용 도구: `_snapshot` API (fs repository 타입)
- 저장 경로: 컨테이너 내부 `/usr/share/elasticsearch/snapshots`
- 호스트에서는 Docker 볼륨 `es_snapshots`에 마운트된다
- `path.repo`가 `elasticsearch.yml` 또는 환경변수에 등록되어야 한다
  (`infra/docker-compose.yml`에 이미 설정됨)

스냅샷 리포지토리가 등록되지 않았다면 `backup.sh`가 자동으로 등록한다.

### 스냅샷 수동 확인

```bash
# 등록된 리포지토리 확인
curl -s http://localhost:9200/_snapshot/_all | jq .

# 스냅샷 목록
curl -s http://localhost:9200/_snapshot/urstory_rag_snapshots/_all | jq '.snapshots[].snapshot'

# 특정 스냅샷 상태
curl -s http://localhost:9200/_snapshot/urstory_rag_snapshots/snapshot_20260424_030000 | jq .
```

## 복원 절차

### 가용한 백업 목록 확인

```bash
./scripts/restore.sh --list
```

### PostgreSQL 복원

```bash
./scripts/restore.sh --postgres backups/postgres/20260424/shared_20260424_030000.sql.gz \
                     --database shared
```

주의:

- 스크립트는 **대상 데이터베이스를 DROP하고 재생성**한다.
- 실행 전 `RESTORE` 문자열 입력을 요구하여 실수를 방지한다.
- 운영 중인 앱이 있다면 **먼저 백엔드/워커 컨테이너를 중지**한 뒤 수행한다.

```bash
# 운영 중단이 필요하면
docker compose -f docker-compose.prod.yml stop backend worker
./scripts/restore.sh --postgres ...
docker compose -f docker-compose.prod.yml start backend worker
```

### Elasticsearch 복원

```bash
./scripts/restore.sh --elasticsearch snapshot_20260424_030000
```

주의:

- 스크립트는 복원 전 **모든 인덱스를 close한다**. 복원 완료 후 `open`을 자동 수행한다.
- 복원 중에는 Elasticsearch 기반 검색 API가 일시적으로 실패할 수 있다.

## 복원 검증 (월 1회)

`scripts/test-restore.sh`는 최신 PostgreSQL 덤프를
일회용 데이터베이스 `restore_test_<unix_ts>`에 복원하여 다음을 검증한다.

- 덤프 파일이 정상적으로 압축 해제되고 SQL이 오류 없이 적용되는지
- `documents`, `users` 등 기대 테이블이 존재하고 행 수가 반환되는지
- 테스트 후 테스트 DB를 자동 삭제 (trap 사용)

```bash
# 최신 덤프로 자동 검증
./scripts/test-restore.sh

# 특정 덤프 지정
./scripts/test-restore.sh backups/postgres/20260423/shared_20260423_030000.sql.gz

# 검증할 테이블 조정
EXPECTED_TABLES="documents users api_keys" ./scripts/test-restore.sh
```

이 스크립트는 실패 시 종료 코드 1을 반환한다. cron 결과 메일이나 알림 채널과 연동하여
사일런트한 백업 손상을 조기에 감지한다.

## 재해 복구(DR) 시나리오

### 시나리오 1: 단일 컨테이너 장애

- 원인: Docker 볼륨/이미지 손상, 업데이트 실패
- 복구: `docker compose down` → 백업으로 볼륨 복원 → `docker compose up -d`
- 기대 RTO: **10~20분**

### 시나리오 2: 호스트 전체 손실

- 원인: 디스크/하드웨어/재해
- 복구:
    1. 새 호스트에 Docker + 저장소 clone
    2. `backups/` 디렉토리를 오프사이트 스토리지에서 복사
    3. `docker compose up -d`로 인프라 기동 (빈 볼륨)
    4. `scripts/restore.sh`로 PostgreSQL + Elasticsearch 복원
- 기대 RTO: **30분~1시간** (네트워크 전송 시간 포함)

### 시나리오 3: 사용자 실수로 인한 데이터 손상

- 원인: 잘못된 `DELETE` / 대량 삭제 / 설정 오류
- 복구:
    1. 가장 최근의 정상 백업 선택
    2. `restore.sh`로 대상 DB만 복원
    3. 문제 발생 이후의 사용자 변경은 **손실됨** — RPO 범위 내
- 기대 RTO: **15~30분**

## 실패 시 에스컬레이션

백업 또는 복원 실패 시:

1. 스크립트 종료 코드가 0이 아니면 cron이 stderr를 이메일로 발송 (표준 cron MAILTO 사용)
2. `logs/backup.log` 최근 100줄 확인
3. Elasticsearch 쪽이면 `docker logs shared-elasticsearch --tail 200`
4. 디스크 여유 공간 확인: `df -h /var/lib/docker`, `df -h backups/`
5. 복원 검증이 실패하면 즉시 백업 체인을 수동 점검 (이전 2~3일치 dump로 재시도)
