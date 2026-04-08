from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    chat = client.chats.create(
        model="gemini-2.0-flash",
        config={"system_instruction": "You are a helpful pirate. Talk like a pirate."}
    )
    response = chat.send_message("Hello, who are you?")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
