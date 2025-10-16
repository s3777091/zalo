import logging
import json
import asyncio
import functools
from typing import List, Optional
from datetime import timedelta
import uuid
from langchain_core.messages import (
    AIMessage, HumanMessage, BaseMessage, SystemMessage, ToolMessage,
    get_buffer_string, message_to_dict, messages_from_dict
)
from langchain_core.language_models import BaseChatModel

from src.database.connection import db_manager, redis_manager

logger = logging.getLogger(__name__)

def _serialize(msg: BaseMessage) -> str:
    """Serializes a LangChain message to a JSON string."""
    return json.dumps(message_to_dict(msg))

def _deserialize(s: str) -> BaseMessage:
    """Deserializes a JSON string back to a LangChain message."""
    return messages_from_dict([json.loads(s)])[0]

def _filter_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Filters out messages that should not be stored in history."""
    filtered = []
    for m in messages:
        if isinstance(m, ToolMessage) or hasattr(m, "tool_calls") and getattr(m, "tool_calls"):
            continue
        if not getattr(m, "content", None):
            continue
        filtered.append(m)
    return filtered

class ChatMessageHistory:
    def __init__(
        self,
        user_id: str,
        summary_llm: BaseChatModel,
        initial_summarization_threshold: int = 20,
        summarization_interval: int = 10,
    ):
        self.user_id = user_id
        self.summary_llm = summary_llm
        self.initial_summarization_threshold = initial_summarization_threshold
        self.summarization_interval = summarization_interval
        self.redis_key = f"chat_history:{self.user_id}"
        self.messages: List[BaseMessage] = []

    async def load_messages(self):
        """Loads messages from cache if available, otherwise from the database."""
        cached_messages = await self._load_from_cache()
        if cached_messages:
            self.messages = cached_messages
        else:
            self.messages = await self._load_from_db()

    async def add_messages(self, messages: List[BaseMessage]):
        """Adds new messages to the history and persists them."""
        filtered_messages = _filter_messages(messages)
        if not filtered_messages:
            return

        self.messages.extend(filtered_messages)
        await self._save_to_db(filtered_messages)
        await self._save_to_cache(filtered_messages)

    async def summarize_if_needed(self):
        """
        Checks if the conversation history needs summarization and performs it if so.
        Uses the in-memory message list instead of re-fetching from cache.
        """
        if not self.messages:
            return

        summary_message = self.messages[0] if isinstance(self.messages[0], SystemMessage) else None
        messages_since_summary = self.messages[1:] if summary_message else self.messages
        
        should_summarize = (
            (not summary_message and len(messages_since_summary) >= self.initial_summarization_threshold) or
            (summary_message and len(messages_since_summary) >= self.summarization_interval)
        )

        if not should_summarize:
            return

        logger.info(f"Background summarization triggered for thread '{self.redis_key}'.")
        try:
            # Keep the last 2 messages out of the summary for context
            last_few_messages = self.messages[-2:]
            messages_to_summarize = self.messages[:-2]

            history_text = get_buffer_string(messages_to_summarize)
            summary_prompt = f"Condense the following conversation into a concise summary:\n\n{history_text}\n\nSummary:"
            
            summary_response = await self.summary_llm.ainvoke(summary_prompt)
            summary_text = str(summary_response.content)

            new_messages_state = [SystemMessage(content=f"Summary of previous conversation: {summary_text}")] + last_few_messages
            
            self.messages = new_messages_state
            await self._overwrite_cache(new_messages_state)
            
            logger.info(f"Background Redis cache update for '{self.redis_key}' with new summary successful.")
        except Exception as e:
            logger.error(f"Error during background summarization for user '{self.user_id}': {e}", exc_info=True)

    async def _run_sync(self, func, *args, **kwargs):
        """Runs a synchronous function in an executor."""
        return await asyncio.get_running_loop().run_in_executor(None, functools.partial(func, *args, **kwargs))

    async def _load_from_cache(self) -> List[BaseMessage]:
        """Loads message history from Redis cache."""
        try:
            raw_messages = await self._run_sync(redis_manager.client.lrange, self.redis_key, 0, -1)
            if raw_messages:
                logger.info(f"Cache HIT for key '{self.redis_key}'. Loading {len(raw_messages)} messages.")
                # Deserialize and filter messages in one go
                return _filter_messages([_deserialize(m) for m in reversed(raw_messages)])
        except Exception as e:
            logger.error(f"Error loading from Redis for key '{self.redis_key}': {e}", exc_info=True)
        return []

    async def _load_from_db(self) -> List[BaseMessage]:
        """Loads message history from PostgreSQL database."""
        logger.info(f"Cache MISS for key '{self.redis_key}'. Loading from PostgreSQL.")
        try:
            rows = await db_manager.fetch_all(
                "SELECT is_bot, text FROM public.chat_histories WHERE from_id = $1 ORDER BY created_at ASC", [self.user_id]
            )
            messages = [AIMessage(content=r['text']) if r['is_bot'] else HumanMessage(content=r['text']) for r in rows]

            filtered_messages = _filter_messages(messages)
            if filtered_messages:
                # Prime the cache for future requests
                await self._overwrite_cache(filtered_messages)
            return filtered_messages
        except Exception as e:
            logger.error(f"Error loading from PostgreSQL for user '{self.user_id}': {e}", exc_info=True)
            return []

    async def _save_to_db(self, messages: List[BaseMessage]):
        """Saves a list of messages to the database using a single bulk insert."""
        if not messages:
            return

        query = """
            INSERT INTO public.chat_histories (is_bot, message_id, text, from_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (message_id) DO NOTHING
        """

        # Prepare all records for bulk insert
        records_to_insert = []
        for m in messages:
            message_id = str(m.id) if hasattr(m, "id") and m.id else str(uuid.uuid4())
            is_bot = isinstance(m, AIMessage)
            text = str(m.content)
            records_to_insert.append((is_bot, message_id, text, self.user_id))

        try:
            # Execute all inserts in a single transaction
            await db_manager.execute_many(query, records_to_insert)
        except Exception as e:
            logger.error(f"Error saving to PostgreSQL for user '{self.user_id}': {e}", exc_info=True)

    async def _save_to_cache(self, messages: List[BaseMessage]):
        """Saves messages to the Redis cache."""
        try:
            pipe = redis_manager.client.pipeline()
            for msg in reversed(messages):
                pipe.lpush(self.redis_key, _serialize(msg))
            pipe.expire(self.redis_key, timedelta(hours=24))
            await self._run_sync(pipe.execute)
        except Exception as e:
            logger.error(f"Error saving to Redis for user '{self.user_id}': {e}", exc_info=True)
            
    async def _overwrite_cache(self, messages: List[BaseMessage]):
        """Overwrites the entire Redis cache with the provided messages."""
        pipe = redis_manager.client.pipeline()
        pipe.delete(self.redis_key)
        for msg in reversed(messages):
            pipe.lpush(self.redis_key, _serialize(msg))
        pipe.expire(self.redis_key, timedelta(hours=24))
        await self._run_sync(pipe.execute)