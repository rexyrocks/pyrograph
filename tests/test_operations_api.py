from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

TEST_API_KEY = "test-only-heatshield-api-key-00000000"
os.environ.setdefault("HEATSHIELD_API_KEY", TEST_API_KEY)

from backend.main import app as full_app
from backend.vercel_app import app as vercel_app
from tests.test_alerts import alert_payload
from tests.test_municipal import workflow_payload
from tests.test_risk import BASE_PAYLOAD


class OperationsApiTests(unittest.TestCase):
    def test_full_api_dispatches_alert_and_transitions_workflow(self) -> None:
        with TestClient(full_app) as client:
            alert = client.post(
                "/alerts/dispatch", json=alert_payload().model_dump(mode="json")
            )
            workflow = client.post(
                "/municipal/workflows",
                json=workflow_payload().model_dump(mode="json"),
            )
            workflow_id = workflow.json()["workflow"]["workflow_id"]
            transitioned = client.post(
                f"/municipal/workflows/{workflow_id}/transitions",
                json={
                    "to_status": "acknowledged",
                    "actor_role": "emergency-operations-controller",
                    "reason": "Offline demo acknowledgement.",
                },
            )
            escalation = client.get(
                f"/municipal/workflows/{workflow_id}/escalation"
            )
        self.assertEqual(alert.status_code, 200)
        self.assertEqual(alert.json()["alert"]["status"], "delivered")
        self.assertEqual(workflow.status_code, 200)
        self.assertEqual(transitioned.status_code, 200)
        self.assertEqual(transitioned.json()["status"], "acknowledged")
        self.assertEqual(escalation.status_code, 200)
        self.assertFalse(escalation.json()["eligible"])

    def test_risk_actions_flow_into_a_municipal_workflow(self) -> None:
        with TestClient(full_app) as client:
            risk = client.post("/risk/assess", json=BASE_PAYLOAD)
            self.assertEqual(risk.status_code, 200)
            assessment = risk.json()
            workflow = client.post(
                "/municipal/workflows",
                json={
                    "idempotency_key": "risk-workflow:jaipur:2026-09-14",
                    "location_id": "jaipur",
                    "priority_band": assessment["band"],
                    "actions": assessment["municipal_actions"],
                },
            )
        self.assertEqual(workflow.status_code, 200)
        self.assertEqual(
            workflow.json()["workflow"]["request"]["actions"],
            assessment["municipal_actions"],
        )
        self.assertEqual(
            workflow.json()["workflow"]["request"]["priority_band"],
            assessment["band"],
        )

    def test_api_maps_idempotency_and_transition_conflicts(self) -> None:
        with TestClient(full_app) as client:
            first_alert = client.post(
                "/alerts/dispatch", json=alert_payload().model_dump(mode="json")
            )
            conflicting_alert = client.post(
                "/alerts/dispatch",
                json=alert_payload(message="Changed message").model_dump(mode="json"),
            )
            workflow = client.post(
                "/municipal/workflows",
                json=workflow_payload(
                    idempotency_key="workflow:conflict-mapping"
                ).model_dump(mode="json"),
            )
            invalid_transition = client.post(
                "/municipal/workflows/"
                f"{workflow.json()['workflow']['workflow_id']}/transitions",
                json={
                    "to_status": "resolved",
                    "actor_role": "incident-command-lead",
                    "reason": "Attempted to skip required acknowledgement.",
                },
            )
        self.assertEqual(first_alert.status_code, 200)
        self.assertEqual(conflicting_alert.status_code, 409)
        self.assertEqual(workflow.status_code, 200)
        self.assertEqual(invalid_transition.status_code, 409)

    def test_production_operations_endpoints_require_api_key(self) -> None:
        with TestClient(vercel_app) as client:
            missing_alert = client.post(
                "/alerts/dispatch", json=alert_payload().model_dump(mode="json")
            )
            missing_workflow = client.post(
                "/municipal/workflows",
                json=workflow_payload().model_dump(mode="json"),
            )
            valid_alert = client.post(
                "/alerts/dispatch",
                json=alert_payload().model_dump(mode="json"),
                headers={"X-API-Key": TEST_API_KEY},
            )
        self.assertEqual(missing_alert.status_code, 401)
        self.assertEqual(missing_workflow.status_code, 401)
        self.assertEqual(valid_alert.status_code, 200)
        self.assertFalse(valid_alert.json()["alert"]["real_delivery_enabled"])


if __name__ == "__main__":
    unittest.main()
