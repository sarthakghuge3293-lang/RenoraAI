import os
from flask import Blueprint, request, jsonify, render_template, session
from werkzeug.utils import secure_filename

from services.document_reader import DocumentReader
from services.chunker import TextChunker
from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore
from models.user import db
from models.user_document import UserDocument

user_pdf = Blueprint("user_pdf", __name__)

UPLOAD_FOLDER = "uploads/user_documents"

document_reader = DocumentReader()
chunker = TextChunker()
embedding_engine = EmbeddingEngine()


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

        # Check if document already exists to prevent duplicate processing
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

        # Read Document
        try:
            pages = document_reader.read_document(pdf_path, pdf.filename)
        except Exception as e:
            return jsonify(
                {"success": False, "message": f"Failed to read document: {str(e)}"}
            )

        # Create Chunks
        chunks = chunker.chunk_document(filename, pages)

        if not chunks:
            # Delete the empty/invalid pdf from disk to save space
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            return jsonify(
                {"success": False, "message": "No readable text found in PDF"}
            )

        # Create Embeddings
        embedded_chunks = embedding_engine.create_embeddings(chunks)

        # Store in User Collection
        collection_name = f"user_{user_id}"
        vector_store = VectorStore(collection_name)
        vector_store.add_chunks(embedded_chunks)

        # Extract document type
        ext = os.path.splitext(pdf.filename)[1].lower().replace(".", "")
        if not ext:
            ext = "unknown"

        # Save metadata to database
        new_doc = UserDocument(
            user_id=user_id,
            file_name=filename,
            original_name=pdf.filename,
            file_path=pdf_path,
            collection_name=collection_name,
            doc_type=ext,
            page_count=len(pages),
            status="ready",
        )
        db.session.add(new_doc)
        db.session.commit()

        # Save active collection in session (for backwards compatibility until Search logic update)
        session["active_collection"] = collection_name
        session["active_pdf"] = filename

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
                "uploaded_at": (
                    doc.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")
                    if doc.uploaded_at
                    else None
                ),
            }
        )

    return jsonify({"success": True, "documents": docs_data})


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

    # Delete from DB
    db.session.delete(doc)
    db.session.commit()

    # If this was the active document in session, remove it
    if session.get("active_pdf") == doc.file_name:
        session.pop("active_pdf", None)

    return jsonify({"success": True, "message": "Document deleted successfully"})


@user_pdf.route("/user/set-active-pdf", methods=["POST"])
def set_active_pdf():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json or {}
    pdf_name = data.get("pdf_name")

    if not pdf_name:
        # Search Across All PDFs (Clear active pdf)
        session.pop("active_pdf", None)
        # Keep active_collection as user_{user_id}
        session["active_collection"] = f"user_{user_id}"
        return jsonify(
            {
                "success": True,
                "message": "Set to Search Across All PDFs",
                "active_pdf": None,
            }
        )

    # Verify the document belongs to the user
    doc = UserDocument.query.filter_by(user_id=user_id, file_name=pdf_name).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    session["active_collection"] = doc.collection_name
    session["active_pdf"] = doc.file_name

    return jsonify(
        {
            "success": True,
            "message": f"Active PDF set to {pdf_name}",
            "active_pdf": pdf_name,
        }
    )


@user_pdf.route("/user/remove-pdf")
def remove_pdf():
    session.pop("active_collection", None)
    session.pop("active_pdf", None)

    return jsonify({"success": True})
