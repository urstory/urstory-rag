"""LLM 기반 멀티쿼리 생성.

사용자 질문을 구조 분해하여 검색 커버리지를 높인다.
비교·복합 질문을 개별 하위 질문으로 분리하는 전략.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.services.generation.base import LLMProvider

logger = logging.getLogger(__name__)

MULTI_QUERY_PROMPT = """다음 질문에 대해 검색 성능을 높이기 위한 변형 질문을 {count}개 생성하세요.

변형 규칙 (우선순위 순):
1. 비교 질문("A와 B의 차이", "A 대 B")이면 → 각 대상을 개별 질문으로 분리
2. 여러 조건이 있는 복합 질문이면 → 각 조건을 개별 질문으로 분리
3. 위에 해당하지 않으면 → 문서나 규정에 있을 법한 문장 형태로 바꾼 질문

한 줄에 하나씩, 번호 없이 질문만 작성하세요.

원본 질문: {query}

변형 질문:"""


@dataclass
class MultiQueryResult:
    original_query: str
    variant_queries: list[str] = field(default_factory=list)


class MultiQueryGenerator:
    """LLM 기반 멀티쿼리 생성기.

    구조 분해 전략:
    1. 원문 그대로
    2. 비교 질문 → 각 대상 개별 질문으로 분리
    3. 복합 조건 질문 → 각 조건별 개별 질문으로 분리
    4. 단순 질문 → 문서 규정 문장 형태로 변환

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
