import os
import sys

# Define the path to the real script in scripts/
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
real_script = os.path.join(project_root, "scripts", "mcp_server.py")

# Execute the real script
with open(real_script, "r", encoding="utf-8") as f:
    code = f.read()

# Make sure __file__ and sys.argv are handled correctly
sys.path.insert(0, os.path.join(project_root, "scripts"))
global_vars = {
    "__file__": real_script,
    "__name__": "__main__",
    "__package__": None,
}
exec(code, global_vars)
