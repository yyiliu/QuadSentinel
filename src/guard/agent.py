from typing import Any, Tuple
from autogen_core import AgentId, SingleThreadedAgentRuntime
from autogen_core.models import ChatCompletionClient
from autogen_core.model_context import BufferedChatCompletionContext
from .utils.functions import resolve_model_client
from .agents.threat import ThreatWatcher
from .agents.predicate import PredicateWatcher
from .agents.verifier import PolicyVerifier
from .agents.judge import JudgeAgent
from .utils.message import PredicateMessage, VerifyMessage, ToolMessage, JudgeMessage, ThreatMessage, MsgJudgeMessage
import logging
import chromadb
import os
import chromadb.utils.embedding_functions as embedding_functions
from .utils.extraction import create_policy_agent
from .utils.functions import async_to_sync
logger = logging.getLogger("Guard")

class Guard:
    def __init__(self, model_client: ChatCompletionClient,
                 chief_judge_model_client: ChatCompletionClient,
                 policy_model_client: ChatCompletionClient,
                 embedding_function: embedding_functions.EmbeddingFunction,
                 message_buffer_size: int = 5,
                 default_predicate_update_size: int = 5,
                 ) -> None:
        self.model_client = model_client
        self.chief_judge_model_client = chief_judge_model_client
        self.policy_model_client = policy_model_client
        self.policy = None
        self.runtime = SingleThreadedAgentRuntime()
        self.predicates = dict()
        self.policies = dict()
        self.threat_levels = dict()
        self.policy_verifier = AgentId("policy_verifier", "default")
        self.predicate_watcher = AgentId("predicate_watcher", "default")
        self.threat_watcher = AgentId("threat_watcher", "default")
        self.judge_agent = AgentId("judge_agent", "default")
        self.chief_judge_agent = AgentId("chief_judge_agent", "default")
        self.tool_descriptions = dict()
        self.context = BufferedChatCompletionContext(buffer_size=message_buffer_size)
        self.context_set = set()
        self.initial_message = None
        self.saved_action_hash = None
        self.saved_action_result = None
        self.message_policy = None
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(name="predicate_collection", embedding_function=embedding_function)
        self.agent_history = dict()
        self.default_k = default_predicate_update_size
        self.enabled = True
        self.force_message_check = False

    async def init(self):
        await ThreatWatcher.register(self.runtime, "threat_watcher", lambda: ThreatWatcher(self.model_client))
        await PredicateWatcher.register(self.runtime, "predicate_watcher", lambda: PredicateWatcher(self.model_client))
        await PolicyVerifier.register(self.runtime, "policy_verifier", lambda: PolicyVerifier(self.model_client))
        await JudgeAgent.register(self.runtime, "judge_agent", lambda: JudgeAgent(self.model_client))
        await JudgeAgent.register(self.runtime, "chief_judge_agent", lambda: JudgeAgent(self.chief_judge_model_client))
        self.policy_agent = await create_policy_agent(self.policy_model_client)
        self.runtime.start()
    
    async def stop(self):
        await self.policy_agent.stop()
        await self.runtime.stop()
    
    def enable(self) -> None:
        self.enabled = True
    
    def disable(self) -> None:
        self.enabled = False

    def add_missing_predicates(self) -> None:
        for name, rule in self.policies.items():
            rule = rule.replace('(', '').replace(')', '')
            ps = rule.split(' ')
            for p in ps:
                if p == 'NOT' or p == 'AND' or p == 'OR' or p == 'IMPLIES':
                    continue
                if p not in self.predicates:
                    self.predicates[p] = dict()
                    self.predicates[p]['description'] = p
                    self.predicates[p]['keywords'] = []
                    self.predicates[p]['value'] = False
                    self.collection.add(
                        ids = [p],
                        documents = [str(self.predicates[p])],
                    )


    
    def add_policy_from_dict(self, policy: dict) -> None:
        if not self.enabled:
            return
        logging.debug(f"loading policy: {policy}")
        for rule in policy:
            predicates = rule['predicates']
            logic = rule['logic']
            for predicate in predicates:
                if predicate[0] not in self.predicates:
                    self.predicates[predicate[0]] = dict()
                self.predicates[predicate[0]]['description'] = predicate[1]
                self.predicates[predicate[0]]['keywords'] = predicate[2]
                self.predicates[predicate[0]]['value'] = predicate[3]
                self.collection.add(
                    ids = [predicate[0]],
                    documents = [str(self.predicates[predicate[0]])],
                )
            self.policies[rule['description']] = logic
        self.add_missing_predicates()
    
    def deactivate_policies(self) -> None:
        self.all_policies = self.policies
        self.policies = dict()

    def activate_policy(self, policy_names: list[str]) -> None:
        self.deactivate_policies()
        for policy_name in policy_names:
            self.policies[policy_name] = self.all_policies[policy_name]

    def add_message_policy_from_dict(self, message_policy: dict) -> None:
        if not self.enabled:
            return
        self.message_policy = dict()
        logging.debug(f"loading message policy: {message_policy}")
        for rule in message_policy:
            predicates = rule['predicates']
            logic = rule['logic']
            for predicate in predicates:
                if predicate[0] not in self.predicates:
                    self.predicates[predicate[0]] = dict()
                self.predicates[predicate[0]]['description'] = predicate[1]
                self.predicates[predicate[0]]['keywords'] = predicate[2]
                self.predicates[predicate[0]]['value'] = predicate[3]
                self.collection.add(
                    ids = [predicate[0]],
                    documents = [str(self.predicates[predicate[0]])],
                )
            self.message_policy[rule['description']] = logic
        self.add_missing_predicates()

    def register_tool(self, name: str, description: str) -> None:
        self.tool_descriptions[name] = description
    
    def register_tools(self, tools: list) -> None:
        for tool in tools:
            self.register_tool(tool.__name__, tool.__doc__)
    
    async def add_policy_from_file(self, file_path: str) -> None:
        policy = await self.policy_agent.extract(file_path)
        self.add_policy_from_dict(policy)
    
    async def add_message_policy_from_file(self, file_path: str) -> None:
        policy = await self.policy_agent.extract(file_path)
        self.add_message_policy_from_dict(policy)
    

    async def handle_message(self, message: str, k: int|None = None, sender: str|None = None, recipient: str|None = None) -> Tuple[bool, str]:
        if not self.enabled:
            return True, ""
        if k is None:
            k = self.default_k
        if str(message) == "" or str(message) == "None":
            return True, ""
        logger.info(f"Handling message: {message}")
        await self.context.add_message(message)
        if self.initial_message is None:
            self.initial_message = message
            k=-1
        
        content = ["Initial User Request: "+self.initial_message, "Current Conversation: "+str(await self.context.get_messages())]
        predicates = self.predicates
        if k != -1:
            message_q = message
            if len(message_q) > 8000:
                message_q = message_q[:8000]
            predicates = dict()
            results = self.collection.query(
                query_texts=[message_q],
                n_results=k
            )
            for i, predicate in enumerate(results['ids'][0]):
                predicates[predicate] = self.predicates[predicate]
                # logger.info(f"Predicate {i}: {predicate}, distance: {results['distances'][0][i]}")
        
        msg = PredicateMessage(predicates=predicates, content=str(content))
        result = await self.runtime.send_message(msg, self.predicate_watcher)
        logger.info(f"Predicate watcher result: {result}")
        for k, v in result.items():
            if k not in self.predicates:
                continue
            self.predicates[k]['value'] = v
        
        if sender is not None:
            if sender not in self.agent_history:
                self.agent_history[sender] = BufferedChatCompletionContext(buffer_size=5)
                self.threat_levels[sender] = 0  
            await self.agent_history[sender].add_message(message)
            msg = ThreatMessage(content=str(await self.agent_history[sender].get_messages()), threat_level=self.threat_levels[sender])
            result = await self.runtime.send_message(msg, self.threat_watcher)
            self.threat_levels[sender] = result
            if recipient is not None:
                if recipient not in self.threat_levels:
                    self.threat_levels[recipient] = 0
                self.threat_levels[recipient] = max(self.threat_levels[recipient], result)
        if not self.force_message_check:
            if self.message_policy is None or sender is None or recipient is None:
                return True, ""
        
        if self.force_message_check or self.threat_levels[sender] > 2 or self.threat_levels[recipient] > 2:
            assert self.message_policy is not None
            logger.info(f"Threat level {sender} is too high, checking message policy")
            predicates = {k: v["value"] for k, v in self.predicates.items()}
            msg = VerifyMessage(predicates=predicates, policies=self.message_policy)
            if self.saved_action_hash is not None and self.saved_action_hash == hash(str(msg)):
                action_result = self.saved_action_result
            else:
                action_result = await self.runtime.send_message(msg, self.policy_verifier)
                self.saved_action_hash = hash(str(msg))
                self.saved_action_result = action_result
            logger.info(f"Action watcher result: {action_result}")
            if action_result['decision'] is True:
                return True, ""

            observation = "Initial User Request: "+self.initial_message+"; Current Conversation: "+str(await self.context.get_messages())
            msg = MsgJudgeMessage(content=observation, policies=str(action_result['reason']))
            result = await self.runtime.send_message(msg, self.judge_agent)
            logger.info(f"Message judge agent result: {result}")
            if result['decision'] is False:
                result = await self.runtime.send_message(msg, self.chief_judge_agent)
                logger.info(f"Chief message judge agent result: {result}")
            return result['decision'], result['reason']
        return True, ""

    async def handle_action(self, action: str, arguments: str|None = None, description: str = "", sender: str|None =None) -> Tuple[bool, str]:
        # logger.info(f"Handling action: {action} with arguments: {arguments}")
        if not self.enabled:
            return True, ""
        tool_name = action
        tool_args = arguments if arguments is not None else ""
        if tool_name in self.tool_descriptions:
            tool_description = self.tool_descriptions[tool_name]
        else:
            tool_description = description
        
        
        observation = str(await self.context.get_messages())
        observation = "Initial User Request: "+self.initial_message+"; Current Conversation: "+observation
        predicates = {k: v["value"] for k, v in self.predicates.items()}
        msg = VerifyMessage(predicates=predicates, policies=self.policies)
        if self.saved_action_hash is not None and self.saved_action_hash == hash(str(msg)):
            action_result = self.saved_action_result
        else:
            action_result = await self.runtime.send_message(msg, self.policy_verifier)
            self.saved_action_hash = hash(str(msg))
            self.saved_action_result = action_result
        logger.info(f"Action watcher result: {action_result}")
        if action_result['decision'] is True:
            return True, ""
        
        threat_level = 0
        if sender is not None:
            if sender not in self.threat_levels:
                self.threat_levels[sender] = 0
            threat_level = self.threat_levels[sender]
        
        msg = JudgeMessage(content=observation, tool=ToolMessage(name=tool_name, description=tool_description, arguments=tool_args), policies=str(action_result['reason']), threat_level=threat_level)
        result = await self.runtime.send_message(msg, self.judge_agent)
        logger.info(f"Judge agent result: {result}")
        if result['decision'] is False:
            result = await self.runtime.send_message(msg, self.chief_judge_agent)
            logger.info(f"Chief judge agent result: {result}")
        return result['decision'], result['reason']

async def create_guard(model_name: str = "gpt-4o-mini",
                       chief_judge_model_name: str = "gpt-4o",
                       policy_model_name: str = "gpt-4o",
                       embedding_model_name: str = "text-embedding-3-small") -> Guard:
    model_client = resolve_model_client(model_name)
    chief_judge_model_client = resolve_model_client(chief_judge_model_name)
    embedding_function = embedding_functions.OpenAIEmbeddingFunction(
        model_name=embedding_model_name,
        api_key=os.getenv('OPENAI_API_KEY')
    )
    policy_model_client = resolve_model_client(policy_model_name)
    guard = Guard(model_client, chief_judge_model_client, policy_model_client, embedding_function)
    await guard.init()
    return guard