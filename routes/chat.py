"""
routes/chat.py

Renvora AI chat endpoints.

Responsibilities:
- Chat API
- Load user documents from DB
- Persist chat history
- Persist source/document lock
- Use services.ai_engine.generate_response()
- Company Knowledge uses local embeddings
- Uploaded PDFs use locked doc_id
- Search chats and documents
"""

import traceback

from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    session,
    redirect,
)

# IMPORTANT:
# Use the main AI engine.
# Do NOT use services.gemini_service here.
from services.ai_engine import AIEngine

ai_engine = AIEngine()

from models.user import db
from models.chat_log import ChatLog
from models.chat_session import ChatSession
from models.user_document import UserDocument


chat = Blueprint("chat", __name__)


# ============================================================
# HELPERS
# ============================================================

def _get_ready_documents(user_id):
    """
    Return all ready PDFs belonging to the current user.
    """

    docs = (
        UserDocument.query
        .filter_by(
            user_id=user_id,
            status="ready",
        )
        .order_by(
            UserDocument.uploaded_at.desc()
        )
        .all()
    )

    return [
        {
            "id": d.id,
            "file_name": d.file_name,
            "original_name": d.original_name,
            "doc_type": d.doc_type,
        }
        for d in docs
    ]


def _get_chat_history(session_id, user_id):
    """
    Load previous messages for the current chat session.
    """

    logs = (
        ChatLog.query
        .filter_by(
            session_id=session_id,
            user_id=user_id,
        )
        .order_by(
            ChatLog.timestamp.asc()
        )
        .all()
    )

    history = []

    for log in logs:

        history.append(
            {
                "role": "user",
                "content": log.message,
            }
        )

        if log.response:

            history.append(
                {
                    "role": "assistant",
                    "content": log.response,
                }
            )

    return history


# ============================================================
# CHAT PAGE
# ============================================================

@chat.route("/chat")
def chat_page():

    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "chat.html"
    )


# ============================================================
# AI CHAT API
# ============================================================

@chat.route("/api/chat", methods=["POST"])
def ai_chat():

    if "user_id" not in session:

        return jsonify(
            {
                "success": False,
                "reply": "Please login first.",
            }
        ), 401

    try:

        data = request.get_json() or {}

        message = (
            data.get(
                "message",
                ""
            )
            .strip()
        )

        session_id = data.get(
            "session_id"
        )

        if not message:

            return jsonify(
                {
                    "success": False,
                    "reply": "Please enter a message.",
                }
            )

        user_id = session["user_id"]


        # ====================================================
        # GET OR CREATE CHAT SESSION
        # ====================================================

        if not session_id:

            new_sess = ChatSession(
                user_id=user_id,
                title=(
                    message[:50] + "..."
                    if len(message) > 50
                    else message
                ),
            )

            db.session.add(
                new_sess
            )

            db.session.commit()

            chat_session = new_sess

            session_id = new_sess.id

        else:

            chat_session = (
                ChatSession.query
                .filter_by(
                    id=session_id,
                    user_id=user_id,
                )
                .first()
            )

            if not chat_session:

                return jsonify(
                    {
                        "success": False,
                        "reply": "Invalid session.",
                    }
                ), 403


        # ====================================================
        # LOAD CHAT HISTORY
        # ====================================================

        chat_history = _get_chat_history(
            session_id,
            user_id,
        )


        # ====================================================
        # LOAD USER DOCUMENTS
        # ====================================================

        user_documents = _get_ready_documents(
            user_id
        )


        # ====================================================
        # READ PERSISTED SOURCE LOCK
        # ====================================================

        locked_source = (
            chat_session.active_source
        )

        locked_doc_name = (
            chat_session.active_doc_name
        )

        locked_doc_id = (
            chat_session.active_doc_id
        )


        print(
            "\n"
            "================ CHAT DEBUG ================\n"
        )

        print(
            "[chat.py] User ID:",
            user_id
        )

        print(
            "[chat.py] Message:",
            message
        )

        print(
            "[chat.py] Session ID:",
            session_id
        )

        print(
            "[chat.py] Locked source:",
            locked_source
        )

        print(
            "[chat.py] Locked document name:",
            locked_doc_name
        )

        print(
            "[chat.py] Locked document ID:",
            locked_doc_id
        )

        print(
            "[chat.py] Ready documents:",
            user_documents
        )

        print(
            "============================================\n"
        )


        # ====================================================
        # CALL MAIN AI ENGINE
        # ====================================================

        # IMPORTANT:
        # ai_engine.generate_response()
        # handles:
        #
        # 1. Renvora Company Knowledge
        # 2. Local embeddings
        # 3. Uploaded PDF retrieval
        # 4. doc_id isolation
        #
        result = ai_engine.generate_response(
    user_message=message,
    user_id=user_id,
    chat_history=chat_history,
    locked_source=locked_source,
    locked_doc_name=locked_doc_name,
    locked_doc_id=locked_doc_id,
    user_documents=user_documents,
)

        reply = result.get(
            "reply",
            ""
        )


        # ====================================================
        # PERSIST SOURCE LOCK
        # ====================================================

        new_lock = result.get(
            "lock_source"
        )

        if new_lock and chat_session:

            chat_session.active_source = (
                new_lock
            )

            chat_session.active_doc_name = (
                result.get(
                    "lock_doc_name"
                )
            )

            # IMPORTANT:
            # Keep existing doc_id unless
            # user explicitly selected another PDF.
            #
            # The doc_id is the internal database
            # identifier used for strict PDF isolation.

            if (
                new_lock == "uploaded_document"
                and result.get("lock_doc_name")
            ):

                if not locked_doc_id:

                    document = (
                        UserDocument.query
                        .filter_by(
                            user_id=user_id,
                            file_name=result.get(
                                "lock_doc_name"
                            ),
                        )
                        .first()
                    )

                    if document:

                        chat_session.active_doc_id = (
                            document.id
                        )

            elif new_lock == "renvora_knowledge":

                chat_session.active_doc_id = None


            db.session.commit()


        # ====================================================
        # ADD SESSION ID
        # ====================================================

        result["session_id"] = (
            session_id
        )

        result["success"] = True


        # ====================================================
        # SAVE CHAT LOG
        # ====================================================

        try:

            log_entry = ChatLog(
                user_id=user_id,
                session_id=session_id,
                message=message,
                response=reply,
                collection_used=(
                    result.get(
                        "source_used",
                        ""
                    )
                ),
                source_used=(
                    result.get(
                        "source_used"
                    )
                ),
                intent_detected=(
                    result.get(
                        "intent"
                    )
                ),
            )

            db.session.add(
                log_entry
            )

            db.session.commit()

        except Exception as log_err:

            print(
                f"[chat.py] ChatLog save error: {log_err}"
            )


        return jsonify(
            result
        )


    except Exception as e:

        traceback.print_exc()

        print(
            f"[chat.py] CRITICAL ERROR in ai_chat: {e}"
        )

        return jsonify(
            {
                "success": False,
                "reply": (
                    f"Server error: {str(e)}"
                ),
                "error": str(e),
            }
        ), 500


