"""
routes/mobile_api.py

REST API endpoints for the Renvora AI Flutter mobile app.

Main responsibilities:
- Authentication
- Chat sessions
- Chat history
- Source selection
- Source switching
- Chat search
- Document upload
- Document processing
- Document deletion
- Document rename
- Session sharing

Important source rules:

1. renvora_knowledge
   -> Renvora company knowledge

2. uploaded_document
   -> User's uploaded documents

3. previous_conversation
   -> Conversation context only

4. ambiguous
   -> Only when two factual sources genuinely match

5. unsupported
   -> Outside available knowledge sources

The current question always has priority over an old source lock.
"""

import os
import uuid
import threading
import traceback

from datetime import datetime

from flask import (
    Blueprint,
    request,
    jsonify,
    session,
    current_app,
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

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


# ============================================================================
# BLUEPRINT
# ============================================================================

mobile_api = Blueprint(
    "mobile_api",
    __name__,
    url_prefix="/mobile",
)


# ============================================================================
# CONFIGURATION
# ============================================================================

UPLOAD_FOLDER = "uploads/user_documents"

ALLOWED_EXTENSIONS = {
    "pdf",
    "xlsx",
    "csv",
    "docx",
    "pptx",
    "txt",
}


# ============================================================================
# SERVICE INSTANCES
# ============================================================================

document_reader = DocumentReader()
chunker = TextChunker()
embedding_engine = EmbeddingEngine()


# ============================================================================
# HELPERS
# ============================================================================

def allowed_file(filename: str) -> bool:
    """
    Check whether the uploaded file extension is supported.
    """

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = (
        filename
        .rsplit(".", 1)[1]
        .lower()
    )

    return extension in ALLOWED_EXTENSIONS


def _require_auth():
    """
    Require an authenticated mobile session.

    Returns:
        (user_id, None)

    OR:

        (None, error_response)
    """

    user_id = session.get("user_id")

    if not user_id:
        return (
            None,
            (
                jsonify({
                    "success": False,
                    "message": "Unauthorized",
                }),
                401,
            ),
        )

    return user_id, None


def _build_chat_history(
    session_id: int,
    limit: int = 20,
) -> list:
    """
    Build conversation history from ChatLog.

    We keep more context than the old 10-row version so that
    natural follow-up questions can be understood better.

    ChatLog represents one user question + one AI response.
    """

    logs = (
        ChatLog.query
        .filter_by(session_id=session_id)
        .order_by(ChatLog.timestamp.asc())
        .limit(limit)
        .all()
    )

    history = []

    for log in logs:

        if log.message:
            history.append({
                "role": "user",
                "content": log.message,
            })

        if log.response:
            history.append({
                "role": "assistant",
                "content": log.response,
            })

    return history


def _get_or_create_session(
    user_id: int,
    session_uuid: str,
) -> ChatSession:
    """
    Get an existing session or create a new one.
    """

    chat_session = (
        ChatSession.query
        .filter_by(
            user_id=user_id,
            session_uuid=session_uuid,
        )
        .first()
    )

    if chat_session:
        return chat_session

    chat_session = ChatSession(
        user_id=user_id,
        session_uuid=session_uuid,
        title="New Chat",
    )

    db.session.add(chat_session)
    db.session.commit()

    return chat_session


def _auto_title(
    message: str,
    max_len: int = 50,
) -> str:
    """
    Create a short title from the first message.
    """

    title = (message or "").strip()

    if len(title) > max_len:

        shortened = title[:max_len]

        if " " in shortened:
            shortened = shortened.rsplit(
                " ",
                1,
            )[0]

        title = shortened + "…"

    return title or "New Chat"


def _get_user_documents(
    user_id: int,
) -> list:
    """
    Load all ready documents belonging to this user.

    This gives uploaded documents permanent availability.

    A document uploaded five days ago is still available as long
    as it remains in the database and has status='ready'.
    """

    documents = (
        UserDocument.query
        .filter_by(
            user_id=user_id,
        )
        .order_by(
            UserDocument.uploaded_at.desc()
        )
        .all()
    )

    ready_documents = []

    for document in documents:

        if str(document.status).lower() != "ready":
            continue

        try:
            ready_documents.append(
                document.to_dict()
            )
        except Exception:
            ready_documents.append({
                "id": document.id,
                "file_name": document.file_name,
                "original_name": document.original_name,
                "collection_name": document.collection_name,
                "status": document.status,
            })

    return ready_documents


def _valid_source(source: str) -> bool:
    """
    Valid factual source values.

    general_ai is intentionally removed.
    """

    return source in {
        "renvora_knowledge",
        "uploaded_document",
    }


def _apply_source_selection(
    chat_session: ChatSession,
    user_id: int,
    source: str,
    doc_id: int = None,
) -> tuple:
    """
    Apply a source selection to a chat session.

    Returns:

        (True, None)

    OR:

        (False, error_message)
    """

    if not _valid_source(source):
        return (
            False,
            "Invalid source. Use renvora_knowledge or uploaded_document.",
        )

    chat_session.active_source = source

    if source == "uploaded_document":

        if not doc_id:
            return (
                False,
                "doc_id is required for uploaded_document.",
            )

        document = (
            UserDocument.query
            .filter_by(
                id=doc_id,
                user_id=user_id,
            )
            .first()
        )

        if not document:
            return (
                False,
                "Document not found.",
            )

        if str(document.status).lower() != "ready":
            return (
                False,
                "Document is not ready yet.",
            )

        chat_session.active_doc_id = document.id
        chat_session.active_doc_name = (
            document.file_name
        )

    else:

        chat_session.active_doc_id = None
        chat_session.active_doc_name = None

    return True, None


# ============================================================================
# AUTH
# ============================================================================

@mobile_api.route(
    "/auth/login",
    methods=["POST"],
)
def api_login():
    """
    POST /mobile/auth/login

    Body:
    {
        "email": "...",
        "password": "..."
    }
    """

    data = request.get_json() or {}

    email = data.get(
        "email",
        "",
    ).strip()

    password = data.get(
        "password",
        "",
    )

    if not email or not password:

        return jsonify({
            "success": False,
            "message": "Email and password required",
        }), 400

    user = (
        User.query
        .filter_by(email=email)
        .first()
    )

    if not user:

        return jsonify({
            "success": False,
            "message": "Invalid email or password",
        }), 401

    if not check_password_hash(
        user.password,
        password,
    ):

        return jsonify({
            "success": False,
            "message": "Invalid email or password",
        }), 401

    session["user_id"] = user.id
    session["user_name"] = user.name
    session["user_email"] = user.email

    documents = _get_user_documents(
        user.id
    )

    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
        "documents": documents,
    })


