"""Tests for mcp_data_tools.guardrails.sql_policy."""

import pytest

from mcp_data_tools.guardrails.sql_policy import is_read_only


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM t",
        "select * from t",
        "WITH cte AS (SELECT 1) SELECT * FROM cte",
        "SELECT * FROM t -- trailing comment",
        "/* leading comment */ SELECT * FROM t",
    ],
)
def test_read_only_statements_pass(sql: str) -> None:
    ok, _ = is_read_only(sql)
    assert ok is True


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM t WHERE 1=1",
        "UPDATE t SET x = 1",
        "INSERT INTO t VALUES (1)",
        "DROP TABLE t",
        "CREATE TABLE t (x INT)",
        "ALTER TABLE t ADD COLUMN y INT",
        "TRUNCATE TABLE t",
        "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN DELETE",
        "CALL my_proc()",
    ],
)
def test_write_statements_are_rejected(sql: str) -> None:
    ok, reason = is_read_only(sql)
    assert ok is False
    assert reason


def test_forbidden_keyword_in_comment_does_not_leak_through() -> None:
    """A DROP mentioned only in a comment must not make a SELECT look unsafe."""
    ok, _ = is_read_only("-- DROP TABLE t\nSELECT 1")
    assert ok is True


def test_forbidden_keyword_in_string_literal_does_not_leak_through() -> None:
    ok, _ = is_read_only("SELECT 'please do not DELETE this' AS note")
    assert ok is True


def test_multiple_statements_rejected() -> None:
    ok, _reason = is_read_only("SELECT 1; DELETE FROM t")
    assert ok is False


def test_empty_query_rejected() -> None:
    ok, reason = is_read_only("   ")
    assert ok is False
    assert "Empty" in reason
