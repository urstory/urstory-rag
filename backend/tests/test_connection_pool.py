"""커넥션 풀 설정 테스트 (Phase 16, Issue #11)."""
import os

import pytest


class TestPoolConfiguration:
    """커넥션 풀 환경변수가 Settings에 올바르게 반영되는지 검증."""

    def _make_settings(self, monkeypatch, **env_vars):
        """환경변수를 설정하고 새 Settings 인스턴스를 생성."""
        for key, val in env_vars.items():
            monkeypatch.setenv(key.upper(), str(val))
        from app.config import get_settings
        get_settings.cache_clear()
        return get_settings()

    # --- PostgreSQL ---

    def test_db_pool_size_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.db_pool_size == 10

    def test_db_pool_size_override(self, monkeypatch):
        s = self._make_settings(monkeypatch, db_pool_size=5)
        assert s.db_pool_size == 5

    def test_db_max_overflow_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.db_max_overflow == 20

    def test_db_pool_pre_ping_default_true(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.db_pool_pre_ping is True

    def test_db_pool_recycle_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.db_pool_recycle == 1800

    def test_db_pool_timeout_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.db_pool_timeout == 30

    # --- Elasticsearch ---

    def test_es_max_connections_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.es_max_connections == 20

    def test_es_request_timeout_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.es_request_timeout == 30.0

    def test_es_max_retries_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.es_max_retries == 3

    def test_es_max_connections_override(self, monkeypatch):
        s = self._make_settings(monkeypatch, es_max_connections=50)
        assert s.es_max_connections == 50

    # --- Redis ---

    def test_redis_max_connections_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.redis_max_connections == 20

    def test_redis_socket_timeout_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.redis_socket_timeout == 5.0

    def test_redis_retry_on_timeout_default(self, monkeypatch):
        s = self._make_settings(monkeypatch)
        assert s.redis_retry_on_timeout is True

    def test_redis_max_connections_override(self, monkeypatch):
        s = self._make_settings(monkeypatch, redis_max_connections=50)
        assert s.redis_max_connections == 50
