"""HyDE 기반 쿼리 확장.

BM25 검색 실패 시 LLM으로 가상 답변을 생성하고,
가상 답변에서 핵심 키워드를 추출하여 ES 재검색 쿼리를 구성한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.generation.base import LLMProvider

HYDE_EXPANSION_PROMPT = """다음 질문에 대한 답변이 될 수 있는 짧은 문단을 작성하세요.
실제 사실 여부는 중요하지 않습니다. 질문과 관련된 구체적인 용어, 수치, 고유명사를 포함하세요.

질문: {query}

답변:"""

KEYWORD_EXTRACTION_PROMPT = """다음 텍스트에서 검색에 가장 유용한 핵심 키워드를 {max_keywords}개 추출하세요.
한국어 명사, 고유명사, 전문 용어를 우선 추출하세요.
키워드만 쉼표로 구분하여 나열하세요. 다른 설명은 불필요합니다.

텍스트: {text}

키워드:"""


@dataclass
class ExpandedQuery:
    original_query: str
    hypothetical_answer: str
    expanded_keywords: list[str] = field(default_factory=list)
    expanded_query: str = ""


class QueryExpander:
    """HyDE 기반 쿼리 확장.

    1. LLM으로 가상 답변 생성
    2. 가상 답변에서 핵심 키워드 추출
    3. 원본 쿼리 + 확장 키워드로 결합
    """

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def expand(self, query: str, max_keywords: int = 10) -> ExpandedQuery:
        """쿼리를 확장한다."""
        # 1. HyDE 가상 답변 생성
        hyde_prompt = HYDE_EXPANSION_PROMPT.format(query=query)
        hypothetical_answer = await self.llm.generate(hyde_prompt)

        # 2. 가상 답변에서 키워드 추출
        extraction_prompt = KEYWORD_EXTRACTION_PROMPT.format(
            text=hypothetical_answer,
            max_keywords=max_keywords,
        )
        keywords_raw = await self.llm.generate(extraction_prompt)
        keywords = self._parse_keywords(keywords_raw, max_keywords)

        # 3. 원본 쿼리 + 키워드 결합
        if keywords:
            expanded_query = query + " " + " ".join(keywords)
        else:
            expanded_query = query

        return ExpandedQuery(
            original_query=query,
            hypothetical_answer=hypothetical_answer,
            expanded_keywords=keywords,
            expanded_query=expanded_query,
        )

    @staticmethod
    def _parse_keywords(raw: str, max_keywords: int) -> list[str]:
        """LLM 응답에서 키워드를 파싱한다."""
        if not raw or not raw.strip():
            return []
        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        return keywords[:max_keywords]
