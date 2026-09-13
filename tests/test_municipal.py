from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from backend.municipal import (
    InvalidTransitionError,
    MunicipalWorkflowService,
    WorkflowConflictError,
    WorkflowCreateInput,
    WorkflowTransitionInput,
)


def workflow_payload(**overrides):
    payload = {
        "idempotency_key": "workflow:jaipur:2026-09-14:severe",
        "location_id": "jaipur",
        "priority_band": "Severe",
        "actions": [
            {
                "priority": "emergency",
                "action": "Activate incident review and readiness checks.",
            }
        ],
    }
    payload.update(overrides)
    return WorkflowCreateInput.model_validate(payload)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


class MunicipalWorkflowTests(unittest.TestCase):
    def test_severe_workflow_has_role_owner_deadline_and_creation_audit(self) -> None:
        clock = MutableClock()
        service = MunicipalWorkflowService(clock=clock)
        workflow = service.create(workflow_payload()).workflow
        self.assertEqual(workflow.owner_role, "incident-command-lead")
        self.assertEqual(workflow.status, "pending")
        self.assertEqual(workflow.escalation_due_at, clock.value + timedelta(minutes=5))
        self.assertEqual(workflow.audit_events[0].event_type, "created")
        self.assertEqual(workflow.storage_kind, "in_memory_demo")

    def test_valid_transitions_append_audit_events(self) -> None:
        service = MunicipalWorkflowService()
        workflow = service.create(workflow_payload()).workflow
        acknowledged = service.transition(
            workflow.workflow_id,
            WorkflowTransitionInput(
                to_status="acknowledged",
                actor_role="emergency-operations-controller",
                reason="Duty controller accepted ownership.",
            ),
        )
        in_progress = service.transition(
            workflow.workflow_id,
            WorkflowTransitionInput(
                to_status="in_progress",
                actor_role="public-health-coordination",
                reason="Readiness checks have started.",
            ),
        )
        self.assertEqual(acknowledged.status, "acknowledged")
        self.assertEqual(in_progress.status, "in_progress")
        self.assertEqual([event.sequence for event in in_progress.audit_events], [1, 2, 3])
        self.assertEqual(in_progress.audit_events[-1].from_status, "acknowledged")
        with self.assertRaises(ValidationError):
            in_progress.audit_events[-1].reason = "Mutated audit event"

    def test_invalid_and_terminal_transitions_are_rejected(self) -> None:
        service = MunicipalWorkflowService()
        workflow = service.create(workflow_payload()).workflow
        with self.assertRaises(InvalidTransitionError):
            service.transition(
                workflow.workflow_id,
                WorkflowTransitionInput(
                    to_status="resolved",
                    actor_role="incident-command-lead",
                    reason="Cannot skip acknowledgement and execution.",
                ),
            )

    def test_escalation_eligibility_requires_deadline_and_nonterminal_state(self) -> None:
        clock = MutableClock()
        service = MunicipalWorkflowService(clock=clock)
        workflow = service.create(workflow_payload()).workflow
        self.assertFalse(service.check_escalation(workflow.workflow_id).eligible)
        clock.value += timedelta(minutes=6)
        self.assertTrue(service.check_escalation(workflow.workflow_id).eligible)

    def test_creation_is_idempotent_and_conflicts_are_rejected(self) -> None:
        service = MunicipalWorkflowService()
        request = workflow_payload()
        original = service.create(request)
        replay = service.create(request)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.workflow.workflow_id, original.workflow.workflow_id)
        with self.assertRaises(WorkflowConflictError):
            service.create(workflow_payload(location_id="jodhpur"))


if __name__ == "__main__":
    unittest.main()
