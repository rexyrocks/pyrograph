# SIH26083 — Extreme Heatwave Early Warning System

Preliminary Jaipur heat-hazard classifier and uncalibrated planning-index demo.
The current serving model is from the legacy retrospective experiment. Its
metrics do not establish advance forecast skill, mortality risk or statewide
validity. A corrected evaluation is now available separately.

## Run

```bash
python3 heatwave_pipeline.py \
  --data /path/to/jaipur_daily_2015_2024.csv \
  --output-dir work/retrospective-v2
```

The corrected evaluation fixes the climate reference to 2015–2018, trains on
2019–2021, selects on 2022, and tests only the selected model on 2023–2024.
It uses realised daily weather and a short ±7-day percentile reference. The
period has been inspected in earlier experiments; fresh external validation is
still required. This command writes a report and does not replace serving
artifacts. See `docs/evaluation-retrospective-v2.json` and `docs/demo-readiness.md`.

`wbgt` and `utci` are produced by the separate `thermal` pipeline for heat-stress
reporting and dashboard use. They intentionally remain outside the 17-feature
heatwave classifier. Earlier feature decisions used the legacy experiment's
test period and must not be represented as independent final validation.

## Legacy serving artifacts in outputs/

These are retained for reproducibility. Their original LOYO preprocessing
included held-out years in training climatology and used test CSI to select
the model. `evaluation_metrics.json` explicitly records those limitations.

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
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Interactive API documentation is available at `http://localhost:8000/docs`.
The service provides:

- `GET /health` — readiness and loaded-model status
- `GET /model/info` — exact model feature order and label semantics
- `POST /predict` — one binary prediction with optional previous-day context
- `POST /predict/batch` — chronological predictions with automatic two-day
  persistence checks; date gaps reset the persistence state
- `POST /risk/assess` — transparent 0–100 heat-health planning index combining
  heat hazard and aggregate demographic vulnerability
- `GET /demographics/wards` — validated synthetic ward fixtures with explicit
  missing fields and non-operational provenance
- `POST /alerts/dispatch` and `GET /alerts/{alert_id}` — offline SMS/WhatsApp
  simulation with idempotency, deduplication, retries, and delivery receipts
- `/municipal/workflows` — role ownership, acknowledgement, escalation checks,
  state transitions, and an append-only audit trail

The alerts and municipal workflow are explicitly in-memory demo services. See
`docs/operations-demo.md` for their contracts and production limitations.

Clients send the eight raw weather values and six lag values. The backend
calculates the LOYO climatological normal, P95/P98 thresholds,
`tmax_departure`, and cyclical date features. `severe` is true only when the
binary model predicts heatwave and `tmax` reaches the P98 threshold. An alert
is triggered only after two consecutive predicted heatwave days.

WBGT and UTCI are consumed separately by heat-stress and presentation layers;
they are not required by the binary prediction endpoints.

The planning index is explicitly uncalibrated and always returns
`mortality_probability: null`. Annual state mortality totals are not treated as
training labels for daily local mortality. See
`docs/mortality-risk-index.md` for its formula, limitations, and calibration
requirements.

Artifact locations can be overridden with `HEATWAVE_MODEL_PATH`,
`HEATWAVE_FEATURES_PATH`, and `HEATWAVE_CLIMATOLOGY_PATH`. Browser origins are
configured as a comma-separated `CORS_ORIGINS` value.

Run the backend tests with:

```bash
python3 -m unittest -v
```

The `Dockerfile` includes Linux OpenMP and the synthetic demographic fixture.
Run `python3 -m scripts.smoke_image` on a Docker-enabled machine before release.

## Production architecture

The application is deployed across Vercel (Frontend) and Railway (Backend).
The browser requests the five-day outlook and the shared planning-index API. A Vercel
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
1. **Historical Weather API**: Fetches the past 3 days of gridded analysis/reanalysis to construct historical lag features (`tmax_lag1/2/3`, `tmin_lag1/2/3`) for Day 1. These are not necessarily station observations; availability depends on the upstream model.
2. **Forecast API**: Fetches the raw weather values for the 5-day outlook.

The pressure input uses Open-Meteo's `surface_pressure_mean` (not sea-level
pressure) because it matches the approximately 960 hPa distribution used to
train the Jaipur model at the city's elevation.

**Known limitation — lag bootstrapping:** Day 1 uses historical analysis values. Days 2–5 use preceding forecast temperatures as lag inputs. Lead-time performance has not been validated. Day 1 persistence remains unknown when no prior-day classification is supplied.

The frontend distinguishes live, loading/unavailable and explicit synthetic
sample modes. Forecasts older than 30 minutes, incorrect dates and malformed
responses are rejected. The page refreshes every minute and uses the risk API
at full input precision. Municipal operations are demonstrated via the local
API rehearsal; the page does not claim an implemented operations console.

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
