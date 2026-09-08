"""Train and compare classical ML models for Jaipur heatwave detection.

The heatwave and severe labels are based on leave-one-year-out (LOYO)
climatology. This module deliberately keeps the IMD persistence rule outside
the training label; persistence belongs in the downstream alert layer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from xgboost import XGBClassifier


RAW_FEATURES = [
    "tmax",
    "tmin",
    "tmean",
    "rh_mean",
    "wind_speed_max",
    "pressure_mean",
    "solar_radiation_sum",
    "cloud_cover_mean",
]

LAG_FEATURES = [
    "tmax_lag1",
    "tmax_lag2",
    "tmax_lag3",
    "tmin_lag1",
    "tmin_lag2",
    "tmin_lag3",
]

ENGINEERED_FEATURES = ["tmax_departure", "doy_sin", "doy_cos"]

# Teammate-provided thermal indices can be activated later by moving them into
# ACTIVE_OPTIONAL_FEATURES. They are created as placeholder columns but are not
# used while unavailable because RandomForestClassifier cannot fit all-NaN data.
OPTIONAL_THERMAL_FEATURES = ["wbgt", "utci"]
ACTIVE_OPTIONAL_FEATURES: list[str] = []

FEATURES = RAW_FEATURES + LAG_FEATURES + ENGINEERED_FEATURES + ACTIVE_OPTIONAL_FEATURES
TARGET = "heatwave"
RANDOM_STATE = 42
TRAIN_END_YEAR = 2022
TEST_START_YEAR = 2023
WINDOW_RADIUS_DAYS = 7


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="Input daily CSV")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("outputs"), help="Artifact directory"
    )
    return parser.parse_args()


def validate_and_load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["date", *RAW_FEATURES]
    missing_columns = sorted(set(required) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df = df[required].copy()
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    df = df.sort_values("date").reset_index(drop=True)

    if df["date"].duplicated().any():
        duplicates = df.loc[df["date"].duplicated(), "date"].dt.strftime("%Y-%m-%d")
        raise ValueError(f"Duplicate dates found: {duplicates.tolist()[:5]}")
    if df[RAW_FEATURES].isna().any().any():
        null_counts = df[RAW_FEATURES].isna().sum()
        raise ValueError(f"Missing feature values found: {null_counts[null_counts > 0].to_dict()}")

    expected_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    if len(expected_dates) != len(df) or not np.array_equal(expected_dates, df["date"]):
        raise ValueError("Input must contain one row for every calendar day with no gaps")
    return df


def calendar_day_index(dates: pd.Series) -> np.ndarray:
    """Map month/day to a leap-year calendar index in [1, 366]."""
    month_day = dates.dt.strftime("%m-%d")
    reference_dates = pd.to_datetime("2000-" + month_day)
    return reference_dates.dt.dayofyear.to_numpy()


def add_loyo_climatology(df: pd.DataFrame) -> pd.DataFrame:
    """Add LOYO mean, P95, and P98 using a circular calendar ±7-day window."""
    result = df.copy()
    years = result["date"].dt.year.to_numpy()
    calendar_days = calendar_day_index(result["date"])
    tmax = result["tmax"].to_numpy(dtype=float)

    climatology_mean = np.empty(len(result), dtype=float)
    climatology_p95 = np.empty(len(result), dtype=float)
    climatology_p98 = np.empty(len(result), dtype=float)

    for index, (year, calendar_day) in enumerate(zip(years, calendar_days, strict=True)):
        direct_distance = np.abs(calendar_days - calendar_day)
        circular_distance = np.minimum(direct_distance, 366 - direct_distance)
        reference_mask = (years != year) & (circular_distance <= WINDOW_RADIUS_DAYS)
        reference_values = tmax[reference_mask]
        if reference_values.size == 0:
            raise ValueError(f"No LOYO reference data available for row {index}")

        climatology_mean[index] = np.mean(reference_values)
        climatology_p95[index] = np.percentile(reference_values, 95)
        climatology_p98[index] = np.percentile(reference_values, 98)

    result["climatology_normal_loyo"] = climatology_mean
    result["climatology_p95_loyo"] = climatology_p95
    result["climatology_p98_loyo"] = climatology_p98
    result["heatwave"] = (result["tmax"] >= result["climatology_p95_loyo"]).astype("int8")
    result["severe"] = (result["tmax"] >= result["climatology_p98_loyo"]).astype("int8")
    return result


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for variable in ("tmax", "tmin"):
        for lag in range(1, 4):
            result[f"{variable}_lag{lag}"] = result[variable].shift(lag)

    result["tmax_departure"] = result["tmax"] - result["climatology_normal_loyo"]
    day_of_year = result["date"].dt.dayofyear.to_numpy(dtype=float)
    days_in_year = np.where(result["date"].dt.is_leap_year, 366.0, 365.0)
    angle = 2.0 * np.pi * (day_of_year - 1.0) / days_in_year
    result["doy_sin"] = np.sin(angle)
    result["doy_cos"] = np.cos(angle)

    for feature in OPTIONAL_THERMAL_FEATURES:
        if feature not in result.columns:
            result[feature] = np.nan
    return result


def split_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_data = df.dropna(subset=FEATURES).copy()
    years = model_data["date"].dt.year
    train = model_data.loc[years <= TRAIN_END_YEAR].copy()
    test = model_data.loc[years >= TEST_START_YEAR].copy()

    if train.empty or test.empty:
        raise ValueError("Chronological split produced an empty train or test set")
    if train["date"].max() >= test["date"].min():
        raise AssertionError("Chronological train/test ordering was violated")
    return train, test


def metric_report(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, Any]:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    denominator = tp + fp + fn
    csi = float(tp / denominator) if denominator else 0.0
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "csi": csi,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "confusion_matrix_labels": [["TN", "FP"], ["FN", "TP"]],
    }


def train_models(train: pd.DataFrame) -> tuple[dict[str, Any], float]:
    negative_count = int((train[TARGET] == 0).sum())
    positive_count = int((train[TARGET] == 1).sum())
    if positive_count == 0:
        raise ValueError("Training data has no positive heatwave examples")
    scale_pos_weight = negative_count / positive_count

    models: dict[str, Any] = {
        "random_forest": RandomForestClassifier(
            n_estimators=500,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }
    for model in models.values():
        model.fit(train[FEATURES], train[TARGET])
    return models, scale_pos_weight


def evaluate_models(
    models: dict[str, Any], test: pd.DataFrame
) -> tuple[dict[str, dict[str, Any]], dict[str, pd.DataFrame]]:
    metrics: dict[str, dict[str, Any]] = {}
    importances: dict[str, pd.DataFrame] = {}
    for name, model in models.items():
        predictions = model.predict(test[FEATURES])
        metrics[name] = metric_report(test[TARGET], predictions)
        importances[name] = (
            pd.DataFrame({"feature": FEATURES, "importance": model.feature_importances_})
            .sort_values("importance", ascending=False)
            .reset_index(drop=True)
        )
    return metrics, importances


def save_artifacts(
    output_dir: Path,
    models: dict[str, Any],
    metrics: dict[str, dict[str, Any]],
    importances: dict[str, pd.DataFrame],
    scale_pos_weight: float,
    featured: pd.DataFrame,
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    # CSI is the locked primary selection metric. F1 is only a deterministic
    # tie-breaker if the two CSI values are identical.
    best_name = max(models, key=lambda name: (metrics[name]["csi"], metrics[name]["f1"]))
    joblib.dump(models[best_name], output_dir / "best_heatwave_model.joblib")

    feature_contract = {
        "features": FEATURES,
        "target": TARGET,
        "prediction_type": "binary",
        "severe_is_post_hoc_flag": True,
        "optional_inactive_features": OPTIONAL_THERMAL_FEATURES,
    }
    (output_dir / "feature_names.json").write_text(
        json.dumps(feature_contract, indent=2) + "\n", encoding="utf-8"
    )

    summary = {
        "selected_model": best_name,
        "selection_metric": "csi",
        "split": {"train": "2015-2022", "test": "2023-2024"},
        "train_rows": len(train),
        "test_rows": len(test),
        "train_class_counts": {
            "negative": int((train[TARGET] == 0).sum()),
            "positive": int((train[TARGET] == 1).sum()),
        },
        "test_class_counts": {
            "negative": int((test[TARGET] == 0).sum()),
            "positive": int((test[TARGET] == 1).sum()),
        },
        "xgboost_scale_pos_weight": scale_pos_weight,
        "metrics": metrics,
    }
    (output_dir / "evaluation_metrics.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    for name, table in importances.items():
        table.to_csv(output_dir / f"{name}_feature_importances.csv", index=False)
    featured[
        [
            "date",
            "tmax",
            "climatology_normal_loyo",
            "climatology_p95_loyo",
            "climatology_p98_loyo",
            "heatwave",
            "severe",
        ]
    ].to_csv(output_dir / "loyo_climatology_labels.csv", index=False)
    return best_name


def main() -> None:
    args = parse_args()
    raw = validate_and_load(args.data)
    labeled = add_loyo_climatology(raw)
    featured = engineer_features(labeled)
    train, test = split_data(featured)
    models, scale_pos_weight = train_models(train)
    metrics, importances = evaluate_models(models, test)
    selected = save_artifacts(
        args.output_dir,
        models,
        metrics,
        importances,
        scale_pos_weight,
        featured,
        train,
        test,
    )

    print(json.dumps({"selected_model": selected, "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
