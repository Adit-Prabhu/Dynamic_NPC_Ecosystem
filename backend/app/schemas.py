from __future__ import annotations

from typing import List, Optional

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
    internal_monologue: Optional[str] = None  # Chain-of-thought reasoning
    graph_context: Optional[str] = None  # Relationship context from GraphRAG


class RunResponse(BaseModel):
    history: List[DialogueTurnModel]
    world_state: dict


class ResetRequest(BaseModel):
    event: str | None = Field(default=None, description="Optional custom rumor seed")


# =========== Propagation Experiment Schemas ===========

class InjectSecretRequest(BaseModel):
    """Request to inject a secret into an NPC."""
    secret: str = Field(..., description="The secret to inject and track")
    source_npc: Optional[str] = Field(None, description="NPC to inject secret into (uses first available if not specified)")


class InjectSecretResponse(BaseModel):
    """Response after injecting a secret."""
    success: bool
    message: str
    source_npc: str
    secret: str


class PropagationStatsResponse(BaseModel):
    """Current propagation statistics - flexible structure."""
    active: bool
    message: str


class ExperimentRequest(BaseModel):
    """Request to run a full propagation experiment."""
    secret: Optional[str] = Field(None, description="Secret to propagate (uses default if not specified)")
    rounds: int = Field(10, ge=1, le=50, description="Number of dialogue rounds")


class ExperimentResponse(BaseModel):
    """Complete experiment results - flexible structure."""
    success: bool
    experiment_id: Optional[str] = None
    secret: Optional[str] = None
    rounds: int = 0
