# Current Jaipur geography and health-outcome gates — 2 October 2026

The requested evidence route is **public sources only**. This check distinguishes accessible background material from data that can actually validate current ward-level or mortality claims.

## Ward geometry

The Rajasthan [Local Self Government Department's 19 February 2025 order](https://lsg.urban.rajasthan.gov.in/content/dam/raj/udh/lsgs/lsg-jaipur/Order/Order2025/OrderFeb2025-/order%20ward%20%282%29.pdf) proposed **150 wards** for the reorganised Jaipur municipal corporation, based on the 2011 population. The [municipal city profile](https://jaipurmc.org/Presentation/AboutMcjaipur/CityProfile.aspx) now states 150 wards. The [Rajdharaa Urban GIS user manual](https://rajdharaa.rajasthan.gov.in/citizenudh/PDF/User_Manual_Urban_GIS_Portal.pdf) lists a Ward Boundary layer, but the public portal describes the map as for viewing and the research found no clearly reusable current vector export with a dated identifier contract. A PDF map or portal screenshot is not a substitute for geometry suited to spatial joins.

An accessible alternative is [DataMeet's Jaipur ward GeoJSON](https://github.com/datameet/Municipal_Spatial_Data/blob/master/Jaipur/Jaipur_Wards.geojson). Its [repository README](https://github.com/datameet/Municipal_Spatial_Data) grants CC BY 4.0 unless otherwise noted. The downloaded file is valid GeoJSON with **77 polygons**, `WARD_NO` and `ZONE_NAME` fields, 354,043 bytes, and SHA-256 `5ab1f312855c9d1b5e9d930529a0b8b249ebd95858abac4475ad2e457bd17e39`. It therefore **does not match** the current 150-ward structure; the file itself provides no reliable date/vintage metadata. It is suitable only as clearly labelled historical or illustrative background, not for current ward risk or joining present demographic records. The raw inspection copy is in ignored `work/Jaipur_Wards_datameet.geojson`.

**GIS gate:** obtain a reusable current 150-ward vector layer with authoritative boundary date, stable identifiers, projection, licence and completeness; then validate each geometry, match identifiers to population inputs, and visually compare against the official map. Until then the application remains city-level and does not render a ward-risk choropleth.

## Health outcomes

The [NCDC surveillance guidance](https://ncdc.mohfw.gov.in/uploads/pdf/heat12.pdf) defines daily and district-wise reporting of suspected heatstroke cases and all-cause deaths. It is a reporting format, not a downloadable Jaipur daily or ward outcome time series. The [Rajasthan health department's analysis guidance](https://rajswasthya.rajasthan.gov.in/admin/upload/letter/2021/85%20Dt.07.04.2021%20Website.pdf) likewise describes analysis rather than releasing the underlying observations. The public source search found no suitable aggregate daily Jaipur outcome extract with coverage, case definition and release terms. Annual state sunstroke totals are too coarse to train or validate a daily city or ward mortality model.

**Health-model gate:** obtain a lawful, suitably aggregated outcome series with dates, geography, denominator, reporting coverage, case definition and use terms. Keep `mortality_probability: null` and describe the existing score as an uncalibrated planning index until validation is possible. Do not infer death probabilities from weather-hazard labels or synthetic ward fixtures.
