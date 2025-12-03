from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class WorldState:
    """Tracks mutable world variables affected by gossip."""

    rumor_heat: float = 0.0
    guard_alert_level: float = 0.2
    shop_price_modifier: float = 1.0
    last_event: str = "Vault door left ajar last night."
    rumor_log: list[Dict[str, str]] = field(default_factory=list)
    # Track the evolving conversation thread
    current_thread: str = ""
    conversation_beats: List[str] = field(default_factory=list)

    def apply_rumor(self, speaker: str, rumor_delta: float, content: str, new_development: str = "") -> None:
        self.rumor_heat = max(0.0, self.rumor_heat + rumor_delta)
        self.guard_alert_level = min(1.0, max(0.0, self.guard_alert_level + rumor_delta * 0.3))
        self.shop_price_modifier = max(0.5, min(1.5, self.shop_price_modifier + rumor_delta * 0.1))
        self.rumor_log.append({
            "speaker": speaker,
            "content": content,
            "delta": f"{rumor_delta:+.2f}",
        })
        # Evolve the conversation thread based on what was just said
        if new_development:
            self.current_thread = new_development
            self.conversation_beats.append(new_development)
            # Keep only recent beats to avoid context bloat
            if len(self.conversation_beats) > 10:
                self.conversation_beats = self.conversation_beats[-10:]

    def get_conversation_context(self) -> str:
        """Returns the current topic plus recent conversation flow."""
        if self.current_thread:
            return self.current_thread
        return self.last_event
    
    def get_recent_beats(self, limit: int = 3) -> List[str]:
        """Returns the most recent conversation developments."""
        return self.conversation_beats[-limit:] if self.conversation_beats else []

    def snapshot(self) -> Dict[str, float | str]:
        return {
            "rumor_heat": round(self.rumor_heat, 2),
            "guard_alert_level": round(self.guard_alert_level, 2),
            "shop_price_modifier": round(self.shop_price_modifier, 2),
            "last_event": self.last_event,
            "current_thread": self.current_thread or self.last_event,
            "rumor_log": self.rumor_log[-10:],
        }
