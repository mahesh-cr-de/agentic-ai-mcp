# Security

## Reporting a vulnerability

Please do **not** open a public GitHub issue for a suspected
vulnerability. Instead, email the maintainer (see the GitHub profile) or
use GitHub's private vulnerability reporting
(`Security` tab → `Report a vulnerability`) on this repository. Include a
minimal reproduction and the affected version. We aim to acknowledge
reports within 5 business days.

## Threat model

`mcp-data-tools` sits between an LLM agent (untrusted, in the sense that
its tool-call arguments are effectively attacker-controlled if the agent
is prompt-injected) and real data-platform backends that can read
sensitive data or trigger real workflows. The design goal is: **even a
fully compromised/prompt-injected agent, calling these tools with
arbitrary arguments, cannot exceed the policy configured by the operator.**

Everything below follows from that goal.

## Defense in depth for SQL execution

A single check is never trusted alone. `bigquery_query` and
`data_quality_check` both go through:

1. **Read-only lexical check** (`guardrails/sql_policy.py`): rejects
   anything that doesn't lexically look like a bare `SELECT`/`WITH`
   statement, stripping comments and string literals first so a forbidden
   keyword inside a comment or string can't leak through, and so a
   forbidden keyword hidden by a benign-looking comment can't sneak a real
   statement past the check either.
2. **Preflight table allow-list check** (`guardrails/sql_tables.py` +
   `GuardrailEngine.preflight_check_sql`): a regex-based, best-effort
   extraction of `FROM`/`JOIN` table references, checked against the
   allow-list *before* any backend call. This is a genuine defense layer,
   not just an optimization: without it, an agent could dry-run (and
   thereby discover the existence, schema, and approximate size of) any
   table the underlying service account can see, even one the operator
   never intended to allow-list. The preflight check only ever *denies* or
   defers — it never authoritatively allows, because regex table
   extraction is not a full SQL parser and a false "allow" would be a
   security bug.
3. **Authoritative post-dry-run check** (`GuardrailEngine.authorize_query`):
   after the backend's own dry run reports the tables it *actually*
   resolved (catching anything the regex preflight missed — views,
   wildcard tables, etc.), the same allow-list and byte-ceiling checks run
   again, this time against ground truth.
4. **Backend-enforced billing ceiling**: `max_bytes_billed` is passed
   through to the real query engine's own execution API, so even a
   dry-run estimate that was stale (e.g. the table grew between the
   estimate and the execute call) cannot result in an unbounded scan —
   the backend itself aborts.

**Known limitation:** the read-only and table-extraction checks are
lexical/regex heuristics, not a full SQL grammar. They are deliberately
conservative (fail closed on anything ambiguous), but a sufficiently
obscure SQL construct could theoretically evade the preflight extraction
(it would still be caught by the authoritative post-dry-run check, just
one layer later, after a dry run has already happened). **The only
airtight backstop is IAM**: the service account this server authenticates
as should itself only have read access
(`roles/bigquery.dataViewer`-equivalent) scoped to the datasets you intend
to allow-list. Treat the guardrail engine as the primary, fast, auditable
control plane and IAM as the backstop that makes a guardrail bug a
degraded-UX problem rather than a data-breach problem.

## Fail-closed audit trail

`AuditConfig.fail_closed` (default `true`) means: if the audit sink itself
cannot be written to (disk full, permissions issue, etc.), the guardrail
engine denies the operation rather than let an unaudited action through.
An ungoverned action that leaves no trace is treated as worse than a
denied request. Set `fail_closed: false` only in environments where audit
completeness is explicitly not a requirement (e.g. a local sandbox).

## Secrets

No credential is ever written into a config file. `bigquery.credentials`,
`gcs.credentials`, and `airflow.auth_token` are all
`core.secrets.SecretRef` values — a *pointer* to a secret (an environment
variable name, a GCP Secret Manager resource id, or an Azure Key Vault
secret name + vault URL), resolved only at the moment an adapter needs it.
This means:

- Config files are safe to commit (see `configs/full-example.yaml`).
- Swapping from local dev (`source: env`) to production (`source:
  gcp_secret_manager` or `source: azure_key_vault`) is a config change,
  not a code change.
- A leaked config file leaks *pointers*, not secrets.

## Least privilege for object storage

The GCS tools (`gcs_inspect_object`, `gcs_list_objects`) are metadata/list
only — no tool in this package can read an object's contents, write, or
delete. The intended IAM role for the service account is
`roles/storage.objectViewer`, scoped to the allow-listed buckets.

## Reporting audit gaps

If you find a way to make a tool call bypass `GuardrailEngine` entirely
(i.e. reach an adapter without an `authorize_*`/`preflight_*` call having
run first), that is a P0 security bug — please report it privately per
the process above rather than opening a public issue.