# ============================================================
# LOCK SOURCE
# ============================================================

@chat.route(
    "/api/chat/lock-source",
    methods=["POST"],
)
def lock_source():

    if "user_id" not in session:

        return jsonify(
            {
                "success": False,
            }
        ), 401


    data = (
        request.get_json()
        or {}
    )

    session_id = data.get(
        "session_id"
    )

    source = data.get(
        "source"
    )

    doc_name = data.get(
        "doc_name"
    )

    doc_id = data.get(
        "doc_id"
    )


    if not session_id:

        return jsonify(
            {
                "success": False,
                "message": "session_id required",
            }
        ), 400


    chat_session = (
        ChatSession.query
        .filter_by(
            id=session_id,
            user_id=session["user_id"],
        )
        .first()
    )


    if not chat_session:

        return jsonify(
            {
                "success": False,
                "message": "Session not found",
            }
        ), 404


    actual_doc_name = doc_name
    actual_doc_id = doc_id


    # ========================================================
    # UPLOADED DOCUMENT LOCK
    # ========================================================

    if source == "uploaded_document":

        document = None


        # Prefer exact internal document ID
        if doc_id:

            document = (
                UserDocument.query
                .filter_by(
                    id=doc_id,
                    user_id=session["user_id"],
                )
                .first()
            )


        # Fallback to name only when no ID was supplied
        elif doc_name:

            document = (
                UserDocument.query
                .filter(
                    UserDocument.user_id
                    == session["user_id"],

                    db.or_(
                        UserDocument.file_name
                        == doc_name,

                        UserDocument.original_name
                        == doc_name,
                    ),
                )
                .first()
            )


        if document:

            actual_doc_name = (
                document.file_name
            )

            actual_doc_id = (
                document.id
            )

        else:

            return jsonify(
                {
                    "success": False,
                    "message": "Document not found",
                }
            ), 404


    # ========================================================
    # SAVE LOCK
    # ========================================================

    chat_session.active_source = (
        source
    )

    chat_session.active_doc_name = (
        actual_doc_name
    )

    if source == "uploaded_document":

        chat_session.active_doc_id = (
            actual_doc_id
        )

    else:

        chat_session.active_doc_id = None


    db.session.commit()


    return jsonify(
        {
            "success": True,
            "locked_to": source,
            "doc_name": actual_doc_name,
            "doc_id": actual_doc_id,
        }
    )


# ============================================================
# SESSIONS API
# ============================================================

