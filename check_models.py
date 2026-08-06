import os
from dotenv import load_dotenv
from google import genai

# Load .env file
load_dotenv()

# Read API Key from .env
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

# Create Gemini Client
client = genai.Client(api_key=API_KEY)

print("\nAvailable Gemini Models:\n")

try:
    for model in client.models.list():
        print(model.name)

except Exception as e:
    print(f"Error: {e}")