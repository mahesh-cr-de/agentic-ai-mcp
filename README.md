# agentic-ai-mcp

Agentic AI experiments and MCP (Model Context Protocol) tools for building AI-driven data workflows.

This repository has two parts:

## [`mcp-tools/`](mcp-tools/) — mcp-data-tools

A governed MCP server that gives an LLM agent guarded access to real
data-platform operations: querying BigQuery, inspecting GCS, triggering
Airflow DAGs, and running data-quality checks. Every tool call is
dry-run estimated, checked against an allow-list, capped by a cost/row
ceiling, and written to an audit trail before it reaches a real backend.

See [`mcp-tools/README.md`](mcp-tools/README.md) for the full write-up,
architecture, and quick start.

## [`experiments/`](experiments/) — Agent Plans

Implementation plans for agentic AI solutions across core Azure data
engineering workflows:

- [ADF Agent Plan](experiments/plans/01-adf-agent-plan.md) — design, troubleshoot, and optimize Azure Data Factory pipelines
- [Databricks Agent Plan](experiments/plans/02-databricks-agent-plan.md) — notebook development, workflow orchestration, Delta Lake operations
- [PySpark Agent Plan](experiments/plans/03-pyspark-agent-plan.md) — author, review, and optimize PySpark code
- [Python ETL Agent Plan](experiments/plans/04-python-etl-agent-plan.md) — accelerate Python-based ETL development
- [Data Quality Agent Plan](experiments/plans/05-data-quality-agent-plan.md) — evaluate data quality rules and detect anomalies
- [PR Review Agent Plan](experiments/plans/06-pr-review-agent-plan.md) — review data engineering pull requests before merge

See [`experiments/README.md`](experiments/README.md) for the recommended delivery order.
