from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from transportability_v6.execution_registry import (
    CanonicalJobRegistry,
    CrashInjected,
    DurableCheckpointStore,
)


def _identity() -> dict[str, str]:
    return {
        "protocol_sha256": "protocol-smoke",
        "run_config_sha256": "config-smoke",
        "job_id": "smoke-91000",
    }


def test_registry_legal_transitions_duplicate_claim_and_unchanged_retry(tmp_path) -> None:
    registry = CanonicalJobRegistry(tmp_path / "registry.sqlite")
    first = registry.initialize(["smoke-91000", "smoke-91001"], "manifest-smoke")
    first.close()
    connection = registry.connect()
    claim = registry.claim_specific(connection, "smoke-91000", "worker-a", 1, "host")
    assert claim["attempt"] == 1
    with pytest.raises(ValueError, match="not planned"):
        registry.claim_specific(connection, "smoke-91000", "worker-b", 2, "host")
    registry.transition(connection, "smoke-91000", "FAILED", {"last_error": "synthetic"})
    with pytest.raises(ValueError, match="invalid"):
        registry.transition(connection, "smoke-91000", "COMPLETED")
    registry.transition(connection, "smoke-91000", "PLANNED", allow_retry=True)
    retried = registry.claim_specific(connection, "smoke-91000", "worker-a", 1, "host")
    assert retried["attempt"] == 2
    registry.transition(connection, "smoke-91000", "COMPLETED", {"output_hash": "same-config"})
    connection.close()
    snapshot = registry.snapshot_frame()
    row = snapshot.set_index("job_id").loc["smoke-91000"]
    assert row.status == "COMPLETED"
    assert row.retry_count == 1
    check = registry.connect()
    immutable = check.execute("SELECT value FROM metadata WHERE key='immutable_task_manifest_sha256'").fetchone()[0]
    check.close()
    assert immutable == "manifest-smoke"


def test_concurrent_workers_cannot_claim_the_same_job(tmp_path) -> None:
    registry = CanonicalJobRegistry(tmp_path / "concurrent.sqlite")
    connection = registry.initialize(["smoke-91000", "smoke-91001"], "manifest-smoke")
    connection.close()

    def claim(worker: str):
        connection = registry.connect()
        try:
            return registry.claim_next(connection, worker, 1, "host")
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, ["worker-a", "worker-b"]))
    assert {claim["job_id"] for claim in claims if claim is not None} == {"smoke-91000", "smoke-91001"}


def test_checkpoint_crash_boundaries_recover_and_reject_overwrite(tmp_path) -> None:
    store = DurableCheckpointStore(tmp_path / "checkpoints")
    identity = _identity()
    with pytest.raises(CrashInjected, match="before_model"):
        store.write_payload("initial", b"model-v1", identity, crash_at="before_model_checkpoint_write")
    assert store.last_valid_checkpoint() is None
    with pytest.raises(CrashInjected, match="temporary"):
        store.write_payload(
            "initial",
            b"model-v1",
            identity,
            realized_progress=0.0,
            acquisition_round=-1,
            queried_count=30,
            crash_at="after_temporary_write_before_rename",
        )
    actions = store.recover(identity)
    assert actions == ["initial:temporary_promoted"]
    assert store.last_valid_checkpoint() == "initial"
    metadata = json.loads((tmp_path / "checkpoints" / "checkpoint_initial.json").read_text(encoding="utf-8"))
    assert metadata["acquisition_round"] == -1
    assert metadata["queried_count"] == 30
    assert store.write_payload("initial", b"model-v1", identity) == "existing_identical"
    with pytest.raises(FileExistsError, match="overwrite"):
        store.write_payload("initial", b"model-v2", identity)
