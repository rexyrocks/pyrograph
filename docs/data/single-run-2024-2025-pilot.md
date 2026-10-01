# Single-run 9-km forecast replay — Jaipur, May 2024 and May 2025

This replay evaluates **every 00 UTC ECMWF IFS HRES 9-km initialization from 1–31 May** in each year. Each forecast day and all three lag days come from the *same archived run*. The model, 0.5 classification cutoff, P95 heatwave label and temperature-threshold comparison were kept fixed. The May 2024 dates were in an earlier retrospective test period; this is exploratory and cannot serve as fresh final validation. No model tuning was performed on either replay.

The 00 UTC initialization begins at 05:30 in Jaipur, so its first local day is incomplete. A target on calendar day 3 would require that partial day as a lag and is rejected. Calendar-day offsets 4 and 5 have complete target and lag days. Assuming a run becomes available six hours after initialization, the target local midnight is **84.5 or 108.5 hours** after publication, respectively. These are *assumed* issue-to-target leads; the archive identifies initialization, not the exact public release time. [Open-Meteo's Single Runs documentation](https://open-meteo.com/en/docs/single-runs-api) describes 9-km ECMWF archive coverage since March 2024 and typical global-model processing latency of four to six hours.

| Initialization month | Target offset | Scored runs | ERA5 heatwave labels | Classifier CSI | Temperature-rule CSI | Classifier TP/FP/FN | Rule TP/FP/FN | Forecast Tmax MAE |
|---|---:|---:|---:|---:|---:|---|---|---:|
| May 2024 | day 4 | 31 | 5 | 0.385 | **0.417** | 5 / 8 / 0 | 5 / 7 / 0 | 1.28°C |
| May 2024 | day 5 | 31 | 5 | 0.333 | **0.364** | 4 / 7 / 1 | 4 / 6 / 1 | 1.31°C |
| May 2025 | day 4 | 31 | 0 | undefined for detection | undefined for detection | 0 / 0 / 0 | 0 / 0 / 0 | 1.85°C |
| May 2025 | day 5 | 31 | 0 | undefined for detection | undefined for detection | 0 / 0 / 0 | 0 / 0 / 0 | 2.34°C |

The machine-readable metrics encode CSI as zero when there are no positives or positive predictions; for May 2025, that number should not be interpreted as measured detection skill. Both methods made no positive predictions in that month. The May 2024 temperature rule had one fewer false positive at each offset, with the same true-positive and false-negative counts. The observed differences are small relative to the five positive labels. This reinforces the earlier [0.25° fixed-lead pilot](fixed-lead-2025-pilot.md): the current classifier has **not demonstrated an advantage** over a simple forecast-temperature threshold at 3–5-day notice.

## Method and reproducibility

- Archived individual forecasts: [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api), `models=ecmwf_ifs`, 192 hourly forecast values per run, Jaipur coordinates 26.91°N, 75.79°E and `Asia/Kolkata` timezone.
- Targets and lags use only complete 24-hour local forecast days within their own run. All 62 target records per month were complete. The script rejects changed units and missing hours before scoring.
- The same `jaipur-fixed-v2` model bundle used by the API computes predictions with its exact feature order and fixed 2015–2018 calendar-day reference.
- Verification proxy: final ERA5 daily Tmax from the [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api). A positive label is ERA5 Tmax ≥ the fixed P95 reference. The comparison rule is forecast Tmax ≥ that same P95.
- `python3 -m scripts.evaluate_single_runs --start 2024-05-01 --end 2024-05-31 --output-dir work/single-run-replay-2024-05` reproduces the first replay; substitute 2025 for the second. Raw responses, exact URLs, hashes, coverage, scored CSV and reports are under these ignored local `work/` directories.

This is a **weather-hazard** replay. ERA5 is gridded reanalysis, not station verification, an official IMD alert, or a health outcome. Hourly-derived daily features differ from the daily products used in training. The archive run is an individual ECMWF forecast, while the live application uses Open-Meteo's best-match feed; its deployed feed may select or stitch other models. The replay assumes six hours to publication and does not prove exactly when a historical run reached users. Outcomes are concentrated in one location and a few weeks. No ward-level or mortality-risk accuracy is established.

**Decision gate:** keep the classifier marked preliminary and retain the temperature rule as a required benchmark. Before operational alert claims, replay multiple untouched hot seasons or prospective forecasts with observed publication times, independent station or official verification, explicit missingness, and uncertainty around rare-event metrics. Keep any health-risk model separate until local outcomes are available.
