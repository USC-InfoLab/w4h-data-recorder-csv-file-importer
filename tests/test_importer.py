"""Unit tests for profiling, mapping, reconciliation and chunked import — no network."""

import json
import shutil
from pathlib import Path

import pytest

from w4h_data_recorder_csv_file_importer.__main__ import main
from w4h_data_recorder_csv_file_importer.csv_import import CHUNK_SIZE, import_all, import_signal
from w4h_data_recorder_csv_file_importer.manifest import load_manifest
from w4h_data_recorder_csv_file_importer.e4_connect import inspect_e4_connect, iso_utc
from w4h_data_recorder_csv_file_importer.mapping import plan_directory, plan_files
from w4h_data_recorder_csv_file_importer.profile import infer_type
from w4h_data_recorder_csv_file_importer.reconcile import reconcile_manifest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    def __init__(self):
        self.imports = []

    def import_csv_batch(self, dataset_id, payload):
        self.imports.append((dataset_id, payload))
        n = len(payload["rows"])
        return {"inserted": n, "skipped": 0, "physical_schema": "ds_t", "physical_table": payload["signal"]}


@pytest.fixture
def data_dir(tmp_path):
    for f in FIXTURES.glob("*.csv"):
        shutil.copy(f, tmp_path / f.name)
    return tmp_path


def _signal(manifest, slug):
    return next(s for s in manifest["signals"] if s["slug"] == slug)


def test_infer_type():
    assert infer_type(["72", "74"]) == "integer"
    assert infer_type(["0.21", "0.24"]) == "double precision"
    assert infer_type(["2024-06-01T08:00:00"]) == "timestamp"
    assert infer_type(["1717228800000000"]) == "bigint"


def test_plan_maps_e4_shapes(data_dir):
    manifest = plan_directory(data_dir)
    assert manifest["vendor"] == "data_recorder"
    hr = _signal(manifest, "hr")
    assert hr["matched_shape"] == "recorder_hr"
    assert hr["sampling_interval"] == "1s"
    assert hr["geomts_mapping"]["subject"] == "id"
    assert hr["geomts_mapping"]["time"] == {"column": "datetime"}
    assert hr["geomts_mapping"]["values"][0]["name"] == "hr_bpm"
    assert "kaggle.com/datasets/priyankraval" in hr["source_url"]

    acc = _signal(manifest, "acc")
    assert acc["matched_shape"] == "recorder_acc"
    assert [v["name"] for v in acc["geomts_mapping"]["values"]] == ["acc_x", "acc_y", "acc_z"]

    merged = _signal(manifest, "merged_physiology")
    assert merged["matched_shape"] == "e4_merged"
    assert [v["name"] for v in merged["geomts_mapping"]["values"]] == [
        "acc_x", "acc_y", "acc_z", "eda", "hr_bpm", "temp_c",
    ]
    assert "label" not in [v["source"] for v in merged["geomts_mapping"]["values"]]


def test_plan_output_needs_no_corrections(data_dir):
    review = reconcile_manifest(plan_directory(data_dir))
    assert review["errors"] == [] and review["corrections"] == []


def test_e4_connect_inspects_headerless_files():
    folder = FIXTURES / "e4_connect"
    acc = inspect_e4_connect(folder / "ACC.csv")
    assert acc["kind"] == "acc" and acc["hz"] == 32.0
    ibi = inspect_e4_connect(folder / "IBI.csv")
    assert ibi["kind"] == "ibi" and ibi["hz"] is None
    assert inspect_e4_connect(FIXTURES / "hr.csv") is None


def test_plan_e4_connect_session_folder(tmp_path):
    session = tmp_path / "1517933194_A01F11"
    session.mkdir()
    for name in ("ACC.csv", "HR.csv", "EDA.csv", "IBI.csv"):
        shutil.copy(FIXTURES / "e4_connect" / name, session / name)
    manifest = plan_directory(session)
    review = reconcile_manifest(manifest)
    assert review["errors"] == []
    slugs = {s["slug"]: s for s in manifest["signals"]}
    assert slugs["acc"]["matched_shape"] == "e4_connect_acc"
    assert slugs["acc"]["sampling_interval"] == "32Hz"
    assert slugs["acc"]["geomts_mapping"]["time"] == {"column": "timestamp"}
    assert slugs["ibi"]["matched_shape"] == "e4_connect_ibi"
    client = FakeClient()
    import_signal(client, "ds", slugs["acc"], session)
    row = client.imports[0][1]["rows"][0]
    assert row["subject_id"] == "1517933194_A01F11"
    assert row["x"] == "27"
    assert row["timestamp"] == iso_utc(1380399004.0)
    assert client.imports[0][1]["table_prefix"] == "recorder"
    ibi_client = FakeClient()
    import_signal(ibi_client, "ds", slugs["ibi"], session)
    ibi_row = ibi_client.imports[0][1]["rows"][0]
    assert ibi_row["ibi"] == "0.875000"
    assert ibi_row["timestamp"] == iso_utc(1381290418.0 + 7.734375)