@mobile_api.route(
    "/auth/register",
    methods=["POST"],
)
def api_register():
    """
    POST /mobile/auth/register

    Body:
    {
        "name": "...",
        "email": "...",
        "password": "..."
    }
    """

    data = request.get_json() or {}

    name = data.get(
        "name",
        "",
    ).strip()

    email = data.get(
        "email",
        "",
    ).strip()

    password = data.get(
        "password",
        "",
    )

    if not name or not email or not password:

        return jsonify({
            "success": False,
            "message": "All fields are required",
        }), 400

    existing = (
        User.query
        .filter_by(email=email)
        .first()
    )

    if existing:

        return jsonify({
            "success": False,
            "message": "Email already registered",
        }), 409

    user = User(
        name=name,
        email=email,
        password=generate_password_hash(
            password
        ),
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": (
            "Registration successful. "
            "Please login."
        ),
    })


@mobile_api.route(
    "/auth/logout",
    methods=["POST"],
)
def api_logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out",
    })


@mobile_api.route(
    "/auth/me",
    methods=["GET"],
)
def api_me():

    user_id = session.get(
        "user_id"
    )

    if not user_id:

        return jsonify({
            "success": False,
            "message": "Not authenticated",
        }), 401

    user = User.query.get(
        user_id
    )

    if not user:

        return jsonify({
            "success": False,
            "message": "User not found",
        }), 404

    documents = _get_user_documents(
        user_id
    )

    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
        "documents": documents,
    })


# ============================================================================
# CHAT SESSIONS
# ============================================================================

