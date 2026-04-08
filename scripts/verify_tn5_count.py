import os
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hard-pin to Bot.db
db_path = os.path.join(os.getcwd(), 'data', 'bot.db')

def check_tn5():
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check for TN5 search patterns
    cursor.execute("""
        SELECT COUNT(*) FROM users 
        WHERE last_name LIKE '%TN5%' 
           OR last_name LIKE '%TEZ NATIJA 5%'
    """)
    count = cursor.fetchone()[0]
    
    logger.info(f"📊 TN5 Classmates found in DB: {count}")
    
    # Show top 5 names for verification
    if count > 0:
        cursor.execute("""
            SELECT first_name, last_name, username FROM users 
            WHERE last_name LIKE '%TN5%' 
               OR last_name LIKE '%TEZ NATIJA 5%'
            LIMIT 5
        """)
        rows = cursor.fetchall()
        for r in rows:
            logger.info(f"👤 {r[0]} {r[1]} (@{r[2]})")
            
    conn.close()

if __name__ == "__main__":
    check_tn5()
