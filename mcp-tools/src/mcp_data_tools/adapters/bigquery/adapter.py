"""Real BigQuery adapter, backed by ``google-cloud-bigquery``.

The client SDK is imported lazily inside :meth:`BigQueryQueryEngine.__init__`
so that this module can be imported (e.g. for type-checking or by the
factory in ``mcp_data_tools.server``) without the optional ``google-cloud-bigquery``
dependency installed, as long as the adapter is never actually
instantiated.
"""

from __future__ import annotations

from typing import Any

from mcp_data_tools.core.exceptions import BackendOperationError
from mcp_data_tools.core.logging import get_logger
from mcp_data_tools.core.retry import RetryPolicy, with_retry
from mcp_data_tools.ports.interfaces import QueryEnginePort
from mcp_data_tools.ports.models import QueryCostEstimate, QueryResult

_LOGGER = get_logger(__name__)

_DEFAULT_RETRY_POLICY = RetryPolicy(max_attempts=3, base_delay_seconds=1.0)


class BigQueryQueryEngine(QueryEnginePort):
    """:class:`QueryEnginePort` implementation backed by Google BigQuery.

    Attributes:
        project_id: GCP project used for billing and job attribution.
        location: BigQuery job location.

    Example:
        This adapter requires network access and real GCP credentials, so
        it is exercised in integration tests only; see
        ``tests/integration/test_bigquery_adapter_contract.py`` (skipped
        unless ``MCP_DATA_TOOLS_LIVE_TESTS=1``). Unit tests use
        :class:`~mcp_data_tools.adapters.bigquery.mock.InMemoryQueryEngine`
        instead, which implements the identical :class:`QueryEnginePort`
        contract.
    """

    def __init__(
        self,
        project_id: str,
        location: str = "US",
        *,
        credentials: Any | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        try:
            from google.cloud import bigquery  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - exercised without extra installed
            raise BackendOperationError(
                "google-cloud-bigquery is required for BigQueryQueryEngine; "
                "install the 'gcp' extra (pip install mcp-data-tools[gcp])"
            ) from exc

        self.project_id = project_id
        self.location = location
        self._retry_policy = retry_policy or _DEFAULT_RETRY_POLICY
        self._client = bigquery.Client(
            project=project_id,
            location=location,
            credentials=credentials,
        )
        self._bigquery = bigquery

    def estimate_cost(self, sql: str) -> QueryCostEstimate:
        """Dry-run the query and report the projected bytes scanned.

        Args:
            sql: The SQL statement to estimate.

        Returns:
            A :class:`QueryCostEstimate`. Cost in USD is computed from the
            standard on-demand pricing of $6.25/TiB as a conservative
            estimate; actual billing may differ under flat-rate/edition
            pricing.

        Raises:
            BackendOperationError: If the dry run fails (e.g. invalid SQL
                or a referenced table the caller cannot access).
        """
        job_config = self._bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

        @with_retry(self._retry_policy)
        def _run() -> Any:
            return self._client.query(sql, job_config=job_config)

        try:
            job = _run()
        except Exception as exc:
            raise BackendOperationError(f"BigQuery dry run failed: {exc}") from exc

        bytes_processed = int(job.total_bytes_processed or 0)
        cost_usd = (bytes_processed / (1024**4)) * 6.25
        referenced = tuple(
            f"{ref.project}.{ref.dataset_id}.{ref.table_id}"
            for ref in (job.referenced_tables or [])
        )
        return QueryCostEstimate(
            estimated_bytes_processed=bytes_processed,
            estimated_cost_usd=round(cost_usd, 6),
            referenced_tables=referenced,
        )

    def execute(self, sql: str, *, max_bytes_billed: int, row_limit: int) -> QueryResult:
        """Execute ``sql`` with a hard billing ceiling and row cap.

        Args:
            sql: The SQL statement to execute.
            max_bytes_billed: Passed through as
                ``QueryJobConfig.maximum_bytes_billed``; BigQuery aborts
                the job rather than exceed it.
            row_limit: Maximum number of rows materialized into the result.

        Returns:
            A :class:`QueryResult`.

        Raises:
            BackendOperationError: If the query fails or exceeds the
                billing ceiling.
        """
        job_config = self._bigquery.QueryJobConfig(
            maximum_bytes_billed=max_bytes_billed,
            use_query_cache=True,
        )

        @with_retry(self._retry_policy)
        def _run() -> Any:
            return self._client.query(sql, job_config=job_config)

        try:
            job = _run()
            rows_iter = job.result(max_results=row_limit)
        except Exception as exc:
            raise BackendOperationError(f"BigQuery execution failed: {exc}") from exc

        rows = tuple(dict(row.items()) for row in rows_iter)
        return QueryResult(
            rows=rows,
            total_rows_in_result_set=int(rows_iter.total_rows or len(rows)),
            bytes_processed=int(job.total_bytes_processed or 0),
            job_id=job.job_id,
        )


__all__ = ["BigQueryQueryEngine"]
