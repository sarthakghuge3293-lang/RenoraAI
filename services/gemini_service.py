from services.ai_engine import ai_engine

def generate_response(user_message, collection_name, chat_history=None, active_pdf=None):
    return ai_engine.generate_response(
        user_message,
        collection_name,
        chat_history,
        active_pdf
    )