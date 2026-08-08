"""
routes/mobile_api.py
────────────────────
REST API endpoints for the Renvora AI Flutter mobile app.

Changes from v1:
- Chat endpoint now: loads conversation history from DB, passes to AI engine,
  saves source_used + intent, updates session state in DB (not in Flask cookie)
- Full session CRUD: list, create, get history, delete, select-source, share
- Search: search messages across all sessions
- Document permanence: always derived from DB (not Flask session cookie)
"""

import os
import uuid
import threading

from flask import Blueprint, request, jsonify, session, render_template
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models.user import db, User
from models.user_document import UserDocument
from models.chat_session import ChatSession
from models.chat_log import ChatLog
from services.document_reader import DocumentReader
from services.chunker import TextChunker
from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore
from services.ai_engine import ai_engine

mobile_api = Blueprint("mobile_api", __name__, url_prefix="/mobile")

UPLOAD_FOLDER = "uploads/user_documents"
ALLOWED_EXTENSIONS = {"pdf", "xlsx", "csv", "docx", "pptx", "txt"}

document_reader = DocumentReader()
chunker = TextChunker()
embedding_engine = EmbeddingEngine()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _require_auth():
    """Returns (user_id, error_response). If error_response is not None, return it."""
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"success": False, "message": "Unauthorized"}), 401)
    return user_id, None


def _build_chat_history(session_id: int, limit: int = 10) -> list:
    """Build alternating user/assistant history list from ChatLog rows."""
    logs = (
        ChatLog.query.filter_by(session_id=session_id)
        .order_by(ChatLog.timestamp.asc())
        .limit(limit)
        .all()
    )
    history = []
    for log in logs:
        history.append({"role": "user", "content": log.message})
        history.append({"role": "assistant", "content": log.response})
    return history


def _get_or_create_session(user_id: int, session_uuid: str) -> ChatSession:
    """Get existing session by UUID or create a new one."""
    chat_session = ChatSession.query.filter_by(
        user_id=user_id, session_uuid=session_uuid
    ).first()
    if not chat_session:
        chat_session = ChatSession(
            user_id=user_id,
            session_uuid=session_uuid,
            title="New Chat",
        )
        db.session.add(chat_session)
        db.session.commit()
    return chat_session


def _auto_title(message: str, max_len: int = 50) -> str:
    """Create a short title from the first user message."""
    title = message.strip()
    if len(title) > max_len:
        title = title[:max_len].rsplit(" ", 1)[0] + "…"
    return title or "New Chat"


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────


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

    # Load user's documents on login so Flutter knows what's available
    docs = UserDocument.query.filter_by(user_id=user.id).order_by(
        UserDocument.uploaded_at.desc()
    ).all()

    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
        "documents": [d.to_dict() for d in docs],
    })


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

    user = User(name=name, email=email, password=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()

    return jsonify({"success": True, "message": "Registration successful. Please login."})


@mobile_api.route("/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out"})


@mobile_api.route("/auth/me", methods=["GET"])
def api_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    docs = UserDocument.query.filter_by(user_id=user_id).order_by(
        UserDocument.uploaded_at.desc()
    ).all()

    return jsonify({
        "success": True,
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
        "documents": [d.to_dict() for d in docs],
    })


# ─────────────────────────────────────────────────────────────────────────────
# CHAT SESSIONS
# ─────────────────────────────────────────────────────────────────────────────


