"""
app.py
Flask application factory and entry point.

Usage:
  python backend/app.py              (development server)
  flask --app backend.app run        (Flask CLI)
"""

from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from backend.config import Config
from backend.routes.generation import generation_bp
from backend.routes.analysis import analysis_bp
from backend.routes.similarity import similarity_bp
from backend.routes.sound import sound_bp

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)

    # ── Configuration ────────────────────────────────────────────────────────
    app.secret_key = Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
    Config.ensure_dirs()

    # ── CORS (allow all origins in dev; tighten for production) ──────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ── Blueprints ───────────────────────────────────────────────────────────
    app.register_blueprint(generation_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(similarity_bp)
    app.register_blueprint(sound_bp)

    # ── Health check ─────────────────────────────────────────────────────────
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "music-maker"})

    # ── Frontend static files (development convenience) ───────────────────────
    @app.get("/")
    def index():
        return send_from_directory(_FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(_FRONTEND_DIR, filename)

    # ── JSON error handlers ───────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": str(e)}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "file_too_large", "max_mb": Config.MAX_CONTENT_LENGTH // (1024 * 1024)}), 413

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "internal_server_error", "message": str(e)}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=Config.DEBUG)
