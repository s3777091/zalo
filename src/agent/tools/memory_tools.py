import json
import logging
import uuid  # <<< THÊM LẠI DÒNG NÀY
from typing import List

from langchain_core.documents import Document
from langchain_core.runnables import ensure_config
from langchain_core.tools import tool
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from src.database.vector_store import vector_store

logger = logging.getLogger(__name__)


@tool(description="Sử dụng tool này để lưu một thông tin quan trọng, cô đọng về người dùng vào trí nhớ dài hạn. Ví dụ: 'Người dùng tên là An, đang tìm bảo hiểm du lịch.'")
async def save_recall_memory(memory: str) -> str:
    """Lưu một mẩu thông tin (ký ức) vào vector store."""
    config = ensure_config()
    user_id = config.get("configurable", {}).get("user_id")

    if not user_id:
        logger.error("Failed to save memory: user_id not found in RunnableConfig.")
        return "Lỗi: Không thể lưu ký ức vì thiếu thông tin người dùng."

    try:
        document = Document(
            page_content=memory,
            metadata={"user_id": user_id, "id": str(uuid.uuid4())}
        )
        await vector_store.aadd_documents([document])
        logger.info(f"Successfully saved memory for user '{user_id}': '{memory}'")
        return f"Đã lưu thành công ký ức: '{memory}'"
    except Exception as e:
        logger.error(f"Failed to save memory for user '{user_id}': {e}", exc_info=True)
        return "Lỗi: Đã có sự cố xảy ra khi cố gắng lưu ký ức."


@tool(description="Sử dụng tool này để tìm trong trí nhớ các thông tin liên quan đến chủ đề hiện tại.")
async def search_recall_memories(query: str) -> str:
    """Tìm kiếm các ký ức liên quan trong vector store."""
    config = ensure_config()
    user_id = config.get("configurable", {}).get("user_id")

    if not user_id:
        logger.error("Failed to search memories: user_id not found in RunnableConfig.")
        return json.dumps({
            "status": "error",
            "message": "Không thể tìm ký ức vì thiếu thông tin người dùng."
        }, ensure_ascii=False)
        
    try:
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.user_id",
                    match=MatchValue(value=user_id)
                )
            ]
        )
        
        results = await vector_store.asimilarity_search(
            query=query,
            k=3,
            filter=qdrant_filter
        )
        
        memories = [doc.page_content for doc in results]
        logger.info(f"Found {len(memories)} memories for user '{user_id}' matching query '{query}'")

        # ✅ Đảm bảo luôn trả JSON string
        return json.dumps({
            "status": "success",
            "query": query,
            "count": len(memories),
            "memories": memories
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Failed to search memories for user '{user_id}': {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": f"Lỗi khi tìm kiếm ký ức: {str(e)}"
        }, ensure_ascii=False)