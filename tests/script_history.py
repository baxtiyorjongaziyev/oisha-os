import os
import io
import sys
from dotenv import load_dotenv
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

chat_history = [
    {"role": "user", "parts": [{"text": "Hello there"}]},
    {"role": "model", "parts": [{"text": "Hi! How can I help you?"}]},
    {"role": "user", "parts": [{"text": "I am sending a message without reply"}]},
]

print("Trying with history ending in 'user'...")
try:
    chat = client.chats.create(
        model="gemini-2.0-flash",
        history=chat_history
    )
    res = chat.send_message("And here is another message from user!")
    print("SUCCESS dicts:", res.text)
except Exception as e:
    print("ERROR dicts:", type(e), e)
