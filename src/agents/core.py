
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Barcha AI agentlar uchun bazaviy klass. Multi-API Fallback bilan."""
    
    def __init__(self, agent_id: str, system_prompt: str, api_keys: Dict[str, str], executor: Optional[Any] = None, db: Optional[Any] = None):
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.api_keys = api_keys
        self.executor = executor
        self.db = db
        self.memories: Dict[int, List[Dict[str, Any]]] = {}
        
        # Default model settings
        self.model_configs = {
            "gemini": {"model": "gemini-2.0-flash", "client": None},
            "groq": {"model": "llama-3.1-70b-versatile", "client": None}
        }
        
        # Clients initialization
        if "gemini" in api_keys:
            self.model_configs["gemini"]["client"] = genai.Client(api_key=api_keys["gemini"])

    @abstractmethod
    async def process_task(self, user_id: int, task_description: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Vazifani bajarish."""
        pass

    async def call_ai_with_fallback(self, contents: Any, current_user_id: int) -> str:
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
                        tools=[{"function_declarations": TOOL_DECLARATIONS}] if TOOL_DECLARATIONS else None
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
                                logger.info(f"[{self.agent_id}] Gemini text response: {part.text[:100]}...")

                    if not tool_calls:
                        return response.text if response.text else "Javob bo'sh qaytdi."

                    # Tool larni bajarish
                    logger.info(f"[{self.agent_id}] Gemini requested {len(tool_calls)} tools.")
                    contents.append(response.candidates[0].content)
                    
                    tool_responses = []
                    for tc in tool_calls:
                        if self.executor:
                            result = await self.executor.execute(tc.name, tc.args, context_user_id=current_user_id)
                        else:
                            result = {"success": False, "error": "Executor not initialized."}
                        
                        tool_responses.append(types.Part.from_function_response(
                            name=tc.name,
                            response=result
                        ))

                    contents.append(types.Content(role="user", parts=tool_responses))

            except Exception as e:
                logger.error(f"[{self.agent_id}] Gemini Agentic Error: {e}")

        return "Kechirasiz, texnik tanaffus."

    async def safe_ai_call(self, contents: Any, tools: Optional[List[Dict[str, Any]]] = None, retries: int = 5):
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
                        system_instruction=self.system_prompt,
                        tools=tools
                    )
                )
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait_time = (2 ** i) + random.random()
                    logger.warning(f"[{self.agent_id}] Rate limit hit (429). Retrying in {wait_time:.2f}s... (Attempt {i+1}/{retries})")
                    await asyncio.sleep(wait_time)
                elif "500" in err_str or "503" in err_str: # Handling temporary server errors
                    wait_time = (2 ** i) + random.random()
                    logger.warning(f"[{self.agent_id}] Gemini Server Error. Retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise e
        return None

    def get_session_history(self, user_id: int) -> List[Dict[str, Any]]:
        if user_id not in self.memories and self.db:
            # Load from DB if not in memory
            recent = self.db.get_recent_messages(user_id, limit=20)
            if recent:
                # DB returns newest first, we need oldest first
                history = []
                for msg_text, is_ai in reversed(recent):
                    role = "assistant" if is_ai else "user"
                    history.append({"role": role, "content": msg_text})
                self.memories[user_id] = history
                logger.info(f"[{self.agent_id}] Loaded {len(history)} messages from DB for user {user_id}")
        
        return self.memories.get(user_id, [])

    def update_history(self, user_id: int, role: str, message: str):
        if user_id not in self.memories:
            # This might trigger a DB load if we use get_session_history first, 
            # but let's ensure we have a list.
            self.memories[user_id] = self.get_session_history(user_id)
        
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
