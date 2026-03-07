"""structlog 로깅 설정 테스트."""
import logging

from app.logging_config import mask_sensitive, setup_logging


class TestMaskSensitive:
    def _mask(self, msg: str) -> str:
        event_dict = {"event": msg}
        result = mask_sensitive(None, None, event_dict)
        return result["event"]

    def test_mask_sensitive_api_key(self):
        msg = "Using key sk-abcdefghij1234567890abcdef"
        result = self._mask(msg)
        assert "sk-" not in result
        assert "***API_KEY***" in result

    def test_mask_sensitive_jwt(self):
        msg = "Token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = self._mask(msg)
        assert "eyJ" not in result
        assert "***JWT***" in result

    def test_mask_sensitive_password(self):
        msg = 'password = "MySecret123!"'
        result = self._mask(msg)
        assert "MySecret123!" not in result
        assert '***' in result

    def test_mask_sensitive_bearer(self):
        msg = "Bearer eyJhbGciOiJIUzI1NiJ9.test.signature"
        result = self._mask(msg)
        assert result == "Bearer ***"

    def test_no_mask_normal_text(self):
        msg = "Normal log message without sensitive data"
        result = self._mask(msg)
        assert result == msg


class TestSetupLogging:
    def test_setup_logging_json(self):
        setup_logging(log_level="INFO", json_format=True)
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) == 1

    def test_setup_logging_console(self):
        setup_logging(log_level="DEBUG", json_format=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_setup_logging_clears_uvicorn_handlers(self):
        uv_logger = logging.getLogger("uvicorn")
        uv_logger.addHandler(logging.StreamHandler())
        setup_logging()
        assert len(uv_logger.handlers) == 0
        assert uv_logger.propagate is True
