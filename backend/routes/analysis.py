"""
routes/analysis.py
Blueprint: /api/analysis

Endpoints:
  POST /api/analysis/detect   — multipart MP3 upload
                                returns { key, mode, bpm, confidence }
"""

from flask import Blueprint, jsonify, request

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api/analysis")


@analysis_bp.post("/detect")
def detect():
    return jsonify({
        "status": "not_implemented",
        "endpoint": "analysis_detect",
        "file_received": bool(request.files.get("file")),
    }), 501
