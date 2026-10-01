# Locked 2026 single-run replay plan

Written before retrieving or scoring the 2026 archive. This is a later-year **weather-hazard** check of the existing `jaipur-fixed-v2` package, not a mortality or official-warning validation.

- Include every Jaipur ECMWF IFS HRES 9-km 00 UTC initialization from **1 April through 30 June 2026**, inclusive, with no selection by temperature, label or forecast outcome.
- Evaluate target offsets **4 and 5 calendar days** after initialization. Complete local target and three lag days must all come from the same run. With six hours of assumed publication latency, target local midnight is about 84.5 or 108.5 hours after availability. The archive does not prove each run's actual publication time.
- Compare the existing XGBoost probability at the frozen 0.5 cutoff with the frozen rule `forecast Tmax >= fixed 2015–2018 calendar-day P95`. Neither model, cutoff nor reference is changed after seeing this period.
- Verify against final ERA5 reanalysis daily Tmax at the same location. Report all run availability, omitted records and the reason for omission. Report the positive-label count, confusion matrix, CSI, precision, recall and forecast Tmax MAE at each target offset. Report zeros with no positives as undefined detection skill in prose.
- Do not use 2026 results to select or tune a new model and then call the same dates final validation. Do not claim superiority from a small rare-event difference. Operational sign-off still requires independent observed station or official labels, true publication times, live-feed equivalence and health outcome data for mortality claims.

Source: [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api), which states that ECMWF HRES 9-km runs are archived and distinguishes initialization from public availability. The provider also notes a May 2026 IFS cycle change, a possible distribution shift to retain in interpretation.
