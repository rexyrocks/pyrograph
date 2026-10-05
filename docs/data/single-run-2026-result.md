# Later-year single-run replay — Jaipur, April–June 2026

This result follows the [locked plan](single-run-2026-preanalysis.md): every 00 UTC ECMWF IFS HRES 9-km initialization from 1 April to 30 June 2026, target offsets 4 and 5 calendar days, unchanged `jaipur-fixed-v2` model and 0.5 cutoff, and unchanged forecast-Tmax ≥ fixed P95 comparison rule. It is a retrospective **weather-hazard** check using final ERA5 reanalysis, not a mortality or official-warning evaluation.

| Target offset | Runs requested | Scored | Omitted | ERA5 positive labels | Classifier TP/FP/FN | Rule TP/FP/FN | Forecast Tmax MAE |
|---:|---:|---:|---:|---:|---|---|---:|
| day 4 (~84.5 h after assumed availability) | 91 | 78 | 13 | **0** | 0 / 1 / 0 | 0 / 2 / 0 | 1.65°C |
| day 5 (~108.5 h after assumed availability) | 91 | 78 | 13 | **0** | 0 / 0 / 0 | 0 / 1 / 0 | 1.65°C |

With **no positive labels**, CSI, precision and recall do not measure detection here. The machine report encodes undefined ratios as zero for consistency with the existing metric helper; those zeros must not be read as measured heatwave skill. The classifier made fewer false alerts on these negative targets, but the period cannot show whether either method would detect a true event. All 92 ERA5 target dates in the verification range were below the fixed P95 threshold (one was just 0.005°C below it).

## Coverage and source quality

All 91 archived runs were retrieved. The replay requires complete 24-hour Jaipur-local weather for the target and each of its three lag days from the same run. Thirteen runs per lead failed that requirement: 11 runs contained at least one physically impossible negative shortwave-radiation hourly value (the first example was −15,295 W/m²), and two runs contained missing hourly weather fields. The validator **excludes** affected days and records the exact field in the per-run coverage; it does not replace, clip or impute values. All other scored target/lag days met the input contract.

Raw JSON responses, exact URLs and hashes, per-run coverage, scored rows and the machine-readable report are under ignored `work/single-run-replay-2026-hot-season/`. Re-run `python3 -m scripts.evaluate_single_runs --start 2026-04-01 --end 2026-06-30 --output-dir work/single-run-replay-2026-hot-season` to retrieve again. The external archive may change; saved hashes identify this retrieval. The public [Single Runs API](https://open-meteo.com/en/docs/single-runs-api) states that initialization time is not publication time and that global runs usually take several hours to publish.

The model remains **preliminary**. This season does not overturn the 2024 positive-event comparison, where the temperature rule was slightly better, and does not supply a health outcome. Advance-warning sign-off still needs more positive events, independent station or official verification, observed publication times, live-feed equivalence and reliability checks.