@mobile_api.route(
    "/sessions",
    methods=["GET"],
)
def api_list_sessions():

    user_id, err = _require_auth()

    if err:
        return err

    sessions_list = (
        ChatSession.query
        .filter_by(user_id=user_id)
        .order_by(
            ChatSession.updated_at.desc()
        )
        .all()
    )

    result = []

    for chat_session in sessions_list:

        last_log = (
            ChatLog.query
            .filter_by(
                session_id=chat_session.id
            )
            .order_by(
                ChatLog.timestamp.desc()
            )
            .first()
        )

        result.append({
            "id": chat_session.id,
            "session_uuid": chat_session.session_uuid,
            "title": (
                chat_session.title
                or "New Chat"
            ),
            "active_source": (
                chat_session.active_source
            ),
            "active_doc_name": (
                chat_session.active_doc_name
            ),
            "is_shared": (
                chat_session.is_shared
            ),
            "share_token": (
                chat_session.share_token
                if chat_session.is_shared
                else None
            ),
            "created_at": (
                chat_session.created_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if chat_session.created_at
                else None
            ),
            "updated_at": (
                chat_session.updated_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if chat_session.updated_at
                else None
            ),
            "last_message": (
                last_log.message[:80]
                if last_log and last_log.message
                else ""
            ),
            "last_response": (
                last_log.response[:80]
                if last_log and last_log.response
                else ""
            ),
        })

    return jsonify({
        "success": True,
        "sessions": result,
    })


@mobile_api.route(
    "/sessions",
    methods=["POST"],
)
def api_create_session():

    user_id, err = _require_auth()

    if err:
        return err

    data = request.get_json() or {}

    session_uuid = (
        data.get("session_uuid")
        or str(uuid.uuid4())
    )

    existing = (
        ChatSession.query
        .filter_by(
            user_id=user_id,
            session_uuid=session_uuid,
        )
        .first()
    )

    if existing:

        return jsonify({
            "success": True,
            "session": {
                "id": existing.id,
                "session_uuid": existing.session_uuid,
                "title": existing.title,
            },
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
            "session_uuid": (
                new_session.session_uuid
            ),
            "title": new_session.title,
        },
    }), 201


@mobile_api.route(
    "/sessions/<int:session_id>",
    methods=["GET"],
)
def api_get_session(session_id):

    user_id, err = _require_auth()

    if err:
        return err

    chat_session = (
        ChatSession.query
        .filter_by(
            id=session_id,
            user_id=user_id,
        )
        .first()
    )

    if not chat_session:

        return jsonify({
            "success": False,
            "message": "Session not found",
        }), 404

    logs = (
        ChatLog.query
        .filter_by(
            session_id=session_id
        )
        .order_by(
            ChatLog.timestamp.asc()
        )
        .all()
    )

    return jsonify({
        "success": True,
        "session": {
            "id": chat_session.id,
            "session_uuid": (
                chat_session.session_uuid
            ),
            "title": chat_session.title,
            "active_source": (
                chat_session.active_source
            ),
            "active_doc_name": (
                chat_session.active_doc_name
            ),
            "is_shared": (
                chat_session.is_shared
            ),
        },
        "messages": [
            log.to_dict()
            for log in logs
        ],
    })


@mobile_api.route(
    "/sessions/<int:session_id>",
    methods=["DELETE"],
)
def api_delete_session(session_id):

    user_id, err = _require_auth()

    if err:
        return err

    chat_session = (
        ChatSession.query
        .filter_by(
            id=session_id,
            user_id=user_id,
        )
        .first()
    )

    if not chat_session:

        return jsonify({
            "success": False,
            "message": "Session not found",
        }), 404

    db.session.delete(
        chat_session
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Session deleted",
    })


# ============================================================================
# SOURCE SELECTION
# ============================================================================

@mobile_api.route(
    "/sessions/<int:session_id>/select-source",
    methods=["POST"],
)
def api_select_source(session_id):
    """
    Explicitly select a source.

    Body:

    {
        "source": "renvora_knowledge"
    }

    OR:

    {
        "source": "uploaded_document",
        "doc_id": 123
    }

    This endpoint is only used when the user explicitly selects
    a source from Flutter clarification chips.

    It is NOT automatically called for every normal question.
    """

    user_id, err = _require_auth()

    if err:
        return err

    chat_session = (
        ChatSession.query
        .filter_by(
            id=session_id,
            user_id=user_id,
        )
        .first()
    )

    if not chat_session:

        return jsonify({
            "success": False,
            "message": "Session not found",
        }), 404

    data = request.get_json() or {}

    source = data.get(
        "source"
    )

    doc_id = data.get(
        "doc_id"
    )

    success, error = _apply_source_selection(
        chat_session,
        user_id,
        source,
        doc_id,
    )

    if not success:

        return jsonify({
            "success": False,
            "message": error,
        }), 400

    db.session.commit()

    return jsonify({
        "success": True,
        "active_source": (
            chat_session.active_source
        ),
        "active_doc_name": (
            chat_session.active_doc_name
        ),
    })


