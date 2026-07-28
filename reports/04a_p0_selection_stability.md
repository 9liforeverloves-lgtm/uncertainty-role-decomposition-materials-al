# P0 selection stability

Status: **sentinel DRAFT, descriptive development-only**. No confirmation selection map has been frozen; this two-environment expt-gap result cannot define a full-universe policy.

## Matched-beta map

- Fixed matched beta: `0.942140151941`
- Stage values: 0-25% `0.934324059716`, 25-50% `0.93662888159`, 50-75% `0.940030751527`, 75-100% `0.950822075069`.
- Missing-stage fallback used: `[]`.
- Leave-one-development-seed-out fixed-beta range: `0.937643039003` to `0.946379183115`.

## Simple-scaling draft selection

The sentinel descriptive minimum was `IDENTITY_CONTROL`. Development summaries were `{'IDENTITY_CONTROL': 0.057559717698154184, 'SCALAR_TEMPERATURE_NLL': 0.1428864685124864, 'SCALAR_TEMPERATURE_RESIDUAL_RATIO': 0.05795331161780673}`. Leave-one-seed-out winner counts were `{'IDENTITY_CONTROL': 8, 'SCALAR_TEMPERATURE_RESIDUAL_RATIO': 2}`. Identity remains a negative implementation control, not a scaling winner; residual-ratio remains the candidate simple non-identity scalar baseline, and NLL remains the prespecified mechanistic scalar baseline. No post-hoc winner selection across all simple scalers is made from these sentinel outcomes.

## Scope limits

The result is limited to the two declared expt-gap sentinel environments and ten development seeds. It is suitable only to form the archived sentinel DRAFT, not a confirmation policy. The 40-pair completeness gate, multiplicity-adjusted confirmation inference, confirmation manifest, and all P1 work remain deliberately unperformed.

DRAFT map: `analysis_plan/v6_selection_map_SENTINEL_DRAFT.json` (byte-identical archive; hash `c1f5494819bca24f5a3405caa1fe6178f06e4fa19143b0b2599bf0c1c49354be`).
