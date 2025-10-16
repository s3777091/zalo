from __future__ import annotations
from typing import List, Dict, Any, Optional
import logging
from .connection import db_manager
from decimal import Decimal


def _normalize(record: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in record.items():
        if isinstance(v, Decimal):
            if v == v.to_integral_value():
                out[k] = int(v)
            else:
                out[k] = float(v)
        else:
            out[k] = v
    return out

logger = logging.getLogger(__name__)


async def ensure_connection():
    try:
        await db_manager.initialize()
    except Exception as e:
        logger.warning(f"DB init failed (insurance_repository): {e}")


async def fetch_by_type(insurance_type: str, limit: int = 25) -> Optional[List[Dict[str, Any]]]:
    """Fetch products by type. Schema does not include base_price -> use sum_insured as price."""
    if not db_manager.pool:
        return None
    rows = await db_manager.fetch_all(
        "SELECT insurance_id, insurance_name, insurance_type, sum_insured, term, sum_insured AS price FROM insurance_products WHERE lower(insurance_type)=lower($1) ORDER BY insurance_id LIMIT $2",
        [insurance_type, limit]
    )
    return [_normalize(dict(r)) for r in rows]


async def fetch_by_name(fragment: str, limit: int = 25) -> Optional[List[Dict[str, Any]]]:
    if not db_manager.pool:
        return None
    rows = await db_manager.fetch_all(
        "SELECT insurance_id, insurance_name, insurance_type, sum_insured, term, sum_insured AS price FROM insurance_products WHERE insurance_name ILIKE '%' || $1 || '%' ORDER BY insurance_id LIMIT $2",
        [fragment, limit]
    )
    return [_normalize(dict(r)) for r in rows]


async def fetch_one(insurance_id: int) -> Optional[Dict[str, Any]]:
    if not db_manager.pool:
        return None
    row = await db_manager.fetch_one(
        "SELECT insurance_id, insurance_name, insurance_type, sum_insured, term, sum_insured AS price FROM insurance_products WHERE insurance_id=$1",
        [insurance_id]
    )
    return _normalize(dict(row)) if row else None
