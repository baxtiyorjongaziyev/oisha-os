"""Add operators to call_operators table.

Usage:
    python scripts/add_operators.py --name "Operator Name" --telegram_id 123456789 --phone "+998901234567"
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from src.services.core.uzbek_entrepreneurs_schema import ensure_hisobchi_db

logger = logging.getLogger(__name__)


async def add_operator(
    db,
    name: str,
    telegram_id: int,
    phone: str,
    is_active: bool = True,
) -> int:
    """Add operator to call_operators table."""
    try:
        _db = ensure_hisobchi_db(db)

        # Check if operator already exists
        existing = await _db.execute(
            "SELECT id FROM call_operators WHERE telegram_id = ?",
            [telegram_id],
        )

        if existing:
            logger.warning(f"Operator with telegram_id {telegram_id} already exists")
            return existing[0]["id"]

        # Insert new operator
        result = await _db.execute(
            """
            INSERT INTO call_operators
            (name, telegram_id, phone, is_active, total_calls_today, created_at)
            VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
            """,
            [name, telegram_id, phone, 1 if is_active else 0],
        )
        await _db.commit()

        operator_id = result[0]["id"] if result else None
        logger.info(f"✅ Operator added: #{operator_id} - {name}")
        return operator_id

    except Exception as e:
        logger.error(f"Failed to add operator: {e}")
        raise


async def list_operators(db) -> list[dict]:
    """List all operators."""
    try:
        _db = ensure_hisobchi_db(db)

        rows = await _db.execute(
            """
            SELECT id, name, telegram_id, phone, is_active,
                   current_call_id, total_calls_today, last_call_time
            FROM call_operators
            ORDER BY id
            """
        )

        return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Failed to list operators: {e}")
        return []


async def remove_operator(db, operator_id: int) -> bool:
    """Remove operator by ID."""
    try:
        _db = ensure_hisobchi_db(db)

        await _db.execute(
            "DELETE FROM call_operators WHERE id = ?",
            [operator_id],
        )
        await _db.commit()

        logger.info(f"✅ Operator #{operator_id} removed")
        return True

    except Exception as e:
        logger.error(f"Failed to remove operator: {e}")
        return False


async def toggle_operator_status(db, operator_id: int) -> bool:
    """Toggle operator active status."""
    try:
        _db = ensure_hisobchi_db(db)

        await _db.execute(
            """
            UPDATE call_operators
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
            WHERE id = ?
            """,
            [operator_id],
        )
        await _db.commit()

        logger.info(f"✅ Operator #{operator_id} status toggled")
        return True

    except Exception as e:
        logger.error(f"Failed to toggle operator status: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Manage call operators")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add command
    add_parser = subparsers.add_parser("add", help="Add new operator")
    add_parser.add_argument("--name", type=str, required=True, help="Operator name")
    add_parser.add_argument("--telegram_id", type=int, required=True, help="Telegram ID")
    add_parser.add_argument("--phone", type=str, required=True, help="Phone number")
    add_parser.add_argument("--active", action="store_true", default=True, help="Mark as active")

    # List command
    list_parser = subparsers.add_parser("list", help="List all operators")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove operator")
    remove_parser.add_argument("--id", type=int, required=True, help="Operator ID")

    # Toggle command
    toggle_parser = subparsers.add_parser("toggle", help="Toggle operator status")
    toggle_parser.add_argument("--id", type=int, required=True, help="Operator ID")

    args = parser.parse_args()

    # Initialize database
    db = Database("data/bot.db")
    await db.init_instance()

    try:
        if args.command == "add":
            operator_id = await add_operator(
                db,
                name=args.name,
                telegram_id=args.telegram_id,
                phone=args.phone,
                is_active=args.active,
            )
            print(f"\n✅ Operator added: ID #{operator_id}")

        elif args.command == "list":
            operators = await list_operators(db)
            print(f"\n📋 Operators ({len(operators)}):")
            print("-" * 80)
            for op in operators:
                status = "✅ Active" if op["is_active"] else "❌ Inactive"
                print(
                    f"ID: {op['id']} | {op['name']} | TG: {op['telegram_id']} | "
                    f"Phone: {op['phone']} | {status} | Calls: {op['total_calls_today']}"
                )
            print("-" * 80)

        elif args.command == "remove":
            success = await remove_operator(db, args.id)
            if success:
                print(f"\n✅ Operator #{args.id} removed")
            else:
                print(f"\n❌ Failed to remove operator #{args.id}")

        elif args.command == "toggle":
            success = await toggle_operator_status(db, args.id)
            if success:
                print(f"\n✅ Operator #{args.id} status toggled")
            else:
                print(f"\n❌ Failed to toggle operator #{args.id}")

    finally:
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
