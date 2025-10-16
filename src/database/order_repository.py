from __future__ import annotations
from typing import Optional, List, Dict, Any
import logging
from .connection import db_manager
from src.config import settings

logger = logging.getLogger(__name__)


async def ensure_connection():
    try:
        await db_manager.initialize()
    except Exception as e:
        logger.warning(f"DB init failed (order_repository): {e}")


async def fetch_orders(from_id: str, status: str = 'pending') -> Optional[List[Dict[str, Any]]]:
    if not db_manager.pool:
        return None
    rows = await db_manager.fetch_all(
        """
        SELECT o.id as order_id, o.insurance_id, o.qty as quantity, o.status, o.created_at,
               ip.insurance_name, ip.sum_insured, ip.term, o.amount
        FROM orders o
        JOIN order_list ol ON o.order_list_id = ol.id
        JOIN insurance_products ip ON o.insurance_id = ip.insurance_id
        WHERE ol.from_id=$1 AND o.status=$2 AND ol.status=$2
        ORDER BY o.created_at DESC
        """,
        [from_id, status]
    )
    return [dict(r) for r in rows]


async def fetch_order_list(from_id: str, status: str = 'pending') -> Optional[Dict[str, Any]]:
    """Fetch the latest order_list aggregate for a user."""
    if not db_manager.pool:
        return None
    row = await db_manager.fetch_one(
        """
        SELECT id, from_id, total_count, total_amount, status, qr_payment, human_check, created_at
        FROM order_list
        WHERE from_id=$1 AND status=$2
        ORDER BY id DESC
        LIMIT 1
        """,
        [from_id, status]
    )
    return dict(row) if row else None


async def update_order_list_qr(order_list_id: int, qr_payment: str) -> bool:
    """Update qr_payment link for an order_list."""
    if not db_manager.pool:
        return False
    await db_manager.execute(
        "UPDATE order_list SET qr_payment=$2 WHERE id=$1",
        [order_list_id, qr_payment]
    )
    return True


async def get_existing_order(from_id: str, insurance_id: int) -> Optional[Dict[str, Any]]:
    if not db_manager.pool:
        return None
    row = await db_manager.fetch_one(
        """
            SELECT o.id as order_id, o.insurance_id, o.qty as quantity, o.status, o.amount
        FROM orders o
        JOIN order_list ol ON o.order_list_id = ol.id
        WHERE ol.from_id=$1 AND o.insurance_id=$2 AND o.status='pending' AND ol.status='pending'
        ORDER BY o.created_at DESC LIMIT 1
        """,
        [from_id, insurance_id]
    )
    return dict(row) if row else None


async def create_order(from_id: str, insurance_id: int, quantity: int) -> Optional[Dict[str, Any]]:
    if not db_manager.pool:
        return None
    row = await db_manager.fetch_one(
            "INSERT INTO orders(order_list_id, insurance_id, qty, amount, from_id) VALUES(NULL,$1,$2,0,$3) RETURNING id as order_id, insurance_id, qty as quantity, status, amount",
        [insurance_id, quantity, from_id]
    )
    if not row:
        return None
    try:
        await recalc_order_list_by_order(row['order_id'])
    except Exception as e:
        logger.debug(f"recalc after create ignored: {e}")
    return dict(row)


async def update_order_quantity(order_id: int, want_qty: int) -> bool:
    if not db_manager.pool:
        return False
    await db_manager.execute(
        """
        UPDATE orders o
        SET qty = $1::int,
            amount = sub.sum_insured * ($2::numeric)
        FROM insurance_products sub
        WHERE o.id = $3 AND sub.insurance_id = o.insurance_id
        """,
        [want_qty, want_qty, order_id]
    )
    try:
        await recalc_order_list_by_order(order_id)
    except Exception as e:
        logger.debug(f"recalc after update ignored: {e}")
    return True
    
