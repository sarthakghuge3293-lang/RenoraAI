import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")

if not API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file.")

client = Groq(api_key=API_KEY)

# Load Company Prompt
PROMPT_PATH = "knowledge/prompt.txt"

with open(PROMPT_PATH, "r", encoding="utf-8") as file:
    COMPANY_PROMPT = file.read()


def generate_response(user_message):
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": COMPANY_PROMPT
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            temperature=0.4,
            max_tokens=1024,
        )

        return {
            "success": True,
            "reply": response.choices[0].message.content,
            "intent": "general",
            "show_form": False
        }

    except Exception as e:
        return {
            "success": False,
            "reply": f"Error: {str(e)}",
            "intent": "error",
            "show_form": False
        }