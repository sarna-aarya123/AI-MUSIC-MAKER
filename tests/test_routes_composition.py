"""
tests/test_routes_composition.py

Integration tests for POST /api/generate/composition.
Uses Flask's test client — exercises the full request/response cycle
without starting a real HTTP server.
"""

from __future__ import annotations

import base64
import json

import pytest

from backend.app import create_app


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def valid_body():
    return {"key": "C", "mode": "major", "genre": "pop", "bpm": 120, "bars": 4, "seed": 42}


def post(client, body):
    """Helper: POST JSON to the composition endpoint."""
    return client.post(
        "/api/generate/composition",
        data=json.dumps(body),
        content_type="application/json",
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def decode_midi(b64_str: str) -> bytes:
    return base64.b64decode(b64_str)


# ═══════════════════════════════════════════════════════════════════════════════
# Happy path — status and top-level structure
# ═══════════════════════════════════════════════════════════════════════════════

def test_200_on_valid_body(client, valid_body):
    rv = post(client, valid_body)
    assert rv.status_code == 200

def test_content_type_is_json(client, valid_body):
    rv = post(client, valid_body)
    assert rv.content_type.startswith("application/json")

def test_response_has_all_required_keys(client, valid_body):
    rv = post(client, valid_body)
    data = rv.get_json()
    required = {
        "key", "mode", "scale", "genre", "bpm", "bars",
        "time_signature", "ppq", "total_beats",
        "parts", "tracks",
        "chord_data", "melody_data", "drum_data",
        "summary", "midi",
    }
    assert required <= data.keys()

def test_ppq_is_480(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["ppq"] == 480

def test_total_beats_correct(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["total_beats"] == valid_body["bars"] * 4.0

def test_default_parts_all_three(client, valid_body):
    data = post(client, valid_body).get_json()
    assert set(data["parts"]) == {"chords", "melody", "drums"}

def test_tracks_keys_match_parts(client, valid_body):
    data = post(client, valid_body).get_json()
    assert set(data["tracks"].keys()) == set(data["parts"])


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata passthrough
# ═══════════════════════════════════════════════════════════════════════════════

def test_key_echoed(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["key"] == valid_body["key"]

def test_mode_echoed(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["mode"] == valid_body["mode"]

def test_genre_echoed(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["genre"] == valid_body["genre"]

def test_bpm_echoed(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["bpm"] == valid_body["bpm"]

def test_bars_echoed(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["bars"] == valid_body["bars"]


# ═══════════════════════════════════════════════════════════════════════════════
# MIDI field
# ═══════════════════════════════════════════════════════════════════════════════

def test_midi_field_is_string(client, valid_body):
    data = post(client, valid_body).get_json()
    assert isinstance(data["midi"], str)

def test_midi_is_valid_base64(client, valid_body):
    data = post(client, valid_body).get_json()
    raw = decode_midi(data["midi"])
    assert isinstance(raw, bytes)

def test_midi_decodes_to_mthd(client, valid_body):
    data = post(client, valid_body).get_json()
    raw = decode_midi(data["midi"])
    assert raw[:4] == bytes.fromhex("4d546864")

def test_midi_contains_drum_channel(client, valid_body):
    data = post(client, valid_body).get_json()
    raw = decode_midi(data["midi"])
    assert b"\x99" in raw   # note-on on channel 9


# ═══════════════════════════════════════════════════════════════════════════════
# chord_data / melody_data / drum_data shapes
# ═══════════════════════════════════════════════════════════════════════════════

def test_chord_data_has_chords(client, valid_body):
    data = post(client, valid_body).get_json()
    assert "chords" in data["chord_data"]
    assert len(data["chord_data"]["chords"]) > 0

def test_melody_data_has_notes(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["melody_data"] is not None
    assert "notes" in data["melody_data"]
    assert len(data["melody_data"]["notes"]) > 0

def test_drum_data_has_events(client, valid_body):
    data = post(client, valid_body).get_json()
    assert data["drum_data"] is not None
    assert "events" in data["drum_data"]
    assert len(data["drum_data"]["events"]) > 0

def test_summary_has_note_count(client, valid_body):
    data = post(client, valid_body).get_json()
    assert "note_count" in data["summary"]
    assert data["summary"]["note_count"] > 0

def test_summary_tracks_list(client, valid_body):
    data = post(client, valid_body).get_json()
    assert isinstance(data["summary"]["tracks"], list)
    assert len(data["summary"]["tracks"]) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 400 — missing required fields
# ═══════════════════════════════════════════════════════════════════════════════

def test_400_missing_key(client):
    rv = post(client, {"mode": "major"})
    assert rv.status_code == 400

def test_400_missing_mode(client):
    rv = post(client, {"key": "C"})
    assert rv.status_code == 400

def test_400_missing_both(client):
    rv = post(client, {})
    assert rv.status_code == 400

def test_400_error_field_missing_fields(client):
    data = post(client, {}).get_json()
    assert data["error"] == "missing_fields"

def test_400_missing_list_contains_key(client):
    data = post(client, {"mode": "major"}).get_json()
    assert "key" in data["missing"]

def test_400_missing_list_contains_mode(client):
    data = post(client, {"key": "C"}).get_json()
    assert "mode" in data["missing"]

def test_400_message_field_present(client):
    data = post(client, {}).get_json()
    assert "message" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 400 — invalid parameter values
# ═══════════════════════════════════════════════════════════════════════════════

def test_400_invalid_bpm(client):
    rv = post(client, {"key": "C", "mode": "major", "bpm": "fast"})
    assert rv.status_code == 400

def test_400_invalid_bars(client):
    rv = post(client, {"key": "C", "mode": "major", "bars": "lots"})
    assert rv.status_code == 400

def test_400_invalid_key(client):
    rv = post(client, {"key": "Z#", "mode": "major"})
    assert rv.status_code == 400

def test_400_invalid_input_error_field(client):
    data = post(client, {"key": "C", "mode": "major", "bpm": "fast"}).get_json()
    assert data["error"] == "invalid_input"

def test_400_empty_body(client):
    rv = client.post("/api/generate/composition", data="", content_type="application/json")
    assert rv.status_code == 400

def test_400_non_json_body(client):
    rv = client.post(
        "/api/generate/composition",
        data="key=C&mode=major",
        content_type="application/x-www-form-urlencoded",
    )
    assert rv.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Parts filtering
# ═══════════════════════════════════════════════════════════════════════════════

def test_parts_chords_only(client):
    body = {"key": "C", "mode": "major", "seed": 0, "parts": ["chords"]}
    data = post(client, body).get_json()
    assert data["parts"] == ["chords"]
    assert data["melody_data"] is None
    assert data["drum_data"] is None

def test_parts_chords_melody(client):
    body = {"key": "C", "mode": "major", "seed": 0, "parts": ["chords", "melody"]}
    data = post(client, body).get_json()
    assert "melody" in data["parts"]
    assert "drums"  not in data["parts"]
    assert data["drum_data"] is None
    assert data["melody_data"] is not None

def test_parts_no_drums_no_channel_9(client):
    body = {"key": "C", "mode": "major", "seed": 0, "parts": ["chords", "melody"]}
    data = post(client, body).get_json()
    raw = decode_midi(data["midi"])
    assert b"\x99" not in raw

def test_parts_all_three_explicit(client):
    body = {"key": "C", "mode": "major", "seed": 0, "parts": ["chords", "melody", "drums"]}
    data = post(client, body).get_json()
    assert set(data["parts"]) == {"chords", "melody", "drums"}


# ═══════════════════════════════════════════════════════════════════════════════
# Optional parameters
# ═══════════════════════════════════════════════════════════════════════════════

def test_custom_bpm(client):
    data = post(client, {"key": "G", "mode": "major", "bpm": 90, "seed": 0}).get_json()
    assert data["bpm"] == 90

def test_custom_bars(client):
    data = post(client, {"key": "G", "mode": "major", "bars": 8, "seed": 0}).get_json()
    assert data["bars"] == 8
    assert data["total_beats"] == 32.0

def test_custom_genre(client):
    data = post(client, {"key": "D", "mode": "minor", "genre": "jazz", "seed": 0}).get_json()
    assert data["genre"] == "jazz"

def test_density_param(client):
    full  = post(client, {"key": "C", "mode": "major", "density": 1.0, "seed": 42}).get_json()
    spare = post(client, {"key": "C", "mode": "major", "density": 0.0, "seed": 42}).get_json()
    assert (len(full["melody_data"]["notes"])
            >= len(spare["melody_data"]["notes"]))

def test_variation_bars_zero(client):
    data = post(client, {"key": "C", "mode": "major", "seed": 42, "variation_bars": 0}).get_json()
    snare_beats = {ev["beat"] for ev in data["drum_data"]["events"] if ev["drum_type"] == "snare"}
    assert 15.25 not in snare_beats

def test_seed_param_deterministic(client):
    body = {"key": "C", "mode": "major", "seed": 77}
    d1 = post(client, body).get_json()
    d2 = post(client, body).get_json()
    assert d1["midi"] == d2["midi"]


# ═══════════════════════════════════════════════════════════════════════════════
# Genre parametrisation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("genre", ["pop", "hip-hop", "jazz", "lo-fi", "edm"])
def test_all_genres_200(client, genre):
    rv = post(client, {"key": "A", "mode": "minor", "genre": genre, "seed": 0})
    assert rv.status_code == 200

@pytest.mark.parametrize("genre", ["pop", "hip-hop", "jazz", "lo-fi", "edm"])
def test_all_genres_valid_midi(client, genre):
    data = post(client, {"key": "A", "mode": "minor", "genre": genre, "seed": 0}).get_json()
    assert decode_midi(data["midi"])[:4] == bytes.fromhex("4d546864")


# ═══════════════════════════════════════════════════════════════════════════════
# Regression — other endpoints unaffected
# ═══════════════════════════════════════════════════════════════════════════════

def test_health_check_still_works(client):
    rv = client.get("/api/health")
    assert rv.status_code == 200
    assert rv.get_json()["status"] == "ok"

def test_chords_endpoint_still_works(client):
    rv = client.post(
        "/api/generate/chords",
        data=json.dumps({"key": "C", "mode": "major"}),
        content_type="application/json",
    )
    assert rv.status_code == 200

def test_get_returns_error(client):
    # The app has a catch-all GET handler for static files so GET to an API
    # route yields 404 (file not found) rather than 405 (method not allowed).
    rv = client.get("/api/generate/composition")
    assert rv.status_code in (404, 405)
