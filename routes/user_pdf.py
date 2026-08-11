import os
from flask import Blueprint, request, jsonify, render_template, session
from werkzeug.utils import secure_filename

from services.document_reader import DocumentReader
from services.chunker import TextChunker
from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore
from models.user import db
from models.user_document import UserDocument
from models.chat_session import ChatSession

user_pdf = Blueprint("user_pdf", __name__)

UPLOAD_FOLDER = "uploads/user_documents"

document_reader = DocumentReader()
chunker = TextChunker()
embedding_engine = EmbeddingEngine()


import threading

def process_document_background(app, pdf_path, filename, user_id, collection_name, doc_id):
    with app.app_context():
        try:
            pages = document_reader.read_document(pdf_path, filename)
            chunks = chunker.chunk_document(filename, pages)
            
            if not chunks:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                doc = UserDocument.query.get(doc_id)
                if doc:
                    doc.status = "Failed: No text found"
                    db.session.commit()
                return

            embedded_chunks = embedding_engine.create_embeddings(chunks)
            vector_store = VectorStore(collection_name)
            vector_store.add_chunks(embedded_chunks)

            doc = UserDocument.query.get(doc_id)
            if doc:
                doc.status = "ready"
                doc.page_count = len(pages)
                db.session.commit()
                
        except Exception as e:
            print("Background Processing Error:", e)
            doc = UserDocument.query.get(doc_id)
            if doc:
                doc.status = f"Failed: {str(e)[:50]}"
                db.session.commit()

from flask import current_app

@user_pdf.route("/user/upload", methods=["GET", "POST"])
def upload_pdf():

    if request.method == "GET":
        return render_template("upload_pdf.html")

    try:
        pdf = request.files.get("pdf")

        if not pdf:
            return jsonify({"success": False, "message": "No PDF Selected"})

        filename = secure_filename(pdf.filename)
        if not filename:
            return jsonify({"success": False, "message": "Invalid PDF filename"})

        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"success": False, "message": "User not logged in"}), 401

        existing_doc = UserDocument.query.filter_by(
            user_id=user_id, file_name=filename
        ).first()
        if existing_doc:
            return jsonify(
                {"success": False, "message": "Document with this name already exists"}
            )

        user_folder = os.path.join(UPLOAD_FOLDER, f"user_{user_id}")
        os.makedirs(user_folder, exist_ok=True)

        pdf_path = os.path.join(user_folder, filename)

        pdf.save(pdf_path)

        collection_name = f"user_{user_id}_v2"
        ext = os.path.splitext(pdf.filename)[1].lower().replace(".", "")
        if not ext:
            ext = "unknown"

        # Save metadata to database with Processing status
        new_doc = UserDocument(
            user_id=user_id,
            file_name=filename,
            original_name=pdf.filename,
            file_path=pdf_path,
            collection_name=collection_name,
            doc_type=ext,
            page_count=0,
            status="Processing",
        )
        db.session.add(new_doc)
        db.session.commit()

        # Start background thread
        app = current_app._get_current_object()
        thread = threading.Thread(
            target=process_document_background, 
            args=(app, pdf_path, filename, user_id, collection_name, new_doc.id)
        )
        thread.daemon = True
        thread.start()

        # session["active_collection"] = collection_name # no longer needed
        # session["active_pdf"] = filename # no longer needed

        return jsonify({"success": True, "pdf": filename})
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@user_pdf.route("/user/documents", methods=["GET"])
def get_user_documents():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    documents = (
        UserDocument.query.filter_by(user_id=user_id)
        .order_by(UserDocument.uploaded_at.desc())
        .all()
    )

    docs_data = []
    for doc in documents:
        docs_data.append(
            {
                "id": doc.id,
                "original_name": doc.original_name,
                "file_name": doc.file_name,
                "doc_type": doc.doc_type,
                "status": doc.status,
                "uploaded_at": (
                    doc.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")
                    if doc.uploaded_at
                    else None
                ),
            }
        )

    return jsonify({"success": True, "documents": docs_data})

@user_pdf.route("/user/documents/<int:doc_id>/status", methods=["GET"])
def get_document_status(doc_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False}), 401
    doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"success": False}), 404
    return jsonify({"success": True, "status": doc.status})

@user_pdf.route("/user/documents/<int:doc_id>/rename", methods=["POST"])
def rename_document(doc_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json or {}
    new_name = data.get("new_name")
    if not new_name:
        return jsonify({"success": False, "message": "New name is required"}), 400

    doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    # Just changing the display name, keep internal file_name same to not break vector db
    doc.original_name = new_name
    db.session.commit()

    return jsonify({"success": True, "message": "Document renamed successfully"})


@user_pdf.route("/user/documents/<int:doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    # Delete from Vector Store
    try:
        vector_store = VectorStore(doc.collection_name)
        vector_store.delete_by_pdf_name(doc.file_name)
    except Exception as e:
        print("Error deleting from ChromaDB:", e)

    # Delete physical file
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            print("Error deleting file:", e)

    # Clear any active chat sessions that have locked this document
    sessions_to_clear = ChatSession.query.filter_by(active_doc_name=doc.file_name).all()
    for s in sessions_to_clear:
        s.active_source = "renvora_knowledge"
        s.active_doc_name = None
        s.active_doc_id = None
    
    # Delete from DB
    db.session.delete(doc)
    db.session.commit()

    return jsonify({"success": True, "message": "Document deleted successfully"})
