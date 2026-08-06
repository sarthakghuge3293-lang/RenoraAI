from models.user import db
from datetime import datetime

class UserDocument(db.Model):
    __tablename__ = "user_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    collection_name = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    doc_type = db.Column(db.String(10), nullable=False, default='pdf')
    page_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='ready')

    user = db.relationship('User', backref=db.backref('documents', lazy=True, cascade="all, delete"))

    def __repr__(self):
        return f"<UserDocument {self.original_name}>"
