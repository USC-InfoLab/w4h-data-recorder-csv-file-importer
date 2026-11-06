# W4H Data Recorder CSV File Importer

Notebook + CLI to import **research data-recorder CSV files you supply** into W4H. The layouts it recognizes are Empatica E4 exports: **E4 Connect** session ZIPs (no header row), merged research CSVs, tidy per-signal files with `id` and `datetime`, and GalaxyPPG-style per-signal files with a `timestamp` column. Pick your own files (or point the CLI at a folder); the importer builds a GeoMTS mapping from the files, lets you review it, and ingests them through the W4H API. Credentials stay in a local `.env` (never committed).

**Publisher:** usc-infolab · **Kinds:** notebook, CLI · **Language:** Python

This repo is bootstrapped from [w4h-fitbit-csv-file-importer](https://github.com/USC-InfoLab/w4h-fitbit-csv-file-importer): `plan` → review `manifest.yaml` → `import` / `sync` via `POST /datasets/:id/import/csv-batch`. Every payload sends `table_prefix: "recorder"`.

## Empatica devices (E3, E4, Embrace)

Empatica has shipped several wristbands. This importer is for **E4 CSV**, not for later Cloud/Avro products.

| Device | Years (approx.) | What the export looks like | This importer |
|--------|-----------------|----------------------------|---------------|
| **E3** | Predecessor to the E4 | Empatica’s old public demo used E3 recordings. Different generation; not the E4 Connect ZIP. | No |
| **E4** | Research wearable from 2015; E4 Connect and the device were [sunset 14 Feb 2025](https://academic-support.empatica.com/hc/en-us/sections/36980773150749-Understanding-Using-Your-Data) | Session ZIP from E4 Connect: `ACC.csv`, `BVP.csv`, `EDA.csv`, `HR.csv`, `IBI.csv`, `TEMP.csv`, `info.txt`. Many public studies republish the same channels as **headered** CSVs. | **Yes** — Connect (headerless) and the headered research copies below |
| **Embrace / EmbracePlus** (Empatica Health Monitoring Platform) | Current clinical/research line | Avro in Empatica Cloud, not E4 Connect CSV. | No — different format |

The E4 is a wrist-worn physiological recorder (accelerometer, blood volume pulse / PPG, electrodermal activity, heart rate, inter-beat interval, skin temperature). It is a different export from a consumer Fitbit CSV and from a glucose monitor.

Empatica documents the E4 Connect CSV layout here: [Decoding wearable sensor signals — what to expect from your E4 data](https://www.empatica.com/blog/decoding-wearable-sensor-signals-what-to-expect-from-your-e4-data/). Firmware rates: ACC 32 Hz, BVP 64 Hz, EDA/TEMP 4 Hz, HR 1 Hz. Accelerometer counts are raw (`64 ≈ 1 g`; Empatica: `xg = x * 2/128`).

`tags.csv` (button-press marks) and `info.txt` are not imported.

## Public samples

Do not commit those downloads. `tests/fixtures/` is a few synthetic rows that use the same headers or Connect preamble.

### E4 Connect (raw, no header)

Unzip the session and point `--data-dir` at that folder (or a PhysioNet tree that still uses Empatica filenames).

| File | Row 1 | Row 2 | Later rows |
|------|-------|-------|------------|
| `ACC.csv` | unix t0, three times (one per axis) | `32` Hz, three times | `x,y,z` raw counts |
| `BVP.csv`, `EDA.csv`, `TEMP.csv`, `HR.csv` | unix t0 | sample rate (Hz) | one value per row |
| `IBI.csv` | `t0, IBI` | — | `seconds_from_t0, ibi` |

The importer synthesizes UTC timestamps (`t0 + i / Hz`). Subject id is the session folder (or the nearest parent that is not `E4`). Nested trees such as PhysioNet `STRESS/S01/ACC.csv` are discovered automatically.

A headerless public copy of this layout: [Wearable Device Dataset from Induced Stress and Structured Exercise Sessions](https://physionet.org/content/wearable-device-dataset/) (also on [Kaggle](https://www.kaggle.com/datasets/protobioengineering/wearable-device-dataset-during-stress-and-exercise)).

### Headered research CSVs (Kaggle)

| Layout | Dataset | Headers the shape match uses |
|--------|---------|------------------------------|
| Merged channels plus a study label | [Nurse Stress Prediction Wearable Sensors](https://www.kaggle.com/datasets/priyankraval/nurse-stress-prediction-wearable-sensors) | `id`, `datetime`, `X`, `Y`, `Z`, `EDA`, `HR`, `TEMP` (`label` is kept on the table and is not a sensor value) |
| Per-signal files with a wearer id | Same study, split one channel per file | `id`, `datetime`, and `HR` / `EDA` / `TEMP` / `X,Y,Z` / `BVP` / `IBI` |
| Per-signal E4 files (no id column) | [GalaxyPPG](https://www.kaggle.com/datasets/mahdiesoltani/galaxyppg) | `timestamp`, `x`, `y`, `z` (and `hr`, `eda`, `temp`, `bvp`, `ibi`) |
| One merged 4 Hz file | [Pain prediction dataset Empatica E4](https://www.kaggle.com/datasets/omprakashyadav45/pain-prediction-dataset-emphatica-e4) | `person_ID`, `acc_x`, `acc_y`, `acc_z`, `eda`, `bvp`, `hr`, `temp`, `pain_scale` |

GalaxyPPG stores participants as folders (`P02/E4/ACC.csv`). When there is no id column the importer sets `subject_id` from the nearest parent folder that is not a device directory (`E4` is skipped, so `P02/E4/ACC.csv` → subject `P02`). A flat file uses its stem. GalaxyPPG `timestamp` values are Unix microseconds and are stored as `bigint`.

### Pain prediction merged CSV

Download `pain_dataset_200P_4hz.csv` from [that Kaggle page](https://www.kaggle.com/datasets/omprakashyadav45/pain-prediction-dataset-emphatica-e4) (do not copy it into git). Then:

```bash
w4h-data-recorder-csv-file-import plan --data-dir /path/to/folder-with-that-csv
w4h-data-recorder-csv-file-import import --dataset-id my-e4-pain --data-dir /path/to/folder-with-that-csv --mode append
```

Or pick the file in the notebook chooser. `person_ID` is the subject. The file has **no clock column**; the importer synthesizes `datetime` at **4 Hz** from row order (epoch + `i * 0.25s`) so GeoMTS has a time axis. Treat those timestamps as a sample index, not as the study’s wall clock. `pain_scale` is ingested as a value alongside the E4 channels.

## Who should do what

| Role | What to do |
|------|-----------|
| **Admin** | Ingest your CSVs into **your team's** catalog. Use the CLI (`import` / `sync`) for cron and incremental updates. |
| **User** | Use analysis contributions against loaded datasets. You cannot add datasets or edit raw tables. |
| **Super admin** | Catalog this repo after it is on a git remote. This package is not seeded into `w4h.contributions` until then. |

## How it works

1. **Files** — E4 Connect session folder, or one CSV per signal (or one merged file), UTF-8. The **notebook** has a file chooser. **In-app Run / `./run.sh` do not use the notebook** — they call the CLI and load the fixtures listed in [`contribution.yaml`](contribution.yaml).
2. **Plan** — profiles each CSV locally, builds a GeoMTS mapping in this package, runs the six deterministic checks, and writes `manifest.yaml` + `plan.json` when you pass `--data-dir`.
3. **Import** — streams rows in 500-row chunks to `POST /datasets/:id/import/csv-batch` with `table_prefix: "recorder"`. Progress is reported through `@@PROGRESS@@` lines.

`plan` sees `*.csv` in the top of `--data-dir` and nested E4 Connect files named `ACC.csv` / `BVP.csv` / `EDA.csv` / `HR.csv` / `TEMP.csv` / `IBI.csv`. For a GalaxyPPG tree of headered files, point it at one participant folder or pass files into the notebook chooser.

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
w4h-data-recorder-csv-file-import plan --data-dir /path/to/e4-session-or-csvs
export W4H_API_KEY=w4h_sk_...
w4h-data-recorder-csv-file-import import --dataset-id my-e4-data --data-dir /path/to/e4-session-or-csvs --mode append
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
