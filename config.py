import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    # ============================================================
    # Flask
    # ============================================================

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "renvora-dev-secret-change-this"
    )

    # ============================================================
    # Database
    # ============================================================

    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Add DATABASE_URL to your .env file."
        )

    # Render / PostgreSQL compatibility
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1,
        )

    SQLALCHEMY_DATABASE_URI = DATABASE_URL

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ============================================================
    # Uploads
    # ============================================================

    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        "uploads/user_documents"
    )

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    # 10 MB per uploaded file

    # ============================================================
    # AI / API Keys
    # ============================================================

    GROQ_API_KEY = os.getenv(
        "GROQ_API_KEY"
    )

    QDRANT_URL = os.getenv(
        "QDRANT_URL"
    )

    QDRANT_API_KEY = os.getenv(
        "QDRANT_API_KEY"
    )

    # ============================================================
    # Session
    # ============================================================

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # HTTPS production me Flask/Render ke saath True kar sakte ho.
    SESSION_COOKIE_SECURE = os.getenv(
        "SESSION_COOKIE_SECURE",
        "false"
    ).lower() == "true"