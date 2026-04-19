"""
Oisha-OS Agentic Bootstrap - XAVFSIZ versiya
Token .env fayldan o'qiladi, kodda saqlanmaydi
"""
import os
import base64
import requests
from pathlib import Path

# .env faylni yuklash
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

load_env()

# SOZLAMALAR - .env fayldan o'qiladi
TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "baxtiyorjongaziyev/oisha-os"

if not TOKEN:
    print("❌ GITHUB_TOKEN topilmadi!")
    print("📋 Iltimos, .env faylga quyidagini qo'shing:")
    print("GITHUB_TOKEN=github_pat_xxx")
    exit(1)

files = {
    "src/services/core/__init__.py": "# Oisha Core Package",
    "src/services/core/github_manager.py": """import os
from github import Github

class GitHubManager:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN o'rnatilmagan!")
        self.repo = Github(self.token).get_repo("baxtiyorjongaziyev/oisha-os")

    def push(self, path, content, message):
        try:
            try:
                old = self.repo.get_contents(path)
                self.repo.update_file(path, message, content, old.sha)
            except:
                self.repo.create_file(path, message, content)
            return True
        except Exception as e:
            print(f"Xato: {e}")
            return False

github_manager = GitHubManager()
""",
    "src/services/core/agent_brain.py": """import logging
import os
from src.services.core.github_manager import github_manager

class OishaBrain:
    async def evolve(self, task: str):
        logging.info(f"Oisha o'zini yangilamoqda: {task}")
        # Bu yerda AI kod yozadi
        return True

oisha_brain = OishaBrain()
"""
}

def upload():
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    for path, content in files.items():
        url = f"https://api.github.com/repos/{REPO}/contents/{path}"
        
        # SHA ni olish (agar fayl bo'lsa)
        r = requests.get(url, headers=headers)
        sha = r.json().get('sha') if r.status_code == 200 else None
        
        payload = {
            "message": "Agentic Bootstrap - Xavfsiz versiya",
            "content": base64.b64encode(content.encode()).decode(),
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        
        r = requests.put(url, headers=headers, json=payload)
        if r.status_code in [200, 201]:
            print(f"✅ Yuklandi: {path}")
        else:
            print(f"❌ Xato ({path}): {r.status_code}")
            print(r.text[:200])

if __name__ == "__main__":
    upload()
