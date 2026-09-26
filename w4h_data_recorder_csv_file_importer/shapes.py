"""Known research data-recorder CSV layouts (Empatica E4).

The E4 is a wrist-worn physiological data recorder (ACC, BVP, EDA, HR, IBI,
temperature), not a consumer Fitbit export and not a glucose monitor.

Public Kaggle samples — cite them, do not vendor the downloads:

- Merged channels (id, datetime, X, Y, Z, EDA, HR, TEMP, label), nurse stress study:
  https://www.kaggle.com/datasets/priyankraval/nurse-stress-prediction-wearable-sensors
- Per-signal E4 files (timestamp + one channel, or x/y/z), GalaxyPPG:
  https://www.kaggle.com/datasets/mahdiesoltani/galaxyppg

Official E4 Connect downloads have no header row (unix time, then sample rate).
This importer expects a header row, which is how those Kaggle copies are published.
"""

import re

SHAPE_MIN_OVERLAP = 0.9

PREFERRED_COLUMNS: dict[str, str] = {}

SUBJECT_CANON = ("subjectid", "participantid", "id")

NOT_SUBJECT = {"index", "label"}

NOT_VALUES = {"label", "index"}

SHAPES: dict[str, dict] = {
    # Nurse-stress merge. Matched ahead of the narrower per-signal shapes
    # because the overlap count is larger.
    "e4_merged": {
        "columns": {"x", "y", "z", "eda", "hr", "temp", "id", "datetime"},
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
