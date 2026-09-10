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
  Users,
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
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import demographicsCsv from '../../data/processed/fixtures_synthetic_wards.csv?raw';

type Risk = 'Moderate' | 'High' | 'Severe';
type ImpactBand = 'Low' | Risk;

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

const riskClass: Record<Risk, string> = {
  Moderate: 'risk-moderate',
  High: 'risk-high',
  Severe: 'risk-severe',
};

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

const vulnerabilityFactors = [
  { key: 'olderAdults' as const, label: 'Older adults', weight: 0.25, referenceHigh: 25 },
  { key: 'youngChildren' as const, label: 'Children under five', weight: 0.15, referenceHigh: 15 },
  { key: 'outdoorWorkers' as const, label: 'Outdoor workers', weight: 0.20, referenceHigh: 50 },
  { key: 'informalHousing' as const, label: 'Informal housing', weight: 0.25, referenceHigh: 40 },
  { key: 'deprivation' as const, label: 'Social deprivation', weight: 0.15, referenceHigh: 100 },
];

function calculateImpact(
  probability: number,
  severe: boolean,
  persistenceMet: boolean | null,
  profile: VulnerabilityProfile,
) {
  const hazard = Math.min(100, probability * 0.82 + (severe ? 10 : 0) + (persistenceMet === true ? 8 : 0));
  const contributions = vulnerabilityFactors.map((factor) => ({
    label: factor.label,
    value: profile[factor.key],
    contribution: Math.min(profile[factor.key] / factor.referenceHigh, 1) * factor.weight * 100,
  }));
  const vulnerability = contributions.reduce((sum, factor) => sum + factor.contribution, 0);
  const index = Math.min(100, hazard * 0.7 + vulnerability * 0.3);
  const band: ImpactBand = index < 30 ? 'Low' : index < 50 ? 'Moderate' : index < 70 ? 'High' : 'Severe';
  return {
    index: Math.round(index * 10) / 10,
    hazard: Math.round(hazard * 10) / 10,
    vulnerability: Math.round(vulnerability * 10) / 10,
    band,
    drivers: contributions.sort((a, b) => b.contribution - a.contribution).slice(0, 3),
  };
}

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
  const [outlook, setOutlook] = useState<OutlookItem[]>(fallbackOutlook);
  const [apiStatus, setApiStatus] = useState<'loading' | 'live' | 'fallback'>('loading');
  const [updatedAt, setUpdatedAt] = useState('Loading live outlook…');
  const selected = outlook[selectedDay];
  const demoWard = useMemo(
    () => demoWards.find((ward) => ward.wardId === selectedDemoWard) ?? null,
    [selectedDemoWard],
  );
  const impact = useMemo(
    () => calculateImpact(
      selected.probability,
      selected.risk === 'Severe',
      selected.persistenceMet,
      vulnerabilityProfile,
    ),
    [selected, vulnerabilityProfile],
  );

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
    }));
  };

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/outlook', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Live outlook unavailable');
        return response.json() as Promise<LiveOutlookResponse>;
      })
      .then((payload) => {
        if (!Array.isArray(payload.outlook) || payload.outlook.length !== 5) {
          throw new Error('Invalid outlook response');
        }
        const liveOutlook: OutlookItem[] = payload.outlook.map((item, index) => {
          const isoDate = item.date;
          const parsedDate = new Date(`${isoDate}T00:00:00Z`);
          const severe = item.severe;
          const heatwave = item.heatwave_prediction === 1;
          return {
            day: index === 0 ? 'Today' : parsedDate.toLocaleDateString('en-IN', { weekday: 'short', timeZone: 'UTC' }),
            date: parsedDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', timeZone: 'UTC' }),
            temperature: item.tmax,
            probability: Math.round(item.heatwave_probability * 100),
            risk: severe ? 'Severe' : heatwave ? 'High' : 'Moderate',
            note: item.lag_source === 'historical' ? 'Observed lag inputs' : 'Forecast-derived lags',
            normal: item.climatology_normal,
            p95: item.climatology_p95,
            p98: item.climatology_p98,
            persistenceMet: item.persistence_met,
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
      .catch((error) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setApiStatus('fallback');
          setUpdatedAt('Live service unavailable');
        }
      });
    return () => controller.abort();
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
            {apiStatus === 'live' ? 'Live model data' : apiStatus === 'loading' ? 'Loading model…' : 'Prototype fallback'}
          </Badge>
          <Button variant="ghost" size="icon" className="mobile-menu" aria-label="Open navigation">
            <Menu />
          </Button>
        </div>
      </header>

      <section id="top" className="hero-shell">
        <div className="eyebrow-row">
          <span className="eyebrow"><MapPin size={14} /> Jaipur, Rajasthan</span>
          <span className="update-time"><Clock3 size={14} /> Updated {updatedAt}</span>
        </div>

        <div className="hero-grid">
          <div className="hero-copy">
            <Badge className="warning-badge"><TriangleAlert size={14} /> {selected.risk} risk outlook</Badge>
            <h1>Heat risk is {selected.risk.toLowerCase()}<br />across Jaipur.</h1>
            <p>
              {selected.risk === 'Moderate'
                ? 'Forecast temperatures remain below Jaipur’s heatwave threshold. Keep hydrated and continue monitoring updates.'
                : 'Dangerous afternoon conditions are likely, with the highest exposure in dense central wards. Reduce outdoor activity between 12–4 PM.'}
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
                  <Info /> Why this alert?
                </SheetTrigger>
                <SheetContent className="reason-sheet">
                  <SheetHeader>
                    <Badge className="sheet-badge">Transparent alert logic</Badge>
                    <SheetTitle>Why Jaipur is at {selected.risk.toLowerCase()} risk</SheetTitle>
                    <SheetDescription>
                      The warning combines the model probability with Jaipur&apos;s calendar-day climate thresholds.
                    </SheetDescription>
                  </SheetHeader>
                  <div className="reason-body">
                    <div className="threshold-card current"><span>Forecast Tmax</span><b>{selected.temperature.toFixed(1)}°C</b></div>
                    <div className="threshold-flow"><span /> compared with <span /></div>
                    <div className="threshold-card"><span>LOYO P95 threshold</span><b>{selected.p95.toFixed(1)}°C</b></div>
                    <ul className="reason-list">
                      <li><span>Model probability</span><b>{selected.probability}%</b></li>
                      <li><span>Departure from normal</span><b>{selected.temperature - selected.normal >= 0 ? '+' : ''}{(selected.temperature - selected.normal).toFixed(1)}°C</b></li>
                      <li><span>Persistence check</span><b>{selected.persistenceMet === true ? 'Met · day 2 of 2' : selected.persistenceMet === false ? 'Not met' : 'Pending prior day'}</b></li>
                      <li><span>P98 severe threshold</span><b>{selected.p98.toFixed(1)}°C</b></li>
                    </ul>
                    <p className="explain-note">
                      LOYO means the year being labelled is excluded when its climate threshold is calculated,
                      preventing the day from influencing its own label.
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
              <span className={`risk-pill ${riskClass[selected.risk]}`}>{selected.risk} risk</span>
              <span>{selected.probability}% heatwave probability</span>
            </div>
            <div className="confidence-track"><span style={{ width: `${selected.probability}%` }} /></div>
            <div className="mini-stats">
              <span><small>Normal</small><b>{selected.normal.toFixed(1)}°C</b></span>
              <span><small>Departure</small><b>{selected.temperature - selected.normal >= 0 ? '+' : ''}{(selected.temperature - selected.normal).toFixed(1)}°C</b></span>
              <span><small>Peak window</small><b>2–5 PM</b></span>
            </div>
          </div>
        </div>
      </section>

      <div className="page-wrap">
        <section id="overview" className="forecast-section section-block">
          <div className="section-heading">
            <div>
              <span className="kicker">Plan ahead</span>
              <h2>Five-day heat outlook</h2>
              <p className="weather-source">Temperature source: Open-Meteo Forecast API · Jaipur 26.91°N, 75.79°E</p>
            </div>
            <div className="view-switcher">
              <span>View for</span>
              <Tabs defaultValue="public">
                <TabsList>
                  <TabsTrigger value="public">Public</TabsTrigger>
                  <TabsTrigger value="operations">Operations</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
          <div className="forecast-scroll">
            <div className="forecast-grid">
              {outlook.map((item, index) => (
                <button
                  key={item.date}
                  className={`forecast-card ${selectedDay === index ? 'selected' : ''}`}
                  onClick={() => setSelectedDay(index)}
                  aria-pressed={selectedDay === index}
                >
                  <span className="forecast-day"><b>{item.day}</b><small>{item.date}</small></span>
                  <strong className="forecast-temp">{item.temperature.toFixed(1)}°</strong>
                  <span className={`forecast-risk ${riskClass[item.risk]}`}>{item.risk}</span>
                  <span className="forecast-prob"><i style={{ width: `${item.probability}%` }} />{item.probability}% probability</span>
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
            <article className="impact-score-card">
              <div className="impact-score-top">
                <span>Planning index</span>
                <Badge variant="outline">{outlook[selectedDay].day} · {outlook[selectedDay].date}</Badge>
              </div>
              <div className="impact-number">{impact.index}<small>/100</small></div>
              <span className={`impact-band impact-${impact.band.toLowerCase()}`}>{impact.band} planning priority</span>
              <div className="component-scores">
                <div>
                  <span><b>Heat hazard</b><strong>{impact.hazard}</strong></span>
                  <i><em style={{ width: `${impact.hazard}%` }} /></i>
                </div>
                <div>
                  <span><b>Vulnerability</b><strong>{impact.vulnerability}</strong></span>
                  <i><em style={{ width: `${impact.vulnerability}%` }} /></i>
                </div>
              </div>
              <p className="formula-note">70% heat hazard + 30% demographic vulnerability. Severe and two-day persistence checks modify the hazard component.</p>
            </article>

            <article className="scenario-card">
              <div className="scenario-heading">
                <div><span className="kicker">Scenario controls</span><h3>Test aggregate vulnerability</h3></div>
                <Button variant="ghost" size="sm" onClick={() => { setSelectedDemoWard(''); setVulnerabilityProfile(defaultVulnerability); }}>Reset</Button>
              </div>
              <p>Load a Gemini-prepared synthetic fixture or adjust the values. These are not official Jaipur demographic estimates.</p>
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

          <div className="impact-detail-grid">
            <article>
              <span className="kicker">What drives the score</span>
              <h3>Top vulnerability contributors</h3>
              <ol className="driver-list">
                {impact.drivers.map((driver) => (
                  <li key={driver.label}>
                    <span>{driver.label}<small>Scenario value {driver.value}%</small></span>
                    <b>+{driver.contribution.toFixed(1)}</b>
                  </li>
                ))}
              </ol>
            </article>
            <article>
              <span className="kicker">Municipal trigger</span>
              <h3>Actions for {impact.band.toLowerCase()} priority</h3>
              <ul className="trigger-list">
                <li><ShieldCheck /> Monitor the forecast and verify response contacts.</li>
                {impact.index >= 30 && <li><Droplets /> Confirm water points, cooling spaces, and outreach teams.</li>}
                {impact.index >= 50 && <li><Clock3 /> Shift outdoor municipal work away from afternoon peak heat.</li>}
                {impact.index >= 50 && <li><Users /> Issue guidance for vulnerable population groups.</li>}
                {impact.index >= 70 && <li><Building2 /> Activate health-facility readiness and incident review.</li>}
              </ul>
            </article>
          </div>
        </section>
      </div>

      <section id="guidance" className="guidance-section">
        <div className="page-wrap">
          <div className="section-heading light">
            <div><span className="kicker">Act before the peak</span><h2>What to do today</h2></div>
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
          <div><Activity /><span><b>Climate-aware thresholds</b><small>Leakage-safe LOYO labelling</small></span></div>
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
