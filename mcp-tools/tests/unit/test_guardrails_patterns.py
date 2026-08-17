"""Tests for mcp_data_tools.guardrails.patterns."""

from mcp_data_tools.guardrails.patterns import matches_any


def test_matches_exact() -> None:
    assert matches_any("proj.sales.orders", ["proj.sales.orders"])


def test_matches_wildcard_segment() -> None:
    assert matches_any("proj.sales.orders", ["proj.sales.*"])
    assert matches_any("proj.sales.customers", ["proj.sales.*"])


def test_no_match_different_dataset() -> None:
    assert not matches_any("proj.hr.salaries", ["proj.sales.*"])


def test_empty_pattern_list_denies_everything() -> None:
    assert not matches_any("anything", [])


def test_matches_any_of_multiple_patterns() -> None:
    patterns = ["proj.hr.*", "proj.sales.*"]
    assert matches_any("proj.sales.orders", patterns)
    assert matches_any("proj.hr.employees", patterns)
    assert not matches_any("proj.finance.ledger", patterns)
