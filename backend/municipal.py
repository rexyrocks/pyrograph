"""Municipal ownership, acknowledgement, escalation, and audit workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import RLock
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.risk import MunicipalAction


PriorityBand = Literal["Low", "Moderate", "High", "Severe"]
WorkflowStatus = Literal[
    "pending",
    "acknowledged",
    "in_progress",
    "escalated",
    "resolved",
    "failed",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WorkflowCreateInput(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    location_id: str = Field(min_length=1, max_length=80)
    priority_band: PriorityBand
    actions: list[MunicipalAction] = Field(min_length=1, max_length=20)


class WorkflowTransitionInput(StrictModel):
    to_status: WorkflowStatus
    actor_role: str = Field(min_length=3, max_length=100)
    reason: str = Field(min_length=3, max_length=500)


class AuditEvent(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int
    occurred_at: datetime
    event_type: Literal["created", "transitioned"]
    from_status: WorkflowStatus | None
    to_status: WorkflowStatus
    actor_role: str
    reason: str


class MunicipalWorkflow(StrictModel):
    workflow_id: str
    request: WorkflowCreateInput
    owner_role: str
    status: WorkflowStatus
    escalation_due_at: datetime
    audit_events: tuple[AuditEvent, ...]
    created_at: datetime
    updated_at: datetime
    storage_kind: Literal["in_memory_demo"] = "in_memory_demo"


class WorkflowCreateOutput(StrictModel):
    workflow: MunicipalWorkflow
    idempotent_replay: bool = False


class EscalationCheckOutput(StrictModel):
    workflow_id: str
    status: WorkflowStatus
    eligible: bool
    escalation_due_at: datetime
    checked_at: datetime
    reason: str


class WorkflowConflictError(ValueError):
    """Raised when an idempotency key is reused for different content."""


class InvalidTransitionError(ValueError):
    """Raised when a workflow state transition is not allowed."""


class WorkflowNotFoundError(KeyError):
    """Raised when a requested demo workflow does not exist."""


_OWNER_BY_BAND = {
    "Low": "heat-monitoring-cell",
    "Moderate": "public-health-coordination",
    "High": "emergency-operations-centre",
    "Severe": "incident-command-lead",
}

_ESCALATION_MINUTES = {"Low": 240, "Moderate": 60, "High": 15, "Severe": 5}

_ALLOWED_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    "pending": frozenset({"acknowledged", "escalated", "failed"}),
    "acknowledged": frozenset({"in_progress", "escalated", "failed"}),
    "in_progress": frozenset({"resolved", "escalated", "failed"}),
    "escalated": frozenset({"acknowledged", "in_progress", "resolved", "failed"}),
    "resolved": frozenset(),
    "failed": frozenset(),
}


class MunicipalWorkflowService:
    """Deterministic, in-memory workflow service for offline demonstrations."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(UTC))
        self._workflows: dict[str, MunicipalWorkflow] = {}
        self._idempotency_fingerprints: dict[str, str] = {}
        self._idempotency_workflow_ids: dict[str, str] = {}
        self._lock = RLock()

    @staticmethod
    def _fingerprint(request: WorkflowCreateInput) -> str:
        return sha256(request.model_dump_json().encode()).hexdigest()

    def create(self, request: WorkflowCreateInput) -> WorkflowCreateOutput:
        with self._lock:
            return self._create_locked(request)

    def _create_locked(self, request: WorkflowCreateInput) -> WorkflowCreateOutput:
        fingerprint = self._fingerprint(request)
        existing_fingerprint = self._idempotency_fingerprints.get(request.idempotency_key)
        if existing_fingerprint is not None:
            if existing_fingerprint != fingerprint:
                raise WorkflowConflictError(
                    "Idempotency key was already used for different workflow content"
                )
            workflow_id = self._idempotency_workflow_ids[request.idempotency_key]
            return WorkflowCreateOutput(
                workflow=self._workflows[workflow_id],
                idempotent_replay=True,
            )

        now = self.clock()
        workflow_id = "workflow_" + sha256(
            request.idempotency_key.encode()
        ).hexdigest()[:16]
        workflow = MunicipalWorkflow(
            workflow_id=workflow_id,
            request=request,
            owner_role=_OWNER_BY_BAND[request.priority_band],
            status="pending",
            escalation_due_at=now
            + timedelta(minutes=_ESCALATION_MINUTES[request.priority_band]),
            audit_events=(
                AuditEvent(
                    sequence=1,
                    occurred_at=now,
                    event_type="created",
                    from_status=None,
                    to_status="pending",
                    actor_role="system",
                    reason="Workflow created from a heat-health priority band.",
                ),
            ),
            created_at=now,
            updated_at=now,
        )
        self._workflows[workflow_id] = workflow
        self._idempotency_fingerprints[request.idempotency_key] = fingerprint
        self._idempotency_workflow_ids[request.idempotency_key] = workflow_id
        return WorkflowCreateOutput(workflow=workflow)

    def get(self, workflow_id: str) -> MunicipalWorkflow:
        with self._lock:
            try:
                return self._workflows[workflow_id]
            except KeyError as error:
                raise WorkflowNotFoundError(workflow_id) from error

    def transition(
        self,
        workflow_id: str,
        request: WorkflowTransitionInput,
    ) -> MunicipalWorkflow:
        with self._lock:
            workflow = self.get(workflow_id)
            if request.to_status not in _ALLOWED_TRANSITIONS[workflow.status]:
                raise InvalidTransitionError(
                    f"Transition {workflow.status} -> {request.to_status} is not allowed"
                )

            now = self.clock()
            event = AuditEvent(
                sequence=len(workflow.audit_events) + 1,
                occurred_at=now,
                event_type="transitioned",
                from_status=workflow.status,
                to_status=request.to_status,
                actor_role=request.actor_role,
                reason=request.reason,
            )
            updated = workflow.model_copy(
                update={
                    "status": request.to_status,
                    "audit_events": (*workflow.audit_events, event),
                    "updated_at": now,
                }
            )
            self._workflows[workflow_id] = updated
            return updated

    def check_escalation(
        self,
        workflow_id: str,
        checked_at: datetime | None = None,
    ) -> EscalationCheckOutput:
        with self._lock:
            workflow = self.get(workflow_id)
            now = checked_at or self.clock()
            terminal = workflow.status in {"resolved", "failed"}
            eligible = (
                not terminal
                and workflow.status != "escalated"
                and now >= workflow.escalation_due_at
            )
            if terminal:
                reason = "Terminal workflows are not eligible for escalation."
            elif workflow.status == "escalated":
                reason = "Workflow is already escalated."
            elif eligible:
                reason = "Acknowledgement or resolution deadline has passed."
            else:
                reason = "Escalation deadline has not passed."
            return EscalationCheckOutput(
                workflow_id=workflow.workflow_id,
                status=workflow.status,
                eligible=eligible,
                escalation_due_at=workflow.escalation_due_at,
                checked_at=now,
                reason=reason,
            )
