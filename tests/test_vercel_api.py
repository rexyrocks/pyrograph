from __future__ import annotations

import os
import unittest

TEST_API_KEY = "test-only-heatshield-api-key-00000000"
os.environ.setdefault("HEATSHIELD_API_KEY", TEST_API_KEY)

from fastapi.testclient import TestClient

from backend.main import app as full_app
from backend.vercel_app import app as vercel_app
from tests.test_api import SECOND


class VercelApiTests(unittest.TestCase):
    def test_lightweight_runtime_matches_full_model(self) -> None:
        payload = {**SECOND, "previous_day_heatwave": True}
        with TestClient(full_app) as full_client, TestClient(vercel_app) as light_client:
            full_response = full_client.post("/predict", json=payload)
            light_response = light_client.post(
                "/predict", json=payload, headers={"X-API-Key": TEST_API_KEY}
            )

        self.assertEqual(full_response.status_code, 200)
        self.assertEqual(light_response.status_code, 200)
        full = full_response.json()
        light = light_response.json()
        self.assertEqual(light["heatwave_prediction"], full["heatwave_prediction"])
        self.assertEqual(light["severe"], full["severe"])
        self.assertAlmostEqual(
            light["heatwave_probability"], full["heatwave_probability"], places=7
        )
        self.assertAlmostEqual(light["climatology_p95"], full["climatology_p95"])

    def test_lightweight_health_contract(self) -> None:
        with TestClient(vercel_app) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_prediction_requires_api_key(self) -> None:
        with TestClient(vercel_app) as client:
            missing = client.post("/predict", json=SECOND)
            incorrect = client.post(
                "/predict", json=SECOND, headers={"X-API-Key": "incorrect"}
            )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(incorrect.status_code, 401)

    def test_public_api_documentation_is_disabled(self) -> None:
        with TestClient(vercel_app) as client:
            self.assertEqual(client.get("/docs").status_code, 404)
            self.assertEqual(client.get("/openapi.json").status_code, 404)


if __name__ == "__main__":
    unittest.main()
