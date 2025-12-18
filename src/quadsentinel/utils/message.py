from pydantic import BaseModel

class Message(BaseModel):
    content: str

class PredicateMessage(BaseModel):
    predicates: dict
    content: str

class ToolMessage(BaseModel):
    name: str
    description: str
    arguments: str

class VerifyMessage(BaseModel):
    predicates: dict
    policies: dict

class JudgeMessage(BaseModel):
    content: str
    policies: str
    tool: ToolMessage
    threat_level: int|None

class MsgJudgeMessage(BaseModel):
    content: str
    policies: str

class ThreatMessage(BaseModel):
    content: str
    threat_level: int