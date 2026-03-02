"""Step 4.9: Haystack 파이프라인 동적 구성.

RAGSettings 에 따라 검색 파이프라인(vector / keyword / hybrid)을
동적으로 빌드한다.  각 모드별 컴포넌트 그래프:

  vector:   query_embedder → vector_retriever → [ranker →] prompt_builder → llm
  keyword:  keyword_retriever → [ranker →] prompt_builder → llm
  hybrid:   query_embedder → vector_retriever ─┐
                                                ├→ joiner → [ranker →] prompt_builder → llm
                        keyword_retriever ──────┘

[ranker] 는 reranking_enabled=True 일 때만 포함된다.
"""
from __future__ import annotations

from haystack import Pipeline
from haystack.components.builders import PromptBuilder
from haystack.components.joiners import DocumentJoiner
from haystack.components.rankers import TransformersSimilarityRanker
from haystack.components.embedders import OpenAITextEmbedder
from haystack.utils import Secret
from haystack.components.generators import OpenAIGenerator
from haystack_integrations.components.retrievers.elasticsearch import (
    ElasticsearchBM25Retriever,
)
from haystack_integrations.components.retrievers.pgvector import (
    PgvectorEmbeddingRetriever,
)
from haystack_integrations.document_stores.elasticsearch import (
    ElasticsearchDocumentStore,
)
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore

from app.config import RAGSettings, Settings

# ---------------------------------------------------------------------------
# RAG 프롬프트 템플릿 (Jinja2)
# ---------------------------------------------------------------------------

_RAG_PROMPT_TEMPLATE = """\
당신은 사내 문서를 기반으로 질문에 답변하는 AI 어시스턴트입니다.
숫자, 퍼센트, 기간, 금액, 고유명사는 문서 원문을 글자 그대로 사용하세요. 절대 바꿔 말하지 마세요.
목록이나 항목을 나열할 때는 문서에 기재된 모든 항목을 빠짐없이 포함하세요.

{% for doc in documents %}
--- 문서 {{ loop.index }} ---
{{ doc.content }}
{% endfor %}

질문: {{ query }}

위 문서만을 근거로 답변하세요. 숫자와 고유명사는 원문 그대로 사용하고, 하나도 빠뜨리지 마세요.
문서에 답이 없으면 '제공된 문서에서 해당 정보를 찾을 수 없습니다'라고 답하세요.
"""


def _build_pgvector_connection_string(database_url: str) -> str:
    """SQLAlchemy asyncpg URL → psycopg 동기 URL 로 변환.

    PgvectorDocumentStore 는 psycopg(동기) 드라이버를 사용하므로
    'postgresql+asyncpg://' → 'postgresql://' 로 치환한다.
    """
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


def build_search_pipeline(
    rag_settings: RAGSettings,
    env_settings: Settings,
) -> Pipeline:
    """RAG 설정에 따라 검색 파이프라인을 동적으로 구성.

    Note: This constructs a Haystack Pipeline object. The actual pipeline
    execution is handled by HybridSearchOrchestrator, not directly through
    Haystack's run method. This function serves as a declarative pipeline
    definition that can be inspected and validated.

    Args:
        rag_settings: 런타임 RAG 설정 (search_mode, reranking 등).
        env_settings: 환경 변수 기반 인프라 설정 (URL 등).

    Returns:
        구성된 Haystack Pipeline 인스턴스.
    """
    pipeline = Pipeline()
    mode = rag_settings.search_mode

    # ------------------------------------------------------------------
    # 1. Retriever 계층: search_mode 에 따라 컴포넌트 배치
    # ------------------------------------------------------------------
    needs_vector = mode in ("vector", "hybrid")
    needs_keyword = mode in ("keyword", "hybrid")
    needs_joiner = mode == "hybrid"

    if needs_vector:
        # Query Embedder — OpenAI embedding (dimensions=1536 for HNSW compatibility)
        embedder = OpenAITextEmbedder(
            model=rag_settings.embedding_model,
            api_key=Secret.from_env_var("OPENAI_API_KEY"),
            dimensions=1536,
        )
        pipeline.add_component("query_embedder", embedder)

        # PGVector Document Store + Retriever
        pg_store = PgvectorDocumentStore(
            connection_string=_build_pgvector_connection_string(
                env_settings.database_url,
            ),
        )
        vector_retriever = PgvectorEmbeddingRetriever(
            document_store=pg_store,
            top_k=rag_settings.retriever_top_k,
        )
        pipeline.add_component("vector_retriever", vector_retriever)

        # 연결: embedder → retriever
        pipeline.connect(
            "query_embedder.embedding", "vector_retriever.query_embedding"
        )

    if needs_keyword:
        # Elasticsearch Document Store + BM25 Retriever
        es_store = ElasticsearchDocumentStore(
            hosts=env_settings.elasticsearch_url,
        )
        keyword_retriever = ElasticsearchBM25Retriever(
            document_store=es_store,
            top_k=rag_settings.retriever_top_k,
        )
        pipeline.add_component("keyword_retriever", keyword_retriever)

    if needs_joiner:
        # DocumentJoiner: 두 retriever 결과를 합침
        joiner = DocumentJoiner(
            join_mode="reciprocal_rank_fusion",
            top_k=rag_settings.retriever_top_k,
        )
        pipeline.add_component("joiner", joiner)

        # 연결: 양쪽 retriever → joiner
        pipeline.connect("vector_retriever.documents", "joiner")
        pipeline.connect("keyword_retriever.documents", "joiner")

    # ------------------------------------------------------------------
    # 2. 리랭킹 계층 (선택)
    # ------------------------------------------------------------------
    # retriever 출력 → (ranker →) prompt_builder 연결을 결정
    if rag_settings.reranking_enabled:
        ranker = TransformersSimilarityRanker(
            model=rag_settings.reranker_model,
            top_k=rag_settings.reranker_top_k,
        )
        pipeline.add_component("ranker", ranker)

    # ------------------------------------------------------------------
    # 3. 답변 생성 계층
    # ------------------------------------------------------------------
    prompt_builder = PromptBuilder(
        template=_RAG_PROMPT_TEMPLATE,
        required_variables=["query", "documents"],
    )
    pipeline.add_component("prompt_builder", prompt_builder)

    llm = OpenAIGenerator(
        model=rag_settings.llm_model,
        api_key=Secret.from_env_var("OPENAI_API_KEY"),
    )
    pipeline.add_component("llm", llm)

    # prompt_builder → llm
    pipeline.connect("prompt_builder.prompt", "llm.prompt")

    # ------------------------------------------------------------------
    # 4. Retriever 출력 → (ranker →) prompt_builder 연결
    # ------------------------------------------------------------------
    # retriever 단일 출력 노드를 결정
    if needs_joiner:
        retriever_output = "joiner.documents"
    elif needs_vector:
        retriever_output = "vector_retriever.documents"
    else:
        retriever_output = "keyword_retriever.documents"

    if rag_settings.reranking_enabled:
        pipeline.connect(retriever_output, "ranker.documents")
        pipeline.connect("ranker.documents", "prompt_builder.documents")
    else:
        pipeline.connect(retriever_output, "prompt_builder.documents")

    return pipeline
