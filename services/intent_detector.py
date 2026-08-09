"""
services/intent_detector.py
────────────────────────────

Renvora AI Conversation-Aware Intent Detector.

IMPORTANT:
This file ONLY detects the intent/source of the CURRENT
user message.

It does NOT import AIEngine.
It does NOT call ai_engine.generate_response().

Flow:

    Current message
          +
    Conversation history
          +
    Previous source
          ↓
    Intent Detection
          ↓
    Renvora / Uploaded Document / General / Conversation
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
        return None

    try:
        return Groq(
            api_key=GROQ_API_KEY
        )

    except Exception as e:
        print(
            f"[IntentDetector] Client error: {e}"
        )
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
    Normalize user text for keyword matching.
    """

    if not text:
        return ""

    text = str(text).lower().strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# ============================================================
# SMALL TALK
# ============================================================

def _is_small_talk(message):
    """
    Detect greetings/simple conversational messages.
    """

    text = _normalize(message)

    text = text.rstrip(
        "!?., "
    )

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

    # Common company phrasing
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
    Detect whether message contains a company-related topic.
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

    These need conversation context.
    """

    text = _normalize(message)

    text = text.rstrip(
        "!?., "
    )

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

    if (
        text.startswith("what about ")
        or
        text.startswith("tell me more")
        or
        text.startswith("explain ")
    ):
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

    # Last 12 messages
    recent_messages = chat_history[-12:]

    for message in recent_messages:

        if not isinstance(
            message,
            dict
        ):
            continue

        role = message.get(
            "role",
            "user"
        )

        content = message.get(
            "content",
            ""
        )

        if not content:
            continue

        role = str(
            role
        ).capitalize()

        lines.append(
            f"{role}: {content}"
        )

    if not lines:
        return "No previous conversation."

    return "\n".join(
        lines
    )


# ============================================================
# FIND PREVIOUS SOURCE
# ============================================================

def _infer_previous_source(
    chat_history,
    locked_source=None
):
    """
    Infer the previous conversational source.

    locked_source is only a hint.
    """

    if locked_source:
        normalized = _normalize(
            locked_source
        )

        if "uploaded" in normalized:
            return "uploaded_document"

        if "renvora" in normalized:
            return "renvora_knowledge"

        if "conversation" in normalized:
            return "previous_conversation"

    if not chat_history:
        return None

    # Inspect recent messages backwards
    for message in reversed(
        chat_history[-12:]
    ):

        if not isinstance(
            message,
            dict
        ):
            continue

        content = message.get(
            "content",
            ""
        )

        if not content:
            continue

        # Explicit Renvora reference
        if _has_explicit_company_reference(
            content
        ):
            return "renvora_knowledge"

        # Explicit document reference
        if _has_explicit_document_reference(
            content
        ):
            return "uploaded_document"

    return None


# ============================================================
# DETECT COMPANY CONTEXT IN HISTORY
# ============================================================

def _history_has_company_context(
    chat_history
):
    """
    Determine whether recent conversation is
    clearly about Renvora.
    """

    if not chat_history:
        return False

    # Inspect last 8 messages
    for message in reversed(
        chat_history[-8:]
    ):

        if not isinstance(
            message,
            dict
        ):
            continue

        content = message.get(
            "content",
            ""
        )

        if not content:
            continue

        text = _normalize(
            content
        )

        # Explicit Renvora
        if "renvora" in text:
            return True

        # Company-related questions
        if any(
            keyword in text
            for keyword in [
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
        ):
            return True

    return False


# ============================================================
# DETECT DOCUMENT CONTEXT IN HISTORY
# ============================================================

def _history_has_document_context(
    chat_history
):
    """
    Determine whether recent conversation is
    clearly about an uploaded document.
    """

    if not chat_history:
        return False

    for message in reversed(
        chat_history[-8:]
    ):

        if not isinstance(
            message,
            dict
        ):
            continue

        content = message.get(
            "content",
            ""
        )

        if not content:
            continue

        if _has_explicit_document_reference(
            content
        ):
            return True

    return False


# ============================================================
# DETERMINISTIC SOURCE ROUTING
# ============================================================

def _deterministic_intent(
    message,
    has_uploaded_document,
    chat_history,
    locked_source
):
    """
    Resolve obvious cases BEFORE calling the LLM.

    Returns:
        intent or None
    """

    text = _normalize(
        message
    )

    # --------------------------------------------------------
    # 1. Small talk
    # --------------------------------------------------------

    if _is_small_talk(
        message
    ):
        return "general_knowledge"


    # --------------------------------------------------------
    # 2. Explicit document reference
    #
    # CURRENT MESSAGE HAS PRIORITY.
    # --------------------------------------------------------

    if _has_explicit_document_reference(
        message
    ):

        if has_uploaded_document:
            return "uploaded_document"

        return "general_knowledge"


    # --------------------------------------------------------
    # 3. Explicit Renvora reference
    #
    # CURRENT MESSAGE HAS PRIORITY.
    # --------------------------------------------------------

    if _has_explicit_company_reference(
        message
    ):

        return "renvora_knowledge"


    # --------------------------------------------------------
    # 4. "Renvora services" type messages
    # --------------------------------------------------------

    if (
        "renvora" in text
        and _has_company_topic(message)
    ):

        return "renvora_knowledge"


    # --------------------------------------------------------
    # 5. Short company follow-up
    #
    # Example:
    #
    # User: Renvora services?
    # AI: ...
    # User: director
    #
    # → Renvora
    # --------------------------------------------------------

    if _is_company_short_question(
        message
    ):

        if _history_has_company_context(
            chat_history
        ):

            return "renvora_knowledge"

        if (
            locked_source
            and
            "renvora"
            in _normalize(
                locked_source
            )
        ):

            return "renvora_knowledge"


        # Without context, let LLM decide.
        return None


    # --------------------------------------------------------
    # 6. Conversational follow-up
    # --------------------------------------------------------

    if _is_follow_up_question(
        message
    ):

        previous_source = (
            _infer_previous_source(
                chat_history,
                locked_source
            )
        )

        if previous_source:

            return previous_source

        if _history_has_document_context(
            chat_history
        ) and has_uploaded_document:

            return "uploaded_document"

        if _history_has_company_context(
            chat_history
        ):

            return "renvora_knowledge"

        return None


    # --------------------------------------------------------
    # 7. Topic + company context
    # --------------------------------------------------------

    if _has_company_topic(
        message
    ):

        if _history_has_company_context(
            chat_history
        ):

            return "renvora_knowledge"


    # --------------------------------------------------------
    # Nothing obvious.
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

    IMPORTANT:

    Current message has highest priority.

    Conversation history is used to understand
    incomplete/short/follow-up messages.

    Previous source is only a hint.
    """

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    message = (
        message
        or ""
    ).strip()

    if chat_history is None:
        chat_history = []

    if document_names is None:
        document_names = []


    # --------------------------------------------------------
    # Empty
    # --------------------------------------------------------

    if not message:

        return _default_response()


    # --------------------------------------------------------
    # Deterministic routing
    # --------------------------------------------------------

    deterministic_intent = (
        _deterministic_intent(
            message=message,
            has_uploaded_document=(
                has_uploaded_document
            ),
            chat_history=chat_history,
            locked_source=locked_source
        )
    )


    if deterministic_intent:

        print(
            "[IntentDetector] Deterministic:",
            deterministic_intent,
            "|",
            message
        )

        return {
            "intent": deterministic_intent,
            "confidence": 0.98,
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
                start=1
            ):

                document_lines.append(
                    f"{index}. {name}"
                )

            document_context = (
                "User uploaded documents:\n"
                +
                "\n".join(
                    document_lines
                )
            )

        else:

            document_context = (
                "User has uploaded at least "
                "one document."
            )

    else:

        document_context = (
            "User has NOT uploaded any document."
        )


    # ========================================================
    # HISTORY
    # ========================================================

    history_context = _build_history(
        chat_history
    )


    # ========================================================
    # PREVIOUS SOURCE
    # ========================================================

    previous_source = (
        _infer_previous_source(
            chat_history,
            locked_source
        )
    )


    previous_source_text = (
        previous_source
        or
        "unknown"
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

Use ONLY when the question genuinely has
two possible factual sources and the conversation
cannot resolve which source is intended.


============================================================
MOST IMPORTANT RULE
============================================================

DO NOT treat each user message independently.

Understand the CURRENT message using the
RECENT CONVERSATION.

The user may use very short messages such as:

"director"

"services"

"team"

"more"

"why?"

"what about it?"

"and?"

These messages must be interpreted using
previous messages.


============================================================
EXAMPLE 1
============================================================

User:
Renvora services?

Assistant:
[answer]

User:
director

Correct intent:

renvora_knowledge


============================================================
EXAMPLE 2
============================================================

User:
Tell me about Renvora.

Assistant:
[answer]

User:
services

Correct intent:

renvora_knowledge


============================================================
EXAMPLE 3
============================================================

User:
I uploaded an AI handbook PDF.

Assistant:
[acknowledgement]

User:
What is machine learning?

Correct intent:

uploaded_document

IF the question is clearly about the uploaded
document based on conversation context.


============================================================
EXAMPLE 4
============================================================

User:
What is machine learning in the PDF?

Assistant:
[answer]

User:
What about neural networks?

Correct intent:

uploaded_document


============================================================
EXAMPLE 5
============================================================

User:
Renvora services?

Assistant:
[answer]

User:
What about the director?

Correct intent:

renvora_knowledge


============================================================
EXAMPLE 6
============================================================

Previous source:
uploaded_document

Current:

Renvora services?

Correct:

renvora_knowledge


The previous source is NOT a permanent lock.


============================================================
EXAMPLE 7
============================================================

Previous source:
renvora_knowledge

Current:

What does my PDF say about AI?

Correct:

uploaded_document


============================================================
EXAMPLE 8
============================================================

Current:

What is Artificial Intelligence?

No document reference.
No Renvora reference.

Correct:

general_knowledge


============================================================
EXAMPLE 9
============================================================

Current:

director

Previous conversation:

User: Renvora services?
Assistant: Renvora provides...

Correct:

renvora_knowledge


============================================================
EXAMPLE 10
============================================================

Current:

services

Previous conversation:

User: Renvora company kya karti hai?
Assistant: ...

Correct:

renvora_knowledge


============================================================
EXAMPLE 11
============================================================

Current:

services

No Renvora context.
No document context.

This could be ambiguous.

Use:

general_knowledge

unless the conversation clearly identifies
Renvora or a document.


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
SOURCE PRIORITY
============================================================

Priority order:

1. Explicit current-message source reference
2. Current-message topic
3. Conversation context
4. Previous source
5. General knowledge


IMPORTANT:

The CURRENT MESSAGE has priority over the
previous source.

The conversation history is used to understand
meaning.

Previous source is only a hint.


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
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],

                temperature=0.05,

                max_tokens=300,

                response_format={
                    "type": "json_object"
                }
            )
        )


        raw = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )


        result = json.loads(
            raw
        )


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
        "general_knowledge"
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
    # CONFIDENCE
    # ========================================================

    try:

        confidence = float(
            result.get(
                "confidence",
                0.7
            )
        )

    except Exception:

        confidence = 0.7


    confidence = max(
        0.0,
        min(
            1.0,
            confidence
        )
    )


    # ========================================================
    # CLARIFICATION
    # ========================================================

    clarification_question = (
        result.get(
            "clarification_question",
            ""
        )
    )

    if not isinstance(
        clarification_question,
        str
    ):

        clarification_question = ""


    # ========================================================
    # SUGGESTED SOURCES
    # ========================================================

    suggested_sources = (
        result.get(
            "suggested_sources",
            []
        )
    )

    if not isinstance(
        suggested_sources,
        list
    ):

        suggested_sources = []


    # ========================================================
    # AMBIGUOUS SAFETY
    # ========================================================

    if (
        intent == "ambiguous"
        and not has_uploaded_document
    ):

        if _has_explicit_company_reference(
            message
        ):

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
        "clarification_question": (
            clarification_question
        ),
        "suggested_sources": (
            suggested_sources
        ),
    }


    print(
        "[IntentDetector] Result:",
        final_result
    )


    return final_result