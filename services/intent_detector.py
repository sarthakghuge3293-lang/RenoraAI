"""
Renvora AI Conversation-Aware Intent Detector

This file detects the source/intent of the CURRENT user message.

Supported intents:
    - renvora_knowledge
    - uploaded_document
    - previous_conversation
    - general_knowledge
    - ambiguous

Important:
    If a user has an uploaded document and the current question
    is not explicitly about Renvora/company knowledge, the uploaded
    document is preferred.

Example:

    User uploads:
        Renvora_Test_5MB.pdf

    User:
        What is SPECIAL_CODE?

    Result:
        uploaded_document

This allows the RAG/retriever pipeline to search the user's
uploaded document instead of falling back to general conversation.
"""

import os
import json
import re

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# ============================================================
# GROQ CLIENT
# ============================================================

def _get_client():
    """
    Create Groq client.
    """

    if not GROQ_API_KEY:
        print("[IntentDetector] GROQ_API_KEY not configured.")
        return None

    try:
        return Groq(api_key=GROQ_API_KEY)

    except Exception as e:
        print(f"[IntentDetector] Client error: {e}")
        return None


# ============================================================
# DEFAULT RESPONSE
# ============================================================

def _default_response():
    """
    Safe fallback.
    """

    return {
        "intent": "general_knowledge",
        "confidence": 0.5,
        "clarification_question": "",
        "suggested_sources": [],
    }


# ============================================================
# NORMALIZE TEXT
# ============================================================

def _normalize(text):
    """
    Normalize text for matching.
    """

    if not text:
        return ""

    text = str(text).lower().strip()

    text = re.sub(r"\s+", " ", text)

    return text


# ============================================================
# SMALL TALK
# ============================================================

def _is_small_talk(message):
    """
    Detect greetings/simple conversational messages.
    """

    text = _normalize(message)

    text = text.rstrip("!?., ")

    small_talk = {
        "hi",
        "hii",
        "hiii",
        "hello",
        "hey",
        "heyy",
        "helo",
        "yo",

        "good morning",
        "good afternoon",
        "good evening",
        "good night",

        "how are you",
        "how are u",
        "how r u",

        "what's up",
        "whats up",

        "thanks",
        "thank you",
        "thx",

        "bye",
        "goodbye",
        "see you",
        "see ya",

        "ok",
        "okay",
        "alright",
    }

    return text in small_talk


# ============================================================
# COMPANY KEYWORDS
# ============================================================

COMPANY_KEYWORDS = [
    "renvora",
    "renvora tech",
    "renvora company",
    "renvora ai",
]


# ============================================================
# COMPANY TOPIC WORDS
# ============================================================

COMPANY_TOPIC_WORDS = [
    "service",
    "services",
    "director",
    "ceo",
    "founder",
    "owner",
    "team",
    "employee",
    "employees",
    "staff",
    "project",
    "projects",
    "product",
    "products",
    "about",
    "company",
    "history",
    "mission",
    "vision",
    "contact",
    "address",
    "email",
    "phone",
    "website",
    "office",
    "location",
    "career",
    "careers",
    "technology",
    "technologies",
    "solution",
    "solutions",
    "ai solution",
    "ai solutions",
]


# ============================================================
# DOCUMENT KEYWORDS
# ============================================================

DOCUMENT_KEYWORDS = [
    "pdf",
    "document",
    "file",
    "uploaded file",
    "uploaded document",
    "uploaded pdf",
    "my pdf",
    "my document",
    "my file",
    "this pdf",
    "this document",
    "this file",
    "the pdf",
    "the document",
    "the file",
    "in the pdf",
    "in this pdf",
    "in the document",
    "in this document",
    "in the file",
    "from the pdf",
    "from this pdf",
    "from the document",
    "from this document",
    "according to the pdf",
    "according to the document",
    "according to my document",
]


# ============================================================
# DOCUMENT FOLLOW-UP WORDS
# ============================================================

DOCUMENT_FOLLOW_UP_WORDS = [
    "this",
    "that",
    "it",
    "these",
    "those",
    "more",
    "explain more",
    "tell me more",
    "what about it",
    "what about that",
    "and",
    "also",
]


# ============================================================
# COMPANY SHORT FOLLOW-UP WORDS
# ============================================================

