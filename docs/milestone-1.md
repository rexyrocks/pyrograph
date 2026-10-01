# Milestone 1 — corrected serving and thermal integration

For the later implementation and current phase status, see `milestone-2.md`.

Implemented locally on `sol/integeration`, starting from `f21ca56`, 2 October 2026.

## Delivered

- Immutable `artifacts/jaipur-fixed-v2` package: native XGBoost model, 366-day fixed climate table, evaluation and manifest with hashes, input units, data digest and limitations.
- Exporter refuses to overwrite a version directory. Both API entrypoints use the same loader, reject mixed legacy overrides, verify hashes and feature order, and report model version/reference period.
- Test-period API feature construction and model predictions reproduce the corrected evaluation across all 731 days. The bundle uses the selected model without a post-test refit.
- Prediction responses include daily WBGT/UTCI estimates and explicit availability. UTCI applicability limits are enforced. Weather range checks reject invalid humidity, negative wind/radiation and nonpositive pressure.
- Dashboard shows dated thermal estimates, assumptions and model provenance. Older responses lacking the corrected contract are rejected rather than silently displayed.
- Container and serverless manifests include the bundle and thermal dependencies. The container smoke script now verifies actual model and thermal inference.

## Verified

49 Python tests, two Node tests, Vercel frontend production build and the offline operations rehearsal pass. Four headless-Chrome scenarios passed: planning-index boundary agreement, upstream failure, stale forecasts and mobile/fixture interaction. Browser weather inputs were controlled fixtures and the browser run used the real local risk API. The backend tests separately exercised corrected-model and thermal prediction. These checks do not validate forecast accuracy or the public deployment.

The Docker image could not be built because Docker is absent. Local Python uses 3.13; the container targets 3.12, so image validation remains a release gate. No push or deployment has occurred.

## Scientific boundaries

The new package corrects reference-period contamination and test-driven model selection. The test years were previously inspected; results remain preliminary. A threshold classifier is also an essential baseline because the label is defined by Tmax exceeding a reference threshold. Retrospective classification with realised weather does not establish advance forecast skill.

Thermal estimates preserve the existing daily aggregation and approximate radiant/globe temperature assumptions. They are not measured WBGT, peak-hour exposure, calibrated mortality risk or local scientific validation. Integration and numerical checks are complete; thermal-method validation is not. [pythermalcomfort documentation](https://pythermalcomfort.readthedocs.io/en/latest/documentation/models.html) describes returning unavailable UTCI values outside its applicability range; this runtime enables that behavior.

## Local reproduction

```bash
python3 -m unittest -q
node --test frontend/tests/outlook.test.mjs
python3 -m scripts.rehearse_demo
cd frontend
npm run build:vercel
```

Set `HEATWAVE_BUNDLE_DIR` to a complete integrity-checked bundle to select another version. The old per-file overrides now fail with a migration message. Existing legacy outputs remain for audit only. A rollback of this entire milestone requires the previous code/dependency revision as well as its artifacts; do not point the new loader at loose legacy files.

Deploy backend and frontend as a coordinated release: a new frontend intentionally rejects old-backend responses. Verify authenticated `/model/info`, prediction provenance, thermal output and the five-day proxy before shifting traffic. The public site is unchanged by this local work.

## Phase gates

| Phase | State | Remaining acceptance condition |
|---|---|---|
| 0 — baseline and requirements | Baseline recorded; original SIH verification pending | Confirm exact original statement and pilot geography |
| 1 — data | Public-source inventory, fixed-lead archive and 62 archived individual 9-km ECMWF runs evaluated | Reusable ward vectors, compatible demographics, local health outcomes, observed issue times and independent station/official verification |
| 2 — modelling and handoff | Serving handoff complete; fixed-lead and single-run pilots performed, including a locked 2026 hot-season replay | More independent positive events and calibration; 2026 had no positive labels, while the 2024 positive-event pilot did not show classifier advantage |
| 3 — thermal integration | API/UI integration complete | Independent scientific validation and improved exposure inputs |
| 4 — GIS | Not implemented | Verified geometry and local data joins |
| 5 — health model | Data-dependent | Outcome data, justified model and held-out validation |
| 6 — response | Offline simulation plus opt-in transactional SQLite municipal workflow and one-shot escalation job | Durable alert storage, operator identity, real provider/consent integration, mounted database and deployed scheduler |
| 7 — UI | First milestone browser-verified | GIS and operator journeys plus localisation |
| 8 — release | Not started | Container, deployment, reliability and submission evidence |