# ============================================================================
# SHARE SESSION
# ============================================================================

@mobile_api.route(
    "/sessions/<int:session_id>/share",
    methods=["POST"],
)
def api_share_session(session_id):

    user_id, err = _require_auth()

    if err:
        return err

    chat_session = (
        ChatSession.query
        .filter_by(
            id=session_id,
            user_id=user_id,
        )
        .first()
    )

    if not chat_session:

        return jsonify({
            "success": False,
            "message": "Session not found",
        }), 404

    if not chat_session.share_token:

        chat_session.generate_share_token()

        db.session.commit()

    base_url = (
        request.host_url.rstrip("/")
    )

    share_url = (
        f"{base_url}/mobile/shared/"
        f"{chat_session.share_token}"
    )

    return jsonify({
        "success": True,
        "share_token": (
            chat_session.share_token
        ),
        "share_url": share_url,
    })


@mobile_api.route(
    "/shared/<share_token>",
    methods=["GET"],
)
def api_view_shared(share_token):

    chat_session = (
        ChatSession.query
        .filter_by(
            share_token=share_token,
            is_shared=True,
        )
        .first()
    )

    if not chat_session:

        return jsonify({
            "success": False,
            "message": "Shared chat not found",
        }), 404

    logs = (
        ChatLog.query
        .filter_by(
            session_id=chat_session.id
        )
        .order_by(
            ChatLog.timestamp.asc()
        )
        .all()
    )

    messages = []

    for log in logs:

        messages.append({
            "role": "user",
            "content": log.message,
            "timestamp": (
                log.timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if log.timestamp
                else None
            ),
        })

        messages.append({
            "role": "assistant",
            "content": log.response,
            "source_used": log.source_used,
            "timestamp": (
                log.timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if log.timestamp
                else None
            ),
        })

    return jsonify({
        "success": True,
        "session_title": (
            chat_session.title
        ),
        "messages": messages,
    })


# ============================================================================
# CHAT SEARCH
# ============================================================================

@mobile_api.route(
    "/sessions/search",
    methods=["GET"],
)
def api_search_sessions():
    """
    Search messages and AI responses belonging only to the
    authenticated user.
    """

    user_id, err = _require_auth()

    if err:
        return err

    query = request.args.get(
        "q",
        "",
    ).strip()

    if not query or len(query) < 2:

        return jsonify({
            "success": False,
            "message": "Search query too short",
        }), 400

    user_session_ids = [
        s.id
        for s in (
            ChatSession.query
            .filter_by(user_id=user_id)
            .all()
        )
    ]

    if not user_session_ids:

        return jsonify({
            "success": True,
            "results": [],
        })

    search_term = f"%{query}%"

    matching_logs = (
        ChatLog.query
        .filter(
            ChatLog.session_id.in_(
                user_session_ids
            ),
            db.or_(
                ChatLog.message.ilike(
                    search_term
                ),
                ChatLog.response.ilike(
                    search_term
                ),
            ),
        )
        .order_by(
            ChatLog.timestamp.desc()
        )
        .limit(30)
        .all()
    )

    results = []

    seen_sessions = {}

    for log in matching_logs:

        chat_session = seen_sessions.get(
            log.session_id
        )

        if not chat_session:

            chat_session = (
                ChatSession.query.get(
                    log.session_id
                )
            )

            seen_sessions[
                log.session_id
            ] = chat_session

        results.append({
            "session_id": log.session_id,
            "session_uuid": (
                chat_session.session_uuid
                if chat_session
                else None
            ),
            "session_title": (
                chat_session.title
                if chat_session
                else "Chat"
            ),
            "message": log.message,
            "response": (
                log.response[:200]
                if log.response
                else ""
            ),
            "source_used": (
                log.source_used
            ),
            "timestamp": (
                log.timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if log.timestamp
                else None
            ),
        })

    return jsonify({
        "success": True,
        "results": results,
        "count": len(results),
    })


# ============================================================================
# CHAT
# ============================================================================

