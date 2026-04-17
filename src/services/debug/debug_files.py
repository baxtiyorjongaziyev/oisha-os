import os

def debug_file(name):
    print(f"--- Raw check: {name} ---")
    if os.path.exists(name):
        with open(name, "rb") as f:
            content = f.read()
            print(f"Bytes: {content[:200]!r}")
            try:
                print(f"Text:\n{content.decode('utf-8')}")
            except:
                print("Could not decode as UTF-8")
    else:
        print(f"File {name} not found.")

debug_file("settings.py")
debug_file("config.py")
