import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")

def get_groq_client():
    if not API_KEY:
        return None
    return Groq(api_key=API_KEY)

def detect_intent(message, has_uploaded_document=False, chat_history=None):
    client = get_groq_client()
    if not client:
        return {"intent": "general_knowledge", "confidence": 1.0, "clarification_question": ""}

    sources_str = "Renvora Company Knowledge, General Knowledge"
    if has_uploaded_document:
        sources_str += ", Uploaded Document"
        
    chat_context = ""
    if chat_history:
        chat_context = "Recent Conversation Context:\n"
        for msg in chat_history[-6:]:
            chat_context += f"{msg['role'].capitalize()}: {msg['content']}\n"

    system_prompt = f"""
You are an intent detection engine for Renvora AI. Your job is to classify the user's message to determine which data source should be used to answer it.

Available sources: {sources_str}

{chat_context}

Intent categories:
- "uploaded_document" (User explicitly refers to the uploaded document, or the question is obviously about uploaded data)
- "renvora_knowledge" (User asks about Renvora, its services, team, or company details)
- "general_knowledge" (General knowledge questions like "What is Python?", greetings, etc.)
- "previous_conversation" (User refers to something said earlier)
- "ambiguous" (The question could refer to multiple sources. e.g. "CEO" when there is both an uploaded document and company knowledge)

GOLDEN RULE:
If the user's question is ambiguous and could logically refer to more than one source (e.g. asking "Who are the team members?" while an uploaded document is present), and the Recent Conversation Context doesn't clarify it, you MUST classify it as "ambiguous".
Do NOT guess. If confidence is below 0.90, classify as "ambiguous".

If "ambiguous", you MUST provide a "clarification_question" asking the user which source they meant.
Example: "Which team are you referring to? The uploaded document or Renvora?"

Output ONLY valid JSON in the following format:
{{
    "intent": "<category>",
    "confidence": 0.95,
    "clarification_question": "<question or empty string>"
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.1,
            max_tokens=256,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)
        return {
            "intent": result.get("intent", "general_knowledge"),
            "confidence": float(result.get("confidence", 1.0)),
            "clarification_question": result.get("clarification_question", "")
        }
    except Exception as e:
        print("Intent Detection Error:", e)
        return {"intent": "general_knowledge", "confidence": 1.0, "clarification_question": ""}