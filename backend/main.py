"""Inference API for the SIH26083 classical heatwave model."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "outputs" / "best_heatwave_model.joblib"
DEFAULT_FEATURES_PATH = PROJECT_ROOT / "outputs" / "feature_names.json"
DEFAULT_CLIMATOLOGY_PATH = PROJECT_ROOT / "outputs" / "loyo_climatology_labels.csv"
WINDOW_RADIUS_DAYS = 7


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


class BatchPredictionOutput(StrictModel):
    count: int
    predictions: list[PredictionOutput]


class Climatology:
    """Calculate operational LOYO climatology from the historical tmax archive."""

    def __init__(self, path: Path) -> None:
        frame = pd.read_csv(path, usecols=["date", "tmax"])
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        if frame.empty or frame[["date", "tmax"]].isna().any().any():
            raise ValueError("Climatology archive is empty or contains missing values")
        self.years = frame["date"].dt.year.to_numpy()
        self.calendar_days = self._calendar_day_index(frame["date"])
        self.tmax = frame["tmax"].to_numpy(dtype=float)

    @staticmethod
    def _calendar_day_index(dates: pd.Series) -> np.ndarray:
        reference_dates = pd.to_datetime("2000-" + dates.dt.strftime("%m-%d"))
        return reference_dates.dt.dayofyear.to_numpy()

    @staticmethod
    def _request_calendar_day(value: date) -> int:
        return pd.Timestamp(year=2000, month=value.month, day=value.day).dayofyear

    def thresholds(self, target_date: date) -> tuple[float, float, float]:
        calendar_day = self._request_calendar_day(target_date)
        direct_distance = np.abs(self.calendar_days - calendar_day)
        circular_distance = np.minimum(direct_distance, 366 - direct_distance)
        reference_mask = (self.years != target_date.year) & (
            circular_distance <= WINDOW_RADIUS_DAYS
        )
        values = self.tmax[reference_mask]
        if values.size == 0:
            raise ValueError(f"No climatology reference values for {target_date.isoformat()}")
        return (
            float(np.mean(values)),
            float(np.percentile(values, 95)),
            float(np.percentile(values, 98)),
        )


def _artifact_path(environment_name: str, default: Path) -> Path:
    return Path(os.getenv(environment_name, str(default))).expanduser().resolve()


def _load_runtime(app: FastAPI) -> None:
    model_path = _artifact_path("HEATWAVE_MODEL_PATH", DEFAULT_MODEL_PATH)
    features_path = _artifact_path("HEATWAVE_FEATURES_PATH", DEFAULT_FEATURES_PATH)
    climatology_path = _artifact_path("HEATWAVE_CLIMATOLOGY_PATH", DEFAULT_CLIMATOLOGY_PATH)
    for path in (model_path, features_path, climatology_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required artifact not found: {path}")

    contract = json.loads(features_path.read_text(encoding="utf-8"))
    features = contract.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Feature contract must contain a non-empty 'features' list")

    model = joblib.load(model_path)
    trained_features = [str(value) for value in getattr(model, "feature_names_in_", [])]
    if trained_features and trained_features != features:
        raise ValueError("Saved model feature order does not match feature_names.json")

    app.state.model = model
    app.state.features = features
    app.state.contract = contract
    app.state.climatology = Climatology(climatology_path)
    app.state.model_name = type(model).__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_runtime(app)
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


def _engineer_features(record: PredictionInput, climatology: Climatology) -> tuple[dict[str, float], tuple[float, float, float]]:
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
    prediction = int(model.predict(frame)[0])
    probability = float(model.predict_proba(frame)[0, 1])

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
