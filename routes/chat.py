from flask import Blueprint, request, jsonify, render_template, session, redirect
from services.gemini_service import generate_response
from models.user import db
from models.chat_log import ChatLog
from models.chat_session import ChatSession

chat = Blueprint("chat", __name__)

# ===========================
# Chat Page
# ===========================
@chat.route("/chat")
def chat_page():
    # User Login Check
    if "user_id" not in session:
        return redirect("/login")
    return render_template("chat.html")

# ===========================
# AI Chat API
# ===========================
@chat.route("/api/chat", methods=["POST"])
def ai_chat():
    # User Login Check
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "response": "Please login first."
        }), 401

    data = request.get_json()
    message = data.get("message", "").strip()
    session_id = data.get("session_id")

    if message == "":
        return jsonify({
            "success": False,
            "response": "Please enter a message."
        })
        
    # Handle Chat Session
    if not session_id:
        new_session = ChatSession(
            user_id=session["user_id"],
            title=message[:50] + "..." if len(message) > 50 else message
        )
        db.session.add(new_session)
        db.session.commit()
        session_id = new_session.id
    else:
        # Verify session belongs to user
        chat_session = ChatSession.query.filter_by(id=session_id, user_id=session["user_id"]).first()
        if not chat_session:
            return jsonify({"success": False, "response": "Invalid session."}), 403

    collection = session.get("active_collection")

    if collection:
        result = generate_response(message, collection)
    else:
        result = generate_response(message, "renvora_knowledge_v2")
        
    result["session_id"] = session_id

    # Save to ChatLog
    try:
        log_entry = ChatLog(
            user_id=session["user_id"],
            session_id=session_id,
            message=message,
            response=result.get("response", "Error generating response"),
            collection_used=collection if collection else "renvora_knowledge_v2"
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Error logging chat: {e}")

    return jsonify(result)

# ===========================
# Chat Sessions API
# ===========================
@chat.route("/api/chat/sessions", methods=["GET"])
def get_sessions():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
        
    sessions = ChatSession.query.filter_by(user_id=session["user_id"]).order_by(ChatSession.created_at.desc()).all()
    sessions_data = [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]
    
    return jsonify({"success": True, "sessions": sessions_data})

@chat.route("/api/chat/sessions/<int:session_id>", methods=["GET"])
def get_session_history(session_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
        
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session["user_id"]).first()
    if not chat_session:
        return jsonify({"success": False, "message": "Session not found"}), 404
        
    logs = ChatLog.query.filter_by(session_id=session_id, user_id=session["user_id"]).order_by(ChatLog.timestamp.asc()).all()
    history = [{"message": log.message, "response": log.response, "timestamp": log.timestamp.isoformat()} for log in logs]
    
    return jsonify({"success": True, "history": history})

@chat.route("/api/chat/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
        
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=session["user_id"]).first()
    if not chat_session:
        return jsonify({"success": False, "message": "Session not found"}), 404
        
    try:
        ChatLog.query.filter_by(session_id=session_id).delete()
        db.session.delete(chat_session)
        db.session.commit()
        return jsonify({"success": True, "message": "Session deleted"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500