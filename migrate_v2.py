"""
migrate_v2.py
─────────────
Safe migration: adds new columns to existing tables without data loss.
Run once after deploying the updated models.

Usage:
    python migrate_v2.py
"""

import sqlite3
import os
import sys

# ──────────────────────────────────────────────────────────────────────────────
# Config — update DB_PATH if your database lives elsewhere
# ──────────────────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "renvora.db")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def safe_add_column(cursor, table, column, definition):
    if not column_exists(cursor, table, column):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"  [+] Added: {table}.{column}")
    else:
        print(f"  [=] Skip (exists): {table}.{column}")


def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        print("   Run the app once first so SQLAlchemy creates the DB.")
        sys.exit(1)

    print(f"\n[*] Running V2 migration on: {DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── chat_sessions ────────────────────────────────────────────────────────
    print("[Table] chat_sessions:")
    safe_add_column(cursor, "chat_sessions", "session_uuid",   "TEXT")
    safe_add_column(cursor, "chat_sessions", "title",          "TEXT DEFAULT 'New Chat'")
    safe_add_column(cursor, "chat_sessions", "active_source",  "TEXT")
    safe_add_column(cursor, "chat_sessions", "active_doc_id",  "INTEGER")
    safe_add_column(cursor, "chat_sessions", "active_doc_name","TEXT")
    safe_add_column(cursor, "chat_sessions", "is_shared",      "INTEGER DEFAULT 0")
    safe_add_column(cursor, "chat_sessions", "share_token",    "TEXT")
    safe_add_column(cursor, "chat_sessions", "updated_at",     "DATETIME DEFAULT CURRENT_TIMESTAMP")

    # ── chat_logs ────────────────────────────────────────────────────────────
    print("\n[Table] chat_logs:")
    safe_add_column(cursor, "chat_logs", "source_used",     "TEXT")
    safe_add_column(cursor, "chat_logs", "intent_detected", "TEXT")

    # ── user_documents ───────────────────────────────────────────────────────
    print("\n[Table] user_documents:")
    safe_add_column(cursor, "user_documents", "description", "TEXT")

    # ── indexes ──────────────────────────────────────────────────────────────
    print("\n[Indexes]:")
    indexes = [
        ("idx_chat_sessions_uuid",   "CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_sessions_uuid ON chat_sessions (session_uuid)"),
        ("idx_chat_sessions_token",  "CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_sessions_token ON chat_sessions (share_token)"),
        ("idx_chat_sessions_user",   "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions (user_id)"),
        ("idx_chat_logs_session",    "CREATE INDEX IF NOT EXISTS idx_chat_logs_session ON chat_logs (session_id)"),
        ("idx_chat_logs_timestamp",  "CREATE INDEX IF NOT EXISTS idx_chat_logs_timestamp ON chat_logs (timestamp)"),
        ("idx_user_documents_user",  "CREATE INDEX IF NOT EXISTS idx_user_documents_user ON user_documents (user_id)"),
    ]
    for name, sql in indexes:
        try:
            cursor.execute(sql)
            print(f"  [+] Index: {name}")
        except Exception as e:
            print(f"  [!] Index {name}: {e}")

    conn.commit()
    conn.close()

    print("\n[DONE] Migration V2 complete!\n")


if __name__ == "__main__":
    run_migration()
