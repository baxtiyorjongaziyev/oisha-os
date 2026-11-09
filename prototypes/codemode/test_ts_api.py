from types import SimpleNamespace as NS

from ts_api import render_api


def test_render_api():
    tools = [
        NS(name="get_history", description="Get history.\nmore", inputSchema={
            "type": "object",
            "properties": {"chat_id": {"type": "integer"}, "limit": {"type": "integer"}},
            "required": ["chat_id"]}),
        NS(name="send_message", description="", inputSchema={
            "type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
    ]
    out = render_api(tools)
    assert "get_history(args: { chat_id: number; limit?: number }): Promise<unknown>;" in out
    assert "send_message(args: { text: string }): Promise<unknown>;" in out
    assert "/** Get history. */" in out
