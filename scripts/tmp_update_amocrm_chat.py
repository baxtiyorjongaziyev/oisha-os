import os
import sys

def main():
    env_path = "/home/ubuntu/oisha-os/.env"
    if not os.path.exists(env_path):
        print(f"Error: {env_path} does not exist.")
        sys.exit(1)

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Define the new variables — pass secrets via env, never hardcode
    required_env = ("AMOCRM_CHAT_ACCOUNT_ID", "AMOCRM_CHAT_CHANNEL_ID", "AMOCRM_CHAT_SECRET")
    missing = [k for k in required_env if not os.environ.get(k)]
    if missing:
        print(f"Error: missing required env vars: {', '.join(missing)}")
        sys.exit(1)
    new_vars = {k: os.environ[k] for k in required_env}

    # Filter out existing variables with the same names
    filtered_lines = []
    for line in lines:
        is_replaced = False
        for key in new_vars.keys():
            if line.startswith(f"{key}="):
                is_replaced = True
                break
        if not is_replaced:
            filtered_lines.append(line)

    # Append new variables
    if filtered_lines and not filtered_lines[-1].endswith("\n"):
        filtered_lines.append("\n")
    
    for key, value in new_vars.items():
        filtered_lines.append(f"{key}={value}\n")

    # Write back to .env
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(filtered_lines)

    print("AmoCRM Chat credentials successfully updated in .env.")

if __name__ == "__main__":
    main()
