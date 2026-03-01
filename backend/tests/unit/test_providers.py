"""Step 2.6 RED: LLM/Embedding 프로바이더 Protocol 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_embedding_provider_protocol():
    """EmbeddingProvider Protocol 인터페이스 준수 확인."""
    from app.services.embedding.base import EmbeddingProvider
    from app.services.embedding.ollama import OllamaEmbedding

    assert isinstance(OllamaEmbedding(url="http://test:11434"), EmbeddingProvider)


def test_llm_provider_protocol():
    """LLMProvider Protocol 인터페이스 준수 확인."""
    from app.services.generation.base import LLMProvider
    from app.services.generation.ollama import OllamaLLM

    assert isinstance(OllamaLLM(url="http://test:11434"), LLMProvider)


def _make_httpx_response(json_data, status_code=200):
    """httpx.Response를 모방하는 MagicMock 생성 (json()과 raise_for_status()는 동기)."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    return mock


@pytest.mark.asyncio
async def test_ollama_embedding_embed_query():
    """Mock Ollama API 응답으로 벡터 반환 검증."""
    from app.services.embedding.ollama import OllamaEmbedding

    embedding = OllamaEmbedding(url="http://test:11434", model="bge-m3")
    mock_resp = _make_httpx_response({"embeddings": [[0.1] * 1024]})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await embedding.embed_query("테스트 쿼리")

    assert len(result) == 1024
    assert result[0] == 0.1


@pytest.mark.asyncio
async def test_ollama_embedding_embed_documents():
    """Mock Ollama API 배치 임베딩 검증."""
    from app.services.embedding.ollama import OllamaEmbedding

    embedding = OllamaEmbedding(url="http://test:11434", model="bge-m3")
    mock_resp = _make_httpx_response({"embeddings": [[0.1] * 1024, [0.2] * 1024]})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await embedding.embed_documents(["문서1", "문서2"])

    assert len(result) == 2
    assert len(result[0]) == 1024
    assert result[1][0] == 0.2


@pytest.mark.asyncio
async def test_ollama_embedding_error():
    """Ollama 에러 시 EmbeddingServiceError 발생."""
    from app.exceptions import EmbeddingServiceError
    from app.services.embedding.ollama import OllamaEmbedding

    embedding = OllamaEmbedding(url="http://test:11434")
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("Ollama down")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(EmbeddingServiceError):
            await embedding.embed_query("fail")


@pytest.mark.asyncio
async def test_ollama_llm_generate():
    """Mock Ollama API 응답으로 텍스트 생성 검증."""
    from app.services.generation.ollama import OllamaLLM

    llm = OllamaLLM(url="http://test:11434", model="qwen2.5:7b")
    mock_resp = _make_httpx_response({"response": "답변 내용입니다."})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await llm.generate("질문입니다")

    assert result == "답변 내용입니다."


@pytest.mark.asyncio
async def test_ollama_llm_generate_with_system_prompt():
    """시스템 프롬프트와 함께 생성 검증."""
    from app.services.generation.ollama import OllamaLLM

    llm = OllamaLLM(url="http://test:11434", model="qwen2.5:7b")
    mock_resp = _make_httpx_response({"response": "시스템 프롬프트 적용 답변"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        result = await llm.generate("질문", system_prompt="한국어로 답하세요")

    assert result == "시스템 프롬프트 적용 답변"
    call_kwargs = mock_post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["system"] == "한국어로 답하세요"
