import test from 'node:test';
import assert from 'node:assert/strict';
import { assertDaily } from '../api/outlook.js';

const dates = ['2026-09-29', '2026-09-30', '2026-10-01'];
const fields = ['temperature_2m_max', 'temperature_2m_min'];
function response() {
  return {
    timezone: 'Asia/Kolkata',
    daily_units: { temperature_2m_max: '°C', temperature_2m_min: '°C' },
    daily: { time: [...dates], temperature_2m_max: [32.4, 33, 33.8],
      temperature_2m_min: [25, 25.3, 25.6] },
  };
}

test('local dates and expected units permit complete lag weather', () => {
  assert.doesNotThrow(() => assertDaily(response(), fields, dates));
});

test('same-length responses with shifted dates or units fail closed', () => {
  const shifted = response();
  shifted.daily.time[0] = '2026-09-28';
  assert.throws(() => assertDaily(shifted, fields, dates), /local dates/);
  const wrongUnit = response();
  wrongUnit.daily_units.temperature_2m_max = '°F';
  assert.throws(() => assertDaily(wrongUnit, fields, dates), /unexpected units/);
  const wrongZone = response();
  wrongZone.timezone = 'UTC';
  assert.throws(() => assertDaily(wrongZone, fields, dates), /timezone/);
});
