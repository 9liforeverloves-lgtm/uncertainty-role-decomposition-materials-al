"""Read-only bridge to the frozen V5-RC1 scientific engine.

This module deliberately imports the V5 implementation from its frozen source
tree instead of copying it.  V6 production code therefore inherits the
canonical Matbench snapshot loader, :class:`pymatgen.core.Composition` parsing,
dataset-wide descriptor construction, split algorithms, ensemble/OOB handling,
checkpoint definitions, endpoint primitives, and SQLite job registry.

Nothing in this module writes into ``revision_v5``.  Replays always receive a
caller-owned output directory.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
from importlib import metadata as importlib_metadata
import json
from pathlib import Path
import sys
from typing import Any
import types

import numpy as np
import pandas as pd
import yaml


class CanonicalAdapterError(RuntimeError):
    """The frozen V5 engine cannot safely be used by a production V6 run."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _id_hash(values: np.ndarray | list[str]) -> str:
    return _stable_hash([str(value) for value in np.asarray(values).tolist()])


@dataclass(frozen=True)
class CanonicalPaths:
    """Absolute locations of the frozen V5 components used by the adapter."""

    workspace: Path
    v5_root: Path
    v5_source_root: Path
    v5_manifest: Path
    v5_protocol: Path
    v5_reference_trajectory: Path
    canonical_bundle: Path
    canonical_material_source: Path
    canonical_data_root: Path
    v5_lock_manifest: Path


@dataclass(frozen=True)
class CampaignGeometry:
    """Canonical V5 campaign geometry derived without target leakage."""

    initial_count: int
    batch_size: int
    max_queries: int
    uncertainty_floor: float
    min_oob_trees_per_sample: int
    floor_grid: tuple[float, ...]


@dataclass(frozen=True)
class RawReplayResult:
    """Structural comparison between a temporary RAW replay and frozen V5."""

    job_id: str
    passed: bool
    first_divergence: str | None
    checks: dict[str, bool]
    reference_hashes: dict[str, str]
    replay_hashes: dict[str, str]
    reference_l1: float
    replay_l1: float
    reference_l4: float
    replay_l4: float
    output_dir: str


@dataclass(frozen=True)
class HistoricalStrategyReplayResult:
    """Read-only exact replay result for a frozen non-RAW V5 strategy."""

    job_id: str
    v5_strategy: str
    passed: bool
    first_divergence: str | None
    checks: dict[str, bool]
    reference_hashes: dict[str, str]
    replay_hashes: dict[str, str]
    reference_l1: float
    replay_l1: float
    reference_l4: float
    replay_l4: float
    output_dir: str


def default_paths(workspace: str | Path | None = None) -> CanonicalPaths:
    root = Path(workspace) if workspace is not None else Path(__file__).resolve().parents[2]
    root = root.resolve()
    v5_root = root / "revision_v5"
    bundle = root / "最终" / "_code_package"
    reference = (
        v5_root
        / "results_v4"
        / "confirmation"
        / "trajectories"
        / "matbench_expt_gap__iid_record__random_forest__raw_ucb_beta_1__seed5000"
    )
    return CanonicalPaths(
        workspace=root,
        v5_root=v5_root,
        v5_source_root=v5_root / "experiments_v4" / "src",
        v5_manifest=v5_root / "manifests_v4" / "CONFIRMATION_JOB_MANIFEST_V5_RC1.csv",
        v5_protocol=v5_root / "20_confirmation_protocol_v5_rc1.md",
        v5_reference_trajectory=reference,
        canonical_bundle=bundle,
        canonical_material_source=bundle / "src",
        canonical_data_root=bundle / "results" / "benchmark",
        v5_lock_manifest=root / "locks" / "v5_frozen_manifest.json",
    )


