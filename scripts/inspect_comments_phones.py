import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    conn = sqlite3.connect('data/instagram_comments.db')
    c = conn.cursor()
    c.execute('''
        SELECT u.user_key, p.username, p.comment_text, u.dm_sent_at, p.private_reply_sent, p.private_reply_text
        FROM user_dm_contacts u
        LEFT JOIN processed_comments p ON u.first_comment_id = p.comment_id
    ''')
    rows = c.fetchall()
    print(f"Total DM contacts from Brend video: {len(rows)}")
    for i, r in enumerate(rows):
        ukey, uname, ctext, dm_time, dm_sent, reply_txt = r
        print(f"[{i+1}] User: @{uname} ({ukey})")
        print(f"    Comment: '{ctext}'")
        print(f"    DM sent: {dm_sent} at {dm_time}")
        print(f"    Reply preview: {reply_txt[:60]}...")

    print("\n--- ALL COMMENTS IN DB THAT CONTAIN NUMBERS OR PHONE PATTERNS ---")
    c.execute("SELECT username, comment_text, created_at FROM processed_comments WHERE comment_text LIKE '%+998%' OR comment_text LIKE '%998%' OR comment_text LIKE '% 9%' OR comment_text LIKE '%nom%' OR comment_text LIKE '%tel%'")
    phone_comments = c.fetchall()
    print(f"Found {len(phone_comments)} comments mentioning numbers/contacts:")
    for uname, ctext, ctime in phone_comments:
        print(f"  @{uname} ({ctime}): {ctext}")

if __name__ == '__main__':
    main()
