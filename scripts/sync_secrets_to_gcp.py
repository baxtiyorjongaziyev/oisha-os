import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

if os.getenv("OISHA_ALLOW_GCP") != "1":
    raise SystemExit(
        "BLOCKED: Oisha production Oracle VMda ishlaydi. "
        "Google Cloud secret sync o'chirilgan. Zarur bo'lsa OISHA_ALLOW_GCP=1 qo'ying."
    )

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
        print("Skipping an unset secret.")
        return

    print("Syncing configured secret...")
    try:
        # Check if secret exists
        cmd_exists = ["gcloud", "secrets", "describe", name, "--project", PROJECT_ID]
        result = subprocess.run(cmd_exists, capture_output=True, text=True)  # nosec

        if result.returncode != 0:
            print("Creating missing secret container...")
            subprocess.run(
                [
                    "gcloud",
                    "secrets",
                    "create",
                    name,
                    "--project",
                    PROJECT_ID,
                    "--replication-policy",
                    "automatic",
                ],
                check=True,
            )  # nosec

        # Add version
        process = subprocess.Popen(
            [
                "gcloud",
                "secrets",
                "versions",
                "add",
                name,
                "--project",
                PROJECT_ID,
                "--data-file=-",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )  # nosec
        process.communicate(input=value)

        if process.returncode == 0:
            print("Secret updated successfully.")
        else:
            print("Secret update failed; inspect gcloud audit logs.")

    except Exception:
        print("Secret sync failed; inspect gcloud audit logs.")


if __name__ == "__main__":
    print("Starting secret sync.")
    for name, value in SECRETS_TO_SYNC.items():
        sync_secret(name, value)
    print("Sync finished.")
