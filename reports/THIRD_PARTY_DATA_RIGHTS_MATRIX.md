# Third-party data rights matrix

Public availability does not automatically authorize repackaging. The conservative release policy is to publish retrieval metadata, checksums, preprocessing code and split/result authorities while excluding local raw/processed task snapshots until the author confirms redistribution rights.

| Dataset/task | Upstream source | Upstream terms/license | Bundled in release? | Redistribution allowed? | Rebuild procedure | Required citation |
|---|---|---|---:|---|---|---|
| `matbench_expt_gap` | Matbench v0.1; Zhuo et al. supplementary data | Matbench software MIT; underlying experimental compilation rights not expressly resolved by repository license | No | AUTHOR/LEGAL REVIEW REQUIRED | Retrieve official Matbench object, verify SHA-256, convert composition/target in original order | Dunn et al. 2020; Zhuo et al. 2018, DOI 10.1021/acs.jpclett.8b00124 |
| `matbench_mp_gap` | Matbench v0.1 snapshot adapted from Materials Project (2019-04-02) | Materials Project currently states CC BY 4.0 for its data; snapshot-specific attribution/version must be preserved | No pending author approval | Conditionally, with attribution and snapshot confirmation | Retrieve official Matbench object, verify SHA-256, derive reduced formula/target | Dunn et al. 2020; Jain et al. 2013, DOI 10.1063/1.4812323 |
| `matbench_log_gvrh` | Matbench v0.1 / Materials Project elastic data | Same caution as Materials Project-derived snapshot | No pending author approval | Conditionally, with attribution and snapshot confirmation | Official retrieval, checksum, reduced-formula conversion | Dunn et al. 2020; de Jong et al. 2015 |
| `matbench_log_kvrh` | Matbench v0.1 / Materials Project elastic data | Same caution as Materials Project-derived snapshot | No pending author approval | Conditionally, with attribution and snapshot confirmation | Official retrieval, checksum, reduced-formula conversion | Dunn et al. 2020; de Jong et al. 2015 |

Official provenance references: <https://github.com/materialsproject/matbench>, <https://hackingmaterials.lbl.gov/matminer/dataset_summary.html>, and <https://doi.org/10.17188/1281376>. The release script never bypasses authentication or terms and stops on checksum mismatch.

