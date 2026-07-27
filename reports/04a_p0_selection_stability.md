# P0 selection stability

Status: **DRAFT, descriptive development-only**. No confirmation selection map has been frozen.

## Matched-beta map

- Fixed matched beta: `0.942140151941`
- Stage values: 0-25% `0.934324059716`, 25-50% `0.93662888159`, 50-75% `0.940030751527`, 75-100% `0.950822075069`.
- Missing-stage fallback used: `[]`.
- Leave-one-development-seed-out fixed-beta range: `0.937643039003` to `0.946379183115`.

## Simple-scaling draft selection

The predeclared environment-balanced median L1 rule selected `IDENTITY_CONTROL`. Development summaries were `{'IDENTITY_CONTROL': 0.057559717698154184, 'SCALAR_TEMPERATURE_NLL': 0.1428864685124864, 'SCALAR_TEMPERATURE_RESIDUAL_RATIO': 0.05795331161780673}`. Leave-one-seed-out winner counts were `{'IDENTITY_CONTROL': 8, 'SCALAR_TEMPERATURE_RESIDUAL_RATIO': 2}`.

## Scope limits

The result is limited to the two declared expt-gap sentinel environments and ten development seeds. It is suitable only to form a DRAFT selection map. The 40-pair completeness gate, multiplicity-adjusted confirmation inference, confirmation manifest, and all P1 work remain deliberately unperformed.

DRAFT map: `analysis_plan/v6_selection_map_DRAFT.json` (hash `c1f5494819bca24f5a3405caa1fe6178f06e4fa19143b0b2599bf0c1c49354be`).