@mobile_api.route(
    "/chat",
    methods=["POST"],
)
def api_chat():
    """
    POST /mobile/chat

    Body:

    {
        "message": "...",
        "session_uuid": "...",

        Optional:
        "source_override":
            "renvora_knowledge"
            "uploaded_document"

        Optional:
        "doc_id": 123
    }

    IMPORTANT:

    source_override is an EXPLICIT user selection.

    Normal questions should NOT send source_override.

    This allows the AI to switch naturally:

        PDF question
        ->
        Renvora question
        ->
        PDF question
    """

    user_id, err = _require_auth()

    if err:
        return err

    try:

        # ==================================================================
        # INPUT
        # ==================================================================

        data = request.get_json() or {}

        message = data.get(
            "message",
            "",
        ).strip()

        if not message:

            return jsonify({
                "success": False,
                "message": "Message cannot be empty",
            }), 400

        session_uuid = (
            data.get("session_uuid")
            or str(uuid.uuid4())
        )

        # ==================================================================
        # SESSION
        # ==================================================================

        chat_session = _get_or_create_session(
            user_id,
            session_uuid,
        )

        # ==================================================================
        # EXPLICIT SOURCE OVERRIDE
        # ==================================================================

        source_override = data.get(
            "source_override"
        )

        doc_id_override = data.get(
            "doc_id"
        )

        if source_override:

            success, error = (
                _apply_source_selection(
                    chat_session,
                    user_id,
                    source_override,
                    doc_id_override,
                )
            )

            if not success:

                return jsonify({
                    "success": False,
                    "message": error,
                }), 400

            db.session.commit()

        # ==================================================================
        # CONVERSATION HISTORY
        # ==================================================================

        chat_history = _build_chat_history(
            chat_session.id,
            limit=20,
        )

        # ==================================================================
        # USER DOCUMENTS
        # ==================================================================

        user_documents = _get_user_documents(
            user_id
        )

        document_names = []

        for document in user_documents:

            name = (
                document.get("original_name")
                or document.get("file_name")
            )

            if name:
                document_names.append(
                    name
                )

        print(
            "[MobileAPI] Chat request:"
            f" user={user_id}"
            f" session={chat_session.id}"
            f" documents={len(user_documents)}"
            f" locked_source={chat_session.active_source}"
            f" locked_doc={chat_session.active_doc_name}"
        )

        # ==================================================================
        # AI ENGINE
        # ==================================================================

        result = ai_engine.generate_response(
            user_message=message,
            user_id=user_id,
            chat_history=chat_history,
            locked_source=(
                chat_session.active_source
            ),
            locked_doc_name=(
                chat_session.active_doc_name
            ),
            user_documents=user_documents,
        )

        # ==================================================================
        # NORMALIZE AI RESULT
        # ==================================================================

        reply = result.get(
            "reply",
            "",
        )

        intent = result.get(
            "intent",
            "unsupported",
        )

        source_used = result.get(
            "source_used",
            "",
        )

        lock_source = result.get(
            "lock_source"
        )

        lock_doc_name = result.get(
            "lock_doc_name"
        )

        needs_clarification = bool(
            result.get(
                "needs_clarification",
                False,
            )
        )

        suggested_sources = result.get(
            "suggested_sources",
            [],
        )

        if not isinstance(
            suggested_sources,
            list,
        ):
            suggested_sources = []

        # ==================================================================
        # DEBUG
        # ==================================================================

        print(
            "[MobileAPI] AI response:"
            f" intent={intent}"
            f" source={source_used}"
            f" reply_length={len(reply)}"
            f" clarification={needs_clarification}"
        )

        # ==================================================================
        # SOURCE LOCK
        # ==================================================================
        #
        # IMPORTANT:
        #
        # We only persist a source when the AI has confidently selected
        # one and there is no clarification.
        #
        # However, an existing source lock is NOT blindly forced here.
        # ai_engine / intent_detector can switch source based on the
        # CURRENT question.
        #
        # Explicit source_override is already applied above.
        # ==================================================================

        if (
            lock_source
            and not needs_clarification
            and lock_source in {
                "renvora_knowledge",
                "uploaded_document",
            }
        ):

            chat_session.active_source = (
                lock_source
            )

            if (
                lock_source
                == "uploaded_document"
            ):

                if lock_doc_name:

                    document = (
                        UserDocument.query
                        .filter(
                            UserDocument.user_id
                            == user_id,
                            db.or_(
                                UserDocument.file_name
                                == lock_doc_name,
                                UserDocument.original_name
                                == lock_doc_name,
                            ),
                        )
                        .first()
                    )

                    if document:

                        chat_session.active_doc_id = (
                            document.id
                        )

                        chat_session.active_doc_name = (
                            document.file_name
                        )

            else:

                chat_session.active_doc_id = None
                chat_session.active_doc_name = None

        # ==================================================================
        # AUTO TITLE
        # ==================================================================

        if (
            chat_session.title == "New Chat"
            and not needs_clarification
        ):

            chat_session.title = _auto_title(
                message
            )

        # ==================================================================
        # SESSION TIMESTAMP
        # ==================================================================

        chat_session.updated_at = (
            datetime.utcnow()
        )

        db.session.commit()

        # ==================================================================
        # SAVE CHAT LOG
        # ==================================================================

        if not needs_clarification:

            try:

                if intent == "uploaded_document":

                    collection_used = (
                        f"user_{user_id}"
                    )

                elif intent == "renvora_knowledge":

                    collection_used = (
                        "renvora_knowledge_v2"
                    )

                else:

                    collection_used = ""

                log = ChatLog(
                    user_id=user_id,
                    session_id=chat_session.id,
                    message=message,
                    response=reply,
                    collection_used=collection_used,
                    source_used=source_used,
                    intent_detected=intent,
                )

                db.session.add(log)
                db.session.commit()

            except Exception as log_error:

                print(
                    "[MobileAPI] "
                    f"Chat log save error: "
                    f"{log_error}"
                )

                db.session.rollback()

        # ==================================================================
        # RESPONSE
        # ==================================================================

        return jsonify({
            "success": True,
            "reply": reply,
            "session_id": chat_session.id,
            "session_uuid": (
                chat_session.session_uuid
            ),
            "session_title": (
                chat_session.title
            ),
            "intent": intent,
            "source_used": source_used,
            "needs_clarification": (
                needs_clarification
            ),
            "suggested_sources": (
                suggested_sources
            ),
        })

    except Exception as e:

        traceback.print_exc()

        print(
            "[MobileAPI] CRITICAL ERROR "
            f"in api_chat: {e}"
        )

        db.session.rollback()

        return jsonify({
            "success": False,
            "reply": (
                "I couldn't process that "
                "right now. Please try again."
            ),
            "error": str(e),
        }), 500


