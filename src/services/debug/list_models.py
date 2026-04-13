import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)

try:
    print("Listing models...")
    for m in client.models.list():
        # In the new SDK, supported algorithms are in m.name or metadata
        print(f"Model: {m.name} (Methods: {m.supported_actions})")
except Exception as e:
    print(f"Error: {e}")
