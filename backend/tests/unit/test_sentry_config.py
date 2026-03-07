"""Sentry 설정 테스트."""
from unittest.mock import patch

from app.sentry_config import _before_send, init_sentry


class TestInitSentry:
    def test_init_sentry_no_dsn(self):
        """DSN 없으면 sentry_sdk.init이 호출되지 않는다."""
        with patch("app.sentry_config.sentry_sdk.init") as mock_init:
            init_sentry(dsn="", environment="test", traces_sample_rate=0.1)
            mock_init.assert_not_called()

    def test_init_sentry_with_dsn(self):
        """DSN이 있으면 sentry_sdk.init이 호출된다."""
        with patch("app.sentry_config.sentry_sdk.init") as mock_init:
            init_sentry(
                dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
                environment="test",
                traces_sample_rate=0.1,
            )
            mock_init.assert_called_once()
            kwargs = mock_init.call_args[1]
            assert kwargs["send_default_pii"] is False
            assert kwargs["environment"] == "test"


class TestBeforeSend:
    def test_before_send_strips_auth(self):
        """Authorization 헤더가 마스킹된다."""
        event = {
            "request": {
                "headers": {
                    "authorization": "Bearer secret-token",
                    "content-type": "application/json",
                }
            }
        }
        result = _before_send(event, {})
        assert result["request"]["headers"]["authorization"] == "***"
        assert result["request"]["headers"]["content-type"] == "application/json"

    def test_before_send_strips_cookie(self):
        """Cookie 헤더가 마스킹된다."""
        event = {
            "request": {
                "headers": {
                    "cookie": "refresh_token=abc123",
                }
            }
        }
        result = _before_send(event, {})
        assert result["request"]["headers"]["cookie"] == "***"

    def test_before_send_no_request(self):
        """request가 없는 이벤트는 그대로 통과한다."""
        event = {"exception": {"values": []}}
        result = _before_send(event, {})
        assert result == event
