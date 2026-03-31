"""API Key 서비스 및 OpenAI 호환 엔드포인트 테스트 (Phase 17)."""
import pytest

from app.services.apikey import generate_api_key, hash_api_key


class TestApiKeyGeneration:
    """API Key 생성/해싱 단위 테스트."""

    def test_key_starts_with_prefix(self):
        key = generate_api_key()
        assert key.startswith("rag_sk_")

    def test_key_length_sufficient(self):
        key = generate_api_key()
        assert len(key) >= 48

    def test_keys_are_unique(self):
        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10

    def test_hash_is_deterministic(self):
        key = "rag_sk_test123"
        assert hash_api_key(key) == hash_api_key(key)

    def test_different_keys_different_hashes(self):
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert hash_api_key(k1) != hash_api_key(k2)

    def test_hash_is_64_char_hex(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestOpenAISchemas:
    """OpenAI 호환 스키마 테스트."""

    def test_chat_request_defaults(self):
        from app.models.schemas import OpenAIChatRequest
        req = OpenAIChatRequest(messages=[{"role": "user", "content": "test"}])
        assert req.model == "urstory-rag"
        assert req.stream is False

    def test_chat_request_with_stream(self):
        from app.models.schemas import OpenAIChatRequest
        req = OpenAIChatRequest(
            messages=[{"role": "user", "content": "test"}],
            stream=True,
        )
        assert req.stream is True

    def test_apikey_create_request(self):
        from app.models.schemas import ApiKeyCreateRequest
        req = ApiKeyCreateRequest(name="테스트 키")
        assert req.name == "테스트 키"
        assert req.expires_in_days is None

    def test_apikey_create_request_with_expiry(self):
        from app.models.schemas import ApiKeyCreateRequest
        req = ApiKeyCreateRequest(name="만료 키", expires_in_days=30)
        assert req.expires_in_days == 30


class TestEstimateTokens:
    """토큰 근사 추정 테스트."""

    def test_empty_string(self):
        from app.api.openai_compat import _estimate_tokens
        assert _estimate_tokens("") == 0

    def test_korean_text(self):
        from app.api.openai_compat import _estimate_tokens
        tokens = _estimate_tokens("한국의 GDP 성장률은?")
        assert tokens > 0

    def test_returns_at_least_one(self):
        from app.api.openai_compat import _estimate_tokens
        assert _estimate_tokens("a") >= 1
