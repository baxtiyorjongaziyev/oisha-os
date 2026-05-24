import os
import boto3
import sys
from dotenv import load_dotenv

# .env yuklash
load_dotenv()

def chat_with_claude():
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "eu-north-1")
    model_id = os.getenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-4-6")

    client = boto3.client(
        service_name="bedrock-runtime",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
    )

    print("-" * 50)
    print("  Claude 3.5 Sonnet Chat (AWS Bedrock)  ")
    print("  Chiqish uchun 'exit' yoki 'quit' deb yozing.  ")
    print("-" * 50)

    messages = []

    while True:
        user_input = input("\nSiz: ")
        if user_input.lower() in ['exit', 'quit', 'chiqish']:
            break

        messages.append({
            "role": "user",
            "content": [{"text": user_input}]
        })

        try:
            response = client.converse(
                modelId=model_id,
                messages=messages,
                system=[{"text": "Siz JonBranding agentligining aqlli yordamchisiz. O'zbek tilida professional javob berasiz."}]
            )

            reply = response['output']['message']['content'][0]['text']
            
            print("\nClaude:", end=" ")
            # Emojilarni Windows terminalida xavfsiz chiqarish
            print(reply.encode('ascii', 'ignore').decode('ascii') if os.name == 'nt' else reply)

            messages.append({
                "role": "assistant",
                "content": [{"text": reply}]
            })

        except Exception as e:
            print(f"\nXatolik: {e}")

if __name__ == "__main__":
    chat_with_claude()
