import os
import time


from dotenv import load_dotenv
from groq import Groq
from flask import session

from services.intent_detector import detect_intent
from services.retriever import Retriever


# ==============================
# Load Environment
# ==============================

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")

if not API_KEY:
    raise ValueError("GROQ_API_KEY not found.")

client = Groq(
    api_key=API_KEY
)

# ==============================
# AI Engine
# ==============================

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

        self.company_prompt = self.load_prompt()
        self.retriever = Retriever()


    # ==========================
    # Load Company Prompt
    # ==========================

    def load_prompt(self):

        try:

            with open(
                self.prompt_path,
                "r",
                encoding="utf-8"
            ) as file:

                return file.read()

        except Exception:

            return """
You are Renvora AI.

You are the official AI assistant of Renvora Tech.

Always answer professionally.

Never answer outside company knowledge.
"""

    # ==========================
    # Build System Prompt
    # ==========================

    def build_system_prompt(
        self,
        user_message,
        retrieved_context,
        chat_history=None
    ):
        
        chat_history_str = ""
        if chat_history:
            chat_history_str = "=========================================\nRECENT CONVERSATION CONTEXT\n=========================================\n\n"
            for msg in chat_history[-6:]:
                chat_history_str += f"{msg['role'].capitalize()}: {msg['content']}\n"

        prompt = f"""
{self.company_prompt}

{chat_history_str}

=========================================
KNOWLEDGE BASE CONTEXT
=========================================

{retrieved_context if retrieved_context.strip() else "No highly relevant context found."}

=========================================
CURRENT USER MESSAGE
=========================================

{user_message}

=========================================
IMPORTANT INSTRUCTIONS
=========================================

You are Renvora AI. You converse naturally like ChatGPT.
Before answering, determine whether the KNOWLEDGE BASE CONTEXT is actually relevant to the user's question.

If the context is relevant, use it to answer the question.
If it is not relevant, ignore it completely.

Always answer based on the following priority:
1. Explicit user instructions.
2. Relevant uploaded document (if provided in context).
3. Renvora Company Knowledge (if provided in context).
4. General model knowledge (only if it's a general question like "What is Python?", greetings, etc.)

If retrieved context is completely unrelated, DO NOT use it. Instead, answer naturally from your general knowledge if it's a general question. If the question is specifically about the company or the document, and the document doesn't contain the answer, say "I couldn't find information about that in the uploaded document."

Never hallucinate. Do not mix unrelated uploaded documents into your answers.

=========================================
ANSWER RULES
=========================================

1. Answer ONLY the user's question. Use the Recent Conversation Context to resolve references like "that" or "they".
2. Never explain where you found the answer (e.g. do not say "According to the context" or "According to the PDF").
3. Give clean, human-like answers. Be conversational but professional.
4. Keep answers concise unless the user asks for details.
"""
        return prompt

    # ==========================
    # Build Messages
    # ==========================

    def build_messages(
        self,
        user_message,
        retrieved_context,
        chat_history=None
    ):

        system_prompt = self.build_system_prompt(
            user_message,
            retrieved_context,
            chat_history
        )

        return [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ]

    # ==========================
    # Generate AI Response
    # ==========================

    def ask_llm(
        self,
        user_message,
        retrieved_context,
        chat_history=None
    ):
        messages = self.build_messages(
             user_message,
             retrieved_context,
             chat_history
        )
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=0.4,
                    max_tokens=1024,
                    top_p=0.9
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print("Groq Error:", e)
                if attempt < 2:
                    time.sleep(2)
                    continue

        return (
            "I'm sorry, but I'm currently unable to process your request. "
            "Please try again later."
        )

    # ==========================
    # Public Generate Function
    # ==========================

    def generate_response(
            self,
            user_message,
            collection_name,
            chat_history=None,
            active_pdf=None
    ):

        has_uploaded = bool(collection_name and collection_name != "renvora_knowledge_v2")
        intent_data = detect_intent(user_message, has_uploaded_document=has_uploaded, chat_history=chat_history)
        
        intent_type = intent_data.get("intent", "general_knowledge")
        clarification_question = intent_data.get("clarification_question", "")
        confidence = intent_data.get("confidence", 1.0)
        
        # SMART RETRIEVAL
        renvora_docs = []
        renvora_dist = 999
        
        user_docs = []
        user_dist = 999
        
        try:
            r_results = self.retriever.search(user_message, "renvora_knowledge_v2", top_k=5)
            if r_results and r_results.get("distances") and r_results["distances"][0]:
                renvora_dist = r_results["distances"][0][0]
                renvora_docs = [doc for doc, dist in zip(r_results["documents"][0], r_results["distances"][0]) if dist < 1.2]
        except Exception as e:
            print("Retriever Error (Renvora):", e)
            
        if has_uploaded:
            try:
                where_clause = {"pdf_name": active_pdf} if active_pdf else None
                u_results = self.retriever.search(user_message, collection_name, top_k=5, where=where_clause)
                if u_results and u_results.get("distances") and u_results["distances"][0]:
                    user_dist = u_results["distances"][0][0]
                    user_docs = [doc for doc, dist in zip(u_results["documents"][0], u_results["distances"][0]) if dist < 1.2]
            except Exception as e:
                print("Retriever Error (User):", e)

        # Decide source if ambiguous
        if intent_type == "ambiguous":
            if renvora_dist < 1.0 and user_dist > 1.2:
                intent_type = "renvora_knowledge"
            elif user_dist < 1.0 and renvora_dist > 1.2:
                intent_type = "uploaded_document"
            elif renvora_dist < 1.0 and user_dist < 1.0:
                # Both highly relevant -> must ask
                return {
                    "success": True,
                    "reply": clarification_question if clarification_question else "Could you please clarify which source you are referring to? The uploaded document or Renvora?",
                    "intent": "ambiguous",
                    "show_form": False,
                    "source_used": "None"
                }
            else:
                # Neither is highly relevant, fall back to general or previous conversation
                pass
                
        if intent_type == "ambiguous" or (confidence < 0.90 and intent_type != "previous_conversation" and intent_type != "general_knowledge"):
            return {
                "success": True,
                "reply": clarification_question if clarification_question else "Could you please clarify which source you are referring to? The uploaded document or Renvora?",
                "intent": "ambiguous",
                "show_form": False,
                "source_used": "None"
            }
            
        # Build context based on decided intent
        retrieved_context = ""
        source_used = "General AI Knowledge"
        
        if intent_type == "uploaded_document" or (intent_type == "previous_conversation" and has_uploaded and user_dist < 1.1):
            if user_docs:
                retrieved_context = "--- UPLOADED DOCUMENT CONTEXT ---\n" + "\n\n".join(user_docs)
                source_used = "Uploaded Document"
        elif intent_type == "renvora_knowledge" or (intent_type == "previous_conversation" and renvora_dist < 1.1):
            if renvora_docs:
                retrieved_context = "--- RENVORA KNOWLEDGE CONTEXT ---\n" + "\n\n".join(renvora_docs)
                source_used = "Renvora Database"
        elif intent_type == "general_knowledge" or intent_type == "previous_conversation":
            # Just let LLM answer using chat history and general knowledge
            source_used = "Conversation History / AI"
            
        reply = self.ask_llm(
            user_message,
            retrieved_context,
            chat_history
        )

        return {
            "success": True,
            "reply": reply,
            "intent": intent_type,
            "show_form": intent_type not in ["general_knowledge", "ambiguous", "uploaded_document", "previous_conversation"],
            "source_used": source_used
        }

# ==========================
# Singleton AI Engine
# ==========================

ai_engine = AIEngine()