'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowRight,
  Building2,
  Clock3,
  Droplets,
  HeartPulse,
  Info,
  MapPin,
  Menu,
  ShieldCheck,
  Sparkles,
  Sun,
  TriangleAlert,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';
import { Slider } from '@/components/ui/slider';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { validateOutlook } from '@/lib/outlook-validation';
import demographicsCsv from '../data/fixtures_synthetic_wards.csv?raw';

type Risk = 'Moderate' | 'High' | 'Severe';
type ImpactBand = 'Low' | Risk;
type ThermalEstimate = {
  method_version: string;
  status: 'estimated' | 'partial' | 'unavailable';
  wbgt_c: number | null;
  utci_c: number | null;
  units: 'degC';
  assumptions: string[];
  unavailable_reason: string | null;
};

type OutlookItem = {
  day: string;
  date: string;
  temperature: number;
  probability: number;
  risk: Risk;
  note: string;
  normal: number;
  p95: number;
  p98: number;
  persistenceMet: boolean | null;
  thermal?: ThermalEstimate;
  modelVersion?: string;
};

type LiveOutlookRecord = {
  date: string;
  severe: boolean;
  heatwave_prediction: number;
  heatwave_probability: number;
  tmax: number;
  lag_source: 'historical' | 'forecast_bootstrap';
  climatology_normal: number;
  climatology_p95: number;
  climatology_p98: number;
  persistence_met: boolean | null;
  model_version: string;
  reference_period: string;
  thermal: ThermalEstimate;
};

type LiveOutlookResponse = {
  generated_at: string;
  outlook: LiveOutlookRecord[];
};

const fallbackOutlook: OutlookItem[] = [
  { day: 'Today', date: '08 Sep', temperature: 44, probability: 81, risk: 'High', note: 'Prototype fallback', normal: 39.2, p95: 42.1, p98: 44.6, persistenceMet: true },
  { day: 'Wed', date: '09 Sep', temperature: 45, probability: 88, risk: 'Severe', note: 'Prototype fallback', normal: 39.4, p95: 42.2, p98: 44.7, persistenceMet: true },
  { day: 'Thu', date: '10 Sep', temperature: 43, probability: 76, risk: 'High', note: 'Prototype fallback', normal: 39.4, p95: 42.2, p98: 44.7, persistenceMet: true },
  { day: 'Fri', date: '11 Sep', temperature: 41, probability: 54, risk: 'Moderate', note: 'Prototype fallback', normal: 39.3, p95: 42.1, p98: 44.6, persistenceMet: false },
  { day: 'Sat', date: '12 Sep', temperature: 40, probability: 38, risk: 'Moderate', note: 'Prototype fallback', normal: 39.1, p95: 42.0, p98: 44.5, persistenceMet: false },
];

const sampleOutlook = fallbackOutlook.map((item, index) => ({
  ...item, day: `Sample day ${index + 1}`, date: 'Illustrative', note: 'Synthetic sample',
}));

type Assessment = {
  index: number;
  band: ImpactBand;
  heat_hazard_score: number;
  vulnerability_score: number;
  drivers: { factor: string; contribution: number; display_value: string }[];
  municipal_actions: { priority: string; action: string }[];
};

const riskClass: Record<Risk, string> = {
  Moderate: 'risk-moderate',
  High: 'risk-high',
  Severe: 'risk-severe',
};

const predictionLabel: Record<Risk, string> = {
  Moderate: 'No heatwave predicted',
  High: 'Heatwave predicted',
  Severe: 'Severe heatwave predicted',
};

function formatModelEstimate(percent: number) {
  return percent > 0 && percent < 0.1 ? '<0.1%' : `${percent.toFixed(1)}%`;
}

type VulnerabilityProfile = {
  olderAdults: number;
  youngChildren: number;
  outdoorWorkers: number;
  informalHousing: number;
  deprivation: number;
};

