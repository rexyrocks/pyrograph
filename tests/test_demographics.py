from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

TEST_API_KEY = "test-only-heatshield-api-key-00000000"
os.environ.setdefault("HEATSHIELD_API_KEY", TEST_API_KEY)

from backend.demographics import load_ward_demographics
from backend.main import app as full_app
from backend.vercel_app import app as vercel_app


class DemographicTests(unittest.TestCase):
    def test_fixture_loads_with_explicit_missingness(self) -> None:
        payload = load_ward_demographics()
        self.assertEqual(payload.count, 5)
        self.assertEqual(payload.data_kind, "synthetic_fixture")
        self.assertFalse(payload.suitable_for_operational_use)
        self.assertEqual(
            payload.records[0].missing_fields,
            ["outdoor_worker_pct", "informal_housing_pct"],
        )
        self.assertIsNone(payload.records[0].outdoor_worker_pct)

    def test_invalid_percentage_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text(
                "ward_id,population_total,elderly_pct,child_pct,"
                "outdoor_worker_pct,informal_housing_pct\n"
                "ward-1,1000,101,10,20,30\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "between 0 and 100"):
                load_ward_demographics(path)

    def test_full_api_exposes_synthetic_provenance(self) -> None:
        with TestClient(full_app) as client:
            response = client.get("/demographics/wards")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 5)
        self.assertEqual(response.json()["data_kind"], "synthetic_fixture")

    def test_production_endpoint_requires_api_key(self) -> None:
        with TestClient(vercel_app) as client:
            missing = client.get("/demographics/wards")
            valid = client.get(
                "/demographics/wards",
                headers={"X-API-Key": TEST_API_KEY},
            )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(valid.status_code, 200)


if __name__ == "__main__":
    unittest.main()
