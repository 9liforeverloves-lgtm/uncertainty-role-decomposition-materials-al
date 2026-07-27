# Conformal semantics correction

Status: **PASS**. `CONFORMAL_INTERVAL_ONLY` now stores a coverage-specific finite-sample residual-ratio order statistic and returns interval half-widths for 50%, 80%, 90%, and 95% coverage. It is not represented as one universal Gaussian standard deviation.

`CONFORMAL_GAUSSIAN_EQUIVALENT` is separate and stores exactly one named reference coverage: `sigma_equiv = q_alpha * sigma / z_(1-alpha/2)`. Production conformal diagnostics retain all four coverage-specific interval widths; conformal acquisition remains RAW/calibration-only by default.

Synthetic tests cover all registered coverages, unsupported coverage rejection, and the distinction among conformal half-width, Gaussian-equivalent sigma, and the former incorrect `q*sigma`-as-sigma interpretation.
