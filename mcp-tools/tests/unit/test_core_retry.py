"""Tests for mcp_data_tools.core.retry."""

from __future__ import annotations

import pytest

from mcp_data_tools.core.exceptions import RetryExhaustedError
from mcp_data_tools.core.retry import RetryPolicy, timeout_seconds, with_retry, with_retry_async


def _fast_policy(**overrides) -> RetryPolicy:
    return RetryPolicy(base_delay_seconds=0, max_delay_seconds=0, jitter_seconds=0, **overrides)


def test_succeeds_without_retry() -> None:
    calls = {"n": 0}

    @with_retry(_fast_policy())
    def fn() -> str:
        calls["n"] += 1
        return "ok"

    assert fn() == "ok"
    assert calls["n"] == 1


def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    @with_retry(_fast_policy(max_attempts=3))
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_exhausts_and_raises() -> None:
    @with_retry(_fast_policy(max_attempts=2))
    def always_fails() -> None:
        raise ConnectionError("nope")

    with pytest.raises(RetryExhaustedError) as exc_info:
        always_fails()
    assert exc_info.value.attempts == 2
    assert isinstance(exc_info.value.last_error, ConnectionError)


def test_non_retryable_exception_propagates_immediately() -> None:
    calls = {"n": 0}

    @with_retry(RetryPolicy(max_attempts=5, retryable_exceptions=(ConnectionError,)))
    def raises_value_error() -> None:
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        raises_value_error()
    assert calls["n"] == 1


@pytest.mark.anyio
async def test_async_retry_then_succeeds() -> None:
    calls = {"n": 0}

    @with_retry_async(_fast_policy(max_attempts=2))
    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("boom")
        return "ok"

    assert await flaky() == "ok"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_retry_policy_rejects_invalid_max_attempts() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)


def test_delay_for_attempt_is_capped() -> None:
    policy = RetryPolicy(base_delay_seconds=100, max_delay_seconds=1, jitter_seconds=0)
    assert policy.delay_for_attempt(5) == 1


def test_timeout_seconds_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        timeout_seconds(0, name="my_op")
    assert timeout_seconds(5, name="my_op") == 5
