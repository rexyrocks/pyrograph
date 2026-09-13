from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from pydantic import ValidationError

from backend.alerts import (
    AlertConflictError,
    AlertDispatchInput,
    AlertService,
    DemoDeliveryProvider,
    ProviderResult,
    build_alert_service_from_environment,
)


def alert_payload(**overrides):
    payload = {
        "idempotency_key": "alert:jaipur:2026-09-14:high:sms",
        "deduplication_key": "jaipur:2026-09-14:high",
        "channel": "sms",
        "recipient_scope": "municipal-role:emergency-operations-centre",
        "location_id": "jaipur",
        "priority_band": "High",
        "message": "Demo heat-health alert for Jaipur. No real message is sent.",
        "max_attempts": 2,
    }
    payload.update(overrides)
    return AlertDispatchInput.model_validate(payload)


class SteppingClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class AcceptedWithoutDeliveryProvider:
    name = "accepted-without-delivery"
    supported_channels = frozenset({"sms", "whatsapp"})

    def send(self, request, attempt):
        return ProviderResult(
            accepted=True,
            delivered=False,
            provider_message_id="pending-provider-message",
        )


class AlertServiceTests(unittest.TestCase):
    def test_demo_provider_supports_sms_and_whatsapp_without_network(self) -> None:
        for channel in ("sms", "whatsapp"):
            with self.subTest(channel=channel):
                service = AlertService(clock=SteppingClock())
                request = alert_payload(
                    channel=channel,
                    idempotency_key=f"alert:jaipur:2026-09-14:high:{channel}",
                )
                result = service.dispatch(request)
                self.assertEqual(result.alert.status, "delivered")
                self.assertEqual(
                    [receipt.status for receipt in result.alert.receipts],
                    ["queued", "sent", "delivered"],
                )
                self.assertFalse(result.alert.real_delivery_enabled)

    def test_idempotent_replay_does_not_create_receipts(self) -> None:
        service = AlertService(clock=SteppingClock())
        request = alert_payload()
        original = service.dispatch(request)
        replay = service.dispatch(request)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.alert.alert_id, original.alert.alert_id)
        self.assertEqual(replay.alert.receipts, original.alert.receipts)

    def test_reusing_idempotency_key_for_different_content_is_rejected(self) -> None:
        service = AlertService()
        service.dispatch(alert_payload())
        with self.assertRaises(AlertConflictError):
            service.dispatch(alert_payload(message="Different content"))

    def test_duplicate_trigger_is_suppressed_before_provider_call(self) -> None:
        service = AlertService(clock=SteppingClock())
        service.dispatch(alert_payload())
        duplicate = service.dispatch(
            alert_payload(idempotency_key="alert:jaipur:duplicate:0001")
        )
        self.assertEqual(duplicate.alert.status, "suppressed")
        self.assertEqual(duplicate.alert.attempts, 0)
        self.assertEqual(
            [receipt.status for receipt in duplicate.alert.receipts],
            ["queued", "suppressed"],
        )

    def test_deduplication_is_scoped_per_channel(self) -> None:
        service = AlertService(clock=SteppingClock())
        sms = service.dispatch(alert_payload())
        whatsapp = service.dispatch(
            alert_payload(
                idempotency_key="alert:jaipur:2026-09-14:high:whatsapp",
                channel="whatsapp",
            )
        )
        self.assertEqual(sms.alert.status, "delivered")
        self.assertEqual(whatsapp.alert.status, "delivered")

    def test_retry_is_immediate_bounded_and_provider_confirmed(self) -> None:
        provider = DemoDeliveryProvider(outcomes=("failed", "delivered"))
        service = AlertService(provider=provider, clock=SteppingClock())
        result = service.dispatch(alert_payload())
        self.assertEqual(result.alert.attempts, 2)
        self.assertEqual(result.alert.status, "delivered")
        self.assertEqual(
            [receipt.status for receipt in result.alert.receipts],
            ["queued", "failed", "sent", "delivered"],
        )

    def test_exhausted_retries_never_claim_delivery(self) -> None:
        provider = DemoDeliveryProvider(outcomes=("failed",))
        service = AlertService(provider=provider, clock=SteppingClock())
        result = service.dispatch(alert_payload(max_attempts=3))
        self.assertEqual(result.alert.status, "failed")
        self.assertEqual(result.alert.attempts, 3)
        self.assertNotIn(
            "delivered", [receipt.status for receipt in result.alert.receipts]
        )

    def test_provider_acceptance_without_confirmation_stays_sent(self) -> None:
        service = AlertService(
            provider=AcceptedWithoutDeliveryProvider(), clock=SteppingClock()
        )
        result = service.dispatch(alert_payload(max_attempts=3))
        self.assertEqual(result.alert.status, "sent")
        self.assertEqual(result.alert.attempts, 1)
        self.assertNotIn(
            "delivered", [receipt.status for receipt in result.alert.receipts]
        )

    def test_new_trigger_can_retry_after_a_terminal_failure(self) -> None:
        service = AlertService(
            provider=DemoDeliveryProvider(outcomes=("failed",)),
            clock=SteppingClock(),
        )
        first = service.dispatch(alert_payload(max_attempts=1))
        second = service.dispatch(
            alert_payload(
                idempotency_key="alert:jaipur:retry-after-failure:0001",
                max_attempts=1,
            )
        )
        self.assertEqual(first.alert.status, "failed")
        self.assertEqual(second.alert.status, "failed")
        self.assertEqual(second.alert.attempts, 1)

    def test_environment_factory_fails_closed_for_real_provider(self) -> None:
        with patch.dict(
            "os.environ", {"HEATSHIELD_ALERT_PROVIDER": "whatsapp"}, clear=False
        ):
            with self.assertRaisesRegex(RuntimeError, "must implement"):
                build_alert_service_from_environment()

    def test_recipient_scope_rejects_direct_contact_values(self) -> None:
        with self.assertRaises(ValidationError):
            alert_payload(recipient_scope="+919999999999")


if __name__ == "__main__":
    unittest.main()
