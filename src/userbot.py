import os

from src.controllers.message_controller import MessageController
from src.database import Database

ai_client = None
db = Database()


async def get_reply(user_id: int, user_name: str, message_text: str) -> str:
    api_keys = {
        "gemini": os.getenv("GEMINI_API_KEY"),
        "aws_access_key": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "aws_region": os.getenv("AWS_REGION", "us-east-1"),
        "bedrock_model_id": os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"),
    }
    controller = MessageController(api_keys=api_keys, db=db)
    return await controller.get_response(user_id, user_name, message_text)
