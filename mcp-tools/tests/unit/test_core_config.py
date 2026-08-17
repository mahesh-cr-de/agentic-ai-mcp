"""Tests for mcp_data_tools.core.config."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_data_tools.core.config import (
    AirflowConnectionConfig,
    AppConfig,
    AuditConfig,
    GuardrailConfig,
)
from mcp_data_tools.core.exceptions import ConfigurationError
from mcp_data_tools.core.secrets import SecretRef, SecretSource


def test_default_config_is_valid() -> None:
    config = AppConfig()
    assert config.server.name == "mcp-data-tools"
    assert config.guardrails.read_only is True
    assert config.audit.kind == "local_jsonl"


def test_guardrail_config_rejects_non_positive_limits() -> None:
    with pytest.raises(ValidationError):
        GuardrailConfig(max_bytes_billed=0)
    with pytest.raises(ValidationError):
        GuardrailConfig(max_rows_returned=-1)


def test_bigquery_audit_requires_table() -> None:
    with pytest.raises(ValidationError):
        AppConfig(audit=AuditConfig(kind="bigquery"))


def test_from_file_yaml(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
server:
  name: my-server
guardrails:
  allowed_table_patterns:
    - "proj.sales.*"
  max_bytes_billed: 5000
""",
        encoding="utf-8",
    )
    config = AppConfig.from_file(path)
    assert config.server.name == "my-server"
    assert config.guardrails.allowed_table_patterns == ["proj.sales.*"]
    assert config.guardrails.max_bytes_billed == 5000


def test_from_file_json(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"server": {"name": "json-server"}}', encoding="utf-8")
    config = AppConfig.from_file(path)
    assert config.server.name == "json-server"


def test_from_file_missing_raises(tmp_path) -> None:
    with pytest.raises(ConfigurationError):
        AppConfig.from_file(tmp_path / "does-not-exist.yaml")


def test_from_file_malformed_yaml_raises(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("server: [unterminated", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        AppConfig.from_file(path)


def test_env_var_interpolation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MDT_PROJECT", "my-gcp-project")
    path = tmp_path / "config.yaml"
    path.write_text(
        "bigquery:\n  project_id: ${ENV:MDT_PROJECT}\n",
        encoding="utf-8",
    )
    config = AppConfig.from_file(path)
    assert config.bigquery.project_id == "my-gcp-project"


def test_env_var_interpolation_missing_raises(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("bigquery:\n  project_id: ${ENV:DOES_NOT_EXIST_VAR}\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        AppConfig.from_file(path)


def test_secret_ref_env_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("MY_TOKEN", "abc123")
    ref = SecretRef(source=SecretSource.ENV, key="MY_TOKEN")
    assert ref.resolve() == "abc123"


def test_secret_ref_env_missing_raises() -> None:
    ref = SecretRef(source=SecretSource.ENV, key="TOTALLY_UNSET_VAR_XYZ")
    with pytest.raises(ConfigurationError):
        ref.resolve()


def test_secret_ref_azure_requires_vault_url() -> None:
    with pytest.raises(ValidationError):
        SecretRef(source=SecretSource.AZURE_KEY_VAULT, key="secret-name")


def test_airflow_config_strips_trailing_slash() -> None:
    cfg = AirflowConnectionConfig(
        base_url="https://airflow.example.com/",
        auth_token=SecretRef(source=SecretSource.ENV, key="X"),
    )
    assert cfg.base_url == "https://airflow.example.com"
