# Fixed-lead weather-hazard pilot — Jaipur, April–June 2025

The corrected Pyrograph classifier was evaluated on a **predeclared 91-day period** at fixed 3-, 4-, and 5-day lead offsets. The project did not train or select a model on these dates. The verification label is final ERA5 reanalysis Tmax at or above Pyrograph's fixed 2015–2018 P95 threshold. This is a heatwave-label proxy, not an observed health outcome or official IMD alert.

| Lead (days) | Days | Positive labels | Classifier CSI | Temperature-rule CSI | Classifier precision | Temperature-rule precision |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 91 | 3 | 0.200 | 0.400 | 0.222 | 0.500 |
| 4 | 91 | 3 | 0.167 | 0.250 | 0.182 | 0.286 |
| 5 | 91 | 3 | 0.222 | 0.286 | 0.250 | 0.333 |

Both methods found two of the three positive days at every lead. The classifier produced more false positives and had lower CSI than the temperature rule at every lead. With only three positives and one season, uncertainty is large. These results are exploratory evidence against an unqualified claim of 3–5-day superiority, not a final deployment verdict.

## How it was constructed

- Archived ECMWF IFS 0.25° hourly fields from Open-Meteo's [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api); fixed offsets 0–5 days supplied target weather and lag weather.
- Twenty-four Jaipur-local hourly values were aggregated to each day. All required fields were present for 91 target days at each lead. Sunlight was converted from W/m² hourly means to MJ/m²/day.
- Final ERA5 daily Tmax from the [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) supplied the verification proxy.
- The currently bundled `jaipur-fixed-v2` model was used without refitting. The baseline was forecast Tmax ≥ the same fixed P95 threshold. Classification cutoff was 0.5.
- Exact source URLs, hashes, daily rows, coverage and machine-readable results are saved under ignored `work/archived-lead-evaluation/` in the local checkout. Re-run `python3 -m scripts.evaluate_archived_leads` to regenerate.

## Limits that govern the next decision

This fixed-offset product may combine several forecast initialization cycles across a day. Its adjacent lead offsets only approximate the lag values that a single issued forecast would provide. The 0.25° archive differs from Pyrograph's live weather feed and the 9 km single-run archive. Hourly aggregation differs from the daily training products. ERA5 is reanalysis, not a station observation. A rigorous operational replay still needs one known issued run, its publication time, the actual first-day lag inputs, and repeated forecast dates. No health-risk accuracy is measured here.

**Next modelling decision:** preserve this pilot and its baseline, then build an as-issued, single-run 9 km replay with enough new heat seasons. Keep the existing classifier preliminary until it beats an appropriate simple rule on that evidence. Do not tune the model on this pilot and present these same dates as untouched validation.
