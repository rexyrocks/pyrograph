# Track 2 — Alerts and municipal operations

## Owner

Human teammate A

## Objective

Demonstrate a reliable alert and municipal-response workflow without requiring
paid SMS/WhatsApp credentials during the hackathon.

## Tasks

1. Build an offline demo delivery provider for SMS and WhatsApp channels.
2. Define provider interfaces for future real delivery services.
3. Add idempotency keys and duplicate-alert prevention.
4. Record queued, sent, delivered, failed, and suppressed receipts.
5. Define retry limits without blocking waits.
6. Create action plans from Low, Moderate, High, and Severe priority bands.
7. Add department or role ownership without personal contact data.
8. Support pending, acknowledged, in-progress, escalated, resolved, and failed
   states.
9. Record immutable audit events for every transition.
10. Add focused unit tests.

## Suggested owned files

- `backend/alerts.py`
- `backend/municipal.py`
- `tests/test_alerts.py`
- `tests/test_municipal.py`

Do not edit shared API entrypoints or frontend files. Track 1 will wire the
completed services into the application.

## Safety constraints

- Make no real network calls in demo mode.
- Do not use unofficial WhatsApp automation.
- Do not commit phone numbers, credentials, tokens, or message-provider secrets.
- A delivery receipt must not claim delivery unless the selected provider
  confirms it.
- Repeated triggers with the same idempotency key must not create duplicates.

## Acceptance checks

- Demo mode works without internet access.
- SMS and WhatsApp use the same provider contract.
- Retry and failure states are deterministic and testable.
- Invalid state transitions are rejected.
- Escalation eligibility can be calculated without background jobs.
- Focused tests pass.

## Handoff to Track 1

Provide:

- Public classes and functions
- Example request and response objects
- Required environment-variable names
- Focused test results
- Decisions and rejected alternatives
- Known limitations
