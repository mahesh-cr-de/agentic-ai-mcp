"""Glob-style allow-list matching for resource identifiers.

Patterns use ``fnmatch``-style wildcards (``*`` matches any run of
characters, including ``.``) so a single entry like
``analytics.gold_*.customer_*`` can allow-list an entire family of
BigQuery tables without enumerating every one.
"""

from __future__ import annotations

from fnmatch import fnmatch


def matches_any(value: str, patterns: list[str]) -> bool:
    """Check whether ``value`` matches at least one allow-list pattern.

    Args:
        value: The identifier to check (e.g. ``proj.sales.orders``).
        patterns: Glob-style patterns. An empty list denies everything —
            callers must explicitly allow-list resources.

    Returns:
        ``True`` if ``value`` matches any pattern, ``False`` otherwise
        (including when ``patterns`` is empty).

    Example:
        >>> matches_any("proj.sales.orders", ["proj.sales.*"])
        True
        >>> matches_any("proj.hr.salaries", ["proj.sales.*"])
        False
        >>> matches_any("proj.sales.orders", [])
        False
    """
    return any(fnmatch(value, pattern) for pattern in patterns)


__all__ = ["matches_any"]
