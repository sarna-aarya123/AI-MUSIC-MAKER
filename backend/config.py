"""
config.py
Application configuration loaded from environment variables.
Reads a .env file if present (python-dotenv).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/)
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")


class Config:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DEBUG: bool = os.getenv("FLASK_ENV", "development") == "development"

    # Max MP3 upload size in bytes
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024

    # Temporary directory for MIDI/WAV exports
    EXPORT_DIR: Path = Path(os.getenv("EXPORT_DIR", str(_root / "exports")))

    # Optional AI sound-generation model
    SOUND_MODEL_API_KEY: str = os.getenv("SOUND_MODEL_API_KEY", "")
    SOUND_MODEL_API_URL: str = os.getenv("SOUND_MODEL_API_URL", "")

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
