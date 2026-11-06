"""Empatica E4 Connect CSV layout (no header row).

E4 Connect ZIPs ship one file per channel. Row 1 is the session start (unix
seconds UTC, sometimes repeated once per axis). Row 2 is the firmware sample
rate in Hz. Remaining rows are samples. IBI is the exception: row 1 is
``t0, IBI`` and each later row is ``seconds_from_t0, ibi``.

Documented by Empatica:
https://www.empatica.com/blog/decoding-wearable-sensor-signals-what-to-expect-from-your-e4-data/

PhysioNet's stress/exercise dump uses the same files (optionally with t0 as UTC
text instead of unix seconds).
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

CHANNEL_STEMS = ("acc", "bvp", "eda", "hr", "temp", "ibi")

_CHANNELS: dict[str, dict] = {
    "acc": {
        "headers": ["timestamp", "x", "y", "z"],
        "types": ["timestamp", "integer", "integer", "integer"],
        "shape": "e4_connect_acc",
        "n_values": 3,
        "expected_hz": 32.0,
    },
    "bvp": {
        "headers": ["timestamp", "bvp"],
        "types": ["timestamp", "double precision"],
        "shape": "e4_connect_bvp",
        "n_values": 1,
        "expected_hz": 64.0,
    },
    "eda": {
        "headers": ["timestamp", "eda"],
        "types": ["timestamp", "double precision"],
        "shape": "e4_connect_eda",
        "n_values": 1,
        "expected_hz": 4.0,
    },
    "hr": {
        "headers": ["timestamp", "hr"],
        "types": ["timestamp", "double precision"],
        "shape": "e4_connect_hr",
        "n_values": 1,
        "expected_hz": 1.0,
    },
    "temp": {
        "headers": ["timestamp", "temp"],
        "types": ["timestamp", "double precision"],
        "shape": "e4_connect_temp",
        "n_values": 1,
        "expected_hz": 4.0,
    },
    "ibi": {
        "headers": ["timestamp", "ibi"],
        "types": ["timestamp", "double precision"],
        "shape": "e4_connect_ibi",
        "n_values": 2,
        "expected_hz": None,
    },
}


def iso_utc(epoch_seconds: float) -> str:
    """Wall-clock UTC text. Sub-second channels need fractional seconds."""
    dt = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _cell(row: list[str], i: int = 0) -> str:
    return row[i].strip() if i < len(row) else ""


def _filled(row: list[str]) -> list[str]:
    return [c.strip() for c in row if str(c).strip() != ""]


def parse_t0(cell: str) -> float | None:
    s = (cell or "").strip()
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        v = None
    if v is not None and 1e8 < v < 4e9:
        return v
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ):
        try:
            dt = datetime.strptime(s.replace("+00:00", "Z"), fmt)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return None


def _is_hz(cell: str) -> bool:
    try:
        v = float(cell)
    except (TypeError, ValueError):
        return False
    return 0.5 <= v <= 256.0


def _is_ibi_preamble(row: list[str]) -> bool:
    cells = _filled(row)
    if len(cells) < 2:
        return False
    return parse_t0(cells[0]) is not None and cells[1].upper() == "IBI"


def _read_preamble(path: Path) -> tuple[str, list[list[str]]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        first = f.readline()
        delimiter = "," if first.count(",") >= first.count("\t") else "\t"
        if first.count(";") > first.count(delimiter):
            delimiter = ";"
        f.seek(0)
        reader = csv.reader(f, delimiter=delimiter)
        rows = [next(reader, []) for _ in range(3)]
    return delimiter, rows


def inspect_e4_connect(path: Path) -> dict | None:
    """Return channel metadata if ``path`` is an E4 Connect CSV, else None."""
    path = Path(path)
    try:
        delimiter, rows = _read_preamble(path)
    except (OSError, csv.Error, UnicodeDecodeError):
        return None
    row0, row1, row2 = rows[0], rows[1], rows[2]
    stem = path.stem.lower()

    if _is_ibi_preamble(row0):
        spec = _CHANNELS["ibi"]
        t0 = parse_t0(_filled(row0)[0])
        if t0 is None:
            return None
        return {
            "kind": "ibi",
            "delimiter": delimiter,
            "t0": t0,
            "hz": None,
            "headers": spec["headers"],
            "types": spec["types"],
            "shape": spec["shape"],
        }

    if stem not in _CHANNELS or stem == "ibi":
        cells0 = _filled(row0)
        # Unnamed 3-axis file at 32 Hz is still ACC.
        if (
            len(cells0) == 3
            and all(parse_t0(c) is not None for c in cells0)
            and len(_filled(row1)) == 3
            and all(_is_hz(c) for c in _filled(row1))
            and abs(float(_filled(row1)[0]) - 32.0) < 0.01
        ):
            stem = "acc"
        else:
            return None

    spec = _CHANNELS[stem]
    t0 = parse_t0(_cell(row0, 0))
    if t0 is None:
        return None
    hz_cells = _filled(row1)
    if not hz_cells or not all(_is_hz(c) for c in hz_cells):
        return None
    hz = float(hz_cells[0])
    n = spec["n_values"]
    data = _filled(row2)
    if data and len(data) < n:
        return None
    return {
        "kind": stem,
        "delimiter": delimiter,
        "t0": t0,
        "hz": hz,
        "headers": spec["headers"],
        "types": spec["types"],
        "shape": spec["shape"],
    }


def iter_e4_connect_rows(
    path: Path,
    meta: dict,
    chunk_size: int,
    fill: dict | None = None,
) -> Iterator[list[dict]]:
    fill = fill or {}
    kind = meta["kind"]
    t0 = float(meta["t0"])
    delimiter = meta.get("delimiter") or ","
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        preamble = next(reader, None)
        if preamble is None:
            return
        if kind != "ibi":
            next(reader, None)
        chunk: list[dict] = []
        i = 0
        for cells in reader:
            values = [c.strip() for c in cells]
            if not any(values):
                continue
            if kind == "ibi":
                if len(values) < 2:
                    continue
                try:
                    offset = float(values[0])
                except ValueError:
                    continue
                row = {"timestamp": iso_utc(t0 + offset), "ibi": values[1]}
            elif kind == "acc":
                if len(values) < 3:
                    continue
                hz = float(meta["hz"])
                row = {
                    "timestamp": iso_utc(t0 + i / hz),
                    "x": values[0],
                    "y": values[1],
                    "z": values[2],
                }
                i += 1
            else:
                hz = float(meta["hz"])
                value_key = kind  # bvp / eda / hr / temp
                row = {
                    "timestamp": iso_utc(t0 + i / hz),
                    value_key: values[0],
                }
                i += 1
            for key, value in fill.items():
                if not str(row.get(key, "")).strip():
                    row[key] = value
            chunk.append(row)
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk


def count_e4_connect_rows(path: Path, meta: dict) -> int:
    delimiter = meta.get("delimiter") or ","
    kind = meta["kind"]
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        next(reader, None)
        if kind != "ibi":
            next(reader, None)
        n = 0
        for cells in reader:
            if any(str(c).strip() for c in cells):
                n += 1
        return n