# ============================================================================
# DOCUMENTS
# ============================================================================

@mobile_api.route(
    "/documents",
    methods=["GET"],
)
def api_get_documents():

    user_id, err = _require_auth()

    if err:
        return err

    documents = (
        UserDocument.query
        .filter_by(
            user_id=user_id
        )
        .order_by(
            UserDocument.uploaded_at.desc()
        )
        .all()
    )

    return jsonify({
        "success": True,
        "documents": [
            document.to_dict()
            for document in documents
        ],
    })


# ============================================================================
# BACKGROUND DOCUMENT PROCESSOR
# ============================================================================

def _process_document_background(
    app,
    file_path,
    filename,
    user_id,
    collection_name,
    doc_id,
):
    """
    Background document pipeline:

        file
        ↓
        DocumentReader
        ↓
        TextChunker
        ↓
        Gemini retrieval_document embedding
        ↓
        ChromaDB
        ↓
        UserDocument.status = ready
    """

    with app.app_context():

        try:

            print(
                "[DocProcessor] Starting:"
                f" {filename}"
                f" user={user_id}"
                f" doc_id={doc_id}"
            )

            # ==============================================================
            # STEP 1 — READ
            # ==============================================================

            try:

                pages = (
                    document_reader.read_document(
                        file_path,
                        filename,
                    )
                )

                print(
                    "[DocProcessor] "
                    f"Read {len(pages)} pages "
                    f"from {filename}"
                )

            except Exception as e:

                traceback.print_exc()

                _update_doc_status(
                    doc_id,
                    (
                        "Failed: Cannot read file — "
                        f"{str(e)[:150]}"
                    ),
                )

                return

            # ==============================================================
            # STEP 2 — CHUNK
            # ==============================================================

            try:

                chunks = (
                    chunker.chunk_document(
                        filename,
                        pages,
                    )
                )

                print(
                    "[DocProcessor] "
                    f"Created {len(chunks)} chunks "
                    f"from {filename}"
                )

            except Exception as e:

                traceback.print_exc()

                _update_doc_status(
                    doc_id,
                    (
                        "Failed: Chunking error — "
                        f"{str(e)[:150]}"
                    ),
                )

                return

            if not chunks:

                print(
                    "[DocProcessor] "
                    f"No text found in {filename}"
                )

                _update_doc_status(
                    doc_id,
                    "Failed: No text found in document",
                )

                return

            # ==============================================================
            # STEP 3 — EMBEDDINGS
            # ==============================================================

            try:

                embedded = (
                    embedding_engine.create_embeddings(
                        chunks
                    )
                )

                print(
                    "[DocProcessor] "
                    f"Embedded "
                    f"{len(embedded)}/{len(chunks)} "
                    f"chunks"
                )

            except Exception as e:

                traceback.print_exc()

                _update_doc_status(
                    doc_id,
                    (
                        "Failed: Embedding error — "
                        f"{str(e)[:150]}"
                    ),
                )

                return

            if not embedded:

                _update_doc_status(
                    doc_id,
                    "Failed: No chunks could be embedded",
                )

                return

            # ==============================================================
            # STEP 4 — CHROMADB
            # ==============================================================

            try:

                vector_store = VectorStore(
                    collection_name
                )

                vector_store.add_chunks(
                    embedded
                )

                print(
                    "[DocProcessor] "
                    f"Stored {len(embedded)} chunks "
                    f"in ChromaDB collection "
                    f"'{collection_name}'"
                )

            except Exception as e:

                traceback.print_exc()

                _update_doc_status(
                    doc_id,
                    (
                        "Failed: ChromaDB storage error — "
                        f"{str(e)[:150]}"
                    ),
                )

                return

            # ==============================================================
            # STEP 5 — DATABASE
            # ==============================================================

            document = (
                UserDocument.query.get(
                    doc_id
                )
            )

            if not document:

                print(
                    "[DocProcessor] "
                    f"Document {doc_id} disappeared "
                    "from database."
                )

                return

            document.status = "ready"
            document.page_count = len(
                pages
            )

            if chunks:

                first_text = (
                    chunks[0].get(
                        "text",
                        "",
                    )
                )

                document.description = (
                    first_text[:300]
                )

            db.session.commit()

            print(
                "[DocProcessor] SUCCESS:"
                f" {filename}"
                f" | chunks={len(embedded)}"
                f" | pages={len(pages)}"
            )

        except Exception as e:

            traceback.print_exc()

            print(
                "[DocProcessor] "
                f"Unexpected error processing "
                f"{filename}: {e}"
            )

            _update_doc_status(
                doc_id,
                (
                    "Failed: "
                    f"{str(e)[:150]}"
                ),
            )


