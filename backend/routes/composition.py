"""
backend/routes/composition.py
Blueprint: POST /api/generate/composition

Thin orchestration layer — validates input, delegates entirely to:
  chord_service.generate_chord_progression()  → chord_data
  composition_service.compose()               → unified result

No music-theory logic lives here.  All domain decisions are in the services.

Request body (JSON):
  key              str    required   root note, e.g. "C", "F#", "Bb"
  mode             str    required   scale name or mood alias
  genre            str    optional   default "pop"
  bpm              int    optional   default 120
  bars             int    optional   default 4
  octave           int    optional   default 4    chord voicing register
  melody_octave    int    optional   default 5    melody register (one above chords)
  density          float  optional   default 0.75 melody note density
  chord_instrument str    optional   default "piano"
  melody_instrument str   optional   default "piano"
  variation_bars   int    optional   default 4    drum fill frequency in bars
  seed             int    optional   set for reproducible output
  with_seventh     bool   optional   include 7th chords (null = genre default)
  spread           str    optional   "close"|"open"|"drop2" (null = genre default)
  parts            list   optional   subset of ["chords","melody","drums"]
                                     omit to include all three

Response 200 (JSON):
  key, mode, scale, genre, bpm, bars, time_signature
  ppq:          480
  total_beats:  float
  parts:        list of included part names
  tracks:       { "chords": 0, "melody": 1, "drums": 2 }
  chord_data:   full chord_service output
  melody_data:  melody_service output, or null if excluded
  drum_data:    drum_service output, or null if excluded
  summary:      { bpm, ppq, tracks, note_count, program_changes }
  midi:         base64-encoded Standard MIDI File bytes

Response 400:
  missing_fields — key or mode absent
  invalid_input  — bad parameter values (ValueError from services)
"""

from __future__ import annotations

import base64

from flask import Blueprint, jsonify, request

from backend.services.chord_service import generate_chord_progression
from backend.services.composition_service import compose

composition_bp = Blueprint("composition", __name__, url_prefix="/api/generate")


@composition_bp.post("/composition")
def generate_composition():
    body = request.get_json(silent=True) or {}

    # ── Validate required fields ───────────────────────────────────────────────
    missing = [f for f in ("key", "mode") if not body.get(f)]
    if missing:
        return jsonify({
            "error":   "missing_fields",
            "missing": missing,
            "message": f"Required field(s) missing: {missing}",
        }), 400

    try:
        # ── Parse optional numeric params (catch bad types early) ──────────────
        bpm            = int(body.get("bpm", 120))
        bars           = int(body.get("bars", 4))
        octave         = int(body.get("octave", 4))
        melody_octave  = int(body.get("melody_octave", 5))
        density        = float(body.get("density", 0.75))
        variation_bars = int(body.get("variation_bars", 4))
        seed_raw       = body.get("seed")
        seed           = int(seed_raw) if seed_raw is not None else None

        # ── Step 1: Generate chord progression ────────────────────────────────
        chord_data = generate_chord_progression(
            key          = body["key"],
            mode         = body["mode"],
            genre        = body.get("genre", "pop"),
            bpm          = bpm,
            bars         = bars,
            octave       = octave,
            with_seventh = body.get("with_seventh"),   # None → genre default
            spread       = body.get("spread"),          # None → genre default
        )

        # ── Step 2: Resolve which parts to include ────────────────────────────
        requested = body.get("parts")   # None means include everything
        include_melody = requested is None or "melody" in requested
        include_drums  = requested is None or "drums"  in requested

        # ── Step 3: Compose (orchestration delegated entirely to service) ─────
        result = compose(
            chord_data,
            melody_octave       = melody_octave,
            melody_density      = density,
            chord_instrument    = body.get("chord_instrument", "piano"),
            melody_instrument   = body.get("melody_instrument", "piano"),
            drum_variation_bars = variation_bars,
            seed                = seed,
            include_melody      = include_melody,
            include_drums       = include_drums,
        )

    except (ValueError, TypeError) as exc:
        return jsonify({"error": "invalid_input", "message": str(exc)}), 400

    # ── Build response — base64-encode raw MIDI bytes ─────────────────────────
    return jsonify({
        "key":            result["key"],
        "mode":           result["mode"],
        "scale":          result["scale"],
        "genre":          result["genre"],
        "bpm":            result["bpm"],
        "bars":           result["bars"],
        "time_signature": result["time_signature"],
        "ppq":            result["ppq"],
        "total_beats":    result["total_beats"],
        "parts":          result["parts"],
        "tracks":         result["tracks"],
        "chord_data":     result["chord_data"],
        "melody_data":    result["melody_data"],
        "drum_data":      result["drum_data"],
        "summary":        result["summary"],
        "midi":           base64.b64encode(result["midi_bytes"]).decode("ascii"),
    }), 200