def test_plan_nested_physionet_style_connect(tmp_path):
    path = tmp_path / "STRESS" / "S01" / "ACC.csv"
    path.parent.mkdir(parents=True)
    shutil.copy(FIXTURES / "e4_connect" / "ACC.csv", path)
    manifest = plan_directory(tmp_path)
    sig = manifest["signals"][0]
    assert sig["file"] == "STRESS/S01/ACC.csv"
    assert sig["matched_shape"] == "e4_connect_acc"
    client = FakeClient()
    import_signal(client, "ds", sig, tmp_path)
    assert client.imports[0][1]["rows"][0]["subject_id"] == "S01"


def test_pain_prediction_merged_csv_synthesizes_time():
    path = FIXTURES / "pain" / "pain_dataset.csv"
    manifest = plan_files([path])
    sig = manifest["signals"][0]
    assert sig["matched_shape"] == "e4_pain_merged"
    assert sig["time_from_row"] is True
    assert sig["sampling_interval"] == "4Hz"
    assert sig["geomts_mapping"]["subject"] == "person_id"
    names = [v["name"] for v in sig["geomts_mapping"]["values"]]
    assert names == ["acc_x", "acc_y", "acc_z", "eda", "bvp", "hr_bpm", "temp_c", "pain_scale"]
    assert reconcile_manifest(manifest)["errors"] == []
    client = FakeClient()
    import_signal(client, "ds", sig, path.parent, csv_path=path)
    rows = client.imports[0][1]["rows"]
    assert rows[0]["person_id"] == "P1"
    assert rows[0]["datetime"] == iso_utc(0.0)
    assert rows[1]["datetime"] == iso_utc(0.25)
    assert rows[2]["person_id"] == "P2"


def test_galaxy_ppg_header_uses_parent_folder_as_subject(tmp_path):
    path = tmp_path / "P02" / "E4" / "ACC.csv"
    path.parent.mkdir(parents=True)
    path.write_text("timestamp,x,y,z\n1717228800000000,10,-2,64\n")
    manifest = plan_files([path])
    sig = manifest["signals"][0]
    assert sig["matched_shape"] == "e4_acc"
    assert sig["subject_from_file"] is True
    assert sig["geomts_mapping"]["time"] == {"column": "timestamp"}
    assert "kaggle.com/datasets/mahdiesoltani/galaxyppg" in sig["source_url"]
    client = FakeClient()
    import_signal(client, "ds", sig, tmp_path, csv_path=path)
    row = client.imports[0][1]["rows"][0]
    assert row["subject_id"] == "P02"
    assert row["x"] == "10"
    assert client.imports[0][1]["table_prefix"] == "recorder"


def test_reconcile_requires_a_subject():
    manifest = {"vendor": "data_recorder", "signals": [{"slug": "x", "file": "x.csv",
                "columns": [{"name": "a", "type": "text"}],
                "geomts_mapping": {"subject": None, "time": None, "values": []}}]}
    assert any("subject is required" in e for e in reconcile_manifest(manifest)["errors"])


def test_plan_command_writes_manifest(data_dir):
    assert main(["plan", "--data-dir", str(data_dir)]) == 0
    manifest = load_manifest(data_dir)
    assert manifest["vendor"] == "data_recorder"
    assert {s["slug"] for s in manifest["signals"]} == {"hr", "eda", "temp", "acc", "merged_physiology"}


def test_import_chunks_prefix(tmp_path):
    n = CHUNK_SIZE * 2 + 1
    body = "\n".join(f"R-01,2024-06-01T08:00:{i % 60:02d},{60 + (i % 5)}" for i in range(n))
    (tmp_path / "hr.csv").write_text("id,datetime,HR\n" + body + "\n")
    client = FakeClient()
    signal = {
        "slug": "hr",
        "file": "hr.csv",
        "columns": [],
        "dedupe_columns": ["id"],
        "sampling_interval": "1s",
        "geomts_mapping": {"subject": "id"},
    }
    result = import_signal(client, "ds", signal, tmp_path, mode="replace")
    assert [p["mode"] for _, p in client.imports] == ["replace", "append", "append"]
    assert all(p["table_prefix"] == "recorder" for _, p in client.imports)
    assert result["inserted"] == n


def test_import_progress_marker(tmp_path, capsys):
    (tmp_path / "a.csv").write_text("id,datetime,HR\nR-01,2024-06-01T08:00:00,72\n")
    signal = {"slug": "a", "file": "a.csv", "columns": [], "geomts_mapping": {}}
    import_all(FakeClient(), "ds", {"signals": [signal]}, tmp_path)
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("@@PROGRESS@@ "))
    progress = json.loads(line.split(" ", 1)[1])
    assert progress["signal"] == "a" and progress["rows_total"] == 1


def test_validate_command(data_dir):
    assert main(["plan", "--data-dir", str(data_dir)]) == 0
    manifest = load_manifest(data_dir)
    _signal(manifest, "hr")["geomts_mapping"]["subject"] = "nope"
    from w4h_data_recorder_csv_file_importer.manifest import write_manifest
    write_manifest(data_dir, manifest)
    assert main(["validate", "--data-dir", str(data_dir)]) == 1
