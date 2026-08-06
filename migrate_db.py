from app import app
from models.user import db

def migrate():
    with app.app_context():
        with db.engine.begin() as conn:
            try:
                # Add columns if they don't exist
                conn.execute(db.text("ALTER TABLE user_documents ADD COLUMN doc_type VARCHAR(10) NOT NULL DEFAULT 'pdf';"))
                print("Added doc_type column.")
            except Exception as e:
                print(f"doc_type column might already exist: {e}")

            try:
                conn.execute(db.text("ALTER TABLE user_documents ADD COLUMN page_count INT DEFAULT 0;"))
                print("Added page_count column.")
            except Exception as e:
                print(f"page_count column might already exist: {e}")

            try:
                conn.execute(db.text("ALTER TABLE user_documents ADD COLUMN status VARCHAR(50) DEFAULT 'ready';"))
                print("Added status column.")
            except Exception as e:
                print(f"status column might already exist: {e}")

if __name__ == "__main__":
    migrate()
