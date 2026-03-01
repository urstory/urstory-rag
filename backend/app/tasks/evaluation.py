"""평가 Celery 태스크."""
from app.worker import celery_app


@celery_app.task(name="run_evaluation")
def run_evaluation_task(dataset_id: str, run_id: str):
    """RAGAS 평가를 비동기로 실행한다.

    Step 6.5에서 본격 구현.
    """
    import asyncio
    from app.services.evaluation.ragas import RAGASEvaluator

    evaluator = RAGASEvaluator()
    asyncio.run(evaluator.evaluate(dataset_id, run_id))
