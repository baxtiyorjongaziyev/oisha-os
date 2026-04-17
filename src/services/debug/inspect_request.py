import inspect
from telethon import functions, types

# Check the signature of GetForumTopicsRequest
try:
    print("Inspecting channels.GetForumTopicsRequest...")
    print(inspect.signature(functions.channels.GetForumTopicsRequest.__init__))
except Exception as e:
    print(f"channels error: {e}")

try:
    print("\nInspecting messages.GetForumTopicsRequest...")
    print(inspect.signature(functions.messages.GetForumTopicsRequest.__init__))
except Exception as e:
    print(f"messages error: {e}")
