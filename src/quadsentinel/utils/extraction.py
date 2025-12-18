from typing import List
from autogen_core import AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime, message_handler
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from .message import Message
from . import prompts, functions
import json
import os

class PolicyAgent:
    def __init__(self, model_client: ChatCompletionClient):
        self.model_client = model_client
        self.policy_extraction_agent = AgentId("policy_extraction_agent", "default")
        self.logic_policy_agent = AgentId("logic_policy_agent", "default")
        self.vr_agent = AgentId("vr_agent", "default")
        self.rp_agent = AgentId("rp_agent", "default")
        self.runtime = SingleThreadedAgentRuntime()
        self.max_chunk_size = 10000  # Maximum characters per chunk
        self.raw_policy = None
    
    async def start(self) -> None:
        await PolicyExtractionAgent.register(self.runtime, "policy_extraction_agent", lambda: PolicyExtractionAgent(self.model_client))
        await LogicPolicyAgent.register(self.runtime, "logic_policy_agent", lambda: LogicPolicyAgent(self.model_client))
        await VRAgent.register(self.runtime, "vr_agent", lambda: VRAgent(self.model_client))
        await RPAgent.register(self.runtime, "rp_agent", lambda: RPAgent(self.model_client))
        self.runtime.start()

    async def stop(self) -> None:
        await self.runtime.stop()
    
    def _split_into_chunks(self, content: str) -> List[str]:
        """
        Split content into chunks based on paragraphs, with a maximum character limit.
        Each chunk will contain complete paragraphs and not exceed max_chunk_size characters.
        """
        paragraphs = content.split('\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If adding this paragraph would exceed the limit, start a new chunk
            if len(current_chunk) + len(paragraph) + 1 > self.max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += '\n' + paragraph
                else:
                    current_chunk = paragraph
        
        # Add the last chunk if it has content
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks

        
    async def extract_policy(self, content: str) -> str:
        result = await self.runtime.send_message(Message(content=content), self.policy_extraction_agent)
        return result
    
    async def extract_logical_policy(self, policy: str) -> str:
        result = await self.runtime.send_message(Message(content=str(policy)), self.logic_policy_agent)
        return result
    
    async def verify_predicate(self, policy: str) -> str:
        result = await self.runtime.send_message(Message(content=str(policy)), self.vr_agent)
        return result
    
    async def refine_predicate(self, policy: str) -> str:
        result = await self.runtime.send_message(Message(content=str(policy)), self.rp_agent)
        return result
    
    async def extract(self, file_path: str) -> dict:
        with open(file_path, "r") as f:
            content = f.read()
        if self.raw_policy is None:
            self.raw_policy = content
        else:
            content = self.raw_policy + "\n\n" + content

        cache_path = file_path+".cache.json"
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                return json.load(f)
        
        
        # Split content into manageable chunks
        chunks = self._split_into_chunks(content)
        policies = []
        for chunk in chunks:
            policy = await self.extract_policy(chunk)
            policy = await self.extract_from_policy(policy)
            policies.extend(policy)
        
        with open(cache_path, "w") as f:
            json.dump(policies, f, indent=4)
        return policies
    
    async def extract_from_policy(self, policy: str) -> dict:
        logic_policy = await self.extract_logical_policy(policy)
        vr_policy = await self.verify_predicate(logic_policy)
        rp_policy = await self.refine_predicate(vr_policy)
        return rp_policy
    
    async def stop(self) -> None:
        await self.runtime.stop()

class PolicyExtractionAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient):
        super().__init__("the policy extraction agent")
        self.model_client = model_client
        self.system_message = SystemMessage(content=prompts.POLICY_EXTRACTION_SYSTEM)
    
    @message_handler
    async def on_message(self, message: Message, ctx: MessageContext) -> str:
        prompt = prompts.POLICY_EXTRACTION_USER.format(content=message.content)
        prompt = UserMessage(content=prompt, source="user")
        response = await self.model_client.create(messages=[self.system_message, prompt], cancellation_token=ctx.cancellation_token, json_output=None)
        return response.content

class LogicPolicyAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient):
        super().__init__("the logic policy agent")
        self.model_client = model_client
        self.system_message = SystemMessage(content=prompts.LOGIC_EXTRACTION_SYSTEM)

    @message_handler
    async def on_message(self, message: Message, ctx: MessageContext) -> str:
        prompt = prompts.LOGIC_EXTRACTION_USER.format(content=message.content)
        prompt = UserMessage(content=prompt, source="user")
        response = await self.model_client.create(messages=[self.system_message, prompt], cancellation_token=ctx.cancellation_token, json_output=None)
        return response.content

class VRAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient):
        super().__init__("the VR agent")
        self.model_client = model_client
        self.system_message = SystemMessage(content=prompts.VR_SYSTEM)
    
    @message_handler
    async def on_message(self, message: Message, ctx: MessageContext) -> str:
        prompt = prompts.VR_USER.format(content=message.content)
        prompt = UserMessage(content=prompt, source="user")
        response = await self.model_client.create(messages=[self.system_message, prompt], cancellation_token=ctx.cancellation_token, json_output=None)
        # response = json.loads(response.content)
        return response.content

class RPAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient):
        super().__init__("the RP agent")
        self.model_client = model_client
        self.system_message = SystemMessage(content=prompts.RP_SYSTEM)
    
    @message_handler
    async def on_message(self, message: Message, ctx: MessageContext) -> list:
        prompt = prompts.RP_USER.format(content=message.content)
        prompt = UserMessage(content=prompt, source="user")
        response = await functions.retry_extract_json(self.model_client, messages=[self.system_message, prompt])
        return response
    

async def create_policy_agent(model_client: ChatCompletionClient) -> PolicyAgent:
    agent = PolicyAgent(model_client)
    await agent.start()
    return agent