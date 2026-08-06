from services.ai_engine import ai_engine

def generate_response(user_message, collection_name):
    return ai_engine.generate_response(
        user_message,
        collection_name
    )