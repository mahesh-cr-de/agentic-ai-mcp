"""Runnable walkthrough: guarded BigQuery access with zero cloud credentials.

This uses the in-memory mock adapters (the same ones the test suite uses)
so it runs anywhere with just the base dependencies installed — no GCP
project, no Airflow instance, no network access required.

Run it with:

    python examples/quickstart.py
"""

from __future__ import annotations

import json

from mcp_data_tools.adapters.audit import InMemoryAuditSink
from mcp_data_tools.adapters.bigquery import InMemoryQueryEngine
from mcp_data_tools.core.config import AppConfig
from mcp_data_tools.core.exceptions import GuardrailViolationError
from mcp_data_tools.testing import ScriptedQueryEngine, single_row_result
from mcp_data_tools.tools.data_quality.tool import DataQualityCheckTool
from mcp_data_tools.tools.registry import ToolRegistry


def main() -> None:
    # 1. A realistic-looking guardrail policy: only the "gold" sales tables
    #    are allow-listed, and no single query may bill more than 1 MB.
    config = AppConfig.from_mapping(
        {
            "guardrails": {
                "allowed_table_patterns": ["acme.analytics_gold.*"],
                "max_bytes_billed": 1_000_000,
                "max_rows_returned": 50,
            }
        }
    )

    # 2. Seed a fake BigQuery with some data — this stands in for a real
    #    `BigQueryQueryEngine` (see server/factory.py for how that's wired
    #    from config in a real deployment).
    engine = InMemoryQueryEngine()
    engine.seed_table(
        "acme.analytics_gold.orders",
        [{"order_id": i, "amount": float(i) * 9.99, "region": "US" if i % 2 else "EU"} for i in range(100)],
    )
    # Deliberately NOT allow-listed, to demonstrate the guardrail denying it below.
    engine.seed_table("acme.hr_raw.salaries", [{"employee_id": 1, "salary": 250_000}])

    audit_sink = InMemoryAuditSink()
    registry = ToolRegistry(config, audit_sink=audit_sink, query_engine=engine)

    print("Registered tools:", sorted(registry.tools))
    print()

    # 3. A normal, allowed call.
    query_tool = registry.get("bigquery_query")
    result = query_tool.execute(
        {"sql": "SELECT * FROM `acme.analytics_gold.orders`", "row_limit": 3},
        actor="demo-agent",
    )
    print("Allowed query result:")
    print(json.dumps(result, indent=2))
    print()

    # 4. A data-quality check against the same allow-listed table.
    #
    #    Note: real BigQuery computes the aggregate (COUNT(*), the null
    #    rate, etc.) server-side, so `InMemoryQueryEngine` — which just
    #    echoes raw seeded rows verbatim rather than evaluating SQL — isn't
    #    the right double here. `ScriptedQueryEngine` lets us say exactly
    #    what the (simulated) aggregate query would return, the same way
    #    `tests/unit/test_tools_data_quality.py` does.
    dq_engine = ScriptedQueryEngine()
    row_count_estimate, row_count_result = single_row_result(
        {"metric": 100}, table="acme.analytics_gold.orders"
    )
    uniqueness_estimate, uniqueness_result = single_row_result(
        {"metric": 0}, table="acme.analytics_gold.orders"
    )
    dq_engine.estimates.extend([row_count_estimate, uniqueness_estimate])
    dq_engine.results.extend([row_count_result, uniqueness_result])

    dq_tool = DataQualityCheckTool(registry.guardrails, dq_engine, config.guardrails)
    report = dq_tool.execute(
        {
            "table": "acme.analytics_gold.orders",
            "checks": [
                {"type": "row_count", "min_rows": 10},
                {"type": "uniqueness", "column": "order_id"},
            ],
        },
        actor="demo-agent",
    )
    print("Data quality report:")
    print(json.dumps(report, indent=2))
    print()

    # 5. An attempt to query a non-allow-listed table — denied *before* the
    #    (mock) backend is ever called; see docs/SECURITY.md.
    try:
        query_tool.execute({"sql": "SELECT * FROM `acme.hr_raw.salaries`"}, actor="demo-agent")
    except GuardrailViolationError as exc:
        print(f"Denied as expected: {exc.message}")
    print()

    # 6. Every decision — allowed or denied — is in the audit trail.
    print(f"Audit trail has {len(audit_sink.read_recent())} entries:")
    for event in audit_sink.read_recent():
        print(f"  [{event.decision:7s}] {event.tool_name}: {event.reason}")


if __name__ == "__main__":
    main()
