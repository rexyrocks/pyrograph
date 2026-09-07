FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY outputs/best_heatwave_model.joblib ./outputs/best_heatwave_model.joblib
COPY outputs/feature_names.json ./outputs/feature_names.json
COPY outputs/loyo_climatology_labels.csv ./outputs/loyo_climatology_labels.csv

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
