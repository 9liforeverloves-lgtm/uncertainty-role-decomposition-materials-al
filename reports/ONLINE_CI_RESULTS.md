# Online CI results

`GITHUB_ACTIONS_STATUS = PASS` for audited main commit `1d6fef9ca8dca3fc92877405d967dde40dcdedc6`.

| Workflow/job | Result | Evidence |
|---|---|---|
| tests / Ubuntu Python 3.12 | PASS | [job 91473311352](https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al/actions/runs/30739158679/job/91473311352) |
| tests / Windows Python 3.12 | PASS | [job 91473311387](https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al/actions/runs/30739158679/job/91473311387) |
| reproducibility / Ubuntu Python 3.12 | PASS | [job 91473311433](https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al/actions/runs/30739158689/job/91473311433) |

The tests workflow passed checkout with Git LFS, dependency installation, package installation, `pip check`, authority verification, the unit-test suite, and the Unicode/space-path smoke test on both operating systems. The reproducibility workflow passed authority verification, smoke reproduction, table reconstruction, selected figure reconstruction, wheel/sdist build, and artifact upload. Linux TeX was not part of these workflows and remains `NOT_TESTED` online.

Initial-import tests failed on commit `9b4dafbc0b3880663da05e4ec3eff1f85973ad6b` because checkout line-ending normalization changed byte-locked assets and two data-exclusion marker directories were absent. PR [#1](https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al/pull/1) fixed only cross-platform byte preservation and marker packaging; no scientific file contents, locks, expected hashes, or test gates were changed.
