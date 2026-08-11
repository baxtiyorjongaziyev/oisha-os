import os
import sys

def main():
    env_path = "/home/ubuntu/oisha-os/.env"
    if not os.path.exists(env_path):
        print(f"Error: {env_path} does not exist.")
        sys.exit(1)

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Define the new variables
    new_vars = {
        "AMOCRM_CHAT_ACCOUNT_ID": "32681154",
        "AMOCRM_CHAT_CHANNEL_ID": "0d2088fa-d9dc-43d8-9ed9-abe79aff1752",
        "AMOCRM_CHAT_SECRET": "FA0Ip3JU7sZ7gRijTPPNo3DRb9W9ul61t7XrZBSgCzLVixtrOw8ln8f88dmukODg"
    }

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
