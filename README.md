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

`wbgt` and `utci` are produced by the separate `thermal` pipeline for heat-stress
reporting and dashboard use. They intentionally remain outside the 17-feature
heatwave classifier because adding them did not improve the selected XGBoost
model's test CSI, recall, precision, or F1.

## Outputs

- `best_heatwave_model.joblib` — model selected by highest test CSI
- `feature_names.json` — exact ordered inference features
- `evaluation_metrics.json` — split details, class counts, imbalance weight,
  Precision, Recall, F1, CSI, and confusion matrices
- `<model>_feature_importances.csv` — sorted feature importances for both models
- `loyo_climatology_labels.csv` — daily LOYO normal, P95/P98 thresholds, binary
  heatwave label, and separate post-hoc severe flag
- `thermal_indices.csv` — separate daily WBGT and UTCI values for downstream
  heat-stress reporting

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

WBGT and UTCI are consumed separately by heat-stress and presentation layers;
they are not required by the binary prediction endpoints.

Artifact locations can be overridden with `HEATWAVE_MODEL_PATH`,
`HEATWAVE_FEATURES_PATH`, and `HEATWAVE_CLIMATOLOGY_PATH`. Browser origins are
configured as a comma-separated `CORS_ORIGINS` value.

Run the backend tests with:

```bash
python3 -m unittest -v
```

A deployment-ready `Dockerfile` includes XGBoost's Linux OpenMP dependency.

## Production architecture

The application is deployed across Vercel (Frontend) and Railway (Backend).
The browser can request only the cached, read-only five-day outlook. A Vercel
server function fetches Open-Meteo data and calls Railway's authenticated batch
predictor; the Railway key is never exposed to browser JavaScript. Generic
public prediction proxy routes are deliberately disabled.

### Infrastructure & Environment Variables

- **Frontend (Vercel)**: `https://heatshield-jaipur.vercel.app`
  - `RAILWAY_API_URL`: `https://heatshield-jaipur-api-production.up.railway.app`
  - `RAILWAY_API_KEY`: Secret key used to authorize requests against the backend.
- **Backend (Railway)**: `https://heatshield-jaipur-api-production.up.railway.app`
  - `HEATSHIELD_API_KEY`: Must match the frontend's `RAILWAY_API_KEY` to authorize incoming requests.
  - `CORS_ORIGINS`: Commma-separated list of allowed origins (e.g. `http://localhost:3000,http://localhost:5173,https://heatshield-jaipur.vercel.app`).

### Open-Meteo Integration & Lag Bootstrapping

The Vercel proxy fetches live weather data for Jaipur (26.91°N, 75.79°E) from Open-Meteo:
1. **Historical Weather API**: Fetches the past 3 days of observations to construct true historical lag features (`tmax_lag1/2/3`, `tmin_lag1/2/3`) for Day 1 of the outlook.
2. **Forecast API**: Fetches the raw weather values for the 5-day outlook.

The pressure input uses Open-Meteo's `surface_pressure_mean` (not sea-level
pressure) because it matches the approximately 960 hPa distribution used to
train the Jaipur model at the city's elevation.

**Known Limitation - Lag Bootstrapping**: Because the model strictly requires 3 days of lag features (previous day temperatures), Day 1 uses true historical observations. For Days 2–5, the preceding days are in the future, so the Vercel helper **bootstraps** their lag features by feeding the prior days' *forecasted* temperatures into the subsequent days' lag inputs. This allows all 5 days to be run through the live model prediction.

## Legacy Google Cloud Run deployment

> **Note:** Railway is now the active backend deployment. This section remains for historical reference.

The production container uses the lightweight native XGBoost Booster artifact,
not the training-time joblib bundle. Deploy it from this directory with:

```bash
gcloud run deploy heatshield-jaipur-api \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars CORS_ORIGINS=https://heatshield-jaipur.vercel.app
```

The frontend remains on Vercel. Cloud Run scales the API to zero when idle;
`min-instances=0` keeps eligible low-volume usage within the free allowance.
