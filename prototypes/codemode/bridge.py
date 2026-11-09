"""Prototype Code Mode runner. Names are namespace-qualified ("telegram.get_history").

Reads run via call_tool. Anything else is refused, or queued (never executed)
when queue_mutation is given -> caller turns the queue into ONE owner approval.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

RUNNER = Path(__file__).with_name("runner.mjs")
DOCKER_IMAGE = "oisha-codemode-runner:latest"
ALLOWED_SANDBOXES = ("docker", "node")
ALLOWED_NAMESPACES = frozenset({"telegram", "amo"})
_NS_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_inputs(sandbox: str, namespaces: tuple[str, ...], allow_unsafe_node: bool) -> None:
    if sandbox not in ALLOWED_SANDBOXES:
        raise ValueError(f"unsupported sandbox: {sandbox!r}")
    if sandbox == "node" and not allow_unsafe_node:
        # Node 24 --permission does not block network; never use for untrusted code.
        raise ValueError("node sandbox is development-only; use sandbox='docker'")
    if not namespaces or any(not _NS_RE.match(n) or n not in ALLOWED_NAMESPACES for n in namespaces):
        raise ValueError(f"invalid namespaces: {namespaces!r}")


def build_command(sandbox: str, script_path: Path, namespaces: str) -> list[str]:
    """sandbox='node' (dev: permission model + vm) or 'docker' (prod: no network)."""
    if sandbox == "docker":
        return [
            shutil.which("docker") or "docker", "run", "--rm", "-i",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--memory", "128m",
            "--pids-limit", "64", "--user", "65534:65534",
            "-v", f"{script_path.parent}:/work:ro",
            DOCKER_IMAGE, "/work/" + script_path.name, namespaces, "/work",
        ]
    return [
        shutil.which("node") or "node", "--permission",
        f"--allow-fs-read={RUNNER}", f"--allow-fs-read={script_path.parent}",
        str(RUNNER), str(script_path), namespaces, str(script_path.parent),
    ]


async def run_script(
    script: str,
    call_tool: Callable[[str, dict], Awaitable[Any]],
    is_read: Callable[[str], bool],
    *,
    namespaces: tuple[str, ...] = ("telegram",),
    queue_mutation: Callable[[str, dict], Any] | None = None,
    sandbox: str = "docker",
    allow_unsafe_node: bool = False,
    max_calls: int = 200,
    timeout: float = 60.0,
    max_result_chars: int = 20000,
) -> Any:
    validate_inputs(sandbox, tuple(namespaces), allow_unsafe_node)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp).resolve()
        sp = tmp_dir / "script.js"
        sp.write_text(script, encoding="utf-8")
        if sp.resolve().parent != tmp_dir:
            raise ValueError("script path escaped managed directory")
        # Container user (65534) must traverse the dir and read the file; nobody else needs write.
        os.chmod(tmp_dir, 0o755)
        os.chmod(sp, 0o644)
        keep = ("SYSTEMROOT", "SystemRoot", "PATH") if sandbox == "docker" else ("SYSTEMROOT", "SystemRoot")
        proc = await asyncio.create_subprocess_exec(
            *build_command(sandbox, sp, ",".join(namespaces)),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={k: v for k, v in os.environ.items() if k in keep},
        )

        async def loop() -> Any:
            calls = 0
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    raise RuntimeError("sandbox exited without result")
                msg = json.loads(raw)
                if msg.get("done"):
                    if "error" in msg:
                        raise RuntimeError(f"script error: {msg['error']}")
                    if len(json.dumps(msg["result"], ensure_ascii=False)) > max_result_chars:
                        raise RuntimeError("result too large; return less data")
                    return msg["result"]
                calls += 1
                name, reply = msg["name"], {"id": msg["id"]}
                if calls > max_calls:
                    reply["error"] = "call limit exceeded"
                elif is_read(name):
                    try:
                        reply["result"] = await call_tool(name, msg["args"])
                    except Exception as exc:
                        reply["error"] = type(exc).__name__
                elif queue_mutation is not None:
                    try:
                        reply["result"] = queue_mutation(name, msg["args"])
                    except Exception as exc:
                        reply["error"] = str(exc)
                else:
                    reply["error"] = f"{name}: mutation not allowed in read-only code mode"
                proc.stdin.write((json.dumps(reply, default=str) + "\n").encode())
                await proc.stdin.drain()

        try:
            return await asyncio.wait_for(loop(), timeout)
        finally:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
