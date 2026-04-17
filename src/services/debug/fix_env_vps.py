import os
import sys

def update_env(env_path, configs):
    """
    configs: list of strings 'KEY=VALUE'
    """
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()

    updated_configs = {}
    for cfg in configs:
        if '=' in cfg:
            k, v = cfg.split('=', 1)
            updated_configs[k] = v

    new_lines = []
    found_keys = set()

    for line in lines:
        matched = False
        for k, v in updated_configs.items():
            if line.startswith(k + '='):
                new_lines.append(f'{k}={v}\n')
                found_keys.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in updated_configs.items():
        if k not in found_keys:
            new_lines.append(f'{k}={v}\n')

    with open(env_path, 'w') as f:
        f.writelines(new_lines)
    print("Environment updated successfully.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 fix_env_vps.py <env_path> KEY1=VALUE1 KEY2=VALUE2 ...")
    else:
        update_env(sys.argv[1], sys.argv[2:])
