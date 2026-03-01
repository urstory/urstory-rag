"""Langfuse 모니터링 통합.

Langfuse SDK를 래핑하여 트레이싱/스코어링 기능을 제공한다.
키 미설정 시 모든 호출이 no-op으로 동작한다.
"""
from __future__ import annotations

from typing import Any

from langfuse import Langfuse


class _NoOp:
    """어떤 메서드 호출이든 자기 자신을 반환하는 no-op 객체."""

    def __getattr__(self, name: str) -> Any:
        return self._noop

    def _noop(self, *args: Any, **kwargs: Any) -> "_NoOp":
        return self


_NOOP = _NoOp()


class LangfuseMonitor:
    """Langfuse SDK 래퍼.

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
            self._langfuse = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
        else:
            self._langfuse = None

    def create_trace(self, name: str, input: str) -> Any:
        if not self.enabled:
            return _NOOP
        return self._langfuse.trace(name=name, input=input)

    def create_span(self, trace: Any, name: str) -> Any:
        if not self.enabled:
            return _NOOP
        return trace.span(name=name)

    def create_generation(
        self, trace: Any, name: str, model: str, input: dict,
    ) -> Any:
        if not self.enabled:
            return _NOOP
        return trace.generation(name=name, model=model, input=input)

    def score(self, trace_id: str, name: str, value: float) -> None:
        if not self.enabled:
            return
        self._langfuse.score(trace_id=trace_id, name=name, value=value)

    def flush(self) -> None:
        if not self.enabled:
            return
        self._langfuse.flush()
