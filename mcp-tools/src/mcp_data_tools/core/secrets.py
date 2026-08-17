"""Secret resolution abstraction.

Credentials are never embedded in configuration files. Instead, config
files reference a :class:`SecretRef`, which is resolved lazily (only when
an adapter actually needs the value) against one of several backends:
plain environment variables, Google Secret Manager, or Azure Key Vault.

This keeps the same YAML config portable across a laptop (``env`` source),
CI (``env`` source backed by masked secrets), and production (a real
secrets manager) without any code changes.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator

from mcp_data_tools.core.exceptions import ConfigurationError


class SecretSource(StrEnum):
    """Supported secret backends."""

    ENV = "env"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    AZURE_KEY_VAULT = "azure_key_vault"


class SecretRef(BaseModel):
    """A pointer to a secret value, not the value itself.

    Attributes:
        source: Which backend to resolve the secret from.
        key: For ``env``, the environment variable name. For
            ``gcp_secret_manager``, the secret resource id
            (``projects/*/secrets/*/versions/*``). For
            ``azure_key_vault``, the secret name.
        vault_url: Required when ``source`` is ``azure_key_vault``; the
            Key Vault URI (e.g. ``https://my-vault.vault.azure.net``).

    Example:
        >>> ref = SecretRef(source=SecretSource.ENV, key="AIRFLOW_TOKEN")
        >>> import os
        >>> os.environ["AIRFLOW_TOKEN"] = "s3cr3t"
        >>> ref.resolve()
        's3cr3t'
    """

    source: SecretSource
    key: str
    vault_url: str | None = None

    @model_validator(mode="after")
    def _validate_vault_url(self) -> SecretRef:
        if self.source is SecretSource.AZURE_KEY_VAULT and not self.vault_url:
            raise ValueError("vault_url is required when source=azure_key_vault")
        return self

    def resolve(self) -> str:
        """Fetch the secret's current value.

        Returns:
            The resolved secret value as a string.

        Raises:
            ConfigurationError: If the secret cannot be resolved (missing
                environment variable, missing optional dependency, or a
                backend-reported error).
        """
        if self.source is SecretSource.ENV:
            return self._resolve_env()
        if self.source is SecretSource.GCP_SECRET_MANAGER:
            return self._resolve_gcp()
        if self.source is SecretSource.AZURE_KEY_VAULT:
            return self._resolve_azure()
        raise ConfigurationError(f"Unsupported secret source: {self.source}")  # pragma: no cover

    def _resolve_env(self) -> str:
        value = os.environ.get(self.key)
        if value is None:
            raise ConfigurationError(
                f"Environment variable {self.key!r} is not set",
                details={"source": "env", "key": self.key},
            )
        return value

    def _resolve_gcp(self) -> str:
        try:
            from google.cloud import secretmanager  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - exercised via mock in tests
            raise ConfigurationError(
                "google-cloud-secret-manager is required to resolve "
                "gcp_secret_manager secrets; install the 'gcp' extra",
            ) from exc
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(name=self.key)
        return str(response.payload.data.decode("utf-8"))

    def _resolve_azure(self) -> str:
        try:
            from azure.identity import DefaultAzureCredential  # noqa: PLC0415
            from azure.keyvault.secrets import SecretClient  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - exercised via mock in tests
            raise ConfigurationError(
                "azure-keyvault-secrets is required to resolve "
                "azure_key_vault secrets; install the 'azure' extra",
            ) from exc
        client = SecretClient(vault_url=self.vault_url, credential=DefaultAzureCredential())
        secret = client.get_secret(self.key)
        return str(secret.value)


def coerce_secret_ref(value: Any) -> SecretRef | None:
    """Normalize loosely-typed config input into a :class:`SecretRef`.

    Accepts ``None``, an existing :class:`SecretRef`, or a mapping such as
    ``{"source": "env", "key": "FOO"}``.

    Args:
        value: Raw value from parsed YAML/JSON.

    Returns:
        A :class:`SecretRef`, or ``None`` if ``value`` is ``None``.
    """
    if value is None or isinstance(value, SecretRef):
        return value
    if isinstance(value, dict):
        return SecretRef.model_validate(value)
    raise ConfigurationError(f"Cannot coerce {value!r} into a SecretRef")


__all__ = ["SecretRef", "SecretSource", "coerce_secret_ref"]
