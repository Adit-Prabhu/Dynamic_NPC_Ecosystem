from __future__ import annotations

from collections import deque
from typing import Deque, List, Optional, Sequence

from .agents import Agent, DialogueTurn, seed_agents
from .llm import TemplateDialogueModel
from .graph_memory import GraphMemoryStore
from .personalities import PersonalityProfile, load_personality, sample_personality_keys
from .propagation import PropagationTracker
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
        enable_propagation_tracking: bool = True,
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
        
        # Propagation tracking
        self._propagation_tracker: Optional[PropagationTracker] = None
        self._tracking_enabled = enable_propagation_tracking
        self._active_secrets: List[str] = []

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
    
    # =========== Propagation Tracking API ===========
    
    def inject_secret(self, secret: str, source_npc: str) -> Optional[str]:
        """
        Inject a secret into an NPC to begin tracking its propagation.
        Returns the experiment ID if successful, None otherwise.
        """
        # Find the source agent
        source_agent = next((a for a in self.agents if a.agent_id == source_npc), None)
        if not source_agent:
            return None
            
        # Create tracker if we don't have one
        if not self._propagation_tracker:
            self._propagation_tracker = PropagationTracker()
        
        # Inject the secret and get experiment ID
        exp_id = self._propagation_tracker.inject_secret(
            agent_id=source_npc,
            agent_name=source_agent.personality.name,
            secret=secret
        )
        self._active_secrets.append(secret)
        
        # Store the secret in the source NPC's memory
        self.memory_store.add_dialogue_memory(
            speaker=source_npc,
            listener="self",
            content=f"[SECRET] {secret}",
            tags=["injected_secret", "confidential"]
        )
        
        # Update world state to inject the secret as the current topic
        self.world_state.last_event = secret
        
        return exp_id
    
    def get_propagation_stats(self) -> Optional[dict]:
        """Get current propagation statistics."""
        if not self._propagation_tracker:
            return None
        return self._propagation_tracker.get_propagation_analysis()
    
    def get_propagation_timeline(self) -> List[dict]:
        """Get all experiments with their propagation data."""
        if not self._propagation_tracker:
            return []
        return self._propagation_tracker.get_all_experiments()
    
    def get_propagation_report(self) -> str:
        """Generate a markdown report of propagation analysis."""
        if not self._propagation_tracker:
            return "No propagation tracking active."
        return self._propagation_tracker.generate_report()
    
    def _turn_number(self) -> int:
        """Get current turn number."""
        return len(self._history)
    
    def step_with_tracking(self) -> DialogueTurn:
        """
        Execute a step and record propagation data if tracking is active.
        """
        speaker, listener = self._pick_pair()
        current_topic = self.world_state.get_conversation_context()
        turn = speaker.speak(listener, self.world_state, topic=current_topic)
        
        # Track propagation if we have an active tracker
        if self._propagation_tracker and turn.content:
            self._propagation_tracker.observe_turn(
                speaker_id=speaker.agent_id,
                speaker_name=speaker.personality.name,
                speaker_mood=turn.speaker_mood,
                speaker_profession=turn.speaker_profession,
                listener_id=listener.agent_id,
                content=turn.content,
                turn_number=self._turn_number()
            )
        
        # Update world state (same logic as regular step)
        new_dev = getattr(turn, 'content', '')[:100] if turn.content else self.world_state.last_event
        if 'glances at' not in new_dev and 'mutters something' not in new_dev:
            self.world_state.apply_rumor(
                speaker.personality.name, 
                turn.rumor_delta, 
                turn.content,
                new_development=new_dev
            )
        else:
            self.world_state.apply_rumor(
                speaker.personality.name, 
                turn.rumor_delta, 
                turn.content,
                new_development=""
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
