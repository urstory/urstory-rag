"""Langfuse v3 모니터링 통합.

Langfuse SDK v3를 래핑하여 트레이싱/스코어링 기능을 제공한다.
키 미설정 시 모든 호출이 no-op으로 동작한다.
"""
from __future__ import annotations

import logging
from typing import Any

from langfuse import Langfuse

logger = logging.getLogger(__name__)


class _NoOp:
    """어떤 메서드 호출이든 자기 자신을 반환하는 no-op 객체."""

    def __getattr__(self, name: str) -> Any:
        return self._noop

    def _noop(self, *args: Any, **kwargs: Any) -> "_NoOp":
        return self


_NOOP = _NoOp()


class LangfuseMonitor:
    """Langfuse SDK v3 래퍼.

    public_key/secret_key가 모두 설정되면 실제 Langfuse 인스턴스를 생성하고,
    하나라도 없으면 모든 호출이 no-op으로 동작한다.
    """

    def __init__(
        self,
        public_key: str | None,
        secret_key: str | None,
        host: str = "http://localhost:3100",
    ) -> None:
        self.enabled = bool(public_key and secret_key)
        if self.enabled:
            try:
                self._langfuse = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
            except Exception as e:
                logger.warning("Langfuse 초기화 실패, no-op 모드: %s", e)
                self.enabled = False
                self._langfuse = None
        else:
            self._langfuse = None

    def create_trace(self, name: str, input: str) -> Any:
        if not self.enabled:
            return _NOOP
        try:
            span = self._langfuse.start_span(name=name, input=input)
            span.update_trace(name=name, input=input)
            return span
        except Exception as e:
            logger.warning("Langfuse create_trace 실패: %s", e)
            return _NOOP

    def create_span(self, trace: Any, name: str) -> Any:
        if not self.enabled:
            return _NOOP
        try:
            return trace.start_span(name)
        except Exception as e:
            logger.warning("Langfuse create_span 실패: %s", e)
            return _NOOP

    def create_generation(
        self, trace: Any, name: str, model: str, input: dict,
    ) -> Any:
        if not self.enabled:
            return _NOOP
        try:
            span = trace.start_span(name, input=input)
            span.update(model=model)
            return span
        except Exception as e:
            logger.warning("Langfuse create_generation 실패: %s", e)
            return _NOOP

    def score(self, trace_id: str, name: str, value: float) -> None:
        if not self.enabled:
            return
        try:
            self._langfuse.create_score(
                trace_id=trace_id, name=name, value=value,
            )
        except Exception as e:
            logger.warning("Langfuse score 실패: %s", e)

    def flush(self) -> None:
        if not self.enabled:
            return
        try:
            self._langfuse.flush()
        except Exception as e:
            logger.warning("Langfuse flush 실패: %s", e)
