"""Fetch one archived ECMWF run; derive complete Jaipur local-day features.

This is an archive availability probe, not model validation. Hourly forecast
values are grouped in the requested local timezone; incomplete first days are
reported and omitted from derived daily records.
"""
import argparse
from datetime import datetime, UTC
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

HOURLY_FIELDS = ['temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
                 'surface_pressure', 'shortwave_radiation', 'cloud_cover']
DAILY_FIELDS = ['tmax', 'tmin', 'tmean', 'rh_mean', 'wind_speed_max',
                'pressure_mean', 'solar_radiation_sum', 'cloud_cover_mean']

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='2025-05-01T00:00', help='Valid UTC ECMWF run time')
    parser.add_argument('--output-dir', type=Path, default=Path('work/archive-probe'))
    args = parser.parse_args()
    query = {'latitude': 26.91, 'longitude': 75.79, 'timezone': 'Asia/Kolkata',
             'models': 'ecmwf_ifs', 'run': args.run, 'forecast_hours': 192,
             'hourly': ','.join(HOURLY_FIELDS)}
    url = 'https://single-runs-api.open-meteo.com/v1/forecast?' + urlencode(query)
    raw = urlopen(url, timeout=60).read()
    data = json.loads(raw)
    hourly = data.get('hourly', {})
    times = hourly.get('time', [])
    available = {name: isinstance(hourly.get(name), list) and len(hourly[name]) == len(times)
                 and all(value is None or isinstance(value, (int, float)) for value in hourly[name])
                 for name in HOURLY_FIELDS}
    if not times or not all(available.values()):
        raise SystemExit(f'Incomplete archived hourly inputs: {available}')

    frame = pd.DataFrame({'time': pd.to_datetime(times)})
    for name in HOURLY_FIELDS:
        frame[name] = pd.to_numeric(hourly[name], errors='coerce')
    frame['local_date'] = frame.time.dt.strftime('%Y-%m-%d')
    rows, completeness = [], {}
    for local_date, group in frame.groupby('local_date', sort=True):
        missing = [name for name in HOURLY_FIELDS if group[name].isna().any()]
        complete = len(group) == 24 and not missing
        completeness[local_date] = {'hours': len(group), 'complete': complete, 'missing_fields': missing}
        if not complete:
            continue
        rows.append({
            'date': local_date,
            'tmax': float(group.temperature_2m.max()),
            'tmin': float(group.temperature_2m.min()),
            'tmean': float(group.temperature_2m.mean()),
            'rh_mean': float(group.relative_humidity_2m.mean()),
            'wind_speed_max': float(group.wind_speed_10m.max()),
            'pressure_mean': float(group.surface_pressure.mean()),
            'solar_radiation_sum': float(group.shortwave_radiation.sum() * 0.0036),
            'cloud_cover_mean': float(group.cloud_cover.mean()),
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'response-hourly.json').write_bytes(raw)
    pd.DataFrame(rows, columns=['date', *DAILY_FIELDS]).to_csv(args.output_dir / 'complete-local-days.csv', index=False)
    manifest = {
        'source_url': url, 'retrieved_at': datetime.now(UTC).isoformat(),
        'requested_run_utc': args.run, 'model': 'ecmwf_ifs',
        'sha256': hashlib.sha256(raw).hexdigest(),
        'timezone': data.get('timezone'), 'utc_offset_seconds': data.get('utc_offset_seconds'),
        'hourly_units': data.get('hourly_units'), 'hour_count': len(times),
        'local_day_coverage': completeness,
        'derived_complete_local_days': [row['date'] for row in rows],
        'derivation': {'tmax': 'hourly max', 'tmin': 'hourly min', 'tmean': 'hourly arithmetic mean',
                       'rh_mean': 'hourly arithmetic mean', 'wind_speed_max': 'hourly max',
                       'pressure_mean': 'hourly arithmetic mean', 'solar_radiation_sum': 'sum hourly W/m2 * 0.0036 to MJ/m2',
                       'cloud_cover_mean': 'hourly arithmetic mean'},
        'status': 'archive_availability_probe_only_not_forecast_validation',
        'limitations': ['Hourly samples approximate local-day extrema and do not exactly reproduce daily products.',
                        'First local day may be incomplete because the forecast run starts before/after local midnight.',
                        'Daily averages derived from hourly fields can differ from the training data daily products.',
                        'Need issue-time lag inputs, fresh independent verification, and publication-latency policy.',
                        'One run does not establish forecast skill.'],
    }
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'requested_run_utc': args.run, 'timezone': manifest['timezone'],
                      'hours': len(times), 'complete_local_days': manifest['derived_complete_local_days'],
                      'status': manifest['status']}, indent=2))
    if len(rows) < 6:
        raise SystemExit('Not enough complete local days to cover 3–5 day evaluation leads.')