@chat.route(
    "/api/chat/sessions",
    methods=["GET"],
)
def get_sessions():

    if "user_id" not in session:

        return jsonify(
            {
                "success": False,
                "message": "Unauthorized",
            }
        ), 401


    sessions = (
        ChatSession.query
        .filter_by(
            user_id=session["user_id"]
        )
        .order_by(
            ChatSession.created_at.desc()
        )
        .all()
    )


    sessions_data = [

        {
            "id": s.id,
            "title": s.title,
            "created_at": (
                s.created_at.isoformat()
                if s.created_at
                else None
            ),
            "locked_source": (
                s.active_source
            ),
            "locked_doc_id": (
                s.active_doc_id
            ),
            "locked_doc_name": (
                s.active_doc_name
            ),
        }

        for s in sessions
    ]


    return jsonify(
        {
            "success": True,
            "sessions": sessions_data,
        }
    )


# ============================================================
# SESSION HISTORY
# ============================================================

@chat.route(
    "/api/chat/sessions/<int:session_id>",
    methods=["GET"],
)
def get_session_history(
    session_id
):

    if "user_id" not in session:

        return jsonify(
            {
                "success": False,
                "message": "Unauthorized",
            }
        ), 401


    chat_session = (
        ChatSession.query
        .filter_by(
            id=session_id,
            user_id=session["user_id"],
        )
        .first()
    )


    if not chat_session:

        return jsonify(
            {
                "success": False,
                "message": "Session not found",
            }
        ), 404


    logs = (
        ChatLog.query
        .filter_by(
            session_id=session_id,
            user_id=session["user_id"],
        )
        .order_by(
            ChatLog.timestamp.asc()
        )
        .all()
    )


    history = [

        {
            "message": log.message,
            "response": log.response,
            "timestamp": (
                log.timestamp.isoformat()
                if log.timestamp
                else None
            ),
        }

        for log in logs
    ]


    return jsonify(
        {
            "success": True,
            "history": history,
        }
    )


# ============================================================
# DELETE SESSION
# ============================================================

@chat.route(
    "/api/chat/sessions/<int:session_id>",
    methods=["DELETE"],
)
def delete_session(
    session_id
):

    if "user_id" not in session:

        return jsonify(
            {
                "success": False,
                "message": "Unauthorized",
            }
        ), 401


    chat_session = (
        ChatSession.query
        .filter_by(
            id=session_id,
            user_id=session["user_id"],
        )
        .first()
    )


    if not chat_session:

        return jsonify(
            {
                "success": False,
                "message": "Session not found",
            }
        ), 404


    try:

        ChatLog.query.filter_by(
            session_id=session_id
        ).delete()


        db.session.delete(
            chat_session
        )

        db.session.commit()


        return jsonify(
            {
                "success": True,
                "message": "Session deleted",
            }
        )


    except Exception as e:

        db.session.rollback()

        return jsonify(
            {
                "success": False,
                "message": str(e),
            }
        ), 500


# ============================================================
# REAL CHAT SEARCH
# ============================================================

@chat.route(
    "/api/chat/search",
    methods=["GET"],
)
def search_chats():

    if "user_id" not in session:

        return jsonify(
            {
                "success": False,
                "message": "Unauthorized",
            }
        ), 401


    q = (
        request.args
        .get("q", "")
        .strip()
    )


    if not q or len(q) < 2:

        return jsonify(
            {
                "success": True,
                "sessions": [],
                "documents": [],
            }
        )


    user_id = session["user_id"]

    search_term = (
        f"%{q}%"
    )


    # ========================================================
    # SEARCH CHAT LOGS
    # ========================================================

    matching_logs = (
        ChatLog.query
        .filter(
            ChatLog.user_id
            == user_id,

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


    seen = {}


    for log in matching_logs:

        if log.session_id in seen:
            continue


        cs = (
            ChatSession.query
            .filter_by(
                id=log.session_id,
                user_id=user_id,
            )
            .first()
        )


        if not cs:
            continue


        snippet = (

            log.message

            if q.lower()
            in (
                log.message or ""
            ).lower()

            else (
                log.response
                or ""
            )
        )


        seen[log.session_id] = {

            "session_id": cs.id,

            "title": cs.title,

            "snippet": (
                snippet[:120] + "..."
                if len(snippet) > 120
                else snippet
            ),

            "created_at": (
                cs.created_at.isoformat()
                if cs.created_at
                else None
            ),
        }


    # ========================================================
    # SEARCH USER DOCUMENTS
    # ========================================================

    matching_docs = (
        UserDocument.query
        .filter(
            UserDocument.user_id
            == user_id,

            UserDocument.original_name
            .ilike(search_term),
        )
        .limit(10)
        .all()
    )


    return jsonify(
        {
            "success": True,

            "sessions":
                list(
                    seen.values()
                ),

            "documents": [

                {
                    "id": d.id,
                    "original_name":
                        d.original_name,
                    "doc_type":
                        d.doc_type,
                    "status":
                        d.status,
                }

                for d in matching_docs
            ],
        }
    )