def _update_doc_status(
    doc_id: int,
    status: str,
):
    """
    Safely update UserDocument.status.
    """

    try:

        document = (
            UserDocument.query.get(
                doc_id
            )
        )

        if document:

            document.status = status

            db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            "[DocProcessor] "
            f"Could not update status "
            f"for doc_id={doc_id}: {e}"
        )


# ============================================================================
# DOCUMENT UPLOAD
# ============================================================================

@mobile_api.route(
    "/documents/upload",
    methods=["POST"],
)
def api_upload_document():

    user_id, err = _require_auth()

    if err:
        return err

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "message": "No file provided",
        }), 400

    uploaded_file = request.files[
        "file"
    ]

    if not uploaded_file.filename:

        return jsonify({
            "success": False,
            "message": "Empty filename",
        }), 400

    if not allowed_file(
        uploaded_file.filename
    ):

        return jsonify({
            "success": False,
            "message": (
                "Unsupported file type. "
                f"Allowed: "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        }), 400

    filename = secure_filename(
        uploaded_file.filename
    )

    if not filename:

        return jsonify({
            "success": False,
            "message": "Invalid filename",
        }), 400

    # ======================================================================
    # DUPLICATE CHECK
    # ======================================================================

    existing = (
        UserDocument.query
        .filter_by(
            user_id=user_id,
            file_name=filename,
        )
        .first()
    )

    if existing:

        return jsonify({
            "success": False,
            "message": (
                "A document with this name "
                "is already uploaded."
            ),
            "existing_document": (
                existing.to_dict()
            ),
        }), 409

    # ======================================================================
    # USER FOLDER
    # ======================================================================

    user_folder = os.path.join(
        UPLOAD_FOLDER,
        f"user_{user_id}",
    )

    os.makedirs(
        user_folder,
        exist_ok=True,
    )

    file_path = os.path.join(
        user_folder,
        filename,
    )

    try:

        uploaded_file.save(
            file_path
        )

        extension = (
            os.path.splitext(
                uploaded_file.filename
            )[1]
            .lower()
            .replace(
                ".",
                "",
            )
            or "unknown"
        )

        collection_name = (
            f"user_{user_id}"
        )

        # ==============================================================
        # DATABASE RECORD
        # ==============================================================

        document = UserDocument(
            user_id=user_id,
            file_name=filename,
            original_name=(
                uploaded_file.filename
            ),
            file_path=file_path,
            collection_name=collection_name,
            doc_type=extension,
            page_count=0,
            status="Processing",
        )

        db.session.add(
            document
        )

        db.session.commit()

        # ==============================================================
        # BACKGROUND PROCESSING
        # ==============================================================

        app_obj = (
            current_app
            ._get_current_object()
        )

        thread = threading.Thread(
            target=_process_document_background,
            args=(
                app_obj,
                file_path,
                filename,
                user_id,
                collection_name,
                document.id,
            ),
            daemon=True,
        )

        thread.start()

        return jsonify({
            "success": True,
            "document": (
                document.to_dict()
            ),
            "message": (
                "Document uploaded and is "
                "being processed. It will be "
                "ready in a moment."
            ),
        }), 201

    except Exception as e:

        db.session.rollback()

        traceback.print_exc()

        # Remove partially saved file.
        try:

            if os.path.exists(
                file_path
            ):
                os.remove(
                    file_path
                )

        except Exception:
            pass

        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ============================================================================
# DOCUMENT STATUS
# ============================================================================

@mobile_api.route(
    "/documents/<int:doc_id>/status",
    methods=["GET"],
)
def api_document_status(doc_id):

    user_id, err = _require_auth()

    if err:
        return err

    document = (
        UserDocument.query
        .filter_by(
            id=doc_id,
            user_id=user_id,
        )
        .first()
    )

    if not document:

        return jsonify({
            "success": False,
            "message": "Document not found",
        }), 404

    return jsonify({
        "success": True,
        "status": document.status,
        "page_count": (
            document.page_count
        ),
    })


# ============================================================================
# DOCUMENT DELETE
# ============================================================================

@mobile_api.route(
    "/documents/<int:doc_id>",
    methods=["DELETE"],
)
def api_delete_document(doc_id):

    user_id, err = _require_auth()

    if err:
        return err

    document = (
        UserDocument.query
        .filter_by(
            id=doc_id,
            user_id=user_id,
        )
        .first()
    )

    if not document:

        return jsonify({
            "success": False,
            "message": "Document not found",
        }), 404

    # ======================================================================
    # DELETE VECTOR DATA
    # ======================================================================

    try:

        vector_store = VectorStore(
            document.collection_name
        )

        vector_store.delete_by_pdf_name(
            document.file_name
        )

    except Exception as e:

        print(
            "[MobileAPI] "
            f"ChromaDB delete error: {e}"
        )

    # ======================================================================
    # DELETE FILE
    # ======================================================================

    try:

        if os.path.exists(
            document.file_path
        ):

            os.remove(
                document.file_path
            )

    except Exception as e:

        print(
            "[MobileAPI] "
            f"File delete error: {e}"
        )

    # ======================================================================
    # CLEAR SESSION REFERENCES
    # ======================================================================

    sessions = (
        ChatSession.query
        .filter_by(
            user_id=user_id,
            active_doc_id=document.id,
        )
        .all()
    )

    for chat_session in sessions:

        chat_session.active_doc_id = None
        chat_session.active_doc_name = None

        if (
            chat_session.active_source
            == "uploaded_document"
        ):
            chat_session.active_source = None

    # ======================================================================
    # DATABASE DELETE
    # ======================================================================

    db.session.delete(
        document
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Document deleted",
    })


# ============================================================================
# DOCUMENT RENAME
# ============================================================================

@mobile_api.route(
    "/documents/<int:doc_id>/rename",
    methods=["POST"],
)
def api_rename_document(doc_id):

    user_id, err = _require_auth()

    if err:
        return err

    data = request.get_json() or {}

    new_name = data.get(
        "new_name",
        "",
    ).strip()

    if not new_name:

        return jsonify({
            "success": False,
            "message": "New name is required",
        }), 400

    document = (
        UserDocument.query
        .filter_by(
            id=doc_id,
            user_id=user_id,
        )
        .first()
    )

    if not document:

        return jsonify({
            "success": False,
            "message": "Document not found",
        }), 404

    # IMPORTANT:
    #
    # We only change original_name.
    #
    # file_name remains unchanged because it is used
    # by the actual stored file and ChromaDB metadata.
    #
    # This prevents existing embeddings from breaking.

    document.original_name = new_name

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Document renamed",
        "document": (
            document.to_dict()
        ),
    })