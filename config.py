import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Config:

    # Flask Secret Key
    SECRET_KEY = os.getenv("SECRET_KEY", "renvora_secret_key")

    # Database Configuration
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "renvora_ai")

    # SQLAlchemy
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Render's PostgreSQL URL might start with postgres:// instead of postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False