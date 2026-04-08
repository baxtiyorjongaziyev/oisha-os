import sys
import os
import traceback

sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))
sys.path.append(os.path.join(os.getcwd(), "src", "services"))

try:
    print("--- IMPORT TEST START ---")
    import src.main
    print("--- IMPORT TEST SUCCESS ---")
except Exception:
    print("--- IMPORT TEST FAILED ---")
    traceback.print_exc()
