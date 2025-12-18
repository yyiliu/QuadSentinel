import logging
from autogen_core import MessageContext, RoutedAgent, message_handler
from autogen_core.models import ChatCompletionClient, SystemMessage
from ..utils import prompts
from ..utils.message import VerifyMessage
logger = logging.getLogger("QuadSentinel")

class PolicyVerifier(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("the policy verifier agent")
        self.model_client = model_client

    def _evaluate_logic(self, logic_str: str, predicates: dict) -> bool:
        # logger.info(f"Evaluating logic: {logic_str}")
        if 'IMPLIES' not in logic_str:
            for name, value in predicates.items():
                if name in logic_str:
                    logic_str = logic_str.replace(name, str(value))
            # logger.debug(f"Evaluating logic: {logic_str}")
            logic_str = logic_str.replace('NOT', 'not')
            logic_str = logic_str.replace('AND', 'and')
            logic_str = logic_str.replace('OR', 'or')
            return eval(logic_str)
        else:
            index = logic_str.index('IMPLIES')
            left = logic_str[:index]
            right = logic_str[index+7:]
            left = self._evaluate_logic(left, predicates)
            right = self._evaluate_logic(right, predicates)
            # logger.debug(f"Left: {left}, Implies, Right: {right}")
            if left and not right:
                return False
            return True
    
    @message_handler
    async def on_message(self, message: VerifyMessage, ctx: MessageContext) -> dict:
        policies = message.policies
        predicates = message.predicates
        predicates = dict(sorted(predicates.items(), key=lambda x: len(x[0]), reverse=True))
        violated_policies = []
        for name, logic in policies.items():
            if not self._evaluate_logic(logic, predicates):
                violated_policies.append(name)
        if len(violated_policies) > 0:
            return {"decision": False, "reason": violated_policies}
        return {"decision": True, "reason": ""}

