"""Evaluate 2025 hot-season fixed-lead weather-hazard classifications.

Exploratory weather-hazard evidence only: fixed-lead 0.25-degree forecasts are
not a complete as-issued run, and verifying labels use reanalysis, not observed
health outcomes. The chosen period and comparison rule are fixed below.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, UTC
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI

from backend.serving import load_runtime
from heatwave_pipeline import metric_report

START = date(2025, 4, 1)
END = date(2025, 6, 30)
FETCH_START = START - timedelta(days=3)
LEADS = (3, 4, 5)
ALL_LEADS = range(0, 6)
MODEL = 'ecmwf_ifs025'
LOCATION = {'latitude': 26.91, 'longitude': 75.79, 'timezone': 'Asia/Kolkata'}
HOURLY = ('temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
          'surface_pressure', 'shortwave_radiation', 'cloud_cover')
OUTPUT = Path('work/archived-lead-evaluation')


def fetch(endpoint: str, params: dict) -> tuple[str, bytes, dict]:
    url = endpoint + '?' + urlencode(params)
    raw = urlopen(url, timeout=120).read()
    return url, raw, json.loads(raw)


def field_name(name: str, lead: int) -> str:
    # The API emits day-0 as the unsuffixed base field.
    return name if lead == 0 else f'{name}_previous_day{lead}'


def aggregate_fixed_leads(hourly: dict) -> tuple[dict[tuple[date, int], dict], dict]:
    times = hourly.get('time', [])
    fields = [field_name(name, lead) for lead in ALL_LEADS for name in HOURLY]
    if not times or any(not isinstance(hourly.get(field), list) or len(hourly[field]) != len(times) for field in fields):
        raise ValueError('Fixed-lead response is missing required hourly fields')
    frame = pd.DataFrame({'date': [date.fromisoformat(value[:10]) for value in times]})
    for field in fields:
        frame[field] = pd.to_numeric(hourly[field], errors='coerce')
    daily, coverage = {}, {}
    for target_date, group in frame.groupby('date', sort=True):
        for lead in ALL_LEADS:
            columns = {name: field_name(name, lead) for name in HOURLY}
            missing = [name for name, column in columns.items() if group[column].isna().any()]
            complete = len(group) == 24 and not missing
            coverage[f'{target_date}:{lead}'] = {'hours': len(group), 'complete': complete, 'missing': missing}
            if not complete:
                continue
            get = lambda name: group[columns[name]]
            daily[(target_date, lead)] = {
                'tmax': float(get('temperature_2m').max()),
                'tmin': float(get('temperature_2m').min()),
                'tmean': float(get('temperature_2m').mean()),
                'rh_mean': float(get('relative_humidity_2m').mean()),
                'wind_speed_max': float(get('wind_speed_10m').max()),
                'pressure_mean': float(get('surface_pressure').mean()),
                'solar_radiation_sum': float(get('shortwave_radiation').sum() * 0.0036),
                'cloud_cover_mean': float(get('cloud_cover').mean()),
            }
    return daily, coverage


def results() -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    names = [field_name(name, lead) for lead in ALL_LEADS for name in HOURLY]
    forecast_url, forecast_raw, forecast = fetch('https://previous-runs-api.open-meteo.com/v1/forecast', {
        **LOCATION, 'models': MODEL, 'start_date': FETCH_START.isoformat(),
        'end_date': END.isoformat(), 'hourly': ','.join(names),
    })
    (OUTPUT / 'forecast-hourly.json').write_bytes(forecast_raw)
    if forecast.get('timezone') != LOCATION['timezone']:
        raise ValueError('Archive timezone does not match Jaipur local days')
    daily, coverage = aggregate_fixed_leads(forecast['hourly'])
    (OUTPUT / 'coverage.json').write_text(json.dumps(coverage, indent=2) + '\n')
    verify_url, verify_raw, verify = fetch('https://archive-api.open-meteo.com/v1/archive', {
        **LOCATION, 'start_date': START.isoformat(), 'end_date': END.isoformat(),
        'daily': 'temperature_2m_max', 'models': 'era5',
    })
    (OUTPUT / 'verifying-reanalysis.json').write_bytes(verify_raw)
    observed = {date.fromisoformat(day): value for day, value in zip(
        verify['daily']['time'], verify['daily']['temperature_2m_max'], strict=True)}
    runtime = FastAPI()
    load_runtime(runtime)
    if runtime.state.contract['model_version'] != 'jaipur-fixed-v2':
        raise ValueError('This predeclared evaluation expects the corrected Jaipur v2 bundle')
    missing_counts = {str(lead): 0 for lead in LEADS}
    rows = []
    for lead in LEADS:
        target = START
        while target <= END:
            current = daily.get((target, lead))
            lag_days = [daily.get((target - timedelta(days=offset), lead - offset)) for offset in (1, 2, 3)]
            truth_tmax = observed.get(target)
            if current is None or any(item is None for item in lag_days) or truth_tmax is None:
                missing_counts[str(lead)] += 1
                target += timedelta(days=1)
                continue
            normal, p95, p98 = runtime.state.climatology.thresholds(target)
            day_of_year = target.timetuple().tm_yday
            angle = 2 * np.pi * (day_of_year - 1) / 365
            features = {**current,
                'tmax_lag1': lag_days[0]['tmax'], 'tmax_lag2': lag_days[1]['tmax'], 'tmax_lag3': lag_days[2]['tmax'],
                'tmin_lag1': lag_days[0]['tmin'], 'tmin_lag2': lag_days[1]['tmin'], 'tmin_lag3': lag_days[2]['tmin'],
                'tmax_departure': current['tmax'] - normal,
                'doy_sin': float(np.sin(angle)), 'doy_cos': float(np.cos(angle))}
            matrix = xgb.DMatrix(np.asarray([[features[name] for name in runtime.state.features]], dtype=np.float32),
                                  feature_names=runtime.state.features)
            probability = float(runtime.state.model.predict(matrix)[0])
            rows.append({'date': target.isoformat(), 'lead_days': lead,
                         'forecast_tmax': current['tmax'], 'verifying_reanalysis_tmax': float(truth_tmax),
                         'p95': p95, 'observed_heatwave_label': int(truth_tmax >= p95),
                         'model_probability': probability, 'model_predicted': int(probability >= .5),
                         'threshold_baseline_predicted': int(current['tmax'] >= p95)})
            target += timedelta(days=1)
    result_frame = pd.DataFrame(rows)
    if result_frame.empty:
        raise ValueError('No complete fixed-lead records; report coverage instead of skill')
    result_frame.to_csv(OUTPUT / 'scored-days.csv', index=False)
    by_lead = {}
    for lead, group in result_frame.groupby('lead_days'):
        truth = group.observed_heatwave_label.astype(int)
        model = group.model_predicted.astype(int)
        baseline = group.threshold_baseline_predicted.astype(int)
        by_lead[str(lead)] = {
            'rows': len(group), 'positive_labels': int(truth.sum()), 'omitted_days': missing_counts[str(lead)],
            'model': metric_report(truth, model), 'temperature_threshold_baseline': metric_report(truth, baseline),
            'brier_score_uncalibrated_probability': float(np.mean((group.model_probability - truth) ** 2)),
            'forecast_tmax_mae_c': float(np.mean(abs(group.forecast_tmax - group.verifying_reanalysis_tmax))),
        }
    report = {'status': 'exploratory_fixed_lead_proxy_not_as_issued_validation',
              'period': {'start': START.isoformat(), 'end': END.isoformat(), 'season': 'predeclared hot season'},
              'location': LOCATION, 'forecast_model': MODEL, 'forecast_resolution': '0.25 degree',
              'heatwave_model_version': runtime.state.contract['model_version'],
              'label': 'ERA5 reanalysis Tmax >= Jaipur fixed-reference P95; not observed health outcomes',
              'forecast_source_url': forecast_url, 'forecast_sha256': hashlib.sha256(forecast_raw).hexdigest(),
              'verifier_source_url': verify_url, 'verifier_sha256': hashlib.sha256(verify_raw).hexdigest(),
              'retrieved_at': datetime.now(UTC).isoformat(), 'lead_metrics': by_lead,
              'limitations': [
                  'Fixed-lead hourly series can stitch several ECMWF initialization cycles across a local day.',
                  'Forecast lag features use the adjacent fixed-lead series, an approximation of one issued run.',
                  'Hourly aggregation approximates the daily inputs used during model training.',
                  'ECMWF 0.25-degree forecasts differ from the deployed best-match weather feed and 9-km single-run probe.',
                  'ERA5 reanalysis is a verification proxy, not an observed station or health outcome.',
                  'Classification probability is not calibrated and Brier score is descriptive only.',
              ]}
    (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

if __name__ == '__main__':
    report = results()
    print(json.dumps({'status': report['status'], 'lead_metrics': report['lead_metrics']}, indent=2))
