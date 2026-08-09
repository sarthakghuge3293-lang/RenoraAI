from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    flash,
    url_for,
)

from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models.user import db, User
from models.user_document import UserDocument
from models.knowledge import KnowledgeFile
from models.chat_log import ChatLog
from models.ai_settings import AISettings

from services.document_reader import DocumentReader
from services.chunker import TextChunker
from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore

from datetime import datetime, timedelta

import os
import shutil


# ============================================================
# ADMIN BLUEPRINT
# ============================================================

admin = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
)


# ============================================================
# CONSTANTS
# ============================================================

COMPANY_KNOWLEDGE_COLLECTION = "renvora_knowledge_v2"

COMPANY_UPLOAD_FOLDER = "knowledge/documents"

ALLOWED_COMPANY_EXTENSIONS = {
    "pdf",
    "xlsx",
    "csv",
    "docx",
    "pptx",
}


# ============================================================
# SECURITY
# ============================================================

def require_super_admin(f):
    """
    Allow access only to authenticated super admins.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if (
            "admin_id" not in session
            or session.get("admin_role") != "super_admin"
        ):
            flash(
                "Unauthorized Access. Super Admin role required.",
                "danger",
            )

            return redirect(
                url_for("admin.login")
            )

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# HELPERS
# ============================================================

def allowed_company_file(filename):
    """
    Check whether a company knowledge file is supported.
    """

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_COMPANY_EXTENSIONS


def get_company_upload_path():
    """
    Return company knowledge upload directory.
    """

    os.makedirs(
        COMPANY_UPLOAD_FOLDER,
        exist_ok=True,
    )

    return COMPANY_UPLOAD_FOLDER


def get_chroma_client():
    """
    Return the local persistent ChromaDB client.
    """

    import chromadb

    return chromadb.PersistentClient(
        path="database/chroma"
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@admin.route(
    "/login",
    methods=["GET", "POST"],
)
def login():

    # Already logged in
    if (
        "admin_id" in session
        and session.get("admin_role") == "super_admin"
    ):
        return redirect(
            url_for("admin.dashboard")
        )

    if request.method == "POST":

        email = (
            request.form.get("email")
            or ""
        ).strip()

        password = (
            request.form.get("password")
            or ""
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if not user:

            flash(
                "Invalid Email or Password",
                "danger",
            )

            return redirect(
                url_for("admin.login")
            )

        if not check_password_hash(
            user.password,
            password,
        ):

            flash(
                "Invalid Email or Password",
                "danger",
            )

            return redirect(
                url_for("admin.login")
            )

        if user.role != "super_admin":

            flash(
                "Access Denied. Super Admin role required.",
                "danger",
            )

            return redirect(
                url_for("admin.login")
            )

        # Store admin session
        session["admin_id"] = user.id
        session["admin_name"] = user.name
        session["admin_email"] = user.email
        session["admin_role"] = user.role

        flash(
            "Welcome to Renvora Admin Panel",
            "success",
        )

        return redirect(
            url_for("admin.dashboard")
        )

    return render_template(
        "admin/login.html"
    )


# ============================================================
# ADMIN ROOT
# ============================================================

@admin.route("/")
@require_super_admin
def index():

    return redirect(
        url_for("admin.dashboard")
    )


# ============================================================
# DASHBOARD
# ============================================================

@admin.route("/dashboard")
@require_super_admin
def dashboard():

    total_users = User.query.count()

    total_docs = UserDocument.query.count()

    company_files = KnowledgeFile.query.count()

    today = datetime.now().date()

    today_chats = (
        ChatLog.query
        .filter(
            db.func.date(
                ChatLog.timestamp
            ) == today
        )
        .count()
    )

    recent_company_docs = (
        KnowledgeFile.query
        .order_by(
            KnowledgeFile.uploaded_at.desc()
        )
        .limit(5)
        .all()
    )

    recent_user_docs = (
        UserDocument.query
        .order_by(
            UserDocument.uploaded_at.desc()
        )
        .limit(5)
        .all()
    )

    # Current model does not maintain a complete
    # storage accounting system, so calculate an
    # approximate value from stored file sizes.
    company_size = 0

    for document in recent_company_docs:

        try:
            company_size += (
                document.file_size or 0
            )
        except Exception:
            pass

    user_size = 0

    for document in recent_user_docs:

        try:
            user_size += (
                document.file_size or 0
            )
        except Exception:
            pass

    total_size = company_size + user_size

    if total_size >= 1024 * 1024:

        storage_usage = (
            f"{total_size / (1024 * 1024):.1f} MB"
        )

    elif total_size >= 1024:

        storage_usage = (
            f"{total_size / 1024:.1f} KB"
        )

    else:

        storage_usage = (
            f"{total_size} B"
        )

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


# ============================================================
# RESET CHROMADB
# ============================================================

@admin.route(
    "/reset_chromadb",
    methods=["POST"],
)
@require_super_admin
def reset_chromadb():

    try:

        client = get_chroma_client()

        # Delete old collections if they exist
        old_collections = [
            "renvora_knowledge",
            "renvora_knowledge_v2",
        ]

        for collection_name in old_collections:

            try:

                client.delete_collection(
                    name=collection_name
                )

            except Exception:
                # Collection may not exist
                pass

        # Create fresh Renvora knowledge collection
        client.get_or_create_collection(
            name=COMPANY_KNOWLEDGE_COLLECTION
        )

        flash(
            "Renvora Knowledge Base reset successfully. "
            "You can now upload fresh company documents.",
            "success",
        )

    except Exception as e:

        print(
            "[Admin] ChromaDB reset error:",
            e,
        )

        flash(
            f"Error resetting ChromaDB: {e}",
            "danger",
        )

    return redirect(
        url_for("admin.company")
    )


# ============================================================
# COMPANY KNOWLEDGE
# ============================================================

@admin.route(
    "/company",
    methods=["GET", "POST"],
)
@require_super_admin
def company():

    upload_folder = get_company_upload_path()

    if request.method == "POST":

        action = (
            request.form.get("action")
            or ""
        ).strip()

        # ----------------------------------------------------
        # DELETE COMPANY DOCUMENT
        # ----------------------------------------------------

        if action == "delete":

            doc_id = request.form.get(
                "doc_id"
            )

            doc = KnowledgeFile.query.get(
                doc_id
            )

            if not doc:

                flash(
                    "Company document not found.",
                    "danger",
                )

                return redirect(
                    url_for("admin.company")
                )

            try:

                # Remove document vectors
                try:

                    vector_store = VectorStore(
                        COMPANY_KNOWLEDGE_COLLECTION
                    )

                    vector_store.delete_by_pdf_name(
                        doc.file_name
                    )

                except Exception as vector_error:

                    print(
                        "[Admin] ChromaDB delete error:",
                        vector_error,
                    )

                # Remove physical document
                filepath = os.path.join(
                    upload_folder,
                    doc.file_name,
                )

                if os.path.exists(filepath):

                    try:
                        os.remove(filepath)

                    except Exception as file_error:

                        print(
                            "[Admin] Physical file delete error:",
                            file_error,
                        )

                # Remove database record
                db.session.delete(doc)

                db.session.commit()

                flash(
                    "Company document deleted successfully.",
                    "success",
                )

            except Exception as e:

                db.session.rollback()

                print(
                    "[Admin] Company document delete error:",
                    e,
                )

                flash(
                    f"Unable to delete document: {e}",
                    "danger",
                )

        # ----------------------------------------------------
        # RENAME COMPANY DOCUMENT
        # ----------------------------------------------------

        elif action == "rename":

            doc_id = request.form.get(
                "doc_id"
            )

            new_name = (
                request.form.get(
                    "new_name"
                )
                or ""
            ).strip()

            doc = KnowledgeFile.query.get(
                doc_id
            )

            if not doc:

                flash(
                    "Company document not found.",
                    "danger",
                )

            elif not new_name:

                flash(
                    "New document name is required.",
                    "danger",
                )

            else:

                try:

                    doc.original_name = new_name

                    db.session.commit()

                    flash(
                        "Document renamed successfully.",
                        "success",
                    )

                except Exception as e:

                    db.session.rollback()

                    flash(
                        f"Unable to rename document: {e}",
                        "danger",
                    )

        return redirect(
            url_for("admin.company")
        )

    # GET
    docs = (
        KnowledgeFile.query
        .order_by(
            KnowledgeFile.uploaded_at.desc()
        )
        .all()
    )

    return render_template(
        "admin/knowledge.html",
        docs=docs,
    )


# ============================================================
# COMPANY KNOWLEDGE UPLOAD
# ============================================================

@admin.route(
    "/company/upload",
    methods=["POST"],
)
@require_super_admin
def company_upload():

    upload_folder = get_company_upload_path()

    if "document" not in request.files:

        flash(
            "Please select a document.",
            "danger",
        )

        return redirect(
            url_for("admin.company")
        )

    file = request.files["document"]

    if not file or not file.filename:

        flash(
            "No file selected.",
            "danger",
        )

        return redirect(
            url_for("admin.company")
        )

    original_filename = file.filename

    if not allowed_company_file(
        original_filename
    ):

        flash(
            "Unsupported file type. "
            "Supported: PDF, XLSX, CSV, DOCX, PPTX.",
            "danger",
        )

        return redirect(
            url_for("admin.company")
        )

    filename = secure_filename(
        original_filename
    )

    if not filename:

        flash(
            "Invalid file name.",
            "danger",
        )

        return redirect(
            url_for("admin.company")
        )

    filepath = os.path.join(
        upload_folder,
        filename,
    )

    # Avoid accidentally overwriting an existing file
    if os.path.exists(filepath):

        base, extension = os.path.splitext(
            filename
        )

        counter = 1

        while os.path.exists(filepath):

            filename = (
                f"{base}_{counter}{extension}"
            )

            filepath = os.path.join(
                upload_folder,
                filename,
            )

            counter += 1

    try:

        # ----------------------------------------------------
        # SAVE FILE
        # ----------------------------------------------------

        file.save(filepath)

        print(
            f"[Admin] Company document saved: {filepath}"
        )

        # ----------------------------------------------------
        # READ DOCUMENT
        # ----------------------------------------------------

        document_reader = DocumentReader()

        pages = document_reader.read_document(
            filepath,
            original_filename,
        )

        if not pages:

            raise ValueError(
                "No readable text found in the document."
            )

        print(
            f"[Admin] Read {len(pages)} pages/sections."
        )

        # ----------------------------------------------------
        # CHUNK DOCUMENT
        # ----------------------------------------------------

        chunker = TextChunker()

        chunks = chunker.chunk_document(
            filename,
            pages,
        )

        if not chunks:

            raise ValueError(
                "Document could not be divided into readable chunks."
            )

        print(
            f"[Admin] Created {len(chunks)} chunks."
        )

        # ----------------------------------------------------
        # CREATE EMBEDDINGS
        # ----------------------------------------------------

        embedding_engine = EmbeddingEngine()

        embedded_chunks = (
            embedding_engine.create_embeddings(
                chunks
            )
        )

        if not embedded_chunks:

            raise ValueError(
                "No embeddings were created for this document."
            )

        print(
            f"[Admin] Created {len(embedded_chunks)} embeddings."
        )

        # ----------------------------------------------------
        # STORE IN RENVORA KNOWLEDGE BASE
        # ----------------------------------------------------

        vector_store = VectorStore(
            COMPANY_KNOWLEDGE_COLLECTION
        )

        vector_store.add_chunks(
            embedded_chunks
        )

        print(
            "[Admin] Document indexed in "
            f"{COMPANY_KNOWLEDGE_COLLECTION}"
        )

        # ----------------------------------------------------
        # DATABASE RECORD
        # ----------------------------------------------------

        extension = (
            os.path.splitext(
                filename
            )[1]
            .lower()
            .replace(".", "")
        )

        data = KnowledgeFile(
            file_name=filename,
            original_name=original_filename,
            file_type=extension,
            file_size=os.path.getsize(
                filepath
            ),
            uploaded_by=session["admin_id"],
        )

        db.session.add(data)

        db.session.commit()

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        flash(
            "Document uploaded and indexed successfully. "
            f"Pages: {len(pages)} | "
            f"Chunks: {len(chunks)} | "
            f"Embeddings: {len(embedded_chunks)}",
            "success",
        )

    except Exception as e:

        # Rollback DB
        try:
            db.session.rollback()
        except Exception:
            pass

        # If indexing failed, don't leave a broken file
        if os.path.exists(filepath):

            try:
                os.remove(filepath)

            except Exception as cleanup_error:

                print(
                    "[Admin] Upload cleanup error:",
                    cleanup_error,
                )

        print(
            "[Admin] Company AI indexing error:",
            e,
        )

        flash(
            f"Document indexing failed: {e}",
            "danger",
        )

    return redirect(
        url_for("admin.company")
    )


# ============================================================
# USER DOCUMENTS
# ============================================================

@admin.route(
    "/documents",
    methods=["GET", "POST"],
)
@require_super_admin
def documents():

    if request.method == "POST":

        action = (
            request.form.get("action")
            or ""
        ).strip()

        if action == "delete":

            doc_id = request.form.get(
                "doc_id"
            )

            doc = UserDocument.query.get(
                doc_id
            )

            if not doc:

                flash(
                    "User document not found.",
                    "danger",
                )

                return redirect(
                    url_for("admin.documents")
                )

            try:

                db.session.delete(doc)

                db.session.commit()

                flash(
                    "User document deleted.",
                    "success",
                )

            except Exception as e:

                db.session.rollback()

                flash(
                    f"Unable to delete user document: {e}",
                    "danger",
                )

        return redirect(
            url_for("admin.documents")
        )

    docs = (
        UserDocument.query
        .order_by(
            UserDocument.uploaded_at.desc()
        )
        .all()
    )

    users = {
        user.id: user.name
        for user in User.query.all()
    }

    return render_template(
        "admin/user_documents.html",
        docs=docs,
        users=users,
    )


# ============================================================
# USERS
# ============================================================

@admin.route(
    "/users",
    methods=["GET", "POST"],
)
@require_super_admin
def users():

    if request.method == "POST":

        action = (
            request.form.get("action")
            or ""
        ).strip()

        user_id = request.form.get(
            "user_id"
        )

        user = User.query.get(
            user_id
        )

        if not user:

            flash(
                "User not found.",
                "danger",
            )

            return redirect(
                url_for("admin.users")
            )

        # ----------------------------------------------------
        # DELETE USER
        # ----------------------------------------------------

        if action == "delete":

            # Never allow deleting super admin
            if user.role == "super_admin":

                flash(
                    "Super Admin cannot be deleted.",
                    "danger",
                )

            else:

                try:

                    db.session.delete(user)

                    db.session.commit()

                    flash(
                        "User deleted successfully.",
                        "success",
                    )

                except Exception as e:

                    db.session.rollback()

                    flash(
                        f"Unable to delete user: {e}",
                        "danger",
                    )

        # ----------------------------------------------------
        # RESET PASSWORD
        # ----------------------------------------------------

        elif action == "reset_password":

            new_password = (
                request.form.get(
                    "new_password"
                )
                or ""
            )

            if not new_password:

                flash(
                    "New password is required.",
                    "danger",
                )

            else:

                try:

                    user.password = (
                        generate_password_hash(
                            new_password
                        )
                    )

                    db.session.commit()

                    flash(
                        "Password reset successfully.",
                        "success",
                    )

                except Exception as e:

                    db.session.rollback()

                    flash(
                        f"Unable to reset password: {e}",
                        "danger",
                    )

        return redirect(
            url_for("admin.users")
        )

    all_users = (
        User.query
        .order_by(
            User.id.desc()
        )
        .all()
    )

    user_stats = []

    for user in all_users:

        doc_count = (
            UserDocument.query
            .filter_by(
                user_id=user.id
            )
            .count()
        )

        chat_count = (
            ChatLog.query
            .filter_by(
                user_id=user.id
            )
            .count()
        )

        user_stats.append(
            {
                "user": user,
                "doc_count": doc_count,
                "chat_count": chat_count,
            }
        )

    return render_template(
        "admin/users.html",
        user_stats=user_stats,
    )


# ============================================================
# ANALYTICS
# ============================================================

@admin.route("/analytics")
@require_super_admin
def analytics():

    total_docs = UserDocument.query.count()

    total_users = User.query.count()

    total_company_docs = (
        KnowledgeFile.query.count()
    )

    total_chats = (
        ChatLog.query.count()
    )

    # --------------------------------------------------------
    # Last 7 days chat statistics
    # --------------------------------------------------------

    chat_stats = []

    for i in range(6, -1, -1):

        current_date = (
            datetime.now().date()
            - timedelta(days=i)
        )

        count = (
            ChatLog.query
            .filter(
                db.func.date(
                    ChatLog.timestamp
                ) == current_date
            )
            .count()
        )

        chat_stats.append(
            {
                "date": current_date.strftime(
                    "%b %d"
                ),
                "count": count,
            }
        )

    # --------------------------------------------------------
    # Most active users
    # --------------------------------------------------------

    active_users = (
        db.session.query(
            ChatLog.user_id,
            db.func.count(
                ChatLog.id
            ).label("total_chats"),
        )
        .group_by(
            ChatLog.user_id
        )
        .order_by(
            db.text(
                "total_chats DESC"
            )
        )
        .limit(5)
        .all()
    )

    users = {
        user.id: user.name
        for user in User.query.all()
    }

    active_users_data = []

    for active_user in active_users:

        active_users_data.append(
            {
                "name": users.get(
                    active_user.user_id,
                    "Unknown",
                ),
                "chats": active_user.total_chats,
            }
        )

    return render_template(
        "admin/analytics.html",
        total_docs=total_docs,
        total_users=total_users,
        total_company_docs=total_company_docs,
        total_chats=total_chats,
        chat_stats=chat_stats,
        active_users=active_users_data,
    )


# ============================================================
# AI SETTINGS
# ============================================================

@admin.route(
    "/settings",
    methods=["GET", "POST"],
)
@require_super_admin
def settings():

    settings = (
        AISettings.query.first()
    )

    if not settings:

        settings = AISettings()

        db.session.add(settings)

        db.session.commit()

    if request.method == "POST":

        try:

            settings.llm_model = (
                request.form.get(
                    "llm_model"
                )
            )

            settings.embedding_model = (
                request.form.get(
                    "embedding_model"
                )
            )

            settings.chunk_size = int(
                request.form.get(
                    "chunk_size",
                    1000,
                )
            )

            settings.chunk_overlap = int(
                request.form.get(
                    "chunk_overlap",
                    200,
                )
            )

            settings.top_k = int(
                request.form.get(
                    "top_k",
                    5,
                )
            )

            settings.max_upload_size_mb = int(
                request.form.get(
                    "max_upload_size_mb",
                    50,
                )
            )

            settings.supported_file_types = (
                request.form.get(
                    "supported_file_types"
                )
            )

            db.session.commit()

            flash(
                "AI Settings updated successfully.",
                "success",
            )

            return redirect(
                url_for("admin.settings")
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f"Unable to update AI settings: {e}",
                "danger",
            )

    return render_template(
        "admin/settings.html",
        settings=settings,
    )


# ============================================================
# CHAT LOGS
# ============================================================

@admin.route("/chat-logs")
@require_super_admin
def chat_logs():

    logs = (
        ChatLog.query
        .order_by(
            ChatLog.timestamp.desc()
        )
        .limit(100)
        .all()
    )

    users = {
        user.id: user.name
        for user in User.query.all()
    }

    return render_template(
        "admin/chat_history.html",
        logs=logs,
        users=users,
    )


# ============================================================
# SYSTEM LOGS
# ============================================================

@admin.route("/system-logs")
@require_super_admin
def system_logs():

    return render_template(
        "admin/system_logs.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@admin.route("/logout")
def logout():

    session.pop(
        "admin_id",
        None,
    )

    session.pop(
        "admin_name",
        None,
    )

    session.pop(
        "admin_email",
        None,
    )

    session.pop(
        "admin_role",
        None,
    )

    flash(
        "Logged Out Successfully",
        "success",
    )

    return redirect(
        url_for("admin.login")
    )