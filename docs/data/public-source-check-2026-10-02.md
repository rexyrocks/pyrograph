# Public data feasibility check — 2 October 2026

The user has no additional ward, demographic or health datasets. Continue from public sources; do not replace missing evidence with synthetic data presented as real.

| Need | Evidence located | Current status |
|---|---|---|
| Archived issue-time weather | [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api) retrieves an individual initialized forecast run | Initial probe succeeded for one 2025-05-01 00 UTC IFS run. Subsequent full-May 2024 and 2025 9-km single-run replay scored all 31 runs per month at two target offsets; see `single-run-2024-2025-pilot.md`. Exact public release times remain unverified. |
| Lead-specific archive alternative | [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api) provides fixed forecast lead offsets | One week of IFS 0.25° archived hourly fields was complete at leads 3–5; an April–June 2025 proxy evaluation is documented in `fixed-lead-2025-pilot.md`. This product is not equivalent to an entire single initialization. |
| Ward definitions | [Jaipur municipal homepage](https://www.jaipurmc.org/) links a ward-delimitation gazette; [official ward-map PDF](https://jaipurmc.org/PDF/91wardmap.pdf) surfaced in search | Source discovered, but reusable georeferenced vectors and matching demographic joins have not been obtained |
| Local health outcomes | [NCDC training manual](https://www.ncdc.mohfw.gov.in/wp-content/uploads/2024/05/4-Training-Manual-for-State-And-District-Nodal-Officers-For-Implementation-of-Heat-Health-Action-Plan.pdf) describes daily surveillance reporting through IHIP | Documentation is not a downloaded, authorized local outcome dataset; mortality-model data gate remains open |

## Archive probe result and time-zone rule

The live experiment established that the archived endpoint returns a complete hourly feature set for this run. A daily request in Asia/Kolkata failed because this IFS run is not midnight in the requested local timezone. Hourly records are therefore grouped to 24-record local days and incomplete or null-field days are omitted. The daily maxima, means and radiation totals reconstructed from hourly values are approximations; they can differ from the daily historical products used to train the classifier. The first partial date (May 1) and final partial date (May 9) were excluded. This single run is not a forecast-skill result.

The provider describes the run parameter as UTC initialization and notes several hours of post-initialization processing before publication. Preserve that latency when constructing issue-time samples; the initialization timestamp alone does not prove the forecast was available to a user.

## Next checks

1. Freeze weather model, initialization and local-day boundaries before scoring. Include publication latency and lag availability in the replay design. Never use final reanalysis as if it were already available at forecast issue time.
2. Extend the 9-km single-run replay beyond two May months with independent verification and measured publication times. The May 2024 positives are too few for a final claim; May 2025 had none in the scored targets. Verify the live best-match feed separately.
3. Obtain ward vectors with boundary vintage and usage terms. Do not trace screenshots or present the old synthetic fixtures as actual Jaipur demographics.
4. Locate a public, suitably aggregated health extract or an explicit data-sharing route. Annual state totals do not establish daily ward mortality risk.

No provider signup, outreach, paid purchase or access to restricted health data was attempted.
