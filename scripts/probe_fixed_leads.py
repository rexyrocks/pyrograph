"""Check fixed-lead archived weather coverage; do not score model skill."""
import argparse
from datetime import datetime, UTC
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

BASE_FIELDS = ('temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
               'surface_pressure', 'shortwave_radiation', 'cloud_cover')
LEADS = (3, 4, 5)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-date', default='2025-05-01')
    parser.add_argument('--end-date', default='2025-05-07')
    parser.add_argument('--model', default='ecmwf_ifs025')
    parser.add_argument('--output-dir', type=Path, default=Path('work/fixed-lead-probe'))
    args = parser.parse_args()
    fields = [f'{name}_previous_day{lead}' for lead in LEADS for name in BASE_FIELDS]
    query = {'latitude': 26.91, 'longitude': 75.79, 'timezone': 'Asia/Kolkata',
             'models': args.model, 'start_date': args.start_date, 'end_date': args.end_date,
             'hourly': ','.join(fields)}
    url = 'https://previous-runs-api.open-meteo.com/v1/forecast?' + urlencode(query)
    raw = urlopen(url, timeout=60).read()
    data = json.loads(raw)
    hourly = data.get('hourly', {})
    times = hourly.get('time', [])
    if not times or any(not isinstance(hourly.get(field), list) or len(hourly[field]) != len(times) for field in fields):
        raise SystemExit('Archive response is missing requested hourly columns')
    frame = pd.DataFrame({'time': pd.to_datetime(times)})
    frame['date'] = frame.time.dt.strftime('%Y-%m-%d')
    for field in fields:
        frame[field] = pd.to_numeric(hourly[field], errors='coerce')
    coverage = []
    for day, group in frame.groupby('date', sort=True):
        for lead in LEADS:
            required = [f'{name}_previous_day{lead}' for name in BASE_FIELDS]
            missing = [field for field in required if group[field].isna().any()]
            coverage.append({'date': day, 'lead_days': lead, 'hours': len(group),
                             'complete': len(group) == 24 and not missing,
                             'missing_fields': ','.join(missing)})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'response-hourly.json').write_bytes(raw)
    pd.DataFrame(coverage).to_csv(args.output_dir / 'coverage.csv', index=False)
    summary = {str(lead): {'complete_days': sum(row['complete'] for row in coverage if row['lead_days'] == lead),
                           'days': sum(row['lead_days'] == lead for row in coverage)} for lead in LEADS}
    manifest = {'source_url': url, 'retrieved_at': datetime.now(UTC).isoformat(),
                'sha256': hashlib.sha256(raw).hexdigest(), 'model': args.model,
                'location': 'Jaipur 26.91,75.79', 'timezone': data.get('timezone'),
                'hourly_units': data.get('hourly_units'), 'lead_days': LEADS,
                'coverage': summary, 'status': 'fixed_lead_coverage_probe_not_model_validation',
                'limitations': ['The 0.25 degree archive is a different weather model/resolution from the single-run IFS 9 km probe.',
                                'Fixed-lead series need not reconstruct one complete as-issued run.',
                                'No independent verification labels, issue-time lag contract or skill estimates are supplied.']}
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'model': args.model, 'coverage': summary, 'status': manifest['status']}, indent=2))
