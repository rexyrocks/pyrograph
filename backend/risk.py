"""Transparent prototype heat-health impact scoring.

The score in this module is a planning index, not an estimate of an individual's
or population's probability of death. Historical annual mortality totals are
not granular enough to fit or validate a daily local mortality model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RISK_MODEL_VERSION = "prototype-impact-index-v1"
CALIBRATION_STATUS = "uncalibrated_planning_index_not_mortality_probability"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class VulnerabilityProfile(StrictModel):
    """Aggregate population shares; each share is expressed from 0 to 1."""

    older_adult_share: float = Field(ge=0, le=1)
    young_child_share: float = Field(ge=0, le=1)
    outdoor_worker_share: float = Field(ge=0, le=1)
    informal_housing_share: float = Field(ge=0, le=1)
    social_deprivation_index: float = Field(ge=0, le=1)


class RiskAssessmentInput(StrictModel):
    heatwave_probability: float = Field(ge=0, le=1)
    severe: bool
    persistence_met: bool | None = None
    vulnerability: VulnerabilityProfile


class ScoreDriver(StrictModel):
    factor: str
    contribution: float
    display_value: str


class MunicipalAction(StrictModel):
    priority: Literal["monitor", "prepare", "activate", "emergency"]
    action: str


class RiskAssessmentOutput(StrictModel):
    index: float
    band: Literal["Low", "Moderate", "High", "Severe"]
    heat_hazard_score: float
    vulnerability_score: float
    drivers: list[ScoreDriver]
    municipal_actions: list[MunicipalAction]
    model_version: str
    calibration_status: str
    mortality_probability: None = None
    methodology: str


_VULNERABILITY_FACTORS = (
    ("Older adults", "older_adult_share", 0.25, 0.25),
    ("Children under five", "young_child_share", 0.15, 0.15),
    ("Outdoor workers", "outdoor_worker_share", 0.20, 0.50),
    ("Informal housing", "informal_housing_share", 0.25, 0.40),
    ("Social deprivation", "social_deprivation_index", 0.15, 1.00),
)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _band(index: float) -> Literal["Low", "Moderate", "High", "Severe"]:
    if index < 30:
        return "Low"
    if index < 50:
        return "Moderate"
    if index < 70:
        return "High"
    return "Severe"


def _actions(band: str) -> list[MunicipalAction]:
    actions = [
        MunicipalAction(
            priority="monitor",
            action="Monitor forecasts and verify local response contacts.",
        )
    ]
    if band in {"Moderate", "High", "Severe"}:
        actions.append(
            MunicipalAction(
                priority="prepare",
                action="Confirm water points, cooling spaces, and outreach teams.",
            )
        )
    if band in {"High", "Severe"}:
        actions.extend(
            [
                MunicipalAction(
                    priority="activate",
                    action="Shift outdoor municipal work away from peak afternoon heat.",
                ),
                MunicipalAction(
                    priority="activate",
                    action="Issue targeted guidance for vulnerable population groups.",
                ),
            ]
        )
    if band == "Severe":
        actions.append(
            MunicipalAction(
                priority="emergency",
                action="Activate incident review and health-facility readiness checks.",
            )
        )
    return actions


def assess_risk(payload: RiskAssessmentInput) -> RiskAssessmentOutput:
    """Return a deterministic and auditable planning index."""

    persistence = payload.persistence_met is True
    hazard_score = _clamp(
        payload.heatwave_probability * 82
        + (10 if payload.severe else 0)
        + (8 if persistence else 0)
    )

    contributions: list[ScoreDriver] = []
    vulnerability_score = 0.0
    for label, field_name, weight, reference_high in _VULNERABILITY_FACTORS:
        raw_value = float(getattr(payload.vulnerability, field_name))
        normalized = min(raw_value / reference_high, 1.0)
        contribution = normalized * weight * 100
        vulnerability_score += contribution
        contributions.append(
            ScoreDriver(
                factor=label,
                contribution=round(contribution, 1),
                display_value=(
                    f"{raw_value * 100:.1f}%"
                    if field_name != "social_deprivation_index"
                    else f"{raw_value * 100:.0f}/100"
                ),
            )
        )

    index = _clamp(0.70 * hazard_score + 0.30 * vulnerability_score)
    band = _band(index)
    top_drivers = sorted(
        contributions, key=lambda item: item.contribution, reverse=True
    )[:3]
    return RiskAssessmentOutput(
        index=round(index, 1),
        band=band,
        heat_hazard_score=round(hazard_score, 1),
        vulnerability_score=round(vulnerability_score, 1),
        drivers=top_drivers,
        municipal_actions=_actions(band),
        model_version=RISK_MODEL_VERSION,
        calibration_status=CALIBRATION_STATUS,
        methodology=(
            "Transparent planning index: 70% heat hazard and 30% aggregate "
            "demographic vulnerability. It is not fitted to mortality outcomes."
        ),
    )
