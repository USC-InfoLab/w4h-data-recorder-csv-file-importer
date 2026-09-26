# W4H Data Recorder CSV File Importer

Notebook + CLI to import **research data-recorder CSV files you supply** into W4H. The layouts it recognizes are Empatica E4 exports: a merged channel file, tidy per-signal files with `id` and `datetime`, and GalaxyPPG-style per-signal files with a `timestamp` column. Pick your own files (or point the CLI at a folder); the importer builds a GeoMTS mapping from their headers, lets you review it, and ingests them through the W4H API. Credentials stay in a local `.env` (never committed).

**Publisher:** usc-infolab · **Kinds:** notebook, CLI · **Language:** Python

This repo is bootstrapped from [w4h-fitbit-csv-file-importer](https://github.com/USC-InfoLab/w4h-fitbit-csv-file-importer): `plan` → review `manifest.yaml` → `import` / `sync` via `POST /datasets/:id/import/csv-batch`. Every payload sends `table_prefix: "recorder"`.

The E4 is a wrist-worn physiological recorder (accelerometer, blood volume pulse, electrodermal activity, heart rate, inter-beat interval, skin temperature). It is a different export from a consumer Fitbit CSV and from a glucose monitor.

## Kaggle samples

Do not commit those downloads. `tests/fixtures/` is a few synthetic rows that use the same headers.

| Layout | Kaggle dataset | Headers the shape match uses |
|--------|----------------|------------------------------|
| Merged channels plus a study label | [Nurse Stress Prediction Wearable Sensors](https://www.kaggle.com/datasets/priyankraval/nurse-stress-prediction-wearable-sensors) | `id`, `datetime`, `X`, `Y`, `Z`, `EDA`, `HR`, `TEMP` (`label` is kept on the table and is not a sensor value) |
| Per-signal files with a wearer id | Same study, split one channel per file | `id`, `datetime`, and `HR` / `EDA` / `TEMP` / `X,Y,Z` / `BVP` / `IBI` |
| Per-signal E4 files (no id column) | [GalaxyPPG](https://www.kaggle.com/datasets/mahdiesoltani/galaxyppg) | `timestamp`, `x`, `y`, `z` (and `hr`, `eda`, `temp`, `bvp`, `ibi`) |

GalaxyPPG stores participants as folders (`P02/E4/ACC.csv`). The importer reads a header row. When there is no id column it sets `subject_id` from the nearest parent folder that is not a device directory (`E4` is skipped, so `P02/E4/ACC.csv` → subject `P02`). A flat file uses its stem.

Official E4 Connect downloads have no header (unix time, then a sample rate, then values). Those files are not this shape. Use a header row, which is how the Kaggle copies above are published. GalaxyPPG `timestamp` values are Unix microseconds and are stored as `bigint`.

Declared sampling intervals on the mapping follow the E4 firmware rates (ACC 32 Hz, EDA/TEMP 4 Hz, HR 1 s, BVP 64 Hz). The nurse-stress merge does not get a single interval because the channels were aligned in that dataset.

## Who should do what

| Role | What to do |
|------|------------|
| **Admin** | Ingest your CSVs into **your team's** catalog. Use the CLI (`import` / `sync`) for cron and incremental updates. |
| **User** | Use analysis contributions against loaded datasets. You cannot add datasets or edit raw tables. |
| **Super admin** | Catalog this repo after it is on a git remote. This package is not seeded into `w4h.contributions` until then. |

## How it works

1. **Files** — one CSV per signal (or one merged file), header row, UTF-8. The **notebook** has a file chooser. **In-app Run / `./run.sh` do not use the notebook** — they call the CLI and load the fixtures listed in [`contribution.yaml`](contribution.yaml).
2. **Plan** — profiles each CSV locally, builds a GeoMTS mapping in this package, runs the six deterministic checks, and writes `manifest.yaml` + `plan.json` when you pass `--data-dir`.
3. **Import** — streams rows in 500-row chunks to `POST /datasets/:id/import/csv-batch` with `table_prefix: "recorder"`. Progress is reported through `@@PROGRESS@@` lines.

`plan` only sees `*.csv` in the top of `--data-dir`. For a GalaxyPPG tree, point it at one participant folder or pass files into the notebook chooser.

## Prerequisites

- Running **w4h-api** and a personal API key (Profile → API keys)
- A dataset you can ingest into
- Python 3.10+

## Credentials

```bash
cp .env.example .env
# Edit .env — W4H_API_KEY only
```

## Install

```bash
pip install -e ".[dev,notebook]"
```

## Notebook

Open [`notebook/import_data_recorder_csv_file.ipynb`](notebook/import_data_recorder_csv_file.ipynb) and run the cells in order: **pick dataset → pick files → review mapping → import**.

## CLI

```bash
w4h-data-recorder-csv-file-import plan --data-dir /path/to/csvs
export W4H_API_KEY=w4h_sk_...
w4h-data-recorder-csv-file-import import --dataset-id my-e4-data --data-dir /path/to/csvs --mode append
```

## One-command run (`run.sh`)

```bash
./run.sh plan
./run.sh import
```

## Tests

```bash
pytest tests/ -q -m "not integration"
```

Optional API test, needs a running w4h-api:

```bash
export W4H_API_KEY=... W4H_DATASET_ID=my-e4-data
pytest tests/test_import_api.py -m integration -q
```
