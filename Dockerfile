FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY backend ./backend
COPY data/processed/fixtures_synthetic_wards.csv ./data/processed/fixtures_synthetic_wards.csv
COPY artifacts ./artifacts
COPY thermal ./thermal

USER appuser

EXPOSE 8080
CMD exec uvicorn backend.vercel_app:app --host 0.0.0.0 --port "${PORT}"
