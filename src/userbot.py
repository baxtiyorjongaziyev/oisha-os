import os

from src.controllers.message_controller import MessageController
from src.database import Database

ai_client = None
db = Database()


async def get_reply(user_id: int, user_name: str, message_text: str) -> str:
    api_keys = {"gemini": os.getenv("GEMINI_API_KEY")}
    controller = MessageController(api_keys=api_keys, db=db)
    return await controller.get_response(user_id, user_name, message_text)
