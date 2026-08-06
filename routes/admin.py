from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from models.user import db, User
from models.user_document import UserDocument
from models.knowledge import KnowledgeFile
from models.chat_log import ChatLog
from models.ai_settings import AISettings
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from services.document_reader import DocumentReader
from services.chunker import TextChunker
from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore

admin = Blueprint("admin", __name__, url_prefix="/admin")


# ==========================================
# Security Decorator
# ==========================================
def require_super_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session or session.get("admin_role") != "super_admin":
            flash("Unauthorized Access. Super Admin role required.", "danger")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)

    return decorated_function


# ==========================================
# Admin Login
# ==========================================
@admin.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session and session.get("admin_role") == "super_admin":
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Invalid Email or Password", "danger")
            return redirect(url_for("admin.login"))

        if not check_password_hash(user.password, password):
            flash("Invalid Email or Password", "danger")
            return redirect(url_for("admin.login"))

        if user.role != "super_admin":
            flash("Access Denied. Super Admin role required.", "danger")
            return redirect(url_for("admin.login"))

        session["admin_id"] = user.id
        session["admin_name"] = user.name
        session["admin_email"] = user.email
        session["admin_role"] = user.role

        flash("Welcome to Renvora Admin Panel", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html")


# ==========================================
# Root Admin
# ==========================================
@admin.route("/")
@require_super_admin
def index():
    return redirect(url_for("admin.dashboard"))


# ==========================================
# Dashboard
# ==========================================
@admin.route("/dashboard")
@require_super_admin
def dashboard():
    total_users = User.query.count()
    total_docs = UserDocument.query.count()
    company_files = KnowledgeFile.query.count()

    # Today's chats
    today = datetime.now().date()
    today_chats = ChatLog.query.filter(db.func.date(ChatLog.timestamp) == today).count()

    # Recent Uploads
    recent_company_docs = (
        KnowledgeFile.query.order_by(KnowledgeFile.uploaded_at.desc()).limit(5).all()
    )
    recent_user_docs = (
        UserDocument.query.order_by(UserDocument.uploaded_at.desc()).limit(5).all()
    )

    # Some mock storage logic (e.g. 1.2 GB) since we don't track file sizes for everything perfectly yet
    storage_usage = f"{company_files * 2 + total_docs * 1.5:.1f} MB"

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_docs=total_docs,
        company_files=company_files,
        today_chats=today_chats,
        recent_company_docs=recent_company_docs,
        recent_user_docs=recent_user_docs,
        storage_usage=storage_usage,
    )


# ==========================================
# Company Knowledge
# ==========================================
@admin.route("/company", methods=["GET", "POST"])
@require_super_admin
def company():
    UPLOAD_FOLDER = "knowledge/documents"

    if request.method == "POST":
        action = request.form.get("action")

        if action == "delete":
            doc_id = request.form.get("doc_id")
            doc = KnowledgeFile.query.get(doc_id)
            if doc:
                try:
                    vector_store = VectorStore("renvora_knowledge")
                    vector_store.delete_by_pdf_name(doc.file_name)
                except Exception as e:
                    print("Error deleting from ChromaDB:", e)

                filepath = os.path.join(UPLOAD_FOLDER, doc.file_name)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        print("Error deleting physical file:", e)

                db.session.delete(doc)
                db.session.commit()
                flash("Document deleted.", "success")
        elif action == "rename":
            doc_id = request.form.get("doc_id")
            new_name = request.form.get("new_name")
            doc = KnowledgeFile.query.get(doc_id)
            if doc and new_name:
                doc.original_name = new_name
                db.session.commit()
                flash("Document renamed.", "success")

        return redirect(url_for("admin.company"))

    docs = KnowledgeFile.query.all()
    return render_template("admin/knowledge.html", docs=docs)


# ==========================================
# Company Knowledge Upload
# ==========================================
@admin.route("/company/upload", methods=["POST"])
@require_super_admin
def company_upload():
    UPLOAD_FOLDER = "knowledge/documents"
    ALLOWED_EXTENSIONS = {"pdf", "xlsx", "csv", "docx", "pptx"}

    def allowed_file(filename):
        return (
            "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
        )

    if "document" not in request.files:
        flash("Please select a document.", "danger")
        return redirect(url_for("admin.company"))

    file = request.files["document"]
    if file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("admin.company"))

    if file and allowed_file(file.filename):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        try:
            document_reader = DocumentReader()
            chunker = TextChunker()
            embedding_engine = EmbeddingEngine()
            # Company knowledge uses 'renvora_knowledge'
            vector_store = VectorStore("renvora_knowledge")

            pages = document_reader.read_document(filepath, file.filename)
            chunks = chunker.chunk_document(filename, pages)

            if not chunks:
                os.remove(filepath)
                flash("No readable text found in document.", "danger")
                return redirect(url_for("admin.company"))

            embedded_chunks = embedding_engine.create_embeddings(chunks)
            vector_store.add_chunks(embedded_chunks)

            ext = os.path.splitext(file.filename)[1].lower().replace(".", "")

            data = KnowledgeFile(
                file_name=filename,
                original_name=file.filename,
                file_type=ext,
                file_size=os.path.getsize(filepath),
                uploaded_by=session["admin_id"],
            )
            db.session.add(data)
            db.session.commit()

            flash(
                f"Document Uploaded & Indexed! Pages: {len(pages)} | Chunks: {len(chunks)}",
                "success",
            )
        except Exception as e:
            print("AI Index Error:", e)
            flash(f"AI Index Error: {e}", "danger")

    else:
        flash("Unsupported file type.", "danger")

    return redirect(url_for("admin.company"))


