# Pyrograph delivery roadmap

## Objective

Complete the six hackathon deliverables without presenting prototype or proxy
data as official operational data:

1. Historical hospitalisation/mortality evidence
2. Mortality Risk Index
3. Demographic vulnerability integration
4. Zone/ward-level spatial risk
5. SMS/WhatsApp alert delivery
6. Municipal action-plan triggers

## Parallel work split

### Track A — GPT-5.6 Sol: product and integration

Sol owns the code that runs in the application.

- Create stable schemas for health evidence, vulnerability inputs, risk output,
  alert recipients, delivery receipts, and municipal actions.
- Build the mortality-risk calculation behind a feature flag. It must remain
  labelled as a calibrated prototype until sufficient health outcome data is
  available for validation.
- Add demographic vulnerability scoring with explicit missing-data handling.
- Replace hard-coded UI values with API responses and give every value a source,
  freshness, and confidence/provenance label.
- Implement an alert adapter with `demo`, `sms`, and `whatsapp` providers. Demo
  mode must work offline and generate auditable delivery receipts.
- Implement municipal trigger rules and an acknowledgement/escalation state
  machine.
- Add unit, contract, and end-to-end tests.

Primary files:

- `backend/`
- `frontend/`
- `tests/`
- deployment configuration

### Track B — Gemini 3.1 Pro: evidence and data preparation

Gemini owns research artifacts and reproducible datasets, not application code.

- Build a source inventory for mortality, hospitalisation, demographics,
  population, administrative boundaries, and heat exposure.
- Record geography, time span, update frequency, licence, access method, and
  known bias for every source.
- Produce validated, machine-readable tables with data dictionaries and
  transformation notes.
- Design a district/state fallback hierarchy for missing ward-level data.
- Propose mortality calibration experiments and document why annual state-level
  mortality cannot directly supervise daily ward-level predictions.
- Prepare test fixtures containing synthetic or aggregate data only; do not add
  personal health information.

Primary files:

- `data/sources/`
- `data/processed/`
- `docs/data/`

### Track C — GPT-6 Astra: architecture and review gates

Astra is used at checkpoints rather than for routine implementation.

- Review the risk formulation for target leakage, false precision, geographic
  mismatch, and unsupported causal claims.
- Review alert safety: deduplication, retries, consent, quiet hours, language,
  escalation, and failure behaviour.
- Review state-wide scaling: location configuration, model/version registry,
  observability, caching, and graceful degradation.
- Perform the final deliverable audit and identify any claim that exceeds the
  supporting evidence.

Astra should normally change documentation or tests only. Product changes flow
back to Track A to keep ownership clear.

## Five phases

### Phase 1 — Contracts and evidence

Parallel:

- Gemini: source inventory, data dictionaries, cleaned aggregate datasets.
- Sol: API/data contracts, provenance fields, feature flags, fixtures.

Exit gate: each UI metric can identify its source, geography, date range, and
whether it is live, historical, synthetic, or unavailable.

### Phase 2 — Vulnerability and mortality-risk prototype

Parallel:

- Gemini: feature rationale, fallback hierarchy, calibration experiment plan.
- Sol: vulnerability service and mortality-risk prototype with uncertainty and
  missingness surfaced explicitly.

Astra gate: approve modelling claims and terminology before the score appears in
the main dashboard.

### Phase 3 — Spatial risk

- Sol implements a generic location hierarchy and risk aggregation.
- Gemini supplies only boundaries that are legally reusable and traceable.
- If official ward geometry remains unavailable, ship district/zone aggregation
  or an explicitly illustrative demo—never screenshot-derived boundaries.

Exit gate: geography joins are tested and the map cannot imply unsupported ward
precision.

### Phase 4 — Alerts and municipal actions

- Sol implements offline demo delivery first, then optional real providers
  behind environment configuration.
- Sol adds trigger, acknowledgement, retry, escalation, and audit-log behaviour.
- Gemini prepares bilingual message content and links each action to an approved
  heat-health guidance source.

Astra gate: safety and failure-mode review before enabling any real recipient.

### Phase 5 — State-wide configuration and demo hardening

- Sol removes Jaipur-specific constants, adds location configuration, completes
  tests, and prepares the demo runbook.
- Gemini verifies coverage gaps and creates the evidence matrix used in judging.
- Astra conducts the final architecture and evidence-claims audit.

Exit gate: one command starts the demo; offline mode works; unsupported data is
clearly labelled; tests pass; the six deliverables have visible evidence.

## Coordination rules

- Use separate branches: `sol/product-integration` and `gemini/data-evidence`.
- Gemini must not edit `backend/` or `frontend/`; Sol must not silently rewrite
  source datasets or their methodology notes.
- Merge data contracts and tiny fixtures from Phase 1 before either track builds
  against them.
- Integrate at the end of each phase, not only at the end of the project.
- Every major architectural or data decision is appended to `deceision.md`.
- No secrets, phone numbers, or personal health data are committed.

## Deliverable ownership matrix

| Deliverable | Responsible | Supporting | Reviewer |
| --- | --- | --- | --- |
| Historical health data | Gemini | Sol | Astra |
| Mortality Risk Index | Sol | Gemini | Astra |
| Demographic vulnerability | Sol | Gemini | Astra |
| Zone/ward spatial risk | Sol | Gemini | Astra |
| SMS/WhatsApp alert API | Sol | Gemini | Astra |
| Municipal action-plan triggers | Sol | Gemini | Astra |