COMPANY_SHORT_WORDS = {
    "director",
    "directors",
    "ceo",
    "founder",
    "founders",
    "owner",
    "owners",
    "services",
    "service",
    "team",
    "teams",
    "employees",
    "employee",
    "staff",
    "projects",
    "project",
    "products",
    "product",
    "website",
    "contact",
    "address",
    "phone",
    "email",
    "office",
    "location",
    "mission",
    "vision",
}


# ============================================================
# EXPLICIT DOCUMENT CHECK
# ============================================================

def _has_explicit_document_reference(message):
    """
    True when CURRENT message explicitly refers
    to an uploaded document.
    """

    text = _normalize(message)

    for keyword in DOCUMENT_KEYWORDS:
        if keyword in text:
            return True

    return False


# ============================================================
# EXPLICIT COMPANY CHECK
# ============================================================

def _has_explicit_company_reference(message):
    """
    True when CURRENT message explicitly refers
    to Renvora/company.
    """

    text = _normalize(message)

    for keyword in COMPANY_KEYWORDS:
        if keyword in text:
            return True

    company_patterns = [
        "your company",
        "your services",
        "your director",
        "your ceo",
        "your founder",
        "your team",
        "your projects",
        "the company",
        "company services",
        "company director",
        "company ceo",
        "company founder",
        "company team",
        "company projects",
    ]

    for pattern in company_patterns:
        if pattern in text:
            return True

    return False


# ============================================================
# COMPANY TOPIC CHECK
# ============================================================

def _has_company_topic(message):
    """
    Detect company-related topic.
    """

    text = _normalize(message)

    for keyword in COMPANY_TOPIC_WORDS:
        if keyword in text:
            return True

    return False


# ============================================================
# SHORT COMPANY QUESTION
# ============================================================

def _is_company_short_question(message):
    """
    Detect short messages like:

        director
        services
        ceo
        founder
        team
    """

    text = _normalize(message)

    text = text.rstrip("!?., ")

    return text in COMPANY_SHORT_WORDS


# ============================================================
# FOLLOW-UP QUESTION
# ============================================================

def _is_follow_up_question(message):
    """
    Detect conversational follow-ups.
    """

    text = _normalize(message)

    followups = [
        "tell me more",
        "explain more",
        "more details",
        "more information",
        "what about it",
        "what about that",
        "what about this",
        "and then",
        "and what",
        "what else",
        "anything else",
        "why",
        "how",
        "how so",
        "explain that",
        "explain this",
        "tell me about that",
        "tell me about this",
        "tell me more about it",
        "tell me more about that",
    ]

    if text in followups:
        return True

    if text.startswith("what about "):
        return True

    if text.startswith("tell me more"):
        return True

    if text.startswith("explain "):
        return True

    return False


# ============================================================
# BUILD HISTORY
# ============================================================

def _build_history(chat_history):
    """
    Convert recent conversation into readable context.
    """

    if not chat_history:
        return "No previous conversation."

    lines = []

    recent_messages = chat_history[-12:]

    for message in recent_messages:

        if not isinstance(message, dict):
            continue

        role = message.get("role", "user")

        content = message.get("content", "")

        if not content:
            continue

        role = str(role).capitalize()

        lines.append(f"{role}: {content}")

    if not lines:
        return "No previous conversation."

    return "\n".join(lines)


# ============================================================
# FIND PREVIOUS SOURCE
# ============================================================

def _infer_previous_source(chat_history, locked_source=None):
    """
    Infer previous conversational source.

    locked_source is only a hint.
    """

    if locked_source:

        normalized = _normalize(locked_source)

        if "uploaded" in normalized:
            return "uploaded_document"

        if "renvora" in normalized:
            return "renvora_knowledge"

        if "conversation" in normalized:
            return "previous_conversation"

    if not chat_history:
        return None

    for message in reversed(chat_history[-12:]):

        if not isinstance(message, dict):
            continue

        content = message.get("content", "")

        if not content:
            continue

        if _has_explicit_company_reference(content):
            return "renvora_knowledge"

        if _has_explicit_document_reference(content):
            return "uploaded_document"

    return None


# ============================================================
# DETECT COMPANY CONTEXT IN HISTORY
# ============================================================

