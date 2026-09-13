export const MAX_OUTLOOK_AGE_MS = 30 * 60 * 1000;

export function localDate(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(now);
}

export function validateOutlook(payload, now = new Date()) {
  const generated = Date.parse(payload?.generated_at);
  if (!Number.isFinite(generated) || generated > now.getTime() + 60_000 ||
      now.getTime() - generated > MAX_OUTLOOK_AGE_MS) {
    throw new Error('Forecast is stale or has an invalid timestamp');
  }
  if (!Array.isArray(payload.outlook) || payload.outlook.length !== 5) {
    throw new Error('Expected five forecast days');
  }
  const today = localDate(now);
  payload.outlook.forEach((item, index) => {
    const expected = new Date(`${today}T00:00:00Z`);
    expected.setUTCDate(expected.getUTCDate() + index);
    if (item.date !== expected.toISOString().slice(0, 10)) {
      throw new Error('Forecast dates are stale or nonconsecutive');
    }
    for (const field of ['tmax', 'heatwave_probability', 'climatology_normal', 'climatology_p95', 'climatology_p98']) {
      if (typeof item[field] !== 'number' || !Number.isFinite(item[field])) {
        throw new Error(`Invalid forecast field: ${field}`);
      }
    }
    if (item.heatwave_probability < 0 || item.heatwave_probability > 1 ||
        ![0, 1].includes(item.heatwave_prediction) || typeof item.severe !== 'boolean' ||
        ![true, false, null].includes(item.persistence_met) ||
        !['historical', 'forecast_bootstrap'].includes(item.lag_source)) {
      throw new Error('Invalid forecast classification');
    }
  });
  return payload;
}
