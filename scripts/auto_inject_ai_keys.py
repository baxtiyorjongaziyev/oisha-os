"""
Auto-detects, tests, and injects AI API keys into local and Oracle VM .env files.
"""
import os
import sys
import httpx
import subprocess

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

PROVIDERS = {
    "gemini": {
        "env_var": "GEMINI_API_KEY",
        "test_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-2.5-flash",
    },
    "cerebras": {
        "env_var": "CEREBRAS_API_KEY",
        "test_url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
    },
    "sambanova": {
        "env_var": "SAMBANOVA_API_KEY",
        "test_url": "https://api.sambanova.ai/v1/chat/completions",
        "model": "Meta-Llama-3.3-70B-Instruct",
    },
    "openrouter": {
        "env_var": "OPENROUTER_API_KEY",
        "test_url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.2-3b-instruct:free",
    },
    "mistral": {
        "env_var": "MISTRAL_API_KEY",
        "test_url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-small-latest",
    },
    "groq": {
        "env_var": "GROQ_API_KEY",
        "test_url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "groq/compound",
    },
}

def detect_provider(key: str) -> str:
    key = key.strip()
    if key.startswith("AIzaSy"):
        return "gemini"
    elif key.startswith("csk-"):
        return "cerebras"
    elif key.startswith("sk-or-"):
        return "openrouter"
    elif key.startswith("gsk_"):
        return "groq"
    elif key.startswith("nvapi-"):
        return "nvidia"
    return ""

def test_key(provider: str, key: str) -> bool:
    spec = PROVIDERS.get(provider)
    if not spec:
        return False
    try:
        res = httpx.post(
            spec["test_url"],
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": spec["model"],
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            },
            timeout=10.0,
        )
        if res.status_code == 200:
            print(f"[{provider.upper()}] Test Call Successful: 200 OK")
            return True
        else:
            print(f"[{provider.upper()}] Test Call Failed: {res.status_code} -> {res.text[:120]}")
            return False
    except Exception as e:
        print(f"[{provider.upper()}] Test Call Exception: {e}")
        return False

def sync_key(provider: str, key: str):
    env_var = PROVIDERS[provider]["env_var"]
    
    # 1. Update local .env
    local_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(local_env):
        lines = open(local_env, "r", encoding="utf-8").read().splitlines()
        filtered = [l for l in lines if not l.startswith(env_var + "=")]
        filtered.append(f"{env_var}={key}")
        with open(local_env, "w", encoding="utf-8") as f:
            f.write("\n".join(filtered) + "\n")
        print(f"Local .env updated: {env_var}")
        
    # 2. Update Oracle VM .env
    ssh_key = "C:/Users/baxti/.ssh/oracle_free_tier_ed25519"
    remote_cmd = f"python3 -c \"lines = open('/home/ubuntu/oisha-os/.env').read().splitlines(); open('/home/ubuntu/oisha-os/.env', 'w').write('\\n'.join([l for l in lines if not l.startswith('{env_var}=')] + ['{env_var}={key}']) + '\\n')\""
    p = subprocess.run(["ssh", "-i", ssh_key, "-o", "StrictHostKeyChecking=no", "ubuntu@163.192.10.104", remote_cmd], capture_output=True, text=True)
    if p.returncode == 0:
        print(f"Oracle VM .env updated: {env_var}")
    else:
        print(f"Oracle VM update failed: {p.stderr}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        raw = sys.argv[1].strip()
        prov = sys.argv[2].strip() if len(sys.argv) > 2 else detect_provider(raw)
        if prov:
            print(f"Detected Provider: {prov}")
            if test_key(prov, raw):
                sync_key(prov, raw)
                print("Key injected and verified successfully!")
        else:
            print("Could not auto-detect provider. Please specify provider name.")
