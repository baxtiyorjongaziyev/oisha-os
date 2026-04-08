
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
        """Gemini tool-calling loop bilan. Agar Gemini xato bersa, fallback-ga o'tish."""
        from src.agents.tools import TOOL_DECLARATIONS
        
        # 1. Gemini (Primary) with Tool Calling
        if self.model_configs["gemini"]["client"]:
            try:
                # Tool calling loop (max 5 iterations to avoid infinite loops)
                for _ in range(5):
                    response = self.model_configs["gemini"]["client"].models.generate_content(
                        model=self.model_configs["gemini"]["model"],
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=self.system_prompt,
                            tools=[{"function_declarations": TOOL_DECLARATIONS}] if TOOL_DECLARATIONS else None
                        )
                    )
                    
                    # Tool call bormi?
                    tool_calls = []
                    if response.candidates and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if part.function_call:
                                tool_calls.append(part.function_call)
                            elif part.text:
                                logger.info(f"[{self.agent_id}] Gemini text response: {part.text[:100]}...")

                    if not tool_calls:
                        logger.info(f"[{self.agent_id}] No tools requested by Gemini.")
                        return response.text if response.text else "Javob bo'sh qaytdi."

                    # Tool larni bajarish
                    logger.info(f"[{self.agent_id}] Gemini requested {len(tool_calls)} tools.")
                    
                    # Model javobini (tool call ni) tarixga qo'shish
                    contents.append(response.candidates[0].content)
                    
                    # Tool natijalarini yig'ish
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

                    # Tool javobini contents ga qo'shish va modelni qayta chaqirish
                    contents.append(types.Content(role="user", parts=tool_responses))

            except Exception as e:
                logger.error(f"[{self.agent_id}] Gemini Agentic Error: {e}")

        return "Kechirasiz, texnik tanaffus."

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
