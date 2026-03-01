"""이상 탐지 알림.

주기적으로 할루시네이션 비율, 에러율 등을 확인하고 이상 시 알림을 생성한다.
Celery Beat로 주기적 실행 (1시간 간격).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)

# 임계값
HALLUCINATION_THRESHOLD = 0.7
ERROR_RATE_THRESHOLD = 0.10  # 10%


class AlertChecker:
    """이상 탐지 체커.

    Langfuse에서 최근 메트릭을 조회하여 임계값 초과 시 알림을 생성한다.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_all_checks(self) -> list[dict[str, Any]]:
        """모든 이상 탐지 체크를 실행한다."""
        alerts: list[dict[str, Any]] = []
        alerts.extend(await self.check_hallucination_rate())
        alerts.extend(await self.check_error_rate())
        return alerts

    async def check_hallucination_rate(self) -> list[dict[str, Any]]:
        """최근 1시간 할루시네이션 스코어 평균을 확인한다."""
        scores = await self._get_recent_hallucination_scores()
        if not scores:
            return []

        avg = sum(scores) / len(scores)
        if avg < HALLUCINATION_THRESHOLD:
            alert = {
                "type": "hallucination_rate",
                "message": f"할루시네이션 비율 증가: 최근 1시간 평균 {avg:.2f} (임계값: {HALLUCINATION_THRESHOLD})",
                "severity": "warning",
                "value": round(avg, 4),
                "threshold": HALLUCINATION_THRESHOLD,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.warning(alert["message"])
            return [alert]

        return []

    async def check_error_rate(self) -> list[dict[str, Any]]:
        """최근 1시간 에러율을 확인한다."""
        error_rate = await self._get_recent_error_rate()

        if error_rate > ERROR_RATE_THRESHOLD:
            alert = {
                "type": "error_rate",
                "message": f"에러율 증가: 최근 1시간 {error_rate:.1%} (임계값: {ERROR_RATE_THRESHOLD:.0%})",
                "severity": "warning",
                "value": round(error_rate, 4),
                "threshold": ERROR_RATE_THRESHOLD,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.warning(alert["message"])
            return [alert]

        return []

    async def _get_recent_hallucination_scores(self) -> list[float]:
        """Langfuse에서 최근 1시간 할루시네이션 점수를 조회한다."""
        env = get_settings()
        if not env.langfuse_public_key or not env.langfuse_secret_key:
            return []

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{env.langfuse_host}/api/public/scores",
                    params={"name": "hallucination", "limit": 100},
                    auth=(env.langfuse_public_key, env.langfuse_secret_key),
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json().get("data", [])
                return [s["value"] for s in data if "value" in s]
        except Exception as e:
            logger.warning("Failed to fetch hallucination scores: %s", e)
            return []

    async def _get_recent_error_rate(self) -> float:
        """Langfuse에서 최근 1시간 에러율을 조회한다."""
        env = get_settings()
        if not env.langfuse_public_key or not env.langfuse_secret_key:
            return 0.0

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{env.langfuse_host}/api/public/traces",
                    params={"limit": 100},
                    auth=(env.langfuse_public_key, env.langfuse_secret_key),
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    return 0.0
                data = resp.json().get("data", [])
                if not data:
                    return 0.0
                errors = sum(1 for t in data if t.get("status") == "ERROR")
                return errors / len(data)
        except Exception as e:
            logger.warning("Failed to fetch error rate: %s", e)
            return 0.0
