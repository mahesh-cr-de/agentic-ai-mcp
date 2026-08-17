"""Retry and timeout primitives.

A small, dependency-free retry decorator with exponential backoff and
jitter. Kept in-house (rather than pulling in a third-party retry library)
so the retry/backoff/timeout behavior of every adapter is auditable in one
place and has zero transitive dependency risk.
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import ParamSpec, TypeVar

from mcp_data_tools.core.exceptions import RetryExhaustedError
from mcp_data_tools.core.logging import get_logger

_LOGGER = get_logger(__name__)

_P = ParamSpec("_P")
_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Describes how an operation should be retried on transient failure.

    Attributes:
        max_attempts: Total number of attempts, including the first. Must
            be at least 1.
        base_delay_seconds: Delay before the second attempt. Subsequent
            delays grow exponentially (``base_delay_seconds * 2 ** n``).
        max_delay_seconds: Upper bound on any single backoff delay.
        jitter_seconds: Maximum random jitter added to each delay, to
            avoid thundering-herd retries across concurrent callers.
        retryable_exceptions: Exception types that should trigger a retry.
            Any other exception propagates immediately.

    Example:
        >>> policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.01)
        >>> policy.delay_for_attempt(0) >= 0
        True
    """

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.1
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be >= 0")

    def delay_for_attempt(self, attempt_index: int) -> float:
        """Compute the backoff delay before retrying.

        Args:
            attempt_index: Zero-based index of the attempt that just
                failed (0 for the first attempt).

        Returns:
            Delay in seconds, capped at ``max_delay_seconds`` plus jitter.
        """
        exponential = self.base_delay_seconds * (2**attempt_index)
        capped = min(exponential, self.max_delay_seconds)
        return float(capped + random.uniform(0, self.jitter_seconds))


def with_retry(
    policy: RetryPolicy | None = None,
) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]:
    """Decorate a synchronous callable with retry-with-backoff behavior.

    Args:
        policy: Retry configuration. Defaults to a conservative 3-attempt
            policy if omitted.

    Returns:
        A decorator that wraps the target function.

    Raises:
        RetryExhaustedError: If every attempt raises a retryable exception.

    Example:
        >>> calls = {"n": 0}
        >>> @with_retry(RetryPolicy(max_attempts=2, base_delay_seconds=0))
        ... def flaky() -> str:
        ...     calls["n"] += 1
        ...     if calls["n"] < 2:
        ...         raise ConnectionError("boom")
        ...     return "ok"
        >>> flaky()
        'ok'
    """
    effective_policy = policy or RetryPolicy()

    def decorator(func: Callable[_P, _T]) -> Callable[_P, _T]:
        @functools.wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            last_error: Exception | None = None
            for attempt in range(effective_policy.max_attempts):
                try:
                    return func(*args, **kwargs)
                except effective_policy.retryable_exceptions as exc:
                    last_error = exc
                    is_last = attempt == effective_policy.max_attempts - 1
                    _LOGGER.warning(
                        "retryable operation failed",
                        extra={
                            "function": func.__qualname__,
                            "attempt": attempt + 1,
                            "max_attempts": effective_policy.max_attempts,
                            "error": str(exc),
                            "will_retry": not is_last,
                        },
                    )
                    if is_last:
                        break
                    time.sleep(effective_policy.delay_for_attempt(attempt))
            if last_error is None:  # pragma: no cover - defensive; loop always sets it
                raise RuntimeError(
                    f"{func.__qualname__} retry loop exited without a recorded error "
                    "(this indicates a bug in with_retry itself, not the wrapped call)"
                )
            raise RetryExhaustedError(
                f"{func.__qualname__} failed after " f"{effective_policy.max_attempts} attempt(s)",
                attempts=effective_policy.max_attempts,
                last_error=last_error,
            ) from last_error

        return wrapper

    return decorator


def with_retry_async(
    policy: RetryPolicy | None = None,
) -> Callable[[Callable[_P, Awaitable[_T]]], Callable[_P, Awaitable[_T]]]:
    """Async counterpart of :func:`with_retry`.

    Args:
        policy: Retry configuration. Defaults to a conservative 3-attempt
            policy if omitted.

    Returns:
        A decorator that wraps the target coroutine function.

    Raises:
        RetryExhaustedError: If every attempt raises a retryable exception.
    """
    effective_policy = policy or RetryPolicy()

    def decorator(
        func: Callable[_P, Awaitable[_T]],
    ) -> Callable[_P, Awaitable[_T]]:
        @functools.wraps(func)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            last_error: Exception | None = None
            for attempt in range(effective_policy.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except effective_policy.retryable_exceptions as exc:
                    last_error = exc
                    is_last = attempt == effective_policy.max_attempts - 1
                    _LOGGER.warning(
                        "retryable async operation failed",
                        extra={
                            "function": func.__qualname__,
                            "attempt": attempt + 1,
                            "max_attempts": effective_policy.max_attempts,
                            "error": str(exc),
                            "will_retry": not is_last,
                        },
                    )
                    if is_last:
                        break
                    await asyncio.sleep(effective_policy.delay_for_attempt(attempt))
            if last_error is None:  # pragma: no cover - defensive; loop always sets it
                raise RuntimeError(
                    f"{func.__qualname__} retry loop exited without a recorded error "
                    "(this indicates a bug in with_retry itself, not the wrapped call)"
                )
            raise RetryExhaustedError(
                f"{func.__qualname__} failed after " f"{effective_policy.max_attempts} attempt(s)",
                attempts=effective_policy.max_attempts,
                last_error=last_error,
            ) from last_error

        return wrapper

    return decorator


def timeout_seconds(value: float, *, name: str = "operation") -> float:
    """Validate a timeout value.

    Args:
        value: Requested timeout in seconds.
        name: Human-readable name used in the error message.

    Returns:
        The validated timeout, unchanged.

    Raises:
        ValueError: If ``value`` is not strictly positive.
    """
    if value <= 0:
        raise ValueError(f"timeout for {name!r} must be > 0, got {value}")
    return value


__all__ = [
    "RetryPolicy",
    "timeout_seconds",
    "with_retry",
    "with_retry_async",
]
