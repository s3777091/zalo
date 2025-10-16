import json
import logging
from typing import Dict, Any, List, Optional, Literal
from langchain_core.tools import tool
from src.agent.prompt import (
    GET_ORDER_TOOLS_DESCRIPTION,
)
from src.database.connection import db_manager

logger = logging.getLogger(__name__)

def _to_dict(record: Any) -> Dict[str, Any]:
    return dict(record) if record else {}

@tool(description=GET_ORDER_TOOLS_DESCRIPTION)
async def view_orders(from_id: str, status: str = "pending") -> str:
    try:
        query = """
        SELECT
            o.id AS order_id, o.insurance_id, o.qty AS quantity, o.status,
            o.created_at, o.amount, ip.insurance_name, ip.sum_insured, ip.term
        FROM orders o
        JOIN order_list ol ON o.order_list_id = ol.id
        JOIN insurance_products ip ON o.insurance_id = ip.insurance_id
        WHERE ol.from_id = $1 AND o.status = $2 AND ol.status = $2
        ORDER BY o.created_at DESC;
        """
        rows = await db_manager.fetch_all(query, [from_id, status]) or []
        
        orders_list = []
        total_amount = 0
        for record in rows:
            order = _to_dict(record)
            unit_price = 0
            if order.get('quantity') and order.get('amount'):
                try:
                    unit_price = float(order['amount']) / order['quantity']
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            order['unit_price'] = unit_price
            orders_list.append(order)
            total_amount += float(order.get('amount', 0) or 0)

        result = {
            "orders": orders_list, "total_orders": len(orders_list),
            "total_amount": total_amount, "status": status, "user_id": from_id,
        }
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"view_orders error for user {from_id}: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool(description="Quản lý đơn hàng: tạo, cập nhật, hoặc xóa sản phẩm trong giỏ hàng.")
async def manage_order(
    action: Literal["create", "update", "delete"],
    from_id: str,
    insurance_id: int,
    quantity: Optional[int] = None,
    quantity_change: Optional[int] = None,
) -> str:
    try:
        if action == "create":
            if quantity is None or quantity <= 0:
                return json.dumps({"success": False, "message": "Quantity must be a positive number for create action."}, ensure_ascii=False)
            
            find_existing_query = "SELECT o.id, o.qty FROM orders o JOIN order_list ol ON o.order_list_id = ol.id WHERE ol.from_id = $1 AND o.insurance_id = $2 AND o.status = 'pending' LIMIT 1;"
            existing_order = _to_dict(await db_manager.fetch_one(find_existing_query, [from_id, insurance_id]))
            
            if existing_order:
                new_qty = existing_order['qty'] + quantity
                update_query = "UPDATE orders o SET qty = $1, amount = ip.sum_insured * $1::integer FROM insurance_products ip WHERE o.id = $2 AND o.insurance_id = ip.insurance_id RETURNING o.id as order_id, o.qty as quantity, o.amount;"
                updated = _to_dict(await db_manager.fetch_one(update_query, [new_qty, existing_order['id']]))
                return json.dumps({"success": True, "action": "create", "merged": True, **updated}, ensure_ascii=False, default=str)
            else:
                create_query = "INSERT INTO orders (order_list_id, insurance_id, qty, amount, from_id) SELECT NULL, $1, $2, ip.sum_insured * $2::integer, $3 FROM insurance_products ip WHERE ip.insurance_id = $1 RETURNING id as order_id, insurance_id, qty as quantity, status, amount;"
                created = _to_dict(await db_manager.fetch_one(create_query, [insurance_id, quantity, from_id]))
                if not created:
                    return json.dumps({"success": False, "message": "Create failed, possibly invalid insurance_id"}, ensure_ascii=False)
                return json.dumps({"success": True, "action": "create", "merged": False, **created}, ensure_ascii=False, default=str)

        elif action == "update":
            if quantity_change is None:
                return json.dumps({"success": False, "message": "quantity_change is required for update action."}, ensure_ascii=False)
            
            update_query = "WITH t AS (SELECT o.id, o.qty FROM orders o JOIN order_list ol ON o.order_list_id = ol.id WHERE ol.from_id = $1 AND o.insurance_id = $2 AND o.status = 'pending' LIMIT 1) UPDATE orders o SET qty = GREATEST(0, t.qty + $3), amount = ip.sum_insured * GREATEST(0, t.qty + $3) FROM t, insurance_products ip WHERE o.id = t.id AND o.insurance_id = ip.insurance_id RETURNING o.id as order_id, o.qty as quantity, o.amount;"
            updated = _to_dict(await db_manager.fetch_one(update_query, [from_id, insurance_id, quantity_change]))
            if not updated:
                return json.dumps({"success": False, "message": "Order not found or not pending"}, ensure_ascii=False)
            return json.dumps({"success": True, "action": "update", **updated}, ensure_ascii=False, default=str)
        
        elif action == "delete":
            delete_query = "DELETE FROM orders WHERE id = (SELECT o.id FROM orders o JOIN order_list ol ON o.order_list_id = ol.id WHERE ol.from_id = $1 AND o.insurance_id = $2 AND o.status = 'pending' LIMIT 1) RETURNING id as order_id;"
            deleted = _to_dict(await db_manager.fetch_one(delete_query, [from_id, insurance_id]))
            if not deleted:
                return json.dumps({"success": False, "message": "Order not found or not pending"}, ensure_ascii=False)
            return json.dumps({"success": True, "action": "delete", "order_id": deleted['order_id']}, ensure_ascii=False)

        else:
            return json.dumps({"success": False, "message": f"Invalid action: {action}. Must be 'create', 'update', or 'delete'."}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"manage_order error for user {from_id} with action {action}: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)