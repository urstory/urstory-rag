"""Step 4.8 GREEN: 한국어 RAG 프롬프트 관리 모듈."""
from __future__ import annotations

from app.models.schemas import SearchResult

SYSTEM_PROMPT = """당신은 사내 문서를 기반으로 질문에 답변하는 AI 어시스턴트입니다.
규칙:
1. 제공된 문서의 내용만을 기반으로 답변하세요.
2. 문서에 없는 내용은 "제공된 문서에서 관련 정보를 찾을 수 없습니다"라고 답변하세요.
3. 답변에 출처 문서를 명시하세요.
4. 개인정보가 포함된 내용은 마스킹하여 표시하세요."""

USER_PROMPT = """다음 문서들을 참고하여 질문에 답변하세요.

{documents}

질문: {query}

답변:"""


def build_prompt(query: str, documents: list[SearchResult]) -> str:
    """검색 결과와 질문을 기반으로 LLM에 전달할 사용자 프롬프트를 생성한다.

    Args:
        query: 사용자 질문
        documents: 검색 결과 목록

    Returns:
        포맷된 사용자 프롬프트 문자열
    """
    if not documents:
        docs_text = "(검색된 문서가 없습니다)"
    else:
        docs_text = "\n\n---\n\n".join(
            f"[문서 {i + 1}]\n{doc.content}" for i, doc in enumerate(documents)
        )
    return USER_PROMPT.format(documents=docs_text, query=query)
