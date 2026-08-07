"""
services/ai_engine.py
─────────────────────
Renvora AI — Think → Retrieve → Answer pipeline.

Pipeline for every message:
  1. Load full conversation history from DB (last 10 exchanges)
  2. Understand intent WITH conversation context (don't search yet)
  3. Check if session already has a locked source (user already chose)
  4. If locked → retrieve from locked source only → answer
  5. If not locked → score both sources → auto-select clear winner
  6. Only ask clarification when TWO sources are genuinely equally relevant
  7. Build contextual prompt → call LLM → return structured response
"""

import os
import time

from dotenv import load_dotenv
from groq import Groq

from services.intent_detector import detect_intent
from services.retriever import Retriever

# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment.")

_groq_client = Groq(api_key=API_KEY)

# Relevance distance thresholds (ChromaDB cosine distance: lower = more similar)
HIGHLY_RELEVANT   = 0.85   # Clearly relevant — auto-use
SOMEWHAT_RELEVANT = 1.10   # Somewhat relevant — consider
NOT_RELEVANT      = 1.20   # Too far — ignore

# ──────────────────────────────────────────────────────────────────────────────


class AIEngine:

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.prompt_path = os.path.join(self.base_dir, "knowledge", "company_prompt.txt")
        self.company_prompt = self._load_company_prompt()
        self.retriever = Retriever()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _load_company_prompt(self) -> str:
        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return (
                "You are Renvora AI, the official AI assistant of Renvora Tech. "
                "Always answer professionally and accurately."
            )

    def _search_collection(self, query: str, collection_name: str,
                           top_k: int = 5, where: dict = None) -> tuple[list, float]:
        """
        Search a ChromaDB collection.
        Returns (docs: List[str], best_distance: float).
        best_distance = 999 if nothing found.
        """
        try:
            results = self.retriever.search(query, collection_name, top_k=top_k, where=where)
            if not (results and results.get("distances") and results["distances"][0]):
                return [], 999.0

            best_dist = results["distances"][0][0]
            docs = [
                doc for doc, dist in zip(results["documents"][0], results["distances"][0])
                if dist < NOT_RELEVANT
            ]
            return docs, best_dist
        except Exception as e:
            print(f"[AIEngine] Search error ({collection_name}): {e}")
            return [], 999.0

    def _build_chat_history_str(self, chat_history: list) -> str:
        if not chat_history:
            return ""
        lines = ["=" * 40, "RECENT CONVERSATION", "=" * 40]
        for msg in chat_history[-10:]:
            role = msg.get("role", "user").capitalize()
            lines.append(f"{role}: {msg.get('content', '')}")
        return "\n".join(lines) + "\n"

    def _build_system_prompt(self, user_message: str, retrieved_context: str,
                              source_label: str, chat_history: list) -> str:
        history_str = self._build_chat_history_str(chat_history)

        context_block = (
            f"--- {source_label.upper()} ---\n{retrieved_context}"
            if retrieved_context.strip()
            else "No specific document context retrieved."
        )

        return f"""{self.company_prompt}

{history_str}
========================================
RETRIEVED CONTEXT ({source_label})
========================================

{context_block}

========================================
INSTRUCTIONS
========================================

You are Renvora AI — a highly intelligent assistant that converses naturally, like ChatGPT, but with access to Renvora Tech's private knowledge and the user's uploaded documents.

REASONING RULES:
1. Read the RETRIEVED CONTEXT carefully. Determine if it genuinely answers the user's question.
2. If the context is relevant, use it as your primary source. Do NOT ignore it.
3. If the context is irrelevant or empty:
   - For general questions (greetings, "what is Python?", math, etc.) → answer from your general knowledge.
   - For questions specifically about the company or an uploaded document → say you couldn't find that information.
4. Use the RECENT CONVERSATION to understand references like "that", "they", "previous one", "the one I mentioned", etc.
5. NEVER hallucinate facts about the company or documents.
6. NEVER mix information from unrelated documents.

ANSWER STYLE:
- Be conversational and professional, like ChatGPT.
- Answer concisely unless the user asks for details or a full explanation.
- Do NOT say "According to the context" or "Based on the retrieved information".
- Do NOT reveal that you searched a database unless the user asks.
- If you used the uploaded document, you may briefly say "Based on your document, ..." if it helps the user understand the source.

CURRENT USER QUESTION: {user_message}
"""

    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        for attempt in range(3):
            try:
                resp = _groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=0.4,
                    max_tokens=1024,
                    top_p=0.9,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"[AIEngine] LLM error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(2)
        return (
            "I'm sorry, I'm having trouble processing your request right now. "
            "Please try again in a moment."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def generate_response(
        self,
        user_message: str,
        user_id: int,
        chat_history: list = None,
        # Session state (from DB)
        locked_source: str = None,        # "renvora_knowledge" | "uploaded_document" | "general_ai" | None
        locked_doc_name: str = None,      # filename if locked_source == "uploaded_document"
        # Available documents info
        user_documents: list = None,      # List of {"id": .., "original_name": .., "file_name": ..}
    ) -> dict:
        """
        Main entry point. Returns a dict with:
            reply          : str   — the AI's answer
            intent         : str   — detected intent
            source_used    : str   — human-readable source label
            lock_source    : str|None — if set, caller should lock session to this source
            lock_doc_name  : str|None — doc filename to lock to
            suggested_sources : list  — source options if clarification needed
            needs_clarification : bool
        """
        if chat_history is None:
            chat_history = []

        user_collection = f"user_{user_id}"
        has_user_docs = bool(user_documents)
        doc_names = [d.get("original_name", d.get("file_name", "")) for d in (user_documents or [])]

        # ── PHASE 1: UNDERSTAND INTENT ─────────────────────────────────────
        # Think before searching. Pass doc names so the LLM knows what's available.
        intent_data = detect_intent(
            message=user_message,
            has_uploaded_document=has_user_docs,
            chat_history=chat_history,
            document_names=doc_names,
            locked_source=locked_source,
        )
        intent_type = intent_data.get("intent", "general_knowledge")
        confidence = float(intent_data.get("confidence", 1.0))
        clarification_q = intent_data.get("clarification_question", "")
        suggested_sources = intent_data.get("suggested_sources", [])

        # ── PHASE 2: RESOLVE SOURCE ────────────────────────────────────────

        # 2a. If session already has a locked source — respect it, skip clarification
        if locked_source:
            if locked_source == "general_ai":
                intent_type = "general_knowledge"
            elif locked_source == "uploaded_document":
                intent_type = "uploaded_document"
            elif locked_source == "renvora_knowledge":
                intent_type = "renvora_knowledge"

        # 2b. If intent is ambiguous, use vector similarity to auto-decide
        if intent_type == "ambiguous" and not locked_source:
            renvora_docs, renvora_dist = self._search_collection(user_message, "renvora_knowledge_v2")
            user_docs_result, user_dist = (
                self._search_collection(user_message, user_collection)
                if has_user_docs else ([], 999.0)
            )

            renvora_relevant = renvora_dist < HIGHLY_RELEVANT
            user_relevant    = user_dist    < HIGHLY_RELEVANT

            if renvora_relevant and not user_relevant:
                # Clear winner: Renvora knowledge
                intent_type = "renvora_knowledge"
            elif user_relevant and not renvora_relevant:
                # Clear winner: uploaded document
                intent_type = "uploaded_document"
            elif renvora_relevant and user_relevant:
                # Both highly relevant — genuinely ambiguous, ask user
                # Build nice source options for Flutter UI
                options = ["Renvora Company Knowledge"]
                for doc in (user_documents or []):
                    options.append(f"Uploaded: {doc.get('original_name', doc.get('file_name'))}")
                return {
                    "reply": clarification_q or (
                        "I found information in multiple sources. Which one would you like me to use?\n\n"
                        + "\n".join(f"{i+1}. {o}" for i, o in enumerate(options))
                    ),
                    "intent": "ambiguous",
                    "source_used": "None",
                    "lock_source": None,
                    "lock_doc_name": None,
                    "suggested_sources": options,
                    "needs_clarification": True,
                }
            else:
                # Neither source has strong signal — fall back to general knowledge
                intent_type = "general_knowledge"

        # 2c. If low-confidence but NOT ambiguous intent — trust the LLM intent,
        #     don't over-ask for clarification
        # (removed the old confidence < 0.90 → ask pattern)

        # ── PHASE 3: RETRIEVE (only for the decided source) ───────────────
        retrieved_context = ""
        source_label = "General AI Knowledge"
        new_lock_source = None
        new_lock_doc_name = None

        if intent_type == "renvora_knowledge":
            docs, _ = self._search_collection(user_message, "renvora_knowledge_v2")
            if docs:
                retrieved_context = "\n\n".join(docs)
                source_label = "Renvora Company Knowledge"
            else:
                source_label = "Renvora Company Knowledge"
            new_lock_source = "renvora_knowledge"

        elif intent_type == "uploaded_document":
            # If a specific doc is locked, filter by it
            where = {"pdf_name": locked_doc_name} if locked_doc_name else None
            docs, _ = self._search_collection(user_message, user_collection, where=where)
            if docs:
                retrieved_context = "\n\n".join(docs)
                # Build source label with file name
                if locked_doc_name:
                    source_label = f"Uploaded Document: {locked_doc_name}"
                elif doc_names:
                    source_label = f"Uploaded Document: {doc_names[0]}" if len(doc_names) == 1 else "Uploaded Documents"
                else:
                    source_label = "Uploaded Document"
            else:
                source_label = "Uploaded Document (no relevant content found)"
            new_lock_source = "uploaded_document"
            new_lock_doc_name = locked_doc_name

        elif intent_type == "previous_conversation":
            # Use chat history only; no retrieval needed
            source_label = "Conversation History"
            # Don't lock — it's a reference question, next message may need different source

        else:
            # general_knowledge — LLM answers from its training
            source_label = "General AI Knowledge"
            new_lock_source = None  # Don't lock for general queries

        # ── PHASE 4: GENERATE ─────────────────────────────────────────────
        system_prompt = self._build_system_prompt(
            user_message, retrieved_context, source_label, chat_history
        )
        reply = self._call_llm(system_prompt, user_message)

        return {
            "reply": reply,
            "intent": intent_type,
            "source_used": source_label,
            "lock_source": new_lock_source,
            "lock_doc_name": new_lock_doc_name,
            "suggested_sources": [],
            "needs_clarification": False,
        }


# ── Singleton ──────────────────────────────────────────────────────────────────
ai_engine = AIEngine()