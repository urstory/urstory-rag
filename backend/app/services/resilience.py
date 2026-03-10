"""Circuit Breaker + Retry 복원력 모듈.

외부 서비스(OpenAI, Elasticsearch) 호출에 대한 재시도와
Circuit Breaker 패턴을 제공한다.

- 재시도: Exponential Backoff + jitter
- Circuit Breaker: CLOSED → OPEN → HALF_OPEN → CLOSED
"""
from __future__ import annotations

import asyncio
import enum
import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Sequence, Type

from app.exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Circuit Breaker 패턴 구현.

    Args:
        name: 서킷 브레이커 이름 (예: "openai", "elasticsearch")
        failure_threshold: 연속 실패 횟수 임계값 (기본 5)
        recovery_timeout: OPEN → HALF_OPEN 전이 대기 시간 (초, 기본 30)
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time: float | None = None
        self._half_open_allowed = False

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_allowed = True
        return self._state

    def allow_request(self) -> bool:
        """요청 허용 여부를 반환한다."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN and self._half_open_allowed:
            self._half_open_allowed = False
            return True
        return False

    def record_success(self) -> None:
        """성공 기록. failure_count 초기화 및 CLOSED 전이."""
        self.failure_count = 0
        self._state = CircuitState.CLOSED
        self._half_open_allowed = False

    def record_failure(self) -> None:
        """실패 기록. threshold 도달 시 OPEN 전이."""
        self.failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # HALF_OPEN에서 실패 → 다시 OPEN
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit Breaker [%s] HALF_OPEN → OPEN (복구 실패)",
                self.name,
            )
        elif self.failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit Breaker [%s] OPEN (연속 %d회 실패)",
                self.name, self.failure_count,
            )

    def stats(self) -> dict[str, Any]:
        """현재 상태 통계를 반환한다."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


def with_retry(
    max_retries: int = 3,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable:
    """비동기 함수에 Exponential Backoff + jitter 재시도를 적용하는 데코레이터.

    Args:
        max_retries: 최대 재시도 횟수 (초기 호출 미포함)
        retryable_exceptions: 재시도 대상 예외 튜플
        base_delay: 초기 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        circuit_breaker: Circuit Breaker 연동 (선택)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Circuit Breaker 확인
            if circuit_breaker and not circuit_breaker.allow_request():
                raise CircuitBreakerOpenError(
                    f"Circuit Breaker [{circuit_breaker.name}] OPEN — "
                    f"서비스 일시 중단 ({circuit_breaker.recovery_timeout}초 후 복구 시도)"
                )

            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    return result
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Exponential Backoff + jitter
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        jitter = delay * random.uniform(0.5, 1.0)
                        logger.warning(
                            "재시도 %d/%d — %s (%.1f초 후 재시도)",
                            attempt + 1, max_retries,
                            str(e)[:100], jitter,
                        )
                        await asyncio.sleep(jitter)
                    else:
                        if circuit_breaker:
                            circuit_breaker.record_failure()
                except Exception:
                    # 재시도 불가능한 예외 → 즉시 전파
                    if circuit_breaker:
                        circuit_breaker.record_failure()
                    raise

            raise last_exception  # type: ignore[misc]

        return wrapper
    return decorator
