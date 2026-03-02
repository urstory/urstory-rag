"""LLM 기반 멀티쿼리 생성.

사용자 질문을 여러 변형으로 재작성하여 검색 커버리지를 높인다.
어휘 불일치(query-document vocabulary mismatch) 문제를 해결하는 핵심 전략.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.services.generation.base import LLMProvider

logger = logging.getLogger(__name__)

MULTI_QUERY_PROMPT = """다음 질문에 대해 검색 성능을 높이기 위한 변형 질문을 {count}개 생성하세요.

변형 규칙:
1. 핵심 용어를 더 일반적/공식적 단어로 바꾼 질문
2. 문서나 규정에 있을 법한 문장 형태로 바꾼 질문
3. 부정 표현이 있으면 긍정으로, 긍정이면 관련 예외/제외 조건으로 바꾼 질문

한 줄에 하나씩, 번호 없이 질문만 작성하세요.

원본 질문: {query}

변형 질문:"""


@dataclass
class MultiQueryResult:
    original_query: str
    variant_queries: list[str] = field(default_factory=list)


class MultiQueryGenerator:
    """LLM 기반 멀티쿼리 생성기.

    4종 변형 템플릿:
    1. 원문 그대로
    2. 용어를 일반적 표현으로 교체
    3. 문서 규정 문장 형태로 변환
    4. 부정 조건을 긍정으로 뒤집기 (해당 시)

    안전장치: LLM 호출 실패/타임아웃 시 원문 쿼리만으로 폴백 (검색 파이프라인 중단 방지)
    """

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def generate(self, query: str, count: int = 4) -> MultiQueryResult:
        """변형 쿼리를 생성한다.

        LLM 호출 실패 시 로깅 후 원문만 포함한 결과를 반환한다.
        """
        try:
            prompt = MULTI_QUERY_PROMPT.format(query=query, count=count - 1)
            response = await self.llm.generate(prompt)
            variants = self._parse_variants(response)
        except Exception:
            logger.warning("멀티쿼리 생성 실패, 원문만 사용: %s", query, exc_info=True)
            variants = []

        # 원문을 항상 첫 번째로 포함
        all_queries = [query] + [v for v in variants if v != query]
        # count 제한
        all_queries = all_queries[:count]

        return MultiQueryResult(
            original_query=query,
            variant_queries=all_queries,
        )

    @staticmethod
    def _parse_variants(raw: str) -> list[str]:
        """LLM 응답에서 변형 쿼리를 파싱한다."""
        if not raw or not raw.strip():
            return []

        variants = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # 번호 접두사 제거: "1. ", "1) ", "- " 등
            line = re.sub(r"^\d+[.)]\s*", "", line)
            line = re.sub(r"^[-•]\s*", "", line)
            line = line.strip()
            if line:
                variants.append(line)

        return variants
