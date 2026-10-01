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
    if (typeof item.model_version !== 'string' || !item.model_version || item.reference_period !== '2015-2018') {
      throw new Error('Missing corrected model provenance');
    }
    const thermal = item.thermal;
    if (!thermal || thermal.method_version !== 'daily-approximation-v1' || thermal.units !== 'degC' ||
        !['estimated', 'partial', 'unavailable'].includes(thermal.status) ||
        !Array.isArray(thermal.assumptions) || !thermal.assumptions.every(value => typeof value === 'string') ||
        !(thermal.unavailable_reason === null || typeof thermal.unavailable_reason === 'string')) {
      throw new Error('Invalid thermal provenance');
    }
    const available = ['wbgt_c', 'utci_c'].map(key => {
      if (thermal[key] !== null && (typeof thermal[key] !== 'number' || !Number.isFinite(thermal[key]))) {
        throw new Error('Invalid thermal value');
      }
      return thermal[key] !== null;
    }).filter(Boolean).length;
    if (thermal.status !== (available === 2 ? 'estimated' : available === 1 ? 'partial' : 'unavailable')) {
      throw new Error('Inconsistent thermal availability');
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
