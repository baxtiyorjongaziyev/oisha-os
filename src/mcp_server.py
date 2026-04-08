import os
import logging
from typing import List, Dict, Any
import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OishaMCP")

# Create the MCP Server
server = Server("oisha-os-enterprise")

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools for Oisha-OS."""
    return [
        Tool(
            name="create_amo_lead",
            description="AmoCRMda yangi bitim va kontakt yaratish.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Mijoz ismi"},
                    "phone": {"type": "string", "description": "Telefon raqami"},
                    "price": {"type": "number", "description": "Loyiha narxi (ixtiyoriy)"}
                },
                "required": ["name", "phone"]
            }
        ),
        Tool(
            name="get_sales_report",
            description="AmoCRMdan oylik sotuv hisobotini (Plan-Fakt) olish.",
            input_schema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_airtable_projects",
            description="Airtabledan loyihalar ro'yxatini va muddatlarini olish.",
            input_schema={"type": "object", "properties": {}}
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls from Manus or other hosts."""
    logger.info(f"[MCP CALL] Tool: {name}, Args: {arguments}")
    
    # Placeholder for actual cross-service calls
    if name == "create_amo_lead":
        return [TextContent(type="text", text=f"SUCCESS: Lead '{arguments['name']}' created in AmoCRM.")]
    
    elif name == "get_sales_report":
        return [TextContent(type="text", text="REPORT: 12 bitim, 45,000,000 so'm (56% progress).")]
        
    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    """Run the MCP server over stdio (standard for Manus/Claude/etc)."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
