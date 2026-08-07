from models.user import db
from datetime import datetime


class UserDocument(db.Model):
    __tablename__ = "user_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # Internal filename (secure_filename result) — used as identifier in vector store
    file_name = db.Column(db.String(255), nullable=False)

    # Human-readable display name (may be renamed by user)
    original_name = db.Column(db.String(255), nullable=False)

    # Path on disk
    file_path = db.Column(db.String(512), nullable=False)

    # ChromaDB collection for this user: "user_{user_id}"
    collection_name = db.Column(db.String(255), nullable=False)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # File type: pdf, xlsx, csv, docx, pptx
    doc_type = db.Column(db.String(10), nullable=False, default='pdf')

    page_count = db.Column(db.Integer, default=0)

    # "Processing", "ready", "Failed: ..."
    status = db.Column(db.String(50), default='ready')

    # Auto-generated one-line description of document content (set after embedding)
    description = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('documents', lazy=True, cascade="all, delete"))

    def __repr__(self):
        return f"<UserDocument {self.original_name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "file_name": self.file_name,
            "original_name": self.original_name,
            "doc_type": self.doc_type,
            "page_count": self.page_count,
            "status": self.status,
            "description": self.description,
            "collection_name": self.collection_name,
            "uploaded_at": self.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if self.uploaded_at else None,
        }
