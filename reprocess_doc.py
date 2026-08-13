import os
import sys

# Ensure the script can find local modules when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# flake8: noqa: E402
from flask import Flask
from config import Config
from models.user import db
from models.chat_log import ChatLog  # noqa: F401
from models.chat_session import ChatSession  # noqa: F401
from models.user_document import UserDocument
from routes.user_pdf import process_document_background

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


def reprocess_doc():
    with app.app_context():
        # Use db.session.get to fix SQLAlchemy 2.0 LegacyAPIWarning
        doc = db.session.get(UserDocument, 1)
        if not doc:
            print("Document ID 1 not found.")
            return

        print(f"Reprocessing document: {doc.file_name}")
        
        doc.status = "Processing"
        db.session.commit()
        
        process_document_background(
            app=app,
            pdf_path=doc.file_path,
            filename=doc.file_name,
            user_id=doc.user_id,
            collection_name=doc.collection_name,
            doc_id=doc.id
        )
        
        # Refresh the document from the database to see the updated status
        db.session.refresh(doc)
        print(f"Final status: {doc.status}")


if __name__ == "__main__":
    reprocess_doc()
