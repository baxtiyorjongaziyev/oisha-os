
import paramiko

def diagnose_db():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # 1. Look for all .db files
        print("--- ALL DB FILES ---")
        stdin, stdout, stderr = ssh.exec_command("find /home/baxtiyorjongaziyev/telegram_bot -name '*.db'")
        db_files = stdout.read().decode().strip().split('\n')
        for db in db_files:
            if not db: continue
            print(f"File: {db}")
            # Check tables via sqlite_master
            query_tables = "SELECT name FROM sqlite_master WHERE type='table';"
            stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db} "{query_tables}"')
            tables = stdout.read().decode().strip().split('\n')
            print(f"  Tables: {tables}")
            
            for table in tables:
                if not table: continue
                stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db} "SELECT COUNT(*) FROM {table}"')
                count = stdout.read().decode().strip()
                print(f"    Table {table}: {count} rows")
                
                if table == "message_logs":
                    print("    Fetching last 5 messages from message_logs...")
                    q_last = "SELECT user_id, message, is_ai, timestamp FROM message_logs ORDER BY timestamp DESC LIMIT 5;"
                    stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db} "{q_last}"')
                    print(stdout.read().decode())
        
        # 2. Check current working directory and last modified files
        print("\n--- RECENTLY MODIFIED FILES ---")
        stdin, stdout, stderr = ssh.exec_command("ls -lt /home/baxtiyorjongaziyev/telegram_bot | head -n 10")
        print(stdout.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    diagnose_db()
