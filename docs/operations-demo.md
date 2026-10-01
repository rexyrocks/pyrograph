# Offline alerts and municipal workflow

## Safety status

This implementation is an offline demonstration. It makes no SMS or WhatsApp
network calls, stores no phone numbers, and cannot enable a real provider.
`mortality_probability` remains unchanged and null in the risk service.

The production backend uses `HEATSHIELD_ALERT_PROVIDER=demo` by default and
fails during startup if any other provider name is configured. A future real
adapter must implement `DeliveryProvider` and return provider-confirmed
acceptance and delivery separately.

## Alert flow

`POST /alerts/dispatch` accepts a logical municipal role or public audience,
not an individual contact:

```json
{
  "idempotency_key": "alert:jaipur:2026-09-14:high:sms",
  "deduplication_key": "jaipur:2026-09-14:high",
  "channel": "sms",
  "recipient_scope": "municipal-role:emergency-operations-centre",
  "location_id": "jaipur",
  "priority_band": "High",
  "message": "Demo heat-health alert for Jaipur. No real message is sent.",
  "max_attempts": 2
}
```

The response includes queued, sent, delivered, failed, or suppressed receipts.
The same idempotency key and content returns the original record without adding
receipts. Reusing that key for different content returns HTTP 409. A separate
idempotency key with an already successful deduplication key for the same
channel and audience is suppressed before provider dispatch. SMS and WhatsApp
can therefore both receive the same event. Failed alerts can be retried with a
new idempotency key.

`GET /alerts/{alert_id}` returns the current in-memory demo record.

## Municipal flow

`POST /municipal/workflows` accepts a location, risk band, and the action list
returned by `/risk/assess`. Ownership is assigned to a role rather than a
person:

- Low: heat monitoring cell
- Moderate: public-health coordination
- High: emergency operations centre
- Severe: incident command lead

Supported states are pending, acknowledged, in progress, escalated, resolved,
and failed. Transitions use
`POST /municipal/workflows/{workflow_id}/transitions`. Invalid transitions and
changes after a terminal state return HTTP 409. Every accepted transition
appends a timestamped, immutable audit event.

`GET /municipal/workflows/{workflow_id}/escalation` calculates eligibility on
demand. It does not itself change state. An optional one-shot job can advance
overdue, nonterminal workflows to `escalated` exactly once and append a system
audit event:

```bash
HEATSHIELD_WORKFLOW_DB=work/municipal.sqlite python3 -m scripts.escalate_due
```

Set the same `HEATSHIELD_WORKFLOW_DB` path on the API to enable the opt-in
SQLite workflow store. Its parent directory must already exist. Restarting
the API with the same database preserves workflows, idempotency keys and
audit history. The job must be invoked by a trusted scheduler for timely
escalation; this repository does not deploy such a scheduler.

## Authentication and storage limitations

All operations endpoints in `backend/vercel_app.py` require `X-API-Key`. The
browser-facing Vercel proxy exposes them only when
`HEATSHIELD_OPERATIONS_DEMO_ENABLED=true`; they otherwise return 404.

Without the database setting, records are labelled `in_memory_demo` and lost
on restart. With it, workflows are labelled `sqlite_local` and mutations are
transactional across local processes, but a container without a persistent
mounted volume will still lose the database on replacement. Alert delivery
records remain in-memory in both modes. Operator authentication,
authorization, recipient consent, quiet-hour rules, a deployed escalation
scheduler, durable alert storage and a secrets-backed provider adapter are
required before real delivery.

## Verification

Run the local production-entrypoint rehearsal:

```bash
python3 -m scripts.rehearse_demo
```

It exercises simulated delivery, idempotent replay, duplicate suppression,
failure after two attempts, acknowledgement and escalation eligibility after
advancing an injected clock by six minutes. Re-entering application lifespan
resets in-memory records; the previous workflow returns 404. Provider and clock
injection exist only in this harness, not as remotely callable controls. No
network sockets or real messages are used. The JSON includes delivery receipts,
`real_delivery_enabled: false`, and storage labels.

There is no operations console in the frontend. Demonstrate these API calls
and disclose the reset behavior. Role strings remain demonstration inputs,
not authenticated operator identities. The public operations proxy should
remain disabled for a real municipal process.

Run the complete suite offline:

```bash
python3 -m unittest -v
```

Focused coverage lives in `tests/test_alerts.py`, `tests/test_municipal.py`, and
`tests/test_operations_api.py`.
