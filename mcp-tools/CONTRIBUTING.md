# Contributing to mcp-data-tools

Thanks for considering a contribution. This project follows a fairly
standard Python OSS workflow; the notes below cover the parts specific to
this codebase.

## Getting set up

```bash
git clone https://github.com/umamahesh-ade/mcp-data-tools.git
cd mcp-data-tools
python -m venv .venv && source .venv/bin/activate
make install-dev
```

`make install-dev` installs the package in editable mode with the `dev`,
`gcp`, and `azure` extras, and installs the pre-commit hooks.

## Before opening a pull request

```bash
make lint        # ruff check
make format      # ruff --fix + black
make typecheck   # mypy --strict
make security    # bandit
make test-cov    # pytest with coverage (fails under 85%)
```

All five must pass; CI runs the same checks (see `.github/workflows/`) and
will not merge otherwise.

## Architecture ground rules

This codebase is organized as a hexagonal architecture (see
`docs/ARCHITECTURE.md`). A few rules follow directly from that and are
enforced in review:

1. **Nothing under `tools/` or `guardrails/` imports a cloud SDK directly.**
   New backend integrations go through a port
   (`ports/interfaces.py`) with a real adapter and an in-memory mock
   adapter under `adapters/<backend>/`.
2. **Every tool handler goes through `GuardrailEngine` before touching an
   adapter.** No exceptions — if a new tool doesn't fit the
   allow-list/cost-ceiling/read-only model, the guardrail engine needs a
   new check, not a bypass.
3. **New adapters need both a real implementation and a mock.** Unit
   tests for the tool/guardrail layers must never require live cloud
   credentials or network access; that's what the mock is for.
4. **New data-quality checks are added as a `CheckStrategy`**, not as a
   branch inside `DataQualityCheckTool` (see `tools/data_quality/strategies.py`).

## Commit style

Conventional, imperative-mood commit subjects (`Add X`, `Fix Y`, `Refactor
Z`) are preferred but not strictly enforced. Reference the issue number
where relevant.

## Reporting bugs / requesting features

Open a GitHub issue. For bugs, include the config (with secrets redacted)
and the exact error/audit-log entry if available.

## Security issues

Do not open a public issue for a suspected vulnerability — see
[SECURITY.md](SECURITY.md) for the private disclosure process.
