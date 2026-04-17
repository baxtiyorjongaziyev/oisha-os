
import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from src.services.airtable_sync import AirtableSync

def test_pm_resolution():
    print("Testing PM Handle Resolution...")
    test_cases = [
        ("reccXjZIGIcRezKgB", "@Inomjon_JonBranding"),
        ("recPi9SROzJNK8SX7", "@jonbranding_pm"),
        (["reccXjZIGIcRezKgB"], "@Inomjon_JonBranding"),
        ("Inomjon", "@Inomjon_JonBranding"),
        ("Dilorom", "@jonbranding_pm"),
        (None, "@Inomjon"),
        ("UnknownID", "@Inomjon_JonBranding"), # Fallback
    ]
    
    at = AirtableSync()
    for val, expected in test_cases:
        resolved = at.resolve_pm_handle(val)
        status = "✅" if resolved == expected else "❌"
        print(f"{status} Input: {val} -> Resolved: {resolved} (Expected: {expected})")

if __name__ == "__main__":
    test_pm_resolution()
