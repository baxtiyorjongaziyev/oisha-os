"""Vilgood Engine: Gamification, SLA Timing, and Strict Pipeline enforcement."""
import structlog
import datetime
from typing import Dict, Any, Optional

logger = structlog.get_logger()

class VilgoodEngine:
    def __init__(self, db, amocrm=None):
        self.db = db
        self.amocrm = amocrm
        
    async def evaluate_task_completion(self, task_id: int, user_id: int) -> Optional[int]:
        """Check if task was completed on time, award/deduct points."""
        conn = await self.db.get_connection()
        async with conn.execute(
            "SELECT deadline, completed_at, sla_minutes, coins_reward FROM tasks WHERE id = ?",
            (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            return None
            
        deadline, completed_at, sla_minutes, coins_reward = row
        if not completed_at:
            completed_at = datetime.datetime.now().isoformat()
            
        reward = coins_reward or 10
        
        # Simple SLA logic
        if deadline:
            deadline_dt = datetime.datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
            completed_dt = datetime.datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
            
            if completed_dt <= deadline_dt:
                # Earn points
                points = reward
                reason = f"Task {task_id} completed on time"
            else:
                # Lose points
                points = -(reward // 2)
                reason = f"Task {task_id} overdue"
                
            new_balance = await self.db.gamification.add_coins(user_id, points, reason, task_id)
            logger.info("[VilgoodEngine] User %s got %s coins for task %s. New balance: %s", user_id, points, task_id, new_balance)
            return points
            
        return None

    async def enforce_pipeline_rules(self, lead_id: int, old_status: int, new_status: int, lead_data: Dict[str, Any]) -> bool:
        """
        Check if moving a lead from old_status to new_status is allowed.
        Returns False if the transition is forbidden by strict pipeline rules.
        """
        # Example hardcoded rules for Vilgood
        # In a real app, this would be loaded from a config or DB
        
        # Example rule: Cannot move to status 142 (Negotiation) without an enriched phone number
        custom_fields = lead_data.get("custom_fields_values") or []
        phone = None
        for field in custom_fields:
            if field.get("field_code") == "PHONE":
                phone = field["values"][0]["value"]
                break
                
        # If moving to a critical stage (e.g. 142) but missing phone
        if new_status == 142 and not phone:
            logger.warning("[VilgoodEngine] Pipeline violation for lead %s: Missing phone for status 142", lead_id)
            return False
            
        return True

class VilgoodDispatcher:
    def __init__(self, db):
        self.db = db

    async def get_next_best_task(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Auto-Dispatcher: Return the single most important task for this user based on LTV/Priority/Deadline.
        This forces the user to focus on one thing (Vilgood model).
        """
        conn = await self.db.get_connection()
        async with conn.execute(
            """
            SELECT id, title, description, deadline, priority, profit_estimate 
            FROM tasks 
            WHERE assigned_to = ? AND status IN ('Pending', 'In Progress')
            ORDER BY 
                CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END ASC,
                profit_estimate DESC,
                deadline ASC
            LIMIT 1
            """,
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            return None
            
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "deadline": row[3],
            "priority": row[4],
            "profit_estimate": row[5]
        }
