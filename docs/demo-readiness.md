# Demo corrections and verification — 14 September 2026

Branch: `sol/integeration`, changes after `a9336fe`.

## Implemented

- Removed unsupported ward exposure and leakage-safe claims.
- Added a persistent, mobile-visible mode banner. Samples require an explicit
  click, use sample-day labels, and never substitute automatically for live
  data. Missing, stale, future-dated, malformed or nonconsecutive forecasts hide
  the heat summary and planning index. Requests have timeouts; refresh occurs
  every minute. Sample mode can be exited without reloading.
- The planning index, band, drivers and municipal recommendations come from
  `/risk/assess` using full input precision. There is no independent frontend
  formula. An unavailable risk API leaves the score unavailable.
- Fixed the production batch entrypoint's first-record persistence context.
- Included the synthetic CSV in the Docker build context and image recipe.
- Replaced the inert operations tab with a statement that operations are
  demonstrated through the API. Mobile navigation opens, follows links and closes.
- Added a fixed-reference evaluation and explicitly marked legacy metrics as
  preliminary, retrospective and affected by future-data contamination/model
  selection. Serving model artifacts were not replaced.

## Evaluation

Fixed 2015–2018 climate reference, fitting on 2019–2021 (1,096 days), selection
on 2022 (365 days), and test on 2023–2024 (731 days). XGBoost is selected using
2022 metrics before evaluating the test period. New test precision 0.8333,
recall 0.8491, F1 0.8411, CSI 0.7258; confusion matrix [[669, 9], [8, 45]].
The experiment uses realised weather and a short reference, so it does not
establish advance forecast skill, calibrated probabilities, mortality risk or
statewide performance. Earlier inspection of the test period also means it is
not a fresh external validation. The changed label/reference definition means
new and legacy metric numbers are not directly comparable.

Full machine-readable output: `evaluation-retrospective-v2.json`.

## Verification executed

- 42 backend tests passed. New regressions cover both-entrypoint persistence,
  full-precision boundary scoring, unaffected training/selection features and
  labels when held-out weather is perturbed, and demographic API availability.
- Two Node validation tests passed, including stale/future dates, malformed
  fields, nonconsecutive days, local date rollover and full probability precision.
- Sites/Vinext and Vercel production frontend builds passed.
- Targeted page/forecast validation lint passed; full-project pre-existing
  generated UI lint issues have not been repaired.
- The local production API rehearsal passed: delivery simulation, replay,
  suppression, two-attempt failure, acknowledgement, escalation eligibility,
  and 404 after restarting in-memory state. Real delivery remains disabled.
- Headless Chrome tested the built frontend against controlled weather responses
  and the real local production risk endpoint. Four scenarios passed: live
  mode/API boundary agreement (29.8 / Low at probability 0.255); upstream
  failure/sample entry and exit; stale data rejection/sample entry and exit;
  and incomplete fixture disabling, complete fixture loading, and 390px mobile
  navigation without page overflow. No browser page errors occurred. Desktop,
  mobile and unavailable screenshots were visually inspected. Weather fixtures
  are deterministic test inputs; this is not an Open-Meteo availability test.

## Remaining gate

The actual backend Docker image was **not built or smoke-tested** because this
machine has no Docker, Podman or Colima runtime installed. The image test is
prepared as `python3 -m scripts.smoke_image`: it builds the exact Dockerfile,
starts a temporary loopback-only container, verifies health and all five
demographic fixtures, checks missing-key rejection, and removes that temporary
container. Run it on a Docker-enabled host before deployment sign-off.

An initial Chrome launch failed on temporary-profile disk space; using
`TMPDIR=/private/tmp` resolved it and the full browser run then passed.

## Reproduction

```bash
python3 -m unittest discover -s tests -q
python3 -m scripts.rehearse_demo
python3 heatwave_pipeline.py --data data/jaipur_daily_2015_2024.csv --output-dir work/retrospective-v2
python3 -m scripts.smoke_image
```

For browser checks, serve `frontend/dist-vercel` on loopback port 18765 and run
`backend.vercel_app:app` on loopback port 18766 with
`HEATSHIELD_API_KEY=local-browser-test-key-00000000000000` and
`HEATSHIELD_ALERT_PROVIDER=demo`. From `frontend/`, run
`node --test tests/outlook.test.mjs` and `node tests/browser-demo.mjs`.
The browser script requires Playwright and installed Chrome; if using a shared
Playwright installation, set `PLAYWRIGHT_PACKAGE_PATH` to that package path.
`DEMO_QA_OUTPUT` chooses where screenshots and results.json are saved.
The documented key is exclusively a local test credential.

## Boundaries

No publish, push or commit was performed for these changes. Real messaging,
authenticated ownership, durable receipts, automatic escalation, Rajasthan
location configuration, verified health/demographic datasets and provider
timeout reconciliation remain outside this demo correction pass.
