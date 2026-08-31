"""
AI Agent Tools — Gemini Function Calling tool declarations.
Composed from tool_schemas subpackage.
"""
from src.agents.agent_tools.tool_schemas.crm_schemas import CRM_TOOL_DECLARATIONS
from src.agents.agent_tools.tool_schemas.general_schemas import GENERAL_TOOL_DECLARATIONS

TOOL_DECLARATIONS = CRM_TOOL_DECLARATIONS + GENERAL_TOOL_DECLARATIONS

__all__ = [
    "TOOL_DECLARATIONS",
    "CRM_TOOL_DECLARATIONS",
    "GENERAL_TOOL_DECLARATIONS",
]
