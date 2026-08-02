# Public release file audit

Status: **PASS for the BSD3 publication candidate**.

`scripts/build_release_candidate.py` constructs `dist/release_candidate` from an allowlist and requires the authorized root BSD-3-Clause license. It rejects either unresolved license-decision file. Every non-`SHA256SUMS` regular file is covered exactly once by `SHA256SUMS`; zero mismatch is required by `scripts/verify_archive_checksums.py`.

`public_release_archive_inventory.csv` classifies source/metadata, tests, automation, documentation, manuscript assets, compact locked evidence and data-provenance metadata. Its self row uses `SELF_REFERENTIAL_NOT_APPLICABLE`, because an inventory cannot contain its own final digest. Root inventory/checksum/exclusion files mirror the latest build.

Included V5 content is restricted to the minimal source and frozen authority files needed by retained regression tests. A tiny compatibility marker preserves the expected canonical directory contract without bundling raw data. Raw trajectories, raw task snapshots, the 68+ GiB execution corpus, environments, caches, logs and historical workspaces are excluded.

The large retained P1 calibration/trajectory tables are author-generated processed outputs required for Level-2 deterministic reconstruction and fall within the explicit authorization scope. The machine inventory, not a prose count, is authoritative after each rebuild.