async def get_order(order_id: int) -> Optional[Dict[str, Any]]:
    if not db_manager.pool:
        return None
    row = await db_manager.fetch_one(
        "SELECT id as order_id, insurance_id, qty as quantity, amount, status FROM orders WHERE id=$1",
        [order_id]
    )
    return dict(row) if row else None


async def delete_order(order_id: int) -> bool:
    if not db_manager.pool:
        return False
    await db_manager.execute(
        "DELETE FROM orders WHERE id=$1",
        [order_id]
    )
    return True


async def recalc_order_list_by_order(order_id: int):
    """Force recompute order_list totals using SQL aggregation.
    Useful if triggers did not fire (defensive)."""
    if not db_manager.pool:
        return
    row = await db_manager.fetch_one(
        "SELECT order_list_id FROM orders WHERE id=$1",
        [order_id]
    )
    if not row:
        return
    order_list_id = row['order_list_id']
    
    # Build QR link using config values
    qr_template = (
        f"'https://qr.sepay.vn/img?"
        f"acc={settings.payment_bank_account}"
        f"&bank={settings.payment_bank_name}"
        f"&amount=' || agg.total_amt::INTEGER::text || "
        f"'&des={settings.payment_code_prefix}+DH' || $1::text"
    )
    
    await db_manager.execute(
        f"""
        WITH agg AS (
          SELECT order_list_id, COALESCE(SUM(qty),0) AS total_qty, COALESCE(SUM(amount),0) AS total_amt
          FROM orders
          WHERE order_list_id=$1
          GROUP BY order_list_id
        )
        UPDATE order_list ol
        SET total_count = agg.total_qty,
            total_amount = agg.total_amt,
            qr_payment = CASE WHEN agg.total_amt > 0 THEN {qr_template} ELSE NULL END,
            updated_at = now()
        FROM agg
        WHERE ol.id = agg.order_list_id;
        """,
        [order_list_id]
    )


async def fetch_product(insurance_id: int) -> Optional[Dict[str, Any]]:
    if not db_manager.pool:
        return None
    row = await db_manager.fetch_one(
        "SELECT insurance_id, insurance_name, sum_insured AS price FROM insurance_products WHERE insurance_id=$1",
        [insurance_id]
    )
    return dict(row) if row else None


async def get_orders_for_followup() -> List[Dict[str, Any]]:
    """
    Get orders that need follow-up consultation:
    - Status is 'success' 
    - Created more than threshold days/minutes ago (from config)
    - Follow-up not yet sent (no entry in user_feedback table with follow_up_sent=true)
    
    Returns:
        List of order dictionaries with user_id, insurance_name, order details
    """
    if not db_manager.pool:
        return []
    
    try:
        if settings.scheduler_dev_mode:
            threshold = settings.followup_minutes_threshold
            interval_str = f"{threshold} minutes"
            logger.info(f" DEV MODE: Looking for orders older than {threshold} minutes")
        else:
            threshold = settings.followup_days_threshold
            interval_str = f"{threshold} days"
        
        rows = await db_manager.fetch_all(
            f"""
            SELECT DISTINCT
                ol.id,
                ol.from_id as user_id,
                o.insurance_id,
                ip.insurance_name,
                ol.created_at,
                ol.total_amount
            FROM order_list ol
            JOIN orders o ON o.order_list_id = ol.id
            JOIN insurance_products ip ON ip.insurance_id = o.insurance_id
            LEFT JOIN user_feedback uf ON uf.order_list_id = ol.id AND uf.follow_up_sent = true
            WHERE ol.status = 'success'
              AND ol.created_at < NOW() - INTERVAL '{interval_str}'
              AND uf.id IS NULL
            ORDER BY ol.created_at ASC
            LIMIT 50
            """,
            []
        )
        
        return [dict(row) for row in rows]
        
    except Exception as e:
        logger.error(f"Error fetching orders for follow-up: {e}")
        return []
