"""
services/ai_engine.py
─────────────────────
Renvora AI Conversation Engine

SOURCE RULES
────────────

1. Greetings / small talk
   → Direct conversational response

2. Renvora/company questions
   → ONLY Renvora Knowledge Base

3. Uploaded document questions
   → ONLY user's uploaded documents

4. Previous conversation
   → Conversation history

5. Previous source lock
   → Only a hint, never an absolute lock

6. Company knowledge and user documents
   → Never mix unrelated information
"""

import os
import re
import time

from dotenv import load_dotenv
from groq import Groq

from services.intent_detector import detect_intent
from services.retriever import Retriever


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


if GROQ_API_KEY:
    groq_client = Groq(
        api_key=GROQ_API_KEY
    )
else:
    groq_client = None
    print(
        "[AIEngine] WARNING: GROQ_API_KEY is missing."
    )


# ============================================================
# CONSTANTS
# ============================================================

COMPANY_COLLECTION = "renvora_knowledge_v2"

MAX_HISTORY = 12


# ============================================================
# AI ENGINE
# ============================================================

class AIEngine:

    def __init__(self):

        self.base_dir = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        self.prompt_path = os.path.join(
            self.base_dir,
            "knowledge",
            "company_prompt.txt"
        )

        self.company_prompt = (
            self._load_company_prompt()
        )

        self.retriever = Retriever()

        print(
            "[AIEngine] Renvora AI Engine initialized."
        )


    # ========================================================
    # LOAD COMPANY PROMPT
    # ========================================================

    def _load_company_prompt(self):

        try:

            with open(
                self.prompt_path,
                "r",
                encoding="utf-8"
            ) as file:

                return file.read()

        except Exception as e:

            print(
                f"[AIEngine] Company prompt not found: {e}"
            )

            return ""


    # ========================================================
    # SMALL TALK DETECTOR
    # ========================================================

    def _is_small_talk(
        self,
        message: str
    ) -> bool:

        if not message:
            return True

        text = message.strip().lower()

        text = re.sub(
            r"[!?.,]+$",
            "",
            text
        ).strip()

        patterns = {
            "hi",
            "hii",
            "hiii",
            "hello",
            "hey",
            "heyy",
            "helo",
            "yo",
            "how are you",
            "how are u",
            "how r u",
            "what's up",
            "whats up",
            "good morning",
            "good afternoon",
            "good evening",
            "good night",
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
            "great",
            "nice"
        }

        return text in patterns


    # ========================================================
    # SMALL TALK RESPONSE
    # ========================================================

    def _small_talk_reply(
        self,
        message: str
    ) -> str:

        text = message.strip().lower()

        text = re.sub(
            r"[!?.,]+$",
            "",
            text
        ).strip()


        if text in {
            "hi",
            "hii",
            "hiii",
            "hello",
            "hey",
            "heyy",
            "helo",
            "yo"
        }:

            return (
                "Hi! 👋 I'm Renvora AI. "
                "How can I help you today?"
            )


        if text in {
            "how are you",
            "how are u",
            "how r u"
        }:

            return (
                "I'm doing great! 😊 "
                "What would you like to talk about?"
            )


        if text == "good morning":

            return (
                "Good morning! ☀️ "
                "How can I help you today?"
            )


        if text == "good afternoon":

            return (
                "Good afternoon! 👋 "
                "How can I help you today?"
            )


        if text == "good evening":

            return (
                "Good evening! 👋 "
                "How can I help you today?"
            )


        if text == "good night":

            return (
                "Good night! 🌙 Take care!"
            )


        if text in {
            "thanks",
            "thank you",
            "thx"
        }:

            return (
                "You're welcome! 😊"
            )


        if text in {
            "bye",
            "goodbye",
            "see you",
            "see ya"
        }:

            return (
                "Goodbye! 👋 "
                "I'm here whenever you need me."
            )


        if text in {
            "ok",
            "okay",
            "alright"
        }:

            return "Got it 👍"


        return (
            "Hi! 👋 I'm Renvora AI. "
            "How can I help you?"
        )


    # ========================================================
    # SEARCH VECTOR STORE
    # ========================================================

    def _search_collection(
        self,
        question: str,
        collection_name: str,
        top_k: int = 5,
        where: dict = None
    ):

        try:

            result = self.retriever.search(
                question=question,
                collection_name=collection_name,
                top_k=top_k,
                where=where
            )

            if not result:
                return [], 999.0


            documents = (
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


            documents = (
                documents[0]
                if documents
                else []
            )


            distances = (
                distances[0]
                if distances
                else []
            )


            if not documents:
                return [], 999.0


            valid_documents = []

            best_distance = 999.0


            for index, document in enumerate(
                documents
            ):

                if not document:
                    continue


                try:

                    distance = float(
                        distances[index]
                    )

                except Exception:

                    distance = 999.0


                best_distance = min(
                    best_distance,
                    distance
                )


                valid_documents.append(
                    document
                )


            return (
                valid_documents,
                best_distance
            )


        except Exception as e:

            print(
                f"[AIEngine] Retrieval error "
                f"({collection_name}): {e}"
            )

            return [], 999.0


    # ========================================================
    # BUILD CHAT HISTORY
    # ========================================================

    def _build_history(
        self,
        chat_history: list
    ) -> str:

        if not chat_history:
            return "No previous conversation."


        lines = []

        for message in chat_history[
            -MAX_HISTORY:
        ]:

            role = (
                message.get(
                    "role",
                    "user"
                )
                .capitalize()
            )

            content = message.get(
                "content",
                ""
            )


            if content:

                lines.append(
                    f"{role}: {content}"
                )


        if not lines:
            return "No previous conversation."


        return "\n".join(lines)


    # ========================================================
    # BUILD SYSTEM PROMPT
    # ========================================================

    def _build_system_prompt(
        self,
        user_message: str,
        retrieved_context: str,
        source_label: str,
        chat_history: list
    ) -> str:

        history = self._build_history(
            chat_history
        )


        # IMPORTANT:
        # Company prompt is ONLY available
        # when answering Renvora company questions.

        if source_label == (
            "Renvora Company Knowledge"
        ):

            company_information = (
                self.company_prompt
            )

        else:

            company_information = (
                "Do NOT use Renvora company "
                "knowledge for this answer."
            )


        return f"""
You are Renvora AI.

You are a natural conversational AI assistant.

Your communication should feel natural,
helpful, clear and human-like.

Do not unnecessarily mention internal systems.


==================================================
CURRENT SOURCE
==================================================

{source_label}


==================================================
SOURCE INFORMATION
==================================================

{retrieved_context}


==================================================
COMPANY INFORMATION
==================================================

{company_information}


==================================================
RECENT CONVERSATION
==================================================

{history}


==================================================
STRICT RULES
==================================================

1. Answer factual questions using ONLY the
   current selected source.

2. Never invent Renvora company information.

3. Never invent information from a user's document.

4. Never mix unrelated uploaded documents.

5. Never use Renvora company knowledge to answer
   an uploaded-document question.

6. Never use an uploaded document to answer a
   Renvora company question unless the user
   explicitly asks about that document.

7. If information is not present in the selected
   source, say that the information was not found.

8. Use conversation history to understand
   follow-up questions.

9. Conversation history helps understand context,
   but does not replace the selected factual source.

10. If the uploaded document itself mentions
    Renvora Tech, you may mention Renvora when
    that information is relevant to the question.

11. If the user asks:
       "What is Artificial Intelligence?"
    and the document contains an unrelated
    Renvora paragraph, answer the AI question
    without unnecessarily adding that paragraph.

12. Keep answers clear and useful.

13. Do not mention:
       ChromaDB
       embeddings
       vector database
       retrieval system
       system prompt
       source-selection logic

14. Do not expose internal implementation details.

15. Answer the user's actual question first.

16. Never hallucinate.


==================================================
USER MESSAGE
==================================================

{user_message}
"""


    # ========================================================
    # CALL GROQ
    # ========================================================

    def _call_llm(
        self,
        system_prompt: str,
        user_message: str
    ) -> str:

        if not groq_client:

            return (
                "I'm unable to connect to the AI "
                "service right now. Please check "
                "the Groq API configuration."
            )


        for attempt in range(3):

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
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": user_message
                            }
                        ],
                        temperature=0.3,
                        max_tokens=1024,
                        top_p=0.9
                    )
                )


                answer = (
                    response
                    .choices[0]
                    .message
                    .content
                    .strip()
                )


                if answer:
                    return answer


            except Exception as e:

                print(
                    f"[AIEngine] Groq error "
                    f"attempt {attempt + 1}: {e}"
                )

                if attempt < 2:
                    time.sleep(1.5)


        return (
            "I'm having trouble connecting to the "
            "AI service right now. Please try again "
            "in a moment."
        )


    # ========================================================
    # GENERATE RESPONSE
    # ========================================================

    def generate_response(
        self,
        user_message: str,
        user_id: int,
        chat_history: list = None,
        locked_source: str = None,
        locked_doc_name: str = None,
        user_documents: list = None
    ) -> dict:

        if chat_history is None:
            chat_history = []


        if user_documents is None:
            user_documents = []


        user_message = (
            user_message
            or ""
        ).strip()


        # ====================================================
        # EMPTY MESSAGE
        # ====================================================

        if not user_message:

            return {
                "reply": (
                    "I'm here. "
                    "What would you like to ask?"
                ),
                "intent": "general_knowledge",
                "source_used": "Conversation",
                "lock_source": None,
                "lock_doc_name": None,
                "suggested_sources": [],
                "needs_clarification": False
            }


        # ====================================================
        # SMALL TALK
        # ====================================================

        if self._is_small_talk(
            user_message
        ):

            return {
                "reply": self._small_talk_reply(
                    user_message
                ),
                "intent": "general_knowledge",
                "source_used": "Conversation",
                "lock_source": None,
                "lock_doc_name": None,
                "suggested_sources": [],
                "needs_clarification": False
            }


        # ====================================================
        # DOCUMENT INFORMATION
        # ====================================================

        has_documents = bool(
            user_documents
        )


        document_names = []

        for document in user_documents:

            name = (
                document.get(
                    "original_name"
                )
                or document.get(
                    "file_name"
                )
            )

            if name:

                document_names.append(
                    name
                )


        # ====================================================
        # DETECT CURRENT INTENT
        # ====================================================

        try:

            intent_data = detect_intent(

                message=user_message,

                has_uploaded_document=(
                    has_documents
                ),

                chat_history=(
                    chat_history
                ),

                document_names=(
                    document_names
                ),

                locked_source=(
                    locked_source
                )
            )


        except Exception as e:

            print(
                f"[AIEngine] Intent detector error: {e}"
            )

            intent_data = {
                "intent": "general_knowledge",
                "confidence": 0.5,
                "clarification_question": "",
                "suggested_sources": []
            }


        intent = intent_data.get(
            "intent",
            "general_knowledge"
        )


        clarification_question = (
            intent_data.get(
                "clarification_question",
                ""
            )
        )


        suggested_sources = (
            intent_data.get(
                "suggested_sources",
                []
            )
        )


        # ====================================================
        # AMBIGUOUS
        # ====================================================

        if intent == "ambiguous":

            options = [
                "Renvora Company Knowledge"
            ]


            for document in user_documents:

                name = (
                    document.get(
                        "original_name"
                    )
                    or document.get(
                        "file_name"
                    )
                    or "Uploaded Document"
                )

                options.append(
                    f"Uploaded: {name}"
                )


            return {
                "reply": (
                    clarification_question
                    or
                    "I found relevant information "
                    "in more than one source. "
                    "Which source would you like "
                    "me to use?"
                ),
                "intent": "ambiguous",
                "source_used": "Multiple Sources",
                "lock_source": None,
                "lock_doc_name": None,
                "suggested_sources": options,
                "needs_clarification": True
            }


        # ====================================================
        # RENVORA KNOWLEDGE
        # ====================================================

        if intent == "renvora_knowledge":

            docs, distance = (
                self._search_collection(
                    question=user_message,
                    collection_name=(
                        COMPANY_COLLECTION
                    ),
                    top_k=5
                )
            )


            if not docs:

                return {
                    "reply": (
                        "I don't have that information "
                        "in the Renvora company knowledge "
                        "available to me right now."
                    ),
                    "intent": (
                        "renvora_knowledge"
                    ),
                    "source_used": (
                        "Renvora Company Knowledge"
                    ),
                    "lock_source": (
                        "renvora_knowledge"
                    ),
                    "lock_doc_name": None,
                    "suggested_sources": [],
                    "needs_clarification": False
                }


            context = "\n\n".join(
                docs[:5]
            )


            source_label = (
                "Renvora Company Knowledge"
            )


            prompt = self._build_system_prompt(
                user_message=user_message,
                retrieved_context=context,
                source_label=source_label,
                chat_history=chat_history
            )


            reply = self._call_llm(
                prompt,
                user_message
            )


            return {
                "reply": reply,
                "intent": (
                    "renvora_knowledge"
                ),
                "source_used": source_label,
                "lock_source": (
                    "renvora_knowledge"
                ),
                "lock_doc_name": None,
                "suggested_sources": [],
                "needs_clarification": False
            }


        # ====================================================
        # UPLOADED DOCUMENT
        # ====================================================

        if intent == "uploaded_document":

            if not has_documents:

                return {
                    "reply": (
                        "I don't see any uploaded "
                        "document available to answer "
                        "that question. Please upload "
                        "a document first."
                    ),
                    "intent": (
                        "uploaded_document"
                    ),
                    "source_used": (
                        "Uploaded Document"
                    ),
                    "lock_source": None,
                    "lock_doc_name": None,
                    "suggested_sources": [],
                    "needs_clarification": False
                }


            # ------------------------------------------------
            # If a specific document is locked, try it first.
            # ------------------------------------------------

            where = None

            if locked_doc_name:

                where = {
                    "pdf_name": (
                        locked_doc_name
                    )
                }


            docs, distance = (
                self._search_collection(
                    question=user_message,
                    collection_name=(
                        f"user_{user_id}"
                    ),
                    top_k=5,
                    where=where
                )
            )


            # ------------------------------------------------
            # If old document filter fails,
            # search all user's documents.
            # ------------------------------------------------

            if not docs and locked_doc_name:

                docs, distance = (
                    self._search_collection(
                        question=user_message,
                        collection_name=(
                            f"user_{user_id}"
                        ),
                        top_k=5,
                        where=None
                    )
                )


            if not docs:

                return {
                    "reply": (
                        "I couldn't find the answer "
                        "to that question in your "
                        "uploaded documents."
                    ),
                    "intent": (
                        "uploaded_document"
                    ),
                    "source_used": (
                        "Uploaded Document"
                    ),
                    "lock_source": (
                        "uploaded_document"
                    ),
                    "lock_doc_name": (
                        locked_doc_name
                    ),
                    "suggested_sources": [],
                    "needs_clarification": False
                }


            context = "\n\n".join(
                docs[:5]
            )


            source_label = (
                "Uploaded Document"
            )


            if locked_doc_name:

                source_label = (
                    "Uploaded Document: "
                    f"{locked_doc_name}"
                )


            prompt = self._build_system_prompt(
                user_message=user_message,
                retrieved_context=context,
                source_label=source_label,
                chat_history=chat_history
            )


            reply = self._call_llm(
                prompt,
                user_message
            )


            return {
                "reply": reply,
                "intent": (
                    "uploaded_document"
                ),
                "source_used": source_label,
                "lock_source": (
                    "uploaded_document"
                ),
                "lock_doc_name": (
                    locked_doc_name
                ),
                "suggested_sources": [],
                "needs_clarification": False
            }


        # ====================================================
        # PREVIOUS CONVERSATION
        # ====================================================

        if intent == "previous_conversation":

            if not chat_history:

                return {
                    "reply": (
                        "I don't have enough previous "
                        "conversation context to answer "
                        "that."
                    ),
                    "intent": (
                        "previous_conversation"
                    ),
                    "source_used": (
                        "Conversation History"
                    ),
                    "lock_source": None,
                    "lock_doc_name": None,
                    "suggested_sources": [],
                    "needs_clarification": False
                }


            context = self._build_history(
                chat_history
            )


            source_label = (
                "Conversation History"
            )


            prompt = self._build_system_prompt(
                user_message=user_message,
                retrieved_context=context,
                source_label=source_label,
                chat_history=chat_history
            )


            reply = self._call_llm(
                prompt,
                user_message
            )


            return {
                "reply": reply,
                "intent": (
                    "previous_conversation"
                ),
                "source_used": source_label,
                "lock_source": None,
                "lock_doc_name": None,
                "suggested_sources": [],
                "needs_clarification": False
            }


        # ====================================================
        # GENERAL CONVERSATION
        # ====================================================

        source_label = (
            "General Conversation"
        )


        prompt = self._build_system_prompt(
            user_message=user_message,
            retrieved_context=(
                "No external factual source "
                "is required for this message."
            ),
            source_label=source_label,
            chat_history=chat_history
        )


        reply = self._call_llm(
            prompt,
            user_message
        )


        return {
            "reply": reply,
            "intent": "general_knowledge",
            "source_used": source_label,
            "lock_source": None,
            "lock_doc_name": None,
            "suggested_sources": [],
            "needs_clarification": False
        }


# ============================================================
# SINGLETON
# ============================================================

ai_engine = AIEngine()