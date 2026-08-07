"""
routes/mobile_api.py
--------------------
REST API endpoints for the Renvora AI Flutter mobile app.
All endpoints return JSON. Authentication is session-cookie based.
"""

import os
from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models.user import db, User
from models.user_document import UserDocument
from services.document_reader import DocumentReader
from services.chunker import TextChunker
from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore
from services.gemini_service import generate_response
from models.chat_log import ChatLog

mobile_api = Blueprint("mobile_api", __name__, url_prefix="/mobile")

UPLOAD_FOLDER = "uploads/user_documents"

document_reader = DocumentReader()
chunker = TextChunker()
embedding_engine = EmbeddingEngine()

ALLOWED_EXTENSIONS = {"pdf", "xlsx", "csv", "docx", "pptx"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────


@mobile_api.route("/auth/login", methods=["POST"])
def api_login():
    """POST /mobile/auth/login  — body: {email, password}"""
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"success": False, "message": "Invalid email or password"}), 401

    session["user_id"] = user.id
    session["user_name"] = user.name
    session["user_email"] = user.email

    return jsonify(
        {
            "success": True,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
            },
        }
    )


@mobile_api.route("/auth/register", methods=["POST"])
def api_register():
    """POST /mobile/auth/register  — body: {name, email, password}"""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email already registered"}), 409

    hashed = generate_password_hash(password)
    user = User(name=name, email=email, password=hashed)
    db.session.add(user)
    db.session.commit()

    return jsonify({"success": True, "message": "Registration successful. Please login."})


@mobile_api.route("/auth/logout", methods=["POST"])
def api_logout():
    """POST /mobile/auth/logout"""
    session.clear()
    return jsonify({"success": True, "message": "Logged out"})


@mobile_api.route("/auth/me", methods=["GET"])
def api_me():
    """GET /mobile/auth/me — returns current logged-in user info"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    return jsonify(
        {
            "success": True,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
            },
        }
    )


# ─────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────


@mobile_api.route("/chat", methods=["POST"])
def api_chat():
    """POST /mobile/chat  — body: {message, collection?}"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"success": False, "message": "Message cannot be empty"}), 400

    collection = data.get("collection") or session.get("active_collection") or "renvora_knowledge_v2"
    result = generate_response(message, collection)

    # Save chat log
    try:
        log = ChatLog(
            user_id=user_id,
            message=message,
            response=result.get("response", ""),
            collection_used=collection,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print("Chat log error:", e)

    return jsonify(result)


# ─────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────


@mobile_api.route("/documents", methods=["GET"])
def api_get_documents():
    """GET /mobile/documents — list all documents for the current user"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    docs = (
        UserDocument.query.filter_by(user_id=user_id)
        .order_by(UserDocument.uploaded_at.desc())
        .all()
    )

    return jsonify(
        {
            "success": True,
            "documents": [
                {
                    "id": d.id,
                    "file_name": d.file_name,
                    "original_name": d.original_name,
                    "doc_type": d.doc_type,
                    "page_count": d.page_count,
                    "status": d.status,
                    "collection_name": d.collection_name,
                    "uploaded_at": (
                        d.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if d.uploaded_at else None
                    ),
                }
                for d in docs
            ],
        }
    )


@mobile_api.route("/documents/upload", methods=["POST"])
def api_upload_document():
    """POST /mobile/documents/upload  — multipart file field: 'file'"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": "Unsupported file type"}), 400

    filename = secure_filename(file.filename)

    # Duplicate check
    if UserDocument.query.filter_by(user_id=user_id, file_name=filename).first():
        return jsonify({"success": False, "message": "Document already uploaded"}), 409

    user_folder = os.path.join(UPLOAD_FOLDER, f"user_{user_id}")
    os.makedirs(user_folder, exist_ok=True)
    file_path = os.path.join(user_folder, filename)
    file.save(file_path)

    try:
        pages = document_reader.read_document(file_path, file.filename)
        chunks = chunker.chunk_document(filename, pages)

        if not chunks:
            os.remove(file_path)
            return jsonify({"success": False, "message": "No readable text found"}), 400

        embedded = embedding_engine.create_embeddings(chunks)
        collection_name = f"user_{user_id}"
        vs = VectorStore(collection_name)
        vs.add_chunks(embedded)

        ext = os.path.splitext(file.filename)[1].lower().replace(".", "") or "unknown"
        doc = UserDocument(
            user_id=user_id,
            file_name=filename,
            original_name=file.filename,
            file_path=file_path,
            collection_name=collection_name,
            doc_type=ext,
            page_count=len(pages),
            status="ready",
        )
        db.session.add(doc)
        db.session.commit()

        session["active_collection"] = collection_name
        session["active_pdf"] = filename

        return jsonify(
            {
                "success": True,
                "document": {
                    "id": doc.id,
                    "file_name": doc.file_name,
                    "doc_type": doc.doc_type,
                    "page_count": doc.page_count,
                    "collection_name": doc.collection_name,
                },
            }
        )
    except Exception as e:
        db.session.rollback()
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@mobile_api.route("/documents/<int:doc_id>", methods=["DELETE"])
def api_delete_document(doc_id):
    """DELETE /mobile/documents/<id>"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    try:
        vs = VectorStore(doc.collection_name)
        vs.delete_by_pdf_name(doc.file_name)
    except Exception as e:
        print("ChromaDB delete error:", e)

    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            print("File delete error:", e)

    db.session.delete(doc)
    db.session.commit()

    if session.get("active_pdf") == doc.file_name:
        session.pop("active_pdf", None)

    return jsonify({"success": True, "message": "Document deleted"})


@mobile_api.route("/documents/<int:doc_id>/rename", methods=["POST"])
def api_rename_document(doc_id):
    """POST /mobile/documents/<id>/rename — body: {new_name}"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    new_name = data.get("new_name")
    if not new_name:
        return jsonify({"success": False, "message": "New name is required"}), 400

    doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    doc.original_name = new_name
    db.session.commit()

    return jsonify({"success": True, "message": "Document renamed successfully"})


@mobile_api.route("/documents/set-active", methods=["POST"])
def api_set_active():
    """POST /mobile/documents/set-active  — body: {collection_name}"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    collection = data.get("collection_name")

    if collection:
        session["active_collection"] = collection
    else:
        session["active_collection"] = f"user_{user_id}"
        session.pop("active_pdf", None)

    return jsonify({"success": True, "active_collection": session["active_collection"]})