@mobile_api.route("/sessions", methods=["GET"])
def api_list_sessions():
    """GET /mobile/sessions — list all chat sessions for this user, most recent first."""
    user_id, err = _require_auth()
    if err:
        return err

    sessions_list = (
        ChatSession.query.filter_by(user_id=user_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    result = []
    for s in sessions_list:
        # Get last message for preview
        last_log = (
            ChatLog.query.filter_by(session_id=s.id)
            .order_by(ChatLog.timestamp.desc())
            .first()
        )
        result.append({
            "id": s.id,
            "session_uuid": s.session_uuid,
            "title": s.title or "New Chat",
            "active_source": s.active_source,
            "active_doc_name": s.active_doc_name,
            "is_shared": s.is_shared,
            "share_token": s.share_token if s.is_shared else None,
            "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else None,
            "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M:%S") if s.updated_at else None,
            "last_message": last_log.message[:80] if last_log else "",
            "last_response": last_log.response[:80] if last_log else "",
        })

    return jsonify({"success": True, "sessions": result})


@mobile_api.route("/sessions", methods=["POST"])
def api_create_session():
    """POST /mobile/sessions — body: {session_uuid?} — create a new session."""
    user_id, err = _require_auth()
    if err:
        return err

    data = request.get_json() or {}
    session_uuid = data.get("session_uuid") or str(uuid.uuid4())

    # Avoid duplicates
    existing = ChatSession.query.filter_by(user_id=user_id, session_uuid=session_uuid).first()
    if existing:
        return jsonify({
            "success": True,
            "session": {
                "id": existing.id,
                "session_uuid": existing.session_uuid,
                "title": existing.title,
            }
        })

    new_session = ChatSession(
        user_id=user_id,
        session_uuid=session_uuid,
        title="New Chat",
    )
    db.session.add(new_session)
    db.session.commit()

    return jsonify({
        "success": True,
        "session": {
            "id": new_session.id,
            "session_uuid": new_session.session_uuid,
            "title": new_session.title,
        }
    }), 201


@mobile_api.route("/sessions/<int:session_id>", methods=["GET"])
def api_get_session(session_id):
    """GET /mobile/sessions/<id> — get full chat history for a session."""
    user_id, err = _require_auth()
    if err:
        return err

    chat_session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not chat_session:
        return jsonify({"success": False, "message": "Session not found"}), 404

    logs = (
        ChatLog.query.filter_by(session_id=session_id)
        .order_by(ChatLog.timestamp.asc())
        .all()
    )

    return jsonify({
        "success": True,
        "session": {
            "id": chat_session.id,
            "session_uuid": chat_session.session_uuid,
            "title": chat_session.title,
            "active_source": chat_session.active_source,
            "active_doc_name": chat_session.active_doc_name,
            "is_shared": chat_session.is_shared,
        },
        "messages": [log.to_dict() for log in logs],
    })


@mobile_api.route("/sessions/<int:session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    """DELETE /mobile/sessions/<id> — delete session and all its messages."""
    user_id, err = _require_auth()
    if err:
        return err

    chat_session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not chat_session:
        return jsonify({"success": False, "message": "Session not found"}), 404

    db.session.delete(chat_session)
    db.session.commit()
    return jsonify({"success": True, "message": "Session deleted"})


@mobile_api.route("/sessions/<int:session_id>/select-source", methods=["POST"])
def api_select_source(session_id):
    """
    POST /mobile/sessions/<id>/select-source
    body: {source: "renvora_knowledge"|"uploaded_document"|"general_ai", doc_id?: int}
    Locks the source for the rest of this session.
    """
    user_id, err = _require_auth()
    if err:
        return err

    chat_session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not chat_session:
        return jsonify({"success": False, "message": "Session not found"}), 404

    data = request.get_json() or {}
    source = data.get("source")
    doc_id = data.get("doc_id")

    valid_sources = {"renvora_knowledge", "uploaded_document", "general_ai"}
    if source not in valid_sources:
        return jsonify({"success": False, "message": f"Invalid source. Use: {valid_sources}"}), 400

    chat_session.active_source = source

    if source == "uploaded_document" and doc_id:
        doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
        if doc:
            chat_session.active_doc_id = doc.id
            chat_session.active_doc_name = doc.file_name
        else:
            return jsonify({"success": False, "message": "Document not found"}), 404
    else:
        chat_session.active_doc_id = None
        chat_session.active_doc_name = None

    db.session.commit()

    return jsonify({
        "success": True,
        "active_source": chat_session.active_source,
        "active_doc_name": chat_session.active_doc_name,
    })


@mobile_api.route("/sessions/<int:session_id>/share", methods=["POST"])
def api_share_session(session_id):
    """POST /mobile/sessions/<id>/share — generate a shareable link."""
    user_id, err = _require_auth()
    if err:
        return err

    chat_session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not chat_session:
        return jsonify({"success": False, "message": "Session not found"}), 404

    if not chat_session.share_token:
        chat_session.generate_share_token()
        db.session.commit()

    base_url = request.host_url.rstrip("/")
    share_url = f"{base_url}/mobile/shared/{chat_session.share_token}"

    return jsonify({
        "success": True,
        "share_token": chat_session.share_token,
        "share_url": share_url,
    })


@mobile_api.route("/shared/<share_token>", methods=["GET"])
def api_view_shared(share_token):
    """GET /mobile/shared/<token> — public, read-only view of a shared chat."""
    chat_session = ChatSession.query.filter_by(
        share_token=share_token, is_shared=True
    ).first()
    if not chat_session:
        return jsonify({"success": False, "message": "Shared chat not found"}), 404

    logs = (
        ChatLog.query.filter_by(session_id=chat_session.id)
        .order_by(ChatLog.timestamp.asc())
        .all()
    )

    return jsonify({
        "success": True,
        "session_title": chat_session.title,
        "messages": [
            {
                "role": "user",
                "content": log.message,
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else None,
            } if idx % 2 == 0 else {
                "role": "assistant",
                "content": log.response,
                "source_used": log.source_used,
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else None,
            }
            for idx, log in enumerate(logs)
        ],
    })


@mobile_api.route("/sessions/search", methods=["GET"])
def api_search_sessions():
    """
    GET /mobile/sessions/search?q=keyword
    Searches through all messages and responses in this user's sessions.
    """
    user_id, err = _require_auth()
    if err:
        return err

    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify({"success": False, "message": "Search query too short"}), 400

    # Get all session IDs for this user
    user_session_ids = [
        s.id for s in ChatSession.query.filter_by(user_id=user_id).all()
    ]
    if not user_session_ids:
        return jsonify({"success": True, "results": []})

    # Search in messages and responses
    search_term = f"%{query}%"
    matching_logs = (
        ChatLog.query.filter(
            ChatLog.session_id.in_(user_session_ids),
            db.or_(
                ChatLog.message.ilike(search_term),
                ChatLog.response.ilike(search_term),
            )
        )
        .order_by(ChatLog.timestamp.desc())
        .limit(30)
        .all()
    )

    results = []
    seen_sessions = {}
    for log in matching_logs:
        chat_session = seen_sessions.get(log.session_id)
        if not chat_session:
            chat_session = ChatSession.query.get(log.session_id)
            seen_sessions[log.session_id] = chat_session

        results.append({
            "session_id": log.session_id,
            "session_uuid": chat_session.session_uuid if chat_session else None,
            "session_title": chat_session.title if chat_session else "Chat",
            "message": log.message,
            "response": log.response[:200],
            "source_used": log.source_used,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else None,
        })

    return jsonify({"success": True, "results": results, "count": len(results)})


# ─────────────────────────────────────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────────────────────────────────────


@mobile_api.route("/chat", methods=["POST"])
def api_chat():
    """
    POST /mobile/chat
    body: {
        message: str,
        session_uuid: str,   # Flutter-generated UUID for this conversation
        source_override?: str  # "renvora_knowledge" | "uploaded_document" | "general_ai"
        doc_id?: int           # if source_override == "uploaded_document"
    }
    """
    user_id, err = _require_auth()
    if err:
        return err

    try:
        data = request.get_json() or {}
        message = data.get("message", "").strip()

        if not message:
            return jsonify({"success": False, "message": "Message cannot be empty"}), 400

        # Resolve or create session
        session_uuid = data.get("session_uuid") or str(uuid.uuid4())
        chat_session = _get_or_create_session(user_id, session_uuid)

        # Handle source override (user tapped a clarification option)
        source_override = data.get("source_override")
        doc_id_override = data.get("doc_id")
        if source_override:
            valid_sources = {"renvora_knowledge", "uploaded_document", "general_ai"}
            if source_override in valid_sources:
                chat_session.active_source = source_override
                if source_override == "uploaded_document" and doc_id_override:
                    doc = UserDocument.query.filter_by(
                        id=doc_id_override, user_id=user_id
                    ).first()
                    if doc:
                        chat_session.active_doc_id = doc.id
                        chat_session.active_doc_name = doc.file_name
                db.session.commit()

        # Build conversation history from DB
        chat_history = _build_chat_history(chat_session.id, limit=10)

        # Get user's ready documents (permanent memory — no re-upload needed)
        user_documents = [
            d.to_dict()
            for d in UserDocument.query.filter_by(user_id=user_id).all()
            if d.status == "ready"
        ]

        print(f"[MobileAPI] Chat: user={user_id}, session={chat_session.id}, "
              f"docs={len(user_documents)}, locked_source={chat_session.active_source}")

        # ── Run the AI pipeline ──────────────────────────────────────────────────
        result = ai_engine.generate_response(
            user_message=message,
            user_id=user_id,
            chat_history=chat_history,
            locked_source=chat_session.active_source,
            locked_doc_name=chat_session.active_doc_name,
            user_documents=user_documents,
        )

        reply         = result.get("reply", "")
        intent        = result.get("intent", "general_knowledge")
        source_used   = result.get("source_used", "General AI Knowledge")
        lock_source   = result.get("lock_source")
        lock_doc_name = result.get("lock_doc_name")
        needs_clarif  = result.get("needs_clarification", False)
        suggested     = result.get("suggested_sources", [])

        print(f"[MobileAPI] AI replied: intent={intent}, source={source_used}, "
              f"reply_len={len(reply)}, needs_clarif={needs_clarif}")

        # Update session source lock (only if AI determined a clear source)
        if lock_source and not needs_clarif:
            if not chat_session.active_source:  # Don't override existing lock
                chat_session.active_source = lock_source
                chat_session.active_doc_name = lock_doc_name

        # Auto-title on first message
        if chat_session.title == "New Chat" and not needs_clarif:
            chat_session.title = _auto_title(message)

        # Update session timestamp
        from datetime import datetime
        chat_session.updated_at = datetime.utcnow()
        db.session.commit()

        # Save to chat log (don't save clarification questions as real logs)
        if not needs_clarif:
            try:
                log = ChatLog(
                    user_id=user_id,
                    session_id=chat_session.id,
                    message=message,
                    response=reply,
                    collection_used=f"user_{user_id}" if intent == "uploaded_document" else "renvora_knowledge_v2",
                    source_used=source_used,
                    intent_detected=intent,
                )
                db.session.add(log)
                db.session.commit()
            except Exception as e:
                print(f"[MobileAPI] Chat log save error: {e}")

        return jsonify({
            "success": True,
            "reply": reply,
            "session_id": chat_session.id,
            "session_uuid": chat_session.session_uuid,
            "session_title": chat_session.title,
            "intent": intent,
            "source_used": source_used,
            "needs_clarification": needs_clarif,
            "suggested_sources": suggested,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[MobileAPI] CRITICAL ERROR in api_chat: {e}")
        return jsonify({
            "success": False,
            "reply": f"Server error: {str(e)}",
            "error": str(e),
        }), 500



# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────


@mobile_api.route("/documents", methods=["GET"])
def api_get_documents():
    """GET /mobile/documents — list all documents for the current user."""
    user_id, err = _require_auth()
    if err:
        return err

    docs = (
        UserDocument.query.filter_by(user_id=user_id)
        .order_by(UserDocument.uploaded_at.desc())
        .all()
    )
    return jsonify({"success": True, "documents": [d.to_dict() for d in docs]})


def _process_document_background(app, file_path, filename, user_id, collection_name, doc_id):
    """Background thread: read → chunk → embed → store in ChromaDB → set status='ready'."""
    with app.app_context():
        try:
            print(f"[DocProcessor] Starting: {filename} (user={user_id}, doc_id={doc_id})")

            # Step 1: Read document
            try:
                pages = document_reader.read_document(file_path, filename)
                print(f"[DocProcessor] Read {len(pages)} pages from {filename}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                _update_doc_status(doc_id, f"Failed: Cannot read file — {str(e)[:100]}")
                return

            # Step 2: Chunk
            try:
                chunks = chunker.chunk_document(filename, pages)
                print(f"[DocProcessor] Created {len(chunks)} chunks from {filename}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                _update_doc_status(doc_id, f"Failed: Chunking error — {str(e)[:100]}")
                return

            if not chunks:
                print(f"[DocProcessor] No text found in {filename}")
                _update_doc_status(doc_id, "Failed: No text found in document")
                return

            # Step 3: Embed
            try:
                embedded = embedding_engine.create_embeddings(chunks)
                print(f"[DocProcessor] Embedded {len(embedded)}/{len(chunks)} chunks")
            except Exception as e:
                import traceback
                traceback.print_exc()
                _update_doc_status(doc_id, f"Failed: Embedding error — {str(e)[:100]}")
                return

            if not embedded:
                _update_doc_status(doc_id, "Failed: No chunks could be embedded")
                return

            # Step 4: Store in ChromaDB
            try:
                vs = VectorStore(collection_name)
                vs.add_chunks(embedded)
                print(f"[DocProcessor] Stored {len(embedded)} chunks in ChromaDB collection '{collection_name}'")
            except Exception as e:
                import traceback
                traceback.print_exc()
                _update_doc_status(doc_id, f"Failed: ChromaDB storage error — {str(e)[:100]}")
                return

            # Step 5: Update DB to 'ready'
            doc = UserDocument.query.get(doc_id)
            if doc:
                doc.status = "ready"
                doc.page_count = len(pages)
                if chunks:
                    doc.description = chunks[0].get("text", "")[:300]
                db.session.commit()
                print(f"[DocProcessor] SUCCESS: {filename} processed successfully ({len(embedded)} chunks, {len(pages)} pages)")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[DocProcessor] ERROR: Unexpected error processing {filename}: {e}")
            _update_doc_status(doc_id, f"Failed: {str(e)[:100]}")


def _update_doc_status(doc_id: int, status: str):
    """Helper to update document status in DB."""
    try:
        doc = UserDocument.query.get(doc_id)
        if doc:
            doc.status = status
            db.session.commit()
    except Exception as e:
        print(f"[DocProcessor] Could not update status for doc_id={doc_id}: {e}")


@mobile_api.route("/documents/upload", methods=["POST"])
def api_upload_document():
    """POST /mobile/documents/upload — multipart: field 'file'"""
    user_id, err = _require_auth()
    if err:
        return err

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "message": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": f"Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}"}), 400

    filename = secure_filename(file.filename)

    # Duplicate check by file_name + user_id
    existing = UserDocument.query.filter_by(user_id=user_id, file_name=filename).first()
    if existing:
        return jsonify({
            "success": False,
            "message": "A document with this name is already uploaded.",
            "existing_document": existing.to_dict(),
        }), 409

    user_folder = os.path.join(UPLOAD_FOLDER, f"user_{user_id}")
    os.makedirs(user_folder, exist_ok=True)
    file_path = os.path.join(user_folder, filename)
    file.save(file_path)

    try:
        ext = os.path.splitext(file.filename)[1].lower().replace(".", "") or "unknown"
        collection_name = f"user_{user_id}"

        doc = UserDocument(
            user_id=user_id,
            file_name=filename,
            original_name=file.filename,
            file_path=file_path,
            collection_name=collection_name,
            doc_type=ext,
            page_count=0,
            status="Processing",
        )
        db.session.add(doc)
        db.session.commit()

        # Process in background
        from flask import current_app
        app_obj = current_app._get_current_object()
        t = threading.Thread(
            target=_process_document_background,
            args=(app_obj, file_path, filename, user_id, collection_name, doc.id),
            daemon=True,
        )
        t.start()

        return jsonify({
            "success": True,
            "document": doc.to_dict(),
            "message": "Document uploaded and is being processed. It will be ready in a moment.",
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@mobile_api.route("/documents/<int:doc_id>/status", methods=["GET"])
def api_document_status(doc_id):
    """GET /mobile/documents/<id>/status — poll processing status."""
    user_id, err = _require_auth()
    if err:
        return err

    doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    return jsonify({"success": True, "status": doc.status, "page_count": doc.page_count})


@mobile_api.route("/documents/<int:doc_id>", methods=["DELETE"])
def api_delete_document(doc_id):
    """DELETE /mobile/documents/<id>"""
    user_id, err = _require_auth()
    if err:
        return err

    doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    # Remove from vector store
    try:
        vs = VectorStore(doc.collection_name)
        vs.delete_by_pdf_name(doc.file_name)
    except Exception as e:
        print(f"[MobileAPI] ChromaDB delete error: {e}")

    # Remove file from disk
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            print(f"[MobileAPI] File delete error: {e}")

    db.session.delete(doc)
    db.session.commit()

    return jsonify({"success": True, "message": "Document deleted"})


@mobile_api.route("/documents/<int:doc_id>/rename", methods=["POST"])
def api_rename_document(doc_id):
    """POST /mobile/documents/<id>/rename — body: {new_name}"""
    user_id, err = _require_auth()
    if err:
        return err

    data = request.get_json() or {}
    new_name = data.get("new_name", "").strip()
    if not new_name:
        return jsonify({"success": False, "message": "New name is required"}), 400

    doc = UserDocument.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"success": False, "message": "Document not found"}), 404

    doc.original_name = new_name
    db.session.commit()

    return jsonify({"success": True, "message": "Document renamed", "document": doc.to_dict()})
