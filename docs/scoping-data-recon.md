# Scoping & Data Recon

## Intro

This covers the scoping and data groundwork for SIH26083 (Extreme Heatwave
Early Warning). It finalizes the heatwave threshold criteria and provides
the raw historical weather data the pipeline trains on. Anyone picking up
downstream work (WBGT/UTCI computation, dashboard, alert API) should read
this first to understand what "heatwave" means in this project and where
the source data comes from — two things that need to stay consistent across
every module.

## Data source

- Historical daily weather pulled from the **Open-Meteo historical archive
  API** (no API key required).
- Target: **Jaipur**, 2015–2024, daily resolution.
- Columns: `date, tmax, tmin, tmean, rh_mean, wind_speed_max,
  pressure_mean, solar_radiation_sum, cloud_cover_mean`.
- 3,653 rows, no missing values, no date gaps — verified before use.
- File: `data/jaipur_daily_2015_2024.csv`.

## IMD threshold rules (finalized)

Absolute tmax threshold by station type:
- Plains: 40°C (Jaipur's applicable threshold)
- Coastal: 37°C
- Hilly: 30°C

Full IMD criteria (for reference/cross-validation, not used as the training
label — see reconciliation note below):
- Heatwave: `tmax >= 40°C` AND departure from normal `>= 4.5°C`
- Severe heatwave: departure `>= 6.5°C`, OR `tmax >= 45°C` regardless of
  departure
- `tmax >= 47°C` is heatwave regardless of departure
- Must hold for >= 2 consecutive days to count as an event (a single hot
  day is not a heatwave under IMD's definition)

"Normal" here means a self-computed 10-year day-of-year climatology
(smoothed +/-7 days), since we don't have IMD's official 30-year
(1981–2010) station normal.

## Percentile framework (finalized)

90th/95th/98th percentile of warm-season (Apr–Jun) tmax, computed from this
station's own historical record — a data-driven fallback/cross-check
alongside the IMD rule.

## Reconciliation with the training pipeline

`heatwave_pipeline.py` already implements labeling using a **leave-one-year-
out (LOYO) percentile climatology**: circular ±7-day calendar window, P95 =
`heatwave`, P98 = `severe`, with no persistence rule baked into the training
label (persistence is deliberately left to the downstream alert layer).

This is a different — and more rigorous — method than the plain 10-year
day-of-year climatology described above, since LOYO avoids leaking each
year's own data into its own normal. **The LOYO-percentile method in
`heatwave_pipeline.py` is the labeling approach used for model training.**

The IMD absolute/departure rule above was validated separately against
known real events (see below) as a sanity check on the underlying data and
threshold assumptions, and remains useful as an interpretable, standards-
based reference for the alert-layer / dashboard side of the project (e.g.
communicating risk to municipal users in IMD's own familiar terms), even
though it isn't what the model was trained on.

## Validation check

Cross-checked threshold logic against known real Jaipur heatwave events:
IMD-rule flags correctly surfaced severe heat in **May 2016** (peak 46.0°C)
and **May 2024** (peak 46.6°C), matching widely-reported Rajasthan
heatwaves in those windows. 2019 and 2024 also emerged as the
highest-frequency heatwave years in the 2015–2024 record, consistent with
known regional heatwave activity.

## Open items for the team

- `wbgt` and `utci` are declared as placeholder features in
  `heatwave_pipeline.py` (`OPTIONAL_THERMAL_FEATURES`) — whoever builds the
  Heat Stress Index module should populate these and add them to
  `ACTIVE_OPTIONAL_FEATURES` once ready.
- Confirm whether other cities/states beyond Jaipur are in scope before
  more data is pulled.