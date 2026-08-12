"""
services/ai_engine.py

Clean Renvora AI source-routing + RAG engine.

SOURCE RULE
-----------
Current question decides the source.

Selected PDF is persistent context,
but NOT a permanent source lock.
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from services.retriever import Retriever


load_dotenv()


# ============================================================
# CONFIG
# ============================================================

COMPANY_COLLECTION = (
    "renvora_knowledge_local_v1"
)

UPLOADED_SOURCE = (
    "Uploaded Document"
)

COMPANY_SOURCE = (
    "Renvora Company Knowledge"
)

CONVERSATION_SOURCE = (
    "Conversation"
)

PDF_NOT_FOUND = (
    "I couldn't find the answer to that question "
    "in the selected document."
)

COMPANY_NOT_FOUND = (
    "I don't have that information in the Renvora "
    "company knowledge available to me right now."
)


GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

if not GROQ_API_KEY:

    print(
        "[AIEngine] WARNING: GROQ_API_KEY missing."
    )

    groq_client = None

else:

    groq_client = Groq(
        api_key=GROQ_API_KEY
    )


# ============================================================
# AI ENGINE
# ============================================================

class AIEngine:

    def __init__(self):

        self.retriever = Retriever()

        print(
            "[AIEngine] Clean RAG Engine initialized."
        )

    # ========================================================
    # SMALL TALK
    # ========================================================

    def _small_talk(
        self,
        text: str,
    ) -> str:

        value = (
            text
            .strip()
            .lower()
            .rstrip("!?.,")
        )

        replies = {

            "hi":
                "Hi! 👋 I'm Renvora AI. "
                "How can I help you today?",

            "hii":
                "Hi! 👋 I'm Renvora AI. "
                "How can I help you today?",

            "hello":
                "Hello! 👋 How can I help you today?",

            "hey":
                "Hey! 👋 How can I help you today?",

            "good morning":
                "Good morning! ☀️ "
                "How can I help you today?",

            "good afternoon":
                "Good afternoon! 👋 "
                "How can I help you today?",

            "good evening":
                "Good evening! 👋 "
                "How can I help you today?",

            "good night":
                "Good night! 🌙 Take care!",

            "thanks":
                "You're welcome! 😊",

            "thank you":
                "You're welcome! 😊",

            "bye":
                "Goodbye! 👋 "
                "I'm here whenever you need me.",
        }

        return replies.get(
            value
        )

    # ========================================================
    # EXPLICIT RENVORA CHECK
    # ========================================================

    def _is_renvora_question(
        self,
        question: str,
    ) -> bool:

        text = question.lower().strip()

        patterns = [

            r"\brenvora\b",

            r"\brenvora tech\b",

            r"\brenvora ai\b",

            r"\brenvora company\b",

            r"\brenvora services?\b",

            r"\brenvora director\b",

            r"\brenvora founder\b",

            r"\brenvora ceo\b",

            r"\brenvora team\b",

            r"\brenvora office\b",

            r"\brenvora website\b",

            r"\brenvora contact\b",

            r"\brenvora working hours\b",

            r"\brenvora business hours\b",

            r"\brenvora headquarters\b",
        ]

        return any(
            re.search(
                pattern,
                text
            )
            for pattern in patterns
        )

    # ========================================================
    # SOURCE RESOLUTION
    # ========================================================

    def _resolve_source(
        self,
        question: str,
        locked_source: str = None,
        locked_doc_id: int = None,
        locked_doc_name: str = None,
        user_documents: list = None,
    ) -> str:

        question = (
            question
            or ""
        ).strip()


        selected_pdf = bool(
            locked_doc_id is not None
            or locked_doc_name
        )


        # ----------------------------------------------------
        # 1. Renvora ALWAYS wins if explicitly mentioned.
        # ----------------------------------------------------

        if self._is_renvora_question(
            question
        ):

            print(
                "[SourceRouter] "
                "Current question -> Renvora."
            )

            return "renvora_knowledge"


        # ----------------------------------------------------
        # 2. If PDF is selected, use selected PDF.
        # ----------------------------------------------------

        if selected_pdf:

            print(
                "[SourceRouter] "
                "Current question -> Selected PDF."
            )

            return "uploaded_document"


        # ----------------------------------------------------
        # 3. No PDF selected.
        #    Preserve existing source intent if present.
        # ----------------------------------------------------

        if locked_source in {
            "renvora_knowledge",
            "uploaded_document",
        }:

            return locked_source


        # ----------------------------------------------------
        # 4. Default.
        # ----------------------------------------------------

        return "general_knowledge"

    # ========================================================
    # LLM
    # ========================================================

    def _ask_llm(
        self,
        question: str,
        context: str,
        source: str,
        history: list = None,
    ) -> str:

        if not groq_client:

            return (
                "AI service is not configured."
            )


        history_text = ""

        if history:

            for item in history[-10:]:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                role = item.get(
                    "role",
                    "user"
                )

                content = item.get(
                    "content",
                    ""
                )

                if content:

                    history_text += (
                        f"{role}: {content}\n"
                    )


        system_prompt = f"""
