"""
routes/sound.py
Blueprint: /api/sound

Endpoints:
  POST /api/sound/generate   — JSON body { prompt, sound_type, duration_ms }
                               returns WAV file (application/octet-stream)
"""

from flask import Blueprint, jsonify, request

sound_bp = Blueprint("sound", __name__, url_prefix="/api/sound")


@sound_bp.post("/generate")
def generate_sound():
    return jsonify({
        "status": "not_implemented",
        "endpoint": "sound_generate",
        "received": request.get_json(silent=True),
    }), 501
