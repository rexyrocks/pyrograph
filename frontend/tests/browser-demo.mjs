// Test built frontend with controlled weather responses and the real local risk API.
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { localDate } from '../lib/outlook-validation.js';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PACKAGE_PATH || 'playwright');
const output = process.env.DEMO_QA_OUTPUT || 'work/browser-demo';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const reports = [];
const errors = [];
const forecast = () => ({
  generated_at: new Date().toISOString(),
  outlook: Array.from({ length: 5 }, (_, i) => {
    const date = new Date(`${localDate()}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + i);
    return {
      date: date.toISOString().slice(0, 10), tmax: 35,
      heatwave_probability: .255, heatwave_prediction: 0, severe: false,
      persistence_met: false, climatology_normal: 32, climatology_p95: 37,
      climatology_p98: 39, lag_source: 'historical',
    };
  }),
});

async function scenario(name, mode, viewport, verify) {
  const page = await browser.newPage({ viewport });
  page.on('pageerror', error => errors.push(`${name}: ${error.message}`));
  await page.route('**/api/outlook', async route => {
    const data = forecast();
    if (mode === 'stale') data.generated_at = '2020-01-01T00:00:00Z';
    await route.fulfill({ status: mode === 'failure' ? 502 : 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.route('**/api/risk/assess', async route => {
    const request = route.request();
    const result = await page.request.post('http://127.0.0.1:18766/risk/assess', {
      headers: { 'X-API-Key': 'local-browser-test-key-00000000000000', 'Content-Type': 'application/json' },
      data: request.postData(),
    });
    await route.fulfill({ response: result });
  });
  await page.goto('http://127.0.0.1:18765');
  await verify(page);
  await page.screenshot({ path: `${output}/${name}.png`, fullPage: true });
  reports.push({ name, status: 'passed' });
  await page.close();
}

try {
  await scenario('live-and-api-boundary', 'live', { width: 1440, height: 1000 }, async page => {
    await page.getByText('LIVE FORECAST —', { exact: false }).waitFor();
    await page.getByText('Low planning priority', { exact: true }).waitFor();
    assert.equal(await page.locator('.impact-number').innerText(), '29.8/100');
    assert.equal(await page.locator('.forecast-card').count(), 5);
  });
  for (const mode of ['failure', 'stale']) {
    await scenario(mode, mode, { width: 1440, height: 1000 }, async page => {
      await page.getByRole('heading', { name: 'Forecast unavailable', exact: true }).waitFor();
      assert.equal(await page.locator('.temperature-panel').count(), 0);
      assert.equal(await page.locator('.impact-number').count(), 0);
      await page.getByRole('button', { name: 'Explore synthetic sample' }).click();
      await page.getByText('SYNTHETIC SAMPLE —', { exact: false }).waitFor();
      await page.locator('.impact-number').waitFor();
      assert.equal(await page.getByText('Today', { exact: true }).count(), 0);
      await page.getByRole('button', { name: 'Return to live forecast' }).click();
      await page.getByRole('heading', { name: 'Forecast unavailable', exact: true }).waitFor();
    });
  }
  await scenario('fixtures-and-mobile', 'live', { width: 390, height: 844 }, async page => {
    await page.getByText('Low planning priority', { exact: true }).waitFor();
    const select = page.getByLabel('Load a synthetic ward fixture');
    const incomplete = select.locator('option:disabled');
    assert.equal(await incomplete.count(), 2);
    assert.match((await incomplete.allTextContents()).join(' '), /incomplete/);
    const firstComplete = await select.locator('option:not(:disabled)').nth(1).getAttribute('value');
    await select.selectOption(firstComplete);
    await page.getByText('Synthetic population:', { exact: false }).waitFor();
    await page.getByRole('button', { name: 'Open navigation' }).click();
    const nav = page.getByRole('navigation', { name: 'Mobile navigation' });
    await nav.getByRole('link', { name: 'guidance' }).click();
    assert.equal(await nav.count(), 0);
    assert.equal(new URL(page.url()).hash, '#guidance');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  });
  assert.deepEqual(errors, []);
  await writeFile(`${output}/results.json`, JSON.stringify({ weather: 'controlled test fixtures; live mode exercised', risk: 'real local API', reports, browserErrors: errors }, null, 2));
  console.log(JSON.stringify(reports, null, 2));
} finally {
  await browser.close();
}
