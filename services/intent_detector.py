"""
services/intent_detector.py

Renvora AI Source / Intent Detector

IMPORTANT:
Conversation context is used to understand what the user means.
Conversation context does NOT permanently lock the source.

Available factual sources:
    1. renvora_knowledge
    2. uploaded_document

The assistant must NOT use general-world knowledge as a factual source.

Examples:

User uploads XYZ.pdf

User:
    "Company ka naam kya hai?"
    -> uploaded_document

User:
    "Iski services kya hain?"
    -> uploaded_document

User:
    "Renvora ki services kya hain?"
    -> renvora_knowledge

User:
    "XYZ wali company ka naam kya hai?"
    -> uploaded_document

User:
    "Is document me joining date kya hai?"
    -> uploaded_document

User:
    "Renvora ka CEO kaun hai?"
    -> renvora_knowledge

User:
    "India ki capital kya hai?"
    -> unsupported

The previous source must NOT automatically control the next question.
"""

import os
import json

from dotenv import load_dotenv
from groq import Groq


# ============================================================================
# ENVIRONMENT
# ============================================================================

load_dotenv()

_API_KEY = os.getenv("GROQ_API_KEY")


# ============================================================================
# GROQ CLIENT
# ============================================================================

def _get_client():
    if not _API_KEY:
        return None

    return Groq(api_key=_API_KEY)


# ============================================================================
# MAIN INTENT DETECTOR
# ============================================================================

