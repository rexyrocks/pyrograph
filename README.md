# SIH26083 — Extreme Heatwave Early Warning System

Classical machine-learning training pipeline for binary daily heatwave detection
in Jaipur. It trains Random Forest and XGBoost models, compares them by CSI, and
saves the better model together with its exact inference feature contract.

## Run

```bash
python3 heatwave_pipeline.py \
  --data /path/to/jaipur_daily_2015_2024.csv \
  --output-dir outputs
```

The training period is 2015–2022 and the test period is 2023–2024. The first
three records are excluded after lag creation. Labels use a circular calendar
day ±7-day leave-one-year-out climatology: P95 defines `heatwave`, while P98
defines the separate post-hoc `severe` flag. No persistence rule is included in
training.

`wbgt` and `utci` are declared as optional placeholders. Once populated, add
their names to `ACTIVE_OPTIONAL_FEATURES` in `heatwave_pipeline.py`; they will
then automatically appear at the end of the saved inference feature order.

## Outputs

- `best_heatwave_model.joblib` — model selected by highest test CSI
- `feature_names.json` — exact ordered inference features
- `evaluation_metrics.json` — split details, class counts, imbalance weight,
  Precision, Recall, F1, CSI, and confusion matrices
- `<model>_feature_importances.csv` — sorted feature importances for both models
- `loyo_climatology_labels.csv` — daily LOYO normal, P95/P98 thresholds, binary
  heatwave label, and separate post-hoc severe flag

On macOS, XGBoost also requires the OpenMP runtime (`brew install libomp`).

## FastAPI backend

Start the API from the project directory:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Interactive API documentation is available at `http://localhost:8000/docs`.
The service provides:

- `GET /health` — readiness and loaded-model status
- `GET /model/info` — exact model feature order and label semantics
- `POST /predict` — one binary prediction with optional previous-day context
- `POST /predict/batch` — chronological predictions with automatic two-day
  persistence checks; date gaps reset the persistence state

Clients send the eight raw weather values and six lag values. The backend
calculates the LOYO climatological normal, P95/P98 thresholds,
`tmax_departure`, and cyclical date features. `severe` is true only when the
binary model predicts heatwave and `tmax` reaches the P98 threshold. An alert
is triggered only after two consecutive predicted heatwave days.

Artifact locations can be overridden with `HEATWAVE_MODEL_PATH`,
`HEATWAVE_FEATURES_PATH`, and `HEATWAVE_CLIMATOLOGY_PATH`. Browser origins are
configured as a comma-separated `CORS_ORIGINS` value.

Run the backend tests with:

```bash
python3 -m unittest -v
```

A deployment-ready `Dockerfile` includes XGBoost's Linux OpenMP dependency.
