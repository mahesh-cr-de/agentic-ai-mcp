"""Lightweight, best-effort table-reference extraction from raw SQL text.

Important:
    This is a regex heuristic, not a SQL parser. It exists purely as a
    **preflight** optimization: if it can confidently extract table names
    from ``FROM``/``JOIN`` clauses and none of them match the allow-list,
    the guardrail engine denies the request *before* ever calling the
    backend — saving the cost of a dry run and, more importantly, never
    giving an agent the chance to probe the existence/schema of a
    non-allow-listed table via a backend that happens to have broader
    IAM access than our policy intends.

    Because it is heuristic, a query this function fails to parse is
    **not** treated as denied — it is treated as "unknown", and the
    authoritative check runs after the backend's own dry run reports the
    tables it actually resolved. See
    :meth:`mcp_data_tools.guardrails.engine.GuardrailEngine.preflight_check_sql`
    and ``docs/SECURITY.md`` for the full two-phase rationale.
"""

from __future__ import annotations

import re

_TABLE_REF_PATTERN = re.compile(r"(?:FROM|JOIN)\s+`?([A-Za-z0-9_.-]+)`?", re.IGNORECASE)


def extract_table_references(sql: str) -> tuple[str, ...]:
    """Best-effort extraction of ``project.dataset.table`` references.

    Args:
        sql: Raw SQL text.

    Returns:
        A tuple of distinct candidate table identifiers, in first-seen
        order. Empty if none could be confidently extracted.

    Example:
        >>> extract_table_references("SELECT * FROM `p.d.t` JOIN p.d.u ON 1=1")
        ('p.d.t', 'p.d.u')
    """
    return tuple(dict.fromkeys(_TABLE_REF_PATTERN.findall(sql)))


__all__ = ["extract_table_references"]
