from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app as full_app
from backend.vercel_app import app as production_app
from evaluate_retrospective import prepare_evaluation, select_model
from heatwave_pipeline import RAW_FEATURES, FEATURES, validate_and_load
from tests.test_api import SECOND
from tests.test_risk import BASE_PAYLOAD, TEST_API_KEY

ROOT = Path(__file__).resolve().parents[1]


class DemoRegressionTests(unittest.TestCase):
    def test_first_record_persistence_matches_both_entrypoints(self):
        results = []
        for app in (full_app, production_app):
            with TestClient(app) as client:
                response = client.post('/predict/batch', json={
                    'records': [{**SECOND, 'previous_day_heatwave': True}],
                }, headers={'X-API-Key': TEST_API_KEY})
                self.assertEqual(response.status_code, 200)
                results.append(response.json()['predictions'][0])
        for result in results:
            self.assertTrue(result['persistence_met'])
            self.assertTrue(result['alert_triggered'])

    def test_boundary_score_uses_unrounded_probability(self):
        with TestClient(production_app) as client:
            response = client.post('/risk/assess', json={
                **BASE_PAYLOAD, 'heatwave_probability': 0.255,
                'severe': False, 'persistence_met': False,
            }, headers={'X-API-Key': TEST_API_KEY})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['band'], 'Low')
        self.assertEqual(response.json()['index'], 29.8)

    def test_future_weather_cannot_change_training_or_selection(self):
        raw = validate_and_load(ROOT / 'data/jaipur_daily_2015_2024.csv')
        before = prepare_evaluation(raw)
        changed = raw.copy()
        changed.loc[changed.date.dt.year >= 2023, RAW_FEATURES] += 20
        after = prepare_evaluation(changed)
        for index in (0, 1):
            pd.testing.assert_frame_equal(
                before[index][['date', *FEATURES, 'heatwave', 'severe']],
                after[index][['date', *FEATURES, 'heatwave', 'severe']],
            )
        self.assertEqual(set(before[0].date.dt.year), {2019, 2020, 2021})
        self.assertEqual(set(before[1].date.dt.year), {2022})
        self.assertEqual(set(before[2].date.dt.year), {2023, 2024})

    def test_selection_uses_only_selection_metrics(self):
        metrics = {'a': {'csi': .6, 'f1': .7}, 'b': {'csi': .5, 'f1': .8}}
        self.assertEqual(select_model(metrics), 'a')

    def test_demographic_fixture_is_available_to_production_api(self):
        with TestClient(production_app) as client:
            response = client.get('/demographics/wards', headers={'X-API-Key': TEST_API_KEY})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 5)
        self.assertFalse(response.json()['suitable_for_operational_use'])


if __name__ == '__main__':
    unittest.main()
