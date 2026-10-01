"""Inference API for the SIH26083 classical heatwave model."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Annotated, Any

import xgboost as xgb
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from backend.alerts import (
    AlertConflictError,
    AlertDispatchInput,
    AlertDispatchOutput,
    AlertNotFoundError,
    AlertRecord,
    build_alert_service_from_environment,
)
from backend.demographics import WardDemographicsCollection, load_ward_demographics
from backend.municipal import (
    EscalationCheckOutput,
    InvalidTransitionError,
    MunicipalWorkflow,
    MunicipalWorkflowService,
    WorkflowConflictError,
    WorkflowCreateInput,
    WorkflowCreateOutput,
    WorkflowNotFoundError,
    WorkflowTransitionInput,
)
from backend.serving import load_runtime
from backend.thermal_assessment import ThermalAssessment, assess_thermal
from backend.risk import RiskAssessmentInput, RiskAssessmentOutput, assess_risk




class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PredictionInput(StrictModel):
    date: date
    tmax: float = Field(ge=-90, le=65)
    tmin: float = Field(ge=-90, le=65)
    tmean: float = Field(ge=-90, le=65)
    rh_mean: float = Field(ge=0, le=100)
    wind_speed_max: float = Field(ge=0)
    pressure_mean: float = Field(gt=0)
    solar_radiation_sum: float = Field(ge=0)
    cloud_cover_mean: float = Field(ge=0, le=100)
    tmax_lag1: float
    tmax_lag2: float
    tmax_lag3: float
    tmin_lag1: float
    tmin_lag2: float
    tmin_lag3: float
    previous_day_heatwave: bool | None = Field(
        default=None,
        description="Previous day's binary prediction for single-record persistence checking",
    )


class BatchPredictionInput(StrictModel):
    records: Annotated[list[PredictionInput], Field(min_length=1, max_length=366)]


class PredictionOutput(StrictModel):
    date: date
    heatwave_prediction: int
    heatwave_probability: float
    severe: bool
    persistence_met: bool | None
    alert_triggered: bool | None
    climatology_normal: float
    climatology_p95: float
    climatology_p98: float
    model_name: str
    model_version: str
    reference_period: str
    thermal: ThermalAssessment


class BatchPredictionOutput(StrictModel):
    count: int
    predictions: list[PredictionOutput]


def _load_runtime(app: FastAPI) -> None:
    load_runtime(app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_runtime(app)
    app.state.alert_service = build_alert_service_from_environment()
    app.state.municipal_service = MunicipalWorkflowService()
    yield


app = FastAPI(
    title="SIH26083 Extreme Heatwave Early Warning API",
    version="1.0.0",
    description=(
        "Binary classical-ML heatwave inference. Severe classification and the "
        "two-consecutive-day rule are applied only after binary prediction."
    ),
    lifespan=lifespan,
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        (
            "http://localhost:3000,http://localhost:5173,"
            "https://heatshield-jaipur.vercel.app"
        ),
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def _engineer_features(record: PredictionInput, climatology: Any) -> tuple[dict[str, float], tuple[float, float, float]]:
    normal, p95, p98 = climatology.thresholds(record.date)
    days_in_year = 366.0 if pd.Timestamp(record.date).is_leap_year else 365.0
    day_of_year = float(record.date.timetuple().tm_yday)
    angle = 2.0 * np.pi * (day_of_year - 1.0) / days_in_year
    supplied = record.model_dump(exclude={"date", "previous_day_heatwave"})
    supplied.update(
        {
            "tmax_departure": record.tmax - normal,
            "doy_sin": float(np.sin(angle)),
            "doy_cos": float(np.cos(angle)),
        }
    )
    return supplied, (normal, p95, p98)


def _predict(
    request: Request,
    record: PredictionInput,
    previous_day_heatwave: bool | None,
) -> PredictionOutput:
    values, (normal, p95, p98) = _engineer_features(
        record, request.app.state.climatology
    )
    expected_features: list[str] = request.app.state.features
    missing = [feature for feature in expected_features if feature not in values]
    if missing:
        raise ValueError(f"Backend cannot construct required model features: {missing}")
    frame = pd.DataFrame([[values[name] for name in expected_features]], columns=expected_features)
    model = request.app.state.model
    probability = float(model.predict(xgb.DMatrix(frame))[0])
    prediction = int(probability >= 0.5)

    severe = bool(prediction == 1 and record.tmax >= p98)
    persistence_met = (
        None
        if previous_day_heatwave is None
        else bool(previous_day_heatwave and prediction == 1)
    )
    return PredictionOutput(
        date=record.date,
        heatwave_prediction=prediction,
        heatwave_probability=probability,
        severe=severe,
        persistence_met=persistence_met,
        alert_triggered=persistence_met,
        climatology_normal=normal,
        climatology_p95=p95,
        climatology_p98=p98,
        model_name=request.app.state.model_name,
        model_version=request.app.state.contract["model_version"],
        reference_period=request.app.state.contract["reference_period"],
        thermal=assess_thermal(record),
    )


@app.get("/health")
def health(request: Request) -> dict[str, Any]:
    return {
        "status": "ok",
        "model_loaded": hasattr(request.app.state, "model"),
        "model_name": request.app.state.model_name,
        "feature_count": len(request.app.state.features),
    }


@app.get("/model/info")
def model_info(request: Request) -> dict[str, Any]:
    return {
        "model_name": request.app.state.model_name,
        "feature_order": request.app.state.features,
        "target": request.app.state.contract["target"],
        "prediction_type": request.app.state.contract["prediction_type"],
        "severe_is_post_hoc_flag": request.app.state.contract[
            "severe_is_post_hoc_flag"
        ],
        "persistence_days": 2,
        "model_version": request.app.state.contract["model_version"],
        "reference_period": request.app.state.contract["reference_period"],
        "validation_status": request.app.state.contract["validation_status"],
        "probability_calibrated": False,
    }


@app.post("/predict", response_model=PredictionOutput)
def predict(request: Request, record: PredictionInput) -> PredictionOutput:
    return _predict(request, record, record.previous_day_heatwave)


@app.post("/predict/batch", response_model=BatchPredictionOutput)
def predict_batch(
    request: Request, payload: BatchPredictionInput
) -> BatchPredictionOutput:
    dates = [record.date for record in payload.records]
    if any(current <= previous for previous, current in zip(dates, dates[1:])):
        raise HTTPException(
            status_code=422, detail="Batch dates must be strictly increasing"
        )

    results: list[PredictionOutput] = []
    for index, record in enumerate(payload.records):
        if index == 0:
            previous = record.previous_day_heatwave
        elif record.date == payload.records[index - 1].date + timedelta(days=1):
            previous = bool(results[index - 1].heatwave_prediction)
        else:
            previous = None
        results.append(_predict(request, record, previous))
    return BatchPredictionOutput(count=len(results), predictions=results)


@app.post("/risk/assess", response_model=RiskAssessmentOutput)
def risk_assessment(payload: RiskAssessmentInput) -> RiskAssessmentOutput:
    """Calculate an uncalibrated heat-health planning index."""

    return assess_risk(payload)


@app.get("/demographics/wards", response_model=WardDemographicsCollection)
def ward_demographics() -> WardDemographicsCollection:
    """Return validated synthetic records for integration testing."""

    return load_ward_demographics()


@app.post("/alerts/dispatch", response_model=AlertDispatchOutput)
def dispatch_alert(
    request: Request, payload: AlertDispatchInput
) -> AlertDispatchOutput:
    """Dispatch through the offline provider; no real message is sent."""

    try:
        return request.app.state.alert_service.dispatch(payload)
    except AlertConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/alerts/{alert_id}", response_model=AlertRecord)
def get_alert(request: Request, alert_id: str) -> AlertRecord:
    try:
        return request.app.state.alert_service.get(alert_id)
    except AlertNotFoundError as error:
        raise HTTPException(status_code=404, detail="Alert not found") from error


@app.post("/municipal/workflows", response_model=WorkflowCreateOutput)
def create_municipal_workflow(
    request: Request, payload: WorkflowCreateInput
) -> WorkflowCreateOutput:
    try:
        return request.app.state.municipal_service.create(payload)
    except WorkflowConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/municipal/workflows/{workflow_id}", response_model=MunicipalWorkflow)
def get_municipal_workflow(request: Request, workflow_id: str) -> MunicipalWorkflow:
    try:
        return request.app.state.municipal_service.get(workflow_id)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="Workflow not found") from error


@app.post(
    "/municipal/workflows/{workflow_id}/transitions",
    response_model=MunicipalWorkflow,
)
def transition_municipal_workflow(
    request: Request,
    workflow_id: str,
    payload: WorkflowTransitionInput,
) -> MunicipalWorkflow:
    try:
        return request.app.state.municipal_service.transition(workflow_id, payload)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="Workflow not found") from error
    except InvalidTransitionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get(
    "/municipal/workflows/{workflow_id}/escalation",
    response_model=EscalationCheckOutput,
)
def check_municipal_escalation(
    request: Request, workflow_id: str
) -> EscalationCheckOutput:
    try:
        return request.app.state.municipal_service.check_escalation(workflow_id)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="Workflow not found") from error
