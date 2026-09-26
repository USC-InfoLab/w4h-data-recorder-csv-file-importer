"""Integration test against a running w4h-api. Run: pytest -m integration -q

Needs W4H_API_KEY (and optionally W4H_API_BASE / W4H_DATASET_ID); skipped otherwise.
"""

import os

import pytest

from w4h_data_recorder_csv_file_importer.client import W4HClient


@pytest.mark.integration
def test_import_recorder_batch():
    if not os.environ.get("W4H_API_KEY", "").strip():
        pytest.skip("W4H_API_KEY not set")
    dataset_id = os.environ.get("W4H_DATASET_ID", "").strip()
    if not dataset_id:
        pytest.skip("W4H_DATASET_ID not set")
    result = W4HClient().import_csv_batch(
        dataset_id,
        {
            "signal": "hr_probe",
            "table_prefix": "recorder",
            "mode": "append",
            "dedupe_columns": ["id", "datetime"],
            "columns": [
                {"name": "id", "type": "text"},
                {"name": "datetime", "type": "timestamp"},
                {"name": "HR", "type": "integer"},
            ],
            "mapping": {
                "signal_type": "hr_probe",
                "subject": "id",
                "time": {"column": "datetime"},
                "values": [{"source": "HR", "name": "hr_bpm", "type": "integer"}],
            },
            "rows": [{"id": "R-TEST", "datetime": "2024-06-01T08:00:00", "HR": "72"}],
            "source_name": "Data recorder",
            "description": "integration test row",
        },
    )
    assert result.get("success") is True
