const LATITUDE = 26.91;
const LONGITUDE = 75.79;
const TIMEZONE = 'Asia/Kolkata';
const DAYS = 5;

const DAILY_FIELDS = [
  'temperature_2m_max',
  'temperature_2m_min',
  'temperature_2m_mean',
  'relative_humidity_2m_mean',
  'wind_speed_10m_max',
  'surface_pressure_mean',
  'shortwave_radiation_sum',
  'cloud_cover_mean',
];

function jaipurDate() {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function shiftDate(isoDate, offsetDays) {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

function assertDaily(payload, fields, expectedDays) {
  if (!payload?.daily || payload.daily.time?.length !== expectedDays) {
    throw new Error('Unexpected Open-Meteo response length');
  }
  for (const field of fields) {
    const values = payload.daily[field];
    if (
      !Array.isArray(values) ||
      values.length !== expectedDays ||
      values.some((value) => typeof value !== 'number' || !Number.isFinite(value))
    ) {
      throw new Error(`Open-Meteo field unavailable: ${field}`);
    }
  }
}

async function fetchJson(url, timeoutMs = 12_000) {
  const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) throw new Error(`Upstream returned ${response.status}`);
  return response.json();
}

export default async function handler(request, response) {
  response.setHeader('X-Content-Type-Options', 'nosniff');
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return response.status(405).json({ detail: 'Method not allowed' });
  }

  const railwayUrl = process.env.RAILWAY_API_URL?.replace(/\/$/, '');
  const apiKey = process.env.RAILWAY_API_KEY;
  if (!railwayUrl || !apiKey) {
    return response.status(503).json({ detail: 'Prediction service unavailable' });
  }

  try {
    const today = jaipurDate();
    const historyStart = shiftDate(today, -3);
    const historyEnd = shiftDate(today, -1);
    const common = new URLSearchParams({
      latitude: String(LATITUDE),
      longitude: String(LONGITUDE),
      timezone: TIMEZONE,
    });
    const historyQuery = new URLSearchParams(common);
    historyQuery.set('start_date', historyStart);
    historyQuery.set('end_date', historyEnd);
    historyQuery.set('daily', 'temperature_2m_max,temperature_2m_min');
    const forecastQuery = new URLSearchParams(common);
    forecastQuery.set('forecast_days', String(DAYS));
    forecastQuery.set('daily', DAILY_FIELDS.join(','));

    const [history, forecast] = await Promise.all([
      fetchJson(`https://archive-api.open-meteo.com/v1/archive?${historyQuery}`),
      fetchJson(`https://api.open-meteo.com/v1/forecast?${forecastQuery}`),
    ]);
    assertDaily(history, ['temperature_2m_max', 'temperature_2m_min'], 3);
    assertDaily(forecast, DAILY_FIELDS, DAYS);

    const tmaxHistory = [...history.daily.temperature_2m_max];
    const tminHistory = [...history.daily.temperature_2m_min];
    const records = forecast.daily.time.map((date, index) => {
      const record = {
        date,
        tmax: forecast.daily.temperature_2m_max[index],
        tmin: forecast.daily.temperature_2m_min[index],
        tmean: forecast.daily.temperature_2m_mean[index],
        rh_mean: forecast.daily.relative_humidity_2m_mean[index],
        wind_speed_max: forecast.daily.wind_speed_10m_max[index],
        pressure_mean: forecast.daily.surface_pressure_mean[index],
        solar_radiation_sum: forecast.daily.shortwave_radiation_sum[index],
        cloud_cover_mean: forecast.daily.cloud_cover_mean[index],
        tmax_lag1: tmaxHistory.at(-1),
        tmax_lag2: tmaxHistory.at(-2),
        tmax_lag3: tmaxHistory.at(-3),
        tmin_lag1: tminHistory.at(-1),
        tmin_lag2: tminHistory.at(-2),
        tmin_lag3: tminHistory.at(-3),
      };
      tmaxHistory.push(record.tmax);
      tminHistory.push(record.tmin);
      return record;
    });

    const predictionResponse = await fetch(`${railwayUrl}/predict/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify({ records }),
      signal: AbortSignal.timeout(20_000),
    });
    if (!predictionResponse.ok) {
      throw new Error(`Prediction service returned ${predictionResponse.status}`);
    }
    const predictionPayload = await predictionResponse.json();
    if (predictionPayload.predictions?.length !== DAYS) {
      throw new Error('Unexpected prediction response length');
    }

    const outlook = predictionPayload.predictions.map((prediction, index) => ({
      ...prediction,
      tmax: records[index].tmax,
      tmin: records[index].tmin,
      tmean: records[index].tmean,
      rh_mean: records[index].rh_mean,
      wind_speed_max: records[index].wind_speed_max,
      pressure_mean: records[index].pressure_mean,
      solar_radiation_sum: records[index].solar_radiation_sum,
      cloud_cover_mean: records[index].cloud_cover_mean,
      lag_source: index === 0 ? 'historical' : 'forecast_bootstrap',
    }));

    response.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=1800');
    return response.status(200).json({
      location: { name: 'Jaipur, Rajasthan', latitude: LATITUDE, longitude: LONGITUDE },
      generated_at: new Date().toISOString(),
      outlook,
      methodology: {
        day_1_lags: `Open-Meteo Historical Weather API (${historyStart} to ${historyEnd})`,
        days_2_to_5_lags: 'Bootstrapped from preceding forecast days',
      },
    });
  } catch (error) {
    console.error('Outlook generation failed', error);
    response.setHeader('Cache-Control', 'no-store');
    return response.status(502).json({ detail: 'Live outlook temporarily unavailable' });
  }
}
