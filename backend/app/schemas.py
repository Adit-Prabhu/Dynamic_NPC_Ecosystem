from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    steps: int = Field(3, ge=1, le=25)


class DialogueTurnModel(BaseModel):
    speaker: str
    listener: str
    speaker_profession: str
    listener_profession: str
    speaker_mood: str
    listener_mood: str
    content: str
    rumor_delta: float
    sentiment: str


class RunResponse(BaseModel):
    history: List[DialogueTurnModel]
    world_state: dict


class ResetRequest(BaseModel):
    event: str | None = Field(default=None, description="Optional custom rumor seed")
