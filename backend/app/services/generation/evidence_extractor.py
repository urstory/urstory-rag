"""CoT 기반 근거 추출 + 답변 생성.

규정형 질문에 대해 단일 LLM 호출로 근거 문장 추출과 답변 생성을 수행한다.
숫자/수치 왜곡을 방지하기 위해 근거 문장의 원문을 그대로 인용하도록 강제한다.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.models.schemas import SearchResult
from app.services.generation.base import LLMProvider

logger = logging.getLogger(__name__)

EVIDENCE_COT_SYSTEM_PROMPT = """당신은 문서를 기반으로 정확하게 답변하는 AI 어시스턴트입니다.
숫자, 기간, 횟수, 주기, 금액은 문서 원문을 글자 그대로 인용해야 합니다."""

EXTRACTION_SYSTEM_PROMPT = """당신은 문서에서 정확한 정보를 추출하는 AI 어시스턴트입니다.
이름, 명칭, 고유명사, 목록 항목은 문서 원문을 글자 그대로 추출해야 합니다."""

EXTRACTION_PROMPT = """아래 문서에서 질문의 정답을 찾아 추출하세요.

규칙:
- 정답이 이름, 명칭, 고유명사이면 문서에 적힌 그대로 추출하세요.
- 정답이 목록이면 번호를 붙여 모두 나열하세요. 하나도 빠뜨리지 마세요.
- 문서에 없는 내용은 추가하지 마세요.
- 서술하지 말고 답만 적으세요.

{documents}

질문: {query}

[근거]
"""

EVIDENCE_COT_PROMPT = """아래 문서를 참고하여 질문에 답변하세요. 반드시 다음 두 단계를 순서대로 수행하세요.

[1단계: 근거 추출]
문서에서 질문에 직접 답하는 문장을 1~3개 찾아 원문 그대로 복사하세요.
문장을 바꾸거나 요약하지 마세요. 찾을 수 없으면 "근거 없음"이라고 쓰세요.

[2단계: 답변 작성]
위에서 추출한 근거 문장만을 사용하여 답변하세요.
숫자, 기간, 횟수, 주기, 금액은 근거 문장의 표현을 글자 그대로 사용하세요.
근거에 없는 수치를 추가하거나 변환하지 마세요.

{documents}

질문: {query}

[근거]
"""


@dataclass
class EvidenceResult:
    evidence_sentences: list[str] = field(default_factory=list)
    answer: str = ""


class EvidenceExtractor:
    """CoT 기반 근거 추출 + 답변 생성 (단일 LLM 호출).

    하나의 프롬프트에서:
    1. 컨텍스트에서 질문에 답하는 문장 1~3개를 그대로 추출
    2. 추출된 문장만으로 답변 작성 (수치 변형 금지)
    """

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def extract_short_answer(
        self, query: str, documents: list[SearchResult],
    ) -> EvidenceResult | None:
        """추출형 질문 전용: 문서에서 단답을 추출한다 (1회 LLM 호출).

        이름, 명칭, 고유명사, 목록 등 서술 없이 정확한 답만 추출.
        """
        try:
            docs_text = self._format_documents(documents)
            prompt = EXTRACTION_PROMPT.format(documents=docs_text, query=query)
            response = await self.llm.generate(
                prompt, system_prompt=EXTRACTION_SYSTEM_PROMPT,
            )
            return self._parse_response(response)
        except Exception:
            logger.warning("추출 모드 실패, 기존 생성으로 폴백: %s", query, exc_info=True)
            return None

    async def extract_and_answer(
        self, query: str, documents: list[SearchResult],
    ) -> EvidenceResult | None:
        """근거를 추출하고 답변을 생성한다 (1회 LLM 호출).

        LLM 호출 실패 시 None을 반환하여 기존 생성 프롬프트로 폴백 가능.
        """
        try:
            docs_text = self._format_documents(documents)
            prompt = EVIDENCE_COT_PROMPT.format(documents=docs_text, query=query)
            response = await self.llm.generate(
                prompt, system_prompt=EVIDENCE_COT_SYSTEM_PROMPT,
            )
            return self._parse_response(response)
        except Exception:
            logger.warning("근거 추출 실패, 기존 생성으로 폴백: %s", query, exc_info=True)
            return None

    def _parse_response(self, response: str) -> EvidenceResult:
        """LLM 응답에서 [근거]와 [답변] 섹션을 분리 파싱한다."""
        # [답변] 섹션 분리
        answer_match = re.search(r"\[답변\]\s*\n?(.*)", response, re.DOTALL)

        if answer_match:
            answer = answer_match.group(1).strip()
            # [근거] 섹션 추출 (응답 시작부터 [답변] 앞까지)
            evidence_section = response[:answer_match.start()]
            # [근거] 태그 제거
            evidence_section = re.sub(r"\[근거\]\s*\n?", "", evidence_section).strip()
            evidence_sentences = self._parse_evidence(evidence_section)
        else:
            # [답변] 섹션이 없으면 전체를 답변으로 처리
            answer = response.strip()
            evidence_sentences = []

        return EvidenceResult(
            evidence_sentences=evidence_sentences,
            answer=answer,
        )

    @staticmethod
    def _parse_evidence(section: str) -> list[str]:
        """근거 섹션에서 개별 문장을 추출한다."""
        if not section or "근거 없음" in section:
            return []

        sentences = []
        for line in section.strip().splitlines():
            line = line.strip()
            # 번호/불릿 접두사 제거
            line = re.sub(r"^\d+[.)]\s*", "", line)
            line = re.sub(r"^[-•]\s*", "", line)
            line = line.strip()
            if line:
                sentences.append(line)

        return sentences

    @staticmethod
    def _format_documents(documents: list[SearchResult]) -> str:
        """검색 결과를 문서 텍스트로 포맷한다."""
        if not documents:
            return "(검색된 문서가 없습니다)"
        return "\n\n---\n\n".join(
            f"[문서 {i + 1}]\n{doc.content}" for i, doc in enumerate(documents)
        )
