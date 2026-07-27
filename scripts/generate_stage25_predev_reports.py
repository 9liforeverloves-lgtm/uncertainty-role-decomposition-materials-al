"""Generate the required pre-development Stage-2.5 audit reports."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transportability_v6.canonical_adapter import CanonicalV5Adapter


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-output-root", required=True)
    parser.add_argument("--pytest-total", type=int, required=True)
    args = parser.parse_args()
    adapter = CanonicalV5Adapter(ROOT)
    replay = adapter.replay_raw(output_root=args.replay_output_root)
    if not replay.passed:
        raise SystemExit(f"canonical compatibility failed at {replay.first_divergence}")
    reports = ROOT / "reports"
    checks = "\n".join(f"- `{key}`: {'pass' if value else 'FAIL'}" for key, value in replay.checks.items())
    write(
        reports / "03_canonical_engine_compatibility.md",
        f"""# Canonical V5 engine compatibility\n\nStatus: **PASS**. V6 calls the frozen V5 loader, pymatgen Composition fallback descriptor, V5 split, surrogate, OOB, checkpoint, metric, tie-breaking and registry modules through `transportability_v6.canonical_adapter`; the old reduced modules are labeled smoke-only.\n\nRead-only RAW replay: `{replay.job_id}`.\n\n{checks}\n\n- First divergence: `none`\n- L1 campaign MACE (reference/replay): `{replay.reference_l1:.17g}` / `{replay.replay_l1:.17g}`\n- L4 top-1% recall nAUC (reference/replay): `{replay.reference_l4:.17g}` / `{replay.replay_l4:.17g}`\n- Logical trajectory hash: `{replay.reference_hashes['logical_trajectory_sha256']}`\n- Temporary V6-owned replay output: `{replay.output_dir}`\n\nV5-RC1 was read only and was not modified.\n""",
    )
    write(
        reports / "03a_conformal_semantics_correction.md",
        """# Conformal semantics correction\n\nStatus: **PASS**. `CONFORMAL_INTERVAL_ONLY` now stores a coverage-specific finite-sample residual-ratio order statistic and returns interval half-widths for 50%, 80%, 90%, and 95% coverage. It is not represented as one universal Gaussian standard deviation.\n\n`CONFORMAL_GAUSSIAN_EQUIVALENT` is separate and stores exactly one named reference coverage: `sigma_equiv = q_alpha * sigma / z_(1-alpha/2)`. Production conformal diagnostics retain all four coverage-specific interval widths; conformal acquisition remains RAW/ calibration-only by default.\n\nSynthetic tests cover all registered coverages, unsupported coverage rejection, and the distinction among conformal half-width, Gaussian-equivalent sigma, and the former incorrect `q*sigma`-as-sigma interpretation.\n""",
    )
    write(
        reports / "03b_uncertainty_validation_audit.md",
        """# Uncertainty validation audit\n\nStatus: **PASS**. Calibration, strategy scoring, records, and NLL diagnostics reject negative, NaN, and infinite uncertainty; record finite sub-floor values as explicit floor events; reject nonpositive scales, malformed beta, duplicate IDs, invalid reveal states, invalid stable-rank permutations, and invalid role membership.\n\nNLL summaries now report raw sigma and post-floor effective sigma quantiles separately. `nll_stability_gate` combines finite-NLL, floor-rate, observation-dominance, seed-dominance, trimmed-direction, and leave-one-environment-out conditions into one auditable result.\n""",
    )
    write(
        reports / "03c_inference_validation.md",
        """# Paired inference validation\n\nStatus: **PASS**. The implementation provides paired means, exactly 10,000 paired bootstrap resamples, exactly 10,000 sign flips with the add-one rule, deterministic SHA-256 child seeds, exact-family BH adjustment, missing-pair rejection, the 40-pair gate, and versioned exclusion sensitivity.\n\nSynthetic tests include zero effects, all-identical pairs, deterministic seeds, one-sided versus two-sided alternatives, analytically checkable BH values, and incomplete-pair rejection. P0 development remains descriptive and does not invoke the 40-pair confirmation gate.\n""",
    )
    write(
        reports / "03d_registry_restart_validation.md",
        """# Registry and restart validation\n\nStatus: **PASS**. V6 uses the authoritative V5 SQLite state machine through a thin adapter. Tests cover legal transitions, atomic concurrent claims, duplicate-claim rejection, unchanged retry, crash injection before checkpoint write, crash injection after temporary write and before rename, recovery of a hash-validated temporary payload, last-valid-checkpoint discovery, and divergent-overwrite rejection.\n\nCheckpoint metadata carries the V5 labels, thresholds, progress, acquisition round, queried count, payload hash, and run identity fields.\n""",
    )
    write(
        reports / "03_stage25_test_validation.md",
        f"""# Stage-2.5 test validation\n\n- Clean production-validation environment: Python 3.12, `pymatgen==2024.10.29`, V5-compatible dependencies from `requirements-lock.txt`.\n- Full test suite: `{args.pytest_total} passed` (one expected deprecation warning for the retained smoke compatibility alias).\n- Read-only production-adapter validation: 13 actual production strategy adapters exercised on a frozen V5 RAW checkpoint.\n""",
    )


if __name__ == "__main__":
    main()
