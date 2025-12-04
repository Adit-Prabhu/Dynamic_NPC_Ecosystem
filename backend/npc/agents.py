from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .llm import DialogueModel, DialogueResult
from .graph_memory import GraphMemoryStore, MemoryRecord
from .personalities import PersonalityProfile
from .state import WorldState

# Alias for compatibility
MemoryStore = GraphMemoryStore


@dataclass(slots=True)
class DialogueTurn:
    speaker: str
    listener: str
    speaker_profession: str
    listener_profession: str
    speaker_mood: str
    listener_mood: str
    content: str
    rumor_delta: float
    sentiment: str
    graph_context: Optional[str] = None  # Relationship context
    internal_monologue: Optional[str] = None  # Chain-of-thought reasoning

    def as_dict(self) -> dict:
        result = {
            "speaker": self.speaker,
            "listener": self.listener,
            "speaker_profession": self.speaker_profession,
            "listener_profession": self.listener_profession,
            "speaker_mood": self.speaker_mood,
            "listener_mood": self.listener_mood,
            "content": self.content,
            "rumor_delta": self.rumor_delta,
            "sentiment": self.sentiment,
        }
        if self.graph_context:
            result["graph_context"] = self.graph_context
        if self.internal_monologue:
            result["internal_monologue"] = self.internal_monologue
        return result


class Agent:
    def __init__(
        self,
        agent_id: str,
        personality: PersonalityProfile,
        memory_store: GraphMemoryStore,
        dialogue_model: DialogueModel,
    ) -> None:
        self.agent_id = agent_id
        self.personality = personality
        self._memory_store = memory_store
        self._dialogue_model = dialogue_model

    def remember(self, text: str, importance: float = 0.5) -> None:
        self._memory_store.add_memory(self.agent_id, text, importance=importance)

    def speak(self, listener: "Agent", world_state: WorldState, topic: str) -> DialogueTurn:
        # Fetch memories using graph traversal
        memories = self._memory_store.fetch_memories(
            self.agent_id,
            topic,
            include_global=True,
            include_connections=True,
        )
        
        # Build graph context for richer dialogue
        graph_context = self._build_graph_context(listener, memories)
        
        result: DialogueResult = self._dialogue_model.generate(
            speaker=self.personality,
            listener=listener.personality,
            memories=memories,
            world_state=world_state,
            topic=topic,
        )
        
        # Add memory with context about who was told
        self._memory_store.add_memory(
            self.agent_id,
            result.new_memory,
            tags=[topic, listener.agent_id],
            importance=result.rumor_delta,
            context={
                "speaker": self.personality.name,
                "listener": listener.personality.name,
            },
        )
        
        # Listener also gains memory with relationship context
        listener._memory_store.add_memory(
            listener.agent_id,
            f"Heard from {self.personality.name} that {result.new_memory}",
            tags=[topic, self.agent_id],
            importance=result.rumor_delta,
            context={
                "speaker": self.personality.name,
                "listener": listener.personality.name,
            },
        )
        
        return DialogueTurn(
            speaker=self.personality.name,
            listener=listener.personality.name,
            speaker_profession=self.personality.profession,
            listener_profession=listener.personality.profession,
            speaker_mood=self.personality.mood,
            listener_mood=listener.personality.mood,
            content=result.utterance,
            rumor_delta=result.rumor_delta,
            sentiment=result.sentiment,
            graph_context=graph_context,
            internal_monologue=result.internal_monologue,
        )
    
    def _build_graph_context(self, listener: "Agent", memories: List[MemoryRecord]) -> str:
        """Build context about relationships and connections."""
        context_parts = []
        
        # Check if there's a relationship path between speaker and listener
        speaker_node = f"npc:{self.agent_id}"
        listener_node = f"npc:{listener.agent_id}"
        
        path = self._memory_store.get_relationship_path(speaker_node, listener_node)
        if path:
            path_desc = " → ".join(
                f"{src.split(':')[-1]} [{rel}]" for src, rel, _ in path
            )
            context_parts.append(f"Relationship path: {path_desc}")
        
        # Add memory connection info
        if memories:
            connections = set()
            for mem in memories[:3]:  # Top 3 memories
                if mem.path_context:
                    connections.add(mem.path_context)
            if connections:
                context_parts.append(f"Memory sources: {'; '.join(connections)}")
        
        return " | ".join(context_parts) if context_parts else ""


def seed_agents(memory_store: GraphMemoryStore, agents: List[Agent], hook: str) -> None:
    """Seed agents with initial memories and create relationships."""
    for agent in agents:
        agent.remember(hook, importance=0.8)
        memory_store.add_memory(
            "global",
            f"{agent.personality.name} heard: {hook}",
            context={"event": "initial_rumor"},
        )
