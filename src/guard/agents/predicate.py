from autogen_core import MessageContext, RoutedAgent, message_handler
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from ..utils.message import PredicateMessage
from ..utils import prompts
from ..utils import functions
import logging

logger = logging.getLogger("Guard")


class PredicateWatcher(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("the predicate watcher")
        self.model_client = model_client
        self.system_message = SystemMessage(content=prompts.PREDICATE_WATCHER_SYSTEM)

    @message_handler
    async def on_message(self, message: PredicateMessage, ctx: MessageContext) -> dict:
        prompt = prompts.PREDICATE_WATCHER_USER.format(predicates=str(message.predicates), observation=message.content)
        prompt = UserMessage(content=prompt, source="user")
        logger.debug(f"Predicate watcher prompt: {prompt.content}")
        return await functions.retry_extract_json(self.model_client, messages=[self.system_message, prompt])
        