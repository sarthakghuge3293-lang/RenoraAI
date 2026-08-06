from models.user import db

class ChatLog(db.Model):
    __tablename__ = "chat_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    collection_used = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
