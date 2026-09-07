from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend.main import app


FIRST = {
    "date": "2015-09-04",
    "tmax": 35.0,
    "tmin": 23.8,
    "tmean": 29.6,
    "rh_mean": 47.0,
    "wind_speed_max": 14.3,
    "pressure_mean": 961.9,
    "solar_radiation_sum": 20.15,
    "cloud_cover_mean": 18.0,
    "tmax_lag1": 33.8,
    "tmax_lag2": 33.8,
    "tmax_lag3": 33.4,
    "tmin_lag1": 23.4,
    "tmin_lag2": 23.5,
    "tmin_lag3": 24.6,
}

SECOND = {
    "date": "2015-09-05",
    "tmax": 35.1,
    "tmin": 25.0,
    "tmean": 30.1,
    "rh_mean": 43.0,
    "wind_speed_max": 18.0,
    "pressure_mean": 961.7,
    "solar_radiation_sum": 19.84,
    "cloud_cover_mean": 16.0,
    "tmax_lag1": 35.0,
    "tmax_lag2": 33.8,
    "tmax_lag3": 33.8,
    "tmin_lag1": 23.8,
    "tmin_lag2": 23.4,
    "tmin_lag3": 23.5,
}


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def test_health_and_feature_contract(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["model_loaded"])
        self.assertEqual(health.json()["feature_count"], 17)

        info = self.client.get("/model/info")
        self.assertEqual(info.status_code, 200)
        self.assertEqual(info.json()["prediction_type"], "binary")
        self.assertEqual(info.json()["persistence_days"], 2)

    def test_single_prediction_and_persistence(self) -> None:
        payload = {**SECOND, "previous_day_heatwave": True}
        response = self.client.post("/predict", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["heatwave_prediction"], 1)
        self.assertTrue(body["persistence_met"])
        self.assertTrue(body["alert_triggered"])
        self.assertLessEqual(body["heatwave_probability"], 1.0)

    def test_batch_applies_consecutive_day_rule(self) -> None:
        response = self.client.post("/predict/batch", json={"records": [FIRST, SECOND]})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertIsNone(body["predictions"][0]["persistence_met"])
        self.assertTrue(body["predictions"][1]["persistence_met"])

    def test_unknown_fields_are_rejected(self) -> None:
        response = self.client.post("/predict", json={**FIRST, "unknown": 1})
        self.assertEqual(response.status_code, 422)

    def test_batch_requires_increasing_dates(self) -> None:
        response = self.client.post(
            "/predict/batch", json={"records": [SECOND, FIRST]}
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
