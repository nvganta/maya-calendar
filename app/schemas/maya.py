from pydantic import BaseModel


# --- Provision ---

class ProvisionRequest(BaseModel):
    maya_user_id: int
    email: str
    name: str


class ProvisionResponse(BaseModel):
    agent_user_id: str
    needs_setup: bool = False
    setup_url: str | None = None


# --- Chat ---

class ChatUser(BaseModel):
    maya_user_id: int
    email: str
    name: str


class ChatContext(BaseModel):
    agent_user_id: str = ""


class ConversationMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    user: ChatUser
    conversation_history: list[ConversationMessage] = []
    context: ChatContext


class ChatResponse(BaseModel):
    response: str
