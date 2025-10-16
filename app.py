import asyncio
import logging
from langchain_core.messages import HumanMessage
from src.agent.chat_agent import ChatAgentFactory
from src.database.connection import db_manager, redis_manager
from src.agent.middleware.memory_middleware import MemoryMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def ainput(prompt: str = "") -> str:
    """Runs input() in a separate thread to avoid blocking the asyncio event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)

async def main():
    await db_manager.initialize()
    redis_manager.initialize()

    try:
        agent_factory = ChatAgentFactory()
        chat_agent = agent_factory.get_agent()
        print("Agent is ready. You can start chatting now.")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}", exc_info=True)
        await db_manager.close()
        if redis_manager._client:
            redis_manager.close()
        return

    user_id = await ainput("Please enter your User ID to begin (e.g., user_123): ")
    user_id = user_id.strip()
    if not user_id:
        print("User ID cannot be empty. Exiting.")
        return

    print(f"\nChat session started for User ID: {user_id}\n" + "-"*30)

    temp_middleware = MemoryMiddleware(summary_llm=agent_factory.model)
    history_manager = temp_middleware.get_history_manager(user_id)
    await history_manager.load_messages()

    try:
        while True:
            user_input = await ainput("You: ")
            if user_input.lower() in ["quit", "exit"]: break
            if not user_input.strip(): continue

            response = await chat_agent.ainvoke(
                {"messages": [HumanMessage(content=user_input)]},
                config={
                    "recursion_limit": 50,
                    "configurable": {
                        "chat_history_manager": history_manager,
                        "user_id": user_id
                    }
                }
            )

            if response and "messages" in response and response["messages"]:
                final_message = response["messages"][-1]
                if final_message.content and not isinstance(final_message.content, list):
                    print(f"Agent: {final_message.content}")
                else:
                    logger.warning("Agent's final message had no printable content.")
                    print("Agent: I'm performing an action in the background.")
            else:
                logger.warning("Agent did not return a valid response with a 'messages' key.")
                print("Agent: I'm sorry, I couldn't generate a response.")

    except (KeyboardInterrupt, EOFError):
        print("\nExiting chat session.")
    except Exception as e:
        logger.error(f"An error occurred during the chat session: {e}", exc_info=True)
    finally:
        # Give background tasks a moment to finish
        await asyncio.sleep(1)
        await db_manager.close()
        if redis_manager._client:
            redis_manager.close()
        print("\nEnding chat session. Goodbye!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Exiting.")