def _history_has_company_context(chat_history):
    """
    Determine whether recent conversation is clearly
    about Renvora/company.
    """

    if not chat_history:
        return False

    for message in reversed(chat_history[-8:]):

        if not isinstance(message, dict):
            continue

        content = message.get("content", "")

        if not content:
            continue

        text = _normalize(content)

        if "renvora" in text:
            return True

        company_patterns = [
            "company services",
            "company director",
            "company ceo",
            "company founder",
            "your services",
            "your company",
            "your director",
            "your ceo",
            "your founder",
            "renvora tech",
        ]

        if any(pattern in text for pattern in company_patterns):
            return True

    return False


# ============================================================
# DETECT DOCUMENT CONTEXT IN HISTORY
# ============================================================

def _history_has_document_context(chat_history):
    """
    Determine whether recent conversation is clearly
    about an uploaded document.
    """

    if not chat_history:
        return False

    for message in reversed(chat_history[-8:]):

        if not isinstance(message, dict):
            continue

        content = message.get("content", "")

        if not content:
            continue

        if _has_explicit_document_reference(content):
            return True

    return False


# ============================================================
# DETERMINISTIC SOURCE ROUTING
# ============================================================

def _deterministic_intent(
    message,
    has_uploaded_document,
    chat_history,
    locked_source,
):
    """
    Resolve obvious cases BEFORE calling the LLM.

    Returns:
        intent or None
    """

    text = _normalize(message)

    # --------------------------------------------------------
    # 1. Small talk
    # --------------------------------------------------------

    if _is_small_talk(message):
        return "general_knowledge"

    # --------------------------------------------------------
    # 2. Explicit document reference
    # --------------------------------------------------------

    if _has_explicit_document_reference(message):

        if has_uploaded_document:
            return "uploaded_document"

        return "general_knowledge"

    # --------------------------------------------------------
    # 3. Explicit Renvora reference
    # --------------------------------------------------------

    if _has_explicit_company_reference(message):
        return "renvora_knowledge"

    # --------------------------------------------------------
    # 4. Renvora topic
    # --------------------------------------------------------

    if "renvora" in text and _has_company_topic(message):
        return "renvora_knowledge"

    # --------------------------------------------------------
    # 5. Short company follow-up
    # --------------------------------------------------------

    if _is_company_short_question(message):

        if _history_has_company_context(chat_history):
            return "renvora_knowledge"

        if locked_source and "renvora" in _normalize(locked_source):
            return "renvora_knowledge"

        # If a PDF is active, a short word such as
        # "director" should NOT automatically force company
        # knowledge unless the conversation is clearly about Renvora.
        if has_uploaded_document:
            return "uploaded_document"

        return None

    # --------------------------------------------------------
    # 6. Conversational follow-up
    # --------------------------------------------------------

    if _is_follow_up_question(message):

        previous_source = _infer_previous_source(
            chat_history,
            locked_source,
        )

        if previous_source:
            return previous_source

        if (
            _history_has_document_context(chat_history)
            and has_uploaded_document
        ):
            return "uploaded_document"

        if _history_has_company_context(chat_history):
            return "renvora_knowledge"

        return None

    # --------------------------------------------------------
    # 7. Company topic + company context
    # --------------------------------------------------------

    if _has_company_topic(message):

        if _history_has_company_context(chat_history):
            return "renvora_knowledge"

    # --------------------------------------------------------
    # 8. IMPORTANT:
    #
    # ACTIVE UPLOADED DOCUMENT DEFAULT
    #
    # If a user has an uploaded document and the current
    # question is not explicitly about Renvora/company,
    # search the uploaded document.
    #
    # This fixes questions like:
    #
    #   What is SPECIAL_CODE?
    #   What is TEST_NUMBER?
    #   Who is the director?
    #   What is the secret sentence?
    #
    # when those answers are inside the uploaded PDF.
    # --------------------------------------------------------

    if has_uploaded_document:

        if not _has_explicit_company_reference(message):

            return "uploaded_document"

    # --------------------------------------------------------
    # 9. Nothing obvious.
    # Let LLM understand it.
    # --------------------------------------------------------

    return None


# ============================================================
# MAIN INTENT DETECTOR
# ============================================================

