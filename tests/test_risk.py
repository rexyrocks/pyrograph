from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

TEST_API_KEY = "test-only-heatshield-api-key-00000000"
os.environ.setdefault("HEATSHIELD_API_KEY", TEST_API_KEY)

from backend.main import app as full_app
from backend.risk import (
    CALIBRATION_STATUS,
    RiskAssessmentInput,
    VulnerabilityProfile,
    assess_risk,
)
from backend.vercel_app import app as vercel_app


BASE_PAYLOAD = {
    "heatwave_probability": 0.82,
    "severe": True,
    "persistence_met": True,
    "vulnerability": {
        "older_adult_share": 0.09,
        "young_child_share": 0.10,
        "outdoor_worker_share": 0.31,
        "informal_housing_share": 0.18,
        "social_deprivation_index": 0.52,
    },
}


class RiskScoringTests(unittest.TestCase):
    def test_assessment_is_bounded_and_explicitly_uncalibrated(self) -> None:
        result = assess_risk(RiskAssessmentInput.model_validate(BASE_PAYLOAD))
        self.assertGreaterEqual(result.index, 0)
        self.assertLessEqual(result.index, 100)
        self.assertEqual(result.calibration_status, CALIBRATION_STATUS)
        self.assertIsNone(result.mortality_probability)
        self.assertEqual(len(result.drivers), 3)
        self.assertGreaterEqual(len(result.municipal_actions), 1)

    def test_higher_hazard_and_vulnerability_raise_the_index(self) -> None:
        low = assess_risk(
            RiskAssessmentInput(
                heatwave_probability=0.1,
                severe=False,
                persistence_met=False,
                vulnerability=VulnerabilityProfile(
                    older_adult_share=0.02,
                    young_child_share=0.03,
                    outdoor_worker_share=0.05,
                    informal_housing_share=0.05,
                    social_deprivation_index=0.05,
                ),
            )
        )
        high = assess_risk(RiskAssessmentInput.model_validate(BASE_PAYLOAD))
        self.assertGreater(high.index, low.index)
        self.assertGreater(high.heat_hazard_score, low.heat_hazard_score)
        self.assertGreater(high.vulnerability_score, low.vulnerability_score)

    def test_full_api_validates_profile_ranges(self) -> None:
        with TestClient(full_app) as client:
            valid = client.post("/risk/assess", json=BASE_PAYLOAD)
            invalid = client.post(
                "/risk/assess",
                json={
                    **BASE_PAYLOAD,
                    "vulnerability": {
                        **BASE_PAYLOAD["vulnerability"],
                        "older_adult_share": 1.5,
                    },
                },
            )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(invalid.status_code, 422)

    def test_production_risk_endpoint_requires_api_key(self) -> None:
        with TestClient(vercel_app) as client:
            missing = client.post("/risk/assess", json=BASE_PAYLOAD)
            valid = client.post(
                "/risk/assess",
                json=BASE_PAYLOAD,
                headers={"X-API-Key": TEST_API_KEY},
            )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["calibration_status"], CALIBRATION_STATUS)


if __name__ == "__main__":
    unittest.main()
