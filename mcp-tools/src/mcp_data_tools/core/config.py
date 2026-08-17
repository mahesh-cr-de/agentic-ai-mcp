"""Application configuration models.

Configuration is loaded from YAML (or JSON/TOML, see
:func:`AppConfig.from_file`) and validated eagerly through Pydantic so that
a malformed guardrail policy or connection profile fails fast at startup
rather than mid-query. CLI arguments and environment variables can
override individual fields; see ``docs/CONFIGURATION.md``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from mcp_data_tools.core.exceptions import ConfigurationError
from mcp_data_tools.core.secrets import SecretRef

_ENV_VAR_PATTERN = re.compile(r"\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}")


def _interpolate_env(raw: str) -> str:
    """Substitute ``${ENV:VAR}`` placeholders in a raw config string.

    This is intentionally limited to non-secret, low-sensitivity values
    (hostnames, project ids, feature flags). Credentials must always be
    expressed as a :class:`~mcp_data_tools.core.secrets.SecretRef` so their
    resolution is explicit and auditable, never silently inlined here.

    Args:
        raw: Raw file contents before YAML/JSON parsing.

    Returns:
        The contents with ``${ENV:VAR}`` placeholders replaced.

    Raises:
        ConfigurationError: If a referenced environment variable is unset.
    """

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name)
        if value is None:
            raise ConfigurationError(
                f"Config references undefined environment variable {var_name!r}"
            )
        return value

    return _ENV_VAR_PATTERN.sub(_replace, raw)


class BigQueryConnectionConfig(BaseModel):
    """Connection settings for the BigQuery adapter.

    Attributes:
        project_id: GCP project that owns the billing for queries.
        location: BigQuery job location (e.g. ``US``, ``EU``, ``asia-south1``).
        credentials: Optional explicit service-account credential secret.
            When omitted, Application Default Credentials are used.
    """

    project_id: str
    location: str = "US"
    credentials: SecretRef | None = None

    model_config = {"extra": "forbid"}


class GcsConnectionConfig(BaseModel):
    """Connection settings for the GCS adapter.

    Attributes:
        project_id: GCP project used for request billing/quota.
        credentials: Optional explicit service-account credential secret.
    """

    project_id: str
    credentials: SecretRef | None = None

    model_config = {"extra": "forbid"}


class AirflowConnectionConfig(BaseModel):
    """Connection settings for the Airflow REST API adapter.

    Attributes:
        base_url: Airflow webserver base URL, e.g.
            ``https://airflow.internal.example.com``.
        auth_token: Secret reference to a bearer token used for the
            Airflow stable REST API.
        timeout_seconds: Per-request HTTP timeout.
        verify_tls: Whether to verify TLS certificates. Only ever set to
            ``False`` for local/dev environments; the config loader emits
            a warning-level log line when it is.
    """

    base_url: str
    auth_token: SecretRef
    timeout_seconds: float = 10.0
    verify_tls: bool = True

    model_config = {"extra": "forbid"}

    @field_validator("base_url")
    @classmethod
    def _no_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


class AuditSinkKind(str):
    """String enum-like constants for audit sink selection (kept as str for YAML ergonomics)."""

    LOCAL_JSONL = "local_jsonl"
    STDOUT = "stdout"
    BIGQUERY = "bigquery"


class AuditConfig(BaseModel):
    """Configuration for the audit trail sink.

    Attributes:
        kind: One of ``local_jsonl``, ``stdout``, or ``bigquery``.
        path: File path for ``local_jsonl``.
        table: Fully-qualified ``project.dataset.table`` for ``bigquery``.
        fail_closed: If ``True`` (default), a tool call is rejected when
            the audit event cannot be written, so no ungoverned action is
            ever silently unlogged. See ``docs/SECURITY.md``.
    """

    kind: str = AuditSinkKind.LOCAL_JSONL
    path: str = "audit-log.jsonl"
    table: str | None = None
    fail_closed: bool = True

    model_config = {"extra": "forbid"}

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        allowed = {AuditSinkKind.LOCAL_JSONL, AuditSinkKind.STDOUT, AuditSinkKind.BIGQUERY}
        if value not in allowed:
            raise ValueError(f"audit.kind must be one of {sorted(allowed)}, got {value!r}")
        return value


class GuardrailConfig(BaseModel):
    """Policy limits enforced before any backend call executes.

    Attributes:
        allowed_table_patterns: Glob-style ``project.dataset.table``
            patterns (``*`` wildcard supported per segment) that BigQuery
            queries and data-quality checks are restricted to.
        allowed_bucket_patterns: Glob-style bucket-name patterns GCS
            operations are restricted to.
        allowed_dag_patterns: Glob-style DAG-id patterns Airflow
            operations are restricted to.
        max_bytes_billed: Hard ceiling on BigQuery ``maximum_bytes_billed``.
        max_rows_returned: Hard ceiling on rows returned to the caller.
        require_dry_run: If ``True``, every query must pass a dry-run cost
            estimate before real execution.
        read_only: If ``True``, only ``SELECT``/``WITH`` statements are
            permitted; DDL/DML is rejected outright.
    """

    allowed_table_patterns: list[str] = Field(default_factory=list)
    allowed_bucket_patterns: list[str] = Field(default_factory=list)
    allowed_dag_patterns: list[str] = Field(default_factory=list)
    max_bytes_billed: int = 10_000_000_000  # 10 GB
    max_rows_returned: int = 10_000
    require_dry_run: bool = True
    read_only: bool = True

    model_config = {"extra": "forbid"}

    @field_validator("max_bytes_billed", "max_rows_returned")
    @classmethod
    def _must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value


class ServerConfig(BaseModel):
    """Top-level MCP server metadata.

    Attributes:
        name: Server name advertised over MCP.
        instructions: Short instructions shown to MCP clients describing
            what this server offers and how it enforces guardrails.
        log_level: One of ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``,
            ``CRITICAL``.
        enabled_tools: Explicit allow-list of tool names to register. An
            empty list means "all tools implemented by this package".
    """

    name: str = "mcp-data-tools"
    instructions: str = "Governed data-platform tools. Every call is policy-checked and audited."
    log_level: str = "INFO"
    enabled_tools: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class AppConfig(BaseModel):
    """Root configuration object assembled from a config file.

    Attributes:
        server: MCP server metadata and feature flags.
        guardrails: Policy limits enforced by
            :class:`~mcp_data_tools.guardrails.engine.GuardrailEngine`.
        audit: Audit trail sink configuration.
        bigquery: BigQuery connection profile, if the tool is enabled.
        gcs: GCS connection profile, if the tool is enabled.
        airflow: Airflow connection profile, if the tool is enabled.
    """

    server: ServerConfig = Field(default_factory=ServerConfig)
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    bigquery: BigQueryConnectionConfig | None = None
    gcs: GcsConnectionConfig | None = None
    airflow: AirflowConnectionConfig | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_audit_table(self) -> AppConfig:
        if self.audit.kind == AuditSinkKind.BIGQUERY and not self.audit.table:
            raise ValueError("audit.table is required when audit.kind=bigquery")
        return self

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> AppConfig:
        """Build an :class:`AppConfig` from an already-parsed mapping.

        Args:
            data: Parsed configuration (e.g. from ``yaml.safe_load``).

        Returns:
            A validated :class:`AppConfig`.

        Raises:
            ConfigurationError: If validation fails.
        """
        from pydantic import ValidationError  # noqa: PLC0415

        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid configuration: {exc}") from exc

    @classmethod
    def from_file(cls, path: str | Path) -> AppConfig:
        """Load configuration from a YAML or JSON file on disk.

        Args:
            path: Path to a ``.yaml``, ``.yml``, or ``.json`` file.
                ``${ENV:VAR}`` placeholders are expanded before parsing.

        Returns:
            A validated :class:`AppConfig`.

        Raises:
            ConfigurationError: If the file is missing, unparsable, or
                fails validation.

        Example:
            >>> from pathlib import Path
            >>> p = Path("/tmp/example-config.yaml")
            >>> _ = p.write_text("server:\\n  name: demo\\n")
            >>> AppConfig.from_file(p).server.name
            'demo'
        """
        file_path = Path(path)
        if not file_path.is_file():
            raise ConfigurationError(f"Config file not found: {file_path}")

        raw = file_path.read_text(encoding="utf-8")
        raw = _interpolate_env(raw)

        try:
            data = json.loads(raw) if file_path.suffix == ".json" else yaml.safe_load(raw) or {}
        except (yaml.YAMLError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Failed to parse config file {file_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigurationError(
                f"Config file {file_path} must contain a mapping at the top level"
            )
        return cls.from_mapping(data)


__all__ = [
    "AirflowConnectionConfig",
    "AppConfig",
    "AuditConfig",
    "AuditSinkKind",
    "BigQueryConnectionConfig",
    "GcsConnectionConfig",
    "GuardrailConfig",
    "ServerConfig",
]
