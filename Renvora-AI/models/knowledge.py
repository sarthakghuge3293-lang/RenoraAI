from models.user import db


class KnowledgeFile(db.Model):

    __tablename__ = "knowledge_files"

    id = db.Column(db.Integer, primary_key=True)

    file_name = db.Column(db.String(255), nullable=False)

    original_name = db.Column(db.String(255), nullable=False)

    file_type = db.Column(db.String(50))

    file_size = db.Column(db.BigInteger)

    uploaded_by = db.Column(db.Integer)

    uploaded_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )