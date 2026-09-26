'''\
Instagram Unanswered Comments Service
Runs audit_unanswered_comments.py periodically (default every 10 minutes) and logs output.
Ensures UTF-8 stdout on Windows and handles Unicode safely.
'''
import sys
import time
import subprocess
import os
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# Directory for service logs
log_dir = Path(__file__).resolve().parent.parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "instagram_unanswered_service.log"

def run_audit():
    """Execute the audit script and capture its output."""
    audit_script = Path(__file__).resolve().parent / "audit_unanswered_comments.py"
    # Use subprocess to run the script, capture both stdout and stderr
    proc = subprocess.run([sys.executable, str(audit_script)], capture_output=True, text=True)
    return proc.stdout, proc.stderr, proc.returncode

def log(message: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

if __name__ == "__main__":
    log("Service started.")
    while True:
        try:
            out, err, rc = run_audit()
            if rc == 0:
                log(f"Audit succeeded. Output:\n{out.strip()}")
            else:
                log(f"Audit failed (code {rc}). Stderr:\n{err.strip()}")
        except Exception as e:
            log(f"Exception during audit: {e}")
        # Wait 10 minutes before next run
        time.sleep(600)