def detect_intent(
    message: str,
    has_uploaded_document: bool = False,
    chat_history: list = None,
    document_names: list = None,
    locked_source: str = None,
) -> dict:
    """
    Main intent detection function.
    """

    message = (message or "").strip()

    if chat_history is None:
        chat_history = []

    if document_names is None:
        document_names = []

    # --------------------------------------------------------
    # Empty message
    # --------------------------------------------------------

    if not message:
        return _default_response()

    # --------------------------------------------------------
    # Deterministic routing
    # --------------------------------------------------------

    deterministic_intent = _deterministic_intent(
        message=message,
        has_uploaded_document=has_uploaded_document,
        chat_history=chat_history,
        locked_source=locked_source,
    )

    if deterministic_intent and not (
        has_uploaded_document
        and deterministic_intent == "general_knowledge"
    ):

        print(
            "[IntentDetector] Deterministic:",
            deterministic_intent,
            "|",
            message,
        )

        return {
            "intent": deterministic_intent,
            "confidence": 0.98,
            "clarification_question": "",
            "suggested_sources": [],
        }

    # ========================================================
    # ACTIVE UPLOADED DOCUMENT — HARD ROUTING
    # ========================================================
    #
    # If a document is available and the current question
    # is NOT explicitly about Renvora/company, ALWAYS use
    # the uploaded document.
    #
    # This prevents Groq from incorrectly selecting
    # general_knowledge for PDF questions.
    # ========================================================

    if has_uploaded_document:

        message_lower = message.lower().strip()

        company_words = [
        "renvora",
        "renvora tech",
        "renvora ai",
        "your company",
        "company services",
        "company director",
        "company ceo",
        "company founder",
    ]

    is_company_question = any(
        word in message_lower
        for word in company_words
    )

    if not is_company_question:

            print(
                "[IntentDetector] HARD ROUTING:",
                "uploaded_document",
                "|",
                message,
                "| documents:",
                document_names,
            )

            return {
                "intent": "uploaded_document",
                "confidence": 1.0,
                "clarification_question": "",
                "suggested_sources": [],
            }

    # ========================================================
    # BUILD DOCUMENT CONTEXT
    # ========================================================

    if has_uploaded_document:

        if document_names:

            document_lines = []

            for index, name in enumerate(
                document_names,
                start=1,
            ):
                document_lines.append(
                    f"{index}. {name}"
                )

            document_context = (
                "User uploaded documents:\n"
                + "\n".join(document_lines)
            )

        else:

            document_context = (
                "User has uploaded at least one document."
            )

    else:

        document_context = (
            "User has NOT uploaded any document."
        )

    # ========================================================
    # HISTORY
    # ========================================================

    history_context = _build_history(chat_history)

    # ========================================================
    # PREVIOUS SOURCE
    # ========================================================

    previous_source = _infer_previous_source(
        chat_history,
        locked_source,
    )

    previous_source_text = (
        previous_source or "unknown"
    )

    # ========================================================
    # GROQ
    # ========================================================

    client = _get_client()

    if not client:
        return _default_response()

    # ========================================================
    # SYSTEM PROMPT
    # ========================================================

    system_prompt = f"""
You are the conversation understanding engine
for Renvora AI.

Your job is ONLY to classify the CURRENT user
message into the correct source.

Do NOT answer the user's question.

Return JSON only.


============================================================
AVAILABLE INTENTS
============================================================

1. renvora_knowledge

Use Renvora Tech company knowledge.

Examples:

- What is Renvora?
- Tell me about Renvora.
- Renvora services
- What services does Renvora provide?
- Who is the director of Renvora?
- Who is Renvora's CEO?
- Tell me about Renvora's team.


2. uploaded_document

Use the user's uploaded document.

Examples:

- What does the PDF say?
- What is written in my document?
- Explain this PDF.
- What does the uploaded file say about AI?
- According to my document, what is machine learning?
- What is SPECIAL_CODE?
- What is TEST_NUMBER?

IMPORTANT:
If the user has an uploaded document and the current
question does not explicitly mention Renvora/company,
prefer uploaded_document.


3. previous_conversation

Use this when the user is specifically asking
about something said earlier.

Examples:

- What did you say earlier?
- Repeat your previous answer.
- What was my first question?
- What did you mention before?


4. general_knowledge

Use normal general knowledge.

Examples:

- What is Artificial Intelligence?
- What is Python?
- Explain machine learning.
- What is a database?
- How does a computer work?


5. ambiguous

Use ONLY when the question genuinely has two
possible factual sources and the conversation
cannot resolve which source is intended.


============================================================
SOURCE PRIORITY
============================================================

1. Explicit current-message Renvora reference
2. Explicit current-message document reference
3. Active uploaded document
4. Conversation context
5. Previous source
6. General knowledge


============================================================
IMPORTANT UPLOADED DOCUMENT RULE
============================================================

If:

has_uploaded_document = true

AND the current question does NOT explicitly refer
to Renvora/company,

classify the question as:

uploaded_document

This is especially important for short factual questions
whose answer may exist only inside the uploaded document.

Examples:

User uploaded PDF containing:
SPECIAL_CODE: ABC123

Current user message:
What is SPECIAL_CODE?

Correct:
uploaded_document


User uploaded PDF containing:
TEST_NUMBER: 57391

Current user message:
What is TEST_NUMBER?

Correct:
uploaded_document


============================================================
CURRENT DOCUMENT STATUS
============================================================

{document_context}


============================================================
PREVIOUS SOURCE
============================================================

{previous_source_text}


============================================================
RECENT CONVERSATION
============================================================

{history_context}


============================================================
CURRENT USER MESSAGE
============================================================

{message}


============================================================
OUTPUT
============================================================

Return ONLY:

{{
    "intent": "",
    "confidence": 0.0,
    "clarification_question": "",
    "suggested_sources": []
}}

No markdown.
No explanation.
JSON only.
"""

    # ========================================================
    # GROQ REQUEST
    # ========================================================

    try:

        response = (
            client
            .chat
            .completions
            .create(
                model="llama-3.3-70b-versatile",

                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": message,
                    },
                ],

                temperature=0.05,

                max_tokens=300,

                response_format={
                    "type": "json_object"
                },
            )
        )

        raw = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        result = json.loads(raw)

    except Exception as e:

        print(
            f"[IntentDetector] Groq error: {e}"
        )

        return _default_response()

    # ========================================================
    # VALIDATE INTENT
    # ========================================================

    valid_intents = {
        "general_knowledge",
        "renvora_knowledge",
        "uploaded_document",
        "previous_conversation",
        "ambiguous",
    }

    intent = result.get(
        "intent",
        "general_knowledge",
    )

    if intent not in valid_intents:
        intent = "general_knowledge"

    # ========================================================
    # NO DOCUMENT SAFETY
    # ========================================================

    if (
        intent == "uploaded_document"
        and not has_uploaded_document
    ):
        intent = "general_knowledge"

    # ========================================================
    # FINAL SAFETY:
    #
    # If a document is available and the message is not
    # explicitly about Renvora, prefer the uploaded document.
    # ========================================================

    if (
        has_uploaded_document
        and not _has_explicit_company_reference(message)
        and intent in {
            "general_knowledge",
            "ambiguous",
        }
    ):
        intent = "uploaded_document"

    # ========================================================
    # CONFIDENCE
    # ========================================================

    try:

        confidence = float(
            result.get(
                "confidence",
                0.7,
            )
        )

    except Exception:

        confidence = 0.7

    confidence = max(
        0.0,
        min(
            1.0,
            confidence,
        ),
    )

    # ========================================================
    # CLARIFICATION
    # ========================================================

    clarification_question = result.get(
        "clarification_question",
        "",
    )

    if not isinstance(
        clarification_question,
        str,
    ):
        clarification_question = ""

    # ========================================================
    # SUGGESTED SOURCES
    # ========================================================

    suggested_sources = result.get(
        "suggested_sources",
        [],
    )

    if not isinstance(
        suggested_sources,
        list,
    ):
        suggested_sources = []

    # ========================================================
    # AMBIGUOUS SAFETY
    # ========================================================

    if (
        intent == "ambiguous"
        and not has_uploaded_document
    ):

        if _has_explicit_company_reference(message):

            intent = "renvora_knowledge"

        else:

            intent = "general_knowledge"

        confidence = 0.8

        clarification_question = ""

        suggested_sources = []

    # ========================================================
    # NON-AMBIGUOUS CLEANUP
    # ========================================================

    if intent != "ambiguous":

        clarification_question = ""

        suggested_sources = []

    # ========================================================
    # FINAL RESULT
    # ========================================================

    final_result = {
        "intent": intent,
        "confidence": confidence,
        "clarification_question": clarification_question,
        "suggested_sources": suggested_sources,
    }

    print(
        "[IntentDetector] Result:",
        final_result,
    )

    return final_result