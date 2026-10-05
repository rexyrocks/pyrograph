# Track 1 — Core risk and integration

## Owner

Codex / primary integration owner

## Objective

Maintain the shared backend contracts and connect heatwave prediction,
demographic vulnerability, the planning index, and the frontend without making
unsupported mortality claims.

## Already complete

- Heatwave single and batch prediction APIs
- Model health and metadata APIs
- Prototype heat-health planning index
- Explicit null mortality probability
- Synthetic demographic fixture validation
- Protected demographic API
- Interactive vulnerability scenario
- Basic municipal action recommendations

## Remaining tasks

1. Review and merge outputs from the other three tracks.
2. Connect verified aggregate datasets when Track 3 approves them.
3. Replace remaining Jaipur constants with the location registry.
4. Connect the Track 2 alert and workflow services to shared APIs.
5. Add integration and end-to-end tests.
6. Run final frontend and backend builds.
7. Prepare deployment and demo smoke tests.

## Owned files

- `backend/main.py`
- `backend/vercel_app.py`
- `backend/risk.py`
- `backend/demographics.py`
- Shared frontend integration
- Shared API tests
- `deceision.md`

Other tracks must request contract changes instead of directly modifying these
files.

## Acceptance checks

- Every displayed metric has provenance and data-kind information.
- Synthetic, historical, estimated, and live data are distinguishable.
- Mortality probability remains unavailable until genuinely calibrated.
- All backend tests and both frontend builds pass.
- No secrets or personal data are committed.

## Handoff

Provide a final integration report listing merged tracks, test results, known
limitations, deployment status, and remaining operational-data requirements.
