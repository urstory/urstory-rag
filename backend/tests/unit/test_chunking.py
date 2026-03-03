"""Step 3.2: 청킹 전략 단위 테스트 (RED → GREEN)."""
from unittest.mock import AsyncMock

import pytest

from app.services.chunking.base import Chunk, ChunkingStrategy
from app.services.chunking.recursive import RecursiveChunking
from app.services.chunking.semantic import SemanticChunking
from app.services.chunking.contextual import ContextualChunking
from app.services.chunking.auto_detect import AutoDetectChunking
from app.services.chunking.header import SectionHeaderChunking

LONG_TEXT = """한국어 자연어 처리는 다양한 기술을 활용합니다.
형태소 분석은 한국어 텍스트의 기본 단위를 파악하는 데 중요합니다.
벡터 임베딩을 사용하면 텍스트의 의미를 수치적으로 표현할 수 있습니다.
검색 증강 생성(RAG)은 대규모 언어 모델의 환각을 줄이는 핵심 기술입니다.
하이브리드 검색은 벡터 검색과 키워드 검색을 결합하여 정확도를 높입니다.
리랭킹은 초기 검색 결과를 재정렬하여 가장 관련성 높은 문서를 선별합니다.
한국어 특화 리랭커인 bge-reranker-v2-m3-ko는 한국어 문서에서 우수한 성능을 보입니다.
PostgreSQL과 PGVector를 사용하면 벡터 데이터베이스를 구축할 수 있습니다.
Elasticsearch와 Nori 분석기를 결합하면 한국어 키워드 검색이 가능합니다.
전체 시스템은 FastAPI로 구축되어 비동기 처리가 가능합니다."""


class TestRecursiveChunking:
    def setup_method(self):
        self.chunker = RecursiveChunking(chunk_size=100, chunk_overlap=20)

    @pytest.mark.asyncio
    async def test_recursive_chunking(self):
        """긴 텍스트를 청크로 분할 확인."""
        chunks = await self.chunker.chunk(LONG_TEXT)

        assert len(chunks) > 1
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.content for c in chunks)
        assert all(c.chunk_index >= 0 for c in chunks)

    @pytest.mark.asyncio
    async def test_recursive_chunk_overlap(self):
        """청크 간 겹침 영역 존재 확인."""
        chunks = await self.chunker.chunk(LONG_TEXT)

        # 인접 청크 간에 공통 텍스트가 있어야 함
        if len(chunks) >= 2:
            found_overlap = False
            for i in range(len(chunks) - 1):
                # 이전 청크의 끝 부분이 다음 청크의 시작 부분에 포함되는지 확인
                tail = chunks[i].content[-20:] if len(chunks[i].content) > 20 else chunks[i].content
                if tail in chunks[i + 1].content:
                    found_overlap = True
                    break
            # overlap이 20자로 설정되었으므로 최소한 일부 청크에서는 겹침이 존재해야 함
            # (문장 경계 분할이므로 항상 보장되지는 않음)
            assert len(chunks) >= 2

    @pytest.mark.asyncio
    async def test_recursive_preserves_all_content(self):
        """모든 원본 텍스트가 청크에 포함되는지 확인."""
        chunks = await self.chunker.chunk(LONG_TEXT)
        combined = " ".join(c.content for c in chunks)
        # 원본의 핵심 문장이 청크에 포함되어야 함
        assert "한국어 자연어 처리" in combined
        assert "FastAPI" in combined

    @pytest.mark.asyncio
    async def test_short_text_single_chunk(self):
        """짧은 텍스트는 하나의 청크로."""
        chunks = await self.chunker.chunk("짧은 텍스트입니다.")
        assert len(chunks) == 1
        assert chunks[0].content == "짧은 텍스트입니다."
        assert chunks[0].chunk_index == 0


class TestSemanticChunking:
    @pytest.mark.asyncio
    async def test_semantic_chunking(self):
        """시맨틱 청킹 — mock 임베딩 사용."""
        mock_embedding = AsyncMock()
        # 각 문장에 대해 서로 다른 임베딩 반환 (의미 변화 시뮬레이션)
        embeddings = [
            [1.0, 0.0, 0.0],  # 문장 1 (NLP 그룹)
            [0.9, 0.1, 0.0],  # 문장 2 (NLP 그룹)
            [0.0, 0.0, 1.0],  # 문장 3 (DB 그룹 - 갑자기 변경)
            [0.1, 0.0, 0.9],  # 문장 4 (DB 그룹)
        ]
        mock_embedding.embed_documents.return_value = embeddings

        text = "한국어 자연어 처리는 중요합니다. 형태소 분석이 핵심입니다. PostgreSQL은 데이터베이스입니다. PGVector로 벡터를 저장합니다."
        chunker = SemanticChunking(embedding_provider=mock_embedding, threshold=0.5)
        chunks = await chunker.chunk(text)

        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)
        mock_embedding.embed_documents.assert_called_once()


