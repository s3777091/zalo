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
    """
    Lưu một mẩu thông tin (ký ức) vào vector store.
    Tự động xóa các ký ức cũ bị trùng lặp hoặc quá giống.
    """
    config = ensure_config()
    user_id = config.get("configurable", {}).get("user_id")
    SIMILARITY_THRESHOLD = 0.95

    if not user_id:
        logger.error("Failed to save memory: user_id not found in RunnableConfig.")
        return "Lỗi: Không thể lưu ký ức vì thiếu thông tin người dùng."

    try:
        # 1. Tìm kiếm các documents tương tự đã có
        qdrant_filter = Filter(must=[FieldCondition(key="metadata.user_id", match=MatchValue(value=user_id))])

        # Sử dụng search_with_score để lấy điểm tương đồng
        similar_docs_with_scores = await vector_store.asimilarity_search_with_relevance_scores(
            query=memory,
            k=5, # Lấy nhiều hơn để kiểm tra
            filter=qdrant_filter
        )

        # 2. Xác định các documents cần xóa
        ids_to_delete = []
        for doc, score in similar_docs_with_scores:
            if score >= SIMILARITY_THRESHOLD:
                # metadata["id"] là ID của điểm trong Qdrant
                if "id" in doc.metadata:
                    ids_to_delete.append(doc.metadata["id"])
                    logger.info(f"Found highly similar memory for user '{user_id}' with score {score:.4f}. Marking for deletion: ID {doc.metadata['id']}")

        # 3. Xóa các documents cũ nếu có
        if ids_to_delete:
            await vector_store.adelete(ids=ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} redundant memories for user '{user_id}'.")

        # 4. Thêm document mới
        new_doc_id = str(uuid.uuid4())
        document = Document(
            page_content=memory,
            metadata={"user_id": user_id, "id": new_doc_id} # Gán ID để có thể xóa sau này
        )
        await vector_store.aadd_documents([document])

        if ids_to_delete:
            logger.info(f"Successfully replaced and saved memory for user '{user_id}': '{memory}'")
            return f"Đã cập nhật và lưu thành công ký ức: '{memory}'"
        else:
            logger.info(f"Successfully saved new memory for user '{user_id}': '{memory}'")
            return f"Đã lưu thành công ký ức mới: '{memory}'"

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