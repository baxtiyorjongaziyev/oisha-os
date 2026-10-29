"""Hermes Agent integration provider for Oisha-OS.

Connects Oisha to local Hermes Agent (Nous Research) for human-like conversational
reasoning, personalized client replies, and multi-turn agent execution with Harness Loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from typing import Any, Dict, Optional, Tuple

from src.services.core.ai.hermes_harness import get_hermes_harness

logger = logging.getLogger("HermesProvider")

_ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SESSION_ID_REGEX = re.compile(
    r"(?:session_id:\s*([0-9a-zA-Z_]+)|hermes\s+--resume\s+([0-9a-zA-Z_]+))",
    re.IGNORECASE,
)


def strip_ansi(text: str) -> str:
    """Remove ANSI terminal color and formatting escape sequences."""
    return _ANSI_REGEX.sub("", text)


def extract_session_id(raw_output: str) -> Optional[str]:
    """Extract Hermes session identifier from CLI output if available."""
    text = strip_ansi(raw_output or "")
    match = _SESSION_ID_REGEX.search(text)
    if match:
        return match.group(1) or match.group(2)
    return None


def clean_hermes_output(raw_output: str) -> str:
    """Extract clean response text from Hermes CLI output."""
    text = strip_ansi(raw_output or "").strip()
    if not text:
        return ""

    # Match content between Hermes response box borders
    box_match = re.search(r"╭─[^\n]*\n(.*?)╰─", text, re.DOTALL)
    if box_match:
        content = box_match.group(1).strip()
        lines = [line.strip() for line in content.splitlines()]
        text = "\n".join(lines).strip()

    # Clean banners, session lines, and resume info
    clean = re.sub(r"Query:.*?\n", "", text, flags=re.DOTALL)
    clean = re.sub(r"Initializing agent\.\.\..*?─{10,}", "", clean, flags=re.DOTALL)
    clean = re.sub(r"↻\s*Resumed session.*?\n", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"session_id:\s*[0-9a-zA-Z_]+\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"Resume this session with:.*", "", clean, flags=re.DOTALL)
    clean = re.sub(r"Session:\s+.*", "", clean)
    clean = re.sub(r"Duration:\s+.*", "", clean)
    clean = re.sub(r"Messages:\s+.*", "", clean)
    clean = re.sub(r"Warning:\s*Unknown toolsets:.*?\n", "", clean, flags=re.IGNORECASE)
    return clean.strip()


class HermesAgentProvider:
    """Provider wrapper for invoking Hermes Agent CLI with Harness Loop support."""

    def __init__(self, executable_path: Optional[str] = None):
        self._custom_path = executable_path
        self._cached_bin: Optional[str] = None

    def find_executable(self) -> Optional[str]:
        """Locate hermes executable on system PATH or default Windows path."""
        if self._cached_bin and os.path.exists(self._cached_bin):
            return self._cached_bin

        if self._custom_path and os.path.exists(self._custom_path):
            self._cached_bin = self._custom_path
            return self._cached_bin

        # 1. Check system PATH
        on_path = shutil.which("hermes")
        if on_path:
            self._cached_bin = on_path
            return on_path

        # 2. Check standard Windows AppData location
        win_path = os.path.expandvars(
            r"%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe"
        )
        if os.path.exists(win_path):
            self._cached_bin = win_path
            return win_path

        return None

    def is_available(self) -> bool:
        """Check if Hermes executable is available on this machine."""
        return self.find_executable() is not None

    def _build_cli_cmd(
        self,
        exe: str,
        prompt: str,
        system_instruction: Optional[str],
        session_id: Optional[str],
        skills: str,
        toolsets: str,
    ) -> List[str]:
        """Construct command argument list for hermes CLI execution."""
        clean_prompt = prompt.strip()
        full_query = (
            f"{system_instruction.strip()}\n\n{clean_prompt}"
            if system_instruction
            else clean_prompt
        )
        cmd = [exe, "chat", "-Q"]
        if toolsets:
            cmd.extend(["-t", toolsets])
        if skills:
            cmd.extend(["-s", skills])
        cmd.extend(["--source", "oisha-os"])
        if session_id:
            cmd.extend(["--resume", str(session_id).strip()])
        cmd.extend(["-q", full_query])
        return cmd

    async def execute_raw_turn(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        session_id: Optional[str] = None,
        skills: str = "oisha-os",
        toolsets: str = "skills,memory",
        timeout: int = 120,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Execute a single raw CLI turn with Hermes, returning (reply, new_session_id)."""
        exe = self.find_executable()
        if not exe:
            logger.warning("[HERMES] Executable not found")
            return None, None

        cmd = self._build_cli_cmd(
            exe, prompt, system_instruction, session_id, skills, toolsets
        )
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=float(timeout)
            )

            raw_text = stdout.decode("utf-8", errors="replace")
            new_sess_id = extract_session_id(raw_text)
            clean_reply = clean_hermes_output(raw_text)

            if proc.returncode != 0:
                err_text = stderr.decode("utf-8", errors="replace")
                logger.warning(
                    "[HERMES] Process exited with code %s: %s",
                    proc.returncode,
                    err_text[:200],
                )

            return clean_reply or None, new_sess_id

        except asyncio.TimeoutError:
            logger.warning("[HERMES] Generation timed out after %ds", timeout)
            return None, None
        except Exception as exc:
            logger.error("[HERMES] Subprocess execution failed: %s", exc)
            return None, None

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        session_id: Optional[str] = None,
        destination: str = "general",
        timeout: int = 120,
        use_harness: bool = True,
    ) -> Optional[str]:
        """Generate response via Hermes Agent with Harness Loop verification."""
        if not use_harness:
            reply, _ = await self.execute_raw_turn(
                prompt,
                system_instruction=system_instruction,
                session_id=session_id,
                timeout=timeout,
            )
            return reply

        harness = get_hermes_harness()

        async def _turn_runner(p: str, s: Optional[str]) -> Optional[str]:
            reply, _ = await self.execute_raw_turn(
                p,
                system_instruction=s,
                session_id=session_id,
                timeout=timeout,
            )
            return reply

        return await harness.execute_loop(
            generate_fn=_turn_runner,
            prompt=prompt,
            system_instruction=system_instruction,
            destination=destination,
        )

    def get_telemetry(self) -> Dict[str, Any]:
        """Return live telemetry metrics from Hermes Harness."""
        return get_hermes_harness().telemetry.as_dict()


_HERMES_SINGLETON: Optional[HermesAgentProvider] = None


def get_hermes_provider() -> HermesAgentProvider:
    """Get singleton HermesAgentProvider instance."""
    global _HERMES_SINGLETON
    if _HERMES_SINGLETON is None:
        _HERMES_SINGLETON = HermesAgentProvider()
    return _HERMES_SINGLETON
