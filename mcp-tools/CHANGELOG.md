# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- BigQuery-backed audit sink (`audit.kind: bigquery`) for centralized,
  queryable audit trails across a fleet of servers.
- Databricks/Delta Lake query-engine adapter implementing the same
  `QueryEnginePort`, alongside the BigQuery adapter.
- Row-level / column-level masking policy in the guardrail engine.

## [0.1.0] - 2026-07-07

### Added

- Initial release: MCP server exposing governed tools for BigQuery
  querying (`bigquery_query`, `bigquery_estimate_cost`), data-quality
  checks (`data_quality_check`: null_rate, uniqueness, freshness,
  row_count), GCS inspection (`gcs_inspect_object`, `gcs_list_objects`),
  and Airflow orchestration (`airflow_trigger_dag`,
  `airflow_get_dag_run_status`).
- `GuardrailEngine`: allow-list, read-only SQL enforcement, byte/row
  ceilings, and a two-phase (preflight + post-dry-run) authorization
  model for SQL queries.
- Audit trail with local JSONL, stdout, and pluggable sink support;
  fail-closed behavior when the audit sink is unavailable.
- Hexagonal architecture: `ports` interfaces with real + in-memory mock
  adapters for BigQuery, GCS, and Airflow.
- Secret resolution via environment variables, GCP Secret Manager, or
  Azure Key Vault (`core.secrets.SecretRef`).
- Full pytest suite (unit + an MCP-protocol integration test using the
  official `mcp` SDK in-memory client/server harness).
- Docker image, GitHub Actions CI (lint, test matrix, build, security
  scan, tagged release), and Sphinx-ready docstrings throughout.

[Unreleased]: https://github.com/umamahesh-ade/mcp-data-tools/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/umamahesh-ade/mcp-data-tools/releases/tag/v0.1.0
