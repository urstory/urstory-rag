"""Step 4.2 RED: Elasticsearch + Nori 키워드 검색 엔진 테스트."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: httpx.Response mock 생성
# ---------------------------------------------------------------------------

def _make_httpx_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """httpx.Response를 모방하는 MagicMock 생성."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Fixtures: 반복 사용하는 테스트 데이터
# ---------------------------------------------------------------------------

CHUNK_ID_1 = str(uuid.uuid4())
CHUNK_ID_2 = str(uuid.uuid4())
DOC_ID = str(uuid.uuid4())


def _es_hits_response(hits: list[dict], total: int | None = None) -> dict:
    """Elasticsearch _search 응답 형식을 생성한다."""
    if total is None:
        total = len(hits)
    return {
        "took": 5,
        "timed_out": False,
        "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
        "hits": {
            "total": {"value": total, "relation": "eq"},
            "max_score": hits[0]["_score"] if hits else None,
            "hits": hits,
        },
    }


def _make_hit(
    chunk_id: str, document_id: str, content: str, score: float, metadata: dict | None = None
) -> dict:
    """단일 ES hit 문서를 생성한다."""
    source = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "content": content,
    }
    if metadata is not None:
        source["metadata"] = metadata
    return {
        "_index": "rag_chunks",
        "_id": chunk_id,
        "_score": score,
        "_source": source,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_search_nori():
    """Mock ES 응답으로 한국어 쿼리에 대한 SearchResult 리스트 반환 검증."""
    from app.services.search.keyword_es import ElasticsearchNoriEngine

    engine = ElasticsearchNoriEngine(es_url="http://test:9200", index_name="rag_chunks")

    hits = [
        _make_hit(CHUNK_ID_1, DOC_ID, "서울은 대한민국의 수도입니다.", 5.23, {"page": 1}),
        _make_hit(CHUNK_ID_2, DOC_ID, "부산은 대한민국 제2의 도시입니다.", 4.11),
    ]
    mock_resp = _make_httpx_response(_es_hits_response(hits))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        results = await engine.search("대한민국 수도")

    assert len(results) == 2
    assert results[0].chunk_id == uuid.UUID(CHUNK_ID_1)
    assert results[0].document_id == uuid.UUID(DOC_ID)
    assert results[0].content == "서울은 대한민국의 수도입니다."
    assert results[0].score == 5.23
    assert results[0].metadata == {"page": 1}
    # 두 번째 결과: metadata가 _source에 없으면 None
    assert results[1].metadata is None


@pytest.mark.asyncio
async def test_keyword_search_top_k():
    """top_k 파라미터가 ES 요청의 size로 전달되는지 검증."""
    from app.services.search.keyword_es import ElasticsearchNoriEngine

    engine = ElasticsearchNoriEngine(es_url="http://test:9200")

    hits = [_make_hit(CHUNK_ID_1, DOC_ID, "테스트 문서", 3.0)]
    mock_resp = _make_httpx_response(_es_hits_response(hits))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        await engine.search("테스트", top_k=5)

    call_kwargs = mock_post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["size"] == 5


@pytest.mark.asyncio
async def test_keyword_search_morpheme():
    """쿼리가 ES match 쿼리로 전송되는지 검증 (Nori 형태소 분석은 인덱스 레벨)."""
    from app.services.search.keyword_es import ElasticsearchNoriEngine

    engine = ElasticsearchNoriEngine(es_url="http://test:9200")

    mock_resp = _make_httpx_response(_es_hits_response([]))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        await engine.search("한국어 형태소 분석 테스트")

    call_kwargs = mock_post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    # bool > must > match > content 구조 확인
    must_clauses = body["query"]["bool"]["must"]
    match_clause = must_clauses[0]
    assert "match" in match_clause
    assert match_clause["match"]["content"] == "한국어 형태소 분석 테스트"


@pytest.mark.asyncio
async def test_keyword_search_empty():
    """검색 결과가 없을 때 빈 리스트 반환 검증."""
    from app.services.search.keyword_es import ElasticsearchNoriEngine

    engine = ElasticsearchNoriEngine(es_url="http://test:9200")

    mock_resp = _make_httpx_response(_es_hits_response([]))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        results = await engine.search("존재하지 않는 검색어")

    assert results == []


@pytest.mark.asyncio
async def test_keyword_search_with_doc_filter():
    """doc_id 필터가 ES term 필터로 변환되는지 검증."""
    from app.services.search.keyword_es import ElasticsearchNoriEngine

    engine = ElasticsearchNoriEngine(es_url="http://test:9200")

    hits = [_make_hit(CHUNK_ID_1, DOC_ID, "필터링된 문서 내용", 4.0)]
    mock_resp = _make_httpx_response(_es_hits_response(hits))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        results = await engine.search("문서 내용", doc_id=DOC_ID)

    assert len(results) == 1

    call_kwargs = mock_post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    # bool > filter 에 term document_id 필터 확인
    filter_clauses = body["query"]["bool"]["filter"]
    assert len(filter_clauses) == 1
    assert filter_clauses[0] == {"term": {"document_id": DOC_ID}}


@pytest.mark.asyncio
async def test_keyword_search_error():
    """ES 에러 시 SearchServiceError 발생 검증."""
    from app.exceptions import SearchServiceError
    from app.services.search.keyword_es import ElasticsearchNoriEngine

    engine = ElasticsearchNoriEngine(es_url="http://test:9200")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("Connection refused")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(SearchServiceError):
            await engine.search("에러 테스트")
