# Selected-CS decoupling reconciliation

## Exact cause

The prospective strategy registry defines `SELECTED_CS` as scaled acquisition plus
candidate-scaled Gaussian evaluation. The production adapter overrode its evaluation mapping
to `raw_gaussian_sigma`, making its L1 identical to `CS_ACQUISITION_ONLY`. Endpoint aliases did
not cause the identity.

## Resolution

- Production dispatch now uses `scaled_gaussian_sigma` for `SELECTED_CS`.
- All 640 checkpoint audit rows reuse accepted SELECTED_CS checkpoint models.
- Queried acquisition paths remain exact against acquisition-only:
  True.
- SELECTED_CS endpoint rows changed: 160/160.
- Independent trajectories rerun: 0.
- Scientific definition came from the frozen prospective registry, not observed outcomes.