def detect_intent(
    message: str,
    has_uploaded_document: bool = False,
    chat_history: list = None,
    document_names: list = None,
    locked_source: str = None,
) -> dict:
    """
    Decide which factual source should answer the CURRENT question.

    Returns:

    {
        "intent": str,
        "confidence": float,
        "clarification_question": str,
        "suggested_sources": list[str]
    }

    Valid intents:

        renvora_knowledge
        uploaded_document
        previous_conversation
        ambiguous
        unsupported

    IMPORTANT:

    "previous_conversation" means the message is a follow-up/reference
    and conversation context is needed to understand it.

    It does NOT mean that conversation history itself is a factual source.
    """

    client = _get_client()

    if not client:
        return _default_response(
            has_uploaded_document=has_uploaded_document
        )

    # =========================================================================
    # INPUT NORMALIZATION
    # =========================================================================

    message = (message or "").strip()

    if not message:
        return {
            "intent": "unsupported",
            "confidence": 1.0,
            "clarification_question": "",
            "suggested_sources": [],
        }

    document_names = document_names or []
    chat_history = chat_history or []

    # =========================================================================
    # DOCUMENT LIST
    # =========================================================================

    if has_uploaded_document and document_names:

        doc_list_str = (
            "The user has these available uploaded documents:\n"
        )

        for index, name in enumerate(
            document_names,
            start=1
        ):
            doc_list_str += (
                f"  {index}. {name}\n"
            )

    elif has_uploaded_document:

        doc_list_str = (
            "The user has uploaded at least one document, "
            "but its filename is unavailable.\n"
        )

    else:

        doc_list_str = (
            "The user currently has no uploaded documents.\n"
        )

    # =========================================================================
    # CONVERSATION HISTORY
    # =========================================================================

    conversation_str = ""

    if chat_history:

        conversation_str = (
            "Recent conversation context:\n"
        )

        for msg in chat_history[-10:]:

            role = str(
                msg.get(
                    "role",
                    "user"
                )
            ).capitalize()

            content = str(
                msg.get(
                    "content",
                    ""
                )
            ).strip()

            if not content:
                continue

            conversation_str += (
                f"  {role}: {content}\n"
            )

    else:

        conversation_str = (
            "There is no previous conversation context.\n"
        )

    # =========================================================================
    # LOCK INFORMATION
    # =========================================================================

    lock_str = ""

    if locked_source:

        lock_str = f"""
An explicit source selection may exist for this session:

    {locked_source}

IMPORTANT:
This source lock should only be followed when the CURRENT message
is a follow-up that clearly refers to the explicitly selected source.

If the CURRENT message explicitly asks about another source,
the current question takes priority.

Example:

Previous source:
uploaded_document

Current message:
"Renvora ki services kya hain?"

Correct:
renvora_knowledge

Do NOT blindly force the old source.
"""

    # =========================================================================
    # SYSTEM PROMPT
    # =========================================================================

    system_prompt = f"""
You are the source-selection engine for Renvora AI.

Your ONLY job is to understand the CURRENT user message and decide
which factual knowledge source should be used to answer it.

You do NOT generate the final answer.

================================================================
AVAILABLE FACTUAL SOURCES
================================================================

SOURCE 1:
"renvora_knowledge"

This contains private Renvora company knowledge, such as:

- Renvora company information
- Renvora services
- Renvora projects
- Renvora team
- Renvora policies
- Renvora products
- Renvora company history
- information uploaded by Renvora admins into company knowledge

SOURCE 2:
"uploaded_document"

This contains documents personally uploaded by the current user.

Examples:

- PDF
- joining letter
- resume
- company document
- spreadsheet
- report
- image/document
- any other user-owned uploaded knowledge

SOURCE 3:
"unsupported"

This means the question is outside the available Renvora knowledge
and uploaded documents.

IMPORTANT:
General-world knowledge is NOT an answer source.

For example:

"What is Python?"
"What is the capital of India?"
"How does gravity work?"

must NOT be classified as a source that the AI can answer from,
unless that information is actually present in the available sources.

================================================================
{doc_list_str}
================================================================

{conversation_str}

================================================================
{lock_str}
================================================================

================================================================
CORE SOURCE SELECTION RULE
================================================================

Always analyze the CURRENT question independently.

Previous conversation helps understand what words such as:

- this
- that
- it
- this company
- this document
- this file
- same company
- same document
- isme
- iska
- usme
- uska
- woh
- wahi
- aur
- aur batao
- previous one
- above
- earlier
- joining date
- services
- company

refer to.

BUT:

Previous conversation does NOT permanently determine the source.

================================================================
RULE 1 — EXPLICIT RENVORA REFERENCE
================================================================

If the user explicitly mentions:

- Renvora
- Renvora Tech
- your company
- your services
- Renvora services
- Renvora team
- Renvora CEO
- Renvora projects

classify:

"renvora_knowledge"

Example:

User:
"Renvora ki services kya hain?"

Answer source:
renvora_knowledge

================================================================
RULE 2 — EXPLICIT USER DOCUMENT REFERENCE
================================================================

If the user explicitly mentions:

- my PDF
- my document
- uploaded PDF
- uploaded document
- the file
- this PDF
- this document
- joining letter
- resume
- XYZ document
- XYZ company document
- the document I uploaded

classify:

"uploaded_document"

Example:

User:
"Is PDF me joining date kya hai?"

Source:
uploaded_document

================================================================
RULE 3 — DOCUMENT COMPANY QUESTIONS
================================================================

If the user asks about a company that is clearly the company
mentioned in an uploaded document, use:

"uploaded_document"

Example:

User uploaded:

XYZ_Company.pdf

User:
"Company ka name kya hai?"

Correct:
uploaded_document

User:
"Is company ki services kya hain?"

Correct:
uploaded_document

User:
"XYZ company kya karti hai?"

Correct:
uploaded_document

================================================================
RULE 4 — RENVORA VS USER DOCUMENT
================================================================

The user can switch sources at any time.

Example:

User uploaded:
XYZ_Company.pdf

Conversation:

User:
"Is document ka summary do."

-> uploaded_document

User:
"Isme joining kab hai?"

-> uploaded_document

User:
"Renvora ki services kya hain?"

-> renvora_knowledge

User:
"XYZ company ka office kaha hai?"

-> uploaded_document

User:
"Renvora ka founder kaun hai?"

-> renvora_knowledge

DO NOT keep using the PDF just because the previous 10 messages
were about the PDF.

================================================================
RULE 5 — SHORT FOLLOW-UP QUESTIONS
================================================================

If the message is something like:

"aur?"
"aur batao"
"simple me?"
"detail me?"
"kab?"
"kaha?"
"kaun?"
"kitna?"
"iska?"
"isme?"
"usme?"
"wahi wala"
"pehle wala"

use conversation history to understand what the user is referring to.

Then classify the appropriate factual source.

Example:

User:
"Is PDF ka summary do."

Assistant:
"Ye XYZ Technologies ka joining document hai."

User:
"Joining kab hai?"

-> uploaded_document

Example:

User:
"Renvora ki services kya hain?"

Assistant:
"Renvora provides..."

User:
"aur batao"

-> renvora_knowledge

================================================================
RULE 6 — SOURCE SWITCHING
================================================================

The current question always has priority.

Example:

Previous 8 questions:
uploaded_document

Current:
"Renvora ke projects kya hain?"

Correct:
renvora_knowledge

Example:

Previous 8 questions:
renvora_knowledge

Current:
"Mere uploaded joining letter me joining date kya hai?"

Correct:
uploaded_document

================================================================
RULE 7 — OLD DOCUMENTS
================================================================

Document age does NOT matter.

If the user uploaded a document 5 days ago,
and it is still available/ready,

it remains a valid source.

Example:

Five days ago:
User uploaded XYZ.pdf

Today:
"XYZ company ki services kya hain?"

Correct:
uploaded_document

Do NOT require the user to upload the document again.

================================================================
RULE 8 — MULTIPLE DOCUMENTS
================================================================

If multiple documents exist, use the current message and conversation
to identify the relevant document.

Example:

Documents:

1. XYZ_Company.pdf
2. ABC_Joining_Letter.pdf
3. Resume.pdf

User:
"XYZ company ka naam kya hai?"

-> uploaded_document

User:
"ABC wali joining date kya hai?"

-> uploaded_document

User:
"Mere resume me skills kya hain?"

-> uploaded_document

If the current question clearly identifies one document,
do not ask for clarification.

================================================================
RULE 9 — TRUE AMBIGUITY
================================================================

Only return:

"ambiguous"

when BOTH sources genuinely appear equally relevant AND
the conversation does not resolve which source the user means.

Example:

Uploaded document:
"Renvora Employees.pdf"

Renvora knowledge:
Renvora employee information

User:
"Team members kaun hain?"

This could genuinely refer to either source.

Then:

intent:
ambiguous

clarification:
"I found relevant information in both Renvora company knowledge and
your uploaded document 'Renvora Employees.pdf'. Which one should I use?"

Do NOT use ambiguous merely because a document exists.

================================================================
RULE 10 — GENERAL QUESTIONS
================================================================

If the question is outside both sources:

Example:

"India ki capital kya hai?"

"What is Python?"

"How does gravity work?"

return:

"unsupported"

Do NOT return:

"general_knowledge"

because Renvora AI is intentionally restricted to:

- Renvora Company Knowledge
- User Uploaded Documents

================================================================
RULE 11 — GREETINGS
================================================================

Greetings such as:

"Hi"
"Hello"
"Hey"
"Good morning"

should be classified as:

"unsupported"

The final AI layer may respond naturally to a greeting,
but it must NOT retrieve unrelated general knowledge.

================================================================
RULE 12 — DO NOT INVENT
================================================================

Never assume information exists in a source.

Never classify a question as Renvora just because
Renvora is the name of the application.

Never classify every question as uploaded_document
just because a document exists.

================================================================
OUTPUT
================================================================

Return JSON only:

{{
    "intent": "",
    "confidence": 0.0,
    "clarification_question": "",
    "suggested_sources": []
}}

Valid intent values:

"renvora_knowledge"
"uploaded_document"
"previous_conversation"
"ambiguous"
"unsupported"

Confidence:
0.0 to 1.0

================================================================
CURRENT USER MESSAGE
================================================================

{message}
"""

    # =========================================================================
    # GROQ REQUEST
    # =========================================================================

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": message
                },
            ],
            temperature=0.0,
            max_tokens=350,
            response_format={
                "type": "json_object"
            },
        )

        raw = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        result = json.loads(raw)

        # =====================================================================
        # VALIDATION
        # =====================================================================

        valid_intents = {
            "renvora_knowledge",
            "uploaded_document",
            "previous_conversation",
            "ambiguous",
            "unsupported",
        }

        intent = result.get(
            "intent",
            "unsupported"
        )

        if intent not in valid_intents:
            intent = "unsupported"

        # ---------------------------------------------------------------------
        # Confidence
        # ---------------------------------------------------------------------

        try:
            confidence = float(
                result.get(
                    "confidence",
                    0.0
                )
            )
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(
            0.0,
            min(
                1.0,
                confidence
            )
        )

        # ---------------------------------------------------------------------
        # Clarification question
        # ---------------------------------------------------------------------

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

        # ---------------------------------------------------------------------
        # Suggested sources
        # ---------------------------------------------------------------------

        suggested_sources = result.get(
            "suggested_sources",
            []
        )

        if not isinstance(
            suggested_sources,
            list
        ):
            suggested_sources = []

        suggested_sources = [
            str(source)
            for source in suggested_sources
            if source
        ]

        # =====================================================================
        # SAFETY VALIDATION
        # =====================================================================

        # No uploaded documents means uploaded_document is impossible.
        if (
            not has_uploaded_document
            and intent == "uploaded_document"
        ):
            intent = "unsupported"
            confidence = 1.0
            clarification_question = ""
            suggested_sources = []

        # Ambiguous requires an uploaded document.
        if (
            intent == "ambiguous"
            and not has_uploaded_document
        ):
            intent = "renvora_knowledge"
            confidence = 0.9
            clarification_question = ""
            suggested_sources = []

        # General knowledge is no longer a valid factual source.
        if intent == "general_knowledge":
            intent = "unsupported"
            confidence = 1.0
            clarification_question = ""
            suggested_sources = []

        # =====================================================================
        # RETURN
        # =====================================================================

        return {
            "intent": intent,
            "confidence": confidence,
            "clarification_question": clarification_question,
            "suggested_sources": suggested_sources,
        }

    # =========================================================================
    # ERROR HANDLING
    # =========================================================================

    except Exception as e:

        print(
            f"[IntentDetector] Error: {e}"
        )

        return _default_response(
            has_uploaded_document=has_uploaded_document
        )


# ============================================================================
# DEFAULT RESPONSE
# ============================================================================

def _default_response(
    has_uploaded_document: bool = False
) -> dict:
    """
    Safe fallback.

    IMPORTANT:
    We do not fall back to general knowledge.

    If documents exist, uploaded_document is a safer fallback
    for document-related conversations.

    Otherwise the AI should not invent an external source.
    """

    return {
        "intent": (
            "uploaded_document"
            if has_uploaded_document
            else "unsupported"
        ),
        "confidence": 0.5,
        "clarification_question": "",
        "suggested_sources": [],
    }