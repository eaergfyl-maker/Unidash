import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import timetable_parser


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        timetable_parser, "settings",
        replace(timetable_parser.settings, gemini_api_key=None),
    )
    with TestClient(app) as test_client:
        yield test_client


def test_parse_valid_notice(client):
    response = client.post(
        "/api/timetable/parse",
        json={"text": "Tue, 17-Nov-2026 | 1:30 pm - 3:30 pm"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["source"] == "regex"
    assert len(result["slots"]) == 1
    slot = result["slots"][0]
    assert (slot["day"], slot["date"], slot["start"], slot["end"]) == (
        "Tue", "17-Nov-2026", "13:30", "15:30"
    )


def test_parse_unrecognised_notice(client):
    response = client.post(
        "/api/timetable/parse",
        json={"text": "Class details will be announced later."},
    )

    assert response.status_code == 200
    assert response.json()["slots"] == []
    assert response.json()["break_window"] is None


def test_import_rejects_executable(client):
    response = client.post(
        "/api/timetable/import",
        files={"file": ("timetable.exe", b"MZ", "application/octet-stream")},
    )

    assert response.status_code == 415


def test_import_rejects_file_over_five_mib(client):
    content = b"%PDF-" + b"x" * (5 * 1024 * 1024)
    response = client.post(
        "/api/timetable/import",
        files={"file": ("timetable.pdf", content, "application/pdf")},
    )

    assert response.status_code == 413


def test_break_window_subtracts_walking_buffer():
    window = timetable_parser.compute_break_window(
        next_class_start="13:30",
        previous_class_end="13:00",
        walk_buffer=7,
    )

    assert window.break_minutes == 30
    assert window.walk_buffer_minutes == 7
    assert window.max_prep_minutes == 23


def test_parse_uses_gemini_when_regex_misses(client, monkeypatch):
    monkeypatch.setattr(
        timetable_parser, "settings",
        replace(timetable_parser.settings, gemini_api_key="fake-key-for-test"),
    )
    expected = {
        "day": "Thu",
        "date": "19-Nov-2026",
        "start": "14:00",
        "end": "16:00",
        "label": None,
        "room": "Lab 4",
    }

    with patch("google.genai.Client") as gemini_client:
        generate = gemini_client.return_value.models.generate_content
        generate.return_value = SimpleNamespace(text=json.dumps([expected]))

        response = client.post(
            "/api/timetable/parse",
            json={
                "text": "Class moved to Thursday, 19 November 2026, "
                        "from two in the afternoon until four, in Lab 4."
            },
        )

    assert response.status_code == 200
    assert response.json()["source"] == "gemini"
    assert response.json()["slots"] == [expected]
    generate.assert_called_once()
