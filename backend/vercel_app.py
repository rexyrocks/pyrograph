"""Lightweight Vercel runtime for the SIH26083 XGBoost predictor."""

from __future__ import annotations

import csv
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import xgboost as xgb
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "outputs" / "best_heatwave_booster.json"
FEATURES_PATH = PROJECT_ROOT / "outputs" / "feature_names.json"
CLIMATOLOGY_PATH = PROJECT_ROOT / "outputs" / "loyo_climatology_labels.csv"
WINDOW_RADIUS_DAYS = 7
MAX_REQUEST_BYTES = 512 * 1024


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PredictionInput(StrictModel):
    date: date
    tmax: float
    tmin: float
    tmean: float
    rh_mean: float
    wind_speed_max: float
    pressure_mean: float
    solar_radiation_sum: float
    cloud_cover_mean: float
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


class BatchPredictionOutput(StrictModel):
    count: int
    predictions: list[PredictionOutput]


class Climatology:
    def __init__(self, path: Path) -> None:
        years: list[int] = []
        calendar_days: list[int] = []
        temperatures: list[float] = []
        with path.open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                value_date = date.fromisoformat(row["date"])
                years.append(value_date.year)
                calendar_days.append(
                    date(2000, value_date.month, value_date.day).timetuple().tm_yday
                )
                temperatures.append(float(row["tmax"]))
        if not temperatures:
            raise ValueError("Climatology archive is empty")
        self.years = np.asarray(years)
        self.calendar_days = np.asarray(calendar_days)
        self.tmax = np.asarray(temperatures, dtype=float)

    def thresholds(self, target_date: date) -> tuple[float, float, float]:
        calendar_day = date(2000, target_date.month, target_date.day).timetuple().tm_yday
        direct_distance = np.abs(self.calendar_days - calendar_day)
        circular_distance = np.minimum(direct_distance, 366 - direct_distance)
        reference_mask = (self.years != target_date.year) & (
            circular_distance <= WINDOW_RADIUS_DAYS
        )
        values = self.tmax[reference_mask]
        if values.size == 0:
            raise ValueError(f"No climatology values for {target_date.isoformat()}")
        return (
            float(np.mean(values)),
            float(np.percentile(values, 95)),
            float(np.percentile(values, 98)),
        )


def _load_runtime(app: FastAPI) -> None:
    api_key = os.getenv("HEATSHIELD_API_KEY", "")
    if len(api_key) < 32:
        raise RuntimeError("HEATSHIELD_API_KEY must contain at least 32 characters")
    for path in (MODEL_PATH, FEATURES_PATH, CLIMATOLOGY_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required artifact not found: {path}")
    contract = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    features = contract.get("features")
    if not isinstance(features, list) or len(features) != 17:
        raise ValueError("Vercel API requires the 17-feature model contract")
    booster = xgb.Booster()
    booster.load_model(MODEL_PATH)
    app.state.model = booster
    app.state.features = features
    app.state.contract = contract
    app.state.climatology = Climatology(CLIMATOLOGY_PATH)
    app.state.api_key = api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_runtime(app)
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
    record: PredictionInput, climatology: Climatology
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
    previous_prediction: bool | None = None
    previous_date: date | None = None
    for record in records:
        if previous_date is not None and record.date != previous_date + timedelta(days=1):
            previous_prediction = None
        results.append(_predict(request, record, previous_prediction))
        previous_prediction = bool(results[-1].heatwave_prediction)
        previous_date = record.date
    return BatchPredictionOutput(count=len(results), predictions=results)
