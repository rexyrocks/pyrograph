# Major decision log

This filename intentionally preserves the name requested for the project.

## D-001 — Separate product engineering from evidence preparation

**Decision:** GPT-5.6 Sol owns application code and integration. Gemini 3.1 Pro
owns source discovery, data preparation, and evidence documentation.

**Why:** The tracks can progress concurrently with little file overlap, and one
owner remains accountable for application-wide consistency.

**Alternatives not chosen:** Splitting work by frontend/backend would force both
agents to repeatedly coordinate changing data contracts. Allowing both agents to
edit any file would increase merge conflicts and make provenance unclear.

## D-002 — Use GPT-6 Astra as a checkpoint reviewer

**Decision:** Use Astra for modelling, safety, scaling, and final-deliverable
reviews instead of routine implementation.

**Why:** These reviews benefit from deeper cross-system reasoning, while the
routine build can be completed efficiently by Sol and Gemini.

**Alternatives not chosen:** Using Astra for every task adds cost without a clear
benefit. Omitting an independent review leaves high-impact health claims and
alert failure modes insufficiently challenged.

## D-003 — Build one configurable product, not separate city implementations

**Decision:** Keep the Jaipur demo as the first configured location while making
location, thresholds, data availability, and model versions configurable.

**Why:** This demonstrates a credible path to Rajasthan-wide deployment without
pretending that Jaipur inputs are valid for every district.

**Alternatives not chosen:** Copying the application per city creates drift.
Immediately claiming a statewide model would exceed the available evidence.

## D-004 — Preserve an offline alert demonstration path

**Decision:** Implement a deterministic demo provider that queues alerts locally
and produces delivery receipts, with real SMS/WhatsApp providers optional.

**Why:** The hackathon demonstration remains reliable without paid credentials
or network access, while the provider interface proves that real delivery can be
connected later.

**Alternatives not chosen:** Browser notifications alone do not demonstrate the
SMS/WhatsApp API deliverable. Unofficial messaging automation is fragile and can
violate platform rules. Paid delivery as a hard requirement makes the demo
dependent on credentials, balance, and connectivity.

## D-005 — Do not reconstruct ward boundaries from screenshots

**Decision:** Use traceable, reusable official/open geometry when available;
otherwise fall back to a coarser geography or a clearly labelled illustrative
demo.

**Why:** Screenshot-derived lines are inaccurate and could imply official ward
precision that the system does not possess.

**Alternatives not chosen:** Manual tracing and image overlays failed visual and
geospatial quality checks and cannot support defensible risk calculations.

## D-006 — Ship an uncalibrated planning index before mortality probability

**Decision:** Implement a versioned 0–100 planning index that combines heat
hazard and aggregate demographic vulnerability. Always return
`mortality_probability: null` until suitable outcomes support calibration.

**Why:** The application needs an inspectable impact layer now, but the available
annual state mortality evidence cannot validate daily local mortality risk. A
transparent index lets the team demonstrate integration and action triggers
without making a false statistical claim.

**Alternatives not chosen:** Calling heatwave probability “mortality risk” would
mislabel the model target. Training on repeated annual state totals would create
geographic and temporal leakage. Omitting the impact layer entirely would leave
the vulnerability and municipal-action deliverables disconnected.

## D-007 — Remove the illustrative ward map from the main dashboard

**Decision:** Replace the hand-drawn ward surface with an interactive,
city-level aggregate vulnerability scenario.

**Why:** The screenshot-derived geometry did not meet accuracy or presentation
standards. The scenario makes uncertainty and input assumptions visible while
official boundaries remain unavailable.

**Alternatives not chosen:** Keeping the illustrative ward shapes—even with a
disclaimer—still suggests spatial precision. Hiding the disclaimer or treating
the shapes as operational data was rejected as misleading.

## D-008 — Integrate Gemini's demographic handoff as synthetic data only

**Decision:** Validate and expose the five synthetic ward rows through the API,
preserve blank occupational and housing values as null, and let the dashboard
load complete rows as explicitly synthetic scenarios. Incomplete rows remain
visible in the selector but cannot be scored.

**Why:** This exercises the demographic contract end to end without overstating
the evidence. Missingness is part of the dataset and must remain visible.

**Alternatives not chosen:** Treating the fixture as real Jaipur ward data would
be false. Zero-filling blanks would bias vulnerability downward. Automatically
mapping district source descriptions to wards would create unsupported spatial
precision.

## D-009 — Split remaining work into four human-owned tracks

**Decision:** Assign core integration, alerts and municipal operations, data and
GIS evidence, and frontend/demo QA as four separate tracks with explicit file
ownership and handoff requirements.

**Why:** The team can work concurrently while protecting shared API contracts
and avoiding overlapping edits.

**Alternatives not chosen:** Splitting only by frontend and backend would mix
research, safety, and integration responsibilities. Allowing everyone to edit
shared entrypoints would create merge conflicts and unclear accountability.
