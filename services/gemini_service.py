"""
services/gemini_service.py
──────────────────────────
Thin wrapper around ai_engine. Updated to use new interface.
"""

from services.ai_engine import ai_engine


def generate_response(
    user_message: str,
    user_id: int,
    chat_history: list = None,
    locked_source: str = None,
    locked_doc_name: str = None,
    user_documents: list = None,
) -> dict:
    """
    Returns dict with keys:
        reply, intent, source_used, lock_source, lock_doc_name,
        suggested_sources, needs_clarification
    """
    return ai_engine.generate_response(
        user_message=user_message,
        user_id=user_id,
        chat_history=chat_history,
        locked_source=locked_source,
        locked_doc_name=locked_doc_name,
        user_documents=user_documents,
    )