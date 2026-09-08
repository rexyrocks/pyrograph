'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowRight,
  Building2,
  ChevronRight,
  Clock3,
  Droplets,
  HeartPulse,
  Info,
  MapPin,
  Menu,
  ShieldCheck,
  Sparkles,
  Sun,
  ThermometerSun,
  TriangleAlert,
  Users,
  Wind,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

type Risk = 'Moderate' | 'High' | 'Severe';

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

const wards = [
  { id: 'amer', name: 'Amer', risk: 'High' as Risk, people: '42K', path: '75,24 150,12 192,52 176,112 99,105 58,70' },
  { id: 'vkn', name: 'Vidhyadhar Nagar', risk: 'Severe' as Risk, people: '68K', path: '99,105 176,112 205,164 166,205 86,188 63,139' },
  { id: 'city', name: 'Walled City', risk: 'Severe' as Risk, people: '91K', path: '166,205 205,164 276,171 296,224 248,267 179,260' },
  { id: 'malviya', name: 'Malviya Nagar', risk: 'High' as Risk, people: '74K', path: '248,267 296,224 351,249 359,318 305,354 245,327' },
  { id: 'sanganer', name: 'Sanganer', risk: 'Moderate' as Risk, people: '57K', path: '179,260 248,267 245,327 205,374 135,347 123,296' },
  { id: 'jhotwara', name: 'Jhotwara', risk: 'High' as Risk, people: '61K', path: '86,188 166,205 179,260 123,296 60,272 38,220' },
];

const riskClass: Record<Risk, string> = {
  Moderate: 'risk-moderate',
  High: 'risk-high',
  Severe: 'risk-severe',
};

const mapFill: Record<Risk, string> = {
  Moderate: '#f3b85c',
  High: '#ec6b3f',
  Severe: '#b72f2f',
};

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="metric">
      <span className="metric-icon">{icon}</span>
      <span>
        <small>{label}</small>
        <strong>{value}</strong>
      </span>
    </div>
  );
}

export default function Home() {
  const [selectedDay, setSelectedDay] = useState(0);
  const [selectedWard, setSelectedWard] = useState('city');
  const [outlook, setOutlook] = useState<OutlookItem[]>(fallbackOutlook);
  const [apiStatus, setApiStatus] = useState<'loading' | 'live' | 'fallback'>('loading');
  const [updatedAt, setUpdatedAt] = useState('Loading live outlook…');
  const selected = outlook[selectedDay];
  const ward = useMemo(
    () => wards.find((item) => item.id === selectedWard) ?? wards[2],
    [selectedWard],
  );

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
          <a href="#map">Ward map</a>
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

        <section id="map" className="map-section section-block">
          <div className="section-heading">
            <div><span className="kicker">Hyperlocal view</span><h2>Where risk is highest</h2></div>
            <div className="legend" aria-label="Risk legend">
              <span><i className="legend-dot moderate" />Moderate</span>
              <span><i className="legend-dot high" />High</span>
              <span><i className="legend-dot severe" />Severe</span>
            </div>
          </div>

          <div className="prototype-notice" role="note">
            <Info size={17} />
            <span><b>Illustrative ward data — not model-generated.</b> The live ML outlook currently applies to Jaipur city as a whole.</span>
          </div>

          <div className="map-grid">
            <div className="map-card">
              <div className="map-toolbar">
                <span><MapPin size={15} /> Select a ward for local guidance</span>
                <Badge variant="outline">{outlook[selectedDay].day} · {outlook[selectedDay].date}</Badge>
              </div>
              <svg className="jaipur-map" viewBox="0 0 400 410" aria-label="Illustrative Jaipur ward risk map">
                <title>Illustrative Jaipur ward risk map</title>
                <path className="river-line" d="M20 356 C102 312, 126 385, 215 350 S329 275, 392 302" />
                {wards.map((item) => (
                  <path
                    key={item.id}
                    d={`M${item.path} Z`}
                    fill={mapFill[item.risk]}
                    className={selectedWard === item.id ? 'ward selected-ward' : 'ward'}
                    onClick={() => setSelectedWard(item.id)}
                    tabIndex={0}
                    aria-label={`${item.name}, ${item.risk} risk`}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') setSelectedWard(item.id);
                    }}
                  />
                ))}
                <g className="map-labels" pointerEvents="none">
                  <text x="111" y="66">Amer</text>
                  <text x="101" y="151">Vidhyadhar</text>
                  <text x="207" y="220">Walled City</text>
                  <text x="282" y="304">Malviya</text>
                  <text x="160" y="327">Sanganer</text>
                  <text x="66" y="239">Jhotwara</text>
                </g>
              </svg>
              <span className="map-caption">Illustrative ward geometry for prototype interface</span>
            </div>

            <aside className="ward-panel">
              <div className="ward-panel-top">
                <span className="kicker">Selected ward</span>
                <span className={`risk-pill ${riskClass[ward.risk]}`}>{ward.risk}</span>
              </div>
              <h3>{ward.name}</h3>
              <p>Dense built-up areas and limited afternoon shade increase exposure here.</p>
              <div className="ward-number"><Users /><span><small>Estimated people exposed</small><b>{ward.people}</b></span></div>
              <div className="ward-metrics">
                <Metric icon={<ThermometerSun />} label="Feels like" value="47°C" />
                <Metric icon={<Droplets />} label="Humidity" value="28%" />
                <Metric icon={<Wind />} label="Max wind" value="18 km/h" />
              </div>
              <Button variant="outline" className="ward-cta">View ward response plan <ChevronRight /></Button>
            </aside>
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
