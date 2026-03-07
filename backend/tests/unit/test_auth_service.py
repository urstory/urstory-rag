"""인증 서비스 단위 테스트."""
import time
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_jwt_secret(monkeypatch):
    """모든 테스트에 JWT_SECRET_KEY 설정."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-unit-testing-min32chars!")
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestPasswordHashing:
    def test_hash_and_verify(self):
        from app.services.auth import hash_password, verify_password
        hashed = hash_password("MyPassword123!@#")
        assert verify_password("MyPassword123!@#", hashed)
        assert not verify_password("WrongPassword123!@#", hashed)

    def test_different_hashes_for_same_password(self):
        from app.services.auth import hash_password
        h1 = hash_password("MyPassword123!@#")
        h2 = hash_password("MyPassword123!@#")
        assert h1 != h2  # bcrypt salt가 다르므로


class TestPasswordValidation:
    def test_valid_password(self):
        from app.services.auth import validate_password_strength
        validate_password_strength("ValidPass123!@#")

    def test_too_short(self):
        from app.services.auth import validate_password_strength
        with pytest.raises(ValueError, match="12자"):
            validate_password_strength("Short1!@")

    def test_no_uppercase(self):
        from app.services.auth import validate_password_strength
        with pytest.raises(ValueError, match="대문자"):
            validate_password_strength("nouppercase123!@#")

    def test_no_lowercase(self):
        from app.services.auth import validate_password_strength
        with pytest.raises(ValueError, match="소문자"):
            validate_password_strength("NOLOWERCASE123!@#")

    def test_no_digit(self):
        from app.services.auth import validate_password_strength
        with pytest.raises(ValueError, match="숫자"):
            validate_password_strength("NoDigitsHere!@#$")

    def test_no_special_char(self):
        from app.services.auth import validate_password_strength
        with pytest.raises(ValueError, match="특수문자"):
            validate_password_strength("NoSpecialChar123")


class TestJWTTokens:
    def test_create_and_decode_access_token(self):
        from app.services.auth import create_access_token, decode_token
        token = create_access_token(user_id=1, role="admin")
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert "jti" in payload

    def test_create_and_decode_refresh_token(self):
        from app.services.auth import create_refresh_token, decode_token
        token = create_refresh_token(user_id=42)
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"
        assert "jti" in payload

    def test_expired_token_raises(self):
        import jwt as pyjwt
        from app.services.auth import decode_token, ALGORITHM

        # 만료된 토큰 직접 생성
        payload = {"sub": "1", "exp": int(time.time()) - 10}
        token = pyjwt.encode(payload, "test-secret-key-for-unit-testing-min32chars!", algorithm=ALGORITHM)

        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)

    def test_invalid_token_raises(self):
        import jwt as pyjwt
        from app.services.auth import decode_token
        with pytest.raises(pyjwt.DecodeError):
            decode_token("invalid.token.here")

    def test_missing_jwt_secret_raises(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "")
        from app.config import get_settings
        get_settings.cache_clear()

        from app.services.auth import create_access_token
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            create_access_token(user_id=1, role="user")
