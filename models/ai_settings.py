from models.user import db

class AISettings(db.Model):
    __tablename__ = "ai_settings"

    id = db.Column(db.Integer, primary_key=True)
    llm_model = db.Column(db.String(100), default="llama3-8b-8192")
    embedding_model = db.Column(db.String(100), default="BAAI/bge-small-en-v1.5")
    chunk_size = db.Column(db.Integer, default=1000)
    chunk_overlap = db.Column(db.Integer, default=200)
    top_k = db.Column(db.Integer, default=5)
    max_upload_size_mb = db.Column(db.Integer, default=50)
    supported_file_types = db.Column(db.String(255), default="pdf,xlsx,csv,docx,pptx")

    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
