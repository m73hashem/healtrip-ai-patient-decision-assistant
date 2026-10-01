from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Action(StrEnum):
    ER = "ER"
    URGENT_CARE = "URGENT_CARE"
    SPECIALIST = "SPECIALIST"
    SECOND_OPINION = "SECOND_OPINION"
    SELF_CARE = "SELF_CARE"
    CLARIFY = "CLARIFY"


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=30)


class Recommendation(BaseModel):
    type: Literal["doctor", "hospital"]
    id: int
    name: str
    specialty: str | None = None
    hospital: str | None = None
    city: str | None = None
    source: Literal["database"] = "database"


class ChatResponse(BaseModel):
    message: str
    action: Action = Action.CLARIFY
    recommendations: list[Recommendation] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
