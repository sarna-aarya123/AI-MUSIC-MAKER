"""
routes/similarity.py
Blueprint: /api/similarity

Endpoints:
  POST /api/similarity/generate  — multipart MP3 upload
                                   returns a new MIDI file inspired by the upload
"""

from flask import Blueprint, jsonify, request

similarity_bp = Blueprint("similarity", __name__, url_prefix="/api/similarity")


@similarity_bp.post("/generate")
def generate_similar():
    return jsonify({
        "status": "not_implemented",
        "endpoint": "similarity_generate",
        "file_received": bool(request.files.get("file")),
    }), 501