# ==========================================
# User Documents
# ==========================================
@admin.route("/documents", methods=["GET", "POST"])
@require_super_admin
def documents():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            doc_id = request.form.get("doc_id")
            doc = UserDocument.query.get(doc_id)
            if doc:
                db.session.delete(doc)
                db.session.commit()
                flash("User document deleted.", "success")
        return redirect(url_for("admin.documents"))

    docs = UserDocument.query.all()
    # Need to match owner name
    users = {u.id: u.name for u in User.query.all()}
    return render_template("admin/user_documents.html", docs=docs, users=users)


# ==========================================
# Users
# ==========================================
@admin.route("/users", methods=["GET", "POST"])
@require_super_admin
def users():
    if request.method == "POST":
        action = request.form.get("action")
        user_id = request.form.get("user_id")
        user = User.query.get(user_id)

        if user:
            if action == "delete" and user.role != "super_admin":
                db.session.delete(user)
                db.session.commit()
                flash("User deleted.", "success")
            elif action == "reset_password":
                new_password = request.form.get("new_password")
                user.password = generate_password_hash(new_password)
                db.session.commit()
                flash("Password reset.", "success")
        return redirect(url_for("admin.users"))

    all_users = User.query.all()

    # Calculate stats per user
    user_stats = []
    for u in all_users:
        doc_count = UserDocument.query.filter_by(user_id=u.id).count()
        user_stats.append({"user": u, "doc_count": doc_count})

    return render_template("admin/users.html", user_stats=user_stats)


# ==========================================
# Analytics
# ==========================================
@admin.route("/analytics")
@require_super_admin
def analytics():
    total_docs = UserDocument.query.count()
    total_users = User.query.count()

    # Get last 7 days chats count
    chat_stats = []
    for i in range(6, -1, -1):
        d = datetime.now().date() - timedelta(days=i)
        count = ChatLog.query.filter(db.func.date(ChatLog.timestamp) == d).count()
        chat_stats.append({"date": d.strftime("%b %d"), "count": count})

    # Most active users
    active_users = (
        db.session.query(
            ChatLog.user_id, db.func.count(ChatLog.id).label("total_chats")
        )
        .group_by(ChatLog.user_id)
        .order_by(db.text("total_chats DESC"))
        .limit(5)
        .all()
    )

    users = {u.id: u.name for u in User.query.all()}
    active_users_data = [
        {"name": users.get(au.user_id, "Unknown"), "chats": au.total_chats}
        for au in active_users
    ]

    return render_template(
        "admin/analytics.html",
        total_docs=total_docs,
        total_users=total_users,
        chat_stats=chat_stats,
        active_users=active_users_data,
    )


# ==========================================
# AI Settings
# ==========================================
@admin.route("/settings", methods=["GET", "POST"])
@require_super_admin
def settings():
    settings = AISettings.query.first()
    if not settings:
        settings = AISettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == "POST":
        settings.llm_model = request.form.get("llm_model")
        settings.embedding_model = request.form.get("embedding_model")
        settings.chunk_size = int(request.form.get("chunk_size", 1000))
        settings.chunk_overlap = int(request.form.get("chunk_overlap", 200))
        settings.top_k = int(request.form.get("top_k", 5))
        settings.max_upload_size_mb = int(request.form.get("max_upload_size_mb", 50))
        settings.supported_file_types = request.form.get("supported_file_types")

        db.session.commit()
        flash("AI Settings updated successfully.", "success")
        return redirect(url_for("admin.settings"))

    return render_template("admin/settings.html", settings=settings)


# ==========================================
# Chat Logs
# ==========================================
@admin.route("/chat-logs")
@require_super_admin
def chat_logs():
    logs = ChatLog.query.order_by(ChatLog.timestamp.desc()).limit(100).all()
    users = {u.id: u.name for u in User.query.all()}
    return render_template("admin/chat_history.html", logs=logs, users=users)


# ==========================================
# Logout
# ==========================================
@admin.route("/logout")
def logout():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    session.pop("admin_email", None)
    session.pop("admin_role", None)
    flash("Logged Out Successfully", "success")
    return redirect(url_for("admin.login"))


# ==========================================
# System Logs
# ==========================================
@admin.route("/system-logs")
@require_super_admin
def system_logs():
    return render_template("admin/system_logs.html")
