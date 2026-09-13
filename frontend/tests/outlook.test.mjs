import test from 'node:test';
import assert from 'node:assert/strict';
import { validateOutlook, localDate } from '../lib/outlook-validation.js';

const now = new Date('2026-09-14T03:30:00Z');
function payload() {
  return {
    generated_at: now.toISOString(),
    outlook: Array.from({ length: 5 }, (_, i) => ({
      date: `2026-09-${14 + i}`, tmax: 35, heatwave_probability: .255,
      heatwave_prediction: 0, severe: false, persistence_met: null,
      climatology_normal: 32, climatology_p95: 37, climatology_p98: 39,
      lag_source: 'historical',
    })),
  };
}
test('fresh forecast retains full probability precision', () => {
  assert.equal(validateOutlook(payload(), now).outlook[0].heatwave_probability, .255);
  assert.equal(localDate(new Date('2026-09-13T20:00:00Z')), '2026-09-14');
});
test('stale, future, nonconsecutive and malformed responses are rejected', () => {
  for (const mutate of [
    p => { p.generated_at = '2026-09-14T00:00:00Z'; },
    p => { p.generated_at = '2026-09-15T00:00:00Z'; },
    p => { p.outlook[0].date = '2026-09-13'; },
    p => { p.outlook[2].date = '2026-09-18'; },
    p => { p.outlook[0].tmax = null; },
    p => { p.outlook[0].heatwave_probability = 1.2; },
  ]) {
    const p = payload(); mutate(p);
    assert.throws(() => validateOutlook(p, now));
  }
});
