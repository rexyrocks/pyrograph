"""Lightweight Vercel runtime for the SIH26083 XGBoost predictor."""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Annotated, Any

import numpy as np
import xgboost as xgb
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    build_municipal_service_from_environment,
    WorkflowConflictError,
    WorkflowCreateInput,
    WorkflowCreateOutput,
    WorkflowNotFoundError,
    WorkflowTransitionInput,
)
from backend.serving import load_runtime
from backend.thermal_assessment import ThermalAssessment, assess_thermal
from backend.risk import RiskAssessmentInput, RiskAssessmentOutput, assess_risk


MAX_REQUEST_BYTES = 512 * 1024


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
    previous_day_heatwave: bool | None = Field(default=None)


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
    api_key = os.getenv("HEATSHIELD_API_KEY", "")
    if len(api_key) < 32:
        raise RuntimeError("HEATSHIELD_API_KEY must contain at least 32 characters")
    app.state.api_key = api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_runtime(app)
    app.state.alert_service = build_alert_service_from_environment()
    app.state.municipal_service = build_municipal_service_from_environment()
    yield


app = FastAPI(
    title="SIH26083 HeatShield Jaipur API",
    version="1.0.0",
    description="Production binary heatwave inference using the selected XGBoost model.",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,https://heatshield-jaipur.vercel.app",
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
    content_length = request.headers.get("content-length")
    try:
        request_size = int(content_length) if content_length is not None else 0
    except ValueError:
        request_size = MAX_REQUEST_BYTES + 1
    if request_size > MAX_REQUEST_BYTES:
        response = JSONResponse(status_code=413, content={"detail": "Request too large"})
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def require_api_key(
    request: Request,
    supplied_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    expected_key: str = request.app.state.api_key
    if supplied_key is None or not secrets.compare_digest(supplied_key, expected_key):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def _engineer_features(
    record: PredictionInput, climatology: Any
) -> tuple[dict[str, float], tuple[float, float, float]]:
    normal, p95, p98 = climatology.thresholds(record.date)
    leap_year = record.date.year % 4 == 0 and (
        record.date.year % 100 != 0 or record.date.year % 400 == 0
    )
    days_in_year = 366.0 if leap_year else 365.0
    angle = 2.0 * np.pi * (record.date.timetuple().tm_yday - 1.0) / days_in_year
    values = record.model_dump(exclude={"date", "previous_day_heatwave"})
    values.update(
        {
            "tmax_departure": record.tmax - normal,
            "doy_sin": float(np.sin(angle)),
            "doy_cos": float(np.cos(angle)),
        }
    )
    return values, (normal, p95, p98)


def _predict(
    request: Request,
    record: PredictionInput,
    previous_day_heatwave: bool | None,
) -> PredictionOutput:
    values, (normal, p95, p98) = _engineer_features(
        record, request.app.state.climatology
    )
    features: list[str] = request.app.state.features
    matrix = xgb.DMatrix(
        np.asarray([[values[name] for name in features]], dtype=np.float32),
        feature_names=features,
    )
    probability = float(request.app.state.model.predict(matrix)[0])
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
        model_name="XGBClassifier",
        model_version=request.app.state.contract["model_version"],
        reference_period=request.app.state.contract["reference_period"],
        thermal=assess_thermal(record),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/model/info")
def model_info(
    request: Request, _authorized: None = Depends(require_api_key)
) -> dict[str, Any]:
    return {
        "model_name": "XGBClassifier",
        "feature_order": request.app.state.features,
        "target": request.app.state.contract["target"],
        "prediction_type": request.app.state.contract["prediction_type"],
        "severe_is_post_hoc_flag": True,
        "persistence_days": 2,
        "model_version": request.app.state.contract["model_version"],
        "reference_period": request.app.state.contract["reference_period"],
        "validation_status": request.app.state.contract["validation_status"],
        "probability_calibrated": False,
    }


@app.post("/predict", response_model=PredictionOutput)
def predict(
    record: PredictionInput,
    request: Request,
    _authorized: None = Depends(require_api_key),
) -> PredictionOutput:
    return _predict(request, record, record.previous_day_heatwave)


@app.post("/predict/batch", response_model=BatchPredictionOutput)
def predict_batch(
    payload: BatchPredictionInput,
    request: Request,
    _authorized: None = Depends(require_api_key),
) -> BatchPredictionOutput:
    records = payload.records
    for previous, current in zip(records, records[1:]):
        if current.date <= previous.date:
            raise HTTPException(status_code=422, detail="Dates must be increasing")
    results: list[PredictionOutput] = []
    previous_prediction: bool | None = records[0].previous_day_heatwave
    previous_date: date | None = None
    for record in records:
        if previous_date is not None and record.date != previous_date + timedelta(days=1):
            previous_prediction = None
        results.append(_predict(request, record, previous_prediction))
        previous_prediction = bool(results[-1].heatwave_prediction)
        previous_date = record.date
    return BatchPredictionOutput(count=len(results), predictions=results)


@app.post(
    "/risk/assess",
    response_model=RiskAssessmentOutput,
    dependencies=[Depends(require_api_key)],
)
def risk_assessment(payload: RiskAssessmentInput) -> RiskAssessmentOutput:
    """Calculate an uncalibrated heat-health planning index."""

    return assess_risk(payload)


@app.get(
    "/demographics/wards",
    response_model=WardDemographicsCollection,
    dependencies=[Depends(require_api_key)],
)
def ward_demographics() -> WardDemographicsCollection:
    """Return validated synthetic records for integration testing."""

    return load_ward_demographics()


@app.post(
    "/alerts/dispatch",
    response_model=AlertDispatchOutput,
    dependencies=[Depends(require_api_key)],
)
def dispatch_alert(request: Request, payload: AlertDispatchInput) -> AlertDispatchOutput:
    """Dispatch through the offline provider; no real message is sent."""

    try:
        return request.app.state.alert_service.dispatch(payload)
    except AlertConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get(
    "/alerts/{alert_id}",
    response_model=AlertRecord,
    dependencies=[Depends(require_api_key)],
)
def get_alert(request: Request, alert_id: str) -> AlertRecord:
    try:
        return request.app.state.alert_service.get(alert_id)
    except AlertNotFoundError as error:
        raise HTTPException(status_code=404, detail="Alert not found") from error


@app.post(
    "/municipal/workflows",
    response_model=WorkflowCreateOutput,
    dependencies=[Depends(require_api_key)],
)
def create_municipal_workflow(
    request: Request, payload: WorkflowCreateInput
) -> WorkflowCreateOutput:
    try:
        return request.app.state.municipal_service.create(payload)
    except WorkflowConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get(
    "/municipal/workflows/{workflow_id}",
    response_model=MunicipalWorkflow,
    dependencies=[Depends(require_api_key)],
)
def get_municipal_workflow(request: Request, workflow_id: str) -> MunicipalWorkflow:
    try:
        return request.app.state.municipal_service.get(workflow_id)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="Workflow not found") from error


@app.post(
    "/municipal/workflows/{workflow_id}/transitions",
    response_model=MunicipalWorkflow,
    dependencies=[Depends(require_api_key)],
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
    dependencies=[Depends(require_api_key)],
)
def check_municipal_escalation(
    request: Request, workflow_id: str
) -> EscalationCheckOutput:
    try:
        return request.app.state.municipal_service.check_escalation(workflow_id)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=404, detail="Workflow not found") from error
