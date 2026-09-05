"""
Background clipboard watcher that automatically detects copied AI API keys,
tests them live, and injects them into local and Oracle VM .env.
"""
import time
import os
import sys
import subprocess

try:
    import pyperclip
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pyperclip", "-q"])
    import pyperclip

from scripts.auto_inject_ai_keys import detect_provider, test_key, sync_key

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def watch(duration_seconds=300):
    print(f"[*] Clipboard key watcher active for {duration_seconds}s...")
    print("[*] Copy any API Key (Gemini, Cerebras, SambaNova, OpenRouter, etc.) to your clipboard!")
    
    last_clip = ""
    seen_keys = set()
    start_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        try:
            current = pyperclip.paste().strip()
            if current and current != last_clip and current not in seen_keys:
                last_clip = current
                prov = detect_provider(current)
                if prov:
                    print(f"\n[!] Detected {prov.upper()} key in clipboard: {current[:8]}...{current[-4:]}")
                    seen_keys.add(current)
                    if test_key(prov, current):
                        sync_key(prov, current)
                        print(f"[SUCCESS] {prov.upper()} key verified and synced to local & Oracle VM .env!\n")
        except Exception as e:
            pass
        time.sleep(1)

if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    watch(dur)
