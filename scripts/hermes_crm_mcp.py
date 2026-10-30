"""Private stdio MCP entry point. No shell, SQL, write tools or user-supplied URLs."""
import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path
import sys


async def serve():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    wire = sys.stdout
    # Imported application modules can log to stdout. Keep the MCP wire pure.
    with contextlib.redirect_stdout(sys.stderr):
        import structlog
        logging.disable(logging.CRITICAL)

        def discard_log(*args, **kwargs):
            raise structlog.DropEvent

        structlog.configure(processors=[discard_log])
        from src.services.core.hermes_crm_bridge import HermesCrmBridge, RpcServer
        from src.services.core.hermes_crm_runtime import LiveCrmApi, RecordingTranscriber
        api = LiveCrmApi()
        server = RpcServer(HermesCrmBridge(api, RecordingTranscriber(api)))
        while line := await asyncio.to_thread(sys.stdin.readline):
            try:
                request = json.loads(line)
                reply = await server.respond(request)
            except (ValueError, TypeError, AttributeError):
                reply = {'jsonrpc': '2.0', 'id': None,
                         'error': {'code': -32700, 'message': 'Invalid request'}}
            if reply is not None:
                wire.write(json.dumps(reply, ensure_ascii=False) + '\n')
                wire.flush()


if __name__ == '__main__':
    asyncio.run(serve())
    # App token loading can start a background DB worker; EOF must terminate it.
    os._exit(0)
