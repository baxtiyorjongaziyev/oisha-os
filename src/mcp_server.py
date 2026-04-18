import sys
import logging
import asyncio
from typing import List, Dict, Any
import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.airtable_sync import AirtableSync
from src.settings import settings

# Setup logging to stderr as per MCP debugging best practices
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("OishaMCP")

# Create the MCP Server
server = Server("oisha-os-enterprise")

# Initialize services
amocrm = AmoCRMSync(
    subdomain=settings.AMOCRM_SUBDOMAIN,
    client_id=settings.AMOCRM_CLIENT_ID,
    client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
    redirect_url=settings.AMOCRM_REDIRECT_URL
)
airtable = AirtableSync()

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools for Oisha-OS."""
    return [
        Tool(
            name="check_amo_auth",
            description="AmoCRM avtorizatsiya holatini tekshirish va 401/403 xatolarini diagnostika qilish.",
            input_schema={"type": "object", "properties": {}}
        ),
        Tool(
            name="list_lost_leads",
            description="AmoCRMdagi 'Lost' (143) statusidagi bitimlar sonini va ro'yxatini olish.",
            input_schema={"type": "object", "properties": {}}
        ),
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
    """Handle tool calls from MCP hosts."""
    logger.info(f"[MCP CALL] Tool: {name}, Args: {arguments}")
    
    try:
        if name == "check_amo_auth":
            status = await amocrm.get_account_status()
            if status:
                return [TextContent(type="text", text=f"✅ AUTH OK: {status.get('name')} (ID: {status.get('id')})")]
            else:
                return [TextContent(type="text", text="❌ AUTH FAILED: Token expired or invalid. Need new Authorization Code.")]

        elif name == "list_lost_leads":
            # Using raw request for status evaluation
            import requests
            url = f"{amocrm.base_url}/api/v4/leads?filter[statuses][0][status_id]=143&limit=250"
            resp = requests.get(url, headers=amocrm._get_headers())
            if resp.status_code == 200:
                leads = resp.json().get("_embedded", {}).get("leads", [])
                return [TextContent(type="text", text=f"🔍 Found {len(leads)} leads with status 'Lost' (143).")]
            else:
                return [TextContent(type="text", text=f"❌ FAILED to fetch leads: {resp.status_code} - {resp.text}")]

        elif name == "create_amo_lead":
            success = amocrm.create_lead(arguments['name'], arguments['phone'], arguments.get('price', 0))
            if success:
                return [TextContent(type="text", text=f"✅ SUCCESS: Lead '{arguments['name']}' created in AmoCRM.")]
            return [TextContent(type="text", text=f"❌ FAILED to create lead.")]
        
        elif name == "get_sales_report":
            report = amocrm.get_sales_report()
            text = f"📊 REPORT:\nFact: {report['fact']:,} so'm\nTarget: {report['target']:,} so'm\nProgress: {report['percent']:.1f}%"
            return [TextContent(type="text", text=text)]

        elif name == "get_airtable_projects":
            projects = airtable.get_projects()
            return [TextContent(type="text", text=f"📂 Found {len(projects)} projects in Airtable.")]
            
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"[MCP ERROR] {e}", exc_info=True)
        return [TextContent(type="text", text=f"❌ Error executing tool '{name}': {str(e)}")]

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
