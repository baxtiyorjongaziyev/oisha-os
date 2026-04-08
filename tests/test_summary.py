
import os
import asyncio
from google import genai
from google.genai import types
import config

async def test_ai_summary():
    api_key = os.environ.get("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", "")
    if not api_key:
        print("Error: GEMINI_API_KEY not found!")
        return
        
    client = genai.Client(api_key=api_key)
    prompt = "Bu sinov xabari. Iltimos, ushbu xabarni 1 ta so'z bilan xulosalang: 'Salom, ishlar yaxshimi?'"
    
    print(f"Calling Gemini with key: {api_key[:10]}...")
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction="Siz aqlli yordamchisiz.")
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"AI Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai_summary())
