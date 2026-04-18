import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = "jonbranding-85662071-ea38e"

SECRETS_TO_SYNC = {
    "BOT_TOKEN": os.getenv("BOT_TOKEN"),
    "API_ID": os.getenv("API_ID"),
    "API_HASH": os.getenv("API_HASH"),
    "USERBOT_SESSION_STRING": os.getenv("USERBOT_SESSION_STRING"),
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "AMOCRM_CLIENT_ID": os.getenv("AMOCRM_CLIENT_ID"),
    "AMOCRM_CLIENT_SECRET": os.getenv("AMOCRM_CLIENT_SECRET"),
    "AMOCRM_REDIRECT_URL": os.getenv("AMOCRM_REDIRECT_URL"),
    "TURSO_AUTH_TOKEN": os.getenv("TURSO_AUTH_TOKEN"),
    "AIRTABLE_API_KEY": os.getenv("AIRTABLE_API_KEY"),
}

def sync_secret(name, value):
    if not value:
        print(f"Skipping {name} - No value found in .env")
        return
    
    print(f"Syncing {name}...")
    try:
        # Check if secret exists
        cmd_exists = ["gcloud", "secrets", "describe", name, "--project", PROJECT_ID]
        result = subprocess.run(cmd_exists, capture_output=True, text=True, shell=True)
        
        if result.returncode != 0:
            print(f"Creating secret {name}...")
            subprocess.run(["gcloud", "secrets", "create", name, "--project", PROJECT_ID, "--replication-policy", "automatic"], check=True, shell=True)
            
        # Add version
        process = subprocess.Popen(
            ["gcloud", "secrets", "versions", "add", name, "--project", PROJECT_ID, "--data-file=-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        stdout, stderr = process.communicate(input=value)
        
        if process.returncode == 0:
            print(f"{name} updated successfully.")
        else:
            print(f"Failed to update {name}: {stderr}")
            
    except Exception as e:
        print(f"Error syncing {name}: {e}")

if __name__ == "__main__":
    print(f"Starting Secret Sync to Project: {PROJECT_ID}")
    for name, value in SECRETS_TO_SYNC.items():
        sync_secret(name, value)
    print("Sync finished.")
