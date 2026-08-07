import os
from sqlalchemy import text

os.environ['GEMINI_API_KEY'] = 'dummy'
from app import db, app

queries = [
    "ALTER TABLE chat_logs ADD COLUMN source_used VARCHAR(50);",
    "ALTER TABLE chat_logs ADD COLUMN intent_detected VARCHAR(50);",
    "ALTER TABLE user_documents ADD COLUMN description TEXT;",
]

with app.app_context():
    for q in queries:
        try:
            db.session.execute(text(q))
            db.session.commit()
            print(f"Executed: {q}")
        except Exception as e:
            db.session.rollback()
            print(f"Skipped/Error for {q}: {e}")

print("Migration completed.")
