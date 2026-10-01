# Pyrograph phase gate — 2 October 2026

This is the honest end-to-end status of the local `sol/integeration` branch after the second implementation pass. The code now covers more of the forecast, data-quality and municipal workflow path. **No phase requiring current ward data, health outcomes or real delivery is complete end to end.** The public site has not been changed by this local work.

## Work completed in this pass

- The dashboard explains the simple forecast-temperature P95 rule next to the preliminary classifier result and flags disagreement. The live weather proxy requires exact Jaipur-local dates, timezone and units before using the source values.
- A locked April–June 2026 single-run 9-km ECMWF replay retrieved 91 initialized forecasts. Per lead, 78 target records passed the feature contract; 13 were omitted. There were **zero ERA5 Tmax ≥ fixed-P95 positive labels**, so this period cannot measure event detection. Eleven runs had physically impossible negative radiation and two had missing hourly weather; affected days were excluded and recorded rather than repaired. See `docs/data/single-run-2026-result.md`.
- Current ward source checks confirmed a 150-ward municipal structure. DataMeet's reusable Jaipur GeoJSON contains only 77 polygons, so it remains an inspected historical source and is not used for present ward risk. Public surveillance guidance is available, but no suitable daily Jaipur health-outcome series was found. See `docs/data/current-ward-and-health-gates.md`.
- Municipal workflows and offline alert receipts now support opt-in transactional SQLite local storage. Idempotency, duplicate suppression, transitions and audit history survive process restart; a one-shot job advances overdue workflows once. The default mode and alert provider remain offline. A trusted scheduler and mounted persistent volume are required in any deployment using that store.
- A GitHub Actions workflow has been added to run backend tests, the offline rehearsal, frontend validation/build and Docker image smoke on a Docker-capable runner. It has **not run**, because this branch has not been pushed.

## Phase status and the remaining gate

| Phase | State | Why it is not end-to-end complete |
|---|---|---|
| 0 — requirements and baseline | Partial | The SIH official problem-statement endpoint still returns HTTP 403. Community transcriptions support the scope, but exact official wording and a signed-off pilot geography remain unverified. |
| 1 — data | Partial | Weather archives are reproducible. Current 150-ward reusable vectors, matching demographic measurements and daily local health outcomes are absent from accessible public sources. |
| 2 — forecasting model | Partial | The integrity-checked model serves consistently, but the May 2024 positive-event single-run replay did not beat the temperature rule; the May 2025 single-run and April–June 2026 windows had no positive labels. Actual release times, official/station verification, live-feed equivalence and more positive events remain unmeasured. |
| 3 — human thermal stress | Partial | Daily WBGT/UTCI estimates are integrated with applicability checks, but the radiation/globe-temperature assumptions have not been validated against local exposure measurements or peak-hour conditions. |
| 4 — GIS | Blocked on current data | The official municipal profile says 150 wards, while the inspected reusable GeoJSON has 77 and no dependable vintage. Showing it as a current ward-risk map would misstate geographic precision. |
| 5 — mortality/hospitalisation risk | Blocked on outcomes | Public guidance describes surveillance reporting, but there is no compatible dated Jaipur outcome series to fit and validate a daily local health model. The API correctly returns `mortality_probability: null`; the existing index is uncalibrated. |
| 6 — alerts and municipal action | Partial | Offline SMS/WhatsApp simulation, role actions, audit history and opt-in local alert/workflow persistence work. Real messages require an approved provider, recipients/consent, authenticated operators, production-grade storage and a deployed escalation scheduler. |
| 7 — dashboard and journeys | Partial | City-level forecast, thermal context, planning scenario and source/freshness checks work. Current ward GIS, operator console and localisation are absent. |
| 8 — release | Partial | 59 Python tests, four Node tests, both frontend builds, offline rehearsal and a Python 3.12 startup/inference/thermal/SQLite check pass locally. Docker/Podman are unavailable here, so the exact image smoke test has not run. The new CI workflow has not run, and no deployment or real-delivery trial has occurred. |

## External facts behind the data gates

The [Jaipur municipal profile](https://jaipurmc.org/Presentation/AboutMcjaipur/CityProfile.aspx) states 150 wards; the [Rajasthan GIS manual](https://rajdharaa.rajasthan.gov.in/citizenudh/PDF/User_Manual_Urban_GIS_Portal.pdf) documents a ward layer but does not provide a clearly reusable current vector export. [DataMeet](https://github.com/datameet/Municipal_Spatial_Data) licenses its repository under CC BY 4.0 by default, but its [Jaipur file](https://github.com/datameet/Municipal_Spatial_Data/blob/master/Jaipur/Jaipur_Wards.geojson) contains 77 polygons. The [NCDC surveillance guidance](https://ncdc.mohfw.gov.in/uploads/pdf/heat12.pdf) specifies daily/district reporting forms; that guidance is not a published local outcome time series. The [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api) distinguishes run initialization from public availability, so the replay's six-hour publication lag remains an assumption.

## Next workable steps

1. Run the new CI on a reviewed branch and resolve any Linux/container failures before release. Exercise real frontend/backend integration against a staging deployment, with a rollback plan.
2. Secure a current 150-ward vector and compatible ward population data with provenance and reuse terms. Validate spatial joins before building a choropleth.
3. Secure aggregated daily Jaipur heat-related cases/deaths with case definitions and reporting coverage. Keep mortality probability unavailable until an independent health-model evaluation is possible.
4. Collect prospectively archived live-feed forecasts with observed publication times and independent station/official verification, including enough positive heat events to test detection and calibration.
5. Obtain an approved messaging provider, recipient consent and operator identities before enabling delivery; move local alert/workflow storage to a supported managed service, and deploy the escalation scheduler.

No synthetic fixture is presented as current Jaipur demographic data, no historical ward geometry is presented as current, and no real SMS/WhatsApp message has been sent.