type DemoWard = {
  wardId: string;
  population: number;
  olderAdults: number;
  youngChildren: number;
  outdoorWorkers: number | null;
  informalHousing: number | null;
};

function parseDemoWards(csv: string): DemoWard[] {
  return csv.trim().split('\n').slice(1).map((line) => {
    const [wardId, population, olderAdults, youngChildren, outdoorWorkers, informalHousing] = line.split(',');
    return {
      wardId,
      population: Number(population),
      olderAdults: Number(olderAdults),
      youngChildren: Number(youngChildren),
      outdoorWorkers: outdoorWorkers === '' ? null : Number(outdoorWorkers),
      informalHousing: informalHousing === '' ? null : Number(informalHousing),
    };
  });
}

const demoWards = parseDemoWards(demographicsCsv);

const defaultVulnerability: VulnerabilityProfile = {
  olderAdults: 9,
  youngChildren: 10,
  outdoorWorkers: 31,
  informalHousing: 18,
  deprivation: 52,
};

function ScenarioSlider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="scenario-control">
      <div><span>{label}</span><output>{value}%</output></div>
      <Slider
        aria-label={label}
        min={0}
        max={100}
        step={1}
        value={[value]}
        onValueChange={(nextValue) => onChange(Array.isArray(nextValue) ? nextValue[0] : nextValue)}
      />
    </div>
  );
}

