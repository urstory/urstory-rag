"""RAGAS 평가 서비스.

RAGAS 0.2+ 클래스 기반 메트릭 API를 사용하여
RAG 파이프라인의 품질을 평가한다.
GPT-4o를 judge LLM으로 사용한다.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from ragas import evaluate
from ragas.dataset_schema import SingleTurnSample, EvaluationDataset as RagasDataset
from ragas.metrics import Faithfulness, ResponseRelevancy, LLMContextPrecisionWithReference, LLMContextRecall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import RAGSettings, get_settings
from app.models.database import EvaluationDataset, EvaluationRun

logger = logging.getLogger(__name__)


class RAGASEvaluator:
    """RAGAS 기반 RAG 평가 엔진.

    GPT-4o를 judge로 사용하여 4개 메트릭을 평가한다:
    - Faithfulness: 답변이 문서에 근거하는 정도
    - ResponseRelevancy: 답변이 질문에 관련된 정도
    - LLMContextPrecisionWithReference: 검색 문서의 관련성 순위 정확도
    - LLMContextRecall: 필요 정보가 검색된 비율
    """

    def _build_metrics(self):
        """RAGAS 메트릭을 초기화한다. GPT-4o judge + OpenAI 임베딩."""
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        evaluator_llm = LangchainLLMWrapper(
            ChatOpenAI(model="gpt-4o", temperature=0)
        )
        evaluator_embeddings = LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(model="text-embedding-3-small")
        )

        return [
            Faithfulness(llm=evaluator_llm),
            ResponseRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
            LLMContextPrecisionWithReference(llm=evaluator_llm),
            LLMContextRecall(llm=evaluator_llm),
        ]

    async def evaluate(self, dataset_id: str, run_id: str) -> None:
        """데이터셋에 대해 RAGAS 평가를 실행하고 결과를 DB에 저장한다."""
        async with self._get_db_session() as db:
            # 1. run 상태를 running으로 변경
            run = await self._load_run(db, run_id)
            run.status = "running"
            await db.commit()

            try:
                # 2. 데이터셋 로드
                dataset = await self._load_dataset(db, dataset_id)

                # 3. 현재 설정 스냅샷 저장
                settings = RAGSettings()
                run.settings_snapshot = settings.model_dump()
                await db.commit()

                # 4. 각 질문에 대해 RAG 파이프라인 실행
                samples = []
                per_question = []

                for item in dataset.items:
                    question = item["question"]
                    ground_truth = item["ground_truth"]

                    search_result = await self._run_search(question)

                    sample = SingleTurnSample(
                        user_input=question,
                        response=search_result["answer"],
                        retrieved_contexts=search_result["contexts"],
                        reference=ground_truth,
                    )
                    samples.append(sample)

                    per_question.append({
                        "question": question,
                        "answer": search_result["answer"],
                        "contexts": search_result["contexts"],
                        "ground_truth": ground_truth,
                    })

                # 5. RAGAS 평가 실행
                ragas_dataset = RagasDataset(samples=samples)
                metrics = self._build_metrics()
                result = evaluate(dataset=ragas_dataset, metrics=metrics)

                # 6. 결과 저장
                scores_df = result.to_pandas()
                avg_scores = scores_df.mean(numeric_only=True).to_dict()

                # NaN → None 변환
                run.metrics = {
                    k: round(v, 4) if v == v else None  # NaN check
                    for k, v in avg_scores.items()
                }
                run.per_question_results = per_question
                run.status = "completed"
                await db.commit()

            except Exception as e:
                logger.error("RAGAS evaluation failed: %s", e)
                run.status = "failed"
                await db.commit()

    @asynccontextmanager
    async def _get_db_session(self):
        """DB 세션을 생성한다. 테스트에서 mock 가능."""
        env = get_settings()
        engine = create_async_engine(env.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            yield session
        await engine.dispose()

    async def _load_dataset(self, db: AsyncSession, dataset_id: str) -> EvaluationDataset:
        result = await db.execute(
            select(EvaluationDataset).where(
                EvaluationDataset.id == uuid.UUID(dataset_id)
            )
        )
        return result.scalar_one()

    async def _load_run(self, db: AsyncSession, run_id: str) -> EvaluationRun:
        result = await db.execute(
            select(EvaluationRun).where(
                EvaluationRun.id == uuid.UUID(run_id)
            )
        )
        return result.scalar_one()

    async def _run_search(self, question: str) -> dict[str, Any]:
        """RAG 검색 파이프라인을 실행한다. 테스트에서 mock 가능."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:8000/api/search",
                json={"query": question, "generate_answer": True},
                timeout=60.0,
            )
            data = resp.json()
            return {
                "answer": data.get("answer", ""),
                "contexts": [r["content"] for r in data.get("results", [])],
            }
