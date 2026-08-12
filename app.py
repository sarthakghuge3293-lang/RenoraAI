from dotenv import load_dotenv

load_dotenv(override=True)


from flask import Flask, redirect
from flask_cors import CORS
from config import Config
from models.user import db
from routes.auth import auth
from routes.project import project
from routes.chat import chat
from routes.admin import admin
from routes.setup import setup
from routes.user_pdf import user_pdf
from routes.pdf_ai import pdf_ai
from routes.mobile_api import mobile_api
from models.user_document import UserDocument
from models.chat_session import ChatSession
from models.chat_log import ChatLog
app = Flask(__name__)

# Load Configuration
app.config.from_object(Config)

# Enable CORS for Flutter mobile app (allow all origins in dev)
CORS(app, supports_credentials=True, resources={r"/mobile/*": {"origins": "*"}})

# Initialize Database
db.init_app(app)

# Register Blueprints
app.register_blueprint(auth)
app.register_blueprint(project)
app.register_blueprint(chat)
app.register_blueprint(admin)
app.register_blueprint(setup)

app.register_blueprint(user_pdf)
app.register_blueprint(pdf_ai)
app.register_blueprint(mobile_api)

# Default Route
@app.route("/")
def home():
    return redirect("/login")

@app.route("/force_setup_admin")
def force_setup_admin():
    from models.user import User
    from werkzeug.security import generate_password_hash
    email = "shivcoretech11@gmail.com"
    existing = User.query.filter_by(email=email).first()
    if existing:
        existing.password = generate_password_hash("Admin.123")
        existing.role = "super_admin"
        db.session.commit()
        return "Admin user updated successfully! Go to /admin/login"
    else:
        new_admin = User(
            name="Admin",
            email=email,
            password=generate_password_hash("Admin.123"),
            role="super_admin"
        )
        db.session.add(new_admin)
        db.session.commit()
        db.session.commit()
        return "Admin user created successfully! Go to /admin/login"

@app.route("/migrate")
def migrate_db():
    from sqlalchemy import text

    migrations = [
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS session_uuid VARCHAR(36);",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS active_source VARCHAR(50);",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS active_doc_id INTEGER;",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS active_doc_name VARCHAR(255);",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS is_shared BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS share_token VARCHAR(36);",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS source_used VARCHAR(255);",
    "ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS intent_detected VARCHAR(50);",
    "ALTER TABLE user_documents ADD COLUMN IF NOT EXISTS description TEXT;"
]
    results = []

    for q in migrations:
        try:
            db.session.execute(text(q))
            db.session.commit()
            results.append(f"SUCCESS: {q}")
        except Exception as e:
            db.session.rollback()
            results.append(
                f"FAILED (or already exists): {q} - ERROR: {str(e)}"
            )

    return {
        "status": "Migration completed",
        "details": results
    }

# Run Application
if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )