"""OpenAI 호환 API 엔드포인트.

POST /v1/chat/completions  — Chat Completions (검색 + 답변 생성)
GET  /v1/models            — 모델 목록
"""
from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_user
from app.models.database import User
from app.models.schemas import OpenAIChatRequest

router = APIRouter(tags=["openai"])


def _estimate_tokens(text: str) -> int:
    """한국어 텍스트의 토큰 수를 근사 추정 (글자당 ~1.5토큰)."""
    if not text:
        return 0
    return max(1, int(len(text) * 1.5))


@router.post(
    "/v1/chat/completions",
    summary="Chat Completions (OpenAI 호환)",
    description="OpenAI SDK의 base_url을 변경하여 UrstoryRAG를 사용할 수 있습니다. "
                "messages의 마지막 user 메시지를 RAG 검색 쿼리로 사용합니다.",
)
async def chat_completions(
    request: OpenAIChatRequest,
    user: User = Depends(get_current_user),
):
    # 1. messages에서 마지막 user 메시지 추출
    query = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            query = msg.content
            break

    if not query:
        raise HTTPException(status_code=400, detail={
            "error": {
                "message": "messages에 user 역할의 메시지가 필요합니다.",
                "type": "invalid_request_error",
                "param": "messages",
                "code": None,
            }
        })

    # 2. system 메시지 추출 (선택)
    system_prompt = None
    for msg in request.messages:
        if msg.role == "system":
            system_prompt = msg.content
            break

    # 3. orchestrator + settings 가져오기
    from app.api.search import get_orchestrator, get_search_settings_service
    orchestrator = get_orchestrator()
    settings_service = get_search_settings_service()
    settings = await settings_service.get_settings()

    if system_prompt:
        settings = settings.model_copy(update={"system_prompt": system_prompt})
    if request.temperature is not None:
        settings = settings.model_copy(update={"llm_temperature": request.temperature})

    # 4. RAG 검색 실행
    result = await orchestrator.search(query, settings, generate_answer=True)
    answer = result.answer or ""

    # 5. 응답 생성
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    prompt_tokens = _estimate_tokens(query)
    completion_tokens = _estimate_tokens(answer)

    if request.stream:
        return StreamingResponse(
            _stream_response(completion_id, created, request.model, answer),
            media_type="text/event-stream",
        )

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": request.model,
        "system_fingerprint": None,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


async def _stream_response(completion_id: str, created: int, model: str, answer: str):
    """답변을 청크 단위로 SSE 스트리밍한다 (시뮬레이션)."""
    # 단어 단위로 분할
    words = answer.split(" ")
    chunks = []
    current = ""
    for word in words:
        current += (" " if current else "") + word
        if len(current) >= 10:  # ~10자 단위로 청크
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)

    if not chunks:
        chunks = [answer]

    for i, chunk_text in enumerate(chunks):
        data = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "system_fingerprint": None,
            "choices": [{
                "index": 0,
                "delta": {"content": chunk_text} if i > 0 else {"role": "assistant", "content": chunk_text},
                "finish_reason": None,
            }],
        }
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    # finish chunk
    finish_data = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "system_fingerprint": None,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop",
        }],
    }
    yield f"data: {json.dumps(finish_data, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.get(
    "/v1/models",
    summary="모델 목록 (OpenAI 호환)",
    description="사용 가능한 모델 목록을 OpenAI API 형식으로 반환합니다.",
)
async def list_models(user: User = Depends(get_current_user)):
    return {
        "object": "list",
        "data": [
            {
                "id": "urstory-rag",
                "object": "model",
                "created": 1700000000,
                "owned_by": "urstory",
            }
        ],
    }
