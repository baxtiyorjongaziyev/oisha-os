import asyncio
import os
from src.database import Database

async def seed_tasks():
    db = Database()
    await db.init_db()
    conn = await db.get_connection()
    await conn.execute("INSERT INTO tasks (title, description, priority, status, profit_estimate) VALUES (?, ?, ?, ?, ?)", 
                       ("Buyurtmachi A bilan uchrashuv", "Yangi loyiha bo'yicha muzokara", "High", "Pending", 1500))
    await conn.execute("INSERT INTO tasks (title, description, priority, status, profit_estimate) VALUES (?, ?, ?, ?, ?)", 
                       ("Dastur xatolarini tuzatish", "Login sahifasidagi xatolikni to'g'irlash", "High", "Pending", 0))
    await conn.execute("INSERT INTO tasks (title, description, priority, status, profit_estimate) VALUES (?, ?, ?, ?, ?)", 
                       ("Sotuvchilar uchun qo'llanma yozish", "Yangi xodimlar uchun material", "Medium", "Pending", 500))
    await conn.commit()
    print("Tasks seeded.")

if __name__ == "__main__":
    asyncio.run(seed_tasks())
