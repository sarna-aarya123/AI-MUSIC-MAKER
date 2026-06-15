"""
routes/generation.py
Blueprint: /api/generate

Implemented:
  POST /api/generate/chords       → 200 with progression data

Stubs (501) — implemented as services are built:
  POST /api/generate/melody
  POST /api/generate/drums
  POST /api/generate/composition

Request body for /chords (JSON):
  key          str   required   root note, e.g. "C", "F#", "Bb"
  mode         str   required   scale name or mood alias
  genre        str   optional   default "pop"
  bpm          int   optional   default 120
  bars         int   optional   default 4
  octave       int   optional   default 4
  with_seventh bool  optional   default null (use genre preference)
  spread       str   optional   "close" | "open" | "drop2"; default null
"""

from flask import Blueprint, jsonify, request

from backend.services.chord_service import generate_chord_progression

generation_bp = Blueprint("generation", __name__, url_prefix="/api/generate")


# ── Implemented ───────────────────────────────────────────────────────────────

@generation_bp.post("/chords")
def generate_chords():
    body = request.get_json(silent=True) or {}

    # Required fields
    missing = [f for f in ('key', 'mode') if not body.get(f)]
    if missing:
        return jsonify({
            'error': 'missing_fields',
            'missing': missing,
            'message': f"Required fields: {missing}",
        }), 400

    try:
        result = generate_chord_progression(
            key          = body['key'],
            mode         = body['mode'],
            genre        = body.get('genre', 'pop'),
            bpm          = int(body.get('bpm', 120)),
            bars         = int(body.get('bars', 4)),
            octave       = int(body.get('octave', 4)),
            with_seventh = body.get('with_seventh'),    # None → genre default
            spread       = body.get('spread'),          # None → genre default
        )
    except ValueError as exc:
        return jsonify({'error': 'invalid_input', 'message': str(exc)}), 400

    return jsonify(result), 200


# ── Stubs (501) ───────────────────────────────────────────────────────────────

def _stub(name: str):
    return jsonify({
        'status': 'not_implemented',
        'endpoint': name,
        'received': request.get_json(silent=True),
    }), 501


@generation_bp.post("/melody")
def generate_melody():
    return _stub("generate_melody")


@generation_bp.post("/drums")
def generate_drums():
    return _stub("generate_drums")
