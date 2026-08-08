from app import app
from models.user import db

# Ensure database tables are created before starting the server
# Useful for Render deployments
with app.app_context():
    db.create_all()

    # Auto-migrate Cloud Database (PostgreSQL) if using old tables
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE chat_sessions ADD COLUMN session_uuid VARCHAR(36);",
        "ALTER TABLE chat_sessions ADD COLUMN active_source VARCHAR(50);",
        "ALTER TABLE chat_sessions ADD COLUMN active_doc_id INTEGER;",
        "ALTER TABLE chat_sessions ADD COLUMN active_doc_name VARCHAR(255);",
        "ALTER TABLE chat_sessions ADD COLUMN is_shared BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE chat_sessions ADD COLUMN share_token VARCHAR(36);",
        "ALTER TABLE chat_logs ADD COLUMN source_used VARCHAR(255);",
        "ALTER TABLE chat_logs ADD COLUMN intent_detected VARCHAR(50);",
        "ALTER TABLE user_documents ADD COLUMN description TEXT;"
    ]
    for q in migrations:
        try:
            db.session.execute(text(q))
            db.session.commit()
            print(f"Migrated: {q}")
        except Exception as e:
            db.session.rollback()
            # Ignore errors if column already exists

if __name__ == "__main__":
    app.run()
