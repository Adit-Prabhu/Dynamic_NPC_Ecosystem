"""
Viral Information Propagation Tracker

Tracks how secrets/rumors spread through the NPC network:
- Injection of "seed secrets" into specific agents
- Monitoring which agents learn the secret over time
- Measuring mutation/drift of information
- Comparing propagation rates across personality types

This enables quantitative analysis of information flow in multi-agent systems.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class SecretTrace:
    """Tracks a single observation of a secret in the wild."""
    turn_number: int
    agent_id: str
    agent_name: str
    personality_type: str  # "gossip", "stoic", "neutral"
    content: str  # What was actually said
    similarity_score: float  # How close to original secret (0-1)
    mutation: str  # Key differences from original
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn_number,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "personality_type": self.personality_type,
            "content": self.content,
            "similarity": round(self.similarity_score, 3),
            "mutation": self.mutation,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PropagationExperiment:
    """A single experiment tracking secret spread."""
    experiment_id: str
    secret: str
    seed_agent_id: str
    seed_agent_name: str
    start_time: datetime
    traces: List[SecretTrace] = field(default_factory=list)
    agents_reached: Set[str] = field(default_factory=set)
    total_turns: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "secret": self.secret,
            "seed_agent": {
                "id": self.seed_agent_id,
                "name": self.seed_agent_name,
            },
            "start_time": self.start_time.isoformat(),
            "total_turns": self.total_turns,
            "agents_reached": list(self.agents_reached),
            "propagation_rate": len(self.agents_reached) / max(1, self.total_turns),
            "traces": [t.to_dict() for t in self.traces],
        }


class PropagationTracker:
    """
    Tracks viral spread of secrets through the NPC network.
    
    Usage:
        tracker = PropagationTracker()
        exp_id = tracker.inject_secret("guard", "The King is a werewolf")
        
        # After each dialogue turn:
        tracker.observe_turn(turn, turn_number)
        
        # Get results:
        results = tracker.get_experiment_results(exp_id)
    """
    
    # Keywords that indicate information sharing
    PROPAGATION_SIGNALS = [
        "heard", "told", "said", "mentioned", "whispered",
        "rumor", "secret", "between us", "don't tell",
        "apparently", "they say", "word is", "I heard",
    ]
    
    # Personality classification based on traits
    GOSSIP_INDICATORS = [
        "curious", "talkative", "social", "nosy", "dramatic",
        "theatrical", "mischievous", "conspiratorial", "excited",
    ]
    
    STOIC_INDICATORS = [
        "reserved", "quiet", "suspicious", "paranoid", "guarded",
        "careful", "stoic", "serene", "calm", "patient",
    ]
    
    def __init__(self, persist_path: Optional[Path] = None):
        self.experiments: Dict[str, PropagationExperiment] = {}
        self.active_secrets: Dict[str, str] = {}  # secret_keywords -> experiment_id
        self.persist_path = persist_path or Path("../.propagation")
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self._load_experiments()
    
    def _load_experiments(self) -> None:
        """Load previous experiments from disk."""
        exp_file = self.persist_path / "experiments.json"
        if exp_file.exists():
            try:
                with open(exp_file, "r") as f:
                    data = json.load(f)
                # Reconstruct experiments (simplified - full reconstruction would need more)
                logger.info(f"Found {len(data.get('experiments', []))} previous experiments")
            except Exception as e:
                logger.warning(f"Failed to load experiments: {e}")
    
    def _save_experiments(self) -> None:
        """Persist experiments to disk."""
        exp_file = self.persist_path / "experiments.json"
        data = {
            "experiments": [exp.to_dict() for exp in self.experiments.values()],
            "saved_at": datetime.now().isoformat(),
        }
        with open(exp_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def inject_secret(
        self,
        agent_id: str,
        agent_name: str,
        secret: str,
        experiment_id: Optional[str] = None,
    ) -> str:
        """
        Inject a secret into an agent and start tracking its spread.
        
        Args:
            agent_id: The agent to receive the secret
            agent_name: Display name of the agent
            secret: The secret content (e.g., "The King is a werewolf")
            experiment_id: Optional custom ID for this experiment
            
        Returns:
            The experiment ID for tracking
        """
        exp_id = experiment_id or f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        experiment = PropagationExperiment(
            experiment_id=exp_id,
            secret=secret,
            seed_agent_id=agent_id,
            seed_agent_name=agent_name,
            start_time=datetime.now(),
        )
        experiment.agents_reached.add(agent_id)
        
        self.experiments[exp_id] = experiment
        
        # Extract keywords for matching
        keywords = self._extract_keywords(secret)
        for keyword in keywords:
            self.active_secrets[keyword.lower()] = exp_id
        
        logger.info(f"Injected secret into {agent_name}: '{secret[:50]}...' (exp: {exp_id})")
        self._save_experiments()
        
        return exp_id
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords from text for matching."""
        # Remove common words and extract meaningful terms
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "that", "this", "these", "those", "it", "its", "as", "or",
            "and", "but", "if", "so", "than", "too", "very", "just",
        }
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [w for w in words if w not in stop_words]
        
        # Also extract phrases (2-grams)
        for i in range(len(words) - 1):
            if words[i] not in stop_words or words[i+1] not in stop_words:
                keywords.append(f"{words[i]} {words[i+1]}")
        
        return keywords[:10]  # Limit to top 10
    
    def classify_personality(self, mood: str, profession: str, name: str) -> str:
        """Classify an agent's personality type for analysis."""
        combined = f"{mood} {profession} {name}".lower()
        
        gossip_score = sum(1 for ind in self.GOSSIP_INDICATORS if ind in combined)
        stoic_score = sum(1 for ind in self.STOIC_INDICATORS if ind in combined)
        
        if gossip_score > stoic_score:
            return "gossip"
        elif stoic_score > gossip_score:
            return "stoic"
        return "neutral"
    
    def observe_turn(
        self,
        speaker_id: str,
        speaker_name: str,
        speaker_mood: str,
        speaker_profession: str,
        listener_id: str,
        content: str,
        turn_number: int,
    ) -> List[Tuple[str, SecretTrace]]:
        """
        Observe a dialogue turn and check for secret propagation.
        
        Returns list of (experiment_id, trace) tuples for any detected propagation.
        """
        detected: List[Tuple[str, SecretTrace]] = []
        content_lower = content.lower()
        
        for experiment in self.experiments.values():
            # Check if this content relates to the secret
            similarity = self._calculate_similarity(content, experiment.secret)
            keyword_match = self._check_keyword_match(content_lower, experiment.secret)
            
            if similarity > 0.3 or keyword_match:
                # Secret detected in this turn!
                personality = self.classify_personality(
                    speaker_mood, speaker_profession, speaker_name
                )
                
                mutation = self._identify_mutation(content, experiment.secret)
                
                trace = SecretTrace(
                    turn_number=turn_number,
                    agent_id=speaker_id,
                    agent_name=speaker_name,
                    personality_type=personality,
                    content=content[:200],
                    similarity_score=max(similarity, 0.5 if keyword_match else 0),
                    mutation=mutation,
                )
                
                experiment.traces.append(trace)
                experiment.agents_reached.add(speaker_id)
                experiment.agents_reached.add(listener_id)  # Listener now knows too
                experiment.total_turns = max(experiment.total_turns, turn_number)
                
                detected.append((experiment.experiment_id, trace))
                
                logger.info(
                    f"Secret propagation detected: {speaker_name} → turn {turn_number}, "
                    f"similarity: {similarity:.2f}, mutation: {mutation[:50]}"
                )
        
        if detected:
            self._save_experiments()
        
        return detected
    
    def _calculate_similarity(self, content: str, secret: str) -> float:
        """Calculate semantic similarity between content and secret."""
        # Use SequenceMatcher for basic similarity
        # In production, you'd use embeddings for semantic similarity
        return SequenceMatcher(None, content.lower(), secret.lower()).ratio()
    
    def _check_keyword_match(self, content: str, secret: str) -> bool:
        """Check if key terms from secret appear in content."""
        keywords = self._extract_keywords(secret)
        matches = sum(1 for kw in keywords if kw in content)
        return matches >= 2  # At least 2 keywords must match
    
    def _identify_mutation(self, content: str, original: str) -> str:
        """Identify how the information has mutated."""
        content_keywords = set(self._extract_keywords(content))
        original_keywords = set(self._extract_keywords(original))
        
        added = content_keywords - original_keywords
        removed = original_keywords - content_keywords
        
        mutations = []
        if added:
            mutations.append(f"added: {', '.join(list(added)[:3])}")
        if removed:
            mutations.append(f"lost: {', '.join(list(removed)[:3])}")
        
        return "; ".join(mutations) if mutations else "minimal drift"
    
    def get_experiment_results(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get results for a specific experiment."""
        if experiment_id not in self.experiments:
            return None
        return self.experiments[experiment_id].to_dict()
    
    def get_all_experiments(self) -> List[Dict[str, Any]]:
        """Get all experiment results."""
        return [exp.to_dict() for exp in self.experiments.values()]
    
    def get_propagation_analysis(self) -> Dict[str, Any]:
        """
        Analyze propagation patterns across all experiments.
        
        Returns statistics comparing gossip vs stoic personality propagation rates.
        """
        gossip_traces: List[SecretTrace] = []
        stoic_traces: List[SecretTrace] = []
        neutral_traces: List[SecretTrace] = []
        
        for exp in self.experiments.values():
            for trace in exp.traces:
                if trace.personality_type == "gossip":
                    gossip_traces.append(trace)
                elif trace.personality_type == "stoic":
                    stoic_traces.append(trace)
                else:
                    neutral_traces.append(trace)
        
        def calc_stats(traces: List[SecretTrace]) -> Dict[str, float]:
            if not traces:
                return {"count": 0, "avg_similarity": 0, "mutation_rate": 0}
            
            avg_sim = sum(t.similarity_score for t in traces) / len(traces)
            mutations = sum(1 for t in traces if t.mutation != "minimal drift")
            
            return {
                "count": len(traces),
                "avg_similarity": round(avg_sim, 3),
                "mutation_rate": round(mutations / len(traces), 3),
            }
        
        total_experiments = len(self.experiments)
        total_agents_reached = sum(len(exp.agents_reached) for exp in self.experiments.values())
        
        return {
            "total_experiments": total_experiments,
            "total_agents_reached": total_agents_reached,
            "personality_analysis": {
                "gossip": calc_stats(gossip_traces),
                "stoic": calc_stats(stoic_traces),
                "neutral": calc_stats(neutral_traces),
            },
            "propagation_comparison": {
                "gossip_spreads_faster": len(gossip_traces) > len(stoic_traces),
                "gossip_to_stoic_ratio": (
                    round(len(gossip_traces) / max(1, len(stoic_traces)), 2)
                ),
            },
            "information_fidelity": {
                "avg_similarity_overall": round(
                    sum(t.similarity_score for exp in self.experiments.values() for t in exp.traces)
                    / max(1, sum(len(exp.traces) for exp in self.experiments.values())),
                    3
                ),
            },
        }
    
    def generate_report(self) -> str:
        """Generate a markdown report of propagation analysis."""
        analysis = self.get_propagation_analysis()
        
        report = f"""# Information Propagation Analysis Report

## Overview
- **Total Experiments**: {analysis['total_experiments']}
- **Total Agents Reached**: {analysis['total_agents_reached']}

## Personality-Based Propagation

| Personality | Propagation Count | Avg Similarity | Mutation Rate |
|-------------|-------------------|----------------|---------------|
| Gossip | {analysis['personality_analysis']['gossip']['count']} | {analysis['personality_analysis']['gossip']['avg_similarity']} | {analysis['personality_analysis']['gossip']['mutation_rate']} |
| Stoic | {analysis['personality_analysis']['stoic']['count']} | {analysis['personality_analysis']['stoic']['avg_similarity']} | {analysis['personality_analysis']['stoic']['mutation_rate']} |
| Neutral | {analysis['personality_analysis']['neutral']['count']} | {analysis['personality_analysis']['neutral']['avg_similarity']} | {analysis['personality_analysis']['neutral']['mutation_rate']} |

## Key Findings

- **Gossip personalities spread information faster**: {analysis['propagation_comparison']['gossip_spreads_faster']}
- **Gossip-to-Stoic propagation ratio**: {analysis['propagation_comparison']['gossip_to_stoic_ratio']}x
- **Overall information fidelity**: {analysis['information_fidelity']['avg_similarity_overall']}

## Experiment Details
"""
        
        for exp in self.experiments.values():
            exp_dict = exp.to_dict()
            report += f"""
### Experiment: {exp_dict['experiment_id']}
- **Secret**: "{exp_dict['secret']}"
- **Seed Agent**: {exp_dict['seed_agent']['name']}
- **Turns**: {exp_dict['total_turns']}
- **Agents Reached**: {len(exp_dict['agents_reached'])}
- **Propagation Rate**: {exp_dict['propagation_rate']:.3f} agents/turn

"""
        
        return report
    
    def clear_experiments(self) -> None:
        """Clear all experiments."""
        self.experiments.clear()
        self.active_secrets.clear()
        self._save_experiments()
