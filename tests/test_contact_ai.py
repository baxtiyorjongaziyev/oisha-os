
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import config

load_dotenv()

def test_ai_response():
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return

    client = genai.Client(api_key=gemini_key)
    
    test_message = "Salom, mening ismim Olim. Men Toshkentdanman, qurilish sohasida tadbirkorman. Raqamim: +998901112233"
    
    print(f"Testing message: {test_message}")
    
    sys_inst = config.system_instruction
    chat_config = types.GenerateContentConfig(
        system_instruction=sys_inst,
    )
    
    chat = client.chats.create(
        model="gemini-2.0-flash",
        config=chat_config
    )
    
    response = chat.send_message(test_message)
    print("\nAI Response received (contains unicode).")
    
    # Save to file to avoid console encoding issues
    with open("ai_response_last.txt", "w", encoding="utf-8") as f:
        f.write(response.text)
    
    if "[CONTACT_INFO:" in response.text:
        print("\nSuccess: CONTACT_INFO tag found!")
    else:
        print("\nFailure: CONTACT_INFO tag NOT found.")
        print(f"Response text start: {response.text[:100]}...")

if __name__ == "__main__":
    test_ai_response()
