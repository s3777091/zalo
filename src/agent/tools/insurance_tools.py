import json
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from ...database.connection import db_manager
from ...database.insurance_repository import _normalize
from ...common.constants import Lexicon

logger = logging.getLogger(__name__)

SEARCH_INSURANCE_TOOL_DESCRIPTION = """
- **Chức năng**: Tìm kiếm sản phẩm bảo hiểm theo TÊN hoặc theo LOẠI.
- **Quan trọng**: CHỈ SỬ DỤNG MỘT trong hai tham số cho mỗi lần gọi.
- **Tham số**:
  - `insurance_name` (str, tùy chọn): Dùng khi người dùng hỏi tên sản phẩm cụ thể (ví dụ: "Bảo hiểm VBI Care").
  - `insurance_type` (str, tùy chọn): Dùng khi người dùng hỏi một loại chung (ví dụ: "bảo hiểm sức khỏe", "du lịch").
- **Trả về**: Danh sách JSON các sản phẩm bảo hiểm phù hợp.
"""

@tool(description=SEARCH_INSURANCE_TOOL_DESCRIPTION)
async def search_insurance_products(
    insurance_name: Optional[str] = None,
    insurance_type: Optional[str] = None
) -> str:
    if not (insurance_name or insurance_type) or (insurance_name and insurance_type):
        return json.dumps({
            "error": "invalid_parameters",
            "message": "Vui lòng chỉ cung cấp `insurance_name` hoặc `insurance_type`, không phải cả hai hoặc không có gì."
        }, ensure_ascii=False)

    try:
        if insurance_name:
            query = "SELECT insurance_id, insurance_name, insurance_type, sum_insured, term, sum_insured AS price FROM insurance_products WHERE insurance_name ILIKE '%' || $1 || '%' ORDER BY insurance_id LIMIT $2"
            params = [insurance_name, 25]
        else:
            mapped_type = Lexicon.normalize_insurance_type(insurance_type)
            if not mapped_type:
                return json.dumps({"error": "unknown_type", "input": insurance_type, "products": []}, ensure_ascii=False)
            query = "SELECT insurance_id, insurance_name, insurance_type, sum_insured, term, sum_insured AS price FROM insurance_products WHERE lower(insurance_type)=lower($1) ORDER BY insurance_id LIMIT $2"
            params = [mapped_type, 25]
        
        rows = await db_manager.fetch_all(query, params)
        
        if rows is None:
            return json.dumps({"error": "db_call_failed", "products": []}, ensure_ascii=False)
            
        normalized_rows = [_normalize(dict(r)) for r in rows]
        return json.dumps(normalized_rows, ensure_ascii=False, default=str)

    except Exception as e:
        logger.error(f"search_insurance_products error: {e}", exc_info=True)
        return json.dumps({"error": "exception", "message": str(e)}, ensure_ascii=False)