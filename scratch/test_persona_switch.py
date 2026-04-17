import sys
import os

# Context
project_dir = os.getcwd()
sys.path.append(project_dir)

from src.services.core.persona_hub import get_persona, INTERNAL_COO_PROMPT, EXTERNAL_CONCIERGE_PROMPT

def test_persona_logic():
    print("--- TESTING PERSONA HUB ---")
    
    # Test 1: Team Member - General Task
    persona = get_persona(is_team_member=True, task_type="general")
    print(f"CASE 1 (Team Member, General): {'PASS (Internal)' if persona == INTERNAL_COO_PROMPT else 'FAIL'}")
    
    # Test 2: Client - General Task
    persona = get_persona(is_team_member=False, task_type="general")
    print(f"CASE 2 (Client, General): {'PASS (External)' if persona == EXTERNAL_CONCIERGE_PROMPT else 'FAIL'}")
    
    # Test 3: Team Member - Client Draft Request
    persona = get_persona(is_team_member=True, task_type="client_draft")
    print(f"CASE 3 (Team Member, Client Draft): {'PASS (External)' if persona == EXTERNAL_CONCIERGE_PROMPT else 'FAIL'}")

    print("\n--- PERSONA PREVIEW ---")
    print(f"EXTERNAL CONCIERGE PREVIEW:\n{EXTERNAL_CONCIERGE_PROMPT[:200]}...")

if __name__ == "__main__":
    test_persona_logic()
