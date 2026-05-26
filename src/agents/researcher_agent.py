import logging
from typing import Any, Dict, List, Optional

from .core import BaseAgent
from .persona_router import PersonaRouter

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Deep research and OSINT agent.

    Execution order:
      1. Run search tools (Google Drive + local files) to gather raw data
      2. Feed results into Gemini with RESEARCHER mission prompt
      3. Return synthesized analysis
    """

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        await self.load_session_history(user_id)
        self.update_history(user_id, "user", task_description)

        # --- Step 1: gather raw data via tools ---
        search_results = await self._gather_search_data(task_description, user_id)

        # --- Step 2: build enriched prompt ---
        persona_ctx = PersonaRouter.route(task_description, "", "researcher")
        researcher_instruction = (
            "\n\n[MISSION: RESEARCHER]\n"
            "Siz Deep Research va OSINT mutaxassisisiz. "
            "Quyidagi qidiruv natijalarini tahlil qiling va har tomonlama xulosa tayyorlang.\n\n"
            "[SEARCH RESULTS]\n" + search_results + persona_ctx
            if search_results
            else (
                "\n\n[MISSION: RESEARCHER]\n"
                "Siz Deep Research va OSINT mutaxassisisiz. "
                "Chuqur tahlil qiling, eng so'nggi ma'lumotlarga asoslaning."
                + persona_ctx
            )
        )

        history = self.get_session_history(user_id)
        contents = [
            {
                "role": "user" if t["role"] == "user" else "model",
                "parts": [{"text": t["content"]}],
            }
            for t in history
        ]

        original = self.system_prompt
        self.system_prompt = (
            original
            + researcher_instruction
            + (f"\n\n[CONTEXT]: {context}" if context else "")
        )
        reply = await self.call_ai_with_fallback(contents, user_id)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply

    async def _gather_search_data(self, query: str, user_id: int) -> str:
        if not self.executor:
            return ""

        results: List[str] = []

        # Google Drive search
        try:
            drive_result = await self.executor.execute(
                "google_drive_search",
                {"query": query, "max_results": 5},
                context_user_id=user_id,
            )
            if drive_result and drive_result.get("items"):
                items = drive_result["items"]
                summary = "\n".join(
                    f"- [{i.get('name', '?')}] {i.get('snippet', '')}"
                    for i in items[:5]
                )
                results.append(f"Google Drive:\n{summary}")
        except Exception as e:
            logger.debug(f"[RESEARCHER] Drive search skipped: {e}")

        # Local file search
        try:
            local_result = await self.executor.execute(
                "search_local_files",
                {"query": query, "max_results": 5},
                context_user_id=user_id,
            )
            if local_result and local_result.get("matches"):
                matches = local_result["matches"]
                summary = "\n".join(
                    f"- [{m.get('file', '?')}] {m.get('snippet', '')}"
                    for m in matches[:5]
                )
                results.append(f"Local files:\n{summary}")
        except Exception as e:
            logger.debug(f"[RESEARCHER] Local search skipped: {e}")

        return "\n\n".join(results)
