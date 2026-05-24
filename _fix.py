import sys 
print("FIXES START") 
 
# FIX 2: star imports 
open("src/airtable_sync.py","w",encoding="utf-8").write("from src.services.core.airtable_sync import AirtableSync\n") 
print("FIX2a done") 
open("src/amocrm_sync.py","w",encoding="utf-8").write("from src.services.core.amocrm_sync import AmoCRMSync\n") 
print("FIX2b done") 
 
# FIX 3: .gitignore append 
g = ["", "# Database ^& Session files", "bot_database.db", "*.session", "", "# Credentials", "service_account.json", "billing_accounts.json", "", "# Log files", "bot_final.log", "bot_startup.log", "sync_progress.log", "ai_response_last.txt", "", "# Python cache", "__pycache__/", "*.pyc", "*.pyo"] 
open(".gitignore","a",encoding="utf-8").write("\n".join(g) + "\n") 
print("FIX3 done")
