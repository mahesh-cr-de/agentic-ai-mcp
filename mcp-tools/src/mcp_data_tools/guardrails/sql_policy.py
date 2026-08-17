"""Coarse, dependency-free read-only SQL enforcement.

Important:
    This is a deliberately conservative lexical guard, **not** a full SQL
    parser. It is designed to fail safe (reject anything it cannot
    confidently classify as read-only) rather than to be a complete SQL
    grammar. It is one layer of defense; production deployments should
    additionally run queries under a service account/role that only has
    read (``roles/bigquery.dataViewer``-equivalent) permissions on the
    allow-listed tables, so that even a guard bypass cannot mutate data.
    See ``docs/SECURITY.md`` for the full defense-in-depth discussion.
"""

from __future__ import annotations

import re

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")

_ALLOWED_LEADING_KEYWORDS = {"SELECT", "WITH"}

_FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXEC",
    "EXECUTE",
    "REPLACE",
}


def _strip_noise(sql: str) -> str:
    """Remove comments and string literal contents to avoid false matches."""
    without_block_comments = _BLOCK_COMMENT.sub(" ", sql)
    without_line_comments = _LINE_COMMENT.sub(" ", without_block_comments)
    without_strings = _STRING_LITERAL.sub("''", without_line_comments)
    return without_strings


def is_read_only(sql: str) -> tuple[bool, str]:
    """Classify a SQL statement as read-only or not.

    Args:
        sql: The raw SQL text to classify.

    Returns:
        A ``(is_read_only, reason)`` tuple. When ``is_read_only`` is
        ``False``, ``reason`` explains which check failed.

    Example:
        >>> is_read_only("SELECT * FROM t")[0]
        True
        >>> is_read_only("DELETE FROM t WHERE 1=1")[0]
        False
        >>> is_read_only("-- DROP TABLE t\\nSELECT 1")[0]
        True
    """
    cleaned = _strip_noise(sql).strip()
    if not cleaned:
        return False, "Empty query"

    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cleaned.upper())
    if not tokens:
        return False, "No SQL tokens found"

    leading = tokens[0]
    if leading not in _ALLOWED_LEADING_KEYWORDS:
        return False, f"Statement must start with SELECT or WITH, found {leading!r}"

    found_forbidden = [tok for tok in tokens if tok in _FORBIDDEN_KEYWORDS]
    if found_forbidden:
        return False, f"Forbidden keyword(s) present: {sorted(set(found_forbidden))}"

    if ";" in cleaned.rstrip(";"):
        return False, "Multiple statements are not permitted"

    return True, "Statement is read-only"


__all__ = ["is_read_only"]