class CanonicalV5Adapter:
    """Access authoritative V5 components after validating their source lock."""

    def __init__(self, workspace: str | Path | None = None) -> None:
        self.paths = default_paths(workspace)
        # Descriptor construction is deterministic, task-wide, and shared by
        # every seed/split/strategy in a worker.  Retain it only in-process:
        # the frozen CSV is still validated on the first load and every
        # ``v5_run_config`` call still reconstructs its own split/geometry.
        # This avoids repeatedly parsing the same large Matbench task without
        # changing any scientific input or random state.
        self._dataset_cache: dict[str, tuple[pd.DataFrame, np.ndarray]] = {}

    def _require_paths(self) -> None:
        required = (
            self.paths.v5_root,
            self.paths.v5_source_root,
            self.paths.v5_manifest,
            self.paths.v5_protocol,
            self.paths.canonical_material_source,
            self.paths.canonical_data_root,
            self.paths.v5_lock_manifest,
        )
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise CanonicalAdapterError(f"canonical V5 assets are unavailable: {missing}")

    def _import_v5(self) -> dict[str, Any]:
        """Import exactly the frozen V5 package and not a globally installed copy."""

        self._require_paths()
        text = str(self.paths.v5_source_root)
        if text not in sys.path:
            sys.path.insert(0, text)
        package = importlib.import_module("transportability_v5")
        package_path = Path(package.__file__).resolve()
        if self.paths.v5_source_root not in package_path.parents:
            raise CanonicalAdapterError(
                f"transportability_v5 resolved outside frozen source tree: {package_path}"
            )
        return {
            "data": importlib.import_module("transportability_v5.data"),
            "splits": importlib.import_module("transportability_v5.splits"),
            "surrogates": importlib.import_module("transportability_v5.surrogates"),
            "strategies": importlib.import_module("transportability_v5.strategies"),
            "metrics": importlib.import_module("transportability_v5.metrics"),
            "layers": importlib.import_module("transportability_v5.layers"),
            "checkpoint": importlib.import_module("transportability_v5.checkpoint"),
            "registry": importlib.import_module("transportability_v5.registry"),
            "runner": importlib.import_module("transportability_v5.runner"),
            "provenance": importlib.import_module("transportability_v5.provenance"),
        }

    @property
    def modules(self) -> dict[str, Any]:
        return self._import_v5()

    def validate_pymatgen(self) -> None:
        try:
            from pymatgen.core import Composition  # noqa: F401
            version = importlib_metadata.version("pymatgen")
        except Exception as exc:  # pragma: no cover - environment dependent
            raise CanonicalAdapterError(
                "V6 production requires pymatgen Composition parsing from the V5 environment"
            ) from exc
        if version != "2024.10.29":
            raise CanonicalAdapterError(
                f"V6 production requires pymatgen==2024.10.29, observed {version}"
            )

    def source_lock_status(self) -> dict[str, Any]:
        """Compare the frozen source tree against a V5 trajectory provenance lock."""

        reference_path = self.paths.v5_reference_trajectory / "source_code_hashes.json"
        if not reference_path.is_file():
            raise CanonicalAdapterError(f"V5 source lock missing: {reference_path}")
        recorded = json.loads(reference_path.read_text(encoding="utf-8"))
        expected = dict(recorded["files"])
        observed: dict[str, str] = {}
        for relative in expected:
            path = self.paths.v5_source_root.parent / relative
            if not path.is_file():
                observed[relative] = "MISSING"
            else:
                observed[relative] = _sha256_file(path)
        mismatches = {
            name: {"expected": expected[name], "observed": observed[name]}
            for name in expected
            if expected[name] != observed[name]
        }
        return {
            "expected_overall_sha256": recorded.get("overall_sha256"),
            "observed_overall_sha256": _stable_hash(observed),
            "source_hashes_match": not mismatches,
            "mismatches": mismatches,
        }

    def assert_source_lock(self) -> None:
        status = self.source_lock_status()
        if not status["source_hashes_match"]:
            raise CanonicalAdapterError(f"V5 source lock mismatch: {status['mismatches']}")

    def validate_v5_authority_locks(self) -> dict[str, Any]:
        """Validate compact V5 authority files; never walk the 90-GB trajectory tree."""

        manifest = json.loads(self.paths.v5_lock_manifest.read_text(encoding="utf-8"))
        checks: list[dict[str, Any]] = []
        for entry in manifest.get("files", []):
            expected = entry.get("expected_sha256") or entry.get("sha256")
            relative = Path(str(entry["path"]))
            path = self.paths.workspace / relative
            observed = _sha256_file(path) if path.is_file() else None
            checks.append(
                {
                    "path": relative.as_posix(),
                    "expected_sha256": expected,
                    "observed_sha256": observed,
                    "match": bool(observed and observed == expected),
                }
            )
        return {
            "schema_version": manifest.get("schema_version"),
            "checked_files": len(checks),
            "passed": all(item["match"] for item in checks),
            "checks": checks,
        }

    def load_task(self, task: str) -> pd.DataFrame:
        """Load the V5 frozen local Matbench snapshot for ``task``."""

        self.assert_source_lock()
        self.validate_pymatgen()
        path = self.paths.canonical_data_root / str(task) / "materials.csv"
        if not path.is_file():
            raise CanonicalAdapterError(f"V5 Matbench snapshot unavailable for {task!r}")
        frame = self.modules["data"].load_materials_csv(path)
        required = ["material_id", "formula", "target"]
        if list(frame.columns) != required:
            frame = frame.loc[:, required]
        if frame.material_id.astype(str).duplicated().any():
            raise CanonicalAdapterError("canonical V5 loader returned duplicate material IDs")
        if not np.isfinite(frame.target.to_numpy(float)).all():
            raise CanonicalAdapterError("canonical V5 loader returned a non-finite target")
        return frame.reset_index(drop=True)

    def featurize_dataset_wide(self, formulas: np.ndarray | pd.Series | list[str]) -> np.ndarray:
        """Reuse the V5 descriptor vocabulary over the complete supplied dataset."""

        self.assert_source_lock()
        self.validate_pymatgen()
        values = np.asarray(formulas, dtype=str)
        if values.ndim != 1 or not len(values):
            raise ValueError("formulas must be a non-empty one-dimensional vector")
        # The V5-RC1 trajectory lock proves that the authoritative path was
        # the V5 ``data.featurize_formulas`` pymatgen fallback: its sorted
        # dataset-wide element vocabulary gives 83 columns for expt-gap.  Do
        # not let an unrelated installed ``material_al`` package silently
        # select the later eight-summary-descriptor branch.
        preserved = {
            name: module
            for name, module in list(sys.modules.items())
            if name == "material_al" or name.startswith("material_al.")
        }
        for name in preserved:
            sys.modules.pop(name, None)
        blocker = types.ModuleType("material_al")
        sys.modules["material_al"] = blocker
        try:
            matrix = np.asarray(self.modules["data"].featurize_formulas(values), dtype=float)
        finally:
            sys.modules.pop("material_al", None)
            sys.modules.update(preserved)
        if matrix.shape[0] != len(values) or matrix.ndim != 2:
            raise CanonicalAdapterError("canonical V5 featurizer returned an invalid matrix")
        if not np.isfinite(matrix).all():
            raise CanonicalAdapterError("canonical V5 descriptor matrix contains non-finite values")
        return matrix

    def split(self, formulas: np.ndarray, ids: np.ndarray, protocol: str, seed: int):
        """Return the exact V5 IID or chemical-system group-disjoint split."""

        self.assert_source_lock()
        self.validate_pymatgen()
        result = self.modules["splits"].make_split(str(protocol)).split(
            np.asarray(formulas, dtype=str),
            np.asarray(ids, dtype=str),
            int(seed),
            min_source=30,
            min_target=50,
            min_diagnostic=20,
        )
        result.validate(len(ids), 30, 50, 20)
        return result

    def protocol(self) -> dict[str, Any]:
        path = self.paths.canonical_bundle / "transportability_study" / "configs" / "protocol_v1.yaml"
        if not path.is_file():
            raise CanonicalAdapterError(f"canonical protocol unavailable: {path}")
        return dict(yaml.safe_load(path.read_text(encoding="utf-8")))

    def campaign_geometry(
        self,
        frame: pd.DataFrame,
        split: Any,
        seed: int,
    ) -> CampaignGeometry:
        """Replicate V5's campaign geometry and floor-sensitivity construction."""

        protocol = self.protocol()
        campaign = protocol["campaign"]
        initial = max(30, min(len(split.source), round(len(frame) * campaign["initial_fraction_total"])))
        batch = max(1, round(len(frame) * campaign["batch_fraction_total"]))
        max_queries = max(1, round(len(split.target) * campaign["maximum_query_fraction_target"]))
        indices = np.sort(np.random.default_rng(int(seed)).choice(split.source, size=initial, replace=False))
        values = frame.target.to_numpy(float)[indices]
        median = float(np.median(values))
        robust_scale = max(
            float(np.std(values)),
            float((np.quantile(values, 0.75) - np.quantile(values, 0.25)) / 1.349),
            float(1.4826 * np.median(np.abs(values - median))),
            1e-12,
        )
        floor = float(protocol["oob"]["uncertainty_floor"])
        floor_grid = tuple(
            sorted({floor, *[max(1e-8, coefficient * robust_scale) for coefficient in (1e-8, 1e-6, 1e-5, 1e-4, 1e-3)]})
        )
        return CampaignGeometry(
            initial_count=int(initial),
            batch_size=int(batch),
            max_queries=int(max_queries),
            uncertainty_floor=floor,
            min_oob_trees_per_sample=int(protocol["oob"]["min_oob_trees_per_sample"]),
            floor_grid=floor_grid,
        )

    def v5_run_config(
        self,
        task: str,
        split: Any,
        seed: int,
        strategy: str,
        *,
        model: str | None = None,
    ) -> tuple[pd.DataFrame, np.ndarray, Any, dict[str, Any]]:
        """Build the exact V5 ``run_job.py`` configuration for one frozen job."""

        cache_key = str(task)
        cached = self._dataset_cache.get(cache_key)
        if cached is None:
            cached_frame = self.load_task(cache_key)
            cached_X = np.ascontiguousarray(
                self.featurize_dataset_wide(cached_frame.formula.to_numpy(str)), dtype=float
            )
            # V6 treats canonical descriptors as read-only input.  Marking the
            # cache immutable protects subsequent jobs from accidental mutation
            # while allowing the surrogate to consume the same exact values.
            cached_X.setflags(write=False)
            self._dataset_cache[cache_key] = (cached_frame.copy(deep=True), cached_X)
            cached = self._dataset_cache[cache_key]
        cached_frame, X = cached
        # DataFrame callers are allowed to manipulate their returned frame;
        # isolate that convenience from the reusable, frozen task cache.
        frame = cached_frame.copy(deep=True)
        formulas = frame.formula.to_numpy(str)
        ids = frame.material_id.to_numpy(str)
        split_result = self.split(formulas, ids, split, seed)
        geometry = self.campaign_geometry(frame, split_result, seed)
        protocol = self.protocol()
        candidate = dict(protocol["candidate_specific"])
        if strategy == "cs_da_oob_hist":
            candidate["min_oob_trees_per_sample"] = 3
        elif str(strategy).startswith("cs_da_oob"):
            candidate["min_oob_trees_per_sample"] = 10
        else:
            candidate["min_oob_trees_per_sample"] = geometry.min_oob_trees_per_sample
        # Frozen V5 jobs retain any historical candidate-specific override in
        # the manifest.  Broad V6 jobs deliberately have no V5 manifest row
        # and therefore keep the canonical protocol defaults above.
        historical_row = self.v5_manifest_row(task, split, seed, strategy, model=model)
        if historical_row is not None:
            raw_override = str(historical_row.get("candidate_specific_config_json", "") or "{}")
            override = json.loads(raw_override)
            if not isinstance(override, dict):
                raise CanonicalAdapterError("V5 candidate-specific manifest override is malformed")
            candidate.update(override)
        config = {
            "task": str(task),
            "campaign": {
                "initial_count": geometry.initial_count,
                "batch_size": geometry.batch_size,
                "max_queries": geometry.max_queries,
            },
            "model": dict(protocol["model"]),
            "oob": dict(protocol["oob"]),
            "candidate_specific": candidate,
            "acquisition": {},
            "floor_sensitivity": {
                "robust_initial_target_scale": float(max(geometry.floor_grid) / 1e-3),
                "absolute_floors": list(geometry.floor_grid),
            },
        }
        # The robust scale is reconstructed directly to preserve the exact V5
        # config hash rather than inferred from the rounded floor grid.
        initial = np.sort(np.random.default_rng(int(seed)).choice(split_result.source, size=geometry.initial_count, replace=False))
        values = frame.target.to_numpy(float)[initial]
        median = float(np.median(values))
        config["floor_sensitivity"]["robust_initial_target_scale"] = max(
            float(np.std(values)),
            float((np.quantile(values, 0.75) - np.quantile(values, 0.25)) / 1.349),
            float(1.4826 * np.median(np.abs(values - median))),
            1e-12,
        )
        return frame, X, split_result, config

    def v5_manifest_row(
        self,
        task: str,
        split: str,
        seed: int,
        strategy: str,
        *,
        model: str | None = None,
    ) -> dict[str, Any] | None:
        """Return one frozen V5 manifest row, or ``None`` for V6-only jobs."""

        table = pd.read_csv(self.paths.v5_manifest)
        matches = table.loc[
            (table.task.astype(str) == str(task))
            & (table.split_protocol.astype(str) == str(split))
            & (table.seed.astype(int) == int(seed))
            & (table.strategy.astype(str) == str(strategy))
        ]
        if model is not None:
            matches = matches.loc[matches.model.astype(str) == str(model)]
        if len(matches) > 1:
            overrides = matches.candidate_specific_config_json.astype(str).drop_duplicates().tolist()
            if len(overrides) != 1:
                raise CanonicalAdapterError("frozen V5 manifest has inconsistent historical strategy overrides")
        return None if matches.empty else dict(matches.iloc[0])

    def v5_identity(self, job_id: str, config: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
        manifest_hash = _sha256_file(self.paths.v5_manifest)
        protocol_hash = _sha256_file(self.paths.v5_protocol)
        relative_manifest = self.paths.v5_manifest.relative_to(self.paths.workspace).as_posix()
        relative_protocol = self.paths.v5_protocol.relative_to(self.paths.workspace).as_posix()
        identity = {
            "protocol_schema_version": "transportability-v5-rc1-confirmation-v1",
            "protocol_path": relative_protocol,
            "protocol_sha256": protocol_hash,
            "analysis_plan_path": relative_protocol,
            "analysis_plan_sha256": protocol_hash,
            "manifest_path": relative_manifest,
            "manifest_sha256": manifest_hash,
            "run_config_sha256": self.modules["provenance"].stable_payload_hash(config),
            "job_id": str(job_id),
        }
        return identity, self.paths.v5_protocol.read_bytes()

    @staticmethod
    def _checkpoint_rounds(directory: Path) -> dict[str, int]:
        output: dict[str, int] = {}
        for label in ("initial", "25pct", "50pct", "75pct"):
            metadata = json.loads((directory / f"checkpoint_{label}.json").read_text(encoding="utf-8"))
            output[label] = int(metadata["acquisition_round"])
        return output

    @classmethod
    def _l1(cls, directory: Path) -> float:
        diagnostic = pd.read_parquet(directory / "diagnostic_metrics.parquet")
        checkpoints = cls._checkpoint_rounds(directory)
        values = [float(diagnostic.iloc[checkpoints[label]]["mean_absolute_coverage_error"]) for label in ("initial", "25pct", "50pct", "75pct")]
        return float(np.mean(values))

    @staticmethod
    def _l4(directory: Path) -> float:
        return float(json.loads((directory / "state.json").read_text(encoding="utf-8"))["primary_nauc"])

    @staticmethod
    def _logical_trajectory_hash(directory: Path) -> str:
        """Hash deterministic scientific state while intentionally excluding runtime telemetry."""

        directory = Path(directory)
        frames: dict[str, Any] = {}
        for name in ("rounds", "selected", "diagnostic_metrics", "floor_ranking_audit"):
            frame = pd.read_parquet(directory / f"{name}.parquet").copy()
            frame = frame.drop(columns=[column for column in ("runtime_seconds", "peak_memory_mb") if column in frame], errors="ignore")
            frames[name] = json.loads(frame.to_json(orient="split", date_format="iso", double_precision=15))
        state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
        payload = {
            "frames": frames,
            "state": state,
            "checkpoints": {
                label: json.loads((directory / f"checkpoint_{label}.json").read_text(encoding="utf-8"))
                for label in ("initial", "25pct", "50pct", "75pct")
            },
        }
        return _stable_hash(payload)

    def replay_raw(
        self,
        *,
        job_id: str = "matbench_expt_gap__iid_record__random_forest__raw_ucb_beta_1__seed5000",
        output_root: str | Path,
    ) -> RawReplayResult:
        """Rerun a frozen V5 RAW job into a non-destructive caller-owned directory."""

        self.assert_source_lock()
        self.validate_pymatgen()
        table = pd.read_csv(self.paths.v5_manifest)
        rows = table.loc[table.job_id.astype(str) == str(job_id)]
        if len(rows) != 1:
            raise CanonicalAdapterError(f"V5 manifest requires exactly one replay row for {job_id!r}")
        row = rows.iloc[0]
        if str(row.strategy) != "raw_ucb_beta_1":
            raise CanonicalAdapterError("canonical replay is intentionally restricted to V5 RAW beta=1")
        frame, X, split, config = self.v5_run_config(
            str(row.task), str(row.split_protocol), int(row.seed), str(row.strategy), model=str(row.model)
        )
        identity, protocol_raw = self.v5_identity(str(row.job_id), config)
        reference = self.paths.v5_root / str(row.expected_output_relative_path)
        if not reference.is_dir():
            raise CanonicalAdapterError(f"frozen V5 trajectory is unavailable: {reference}")
        output_root = Path(output_root).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        result = self.modules["runner"].run_trajectory(
            X,
            frame.target.to_numpy(float),
            frame.formula.to_numpy(str),
            frame.material_id.to_numpy(str),
            split,
            str(row.strategy),
            str(row.model),
            int(row.seed),
            config,
            output_root,
            identity,
            protocol_raw,
            True,
        )
        replay = output_root / str(result["key"])
        ids = frame.material_id.to_numpy(str)
        initial = json.loads(pd.read_parquet(reference / "rounds.parquet").iloc[0]["queried_ids_before"])
        replay_initial = json.loads(pd.read_parquet(replay / "rounds.parquet").iloc[0]["queried_ids_before"])
        reference_rounds = pd.read_parquet(reference / "rounds.parquet").sort_values("round")
        replay_rounds = pd.read_parquet(replay / "rounds.parquet").sort_values("round")
        reference_batches = reference_rounds.loc[reference_rounds["round"] >= 0, "selected_batch_ids"].tolist()
        replay_batches = replay_rounds.loc[replay_rounds["round"] >= 0, "selected_batch_ids"].tolist()
        reference_checkpoint_rounds = self._checkpoint_rounds(reference)
        replay_checkpoint_rounds = self._checkpoint_rounds(replay)
        checks = {
            "source_split_hash": _id_hash(ids[split.source]) == _id_hash(ids[split.source]),
            "target_split_hash": _id_hash(ids[split.target]) == _id_hash(ids[split.target]),
            "diagnostic_split_hash": _id_hash(ids[split.diagnostic]) == _id_hash(ids[split.diagnostic]),
            "initial_labeled_ids": initial == replay_initial,
            "every_queried_batch": reference_batches == replay_batches,
            "checkpoint_definitions": reference_checkpoint_rounds == replay_checkpoint_rounds,
            "l1_campaign_mace": bool(np.isclose(self._l1(reference), self._l1(replay), rtol=0.0, atol=0.0)),
            "l4_top1pct_recall_nauc": bool(np.isclose(self._l4(reference), self._l4(replay), rtol=0.0, atol=0.0)),
            "logical_trajectory_hash": self._logical_trajectory_hash(reference) == self._logical_trajectory_hash(replay),
        }
        # The frozen source split has to be compared to a separately
        # reconstructed canonical V5 split, not merely the object used above.
        frozen_split = self.split(frame.formula.to_numpy(str), ids, str(row.split_protocol), int(row.seed))
        checks["source_split_hash"] = _id_hash(ids[frozen_split.source]) == _id_hash(ids[split.source])
        checks["target_split_hash"] = _id_hash(ids[frozen_split.target]) == _id_hash(ids[split.target])
        checks["diagnostic_split_hash"] = _id_hash(ids[frozen_split.diagnostic]) == _id_hash(ids[split.diagnostic])
        ordered_checks = (
            "source_split_hash",
            "target_split_hash",
            "diagnostic_split_hash",
            "initial_labeled_ids",
            "every_queried_batch",
            "checkpoint_definitions",
            "l1_campaign_mace",
            "l4_top1pct_recall_nauc",
            "logical_trajectory_hash",
        )
        first = next((name for name in ordered_checks if not checks[name]), None)
        reference_hashes = {
            "logical_trajectory_sha256": self._logical_trajectory_hash(reference),
            "source_code_sha256": _sha256_file(reference / "source_code_hashes.json"),
        }
        replay_hashes = {
            "logical_trajectory_sha256": self._logical_trajectory_hash(replay),
            "source_code_sha256": _sha256_file(replay / "source_code_hashes.json"),
        }
        return RawReplayResult(
            job_id=str(job_id),
            passed=all(checks.values()),
            first_divergence=first,
            checks=checks,
            reference_hashes=reference_hashes,
            replay_hashes=replay_hashes,
            reference_l1=self._l1(reference),
            replay_l1=self._l1(replay),
            reference_l4=self._l4(reference),
            replay_l4=self._l4(replay),
            output_dir=str(replay),
        )

    @staticmethod
    def _frame_hash(frame: pd.DataFrame) -> str:
        return _stable_hash(json.loads(frame.to_json(orient="split", date_format="iso", double_precision=15)))

    def replay_historical_strategy(
        self,
        *,
        job_id: str,
        output_root: str | Path,
    ) -> HistoricalStrategyReplayResult:
        """Exactly re-run one frozen GG/CS strategy into V6-owned storage.

        This is intentionally a thin call to the frozen V5 runner.  It is not
        a replacement implementation, and it never writes under ``revision_v5``.
        """

        allowed = {
            "gg_ucb_beta_1",
            "gg_ucb_beta_0p5",
            "cs_da_oob_hist",
            "cs_da_oob_parsimonious_f1",
        }
        self.assert_source_lock()
        self.validate_pymatgen()
        table = pd.read_csv(self.paths.v5_manifest)
        rows = table.loc[table.job_id.astype(str) == str(job_id)]
        if len(rows) != 1:
            raise CanonicalAdapterError(f"V5 manifest requires exactly one replay row for {job_id!r}")
        row = rows.iloc[0]
        strategy = str(row.strategy)
        if strategy not in allowed:
            raise CanonicalAdapterError(f"unsupported historical strategy replay: {strategy}")
        frame, X, split, config = self.v5_run_config(
            str(row.task), str(row.split_protocol), int(row.seed), strategy, model=str(row.model)
        )
        identity, protocol_raw = self.v5_identity(str(row.job_id), config)
        reference = self.paths.v5_root / str(row.expected_output_relative_path)
        if not reference.is_dir():
            raise CanonicalAdapterError(f"frozen V5 trajectory is unavailable: {reference}")
        root = Path(output_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        result = self.modules["runner"].run_trajectory(
            X,
            frame.target.to_numpy(float),
            frame.formula.to_numpy(str),
            frame.material_id.to_numpy(str),
            split,
            strategy,
            str(row.model),
            int(row.seed),
            config,
            root,
            identity,
            protocol_raw,
            True,
        )
        replay = root / str(result["key"])
        ids = frame.material_id.to_numpy(str)
        reference_rounds = pd.read_parquet(reference / "rounds.parquet").sort_values("round")
        replay_rounds = pd.read_parquet(replay / "rounds.parquet").sort_values("round")
        reference_selected = pd.read_parquet(reference / "selected.parquet").sort_values(
            ["round", "rank"], kind="stable"
        )
        replay_selected = pd.read_parquet(replay / "selected.parquet").sort_values(
            ["round", "rank"], kind="stable"
        )
        predictive_columns = [
            column
            for column in (
                "round",
                "rank",
                "candidate_id",
                "predicted_mean",
                "raw_predicted_std",
                "effective_predicted_std",
            )
            if column in reference_selected and column in replay_selected
        ]
        scale_columns = [
            column
            for column in ("round", "global_scale", "scale_status", "candidate_scale_status")
            if column in reference_rounds and column in replay_rounds
        ]
        score_columns = [
            column
            for column in ("round", "rank", "candidate_id", "scale", "score")
            if column in reference_selected and column in replay_selected
        ]
        rank_columns = [
            column
            for column in ("round", "rank", "candidate_id", "stable_candidate_id", "selected")
            if column in reference_selected and column in replay_selected
        ]
        reference_initial = json.loads(reference_rounds.iloc[0]["queried_ids_before"])
        replay_initial = json.loads(replay_rounds.iloc[0]["queried_ids_before"])
        checks = {
            "source_split_hash": True,
            "target_split_hash": True,
            "diagnostic_split_hash": True,
            "initial_labeled_ids": reference_initial == replay_initial,
            "per_round_predictive_mean_raw_sigma": self._frame_hash(reference_selected[predictive_columns])
            == self._frame_hash(replay_selected[predictive_columns]),
            "fitted_scale_or_cs_parameters": self._frame_hash(reference_rounds[scale_columns])
            == self._frame_hash(replay_rounds[scale_columns]),
            "acquisition_scores": self._frame_hash(reference_selected[score_columns])
            == self._frame_hash(replay_selected[score_columns]),
            "stable_ranking": self._frame_hash(reference_selected[rank_columns])
            == self._frame_hash(replay_selected[rank_columns]),
            "selected_batch": reference_rounds.loc[reference_rounds["round"] >= 0, "selected_batch_ids"].tolist()
            == replay_rounds.loc[replay_rounds["round"] >= 0, "selected_batch_ids"].tolist(),
            "checkpoint_values": self._checkpoint_rounds(reference) == self._checkpoint_rounds(replay),
            "l1_campaign_mace": bool(np.isclose(self._l1(reference), self._l1(replay), rtol=0.0, atol=0.0)),
            "l4_top1pct_recall_nauc": bool(np.isclose(self._l4(reference), self._l4(replay), rtol=0.0, atol=0.0)),
            "logical_trajectory_hash": self._logical_trajectory_hash(reference) == self._logical_trajectory_hash(replay),
        }
        frozen_split = self.split(frame.formula.to_numpy(str), ids, str(row.split_protocol), int(row.seed))
        checks["source_split_hash"] = _id_hash(ids[frozen_split.source]) == _id_hash(ids[split.source])
        checks["target_split_hash"] = _id_hash(ids[frozen_split.target]) == _id_hash(ids[split.target])
        checks["diagnostic_split_hash"] = _id_hash(ids[frozen_split.diagnostic]) == _id_hash(ids[split.diagnostic])
        ordered = (
            "source_split_hash",
            "target_split_hash",
            "diagnostic_split_hash",
            "initial_labeled_ids",
            "per_round_predictive_mean_raw_sigma",
            "fitted_scale_or_cs_parameters",
            "acquisition_scores",
            "stable_ranking",
            "selected_batch",
            "checkpoint_values",
            "l1_campaign_mace",
            "l4_top1pct_recall_nauc",
            "logical_trajectory_hash",
        )
        first = next((name for name in ordered if not checks[name]), None)
        return HistoricalStrategyReplayResult(
            job_id=str(job_id),
            v5_strategy=strategy,
            passed=all(checks.values()),
            first_divergence=first,
            checks=checks,
            reference_hashes={
                "logical_trajectory_sha256": self._logical_trajectory_hash(reference),
                "source_code_sha256": _sha256_file(reference / "source_code_hashes.json"),
            },
            replay_hashes={
                "logical_trajectory_sha256": self._logical_trajectory_hash(replay),
                "source_code_sha256": _sha256_file(replay / "source_code_hashes.json"),
            },
            reference_l1=self._l1(reference),
            replay_l1=self._l1(replay),
            reference_l4=self._l4(reference),
            replay_l4=self._l4(replay),
            output_dir=str(replay),
        )
