# AGENTS.md — w4h-data-recorder-csv-file-importer

Importer module for **user-supplied Empatica E4 data-recorder CSV files** (notebook + CLI + tests). No bundled Kaggle or PhysioNet download. The notebook picks files with a chooser. In-app **Run** / `./run.sh` calls the CLI and loads the synthetic fixtures declared in `contribution.yaml`.

Kaggle / vendor references (do not copy those files into git):

- https://www.kaggle.com/datasets/priyankraval/nurse-stress-prediction-wearable-sensors
- https://www.kaggle.com/datasets/mahdiesoltani/galaxyppg
- https://www.kaggle.com/datasets/omprakashyadav45/pain-prediction-dataset-emphatica-e4
- https://www.empatica.com/blog/decoding-wearable-sensor-signals-what-to-expect-from-your-e4-data/
- https://physionet.org/content/wearable-device-dataset/

- API key via `W4H_API_KEY` in local `.env` only — never in git.
- Do not add direct Postgres / `to_sql` paths; use the W4H API (`POST /datasets/:id/import/csv-batch`).
- The module owns its mapping logic (`profile.py`, `mapping.py`, `reconcile.py`, `catalog.py`, `shapes.py`, `e4_connect.py`). Do not call any W4H API route except `csv-batch` and `GET /datasets` (notebook picker).
- Supported layouts: E4 Connect (unix t0 + Hz, no header), headered merged/per-signal research CSVs, GalaxyPPG, pain-prediction `person_ID` merge. Official E3 and Embrace/Avro are out of scope.
- When a file has no id column, `subject_id` comes from the nearest parent folder that is not a device directory (`P02/E4/ACC.csv` → `P02`); for a Connect ZIP extract it is the session folder.
- The merged nurse-stress shape wins over narrower per-signal shapes when both could match.
- Every `csv-batch` payload sends `table_prefix: "recorder"` (`config.TABLE_PREFIX`) — do not drop it.
- Progress: keep printing `@@PROGRESS@@ {json}` lines (contribution-runner.js parses them).
- Tests: `pytest tests/ -q -m "not integration"`. `contribution.yaml` is the test contract. `-m integration` tests need a running w4h-api.
