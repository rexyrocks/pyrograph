# Track 4 — Frontend, demo flow, and quality assurance

## Owner

Human teammate C

## Objective

Make the existing dashboard understandable and demo-ready, verify the complete
user journey, and report defects without creating unsupported data claims.

## Tasks

1. Review the public and operations journeys on desktop and mobile.
2. Check the five-day forecast selection and explanation panel.
3. Check the heat-health planning index and all scenario controls.
4. Verify that synthetic fixtures and missing data are visibly labelled.
5. Design the operations view for alerts and municipal acknowledgements.
6. Test loading, empty, offline, invalid-data, and upstream-failure states.
7. Check keyboard navigation, focus states, contrast, zoom, and touch targets.
8. Write the three-minute judging/demo script.
9. Create a concise defect list with reproduction steps and severity.

## File ownership

During the first review, do not edit product code. Put findings in:

- `docs/qa/frontend-review.md`
- `docs/qa/demo-script.md`
- `docs/qa/test-checklist.md`

Track 1 will apply shared frontend changes. After coordination, isolated visual
fixes may be assigned explicitly.

## Truthfulness checks

- Heatwave probability is not labelled mortality probability.
- The planning index is labelled uncalibrated.
- Synthetic ward fixtures are never presented as official ward data.
- Historical observations are not labelled live.
- A queued demo alert is not labelled delivered.
- The application states that it is not an official warning service.

## Acceptance checks

- Core tasks work at mobile and desktop widths.
- The first viewport communicates current risk and the next action.
- No text overlaps, clips, or becomes unreadable at 200% zoom.
- Every interactive control works with a keyboard.
- Failure states tell the user what remains available.
- The demo script includes an offline fallback.

## Handoff to Track 1

Provide:

- Prioritized defect list
- Screens or routes affected
- Expected versus actual behaviour
- Accessibility findings
- Final demo script
- Go/no-go recommendation
