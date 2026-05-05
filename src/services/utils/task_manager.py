import logging
import datetime
from database import Database  # type: ignore

logger = logging.getLogger(__name__)


class TaskManager:
    def __init__(self, db: Database):
        self.db = db

    def add_task(
        self, title, description, assigned_to, due_date, created_by, priority="Medium"
    ):
        """Yangi topshiriq qo'shish."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO tasks (title, description, assigned_to, due_date, priority, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        title,
                        description,
                        assigned_to,
                        due_date,
                        priority,
                        created_by,
                        datetime.datetime.now().isoformat(),
                    ),
                )
            logger.info(f"[HR] Task added: {title} for user {assigned_to}")
            return True
        except Exception as e:
            logger.error(f"[HR ERROR] add_task: {e}")
            return False

    def get_user_tasks(self, user_id):
        """Xodimning barcha topshiriqlarini olish."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM tasks WHERE assigned_to = ? AND status != 'Completed'",
                    (user_id,),
                )
                rows = cursor.fetchall()
                return rows
        except Exception as e:
            logger.error(f"[HR ERROR] get_user_tasks: {e}")
            return []

    def update_task_status(self, task_id, status):
        """Topshiriq holatini yangilash."""
        try:
            now = datetime.datetime.now().isoformat() if status == "Completed" else None
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                if now:
                    cursor.execute(
                        "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
                        (status, now, task_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE tasks SET status = ? WHERE id = ?", (status, task_id)
                    )
            return True
        except Exception as e:
            logger.error(f"[HR ERROR] update_task_status: {e}")
            return False

    def check_overdue_tasks(self):
        """Muddati o'tgan topshiriqlarni aniqlash."""
        try:
            now = datetime.datetime.now().isoformat()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM tasks WHERE due_date < ? AND status != 'Completed' AND status != 'Overdue'",
                    (now,),
                )
                overdue_tasks = cursor.fetchall()
                for task in overdue_tasks:
                    cursor.execute(
                        "UPDATE tasks SET status = 'Overdue' WHERE id = ?", (task[0],)
                    )
                return overdue_tasks
        except Exception as e:
            logger.error(f"[HR ERROR] check_overdue_tasks: {e}")
            return []
