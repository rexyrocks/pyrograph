# Track 3 — Data, GIS, and evidence

## Owner

Human teammate B with Gemini assistance

## Objective

Supply traceable, legally reusable, machine-readable health, demographic, and
geographic data while preserving its real temporal and spatial resolution.

## Already complete

- Initial data-source inventory
- Vulnerability feature specification
- Demographic data dictionary
- Five-row synthetic ward fixture

These artifacts are research inputs. Their source and licence claims still
require independent verification.

## Tasks

1. Verify every source URL, publisher, licence, and access method.
2. Download or extract aggregate mortality records with reproducible source
   notes.
3. Locate usable ward, zone, or district population tables.
4. Find legally reusable administrative boundary geometry.
5. Validate identifiers, duplicates, missing values, ranges, and geography.
6. Keep state, district, zone, and ward data at their true resolutions.
7. Produce cleaned CSV or GeoJSON files and matching data dictionaries.
8. Document the fallback hierarchy when local data is unavailable.
9. Record why rejected sources cannot be used.

## Owned files

- `data/sources/`
- `data/processed/`
- `docs/data/`

Do not edit backend, frontend, deployment, or model code. Track 1 will consume
approved outputs through validated contracts.

## Evidence constraints

- Never invent missing measurements.
- Never repeat state or district totals across wards.
- Do not reconstruct boundaries from screenshots.
- Do not bypass access controls.
- Do not add individual medical records or personal data.
- Mark synthetic fixtures clearly.
- Record the exact source date and geography for every processed row.

## Acceptance checks

- Every processed dataset has a data dictionary.
- Every source has a direct citation and reuse status.
- CSV and JSON/GeoJSON files parse successfully.
- Missing values remain explicit.
- Geographic identifiers are unique at their declared level.
- A limitations note explains staleness and resolution mismatches.

## Handoff to Track 1

Provide:

- Accepted and rejected sources
- Files ready for application use
- Schema and identifier contracts
- Data-quality results
- Coverage gaps
- Decisions and rejected alternatives
