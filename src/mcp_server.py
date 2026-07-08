import os
import runpy
import sys

# Define the path to the real script in scripts/
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
real_script = os.path.join(project_root, "scripts", "mcp_server.py")

# Run the real script as __main__ without exec() (bandit B102)
sys.path.insert(0, os.path.join(project_root, "scripts"))
runpy.run_path(real_script, run_name="__main__")
