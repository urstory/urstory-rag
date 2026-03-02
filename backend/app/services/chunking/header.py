"""섹션 헤더 기반 Contextual Chunking: 각 청크에 브레드크럼 헤더를 prepend."""
import re

from app.services.chunking.base import Chunk
from app.services.chunking.recursive import RecursiveChunking


class SectionHeaderChunking:
    """문서의 섹션 구조를 파싱하여 각 청크에 계층 헤더를 붙인다.

    - Markdown: # ## ### 헤딩을 정규식으로 파싱
    - PDF/기타 평문: 짧은 줄(80자 이하, 마침표 없음)을 헤딩으로 추정
    - 각 청크 앞에 "[# Title > ## Section > ### Sub]" 형태의 브레드크럼 prepend
    """

    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 100):
        self.base_chunker = RecursiveChunking(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]:
        if not text.strip():
            return []

        file_type = (meta or {}).get("file_type", "txt")
        if file_type == "md":
            sections = self._parse_markdown(text)
        else:
            sections = self._parse_plaintext(text)

        all_chunks: list[Chunk] = []
        for breadcrumb, section_text in sections:
            if not section_text.strip():
                continue
            sub_chunks = await self.base_chunker.chunk(section_text, meta)
            for chunk in sub_chunks:
                if breadcrumb:
                    chunk.content = f"[{breadcrumb}]\n\n{chunk.content}"
                chunk.chunk_index = len(all_chunks)
                all_chunks.append(chunk)

        if not all_chunks:
            return [Chunk(content=text, chunk_index=0, metadata=meta or {})]

        return all_chunks

    def _parse_markdown(self, text: str) -> list[tuple[str, str]]:
        """Markdown 헤딩(# ## ###)을 파싱하여 (브레드크럼, 본문) 리스트 반환."""
        heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
        sections: list[tuple[str, str]] = []
        # 헤딩 레벨별 스택: [h1, h2, h3]
        heading_stack: list[str] = ["", "", ""]
        last_pos = 0

        matches = list(heading_pattern.finditer(text))

        if not matches:
            # 헤딩이 없으면 전체를 하나의 섹션으로
            return [("", text)]

        # 첫 헤딩 이전 텍스트
        pre_text = text[:matches[0].start()].strip()
        if pre_text:
            sections.append(("", pre_text))

        for i, match in enumerate(matches):
            level = len(match.group(1))  # 1, 2, or 3
            title = match.group(2).strip()

            # 스택 업데이트
            heading_stack[level - 1] = f"{'#' * level} {title}"
            # 하위 레벨 초기화
            for j in range(level, 3):
                heading_stack[j] = ""

            # 브레드크럼 생성
            breadcrumb = " > ".join(h for h in heading_stack if h)

            # 섹션 본문: 현재 헤딩 끝 ~ 다음 헤딩 시작
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()

            if section_text:
                sections.append((breadcrumb, section_text))

        return sections

    def _parse_plaintext(self, text: str) -> list[tuple[str, str]]:
        """평문(PDF 변환 텍스트)에서 헤딩을 추정하여 섹션 분리.

        짧은 줄(80자 이하, 마침표 없음)을 헤딩 후보로 간주.
        """
        lines = text.split("\n")
        sections: list[tuple[str, str]] = []
        current_heading = ""
        current_lines: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if self._is_heading_candidate(stripped, i, lines):
                # 이전 섹션 저장
                if current_lines:
                    body = "\n".join(current_lines).strip()
                    if body:
                        sections.append((current_heading, body))
                    current_lines = []
                current_heading = stripped
            else:
                current_lines.append(line)

        # 마지막 섹션
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_heading, body))

        if not sections:
            return [("", text)]

        return sections

    def _is_heading_candidate(
        self, line: str, index: int, all_lines: list[str]
    ) -> bool:
        """줄이 헤딩 후보인지 판단."""
        if not line:
            return False
        if len(line) > 80:
            return False
        # 마침표, 쉼표로 끝나면 헤딩 아님
        if line[-1] in ".。,，":
            return False
        # 숫자만으로 구성되면 헤딩 아님
        if line.replace(" ", "").isdigit():
            return False
        # 다음 줄이 존재하고 비어있지 않아야 헤딩
        if index + 1 < len(all_lines):
            next_line = all_lines[index + 1].strip()
            if not next_line:
                return False
        # 앞에 빈 줄이 있으면 헤딩 가능성 높음
        if index > 0 and all_lines[index - 1].strip() == "":
            return True
        # 첫 줄이면 헤딩
        if index == 0:
            return True
        return False
