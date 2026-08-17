# Configuration reference

Configuration is a single YAML (or JSON) file, validated by
`mcp_data_tools.core.config.AppConfig` (Pydantic). Validate any config
file without starting the server:

```bash
mcp-data-tools validate-config --config configs/full-example.yaml
```

See `configs/default.yaml` (minimal, zero tools registered) and
`configs/full-example.yaml` (every backend + guardrail knob) for complete
examples.

## `server`

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | `mcp-data-tools` | Advertised to MCP clients. |
| `instructions` | string | (a default sentence) | Shown to MCP clients describing the server. |
| `log_level` | string | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`. |
| `enabled_tools` | list[string] | `[]` (all) | Restrict to a subset of the tools implied by the configured backends. |

## `audit`

| Field | Type | Default | Notes |
|---|---|---|---|
| `kind` | string | `local_jsonl` | `local_jsonl`, `stdout`, or `bigquery` (not yet implemented — see CHANGELOG). |
| `path` | string | `audit-log.jsonl` | File path, when `kind: local_jsonl`. |
| `table` | string \| null | `null` | Required when `kind: bigquery`. |
| `fail_closed` | bool | `true` | Deny operations rather than proceed unaudited if the sink write fails. See `SECURITY.md`. |

## `guardrails`

| Field | Type | Default | Notes |
|---|---|---|---|
| `allowed_table_patterns` | list[string] | `[]` | Glob (`fnmatch`) patterns over `project.dataset.table`. Empty = nothing allowed. |
| `allowed_bucket_patterns` | list[string] | `[]` | Glob patterns over bucket names. |
| `allowed_dag_patterns` | list[string] | `[]` | Glob patterns over Airflow DAG ids. |
| `max_bytes_billed` | int | `10_000_000_000` (10 GB) | Hard ceiling per query, enforced by the backend itself. |
| `max_rows_returned` | int | `10_000` | Hard ceiling on rows returned to the caller. |
| `require_dry_run` | bool | `true` | Reserved for future backends where dry run is optional; BigQuery always dry-runs today. |
| `read_only` | bool | `true` | Disable only if you deeply understand `SECURITY.md`'s discussion of the SQL-safety trade-offs — not recommended. |

## `bigquery` / `gcs` / `airflow`

Omitting a section entirely means its tools are not registered at all
(the server simply won't advertise `bigquery_query`, `gcs_inspect_object`,
etc. to MCP clients). See `SECURITY.md` for the secret-reference (`source:
env` / `gcp_secret_manager` / `azure_key_vault`) pattern used by
`bigquery.credentials`, `gcs.credentials`, and `airflow.auth_token`.

| Section | Required fields | Notes |
|---|---|---|
| `bigquery` | `project_id` | `location` defaults to `US`; `credentials` optional (falls back to ADC). |
| `gcs` | `project_id` | `credentials` optional (falls back to ADC). |
| `airflow` | `base_url`, `auth_token` | `timeout_seconds` default `10`; `verify_tls` default `true`. |

## Environment variable interpolation

Non-secret scalar values may reference `${ENV:VAR_NAME}`, expanded before
YAML/JSON parsing:

```yaml
bigquery:
  project_id: ${ENV:GCP_PROJECT_ID}
```

This is separate from — and not a substitute for — the `SecretRef`
mechanism used for credentials; see `SECURITY.md` for why secrets always
go through `SecretRef` instead.

## CLI overrides

`mcp-data-tools serve --config <path> --log-level DEBUG` overrides
`server.log_level` for a single run without editing the file.
