from models.user import db
from datetime import datetime
import uuid


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # Flutter-generated UUID for this conversation thread
    session_uuid = db.Column(db.String(36), unique=True, nullable=True, index=True)

    # Auto-generated title from first message
    title = db.Column(db.String(255), nullable=True, default="New Chat")

    # Source lock — once user selects a source, remember it for the session
    # Values: None (auto), "renvora_knowledge", "uploaded_document", "general_ai"
    active_source = db.Column(db.String(50), nullable=True)

    # FK to the specific document selected (if source is uploaded_document)
    active_doc_id = db.Column(db.Integer, db.ForeignKey('user_documents.id', ondelete='SET NULL'), nullable=True)
    active_doc_name = db.Column(db.String(255), nullable=True)

    # Share feature
    is_shared = db.Column(db.Boolean, default=False)
    share_token = db.Column(db.String(36), unique=True, nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('chat_sessions', lazy=True, cascade="all, delete"))
    messages = db.relationship('ChatLog', backref='session', lazy=True, cascade="all, delete")

    def generate_share_token(self):
        self.share_token = str(uuid.uuid4())
        self.is_shared = True
        return self.share_token

    def __repr__(self):
        return f"<ChatSession {self.id} user={self.user_id} title='{self.title}'>"
