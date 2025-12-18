from autogen_core import MessageContext, RoutedAgent, message_handler
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from ..utils.message import ThreatMessage
from ..utils import prompts
import logging
logger = logging.getLogger("QuadSentinel")
from ..utils import functions

class ThreatWatcher(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("the threat watcher agent")
        self.model_client = model_client
        self.system_message = SystemMessage(content=prompts.THREAT_WATCHER_SYSTEM)

    @message_handler
    async def on_message(self, message: ThreatMessage, ctx: MessageContext) -> int:
        prompt = prompts.THREAT_WATCHER_USER.format(observations=str(message.content), threat_level=message.threat_level)
        prompt = UserMessage(content=prompt, source="user")
        logger.debug(f"Threat watcher prompt: {prompt.content}")
        response = await functions.retry_extract_json(self.model_client, messages=[self.system_message, prompt])
        logger.debug(f"Threat watcher result: {response}")
        return response['threat_level']