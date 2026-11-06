"""Known research data-recorder CSV layouts (Empatica E4).

The E4 is a wrist-worn physiological data recorder (ACC, BVP, EDA, HR, IBI,
temperature), not a consumer Fitbit export and not a glucose monitor.

Public samples — cite them, do not vendor the downloads:

- Merged channels (id, datetime, X, Y, Z, EDA, HR, TEMP, label), nurse stress:
  https://www.kaggle.com/datasets/priyankraval/nurse-stress-prediction-wearable-sensors
- Per-signal E4 files (timestamp + one channel, or x/y/z), GalaxyPPG:
  https://www.kaggle.com/datasets/mahdiesoltani/galaxyppg
- Merged 4 Hz channels (person_ID, acc_x/y/z, eda, bvp, hr, temp), pain prediction:
  https://www.kaggle.com/datasets/omprakashyadav45/pain-prediction-dataset-emphatica-e4
- Official E4 Connect ZIPs (no header: unix t0, then Hz, then samples) and the
  PhysioNet copy of that layout:
  https://www.empatica.com/blog/decoding-wearable-sensor-signals-what-to-expect-from-your-e4-data/
  https://physionet.org/content/wearable-device-dataset/
"""

import re

from .e4_connect import CHANNEL_STEMS, inspect_e4_connect

SHAPE_MIN_OVERLAP = 0.9

PREFERRED_COLUMNS: dict[str, str] = {
    "personid": "person_id",
    "accx": "acc_x",
    "accy": "acc_y",
    "accz": "acc_z",
    "painscale": "pain_scale",
}

SUBJECT_CANON = ("subjectid", "participantid", "personid", "id")

NOT_SUBJECT = {"index", "label"}

NOT_VALUES = {"label", "index"}

# Headered research CSVs. E4 Connect (headerless) is detected in e4_connect.py
# and does not go through matched_shape().
SHAPES: dict[str, dict] = {
    # Nurse-stress merge. Matched ahead of the narrower per-signal shapes
    # because the overlap count is larger.
    "e4_merged": {
        "columns": {"x", "y", "z", "eda", "hr", "temp", "id", "datetime"},
    },
    "e4_pain_merged": {
        "columns": {"personid", "accx", "accy", "accz", "eda", "bvp", "hr", "temp"},
        "inject_time_seconds": 0.25,
    },
    "recorder_acc": {"columns": {"id", "datetime", "x", "y", "z"}},
    "recorder_hr": {"columns": {"id", "datetime", "hr"}},
    "recorder_eda": {"columns": {"id", "datetime", "eda"}},
    "recorder_temp": {"columns": {"id", "datetime", "temp"}},
    "recorder_bvp": {"columns": {"id", "datetime", "bvp"}},
    "recorder_ibi": {"columns": {"id", "datetime", "ibi"}},
    # GalaxyPPG / E4 realtime header row: timestamp instead of id+datetime.
    "e4_acc": {"columns": {"timestamp", "x", "y", "z"}},
    "e4_hr": {"columns": {"timestamp", "hr"}},
    "e4_eda": {"columns": {"timestamp", "eda"}},
    "e4_temp": {"columns": {"timestamp", "temp"}},
    "e4_bvp": {"columns": {"timestamp", "bvp"}},
    "e4_ibi": {"columns": {"timestamp", "ibi"}},
}


def canonicalize_header(header: str) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(header or ""))
    return re.sub(r"[^a-z0-9]+", "", spaced.lower())


def matched_shape(headers: list[str]) -> str | None:
    """Highest column-overlap match at or above SHAPE_MIN_OVERLAP."""
    canon = {canonicalize_header(h) for h in headers}
    best = None
    best_n = 0
    for name, spec in SHAPES.items():
        cols = spec["columns"]
        n = len(cols & canon)
        if n / len(cols) < SHAPE_MIN_OVERLAP:
            continue
        hints = spec.get("any")
        if hints and not (hints & canon):
            continue
        if n > best_n:
            best, best_n = name, n
    return best


def keep_row(headers: list[str], cells: list[str]) -> bool:
    return bool(cells) and any(str(c).strip() for c in cells)


def discover_csv_files(data_dir) -> list:
    """Top-level ``*.csv`` plus nested E4 Connect channel files (ACC.csv, …)."""
    from pathlib import Path

    root = Path(data_dir)
    top = sorted(root.glob("*.csv"))
    seen = {p.resolve() for p in top}
    nested = []
    for path in sorted(root.rglob("*.csv")):
        resolved = path.resolve()
        if resolved in seen:
            continue
        if path.stem.lower() not in CHANNEL_STEMS:
            continue
        if inspect_e4_connect(path):
            nested.append(path)
            seen.add(resolved)
    return top + nested
