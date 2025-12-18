from autogen_core import MessageContext, RoutedAgent, message_handler
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from ..utils.message import JudgeMessage, MsgJudgeMessage
from ..utils import prompts, functions
import logging
logger = logging.getLogger("QuadSentinel")

class JudgeAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("the judge agent")
        self.model_client = model_client
        self.system_message = SystemMessage(content=prompts.JUDGE_SYSTEM)
        self.threat_level_map = {
            0: "Trusted",
            1: "Low",
            2: "Moderate",
            3: "High",
            4: "Critical"
        }

    @message_handler
    async def on_action_message(self, message: JudgeMessage, ctx: MessageContext) -> dict:
        observation = message.content
        tool_name = message.tool.name
        tool_description = message.tool.description
        tool_arguments = message.tool.arguments
        policies = str(message.policies)
        threat_level = self.threat_level_map[message.threat_level]
        prompt = prompts.JUDGE_USER.format(observation=observation, tool_name=tool_name, tool_description=tool_description, tool_arguments=tool_arguments, policies=policies, threat_level=threat_level)
        logger.debug(f"Judge Prompt: {prompt}")
        return await functions.retry_extract_json(self.model_client, messages=[self.system_message, UserMessage(content=prompt, source="user")])
    
    @message_handler
    async def on_msg_message(self, message: MsgJudgeMessage, ctx: MessageContext) -> dict:
        observation = message.content
        policies = str(message.policies)
        system_prompt = prompts.JUDGE_SYSTEM_MSG
        prompt = prompts.JUDGE_USER_MSG.format(observation=observation, policies=policies)
        logger.debug(f"Judge Prompt: {prompt}")
        return await functions.retry_extract_json(self.model_client, messages=[SystemMessage(content=system_prompt), UserMessage(content=prompt, source="user")])