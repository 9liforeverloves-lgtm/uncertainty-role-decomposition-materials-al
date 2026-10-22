# Author procedure: publish GitHub and permanent archive

This checklist was drafted before repository creation. Since then, the repository has been made public and the historical experiment-data archive was published as a GitHub Release (`research-data-archive-2026-08-17`, 2026-08-17). Do not repeat repository-creation, remote-push or visibility-change steps. The archive is not the planned formal `v1.0.0` software release and has no Zenodo DOI. The remaining work concerns review of the formal software-release candidate and any later Zenodo deposition. BSD-3-Clause and the processed-output authorization are resolved.

1. Complete the remaining author metadata and create a real repository under the authorized account; enable secret scanning and confirm visibility/default branch.
2. Review `dist/release_candidate`, `public_release_archive_inventory.csv` and `SHA256SUMS`.
3. Add the real remote and push the reviewed branch (replace the placeholder only after the repository exists):

   ```bash
   git remote add origin <REAL_URL>
   git push -u origin codex/bsd3-publication-final
   ```

4. Inspect Git history for secrets and files over hosting limits. Do not force-push, rewrite history, change repository visibility or delete history without separate approval.
5. After confirming the pushed commit and online CI, create and push the authorized immutable tag:

   ```bash
   git tag -a v1.0.0 -m "Version 1.0.0"
   git push origin v1.0.0
   ```

6. Connect the public repository to Zenodo through the author's account; never place tokens in this repository.
7. Create the GitHub release from the exact reviewed commit/candidate and wait for Zenodo to mint the DOI.
8. Record both the Zenodo version DOI and concept DOI. Insert only the resolving repository URL/version DOI into README, CFF, paper availability text and metadata. Create a metadata-only follow-up tag if required.
9. Verify the DOI resolves to content matching `SHA256SUMS` and keep the paper's tag, commit and DOI aligned.

Avoid a DOI/content loop: archive the content first, receive the DOI, then update only metadata in a clearly versioned follow-up release.

Current state (2026-10-22): `PUBLIC_REPOSITORY_CREATED = true`; online GitHub Actions tests/reproducibility have successful runs (see `reports/ONLINE_CI_RESULTS.md`); historical GitHub archive Release = published; formal `v1.0.0` software tag/Release = not published; Zenodo DOI = not created.