You are Renvora AI.

CURRENT SOURCE:
{source}

IMPORTANT:
You may ONLY use the supplied context for factual answers.

DO NOT:
- invent information
- use unrelated uploaded documents
- use company knowledge when source is Uploaded Document
- use uploaded documents when source is Renvora Company Knowledge
- switch sources yourself

The backend already selected the source.

If the context does not contain the answer,
do not guess.

SOURCE:
{source}

CONTEXT:
{context}

RECENT CONVERSATION:
{history_text}
"""


        try:

            response = (
                groq_client
                .chat
                .completions
                .create(

                    model=(
                        "llama-3.3-70b-versatile"
                    ),

                    messages=[

                        {
                            "role": "system",
                            "content": system_prompt,
                        },

                        {
                            "role": "user",
                            "content": question,
                        },
                    ],

                    temperature=0.2,

                    max_tokens=1024,
                )
            )


            return (
                response
                .choices[0]
                .message
                .content
                .strip()
            )


        except Exception as e:

            print(
                "[AIEngine] LLM error:",
                e
            )

            return (
                "I couldn't generate an answer right now."
            )

    # ========================================================
    # MAIN
    # ========================================================

    def generate_response(
        self,
        user_message: str,
        user_id: int,
        chat_history: list = None,
        locked_source: str = None,
        locked_doc_name: str = None,
        locked_doc_id: int = None,
        user_documents: list = None,
    ) -> dict:

        question = (
            user_message
            or ""
        ).strip()


        if chat_history is None:
            chat_history = []


        if user_documents is None:
            user_documents = []


        # ----------------------------------------------------
        # Small talk
        # ----------------------------------------------------

        small_reply = self._small_talk(
            question
        )

        if small_reply:

            return {
                "reply": small_reply,
                "intent": "general_knowledge",
                "source_used": CONVERSATION_SOURCE,
                "lock_source": None,

                # IMPORTANT:
                # Keep selected PDF state.
                "lock_doc_name": locked_doc_name,

                "keep_doc_id": True,

                "needs_clarification": False,
            }


        # ----------------------------------------------------
        # Resolve source
        # ----------------------------------------------------

        source = self._resolve_source(

            question=question,

            locked_source=locked_source,

            locked_doc_id=locked_doc_id,

            locked_doc_name=locked_doc_name,

            user_documents=user_documents,
        )


        print(
            "[SourceRouter]"
        )

        print(
            "Question:",
            question
        )

        print(
            "Selected source:",
            source
        )

        print(
            "Selected doc_id:",
            locked_doc_id
        )

        print(
            "Previous source:",
            locked_source
        )


        # ====================================================
        # RENVORA
        # ====================================================

        if source == "renvora_knowledge":

            result = self.retriever.search(

                question=question,

                collection_name=(
                    COMPANY_COLLECTION
                ),

                top_k=5,

                where=None,
            )


            docs = (
                result.get(
                    "documents",
                    [[]]
                )
                or [[]]
            )


            docs = (
                docs[0]
                if docs
                else []
            )


            if not docs:

                return {
                    "reply": COMPANY_NOT_FOUND,
                    "intent": "renvora_knowledge",
                    "source_used": COMPANY_SOURCE,

                    "lock_source":
                        "renvora_knowledge",

                    # KEEP EXISTING PDF
                    "lock_doc_name":
                        locked_doc_name,

                    "keep_doc_id": True,

                    "needs_clarification": False,
                }


            context = "\n\n".join(
                docs[:5]
            )


            reply = self._ask_llm(

                question=question,

                context=context,

                source=COMPANY_SOURCE,

                history=chat_history,
            )


            return {
                "reply": reply,

                "intent":
                    "renvora_knowledge",

                "source_used":
                    COMPANY_SOURCE,

                "lock_source":
                    "renvora_knowledge",

                # DO NOT DELETE SELECTED PDF
                "lock_doc_name":
                    locked_doc_name,

                "keep_doc_id": True,

                "needs_clarification": False,
            }


        # ====================================================
        # UPLOADED DOCUMENT
        # ====================================================

        if source == "uploaded_document":

            if locked_doc_id is None:

                return {
                    "reply": PDF_NOT_FOUND,

                    "intent":
                        "uploaded_document",

                    "source_used":
                        UPLOADED_SOURCE,

                    "lock_source":
                        "uploaded_document",

                    "lock_doc_name":
                        locked_doc_name,

                    "keep_doc_id": True,

                    "needs_clarification": False,
                }


            user_collection = (
                f"user_{int(user_id)}_local_v1"
            )


            where = {
                "doc_id":
                    int(locked_doc_id)
            }


            print(
                "[AIEngine] PDF retrieval:"
            )

            print(
                "Collection:",
                user_collection
            )

            print(
                "doc_id:",
                locked_doc_id
            )


            result = self.retriever.search(

                question=question,

                collection_name=(
                    user_collection
                ),

                top_k=5,

                where=where,
            )


            docs = (
                result.get(
                    "documents",
                    [[]]
                )
                or [[]]
            )


            distances = (
                result.get(
                    "distances",
                    [[]]
                )
                or [[]]
            )


            docs = (
                docs[0]
                if docs
                else []
            )


            distances = (
                distances[0]
                if distances
                else []
            )


            if not docs:

                print(
                    "[AIEngine] "
                    "No selected-document context found."
                )

                return {
                    "reply": PDF_NOT_FOUND,

                    "intent":
                        "uploaded_document",

                    "source_used":
                        UPLOADED_SOURCE,

                    "lock_source":
                        "uploaded_document",

                    "lock_doc_name":
                        locked_doc_name,

                    "keep_doc_id":
                        True,

                    "needs_clarification":
                        False,
                }


            print(
                "[AIEngine] Retrieved PDF chunks:",
                len(docs)
            )


            if distances:

                print(
                    "[AIEngine] Best score:",
                    distances[0]
                )


            context = "\n\n".join(
                docs[:5]
            )


            reply = self._ask_llm(

                question=question,

                context=context,

                source=(
                    f"{UPLOADED_SOURCE}: "
                    f"{locked_doc_name or 'Selected document'}"
                ),

                history=chat_history,
            )


            return {
                "reply": reply,

                "intent":
                    "uploaded_document",

                "source_used":
                    UPLOADED_SOURCE,

                "lock_source":
                    "uploaded_document",

                "lock_doc_name":
                    locked_doc_name,

                "keep_doc_id":
                    True,

                "needs_clarification":
                    False,
            }


        # ====================================================
        # CONVERSATION
        # ====================================================

        return {
            "reply": self._ask_llm(

                question=question,

                context=(
                    "No external factual "
                    "context is required."
                ),

                source=CONVERSATION_SOURCE,

                history=chat_history,
            ),

            "intent":
                "general_knowledge",

            "source_used":
                CONVERSATION_SOURCE,

            "lock_source": None,

            "lock_doc_name":
                locked_doc_name,

            # KEEP PDF
            "keep_doc_id":
                True,

            "needs_clarification":
                False,
        }


# ============================================================
# SINGLETON
# ============================================================

ai_engine = AIEngine()


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

def generate_response(
    user_message: str,
    user_id: int,
    chat_history: list = None,
    locked_source: str = None,
    locked_doc_name: str = None,
    locked_doc_id: int = None,
    user_documents: list = None,
):

    return ai_engine.generate_response(

        user_message=user_message,

        user_id=user_id,

        chat_history=chat_history,

        locked_source=locked_source,

        locked_doc_name=locked_doc_name,

        locked_doc_id=locked_doc_id,

        user_documents=user_documents,
    )