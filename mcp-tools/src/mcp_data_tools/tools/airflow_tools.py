"""MCP tools exposing governed Airflow orchestration capability."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, ClassVar

from mcp_data_tools.guardrails.engine import GuardrailEngine
from mcp_data_tools.ports.interfaces import OrchestratorPort
from mcp_data_tools.tools.base import ToolHandler


class AirflowTriggerDagTool(ToolHandler):
    """Triggers a new run of an allow-listed Airflow DAG."""

    name = "airflow_trigger_dag"
    description = (
        "Trigger a new run of an allow-listed Airflow DAG, optionally "
        "passing a run configuration payload."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "dag_id": {"type": "string"},
            "conf": {"type": "object", "description": "Run configuration passed to the DAG."},
        },
        "required": ["dag_id"],
        "additionalProperties": False,
    }

    def __init__(self, guardrails: GuardrailEngine, orchestrator: OrchestratorPort) -> None:
        super().__init__(guardrails)
        self._orchestrator = orchestrator

    def execute(self, arguments: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """Trigger a DAG run.

        Args:
            arguments: Must contain ``dag_id``; may contain ``conf``.
            actor: Calling agent/session identifier.

        Returns:
            A dict describing the newly created run's status.

        Raises:
            mcp_data_tools.core.exceptions.GuardrailViolationError: If the
                DAG is not allow-listed.
            mcp_data_tools.core.exceptions.BackendOperationError: If
                Airflow rejects the trigger request.
        """
        dag_id = arguments["dag_id"]
        decision = self.guardrails.authorize_dag_trigger(dag_id=dag_id, actor=actor)
        self.guardrails.require(decision)

        status = self._orchestrator.trigger_dag_run(dag_id, conf=arguments.get("conf"))
        return _status_to_dict(status)


class AirflowGetDagRunStatusTool(ToolHandler):
    """Fetches the status of a previously triggered Airflow DAG run."""

    name = "airflow_get_dag_run_status"
    description = "Fetch the current status of a previously triggered Airflow DAG run."
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "dag_id": {"type": "string"},
            "run_id": {"type": "string"},
        },
        "required": ["dag_id", "run_id"],
        "additionalProperties": False,
    }

    def __init__(self, guardrails: GuardrailEngine, orchestrator: OrchestratorPort) -> None:
        super().__init__(guardrails)
        self._orchestrator = orchestrator

    def execute(self, arguments: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """Fetch a DAG run's status.

        Args:
            arguments: Must contain ``dag_id`` and ``run_id``.
            actor: Calling agent/session identifier.

        Returns:
            A dict describing the run's current status.

        Raises:
            mcp_data_tools.core.exceptions.GuardrailViolationError: If the
                DAG is not allow-listed.
            mcp_data_tools.core.exceptions.BackendOperationError: If the
                run cannot be found.
        """
        dag_id = arguments["dag_id"]
        decision = self.guardrails.authorize_dag_trigger(dag_id=dag_id, actor=actor)
        self.guardrails.require(decision)

        status = self._orchestrator.get_dag_run_status(dag_id, arguments["run_id"])
        return _status_to_dict(status)


def _status_to_dict(status: Any) -> dict[str, Any]:
    payload = asdict(status)
    payload["state"] = status.state.value
    return payload


__all__ = ["AirflowGetDagRunStatusTool", "AirflowTriggerDagTool"]
