"""Data-recorder column descriptions. Fills empty fields only."""

from .shapes import canonicalize_header

TITLE = "Data recorder CSV import"
DESCRIPTION = (
    "Empatica E4 physiological data-recorder CSVs (merged or per signal). "
    "Review each signal before importing. Kaggle samples are cited in the README; "
    "this package does not ship those files."
)

_NURSE = "https://www.kaggle.com/datasets/priyankraval/nurse-stress-prediction-wearable-sensors"
_GALAXY = "https://www.kaggle.com/datasets/mahdiesoltani/galaxyppg"

_ACC_VALUES = {
    "x": {"name": "acc_x", "description": "Accelerometer X", "unit": "g"},
    "y": {"name": "acc_y", "description": "Accelerometer Y", "unit": "g"},
    "z": {"name": "acc_z", "description": "Accelerometer Z", "unit": "g"},
}
_HR_VALUES = {"hr": {"name": "hr_bpm", "description": "Heart rate", "unit": "bpm"}}
_EDA_VALUES = {"eda": {"name": "eda", "description": "Electrodermal activity", "unit": "µS"}}
_TEMP_VALUES = {"temp": {"name": "temp_c", "description": "Skin temperature", "unit": "°C"}}
_BVP_VALUES = {"bvp": {"name": "bvp", "description": "Blood volume pulse"}}
_IBI_VALUES = {"ibi": {"name": "ibi", "description": "Inter-beat interval", "unit": "s"}}

_COLUMNS = {
    "id": {"description": "Wearer or session id."},
    "subjectid": {"description": "Wearer id taken from the file path when the CSV has no id column."},
    "datetime": {"description": "Sample time."},
    "timestamp": {"description": "Sample time. GalaxyPPG E4 files use Unix microseconds."},
    "hr": {"description": "Heart rate.", "unit": "bpm"},
    "eda": {"description": "Electrodermal activity.", "unit": "µS"},
    "temp": {"description": "Skin temperature.", "unit": "°C"},
    "x": {"description": "Accelerometer X.", "unit": "g"},
    "y": {"description": "Accelerometer Y.", "unit": "g"},
    "z": {"description": "Accelerometer Z.", "unit": "g"},
    "bvp": {"description": "Blood volume pulse."},
    "ibi": {"description": "Inter-beat interval.", "unit": "s"},
    "label": {"description": "Study label on the merged nurse-stress export (not a sensor channel)."},
}


def _shape(description: str, url: str, values: dict, sampling_interval: str | None = None) -> dict:
    out = {
        "description": description,
        "source_url": url,
        "columns": _COLUMNS,
        "values": values,
    }
    if sampling_interval:
        out["sampling_interval"] = sampling_interval
    return out


SHAPES: dict[str, dict] = {
    "e4_merged": _shape(
        "Empatica E4 channels aligned in one CSV (X, Y, Z, EDA, HR, TEMP) plus a study label. "
        "Header from the Kaggle nurse-stress wearable merge.",
        _NURSE,
        {**_ACC_VALUES, **_EDA_VALUES, **_HR_VALUES, **_TEMP_VALUES},
    ),
    "recorder_acc": _shape(
        "Empatica E4 accelerometer with an id and datetime column (tidy split of the nurse-stress merge).",
        _NURSE,
        _ACC_VALUES,
        "32Hz",
    ),
    "recorder_hr": _shape(
        "Empatica E4 heart rate with an id and datetime column.",
        _NURSE,
        _HR_VALUES,
        "1s",
    ),
    "recorder_eda": _shape(
        "Empatica E4 electrodermal activity with an id and datetime column.",
        _NURSE,
        _EDA_VALUES,
        "4Hz",
    ),
    "recorder_temp": _shape(
        "Empatica E4 skin temperature with an id and datetime column.",
        _NURSE,
        _TEMP_VALUES,
        "4Hz",
    ),
    "recorder_bvp": _shape("Empatica E4 blood volume pulse with an id and datetime column.", _NURSE, _BVP_VALUES, "64Hz"),
    "recorder_ibi": _shape("Empatica E4 inter-beat interval with an id and datetime column.", _NURSE, _IBI_VALUES),
    "e4_acc": _shape("Empatica E4 accelerometer (GalaxyPPG header: timestamp, x, y, z).", _GALAXY, _ACC_VALUES, "32Hz"),
    "e4_hr": _shape("Empatica E4 heart rate (GalaxyPPG header: timestamp, hr).", _GALAXY, _HR_VALUES, "1s"),
    "e4_eda": _shape("Empatica E4 electrodermal activity (GalaxyPPG header: timestamp, eda).", _GALAXY, _EDA_VALUES, "4Hz"),
    "e4_temp": _shape("Empatica E4 skin temperature (GalaxyPPG header: timestamp, temp).", _GALAXY, _TEMP_VALUES, "4Hz"),
    "e4_bvp": _shape("Empatica E4 blood volume pulse (GalaxyPPG header: timestamp, bvp).", _GALAXY, _BVP_VALUES, "64Hz"),
    "e4_ibi": _shape("Empatica E4 inter-beat interval (GalaxyPPG header: timestamp, ibi).", _GALAXY, _IBI_VALUES),
}


def apply_catalog(manifest: dict) -> None:
    """Fill empty title/description/units from the catalog, in place."""
    if not manifest.get("title"):
        manifest["title"] = TITLE
    if not manifest.get("description"):
        manifest["description"] = DESCRIPTION
    for signal in manifest.get("signals", []):
        sdef = SHAPES.get(signal.get("matched_shape") or "") or {}
        for key in ("description", "source_url", "sampling_interval"):
            if not signal.get(key) and sdef.get(key):
                signal[key] = sdef[key]
        for col in signal.get("columns", []):
            canon = canonicalize_header(col["name"])
            meta = sdef.get("columns", {}).get(canon)
            if not meta:
                continue
            if not col.get("description") and meta.get("description"):
                col["description"] = meta["description"]
            if not col.get("unit") and meta.get("unit"):
                col["unit"] = meta["unit"]
        for v in signal.get("geomts_mapping", {}).get("values") or []:
            meta = sdef.get("values", {}).get(canonicalize_header(v["source"]))
            if not meta:
                continue
            if meta.get("name") and v.get("name") == v.get("source"):
                v["name"] = meta["name"]
            if not v.get("description") and meta.get("description"):
                v["description"] = meta["description"]
            if not v.get("unit") and meta.get("unit"):
                v["unit"] = meta["unit"]
