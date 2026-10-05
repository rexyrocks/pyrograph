from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from backend.municipal import (
    InvalidTransitionError,
    MunicipalWorkflowService,
    SqliteMunicipalWorkflowService,
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
        self.assertEqual([item.workflow_id for item in service.escalate_due()], [workflow.workflow_id])
        self.assertEqual(service.escalate_due(), [])

    def test_creation_is_idempotent_and_conflicts_are_rejected(self) -> None:
        service = MunicipalWorkflowService()
        request = workflow_payload()
        original = service.create(request)
        replay = service.create(request)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.workflow.workflow_id, original.workflow.workflow_id)
        with self.assertRaises(WorkflowConflictError):
            service.create(workflow_payload(location_id="jodhpur"))

    def test_sqlite_workflow_survives_restart_with_audit_and_idempotency(self) -> None:
        clock = MutableClock()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "municipal.sqlite"
            first = SqliteMunicipalWorkflowService(path, clock=clock)
            created = first.create(workflow_payload()).workflow
            self.assertEqual(created.storage_kind, "sqlite_local")
            first.transition(created.workflow_id, WorkflowTransitionInput(
                to_status="acknowledged", actor_role="incident-command-lead",
                reason="Duty role accepted the response."))
            second = SqliteMunicipalWorkflowService(path, clock=clock)
            restored = second.get(created.workflow_id)
            self.assertEqual(restored.status, "acknowledged")
            self.assertEqual([event.sequence for event in restored.audit_events], [1, 2])
            self.assertTrue(second.create(workflow_payload()).idempotent_replay)
            with self.assertRaises(WorkflowConflictError):
                second.create(workflow_payload(location_id="jodhpur"))
            self.assertEqual(second.escalate_due(), [])
            clock.value += timedelta(minutes=6)
            self.assertTrue(second.check_escalation(created.workflow_id).eligible)
            escalated = second.escalate_due()
            self.assertEqual([item.workflow_id for item in escalated], [created.workflow_id])
            self.assertEqual(second.escalate_due(), [])
            self.assertEqual(first.get(created.workflow_id).status, "escalated")
            self.assertEqual(len(first.get(created.workflow_id).audit_events), 3)

    def test_sqlite_rejects_a_second_concurrent_transition(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "municipal.sqlite"
            first = SqliteMunicipalWorkflowService(path)
            second = SqliteMunicipalWorkflowService(path)
            workflow_id = first.create(workflow_payload()).workflow.workflow_id
            transition = WorkflowTransitionInput(to_status="acknowledged",
                                                 actor_role="incident-command-lead",
                                                 reason="Accepted the response.")
            def attempt(service):
                try:
                    service.transition(workflow_id, transition)
                    return "accepted"
                except InvalidTransitionError:
                    return "conflict"
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(attempt, (first, second)))
            self.assertCountEqual(outcomes, ["accepted", "conflict"])
            self.assertEqual(len(first.get(workflow_id).audit_events), 2)


if __name__ == "__main__":
    unittest.main()
