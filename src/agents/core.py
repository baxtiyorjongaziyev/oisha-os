import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Barcha AI agentlar uchun bazaviy klass. Multi-API Fallback bilan."""

    def __init__(
        self,
        agent_id: str,
        system_prompt: str,
        api_keys: Dict[str, str],
        executor: Optional[Any] = None,
        db: Optional[Any] = None,
    ):
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.api_keys = api_keys
        self.executor = executor
        self.db = db
        self.memories: Dict[int, List[Dict[str, Any]]] = {}

        # Default model settings
        self.model_configs = {
            "gemini": {"model": "gemini-2.0-flash", "client": None},
            "groq": {"model": "llama-3.1-70b-versatile", "client": None},
        }

        # Clients initialization
        if "gemini" in api_keys:
            self.model_configs["gemini"]["client"] = genai.Client(
                api_key=api_keys["gemini"]
            )

    @abstractmethod
    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Vazifani bajarish."""
        pass

    async def call_ai_with_fallback(
        self, contents: Any, current_user_id: int, enable_tools: bool = True
    ) -> str:
        """Gemini tool-calling loop bilan. 429 xatosi bo'lsa retry qiladi."""
        from src.agents.tools import TOOL_DECLARATIONS

        # 1. Gemini (Primary) with Tool Calling
        if self.model_configs["gemini"]["client"]:
            try:
                # Tool calling loop (max 5 iterations to avoid infinite loops)
                for _ in range(5):
                    # Robust async call with retry logic
                    response = await self.safe_ai_call(
                        contents=contents,
                        tools=(
                            [{"function_declarations": TOOL_DECLARATIONS}]
                            if (enable_tools and TOOL_DECLARATIONS)
                            else None
                        ),
                    )

                    if not response:
                        return "Kechirasiz, AI resurslari vaqtincha band. Iltimos, birozdan so'ng urinib ko'ring. (429)"

                    # Tool call bormi?
                    tool_calls = []
                    if response.candidates and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if part.function_call:
                                tool_calls.append(part.function_call)
                            elif part.text:
                                logger.info(
                                    f"[{self.agent_id}] Gemini text response: {part.text[:100]}..."
                                )

                    if not tool_calls:
                        return response.text if response.text else "Javob bo'sh qaytdi."

                    # Tool larni bajarish
                    logger.info(
                        f"[{self.agent_id}] Gemini requested {len(tool_calls)} tools."
                    )
                    contents.append(response.candidates[0].content)

                    tool_responses = []
                    for tc in tool_calls:
                        if self.executor:
                            result = await self.executor.execute(
                                tc.name, tc.args, context_user_id=current_user_id
                            )
                        else:
                            result = {
                                "success": False,
                                "error": "Executor not initialized.",
                            }

                        tool_responses.append(
                            types.Part.from_function_response(
                                name=tc.name, response=result
                            )
                        )

                    contents.append(types.Content(role="user", parts=tool_responses))

            except Exception as e:
                logger.error(f"[{self.agent_id}] Gemini Agentic Error: {e}")

        return "Kechirasiz, texnik tanaffus."

    async def safe_ai_call(
        self,
        contents: Any,
        tools: Optional[List[Dict[str, Any]]] = None,
        retries: int = 5,
    ):
        """Exponential backoff bilan xavfsiz AI chaqiruvi (Synchronized with global standard)."""
        import asyncio
        import random

        client = self.model_configs["gemini"]["client"]
        model = self.model_configs["gemini"]["model"]

        for i in range(retries):
            try:
                # Use aio generate_content with tools if provided
                return await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt, tools=tools
                    ),
                )
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait_time = (2**i) + random.random()
                    logger.warning(
                        f"[{self.agent_id}] Rate limit hit (429). Retrying in {wait_time:.2f}s... (Attempt {i+1}/{retries})"
                    )
                    await asyncio.sleep(wait_time)
                elif (
                    "500" in err_str or "503" in err_str
                ):  # Handling temporary server errors
                    wait_time = (2**i) + random.random()
                    logger.warning(
                        f"[{self.agent_id}] Gemini Server Error. Retrying in {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise e
        return None

    async def load_session_history(
        self, user_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """User uchun chat tarixini yuklash (Xulosa bilan birga)."""
        if user_id in self.memories and self.memories[user_id]:
            return self.memories[user_id]

        self.memories[user_id] = []

        # 1. Avval saqlangan xulosani yuklash
        summary = None
        if self.db and hasattr(self.db, "get_chat_summary"):
            summary = await self.db.get_chat_summary(user_id)

        if summary:
            self.memories[user_id].append(
                {
                    "role": "user",
                    "content": f"[ESLATMA/CONTEXT: Avvalgi suhbatlar xulosasi: {summary}]",
                }
            )
            logger.info(
                f"[{self.agent_id}] Long-term summary loaded for user {user_id}"
            )

        # 2. Oxirgi xabarlarni yuklash
        if self.db and hasattr(self.db, "get_recent_messages"):
            try:
                recent = await self.db.get_recent_messages(user_id, limit=limit)
                if recent:
                    history = []
                    for item in recent:
                        role = item.get("role", "user")
                        parts = item.get("parts") or []
                        text = str(parts[0].get("text", "")) if parts else ""
                        if text:
                            history.append({"role": role, "content": text})

                    self.memories[user_id].extend(history)
                    logger.info(
                        f"[{self.agent_id}] Loaded {len(history)} messages from DB for user {user_id}"
                    )
            except Exception as e:
                logger.error(
                    f"[{self.agent_id}] Failed to load history for {user_id}: {e}"
                )

        return self.memories[user_id]

    async def check_and_summarize(self, user_id: int, threshold: int = 30):
        """Agar xabarlar soni thresholddan oshsa, xulosa qiladi."""
        if not self.db or not hasattr(self.db, "get_message_count"):
            return

        try:
            count = await self.db.get_message_count(user_id)
            if count >= threshold:
                logger.info(
                    f"[{self.agent_id}] Summarization triggered for user {user_id} (count: {count})"
                )

                recent_all = await self.db.get_recent_messages(user_id, limit=100)
                if not recent_all:
                    return

                history_str = "\n".join(
                    [
                        f"{'AI' if m['role']=='model' else 'User'}: {m['parts'][0]['text']}"
                        for m in recent_all
                    ]
                )
                new_summary = await self.summarize_history(user_id, history_str)

                if new_summary:
                    await self.db.set_chat_summary(user_id, new_summary)
                    # Muhim: Xotira keshini tozalaymiz, shunda keyingi safar yangi xulosa bilan yuklanadi
                    if user_id in self.memories:
                        del self.memories[user_id]
                    logger.info(
                        f"[{self.agent_id}] Updated chat summary and cleared cache for user {user_id}"
                    )
        except Exception as e:
            logger.error(f"[{self.agent_id}] Summarization error for {user_id}: {e}")

    async def summarize_history(self, user_id: int, history_text: str) -> Optional[str]:
        """Gemini yordamida suhbat tarixini qisqa va mazmuni xulosaga aylantiradi."""
        prompt = f"""
Siz profesional sales-assistent Oishasiz. Quyidagi suhbat tarixini tahlil qiling va mijoz haqidagi ENG MUHIM ma'lumotlarni qisqa (max 150-200 so'z) xulosa shaklida yozing.
Xulosada quyidagilar bo'lishi shart (agar bo'lsa):
1. Mijozning ismi va biznesi/sohasi.
2. Qaysi xizmat bilan qiziqyapti.
3. Asosiy ehtiyoji yoki muammosi.
4. Muhokama qilingan narx yoki budjet.
5. Hozirgi holat (qaysi bosqichda to'xtagan).
6. Mijozning xarakteri yoki muhim e'tirozlari.

Suhbat tarixi:
{history_text}

Xulosa (O'zbek tilida, profesional va lo'nda):
"""
        try:
            response = await self.safe_ai_call(
                contents=[{"role": "user", "parts": [{"text": prompt}]}], tools=None
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.error(f"[{self.agent_id}] Gemini summarization API error: {e}")
        return None

    def get_session_history(self, user_id: int) -> List[Dict[str, Any]]:
        return self.memories.get(user_id, [])

    def update_history(self, user_id: int, role: str, message: str):
        if user_id not in self.memories:
            self.memories[user_id] = []

        self.memories[user_id].append({"role": role, "content": message})
        if len(self.memories[user_id]) > 20:
            self.memories[user_id] = self.memories[user_id][-20:]


class AgentManager:
    """Agentlarni boshqarish va ularni orkestratsiya qilish."""

    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self.agents: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent):
        self.agents[agent.agent_id] = agent

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        return self.agents.get(agent_id)
