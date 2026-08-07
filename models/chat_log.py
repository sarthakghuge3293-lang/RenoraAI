from models.user import db
from datetime import datetime


class ChatLog(db.Model):
    __tablename__ = "chat_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)

    # Session this message belongs to (required)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=True)

    # The user message
    message = db.Column(db.Text, nullable=False)

    # The AI response
    response = db.Column(db.Text, nullable=False)

    # Which ChromaDB collection was queried (legacy, kept for compatibility)
    collection_used = db.Column(db.String(255), nullable=True)

    # Human-readable label of the source actually used to answer
    # Values: "General AI Knowledge", "Renvora Company Knowledge",
    #         "Uploaded Document: filename.pdf", "Conversation History"
    source_used = db.Column(db.String(255), nullable=True)

    # The intent the AI detected for this message
    # Values: "general_knowledge", "renvora_knowledge", "uploaded_document",
    #         "previous_conversation", "ambiguous"
    intent_detected = db.Column(db.String(50), nullable=True)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<ChatLog {self.id} session={self.session_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "message": self.message,
            "response": self.response,
            "source_used": self.source_used,
            "intent_detected": self.intent_detected,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None,
        }
