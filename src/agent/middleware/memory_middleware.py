import logging
import asyncio
from typing import Any, Optional, Dict

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import get_buffer_string, AIMessage
from langchain_core.runnables import RunnableConfig

from .chat_history import ChatMessageHistory
from src.agent.tools.memory_tools import search_recall_memories

logger = logging.getLogger(__name__)

class MemoryMiddleware(AgentMiddleware):
    def __init__(self, **kwargs):
        self.summary_llm_config = kwargs

    def get_history_manager(self, user_id: str) -> ChatMessageHistory:
        return ChatMessageHistory(user_id=user_id, **self.summary_llm_config)

    async def before_model(self, state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        config = config or {}
        configurable_params = config.get("configurable", {})
        
        user_id = configurable_params.get("user_id")
        history_manager = configurable_params.get("chat_history_manager")

        if not user_id or not history_manager:
            return state
        combined_messages = history_manager.messages + state.get("messages", [])
        state["messages"] = combined_messages

        try:
            query = get_buffer_string(combined_messages[-5:])
            if not query.strip() and state.get("messages"):
                query = state["messages"][-1].content
                
            recall_results = await search_recall_memories.ainvoke({"query": query, "user_id": user_id})
            
            if recall_results and isinstance(recall_results, list):
                logger.info(f"Found {len(recall_results)} recall memories for user '{user_id}'.")
                state["recall_memories"] = "\n".join(f"- {mem}" for mem in recall_results)
            else:
                 state["recall_memories"] = "Chưa có ký ức nào được lưu."

        except Exception as e:
            logger.warning(f"Could not check or search recall memories for user '{user_id}': {e}", exc_info=True)
            state["recall_memories"] = "Chưa thể truy cập ký ức dài hạn."
        
        return state
    
    async def after_model(self, state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        config = config or {}
        configurable_params = config.get("configurable", {})
        history_manager : ChatMessageHistory = configurable_params.get("chat_history_manager")

        if not history_manager:
            return state
        new_messages = state["messages"][len(history_manager.messages):]

        if new_messages:
            await history_manager.add_messages(new_messages)
            
            
            asyncio.create_task(history_manager.summarize_if_needed())
                
        return state

