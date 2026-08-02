# External reproduction test

Overall status: **PASS**

A fresh Python 3.12 virtual environment was created outside the repository. Only a copied `dist/release_candidate` tree was used; pip cache was disabled. No local Matbench data or parent-repository file was read.

| Step | Return code | Seconds |
|---|---:|---:|
| `<PYTHON> -m pip install --no-cache-dir -r requirements-lock.txt` | 0 | 146.196 |
| `<PYTHON> -m pip install --no-cache-dir build==1.3.0` | 0 | 8.584 |
| `<PYTHON> -m build --outdir <TEMP_ROOT>\outputs 空格\packages .` | 0 | 12.131 |
| `<PYTHON> -m pip install --no-cache-dir --no-deps --force-reinstall <TEMP_ROOT>\outputs 空格\packages\materials_transportability_v6-1.0.0-py3-none-any.whl` | 0 | 3.686 |
| `<PYTHON> -c import importlib.metadata as m, transportability_v6, p1_extension; assert m.version('materials-transportability-v6') == '1.0.0'` | 0 | 5.905 |
| `<PYTHON> -m pip install --no-cache-dir --no-deps --force-reinstall <TEMP_ROOT>\outputs 空格\packages\materials_transportability_v6-1.0.0.tar.gz` | 0 | 11.541 |
| `<PYTHON> -c import importlib.metadata as m, transportability_v6, p1_extension; assert m.version('materials-transportability-v6') == '1.0.0'` | 0 | 1.257 |
| `<PYTHON> -m pip check` | 0 | 0.619 |
| `<PYTHON> -m transportability_v6 --help` | 0 | 1.184 |
| `<PYTHON> scripts/verify_release.py --json-output <TEMP_ROOT>\outputs 空格\verify.json` | 0 | 0.906 |
| `<PYTHON> scripts/reproduce_smoke.py --output-dir <TEMP_ROOT>\outputs 空格\smoke 复现` | 0 | 1.512 |
| `<PYTHON> scripts/reproduce_tables.py --output-dir <TEMP_ROOT>\outputs 空格\tables 复现` | 0 | 2.247 |
| `<PYTHON> scripts/reproduce_figures.py --output-dir <TEMP_ROOT>\outputs 空格\figures 复现` | 0 | 18.444 |
| `<PYTHON> scripts/reproduce_manuscript.py --output-dir <TEMP_ROOT>\outputs 空格\manuscript 复现` | 0 | 13.324 |
| `<PYTHON> -m pytest tests v6_revision/tests -q` | 0 | 25.64 |
| `<PYTHON> scripts/verify_release.py --json-output <TEMP_ROOT>\outputs 空格\verify_after.json` | 0 | 0.601 |

Full sanitized stdout/stderr tails and output hashes are in `reports/external_reproduction_status.json`.
