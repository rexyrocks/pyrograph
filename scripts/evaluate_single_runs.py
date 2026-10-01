"""Replay one archived 9-km ECMWF run per day for a predeclared Jaipur month.

Each forecast target and its three lag days come from the SAME initialization.
The 00Z run's first Jaipur-local day is partial, so target offsets 4 and 5
are the first complete targets whose three lag days are also complete.
This is an exploratory weather-hazard evaluation, not an operational claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI

from backend.main import PredictionInput, _engineer_features
from backend.serving import load_runtime
from heatwave_pipeline import metric_report
from scripts.probe_forecast_archive import HOURLY_FIELDS

DEFAULT_START = date(2024, 5, 1)
DEFAULT_END = date(2024, 5, 31)
TARGET_OFFSETS = (4, 5)
LOCATION = {'latitude': 26.91, 'longitude': 75.79, 'timezone': 'Asia/Kolkata'}
MODEL = 'ecmwf_ifs'
FORECAST_HOURS = 192
PUBLICATION_LAG_HOURS_ASSUMED = 6
EXPECTED_UNITS = {'temperature_2m': '°C', 'relative_humidity_2m': '%',
                  'wind_speed_10m': 'km/h', 'surface_pressure': 'hPa',
                  'shortwave_radiation': 'W/m²', 'cloud_cover': '%'}


def request_json(endpoint: str, params: dict) -> tuple[str, bytes, dict]:
    url = endpoint + '?' + urlencode(params)
    raw = urlopen(url, timeout=120).read()
    return url, raw, json.loads(raw)


def aggregate_complete_days(payload: dict) -> tuple[dict[date, dict], dict]:
    if payload.get('timezone') != LOCATION['timezone']:
        raise ValueError('Forecast timezone does not match the local-day contract')
    units = payload.get('hourly_units', {})
    if any(units.get(name) != unit for name, unit in EXPECTED_UNITS.items()):
        raise ValueError('Forecast hourly units do not match the model input contract')
    hourly = payload.get('hourly', {})
    times = hourly.get('time', [])
    if not times or any(not isinstance(hourly.get(name), list) or len(hourly[name]) != len(times)
                        for name in HOURLY_FIELDS):
        raise ValueError('Forecast is missing required hourly fields')
    frame = pd.DataFrame({'date': [date.fromisoformat(item[:10]) for item in times]})
    for name in HOURLY_FIELDS:
        frame[name] = pd.to_numeric(hourly[name], errors='coerce')
    daily, coverage = {}, {}
    for local_day, group in frame.groupby('date', sort=True):
        missing = [name for name in HOURLY_FIELDS if group[name].isna().any()]
        ranges = {'temperature_2m': (-90, 65), 'relative_humidity_2m': (0, 100),
                  'wind_speed_10m': (0, float('inf')), 'surface_pressure': (0, float('inf')),
                  'shortwave_radiation': (0, float('inf')), 'cloud_cover': (0, 100)}
        invalid = [name for name, (low, high) in ranges.items()
                   if name not in missing and (not group[name].between(low, high).all()
                                               or (name == 'surface_pressure' and (group[name] == 0).any()))]
        complete = len(group) == 24 and not missing and not invalid
        coverage[local_day.isoformat()] = {'hours': len(group), 'complete': complete,
                                          'missing': missing, 'invalid': invalid}
        if not complete:
            continue
        daily[local_day] = {
            'tmax': float(group.temperature_2m.max()),
            'tmin': float(group.temperature_2m.min()),
            'tmean': float(group.temperature_2m.mean()),
            'rh_mean': float(group.relative_humidity_2m.mean()),
            'wind_speed_max': float(group.wind_speed_10m.max()),
            'pressure_mean': float(group.surface_pressure.mean()),
            'solar_radiation_sum': float(group.shortwave_radiation.sum() * 0.0036),
            'cloud_cover_mean': float(group.cloud_cover.mean()),
        }
    return daily, coverage


def record_for_target(target: date, daily: dict[date, dict]) -> PredictionInput | None:
    required = [target - timedelta(days=offset) for offset in range(4)]
    if any(day not in daily for day in required):
        return None
    values = {**daily[target]}
    for offset in (1, 2, 3):
        values[f'tmax_lag{offset}'] = daily[target - timedelta(days=offset)]['tmax']
        values[f'tmin_lag{offset}'] = daily[target - timedelta(days=offset)]['tmin']
    return PredictionInput(date=target, **values)


def replay(start: date, end: date, output: Path) -> dict:
    if end < start or (end - start).days > 92:
        raise ValueError('Select a chronological period of at most 93 runs')
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / 'raw-runs'
    raw_dir.mkdir(exist_ok=True)
    runtime = FastAPI()
    load_runtime(runtime)
    if runtime.state.contract['model_version'] != 'jaipur-fixed-v2':
        raise ValueError('This replay is predeclared for the corrected Jaipur v2 model')

    verify_url, verify_raw, verify = request_json('https://archive-api.open-meteo.com/v1/archive', {
        **LOCATION, 'start_date': (start + timedelta(days=min(TARGET_OFFSETS))).isoformat(),
        'end_date': (end + timedelta(days=max(TARGET_OFFSETS))).isoformat(),
        'daily': 'temperature_2m_max', 'models': 'era5',
    })
    (output / 'verifying-reanalysis.json').write_bytes(verify_raw)
    observed = dict(zip((date.fromisoformat(day) for day in verify['daily']['time']),
                        verify['daily']['temperature_2m_max'], strict=True))
    run_manifests, rows = [], []
    run_day = start
    while run_day <= end:
        run = run_day.isoformat() + 'T00:00'
        url, raw, payload = request_json('https://single-runs-api.open-meteo.com/v1/forecast', {
            **LOCATION, 'models': MODEL, 'run': run, 'forecast_hours': FORECAST_HOURS,
            'hourly': ','.join(HOURLY_FIELDS),
        })
        (raw_dir / f'{run_day.isoformat()}-00z.json').write_bytes(raw)
        daily, coverage = aggregate_complete_days(payload)
        manifest = {'run_utc': run, 'source_url': url, 'sha256': hashlib.sha256(raw).hexdigest(),
                    'coverage': coverage, 'score_status': {}}
        for offset in TARGET_OFFSETS:
            target = run_day + timedelta(days=offset)
            record = record_for_target(target, daily)
            truth_tmax = observed.get(target)
            if record is None or truth_tmax is None:
                manifest['score_status'][str(offset)] = 'missing_complete_forecast_or_verification'
                continue
            values, (_, p95, _) = _engineer_features(record, runtime.state.climatology)
            matrix = xgb.DMatrix(np.asarray([[values[name] for name in runtime.state.features]],
                                            dtype=np.float32), feature_names=runtime.state.features)
            probability = float(runtime.state.model.predict(matrix)[0])
            rows.append({'run_utc': run, 'target_date': target.isoformat(),
                         'target_offset_calendar_days': offset,
                         'forecast_tmax': record.tmax, 'verifying_reanalysis_tmax': float(truth_tmax),
                         'p95': p95, 'observed_heatwave_label': int(truth_tmax >= p95),
                         'model_probability': probability, 'model_predicted': int(probability >= .5),
                         'temperature_threshold_predicted': int(record.tmax >= p95)})
            manifest['score_status'][str(offset)] = 'scored'
        run_manifests.append(manifest)
        run_day += timedelta(days=1)

    (output / 'run-manifests.json').write_text(json.dumps(run_manifests, indent=2) + '\n')
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError('No complete single-run records could be scored')
    frame.to_csv(output / 'scored-days.csv', index=False)
    metrics = {}
    for offset in TARGET_OFFSETS:
        group = frame[frame.target_offset_calendar_days == offset]
        if group.empty:
            metrics[str(offset)] = {'rows': 0}
            continue
        truth = group.observed_heatwave_label.astype(int)
        metrics[str(offset)] = {
            'rows': len(group), 'positive_labels': int(truth.sum()),
            'model': metric_report(truth, group.model_predicted.astype(int)),
            'temperature_threshold_baseline': metric_report(truth, group.temperature_threshold_predicted.astype(int)),
            'forecast_tmax_mae_c': float(np.mean(abs(group.forecast_tmax - group.verifying_reanalysis_tmax))),
        }
    report = {
        'status': 'exploratory_single_run_9km_weather_hazard_replay',
        'period': {'first_run': start.isoformat(), 'last_run': end.isoformat(),
                   'selection': 'every 00Z initialization in the requested consecutive date range'},
        'location': LOCATION, 'forecast_model': MODEL, 'forecast_resolution': '9 km',
        'run_initialization_utc': '00:00', 'target_offsets_calendar_days': TARGET_OFFSETS,
        'assumed_publication_lag_hours': PUBLICATION_LAG_HOURS_ASSUMED,
        'earliest_target_start_after_assumed_publication_hours': {
            str(offset): offset * 24 - 5.5 - PUBLICATION_LAG_HOURS_ASSUMED for offset in TARGET_OFFSETS},
        'heatwave_model_version': runtime.state.contract['model_version'],
        'label': 'ERA5 reanalysis Tmax >= fixed Jaipur 2015–2018 P95; not observed health outcomes',
        'verifier_source_url': verify_url, 'verifier_sha256': hashlib.sha256(verify_raw).hexdigest(),
        'retrieved_at': datetime.now(UTC).isoformat(), 'metrics': metrics,
        'limitations': [
            'Publication time is assumed at 6 hours after initialization, not observed for each run.',
            'The initialization time is not the user-visible issue time.',
            'Hourly aggregation approximates the daily weather inputs used in training.',
            'ERA5 reanalysis is a verification proxy, not an observed station or health outcome.',
            'Historical test years were inspected during development; this is not fresh external validation.',
            'Probabilities are uncalibrated; no health or ward-level performance is measured.',
        ],
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument('--end', type=date.fromisoformat, default=DEFAULT_END)
    parser.add_argument('--output-dir', type=Path, default=Path('work/single-run-replay-2024-05'))
    args = parser.parse_args()
    print(json.dumps(replay(args.start, args.end, args.output_dir), indent=2))
