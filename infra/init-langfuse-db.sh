#!/bin/bash
# Langfuse 전용 데이터베이스 생성
# Docker postgres entrypoint가 /docker-entrypoint-initdb.d/ 내 .sh 파일을 자동 실행한다.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE langfuse OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
EOSQL
