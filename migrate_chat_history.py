from app import app
from models.user import db
from sqlalchemy import text

def migrate():
    with app.app_context():
        # Create chat_sessions table if it doesn't exist (db.create_all handles this)
        db.create_all()

        try:
            # Add session_id to chat_logs
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE chat_logs ADD COLUMN session_id INTEGER"))
                conn.execute(text("ALTER TABLE chat_logs ADD CONSTRAINT fk_chat_session FOREIGN KEY (session_id) REFERENCES chat_sessions(id)"))
            print("Migration complete. Added session_id to chat_logs.")
        except Exception as e:
            if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                print("Column session_id already exists.")
            else:
                print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
