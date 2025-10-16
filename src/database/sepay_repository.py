import logging
from typing import Optional, Dict, Any
from .connection import db_manager

logger = logging.getLogger(__name__)

GET_ROW_SQL = "SELECT id, owner_name, owner_email, amount_count FROM public.sepay WHERE id = $1 LIMIT 1"
SEPAY_DEFAULT_ROW_ID = 1

async def get_sepay_info() -> Optional[Dict[str, Any]]:
    try:
        row = await db_manager.fetch_one(GET_ROW_SQL, [SEPAY_DEFAULT_ROW_ID])
        if row:
            return {
                'id': row[0],
                'owner_name': row[1],
                'owner_email': row[2],
                'amount_count': row[3]
            }
    except Exception as e:
        logger.error(f"Error fetching sepay info: {e}")
    return None