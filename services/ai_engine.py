
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
        collection_name
):
        knowledge_context = ""

        if collection_name:
            try:
                # Use default collection name. Avoid using requests.session which
                # is not the intended source for application session data.
                results = self.retriever.search(
                    question=user_message,
                    collection_name=collection_name,
                    top_k=8
                )

                docs = results.get("documents", [[]])[0]
                distances = results.get("distances", [[]])[0]

                # Filter out chunks with high distance (low similarity)
                if docs and distances:
                    for doc, distance in zip(docs, distances):
                        if distance < 1.2:
                            knowledge_context += f"""
{doc}

----------------------------------------
"""

            except Exception as e:
                print("Retriever Error:", e)

        prompt = f"""
{self.company_prompt}

=========================================
KNOWLEDGE BASE CONTEXT
=========================================

{knowledge_context if knowledge_context.strip() else "No highly relevant context found."}

=========================================
CURRENT USER MESSAGE
=========================================

{user_message}

=========================================
IMPORTANT INSTRUCTIONS
=========================================

You are Renvora AI.

Before answering, determine whether the KNOWLEDGE BASE CONTEXT is actually relevant to the user's question.

If the context is relevant, use it to answer the question.
If it is not relevant, ignore it completely.

Never assume uploaded files are related unless the user explicitly refers to them or the semantic context clearly matches.
Always answer based on the following priority:
1. Explicit user instructions.
2. Relevant uploaded document (if provided and relevant).
3. General model knowledge.

If retrieved context is completely unrelated, DO NOT use it. Instead, answer naturally from your general knowledge if it's a general question (e.g., "What is Python?"). If the question is specifically about the company or the document, and the document doesn't contain the answer, say "I couldn't find information about that in the uploaded document."

Never hallucinate. Do not mix unrelated uploaded documents into your answers.

=========================================
ANSWER RULES
=========================================

1. Answer ONLY the user's question.
2. Never explain where you found the answer.
3. Never say "According to the context/PDF".
4. Never mention retrieved documents unless the user asks about them.
5. Give clean, human-like answers.
6. Keep answers concise unless the user asks for details.

Examples

User:
Who is the Director?

Answer:
The Director of Renvora Tech is Renuka Kangne.

User:
What is Python?

Answer:
Python is a high-level, interpreted programming language known for its readability and versatility.
"""
        

        return prompt

        # ==========================
    # Build Messages
    # ==========================

    def build_messages(
        self,
        user_message,
        collection_name
):

        system_prompt = self.build_system_prompt(
    user_message,
    collection_name
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
        collection_name
):
        messages = self.build_messages(
             user_message,
            collection_name
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
            collection_name
    ):

        has_uploaded = bool(collection_name and collection_name != "renvora_knowledge")
        intent_data = detect_intent(user_message, has_uploaded_document=has_uploaded)
        
        intent_type = intent_data.get("intent", "general_knowledge")
        clarification_question = intent_data.get("clarification_question", "")
        confidence = intent_data.get("confidence", 1.0)
        
        if intent_type == "ambiguous" or confidence < 0.90:
            return {
                "success": True,
                "reply": clarification_question if clarification_question else "Could you please clarify which source you are referring to? The uploaded document or Renvora?",
                "intent": "ambiguous",
                "show_form": False
            }
            
        target_collection = None
        if intent_type == "uploaded_document" and has_uploaded:
            target_collection = collection_name
        elif intent_type == "renvora_knowledge":
            target_collection = "renvora_knowledge"
            
        reply = self.ask_llm(
            user_message,
            target_collection
        )

        return {
            "success": True,
            "reply": reply,
            "intent": intent_type,
            "show_form": intent_type not in ["general_knowledge", "ambiguous", "uploaded_document"]
        }    # ==========================
# Singleton AI Engine
# ==========================

ai_engine = AIEngine()