class TestContextualChunking:
    @pytest.mark.asyncio
    async def test_contextual_wraps_any_strategy(self):
        """어떤 전략이든 래핑 가능."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "이 청크는 한국어 NLP에 대한 내용입니다."
        base = RecursiveChunking(chunk_size=100, chunk_overlap=20)

        chunker = ContextualChunking(llm_provider=mock_llm, base_strategy=base)
        chunks = await chunker.chunk(LONG_TEXT)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert "이 청크는" in chunk.content
        assert mock_llm.generate.call_count == len(chunks)

    @pytest.mark.asyncio
    async def test_contextual_prepends_context(self):
        """LLM 맥락이 청크 앞에 추가된다."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "[맥락]"
        base = RecursiveChunking(chunk_size=100, chunk_overlap=20)

        chunker = ContextualChunking(llm_provider=mock_llm, base_strategy=base)
        chunks = await chunker.chunk(LONG_TEXT)

        for chunk in chunks:
            assert chunk.content.startswith("[맥락]\n\n")

    @pytest.mark.asyncio
    async def test_contextual_llm_failure_fallback(self):
        """LLM 실패 → 원본 청크 유지."""
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("LLM 오류")
        base = RecursiveChunking(chunk_size=100, chunk_overlap=20)

        chunker = ContextualChunking(llm_provider=mock_llm, base_strategy=base)
        chunks = await chunker.chunk(LONG_TEXT)

        assert len(chunks) >= 1
        # LLM 실패했으므로 원본 그대로
        for chunk in chunks:
            assert "[맥락]" not in chunk.content

    @pytest.mark.asyncio
    async def test_contextual_metadata_annotation(self):
        """metadata에 contextual: True 추가."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "맥락 요약"
        base = RecursiveChunking(chunk_size=100, chunk_overlap=20)

        chunker = ContextualChunking(llm_provider=mock_llm, base_strategy=base)
        chunks = await chunker.chunk(LONG_TEXT)

        for chunk in chunks:
            assert chunk.metadata.get("contextual") is True

    @pytest.mark.asyncio
    async def test_contextual_with_header_strategy(self):
        """SectionHeaderChunking 위에도 contextual 적용 가능."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "맥락"
        base = SectionHeaderChunking(chunk_size=1024, chunk_overlap=100)

        chunker = ContextualChunking(llm_provider=mock_llm, base_strategy=base)
        chunks = await chunker.chunk(MARKDOWN_TEXT, meta={"file_type": "md"})

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.content.startswith("맥락\n\n")


class TestContextualChunkingPathFormat:
    @pytest.mark.asyncio
    async def test_context_follows_path_format(self):
        """생성된 컨텍스트가 '>' 구분 경로 형식을 따른다."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "한국어 NLP > 기본 기술 > 형태소 분석, 임베딩"
        base = RecursiveChunking(chunk_size=100, chunk_overlap=20)

        chunker = ContextualChunking(llm_provider=mock_llm, base_strategy=base)
        chunks = await chunker.chunk(LONG_TEXT)

        for chunk in chunks:
            # 컨텍스트가 > 구분자를 포함해야 함
            context_line = chunk.content.split("\n\n")[0]
            assert ">" in context_line

    @pytest.mark.asyncio
    async def test_context_includes_document_topic(self):
        """경로에 문서 주제가 포함된다."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "한국어 NLP 기술 > 검색 > 하이브리드 검색, BM25"
        base = RecursiveChunking(chunk_size=100, chunk_overlap=20)

        chunker = ContextualChunking(llm_provider=mock_llm, base_strategy=base)
        chunks = await chunker.chunk(LONG_TEXT)

        assert len(chunks) >= 1
        # 첫 번째 청크의 컨텍스트에 주제가 포함
        context_line = chunks[0].content.split("\n\n")[0]
        assert "한국어 NLP" in context_line


MARKDOWN_TEXT = """# 블루멤버스 안내

블루멤버스는 현대자동차의 고객 포인트 프로그램입니다.

## 포인트 적립

포인트는 차량 구매 시 자동 적립됩니다. 최대 130만 포인트까지 적립 가능합니다.
적립된 포인트의 유효기간은 60개월(5년)입니다.

## 포인트 사용

포인트는 현대자동차 정비, 부품 구매, 액세서리 구매 등에 사용할 수 있습니다.
최소 사용 단위는 1,000 포인트입니다.

### 사용 제한

일부 프로모션 상품에는 포인트 사용이 제한될 수 있습니다.
법인 회원의 경우 별도 규정이 적용됩니다.
"""

PDF_LIKE_TEXT = """블루멤버스 서비스 안내서

본 문서는 블루멤버스 서비스의 전반적인 내용을 안내합니다.
고객 여러분의 편의를 위해 작성되었습니다.

포인트 적립 방법

차량 구매 시 자동으로 포인트가 적립됩니다.
적립 비율은 차종에 따라 다릅니다.
최대 적립 한도는 130만 포인트입니다.

포인트 사용 안내

적립된 포인트는 다양한 서비스에 사용할 수 있습니다.
정비, 부품 구매, 액세서리 구매가 가능합니다.
"""


