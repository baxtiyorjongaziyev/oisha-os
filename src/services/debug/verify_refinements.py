import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import config

load_dotenv()

def test_ai():
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return

    client = genai.Client(api_key=gemini_key)
    
    # Read training data
    training_data_text = ""
    if os.path.exists("training_data.txt"):
        with open("training_data.txt", "r", encoding="utf-8") as f:
            training_data_text = f.read()

    # Chat configuration
    safety_settings = [
        types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
        types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
        types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
        types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
    ]
    
    chat_config = types.GenerateContentConfig(
        system_instruction=config.system_instruction,
        safety_settings=safety_settings
    )

    scenarios = [
        ("Salom", "Greeting"),
        ("Toshkent", "Region response (after some context)"),
        ("Ma'lumotlarimni qayerga olding?", "Data source question"),
        ("Baxtiyorjon hali aloqaga chiqmadi", "Complaint about delay")
    ]

    print("=== AI RESPONSE VERIFICATION ===\n")

    chat = client.chats.create(model=config.AI_MODEL, config=chat_config)
    
    # Inject training data if needed
    if training_data_text:
        chat.send_message(message=f"KNOWLEDGE BASE:\n{training_data_text}\nConfirm understanding.")

    for query, label in scenarios:
        print(f"[{label}] User: {query}")
        response = chat.send_message(message=query)
        print(f"AI: {response.text}\n")

if __name__ == "__main__":
    test_ai()
