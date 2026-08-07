"""
services/intent_detector.py
────────────────────────────
Classifies the user's intent so the AI can decide which source to retrieve from.

Improvements over v1:
- Passes actual document names (not just a boolean flag) so the LLM can be specific.
- Passes the session's locked source so reference questions ("use the PDF") resolve correctly.
- Significantly reduced false-positive "ambiguous" classifications via better examples.
- Returns `suggested_sources` list for the Flutter UI to render as tap buttons.
- Only classifies as "ambiguous" when the question genuinely could come from two distinct sources
  AND the chat history doesn't resolve which one.
"""

import os
import json

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_API_KEY = os.getenv("GROQ_API_KEY")


def _get_client():
    if not _API_KEY:
        return None
    return Groq(api_key=_API_KEY)


def detect_intent(
    message: str,
    has_uploaded_document: bool = False,
    chat_history: list = None,
    document_names: list = None,
    locked_source: str = None,
) -> dict:
    """
    Returns:
    {
        "intent": str,                  # see categories below
        "confidence": float,            # 0.0 – 1.0
        "clarification_question": str,  # empty unless intent == "ambiguous"
        "suggested_sources": list[str], # source options for UI chips
    }

    Intent categories:
        "general_knowledge"    - greetings, general questions, math, programming, etc.
        "renvora_knowledge"    - questions about Renvora Tech, its team, services, etc.
        "uploaded_document"    - questions about the user's own uploaded files
        "previous_conversation"- refers to something said in the conversation history
        "ambiguous"            - truly could be answered by 2+ sources equally
    """

    client = _get_client()
    if not client:
        return _default_response()

    # Build document listing string
    doc_list_str = ""
    if has_uploaded_document and document_names:
        doc_list_str = "User has uploaded the following documents:\n"
        for i, name in enumerate(document_names, 1):
            doc_list_str += f"  {i}. {name}\n"
    elif has_uploaded_document:
        doc_list_str = "User has uploaded at least one document (name unknown).\n"
    else:
        doc_list_str = "User has NOT uploaded any documents.\n"

    # Build conversation context (last 6 messages)
    conversation_str = ""
    if chat_history:
        conversation_str = "Recent conversation:\n"
        for msg in (chat_history or [])[-6:]:
            role = msg.get("role", "user").capitalize()
            conversation_str += f"  {role}: {msg.get('content', '')}\n"

    # Build locked source string
    locked_str = ""
    if locked_source:
        locked_str = f"\nNOTE: The user has already selected '{locked_source}' as their source for this session. If the message is a follow-up question, classify as '{locked_source}' with confidence 1.0.\n"

    system_prompt = f"""You are an intent detection engine for Renvora AI.

Your ONLY job is to classify the user's message and decide which data source the AI should retrieve from.

Available sources:
1. "renvora_knowledge"    — Renvora Tech company info (team, services, projects, history, etc.)
2. "uploaded_document"    — Files the user has personally uploaded
3. "general_knowledge"    — Generic facts, greetings, programming, science, math, etc.
4. "previous_conversation"— The answer is in the recent chat history
5. "ambiguous"            — The question CANNOT be resolved without asking the user

{doc_list_str}
{conversation_str}
{locked_str}

CLASSIFICATION RULES:
─────────────────────
1. If the message is a greeting, general question, or something clearly unrelated to any company or document → "general_knowledge" (confidence 1.0)

2. If the message explicitly mentions Renvora, the company, its team, services, CEO, projects → "renvora_knowledge" (confidence > 0.95)

3. If the message says "my document", "the file I uploaded", "the PDF", "the spreadsheet", or refers to specific content only in uploaded files → "uploaded_document" (confidence > 0.95)

4. If the message uses "this", "that", "you mentioned", "before", "earlier", "what you said" → "previous_conversation" (confidence 1.0)

5. ONLY classify as "ambiguous" if:
   - The user has at least 1 uploaded document, AND
   - Renvora knowledge ALSO covers this topic (e.g., user uploads a Renvora employees list → asks "who are the team members?"), AND
   - The conversation history does NOT resolve which source to use.
   
   DO NOT classify as "ambiguous" if:
   - Only one source could possibly contain the answer.
   - The user just asked a general question.
   - The confidence is slightly below 1.0 for any other reason.

ANTI-PATTERNS (do NOT do these):
- Do NOT classify "What is Python?" as ambiguous just because a PDF was uploaded.
- Do NOT classify "Who is the CEO of Renvora?" as ambiguous unless the user uploaded a different company's org chart.
- Do NOT ask for clarification unless you are certain that two distinct sources can genuinely answer.

CLARIFICATION QUESTION FORMAT (only when ambiguous):
- Be specific. Name the actual document files.
- Example: "I found this topic in two places — the Renvora company knowledge and your uploaded 'Employees.xlsx'. Which one should I use?"
- Keep it short. One sentence per option.

OUTPUT FORMAT (JSON only, no other text):
{{
  "intent": "<category>",
  "confidence": <float 0.0-1.0>,
  "clarification_question": "<question or empty string>",
  "suggested_sources": ["<option1>", "<option2>"]
}}
"""

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.05,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        result = json.loads(raw)

        # Validate and sanitize
        valid_intents = {
            "general_knowledge", "renvora_knowledge",
            "uploaded_document", "previous_conversation", "ambiguous"
        }
        intent = result.get("intent", "general_knowledge")
        if intent not in valid_intents:
            intent = "general_knowledge"

        confidence = float(result.get("confidence", 1.0))
        clarification_q = result.get("clarification_question", "")
        suggested_sources = result.get("suggested_sources", [])

        # Safety: if no docs uploaded, never return uploaded_document
        if not has_uploaded_document and intent == "uploaded_document":
            intent = "general_knowledge"

        # Safety: if ambiguous but no docs, resolve to renvora_knowledge
        if intent == "ambiguous" and not has_uploaded_document:
            intent = "renvora_knowledge"
            confidence = 0.9
            clarification_q = ""
            suggested_sources = []

        return {
            "intent": intent,
            "confidence": confidence,
            "clarification_question": clarification_q,
            "suggested_sources": suggested_sources,
        }

    except Exception as e:
        print(f"[IntentDetector] Error: {e}")
        return _default_response()


def _default_response() -> dict:
    return {
        "intent": "general_knowledge",
        "confidence": 1.0,
        "clarification_question": "",
        "suggested_sources": [],
    }