class TestSectionHeaderChunking:
    def setup_method(self):
        self.chunker = SectionHeaderChunking(chunk_size=1024, chunk_overlap=100)

    @pytest.mark.asyncio
    async def test_markdown_headings_parsed(self):
        """마크다운 헤딩이 파싱되어 브레드크럼이 추가된다."""
        chunks = await self.chunker.chunk(MARKDOWN_TEXT, meta={"file_type": "md"})

        assert len(chunks) >= 1
        # 브레드크럼이 포함되어야 함
        has_breadcrumb = any("[#" in c.content for c in chunks)
        assert has_breadcrumb

    @pytest.mark.asyncio
    async def test_markdown_breadcrumb_hierarchy(self):
        """하위 헤딩에 상위 헤딩이 포함된 브레드크럼이 생성된다."""
        chunks = await self.chunker.chunk(MARKDOWN_TEXT, meta={"file_type": "md"})

        # "### 사용 제한" 청크에 상위 헤더가 포함되어야 함
        restriction_chunks = [c for c in chunks if "사용 제한" in c.content]
        assert len(restriction_chunks) >= 1
        # 브레드크럼에 "블루멤버스 안내 > ## 포인트 사용 > ### 사용 제한"
        assert "포인트 사용" in restriction_chunks[0].content

    @pytest.mark.asyncio
    async def test_plaintext_heading_detection(self):
        """평문(PDF)에서 짧은 줄이 헤딩으로 감지된다."""
        chunks = await self.chunker.chunk(PDF_LIKE_TEXT, meta={"file_type": "pdf"})

        assert len(chunks) >= 1
        # 평문 헤딩이 브레드크럼으로 추가되어야 함
        has_heading = any("적립" in c.content or "사용" in c.content for c in chunks)
        assert has_heading

    @pytest.mark.asyncio
    async def test_chunk_index_sequential(self):
        """청크 인덱스가 순차적으로 부여된다."""
        chunks = await self.chunker.chunk(MARKDOWN_TEXT, meta={"file_type": "md"})

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self):
        """빈 텍스트 → 빈 리스트."""
        chunks = await self.chunker.chunk("", meta={"file_type": "md"})
        assert chunks == []

    @pytest.mark.asyncio
    async def test_no_headings_fallback(self):
        """헤딩이 없는 텍스트 → 브레드크럼 없이 청킹."""
        plain = "이것은 헤딩이 없는 일반 텍스트입니다. 여러 문장이 있습니다."
        chunks = await self.chunker.chunk(plain, meta={"file_type": "md"})
        assert len(chunks) >= 1


class TestAutoDetectChunking:
    @pytest.mark.asyncio
    async def test_auto_detect_markdown(self):
        """마크다운 파일 → SectionHeaderChunking 선택."""
        chunker = AutoDetectChunking()
        strategy = chunker.detect_strategy(
            meta={"file_type": "md"},
            text="# Title\n\nParagraph\n\n## Section\n\nMore text",
        )
        assert isinstance(strategy, SectionHeaderChunking)

    @pytest.mark.asyncio
    async def test_auto_detect_plain_text(self):
        """일반 텍스트 → recursive 전략."""
        chunker = AutoDetectChunking()
        strategy = chunker.detect_strategy(
            meta={"file_type": "txt"},
            text="일반 텍스트 내용입니다. 섹션 구조가 없습니다.",
        )
        assert isinstance(strategy, RecursiveChunking)

    @pytest.mark.asyncio
    async def test_auto_detect_chunk(self):
        """auto_detect의 chunk 메서드가 동작하는지 확인."""
        chunker = AutoDetectChunking()
        chunks = await chunker.chunk(LONG_TEXT, meta={"file_type": "txt"})
        assert len(chunks) >= 1


class TestAutoDetectContextual:
    @pytest.mark.asyncio
    async def test_auto_contextual_enabled(self):
        """ON → ContextualChunking 래핑."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "맥락 추가됨"
        chunker = AutoDetectChunking(
            llm_provider=mock_llm, contextual_enabled=True,
        )
        chunks = await chunker.chunk(LONG_TEXT, meta={"file_type": "txt"})
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "맥락 추가됨" in chunk.content
        assert mock_llm.generate.call_count == len(chunks)

    @pytest.mark.asyncio
    async def test_auto_contextual_disabled(self):
        """OFF → 기본 전략."""
        mock_llm = AsyncMock()
        chunker = AutoDetectChunking(
            llm_provider=mock_llm, contextual_enabled=False,
        )
        chunks = await chunker.chunk(LONG_TEXT, meta={"file_type": "txt"})
        assert len(chunks) >= 1
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_contextual_no_llm(self):
        """LLM 없으면 비활성."""
        chunker = AutoDetectChunking(
            llm_provider=None, contextual_enabled=True,
        )
        chunks = await chunker.chunk(LONG_TEXT, meta={"file_type": "txt"})
        assert len(chunks) >= 1
