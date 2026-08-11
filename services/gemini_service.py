"""
services/gemini_service.py

Thin wrapper around the Renvora AI Engine.
Keeps the existing chat.py interface while forwarding
document/source locking information to the AI engine.
"""

from services.ai_engine import ai_engine


def generate_response(
    user_message: str,
    user_id: int,
    chat_history: list = None,
    locked_source: str = None,
    locked_doc_name: str = None,
    locked_doc_id: int = None,
    user_documents: list = None,
) -> dict:
    """
    Generate a response through the central Renvora AI Engine.

    Parameters
    ----------
    user_message:
        Current user question.

    user_id:
        Logged-in user's database ID.

    chat_history:
        Previous conversation messages.

    locked_source:
        Currently selected source, if any.

    locked_doc_name:
        Display name of the selected PDF.

    locked_doc_id:
        Internal database ID of the selected PDF.

        IMPORTANT:
        This is forwarded to AIEngine so document retrieval
        can be restricted to the exact selected document.

    user_documents:
        User's available documents.
    """

    return ai_engine.generate_response(
        user_message=user_message,
        user_id=user_id,
        chat_history=chat_history,
        locked_source=locked_source,
        locked_doc_name=locked_doc_name,
        locked_doc_id=locked_doc_id,
        user_documents=user_documents,
    )