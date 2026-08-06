from app import app
from models.user import db
from models.ai_settings import AISettings
from models.chat_log import ChatLog
import traceback

def migrate():
    with app.app_context():
        print("Creating new tables...")
        # create_all will create tables that don't exist yet
        db.create_all()
        
        # Seed default AISettings if none exist
        if not AISettings.query.first():
            print("Seeding default AI Settings...")
            default_settings = AISettings(
                llm_model="llama3-8b-8192",
                embedding_model="BAAI/bge-small-en-v1.5",
                chunk_size=1000,
                chunk_overlap=200,
                top_k=5,
                max_upload_size_mb=50,
                supported_file_types="pdf,xlsx,csv,docx,pptx"
            )
            db.session.add(default_settings)
            db.session.commit()
            print("Default settings added successfully.")
        else:
            print("AI Settings already exist.")
            
        print("Migration complete!")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        traceback.print_exc()