export default function Home() {
  const [selectedDay, setSelectedDay] = useState(0);
  const [vulnerabilityProfile, setVulnerabilityProfile] = useState(defaultVulnerability);
  const [selectedDemoWard, setSelectedDemoWard] = useState('');
  const [outlook, setOutlook] = useState<OutlookItem[]>(sampleOutlook);
  const [apiStatus, setApiStatus] = useState<'loading' | 'live' | 'unavailable'>('loading');
  const [sampleMode, setSampleMode] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [assessment, setAssessment] = useState<{ key: string; result: Assessment } | null>(null);
  const [assessmentError, setAssessmentError] = useState('');
  const [updatedAt, setUpdatedAt] = useState('Loading live outlook…');
  const displayedOutlook = sampleMode ? sampleOutlook : outlook;
  const selected = displayedOutlook[selectedDay];
  const temperatureRuleFlags = selected.temperature >= selected.p95;
  const classifierFlags = selected.risk === 'High' || selected.risk === 'Severe';
  const hasOutlook = sampleMode || apiStatus === 'live';
  const demoWard = useMemo(
    () => demoWards.find((ward) => ward.wardId === selectedDemoWard) ?? null,
    [selectedDemoWard],
  );
  const assessmentBody = JSON.stringify({
    heatwave_probability: selected.probability / 100,
    severe: selected.risk === 'Severe',
    persistence_met: selected.persistenceMet,
    vulnerability: {
      older_adult_share: vulnerabilityProfile.olderAdults / 100,
      young_child_share: vulnerabilityProfile.youngChildren / 100,
      outdoor_worker_share: vulnerabilityProfile.outdoorWorkers / 100,
      informal_housing_share: vulnerabilityProfile.informalHousing / 100,
      social_deprivation_index: vulnerabilityProfile.deprivation / 100,
    },
  });
  const impact = hasOutlook && assessment?.key === assessmentBody ? assessment.result : null;

  useEffect(() => {
    if (!hasOutlook) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetch('/api/risk/assess', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: assessmentBody,
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]),
      }).then(async (response) => {
        if (!response.ok) throw new Error('Assessment unavailable');
        const result = await response.json() as Assessment & { mortality_probability: null };
        if (result.mortality_probability !== null || !Number.isFinite(result.index) ||
            !Array.isArray(result.drivers) || !Array.isArray(result.municipal_actions)) {
          throw new Error('Invalid assessment');
        }
        if (!controller.signal.aborted) {
          setAssessment({ key: assessmentBody, result });
          setAssessmentError('');
        }
      }).catch(() => {
        if (!controller.signal.aborted) setAssessmentError('Planning index unavailable. No local substitute score is shown.');
      });
    }, 150);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [assessmentBody, hasOutlook]);

  const updateVulnerability = (key: keyof VulnerabilityProfile, value: number) => {
    setVulnerabilityProfile((current) => ({ ...current, [key]: value }));
  };

  const loadDemoWard = (wardId: string) => {
    setSelectedDemoWard(wardId);
    const ward = demoWards.find((candidate) => candidate.wardId === wardId);
    if (!ward || ward.outdoorWorkers === null || ward.informalHousing === null) return;
    const outdoorWorkers = ward.outdoorWorkers;
    const informalHousing = ward.informalHousing;
    setVulnerabilityProfile((current) => ({
      ...current,
      olderAdults: ward.olderAdults,
      youngChildren: ward.youngChildren,
      outdoorWorkers,
      informalHousing,
      deprivation: defaultVulnerability.deprivation,
    }));
  };

  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => fetch('/api/outlook', {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]),
    })
      .then((response) => {
        if (!response.ok) throw new Error('Live outlook unavailable');
        return response.json() as Promise<LiveOutlookResponse>;
      })
      .then((payload) => {
        validateOutlook(payload);
        if (controller.signal.aborted) return;
        const liveOutlook: OutlookItem[] = payload.outlook.map((item, index) => {
          const isoDate = item.date;
          const parsedDate = new Date(`${isoDate}T00:00:00Z`);
          const severe = item.severe;
          const heatwave = item.heatwave_prediction === 1;
          return {
            day: index === 0 ? 'Today' : parsedDate.toLocaleDateString('en-IN', { weekday: 'short', timeZone: 'UTC' }),
            date: parsedDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', timeZone: 'UTC' }),
            temperature: item.tmax,
            probability: item.heatwave_probability * 100,
            risk: severe ? 'Severe' : heatwave ? 'High' : 'Moderate',
            note: item.lag_source === 'historical' ? 'Historical analysis lags' : 'Forecast-derived lags',
            normal: item.climatology_normal,
            p95: item.climatology_p95,
            p98: item.climatology_p98,
            persistenceMet: item.persistence_met,
            thermal: item.thermal,
            modelVersion: item.model_version,
          };
        });
        setOutlook(liveOutlook);
        setApiStatus('live');
        setUpdatedAt(
          new Date(payload.generated_at).toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
            timeZone: 'Asia/Kolkata',
            timeZoneName: 'short',
          }),
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setApiStatus('unavailable');
          setUpdatedAt('Live forecast unavailable or stale');
        }
      });
    void refresh();
    const timer = setInterval(refresh, 60_000);
    return () => { clearInterval(timer); controller.abort(); };
  }, []);

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Pyrograph Jaipur home">
          <span className="brand-mark"><Sun size={19} /></span>
          <span>Pyrograph <b>Jaipur</b></span>
        </a>

        <nav className="desktop-nav" aria-label="Primary navigation">
          <a className="active" href="#overview">Overview</a>
          <a href="#impact">Impact index</a>
          <a href="#guidance">Guidance</a>
        </nav>

        <div className="header-actions">
          <Badge className="prototype-badge" aria-live="polite">
            {sampleMode ? 'Synthetic sample' : apiStatus === 'live' ? 'Live forecast' : apiStatus === 'loading' ? 'Loading forecast…' : 'Forecast unavailable'}
          </Badge>
          <Button variant="ghost" size="icon" className="mobile-menu" aria-label="Open navigation" aria-expanded={mobileMenuOpen} aria-controls="mobile-navigation" onClick={() => setMobileMenuOpen((open) => !open)}>
            <Menu />
          </Button>
        </div>
      </header>
      {mobileMenuOpen && <nav id="mobile-navigation" className="mobile-navigation" aria-label="Mobile navigation">
        {['overview', 'impact', 'guidance'].map((section) => <a key={section} href={`#${section}`} onClick={() => setMobileMenuOpen(false)}>{section === 'impact' ? 'Planning index' : section}</a>)}
      </nav>}
      <div className="data-mode-banner" aria-live="polite">
        <b>{sampleMode ? 'SYNTHETIC SAMPLE — invented temperatures, not current weather.' : apiStatus === 'live' ? 'LIVE FORECAST — preliminary model; not an official warning.' : apiStatus === 'loading' ? 'LOADING — no current heat assessment available.' : 'UNAVAILABLE — live data is missing, invalid or stale. No current heat assessment is shown.'}</b>
        <Button variant="outline" onClick={() => { setSampleMode((current) => !current); setSelectedDay(0); }}>{sampleMode ? 'Return to live forecast' : 'Explore synthetic sample'}</Button>
      </div>

      {hasOutlook ? <>
      <section id="top" className="hero-shell">
        <div className="eyebrow-row">
          <span className="eyebrow"><MapPin size={14} /> Jaipur, Rajasthan</span>
          <span className="update-time"><Clock3 size={14} /> {sampleMode ? 'Illustrative scenario · no observation date' : `Updated ${updatedAt}`}</span>
        </div>

        <div className="hero-grid">
          <div className="hero-copy">
            <Badge className="warning-badge"><TriangleAlert size={14} /> {sampleMode ? 'Sample' : 'Preliminary'} · {predictionLabel[selected.risk]}</Badge>
            <h1>{sampleMode ? 'Explore a sample' : 'Jaipur forecast'}<br />heat scenario.</h1>
            <p>
              {selected.risk === 'Moderate'
                ? 'The classifier does not flag this day as a heatwave. This is a preliminary model result, not a guarantee of safe conditions.'
                : 'The preliminary classifier flags elevated heat hazard. Check official local advisories before making operational decisions.'}
            </p>
            <div className="hero-actions">
              <Button
                className="primary-cta"
                onClick={() => document.getElementById('guidance')?.scrollIntoView({ behavior: 'smooth' })}
              >
                What should I do? <ArrowRight />
              </Button>
              <Sheet>
                <SheetTrigger render={<Button variant="outline" className="reason-button" />}>
                  <Info /> Explain this scenario
                </SheetTrigger>
                <SheetContent className="reason-sheet">
                  <SheetHeader>
                    <Badge className="sheet-badge">Preliminary hazard logic</Badge>
                    <SheetTitle>How this prediction was made</SheetTitle>
                    <SheetDescription>
                      The warning combines the model probability with Jaipur&apos;s calendar-day climate thresholds.
                    </SheetDescription>
                  </SheetHeader>
                  <div className="reason-body">
                    <div className="threshold-card current"><span>Forecast Tmax</span><b>{selected.temperature.toFixed(1)}°C</b></div>
                    <div className="threshold-flow"><span /> compared with <span /></div>
                    <div className="threshold-card"><span>Fixed-reference P95 threshold</span><b>{selected.p95.toFixed(1)}°C</b></div>
                    <p>Model: {selected.modelVersion ?? "Synthetic scenario"} · Reference: 2015–2018</p>
                    <ul className="reason-list">
                      <li><span>Uncalibrated model estimate</span><b>{formatModelEstimate(selected.probability)}</b></li>
                      <li><span>Forecast-temperature rule</span><b>{temperatureRuleFlags ? 'P95 crossed' : 'Below P95'}</b></li>
                      <li><span>Departure from normal</span><b>{selected.temperature - selected.normal >= 0 ? '+' : ''}{(selected.temperature - selected.normal).toFixed(1)}°C</b></li>
                      <li><span>Persistence check</span><b>{selected.persistenceMet === true ? 'Met · day 2 of 2' : selected.persistenceMet === false ? 'Not met' : 'Pending prior day'}</b></li>
                      <li><span>P98 severe threshold</span><b>{selected.p98.toFixed(1)}°C</b></li>
                    </ul>
                    <p className="explain-note">
                      The model uses a fixed 2015–2018 climate reference with separate fitting, selection and test periods.
                      Retrospective results do not establish advance forecast accuracy.
                      {!sampleMode && (classifierFlags !== temperatureRuleFlags ? ' The classifier and temperature rule disagree for this date; treat this as an unresolved preliminary result.' : ' The classifier and temperature rule agree for this date, but that agreement does not validate either forecast.')}
                      Percentile thresholds and this daily hazard label are not an official IMD declaration.
                      Persistence must be assessed separately; unknown is not confirmed.
                    </p>
                  </div>
                </SheetContent>
              </Sheet>
            </div>
          </div>

          <div className="temperature-panel" aria-label="Current risk summary">
            <div className="temp-topline"><span>Expected maximum</span><Sun size={22} /></div>
            <div className="temperature">{selected.temperature.toFixed(1)}<sup>°C</sup></div>
            <div className="risk-line">
              <span className={`risk-pill ${riskClass[selected.risk]}`}>{predictionLabel[selected.risk]}</span>
              <span>{formatModelEstimate(selected.probability)} uncalibrated model estimate</span>
            </div>
            <div className="confidence-track"><span style={{ width: `${selected.probability}%` }} /></div>
            <div className="mini-stats">
              <span><small>Normal</small><b>{selected.normal.toFixed(1)}°C</b></span>
              <span><small>Departure</small><b>{selected.temperature - selected.normal >= 0 ? '+' : ''}{(selected.temperature - selected.normal).toFixed(1)}°C</b></span>
              <span><small>Persistence</small><b>{selected.persistenceMet === true ? 'Met' : selected.persistenceMet === false ? 'Not met' : 'Unknown'}</b></span>
            </div>
          </div>
        </div>
      </section>

      <div className="page-wrap">
        <section className="section-block" aria-label="Daily thermal estimates">
          <div className="section-heading"><div><span className="kicker">Thermal stress</span><h2>Daily thermal estimates</h2></div></div>
          {selected.thermal ? <>
            <div className="mini-stats">
              <span><small>WBGT estimate</small><b>{selected.thermal.wbgt_c === null ? 'Unavailable' : `${selected.thermal.wbgt_c.toFixed(1)}°C`}</b></span>
              <span><small>UTCI estimate</small><b>{selected.thermal.utci_c === null ? 'Unavailable' : `${selected.thermal.utci_c.toFixed(1)}°C`}</b></span>
              <span><small>Forecast date</small><b>{selected.date}</b></span>
            </div>
            <p>Estimates use daily weather and approximate radiation. They do not represent peak-hour exposure or mortality risk.</p>
            {selected.thermal.unavailable_reason && <p role="note">{selected.thermal.unavailable_reason}</p>}
            <details><summary>Calculation assumptions</summary><ul>{selected.thermal.assumptions.map(text => <li key={text}>{text}</li>)}</ul></details>
          </> : <p>Thermal estimates are unavailable for this synthetic scenario.</p>}
        </section>
        <section id="overview" className="forecast-section section-block">
          <div className="section-heading">
            <div>
              <span className="kicker">Plan ahead</span>
              <h2>Five-day heat outlook</h2>
              <p className="weather-source">{sampleMode ? 'Synthetic temperatures for illustration only' : 'Temperature source: Open-Meteo Forecast API · Jaipur 26.91°N, 75.79°E'}</p>
            </div>
            <div className="view-switcher">
              <span>Municipal operations are demonstrated through the local API.</span>
            </div>
          </div>
          <div className="forecast-scroll">
            <div className="forecast-grid">
              {displayedOutlook.map((item, index) => (
                <button
                  key={item.day}
                  className={`forecast-card ${selectedDay === index ? 'selected' : ''}`}
                  onClick={() => setSelectedDay(index)}
                  aria-pressed={selectedDay === index}
                >
                  <span className="forecast-day"><b>{item.day}</b><small>{item.date}</small></span>
                  <strong className="forecast-temp">{item.temperature.toFixed(1)}°</strong>
                  <span className={`forecast-risk ${riskClass[item.risk]}`}>{predictionLabel[item.risk]}</span>
                  <span className="forecast-prob"><i style={{ width: `${item.probability}%` }} />{formatModelEstimate(item.probability)} model estimate</span>
                  <small className="forecast-note">{item.note}</small>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section id="impact" className="impact-section section-block">
          <div className="section-heading">
            <div>
              <span className="kicker">Population impact</span>
              <h2>Heat-health planning index</h2>
              <p className="weather-source">Prototype impact-index-v1 · Selected forecast day and aggregate scenario inputs</p>
            </div>
            <Badge variant="outline">Auditable formula</Badge>
          </div>

          <div className="prototype-notice" role="note">
            <Info size={17} />
            <span><b>This is not mortality probability.</b> It is an uncalibrated planning index. Suitable daily local health outcomes are still required before mortality probability can be trained or validated.</span>
          </div>

          <div className="impact-grid">
            <article className="impact-score-card" aria-live="polite">
              {impact ? <>
              <div className="impact-score-top">
                <span>Planning index</span>
                <Badge variant="outline">{selected.day} · {selected.date}</Badge>
              </div>
              <div className="impact-number">{impact.index}<small>/100</small></div>
              <span className={`impact-band impact-${impact.band.toLowerCase()}`}>{impact.band} planning priority</span>
              <div className="component-scores">
                <div>
                  <span><b>Heat hazard</b><strong>{impact.heat_hazard_score}</strong></span>
                  <i><em style={{ width: `${impact.heat_hazard_score}%` }} /></i>
                </div>
                <div>
                  <span><b>Vulnerability</b><strong>{impact.vulnerability_score}</strong></span>
                  <i><em style={{ width: `${impact.vulnerability_score}%` }} /></i>
                </div>
              </div>
              <p className="formula-note">70% heat hazard + 30% demographic vulnerability. Severe and two-day persistence checks modify the hazard component.</p>
              </> : <p>{assessmentError || 'Calculating the planning index…'}</p>}
            </article>

            <article className="scenario-card">
              <div className="scenario-heading">
                <div><span className="kicker">Scenario controls</span><h3>Test aggregate vulnerability</h3></div>
                <Button variant="ghost" size="sm" onClick={() => { setSelectedDemoWard(''); setVulnerabilityProfile(defaultVulnerability); }}>Reset</Button>
              </div>
              <p>Load a synthetic fixture or adjust the values. These are not official Jaipur demographic estimates. Social deprivation resets to a manual sample value of 52 when a fixture is loaded.</p>
              <div className="demo-ward-picker">
                <NativeSelect
                  aria-label="Load a synthetic ward fixture"
                  value={selectedDemoWard}
                  onChange={(event) => loadDemoWard(event.target.value)}
                >
                  <NativeSelectOption value="">Manual demonstration scenario</NativeSelectOption>
                  {demoWards.map((ward) => (
                    <NativeSelectOption
                      key={ward.wardId}
                      value={ward.wardId}
                      disabled={ward.outdoorWorkers === null || ward.informalHousing === null}
                    >
                      {ward.wardId}{ward.outdoorWorkers === null || ward.informalHousing === null ? ' · incomplete' : ''}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
                {demoWard && (
                  <span>
                    Synthetic population: {demoWard.population.toLocaleString('en-IN')}
                  </span>
                )}
              </div>
              <ScenarioSlider label="Older adults" value={vulnerabilityProfile.olderAdults} onChange={(value) => updateVulnerability('olderAdults', value)} />
              <ScenarioSlider label="Children under five" value={vulnerabilityProfile.youngChildren} onChange={(value) => updateVulnerability('youngChildren', value)} />
              <ScenarioSlider label="Outdoor workers" value={vulnerabilityProfile.outdoorWorkers} onChange={(value) => updateVulnerability('outdoorWorkers', value)} />
              <ScenarioSlider label="Informal housing" value={vulnerabilityProfile.informalHousing} onChange={(value) => updateVulnerability('informalHousing', value)} />
              <ScenarioSlider label="Social deprivation index" value={vulnerabilityProfile.deprivation} onChange={(value) => updateVulnerability('deprivation', value)} />
            </article>
          </div>

          {impact && <div className="impact-detail-grid">
            <article>
              <span className="kicker">What drives the score</span>
              <h3>Top vulnerability contributors</h3>
              <ol className="driver-list">
                {impact.drivers.map((driver) => (
                  <li key={driver.factor}>
                    <span>{driver.factor}<small>Scenario value {driver.display_value}</small></span>
                    <b>+{driver.contribution.toFixed(1)} vulnerability pts</b>
                  </li>
                ))}
              </ol>
            </article>
            <article>
              <span className="kicker">Municipal trigger</span>
              <h3>Actions for {impact.band.toLowerCase()} priority</h3>
              <ul className="trigger-list">
                {impact.municipal_actions.map((action) => <li key={action.action}><ShieldCheck />{action.action}</li>)}
              </ul>
            </article>
          </div>}
        </section>
      </div>
      </> : <section className="page-wrap unavailable-panel" id="overview"><h1>{apiStatus === 'loading' ? 'Loading forecast' : 'Forecast unavailable'}</h1><p>Current temperatures and planning scores are hidden until a fresh forecast is available. You can explicitly explore a synthetic sample above.</p></section>}

      <section id="guidance" className="guidance-section">
        <div className="page-wrap">
          <div className="section-heading light">
            <div><span className="kicker">General preparedness</span><h2>Heat safety guidance</h2></div>
            <p>Simple actions that reduce exposure and protect people at highest risk.</p>
          </div>
          <div className="action-grid">
            <article><span className="action-icon"><Clock3 /></span><b>Reschedule outdoor work</b><p>Move strenuous activity before 11 AM or after 5 PM.</p></article>
            <article><span className="action-icon"><Droplets /></span><b>Hydrate more often</b><p>Drink water regularly—even before you feel thirsty.</p></article>
            <article><span className="action-icon"><HeartPulse /></span><b>Check on vulnerable people</b><p>Older adults, infants, outdoor workers, and people living alone need extra support.</p></article>
            <article><span className="action-icon"><Building2 /></span><b>Use cooler spaces</b><p>Stay shaded or indoors during the afternoon peak.</p></article>
          </div>
          <div className="symptoms-banner">
            <TriangleAlert />
            <p><b>Know the warning signs.</b> Confusion, fainting, very hot skin, or loss of consciousness can indicate heatstroke.</p>
            <a href="tel:112">Emergency: 112 <ArrowRight /></a>
          </div>
        </div>
      </section>

      <section className="trust-strip">
        <div className="page-wrap trust-grid">
          <div><ShieldCheck /><span><b>Classical ML, explained</b><small>Random Forest and XGBoost comparison</small></span></div>
          <div><Activity /><span><b>Preliminary retrospective model</b><small>Advance forecast skill is not validated</small></span></div>
          <div><Sparkles /><span><b>Action-led alerts</b><small>Risk translated into clear steps</small></span></div>
        </div>
      </section>

      <footer>
        <div className="page-wrap footer-inner">
          <a className="brand footer-brand" href="#top"><span className="brand-mark"><Sun size={18} /></span><span>Pyrograph <b>Jaipur</b></span></a>
          <p>Decision-support prototype for SIH26083 · Not an official public warning service.</p>
          <span>Built for heat resilience</span>
        </div>
      </footer>
    </main>
  );
}
