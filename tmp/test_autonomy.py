import sys
import os
import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Root path qo'shish
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))

from src.database import Database
from src.services.proactive_worker import send_morning_briefing, send_overdue_nudges, check_amocrm_stagnation

async def test_autonomy():
    print("Testing Autonomy Features...")
    db = Database()
    
    # 1. Setup Dummy Data
    db.upsert_user(999002, "Priority Member", username="priority_user", role="Manager")
    
    # High Priority Task for Morning Briefing
    deadline_soon = (datetime.datetime.now() + datetime.timedelta(hours=5)).isoformat()
    db.add_task(assigned_to=999002, description="Critical Launch", deadline=deadline_soon, priority="High", title="Launch Project")
    
    # Overdue Task for Nudges
    deadline_past = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
    db.add_task(assigned_to=999002, description="Missing Report Fix", deadline=deadline_past, title="Fix DB")

    print("Dummy data ready.")

    # 2. Mock Bot and AI
    with patch("telegram.Bot") as MockBot, \
         patch("src.services.proactive_worker.generate_ai_message", new_callable=AsyncMock) as MockAI:
        
        mock_bot_inst = MockBot.return_value
        mock_bot_inst.send_message = AsyncMock()
        MockAI.return_value = "AI Generated: Good morning team! Let's crush those priorities."

        # Test Morning Briefing
        print("\n--- Testing Morning Briefing ---")
        await send_morning_briefing()
        
        # Test Nudges
        print("\n--- Testing Overdue Nudges ---")
        await send_overdue_nudges()
        
        # Verify calls
        print("\nVerification:")
        for call in mock_bot_inst.send_message.call_args_list:
            chat_id = call.kwargs.get('chat_id') or call.args[0]
            text = call.kwargs.get('text') or (call.args[1] if len(call.args)>1 else "")
            print(f"Sent to {chat_id}: {text[:100]}...")

    print("\nAutonomy Test Completed.")

if __name__ == "__main__":
    asyncio.run(test_autonomy())
