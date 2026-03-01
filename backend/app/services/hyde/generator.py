"""Step 4.6 GREEN: HyDE (Hypothetical Document Embeddings) 구현."""
from __future__ import annotations

from app.services.generation.base import LLMProvider


class HyDEGenerator:
    """HyDE: 가상 문서를 생성하여 검색 품질 향상.

    사용자의 쿼리로부터 가상의 답변 문서를 LLM으로 생성한 뒤,
    해당 문서의 임베딩을 활용하여 의미적으로 더 관련성 높은
    실제 문서를 검색할 수 있도록 한다.
    """

    PROMPT = """다음 질문에 대한 답변이 될 수 있는 문서를 한 단락으로 작성하세요.
실제 사실 여부는 중요하지 않습니다. 질문과 관련된 내용을 포함하면 됩니다.

질문: {query}

문서:"""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def generate(self, query: str) -> str:
        """쿼리에 대한 가상 문서 생성."""
        prompt = self.PROMPT.format(query=query)
        return await self.llm.generate(prompt)

    def should_apply(self, query: str, mode: str) -> bool:
        """HyDE 적용 여부 판단.

        Args:
            query: 사용자 질문 문자열.
            mode: 적용 모드.
                - "all": 항상 적용.
                - "long_query": 쿼리 길이가 50자 초과일 때만 적용.
                - "complex": 복합 질문(물음표 2개 이상 또는 접속사 포함)일 때 적용.

        Returns:
            True이면 HyDE를 적용, False이면 원본 쿼리 사용.
        """
        if mode == "all":
            return True
        if mode == "long_query" and len(query) > 50:
            return True
        if mode == "complex" and self._is_complex(query):
            return True
        return False

    def _is_complex(self, query: str) -> bool:
        """복합 질문 판단 (물음표 2개 이상 또는 접속사 포함).

        한국어 접속사 및 조사를 기반으로 복합 질문 여부를 판별한다.
        """
        if query.count("?") >= 2 or query.count("\uff1f") >= 2:
            return True
        complex_markers = [
            "그리고", "또한", "그런데", "하지만",
            "뿐만 아니라", "및", "와", "과",
        ]
        return any(marker in query for marker in complex_markers)
