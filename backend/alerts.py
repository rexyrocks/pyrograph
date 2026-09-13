"""Offline-first alert delivery contracts and deterministic demo provider."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import os
from threading import RLock
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


AlertChannel = Literal["sms", "whatsapp"]
AlertStatus = Literal["queued", "sent", "delivered", "failed", "suppressed"]
PriorityBand = Literal["Low", "Moderate", "High", "Severe"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AlertDispatchInput(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    deduplication_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    channel: AlertChannel
    recipient_scope: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^(municipal-role|public-audience):[A-Za-z0-9._:-]+$",
    )
    location_id: str = Field(min_length=1, max_length=80)
    priority_band: PriorityBand
    message: str = Field(min_length=1, max_length=1000)
    max_attempts: int = Field(default=2, ge=1, le=3)


class ProviderResult(StrictModel):
    accepted: bool
    delivered: bool
    provider_message_id: str | None = None
    error_code: str | None = None


class DeliveryReceipt(StrictModel):
    sequence: int
    status: AlertStatus
    attempted_at: datetime
    attempt: int
    provider: str
    provider_message_id: str | None = None
    error_code: str | None = None
    detail: str


class AlertRecord(StrictModel):
    alert_id: str
    request: AlertDispatchInput
    status: AlertStatus
    attempts: int
    receipts: list[DeliveryReceipt]
    created_at: datetime
    updated_at: datetime
    storage_kind: Literal["in_memory_demo"] = "in_memory_demo"
    real_delivery_enabled: Literal[False] = False


class AlertDispatchOutput(StrictModel):
    alert: AlertRecord
    idempotent_replay: bool = False


class AlertConflictError(ValueError):
    """Raised when an idempotency key is reused for different content."""


class AlertNotFoundError(KeyError):
    """Raised when a requested demo alert does not exist."""


class DeliveryProvider(Protocol):
    """Interface for demo and future credential-backed delivery providers."""

    name: str
    supported_channels: frozenset[AlertChannel]

    def send(self, request: AlertDispatchInput, attempt: int) -> ProviderResult:
        """Attempt delivery once and return only provider-confirmed state."""


@dataclass(frozen=True)
class DemoDeliveryProvider:
    """No-network provider with deterministic outcomes for demos and tests."""

    outcomes: tuple[Literal["delivered", "failed"], ...] = ("delivered",)
    name: str = "offline-demo"
    supported_channels: frozenset[AlertChannel] = frozenset({"sms", "whatsapp"})

    def __post_init__(self) -> None:
        if not self.outcomes:
            raise ValueError("Demo provider needs at least one deterministic outcome")

    def send(self, request: AlertDispatchInput, attempt: int) -> ProviderResult:
        outcome = self.outcomes[min(attempt - 1, len(self.outcomes) - 1)]
        message_id = "demo_" + sha256(
            f"{request.idempotency_key}:{attempt}".encode()
        ).hexdigest()[:16]
        if outcome == "delivered":
            return ProviderResult(
                accepted=True,
                delivered=True,
                provider_message_id=message_id,
            )
        return ProviderResult(
            accepted=False,
            delivered=False,
            error_code="demo_provider_failure",
        )


class AlertService:
    """In-memory orchestration for an offline, auditable alert demonstration."""

    def __init__(
        self,
        provider: DeliveryProvider | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.provider = provider or DemoDeliveryProvider()
        self.clock = clock or (lambda: datetime.now(UTC))
        self._alerts_by_id: dict[str, AlertRecord] = {}
        self._idempotency_fingerprints: dict[str, str] = {}
        self._idempotency_alert_ids: dict[str, str] = {}
        self._deduplication_alert_ids: dict[tuple[str, str, str], str] = {}
        self._lock = RLock()

    @staticmethod
    def _fingerprint(request: AlertDispatchInput) -> str:
        return sha256(request.model_dump_json().encode()).hexdigest()

    @staticmethod
    def _deduplication_scope(request: AlertDispatchInput) -> tuple[str, str, str]:
        return (request.channel, request.recipient_scope, request.deduplication_key)

    def dispatch(self, request: AlertDispatchInput) -> AlertDispatchOutput:
        with self._lock:
            return self._dispatch_locked(request)

    def _dispatch_locked(self, request: AlertDispatchInput) -> AlertDispatchOutput:
        fingerprint = self._fingerprint(request)
        existing_fingerprint = self._idempotency_fingerprints.get(request.idempotency_key)
        if existing_fingerprint is not None:
            if existing_fingerprint != fingerprint:
                raise AlertConflictError(
                    "Idempotency key was already used for different alert content"
                )
            alert_id = self._idempotency_alert_ids[request.idempotency_key]
            return AlertDispatchOutput(
                alert=self._alerts_by_id[alert_id],
                idempotent_replay=True,
            )

        alert_id = "alert_" + sha256(request.idempotency_key.encode()).hexdigest()[:16]
        now = self.clock()
        receipts = [
            DeliveryReceipt(
                sequence=1,
                status="queued",
                attempted_at=now,
                attempt=0,
                provider=self.provider.name,
                detail="Alert accepted by the local orchestration service.",
            )
        ]

        deduplication_scope = self._deduplication_scope(request)
        if deduplication_scope in self._deduplication_alert_ids:
            receipts.append(
                DeliveryReceipt(
                    sequence=2,
                    status="suppressed",
                    attempted_at=self.clock(),
                    attempt=0,
                    provider=self.provider.name,
                    detail="Duplicate alert suppressed before provider dispatch.",
                )
            )
            record = AlertRecord(
                alert_id=alert_id,
                request=request,
                status="suppressed",
                attempts=0,
                receipts=receipts,
                created_at=now,
                updated_at=receipts[-1].attempted_at,
            )
            self._store(record, fingerprint)
            return AlertDispatchOutput(alert=record)

        if request.channel not in self.provider.supported_channels:
            raise ValueError(f"Provider does not support channel: {request.channel}")

        final_status: AlertStatus = "failed"
        attempts = 0
        for attempt in range(1, request.max_attempts + 1):
            attempts = attempt
            result = self.provider.send(request, attempt)
            receipts.append(
                DeliveryReceipt(
                    sequence=len(receipts) + 1,
                    status="sent" if result.accepted else "failed",
                    attempted_at=self.clock(),
                    attempt=attempt,
                    provider=self.provider.name,
                    provider_message_id=result.provider_message_id,
                    error_code=result.error_code,
                    detail=(
                        "Provider accepted the alert."
                        if result.accepted
                        else "Provider rejected the delivery attempt."
                    ),
                )
            )
            if result.delivered:
                receipts.append(
                    DeliveryReceipt(
                        sequence=len(receipts) + 1,
                        status="delivered",
                        attempted_at=self.clock(),
                        attempt=attempt,
                        provider=self.provider.name,
                        provider_message_id=result.provider_message_id,
                        detail="Delivery confirmed by the selected provider.",
                    )
                )
                final_status = "delivered"
                break
            if result.accepted:
                final_status = "sent"
                break

        record = AlertRecord(
            alert_id=alert_id,
            request=request,
            status=final_status,
            attempts=attempts,
            receipts=receipts,
            created_at=now,
            updated_at=receipts[-1].attempted_at,
        )
        self._store(record, fingerprint)
        if final_status in {"sent", "delivered"}:
            self._deduplication_alert_ids[deduplication_scope] = alert_id
        return AlertDispatchOutput(alert=record)

    def _store(self, record: AlertRecord, fingerprint: str) -> None:
        self._alerts_by_id[record.alert_id] = record
        key = record.request.idempotency_key
        self._idempotency_fingerprints[key] = fingerprint
        self._idempotency_alert_ids[key] = record.alert_id

    def get(self, alert_id: str) -> AlertRecord:
        with self._lock:
            try:
                return self._alerts_by_id[alert_id]
            except KeyError as error:
                raise AlertNotFoundError(alert_id) from error


def build_alert_service_from_environment() -> AlertService:
    """Fail closed if an unimplemented real delivery provider is requested."""

    provider_name = os.getenv("HEATSHIELD_ALERT_PROVIDER", "demo").strip().lower()
    if provider_name != "demo":
        raise RuntimeError(
            "Only HEATSHIELD_ALERT_PROVIDER=demo is available; real providers "
            "must implement DeliveryProvider before use"
        )
    return AlertService(provider=DemoDeliveryProvider())
