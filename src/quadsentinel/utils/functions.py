import asyncio
import json
import re
import os
import threading
from autogen_core.models import ChatCompletionClient, ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.anthropic import AnthropicChatCompletionClient


def extract_json(text: str) -> dict:
    try:
        if "```json" in text:
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
        result = json.loads(text)
    except json.JSONDecodeError:
        print("Error parsing JSON: ", text)
        raise ValueError("Invalid JSON")
    return result

async def retry_extract_json(model_client: ChatCompletionClient, messages: list, retry_times: int = 3) -> dict:
    for i in range(retry_times):
        try:
            msg = await model_client.create(messages=messages, json_output=None)
            return extract_json(msg.content)
        except ValueError:
            await asyncio.sleep(1)
    raise ValueError("Failed to extract JSON")

def resolve_model_client(model_name: str) -> ChatCompletionClient:
    if "claude" in model_name.lower():
        return AnthropicChatCompletionClient(model=model_name)
    elif "gpt" in model_name.lower():
        return OpenAIChatCompletionClient(model=model_name)
    else:
        model_info = ModelInfo(
            vision=False, 
            function_calling=True, 
            json_output=True, 
            family="unknown", 
            structured_output=False
        )
        open_router_model_client = OpenAIChatCompletionClient(
            base_url="https://openrouter.ai/api/v1",
            model=model_name,
            api_key=os.getenv("OPEN_ROUTER_API_KEY"),
            model_info=model_info
        )
        return open_router_model_client

class AsyncRunner:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._start_loop, daemon=True)
        self.thread.start()

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

async_runner = AsyncRunner()

def run_async(coro):
    return async_runner.run(coro)

def async_to_sync(func):
    def wrapper(*args, **kwargs):
        return run_async(func(*args, **kwargs))
    return wrapper
