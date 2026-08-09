"""
Renvora AI - Fresh Data Reset

WARNING:
This deletes application DATA, not database tables/schema.

Deleted:
- Chat logs
- Chat sessions
- User documents
- Users

Also removes local uploaded files.

Run only when you intentionally want a fresh start.
"""

import os
import shutil

from app import app
from models.user import db
from models.user import User
from models.user_document import UserDocument
from models.chat_session import ChatSession
from models.chat_log import ChatLog


def reset_database():
    print("=" * 60)
    print("        RENVORA AI - DATA RESET")
    print("=" * 60)
    print()
    print("This will DELETE:")
    print("  - All users")
    print("  - All chat sessions")
    print("  - All chat logs")
    print("  - All uploaded document records")
    print("  - Local uploaded files")
    print()

    confirmation = input(
        "Type DELETE to continue: "
    ).strip()

    if confirmation != "DELETE":
        print()
        print("Reset cancelled.")
        return

    with app.app_context():

        try:
            print()
            print("[1/5] Deleting chat logs...")

            deleted_logs = ChatLog.query.delete(
                synchronize_session=False
            )

            db.session.commit()

            print(
                f"      Deleted {deleted_logs} chat logs."
            )

            print("[2/5] Deleting chat sessions...")

            deleted_sessions = ChatSession.query.delete(
                synchronize_session=False
            )

            db.session.commit()

            print(
                f"      Deleted {deleted_sessions} chat sessions."
            )

            print("[3/5] Deleting user documents...")

            deleted_documents = UserDocument.query.delete(
                synchronize_session=False
            )

            db.session.commit()

            print(
                f"      Deleted {deleted_documents} documents."
            )

            print("[4/5] Deleting users...")

            deleted_users = User.query.delete(
                synchronize_session=False
            )

            db.session.commit()

            print(
                f"      Deleted {deleted_users} users."
            )

            print("[5/5] Removing uploaded files...")

            upload_folders = [
                "uploads/user_documents",
                "uploads",
            ]

            removed_paths = set()

            for folder in upload_folders:

                if os.path.exists(folder):

                    # Don't remove the entire uploads directory
                    # if it contains unrelated application files.
                    if folder == "uploads/user_documents":

                        shutil.rmtree(
                            folder,
                            ignore_errors=True
                        )

                        removed_paths.add(folder)

            os.makedirs(
                "uploads/user_documents",
                exist_ok=True
            )

            print(
                f"      Cleaned uploaded document storage."
            )

            print()
            print("=" * 60)
            print("             RESET COMPLETE")
            print("=" * 60)
            print()
            print("Database schema: PRESERVED")
            print("Users:           0")
            print("Chat sessions:   0")
            print("Chat logs:       0")
            print("Documents:       0")
            print()
            print(
                "Next step: Create a fresh Admin account."
            )
            print()

        except Exception as e:

            db.session.rollback()

            print()
            print("=" * 60)
            print("RESET FAILED")
            print("=" * 60)
            print()
            print(f"ERROR: {e}")
            print()

            raise


if __name__ == "__main__":
    reset_database()