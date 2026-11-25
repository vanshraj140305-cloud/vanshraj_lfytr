from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

SessionId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ChatRequest(BaseModel):
    session_id: SessionId
    message: Message
    system_prompt: Optional[Annotated[str, StringConstraints(max_length=4000)]] = None
