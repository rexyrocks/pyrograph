# Data Source Inventory

> Research handoff: source URLs, licence statements, and availability claims
> require independent verification before operational use. The application
> currently consumes only the synthetic fixture, not records downloaded from
> these sources.

## 1. Heat-Related Mortality
- **Dataset Name:** Accidental Deaths and Suicides in India (ADSI)
- **Publisher:** National Crime Records Bureau (NCRB)
- **Direct URL:** https://ncrb.gov.in/en/adsi
- **Geographic Resolution:** State-level
- **Time Period:** Annual (2018–2022 used)
- **Update Frequency:** Annual
- **Access Method:** Public PDF/Excel download
- **Licence or Reuse Status:** Government Open Data License (GODL)
- **Relevant Columns:** Year, State/UT, Cause (Heat/Sunstroke), Total Deaths
- **Missingness and Known Bias:** Captures only accidental/medico-legal sunstroke deaths. Systematically undercounts all-cause excess heat mortality. Lacks daily and district-level resolution.
- **Use Case:** Calibration and contextualisation only. Cannot support training daily models.

## 2. Heat-Related Hospitalisation
- **Dataset Name:** Integrated Disease Surveillance Programme (IDSP)
- **Publisher:** National Centre for Disease Control (NCDC), MoHFW
- **Direct URL:** https://idsp.nic.in/
- **Geographic Resolution:** District-level (potentially ward-level for specific hospitals)
- **Time Period:** Ongoing
- **Update Frequency:** Weekly/Daily reporting
- **Access Method:** Restricted portal access (requires authorization)
- **Licence or Reuse Status:** Restricted; requires specific data sharing agreement
- **Relevant Columns:** Date, District, Facility, Syndromic surveillance (fever/heat exhaustion)
- **Missingness and Known Bias:** Reporting quality varies by district and facility participation. Often delayed.
- **Use Case:** Future validation and training (if daily extracts become available). Currently unavailable.

## 3. Population and Demographics
- **Dataset Name:** Jaipur Ward Population Registry (from unified delimitation)
- **Publisher:** Government of Rajasthan (Local Self Government Department)
- **Direct URL:** Rajasthan e-Gazette portal (notification dated Sept 20, 2025)
- **Geographic Resolution:** Ward-level (150 wards)
- **Time Period:** 2025
- **Update Frequency:** Ad hoc (upon redelimitation)
- **Access Method:** Public PDF gazette notification
- **Licence or Reuse Status:** Public domain/government document
- **Relevant Columns:** Ward Number, Total Population, SC/ST Population
- **Missingness and Known Bias:** Lacks detailed age or occupational breakdowns. Total counts only.
- **Use Case:** Calibration, contextualisation, mapping exposure.

## 4. Elderly Population, Children, and Vulnerable Age Groups
- **Dataset Name:** Primary Census Abstract Data Tables (India)
- **Publisher:** Office of the Registrar General & Census Commissioner, India
- **Direct URL:** https://censusindia.gov.in/
- **Geographic Resolution:** District/City/Ward (2011 boundaries)
- **Time Period:** 2011 (projections required for 2024+)
- **Update Frequency:** Decadal
- **Access Method:** Public CSV/Excel
- **Licence or Reuse Status:** GODL
- **Relevant Columns:** Age Group, Total Persons, Males, Females
- **Missingness and Known Bias:** 2011 data is highly stale. 2011 ward boundaries do not match 2025 ward boundaries.
- **Use Case:** Contextualisation. Requires projection or synthesis to map to 2025 wards.

## 5. Informal Housing or Socioeconomic Vulnerability
- **Dataset Name:** National Family Health Survey (NFHS-5)
- **Publisher:** Ministry of Health and Family Welfare (MoHFW) / IIPS
- **Direct URL:** http://rchiips.org/nfhs/
- **Geographic Resolution:** District-level
- **Time Period:** 2019-2021
- **Update Frequency:** Every 4-5 years
- **Access Method:** Public reports and microdata (upon request)
- **Licence or Reuse Status:** Open access for research with registration
- **Relevant Columns:** Wealth Index, Housing Material (Roof/Wall), Water Access
- **Missingness and Known Bias:** Survey-based sampling. Cannot be deterministically downscaled to individual wards.
- **Use Case:** Contextualisation only. Cannot be used to score individual wards without spatial modeling.

## 6. Administrative Boundaries
- **Dataset Name:** Rajdharaa GIS Portal
- **Publisher:** Department of Information Technology & Communication, Rajasthan
- **Direct URL:** https://rajdharaa.rajasthan.gov.in/
- **Geographic Resolution:** Ward, Zone, District
- **Time Period:** 2025 (current view)
- **Update Frequency:** Continuous/As needed
- **Access Method:** View-only map (export restricted/requires token)
- **Licence or Reuse Status:** Proprietary/Government restricted
- **Relevant Columns:** Geometry (Polygon), Ward ID, Name
- **Missingness and Known Bias:** Official source but currently lacks public export path.
- **Use Case:** Demonstration. Official vector data required for production.

## 7. Historical Heat Exposure
- **Dataset Name:** Open-Meteo Historical Archive
- **Publisher:** Open-Meteo (aggregating ERA5/DWD/NOAA)
- **Direct URL:** https://open-meteo.com/en/docs/historical-weather-api
- **Geographic Resolution:** 0.1 degree gridded (approx 10km)
- **Time Period:** 1940 to present (2015-2024 used)
- **Update Frequency:** Daily
- **Access Method:** Open API
- **Licence or Reuse Status:** Non-commercial open use (CC-BY 4.0)
- **Relevant Columns:** date, tmax, tmin, rh_mean, wind_speed_max, surface_pressure_mean
- **Missingness and Known Bias:** Gridded reanalysis data; might smooth out extreme urban heat island micro-peaks.
- **Use Case:** Training, historical calibration.
