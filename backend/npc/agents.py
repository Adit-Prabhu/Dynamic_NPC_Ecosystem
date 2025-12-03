from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .llm import DialogueModel, DialogueResult
from .memory import MemoryStore
from .personalities import PersonalityProfile
from .state import WorldState


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

    def as_dict(self) -> dict:
        return {
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


class Agent:
    def __init__(
        self,
        agent_id: str,
        personality: PersonalityProfile,
        memory_store: MemoryStore,
        dialogue_model: DialogueModel,
    ) -> None:
        self.agent_id = agent_id
        self.personality = personality
        self._memory_store = memory_store
        self._dialogue_model = dialogue_model

    def remember(self, text: str, importance: float = 0.5) -> None:
        self._memory_store.add_memory(self.agent_id, text, importance=importance)

    def speak(self, listener: "Agent", world_state: WorldState, topic: str) -> DialogueTurn:
        memories = self._memory_store.fetch_memories(self.agent_id, topic)
        result: DialogueResult = self._dialogue_model.generate(
            speaker=self.personality,
            listener=listener.personality,
            memories=memories,
            world_state=world_state,
            topic=topic,
        )
        self._memory_store.add_memory(
            self.agent_id,
            result.new_memory,
            tags=[topic, listener.agent_id],
            importance=result.rumor_delta,
        )
        listener._memory_store.add_memory(
            listener.agent_id,
            f"Heard from {self.personality.name} that {result.new_memory}",
            tags=[topic, self.agent_id],
            importance=result.rumor_delta,
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
        )


def seed_agents(memory_store: MemoryStore, agents: List[Agent], hook: str) -> None:
    for agent in agents:
        agent.remember(hook, importance=0.8)
        memory_store.add_memory("global", f"{agent.personality.name} heard: {hook}")
