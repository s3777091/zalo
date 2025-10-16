from deepagents import create_deep_agent
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from ..config import settings
from .middleware.memory_middleware import MemoryMiddleware
from .prompt.consultation import VIETNAMESE_INSURANCE_AGENT
from .tools.insurance_tools import search_insurance_products
from .tools.memory_tools import save_recall_memory, search_recall_memories
from .tools.order_tools import manage_order, view_orders


class ChatAgentFactory:
    def __init__(self):
        self.model = ChatOpenAI(
            model=settings.openai_model, temperature=0, max_retries=3
        )

    def get_agent(self):
        all_tools = [
            search_insurance_products,
            manage_order,
            view_orders,
            save_recall_memory,
            search_recall_memories,
        ]
        

        middleware = MemoryMiddleware(
            summary_llm=self.model,
            initial_summarization_threshold=4,
            summarization_interval=2,
        )

        agent = create_deep_agent(
            model=self.model,
            instructions=VIETNAMESE_INSURANCE_AGENT,
            middleware=[middleware],
            tools=all_tools,
        )
        
        return agent