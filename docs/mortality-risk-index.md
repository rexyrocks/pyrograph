# Heat-health planning index

## Status

Version **prototype-impact-index-v1** is an uncalibrated planning index. It is
not a mortality probability, a clinical score, or a forecast of expected deaths.

The project currently has annual state-level historical mortality evidence.
That evidence is useful for context and later calibration design, but it cannot
validate a daily city-, zone-, or ward-level mortality model.

## Input contract

The heat-hazard component uses:

- Heatwave model probability, from 0 to 1
- Severe-threshold flag
- Two-consecutive-day persistence flag

The vulnerability component uses aggregate shares, each from 0 to 1:

- Older adults
- Children under five
- Outdoor workers
- People living in informal housing
- Social deprivation index

Inputs must represent the same geography. The service rejects values outside the
0–1 range.

## Version 1 formula

Heat hazard equals the heatwave probability multiplied by 82, plus 10 when
severe and 8 when persistence is met, capped at 100.

Each vulnerability share is divided by a documented high-reference value,
capped at 1, and multiplied by its weight:

| Factor | Weight | High-reference value |
| --- | ---: | ---: |
| Older adults | 25% | 25% |
| Children under five | 15% | 15% |
| Outdoor workers | 20% | 50% |
| Informal housing | 25% | 40% |
| Social deprivation | 15% | 100/100 |

The final index is 70% heat hazard plus 30% vulnerability.

Bands:

- Low: below 30
- Moderate: 30 to below 50
- High: 50 to below 70
- Severe: 70 or above

These weights and cut-offs are transparent product assumptions for the
hackathon prototype. They must be reviewed and recalibrated before operational
use.

## API

**POST /risk/assess** accepts a heatwave result plus an aggregate vulnerability
profile. It returns:

- The 0–100 planning index and band
- Heat-hazard and vulnerability component scores
- Top three vulnerability contributors
- Municipal action triggers
- Formula version and calibration status
- A null mortality probability

The production endpoint requires the existing X-API-Key.

## Evidence needed for calibration

A validated mortality model needs daily or weekly health outcomes at a
compatible geographic resolution, population denominators, exposure and
confounder data, reporting-delay corrections, and out-of-time/geography
validation. Until those conditions are met, the API deliberately returns no
mortality probability.
