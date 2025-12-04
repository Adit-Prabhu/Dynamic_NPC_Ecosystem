from __future__ import annotations

from collections import deque
from typing import Deque, List, Sequence

from .agents import Agent, DialogueTurn, seed_agents
from .llm import TemplateDialogueModel
from .graph_memory import GraphMemoryStore
from .personalities import PersonalityProfile, load_personality, sample_personality_keys
from .state import WorldState

# Alias for compatibility
MemoryStore = GraphMemoryStore


class Orchestrator:
    def __init__(
        self,
        personalities: Sequence[str] | None = None,
        memory_store: GraphMemoryStore | None = None,
        model: TemplateDialogueModel | None = None,
        rumor_hook: str = "Vault door left ajar last night.",
    ) -> None:
        roster = list(personalities) if personalities else sample_personality_keys(2)
        self.world_state = WorldState(last_event=rumor_hook)
        self.memory_store = memory_store or GraphMemoryStore()
        self.model = model or TemplateDialogueModel()
        self.agents: List[Agent] = [
            Agent(agent_id=key, personality=load_personality(key), memory_store=self.memory_store, dialogue_model=self.model)
            for key in roster
        ]
        seed_agents(self.memory_store, self.agents, rumor_hook)
        self._queue: Deque[Agent] = deque(self.agents)
        self._history: Deque[DialogueTurn] = deque(maxlen=50)

    def _pick_pair(self) -> tuple[Agent, Agent]:
        speaker = self._queue[0]
        listener = self._queue[1]
        self._queue.rotate(-1)
        return speaker, listener

    def step(self) -> DialogueTurn:
        speaker, listener = self._pick_pair()
        # Use the evolving conversation context, not just the original seed
        current_topic = self.world_state.get_conversation_context()
        turn = speaker.speak(listener, self.world_state, topic=current_topic)
        # Extract a short summary for the new development, not the full utterance
        # Use new_memory from the LLM which should be a brief note
        new_dev = getattr(turn, 'content', '')[:100] if turn.content else self.world_state.last_event
        # Only update if it's actually new content (not a fallback that repeats the topic)
        if 'glances at' not in new_dev and 'mutters something' not in new_dev:
            self.world_state.apply_rumor(
                speaker.personality.name, 
                turn.rumor_delta, 
                turn.content,
                new_development=new_dev
            )
        else:
            # Fallback was used, don't update the thread
            self.world_state.apply_rumor(
                speaker.personality.name, 
                turn.rumor_delta, 
                turn.content,
                new_development=""  # Keep the existing thread
            )
        self._history.append(turn)
        return turn

    def run_steps(self, steps: int) -> List[dict]:
        return [self.step().as_dict() for _ in range(max(1, steps))]

    def history(self, limit: int = 20) -> List[dict]:
        return [turn.as_dict() for turn in list(self._history)[-limit:]]

    def snapshot(self) -> dict:
        return {
            "world_state": self.world_state.snapshot(),
            "history": self.history(),
        }
