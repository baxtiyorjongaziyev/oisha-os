"""Composio integration service for Trello and Google Tasks."""
from typing import List, Dict, Any, Optional
import os
import structlog
from pydantic import SecretStr

logger = structlog.get_logger()

class ComposioTaskService:
    def __init__(self, api_key: Optional[SecretStr] = None):
        from src.settings import settings
        self.api_key = (api_key or settings.COMPOSIO_API_KEY)
        self._client = None

    def get_client(self):
        if self._client is not None:
            return self._client
        
        api_key_str = self.api_key.get_secret_value() if self.api_key else os.environ.get("COMPOSIO_API_KEY")
        if not api_key_str:
            logger.warning("[COMPOSIO] COMPOSIO_API_KEY is not configured.")
            return None
            
        try:
            from composio import Composio
            self._client = Composio(api_key=api_key_str)
            return self._client
        except Exception as e:
            logger.error(f"[COMPOSIO] Failed to initialize Composio client: {e}")
            return None

    async def fetch_tasks(self) -> List[Dict[str, Any]]:
        """Fetches tasks from Trello and Google Tasks using Composio.
        
        Returns a list of unified task dicts.
        """
        client = self.get_client()
        if not client:
            return []

        tasks = []
        
        # 1. Fetch Google Tasks
        try:
            from src.settings import settings
            tasklist_id = settings.COMPOSIO_GOOGLE_TASKLIST_ID
            
            if tasklist_id:
                logger.info(f"[COMPOSIO] Fetching Google Tasks from list: {tasklist_id}")
                res = client.tools.execute(
                    tool_slug="googletasks_list_tasks",
                    params={"tasklist": tasklist_id}
                )
            else:
                logger.info("[COMPOSIO] Fetching Google Tasks across all lists")
                res = client.tools.execute(
                    tool_slug="googletasks_list_all_tasks_across_all_lists",
                    params={}
                )
            
            # Parse Google Tasks response
            # Response typically contains a list under 'items' or directly
            if isinstance(res, dict):
                items = res.get("items") or res.get("data", {}).get("items") or []
                if not items and "tasks" in res:
                    items = res["tasks"]
                if not items and isinstance(res.get("response"), list):
                    items = res["response"]
            elif isinstance(res, list):
                items = res
            else:
                items = []

            for item in items:
                if not isinstance(item, dict):
                    continue
                tasks.append({
                    "title": item.get("title") or "Unnamed Task",
                    "description": item.get("notes") or item.get("description") or "",
                    "priority": "Medium",
                    "profit_estimate": self._extract_profit_estimate(item.get("title", "") + " " + (item.get("notes") or "")),
                    "external_task_id": f"googletasks_{item.get('id')}",
                    "source_manager": "googletasks"
                })
        except Exception as e:
            logger.error(f"[COMPOSIO] Google Tasks fetch failed: {e}")

        # 2. Fetch Trello Cards
        try:
            from src.settings import settings
            board_id = settings.COMPOSIO_TRELLO_BOARD_ID
            if board_id:
                logger.info(f"[COMPOSIO] Fetching Trello cards from board: {board_id}")
                # Common slug variations: trello_get_board_cards, trello_get_cards_on_board, trello_get_cards
                # Try trello_get_board_cards first
                try:
                    res = client.tools.execute(
                        tool_slug="trello_get_board_cards",
                        params={"id": board_id}
                    )
                except Exception:
                    # Fallback to general cards search or board lists
                    res = client.tools.execute(
                        tool_slug="trello_get_cards",
                        params={"boardId": board_id}
                    )

                if isinstance(res, dict):
                    items = res.get("items") or res.get("cards") or res.get("response") or []
                elif isinstance(res, list):
                    items = res
                else:
                    items = []

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    tasks.append({
                        "title": item.get("name") or "Unnamed Card",
                        "description": item.get("desc") or item.get("description") or "",
                        "priority": "High" if item.get("dueComplete") is False and item.get("due") else "Medium",
                        "profit_estimate": self._extract_profit_estimate(item.get("name", "") + " " + (item.get("desc") or "")),
                        "external_task_id": f"trello_{item.get('id')}",
                        "source_manager": "trello"
                    })
        except Exception as e:
            logger.error(f"[COMPOSIO] Trello fetch failed: {e}")

        return tasks

    def _extract_profit_estimate(self, text: str) -> int:
        """Helper to extract dollar amount from task title or description."""
        import re
        # Find $1500 or 1500$ or 1500 USD or 1500 dollar
        matches = re.findall(r'\$?(\d+)\s*(?:\$|usd|dollar|foyda)', text.lower())
        if matches:
            try:
                return int(matches[0])
            except ValueError:
                pass
        
        matches_prefix = re.findall(r'\$\s*(\d+)', text)
        if matches_prefix:
            try:
                return int(matches_prefix[0])
            except ValueError:
                pass
        return 0
