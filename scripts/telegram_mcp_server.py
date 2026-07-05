import sys
import logging
import json
import os
import urllib.request
import urllib.error

# Ensure the project root is in sys.path so we can import from src
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mcp.server.fastmcp import FastMCP
import structlog

# Configure logging to stderr to avoid interfering with stdout-based MCP protocol
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)

# Re-configure structlog to write to stderr so it doesn't pollute stdout (critical for MCP stdio)
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    cache_logger_on_first_use=True,
)

logger = logging.getLogger("telegram-mcp")

# Initialize FastMCP server
mcp = FastMCP("telegram")

API_BASE_URL = "http://127.0.0.1:8080/internal/mcp"

def _request(url: str, data: bytes | None = None) -> urllib.request.Request:
    headers = {}
    secret = (os.environ.get("OISHA_API_SECRET") or "").strip()
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=headers)

@mcp.tool()
async def get_recent_dialogs(limit: int = 10) -> str:
    """
    Fetch the most recent Telegram dialogs (chats).
    """
    logger.info(f"Fetching recent dialogs, limit={limit}")
    url = f"{API_BASE_URL}/dialogs?limit={limit}"
    try:
        req = _request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return json.dumps(data, indent=2, ensure_ascii=False)
    except urllib.error.URLError as e:
        logger.error(f"Error fetching dialogs: {e}")
        return f"Error: Cannot connect to Telegram backend. {e}"

@mcp.tool()
async def get_chat_history(chat_id: str, limit: int = 20) -> str:
    """
    Fetch the recent message history for a specific Telegram chat/user ID.
    """
    logger.info(f"Fetching chat history for {chat_id}, limit={limit}")
    url = f"{API_BASE_URL}/messages/{chat_id}?limit={limit}"
    try:
        req = _request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return json.dumps(data, indent=2, ensure_ascii=False)
    except urllib.error.URLError as e:
        logger.error(f"Error fetching chat history: {e}")
        return f"Error: Cannot connect to Telegram backend. {e}"

@mcp.tool()
async def send_telegram_message(user_id: str, text: str) -> str:
    """
    Send a Telegram message to a specific user or group.
    """
    logger.info(f"Sending message to {user_id}")
    url = f"{API_BASE_URL}/send_message"
    payload = json.dumps({"user_id": str(user_id), "text": text}).encode("utf-8")
    try:
        req = _request(url, data=payload)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return f"Successfully sent message to {user_id}: {text}"
    except urllib.error.URLError as e:
        logger.error(f"Error sending message: {e}")
        return f"Error: Cannot connect to Telegram backend. {e}"

if __name__ == "__main__":
    # Start the server using stdio transport
    mcp.run(transport="stdio")

