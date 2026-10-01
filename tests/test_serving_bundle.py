import json
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import xgboost as xgb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.serving import DEFAULT_BUNDLE, load_runtime
from backend.main import app, PredictionInput, _engineer_features
from backend.thermal_assessment import assess_thermal
from evaluate_retrospective import prepare_evaluation
from heatwave_pipeline import validate_and_load, metric_report
from tests.test_api import FIRST

ROOT = Path(__file__).resolve().parents[1]

class ServingBundleTests(unittest.TestCase):
    def test_served_model_reproduces_evaluation_on_entire_test_period(self):
        runtime = FastAPI()
        load_runtime(runtime)
        _, _, test = prepare_evaluation(validate_and_load(ROOT / 'data/jaipur_daily_2015_2024.csv'))
        rows = []
        for _, row in test.iterrows():
            payload = {name: row[name] for name in FIRST if name != 'date'}
            record = PredictionInput(date=row.date.date(), **payload)
            values, thresholds = _engineer_features(record, runtime.state.climatology)
            self.assertAlmostEqual(thresholds[0], row.climatology_normal_loyo, places=10)
            rows.append([values[name] for name in runtime.state.features])
        matrix = xgb.DMatrix(np.asarray(rows, dtype=np.float32), feature_names=runtime.state.features)
        actual = metric_report(test.heatwave, (runtime.state.model.predict(matrix) >= .5).astype(int))
        expected = json.loads((DEFAULT_BUNDLE / 'evaluation.json').read_text())['test_metrics']['xgboost']
        self.assertEqual(actual, expected)

    def test_reference_is_fixed_across_years_including_leap_day(self):
        runtime = FastAPI(); load_runtime(runtime)
        self.assertEqual(runtime.state.climatology.thresholds(date(2016, 2, 29)), runtime.state.climatology.thresholds(date(2024, 2, 29)))
        self.assertEqual(runtime.state.climatology.thresholds(date(2015, 9, 4)), runtime.state.climatology.thresholds(date(2026, 9, 4)))

    def test_tampered_bundle_fails_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'bundle'; shutil.copytree(DEFAULT_BUNDLE, root)
            with (root / 'reference.json').open('a') as output: output.write(' ')
            with patch.dict(os.environ, {'HEATWAVE_BUNDLE_DIR': str(root)}):
                with self.assertRaisesRegex(ValueError, 'integrity mismatch'): load_runtime(FastAPI())

    def test_feature_contract_mismatch_fails_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'bundle'; shutil.copytree(DEFAULT_BUNDLE, root)
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['features'].reverse()
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with patch.dict(os.environ, {'HEATWAVE_BUNDLE_DIR': str(root)}):
                with self.assertRaisesRegex(ValueError, 'feature order'): load_runtime(FastAPI())

    def test_api_returns_provenance_and_thermal_estimates(self):
        with TestClient(app) as client:
            response = client.post('/predict', json=FIRST)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result['model_version'], 'jaipur-fixed-v2')
            self.assertEqual(result['reference_period'], '2015-2018')
            self.assertEqual(result['thermal']['status'], 'estimated')
            self.assertTrue(np.isfinite(result['thermal']['utci_c']))
            self.assertEqual(client.post('/predict', json={**FIRST, 'rh_mean': 101}).status_code, 422)

    def test_out_of_domain_utci_is_explicitly_null(self):
        result = assess_thermal(PredictionInput(**{**FIRST, 'wind_speed_max': .1}))
        self.assertIsNone(result.utci_c)
        self.assertEqual(result.status, 'partial')
        self.assertIsNotNone(result.unavailable_reason)

    def test_wbgt_matches_weighted_reference_equation(self):
        # Zero radiation gives Tg = Tdb. Independent weighted WBGT equation.
        from pythermalcomfort.utilities import psy_ta_rh
        record = PredictionInput(**{**FIRST, 'solar_radiation_sum': 0})
        wet_bulb = float(psy_ta_rh(tdb=record.tmean, rh=record.rh_mean, p_atm=101325).wet_bulb_tmp)
        expected = .7 * wet_bulb + .3 * record.tmean
        self.assertAlmostEqual(assess_thermal(record).wbgt_c, expected, places=2)
