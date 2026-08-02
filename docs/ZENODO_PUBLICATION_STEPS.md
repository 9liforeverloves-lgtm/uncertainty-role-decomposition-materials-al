# Zenodo publication steps

The current machine has no `ZENODO_TOKEN`. Do not paste a token into chat, prompts, Git files, CI logs or reports.

1. Keep the GitHub repository private until online CI and pre-public audits pass.
2. After author approval, make the reviewed repository public and create the exact annotated `v1.0.0` tag.
3. Connect the repository to production Zenodo through the author's browser/account.
4. Create a draft deposition from `release_metadata/zenodo.json` and upload the checksum-verified archive candidate.
5. Verify filenames, sizes, SHA-256 values, author identity, BSD-3-Clause scope and raw-data exclusion.
6. Record the draft deposition ID and reserved DOI without calling the publish endpoint.
7. Obtain separate explicit author confirmation before permanent publication.
8. After publication, verify the DOI resolves and update README/CFF/paper availability metadata in a metadata-only follow-up commit.
