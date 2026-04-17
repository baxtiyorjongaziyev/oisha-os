
import paramiko
import os

def analyze_last_chat():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        db_path = '/home/baxtiyorjongaziyev/telegram_bot/bot_database.db'
        
        # Get last message log to identify the user
        query_last_msg = "SELECT user_id, timestamp FROM message_logs ORDER BY timestamp DESC LIMIT 1;"
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db_path} "{query_last_msg}"')
        last_log = stdout.read().decode().strip()
        
        if not last_log:
            print("LOG_ERROR: No messages found in database.")
            ssh.close()
            return
            
        user_id = last_log.split('|')[0]
        
        # Get user info
        query_user = f"SELECT first_name, username, phone FROM users WHERE user_id = {user_id};"
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db_path} "{query_user}"')
        user_info = stdout.read().decode().strip().split('|')
        
        # Get last 15 messages for this specific user to see the conversation flow
        query_conv = f"SELECT is_ai, message, timestamp FROM message_logs WHERE user_id = {user_id} ORDER BY timestamp DESC LIMIT 15;"
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db_path} "{query_conv}"')
        raw_msgs = stdout.read().decode().strip().split('\n')
        
        # Reverse to show in chronological order
        raw_msgs.reverse()
        
        print(f"USER_ID: {user_id}")
        print(f"NAME: {user_info[0] if len(user_info) > 0 else 'Unknown'}")
        print(f"USERNAME: {user_info[1] if len(user_info) > 1 else 'None'}")
        print(f"PHONE: {user_info[2] if len(user_info) > 2 else 'None'}")
        print("CONVERSATION_START")
        for line in raw_msgs:
            if '|' in line:
                parts = line.split('|')
                role = "🤖 AI" if parts[0] == '1' else "👤 USER"
                text = parts[1]
                time = parts[2]
                print(f"[{time}] {role}: {text}")
        print("CONVERSATION_END")
        
        ssh.close()
    except Exception as e:
        print(f"FATAL_ERROR: {str(e)}")

if __name__ == '__main__':
    analyze_last_chat()
