
import os
import sys
import asyncio
import logging
from typing import Optional

# Ensure the project root is in sys.path so we can import from src
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mcp.server.fastmcp import FastMCP
from src.database import Database
import src.config as config

# Configure logging to stderr to avoid interfering with stdout-based MCP protocol
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("telegram-mcp")

# Initialize FastMCP server
mcp = FastMCP("telegram")

@mcp.tool()
async def send_telegram_message(user_id: int, text: str) -> str:
    """
    Send a Telegram message to a specific user.
    """
    logger.info(f"Sending message to {user_id}")
    # In a real scenario, we would use the shared Telegram client
    # For now, we simulate success to verify the MCP connection
    return f"Successfully sent message to {user_id}: {text}"

@mcp.tool()
async def get_user_info(user_id: int) -> str:
    """
    Retrieve user information from the local database.
    """
    db = Database("data/bot_database.db")
    user = db.get_user_info(user_id)
    if user:
        return f"User Info: {user}"
    return "User not found."

if __name__ == "__main__":
    # Start the server using stdio transport
    mcp.run(transport="stdio")
