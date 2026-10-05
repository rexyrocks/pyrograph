"""One integrity-checked model and fixed reference for both API entrypoints."""
import hashlib
import json
import os
from datetime import date
from pathlib import Path

import numpy as np
import xgboost as xgb

DEFAULT_BUNDLE = Path(__file__).resolve().parents[1] / 'artifacts' / 'jaipur-fixed-v2'

class FixedClimatology:
    def __init__(self, table):
        if set(table) != {str(day) for day in range(1, 367)}:
            raise ValueError('Reference must cover all 366 calendar days')
        self.table = table
        for values in table.values():
            if len(values) != 3 or not np.isfinite(values).all() or values[1] > values[2]:
                raise ValueError('Invalid climatology thresholds')

    def thresholds(self, target_date: date):
        day = date(2000, target_date.month, target_date.day).timetuple().tm_yday
        return tuple(self.table[str(day)])


def load_runtime(app):
    # Separate overrides can accidentally mix models and reference periods.
    if any(os.getenv(name) for name in ('HEATWAVE_MODEL_PATH', 'HEATWAVE_FEATURES_PATH', 'HEATWAVE_CLIMATOLOGY_PATH')):
        raise ValueError('Use HEATWAVE_BUNDLE_DIR to select a complete versioned bundle')
    root = Path(os.getenv('HEATWAVE_BUNDLE_DIR', str(DEFAULT_BUNDLE)))
    contract = json.loads((root / 'manifest.json').read_text())
    if contract.get('schema_version') != 1 or contract.get('reference_period') != '2015-2018':
        raise ValueError('Unsupported model/reference contract')
    for name in ('model.json', 'reference.json', 'evaluation.json'):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != contract['sha256'][name]:
            raise ValueError(f'Artifact integrity mismatch: {name}')
    booster = xgb.Booster()
    booster.load_model(root / 'model.json')
    if booster.feature_names != contract['features'] or len(contract['features']) != 17:
        raise ValueError('Model feature order does not match its manifest')
    app.state.model = booster
    app.state.features = contract['features']
    app.state.contract = contract
    app.state.model_name = contract['model_name']
    app.state.climatology = FixedClimatology(json.loads((root / 'reference.json').read_text()))
