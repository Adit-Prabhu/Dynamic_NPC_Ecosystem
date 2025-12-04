"""
GraphRAG-based memory system for NPCs.

Uses a knowledge graph to track:
- Entities (NPCs, locations, objects, events)
- Relationships (who knows what, who told whom, connections)
- Temporal context (when things happened, conversation order)

This enables richer retrieval than pure vector search by following
relationship paths and understanding context.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)

# Optional: Use LLM for entity extraction
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


@dataclass
class Entity:
    """A node in the knowledge graph."""
    id: str
    type: str  # "npc", "location", "object", "event", "rumor", "concept"
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Relationship:
    """An edge in the knowledge graph."""
    source_id: str
    target_id: str
    type: str  # "knows", "told", "witnessed", "suspects", "located_at", "related_to"
    properties: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.type,
            "properties": self.properties,
            "weight": self.weight,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MemoryRecord:
    """Compatible with the old interface but with graph context."""
    text: str
    metadata: Dict[str, Any]
    score: float
    entities: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    path_context: str = ""  # How this memory connects to the query


class EntityExtractor:
    """Extracts entities and relationships from text using LLM or rules."""
    
    ENTITY_PATTERNS = {
        "npc": [
            r"\b(Mara|Rylan|Iris|Theron|Kel|Suna)\b",
            r"\b(guard|shopkeeper|smuggler|bard|artificer|herbalist)\b",
            r"\b(captain|quartermaster|apothecary)\b",
        ],
        "location": [
            r"\b(vault|sewers?|docks?|harbor|temple|market|alehouse|workshop|cellar)\b",
            r"\b(gate|aqueduct|tannery|alley)\b",
        ],
        "object": [
            r"\b(coins?|silver|gold|ledger|key|door|bells?|shipment|crates?)\b",
            r"\b(iron|steel|ale|poppy|nightshade|tea)\b",
        ],
        "event": [
            r"\b(rang|missing|stolen|spotted|slipping|vanished|ajar)\b",
        ],
    }
    
    RELATIONSHIP_PATTERNS = [
        (r"(\w+)\s+(?:told|said to|confided in|whispered to)\s+(\w+)", "told"),
        (r"(\w+)\s+(?:saw|spotted|witnessed|noticed)\s+(.+)", "witnessed"),
        (r"(\w+)\s+(?:suspects?|thinks?|believes?)\s+(.+)", "suspects"),
        (r"(\w+)\s+(?:heard about|learned of)\s+(.+)", "heard_about"),
        (r"(\w+)\s+(?:knows?|knew)\s+(?:about\s+)?(.+)", "knows"),
    ]
    
    def __init__(self, use_llm: bool = False, llm_client: Any = None):
        self.use_llm = use_llm
        self.llm_client = llm_client
    
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[List[Entity], List[Relationship]]:
        """Extract entities and relationships from text."""
        if self.use_llm and self.llm_client:
            return self._extract_with_llm(text, context)
        return self._extract_with_rules(text, context)
    
    def _extract_with_rules(self, text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[List[Entity], List[Relationship]]:
        """Rule-based extraction using regex patterns."""
        entities: List[Entity] = []
        relationships: List[Relationship] = []
        seen_entities: Set[str] = set()
        
        text_lower = text.lower()
        
        # Extract entities
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text_lower):
                    name = match.group(1) if match.groups() else match.group(0)
                    entity_id = f"{entity_type}:{name.lower()}"
                    if entity_id not in seen_entities:
                        seen_entities.add(entity_id)
                        entities.append(Entity(
                            id=entity_id,
                            type=entity_type,
                            name=name.title() if entity_type == "npc" else name,
                            properties={"source_text": text[:100]},
                        ))
        
        # Add context entities (speaker, listener)
        if context:
            if "speaker" in context:
                speaker_id = f"npc:{context['speaker'].lower()}"
                if speaker_id not in seen_entities:
                    entities.append(Entity(
                        id=speaker_id,
                        type="npc",
                        name=context["speaker"],
                    ))
                    seen_entities.add(speaker_id)
            
            if "listener" in context:
                listener_id = f"npc:{context['listener'].lower()}"
                if listener_id not in seen_entities:
                    entities.append(Entity(
                        id=listener_id,
                        type="npc",
                        name=context["listener"],
                    ))
                    seen_entities.add(listener_id)
                
                # Add "told" relationship
                if "speaker" in context:
                    relationships.append(Relationship(
                        source_id=f"npc:{context['speaker'].lower()}",
                        target_id=f"npc:{context['listener'].lower()}",
                        type="told",
                        properties={"content": text[:200]},
                    ))
        
        # Extract relationships from text
        for pattern, rel_type in self.RELATIONSHIP_PATTERNS:
            for match in re.finditer(pattern, text_lower):
                if len(match.groups()) >= 2:
                    source = match.group(1)
                    target = match.group(2)[:50]  # Limit target length
                    
                    # Try to match to known entities
                    source_id = self._find_entity_id(source, seen_entities)
                    target_id = self._find_entity_id(target, seen_entities)
                    
                    if source_id and target_id:
                        relationships.append(Relationship(
                            source_id=source_id,
                            target_id=target_id,
                            type=rel_type,
                        ))
        
        return entities, relationships
    
    def _find_entity_id(self, text: str, known_entities: Set[str]) -> Optional[str]:
        """Try to match text to a known entity."""
        text_lower = text.lower().strip()
        
        # Direct match
        for entity_id in known_entities:
            if text_lower in entity_id:
                return entity_id
        
        # Check entity patterns
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    match = re.search(pattern, text_lower)
                    if match:
                        name = match.group(1) if match.groups() else match.group(0)
                        return f"{entity_type}:{name}"
        
        return None
    
    def _extract_with_llm(self, text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[List[Entity], List[Relationship]]:
        """LLM-based extraction for richer understanding."""
        # Fallback to rules if LLM fails
        try:
            prompt = f"""Extract entities and relationships from this dialogue in a medieval fantasy setting.

Text: "{text}"
Context: {json.dumps(context) if context else "None"}

Return JSON with:
{{
  "entities": [
    {{"id": "type:name", "type": "npc|location|object|event|concept", "name": "...", "properties": {{}}}}
  ],
  "relationships": [
    {{"source": "entity_id", "target": "entity_id", "type": "knows|told|witnessed|suspects|related_to", "properties": {{}}}}
  ]
}}

Entity types: npc (characters), location (places), object (items), event (happenings), concept (ideas/rumors)
Relationship types: knows, told, witnessed, suspects, located_at, related_to, owns, heard_about"""

            # Use OpenAI-compatible client
            if hasattr(self.llm_client, 'chat'):
                response = self.llm_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                content = response.choices[0].message.content
            else:
                # Fallback to rules
                return self._extract_with_rules(text, context)
            
            # Parse response
            data = json.loads(content)
            entities = [
                Entity(
                    id=e["id"],
                    type=e["type"],
                    name=e["name"],
                    properties=e.get("properties", {}),
                )
                for e in data.get("entities", [])
            ]
            relationships = [
                Relationship(
                    source_id=r["source"],
                    target_id=r["target"],
                    type=r["type"],
                    properties=r.get("properties", {}),
                )
                for r in data.get("relationships", [])
            ]
            return entities, relationships
            
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}, falling back to rules")
            return self._extract_with_rules(text, context)


class GraphMemoryStore:
    """
    Knowledge graph-based memory store for NPCs.
    
    Uses NetworkX for in-memory graph with persistence to JSON.
    Can be upgraded to Neo4j for production use.
    """
    
    def __init__(
        self,
        persist_path: str | Path = "../.graph_memory",
        use_llm_extraction: bool = False,
    ):
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        self.graph = nx.MultiDiGraph()  # Directed graph with multiple edges
        self.extractor = EntityExtractor(use_llm=use_llm_extraction)
        
        self._memory_counter = 0
        self._load_graph()
    
    def _load_graph(self) -> None:
        """Load graph from disk if it exists."""
        graph_file = self.persist_path / "graph.json"
        if graph_file.exists():
            try:
                with open(graph_file, "r") as f:
                    data = json.load(f)
                
                # Reconstruct graph
                for node in data.get("nodes", []):
                    self.graph.add_node(node["id"], **node)
                
                for edge in data.get("edges", []):
                    self.graph.add_edge(
                        edge["source"],
                        edge["target"],
                        key=edge.get("key", 0),
                        **{k: v for k, v in edge.items() if k not in ("source", "target", "key")}
                    )
                
                self._memory_counter = data.get("counter", 0)
                logger.info(f"Loaded graph with {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
            except Exception as e:
                logger.warning(f"Failed to load graph: {e}")
    
    def _save_graph(self) -> None:
        """Persist graph to disk."""
        graph_file = self.persist_path / "graph.json"
        
        nodes = [{"id": n, **self.graph.nodes[n]} for n in self.graph.nodes]
        edges = [
            {"source": u, "target": v, "key": k, **d}
            for u, v, k, d in self.graph.edges(keys=True, data=True)
        ]
        
        with open(graph_file, "w") as f:
            json.dump({
                "nodes": nodes,
                "edges": edges,
                "counter": self._memory_counter,
            }, f, indent=2, default=str)
    
    def add_memory(
        self,
        agent_id: str,
        text: str,
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a memory to the graph.
        
        Creates a memory node and links it to:
        - The agent who has this memory
        - Extracted entities mentioned in the text
        - Other memories via shared entities
        """
        self._memory_counter += 1
        memory_id = f"memory:{agent_id}:{self._memory_counter}"
        
        # Create memory node
        self.graph.add_node(
            memory_id,
            type="memory",
            text=text,
            agent_id=agent_id,
            importance=importance,
            tags=tags or [],
            created_at=datetime.now().isoformat(),
        )
        
        # Ensure agent node exists
        agent_node_id = f"npc:{agent_id}"
        if not self.graph.has_node(agent_node_id):
            self.graph.add_node(agent_node_id, type="npc", name=agent_id)
        
        # Link memory to agent
        self.graph.add_edge(
            agent_node_id,
            memory_id,
            type="remembers",
            weight=importance,
        )
        
        # Extract and add entities
        entities, relationships = self.extractor.extract(text, context)
        
        for entity in entities:
            if not self.graph.has_node(entity.id):
                self.graph.add_node(entity.id, **entity.to_dict())
            
            # Link memory to entity
            self.graph.add_edge(
                memory_id,
                entity.id,
                type="mentions",
                weight=0.5,
            )
        
        # Add extracted relationships
        for rel in relationships:
            if self.graph.has_node(rel.source_id) and self.graph.has_node(rel.target_id):
                self.graph.add_edge(
                    rel.source_id,
                    rel.target_id,
                    type=rel.type,
                    weight=rel.weight,
                    **rel.properties,
                )
        
        self._save_graph()
        return memory_id
    
    def fetch_memories(
        self,
        agent_id: str,
        topic: str,
        limit: int = 4,
        include_global: bool = True,
        include_connections: bool = True,
    ) -> List[MemoryRecord]:
        """
        Fetch relevant memories using graph traversal.
        
        Strategy:
        1. Find entities mentioned in the topic
        2. Find memories that mention these entities
        3. Score by relevance (path length, importance, recency)
        4. Include connected memories through relationships
        """
        memories: List[MemoryRecord] = []
        seen_memory_ids: Set[str] = set()
        
        # Extract entities from topic
        topic_entities, _ = self.extractor.extract(topic)
        topic_entity_ids = {e.id for e in topic_entities}
        
        # Also check for direct text matches in entity names
        topic_lower = topic.lower()
        for node_id in self.graph.nodes:
            node_data = self.graph.nodes[node_id]
            node_name = node_data.get("name", "").lower()
            if node_name and node_name in topic_lower:
                topic_entity_ids.add(node_id)
        
        agent_node_id = f"npc:{agent_id}"
        
        # Strategy 1: Get agent's direct memories about topic entities
        if self.graph.has_node(agent_node_id):
            for _, memory_id, edge_data in self.graph.out_edges(agent_node_id, data=True):
                if edge_data.get("type") == "remembers":
                    memory_data = self.graph.nodes.get(memory_id, {})
                    if memory_data.get("type") == "memory":
                        # Check if memory mentions any topic entities
                        memory_entities = set(
                            target for _, target, d in self.graph.out_edges(memory_id, data=True)
                            if d.get("type") == "mentions"
                        )
                        
                        overlap = memory_entities & topic_entity_ids
                        if overlap or self._text_matches(memory_data.get("text", ""), topic):
                            score = self._calculate_score(
                                memory_data,
                                len(overlap),
                                path_length=1,
                            )
                            if memory_id not in seen_memory_ids:
                                seen_memory_ids.add(memory_id)
                                memories.append(MemoryRecord(
                                    text=memory_data.get("text", ""),
                                    metadata={
                                        "agent_id": agent_id,
                                        "importance": memory_data.get("importance", 0.5),
                                        "tags": ",".join(memory_data.get("tags", [])),
                                    },
                                    score=score,
                                    entities=list(memory_entities),
                                    path_context=f"Direct memory about: {', '.join(overlap)}" if overlap else "Direct memory (text match)",
                                ))
        
        # Strategy 2: Find memories through entity connections (graph traversal)
        if include_connections and topic_entity_ids:
            for entity_id in topic_entity_ids:
                if not self.graph.has_node(entity_id):
                    continue
                
                # Find all memories that mention this entity
                for source, _, edge_data in self.graph.in_edges(entity_id, data=True):
                    if edge_data.get("type") == "mentions":
                        memory_data = self.graph.nodes.get(source, {})
                        if memory_data.get("type") == "memory" and source not in seen_memory_ids:
                            mem_agent = memory_data.get("agent_id", "")
                            
                            # Include if it's this agent's memory or global
                            if mem_agent == agent_id or (include_global and mem_agent == "global"):
                                seen_memory_ids.add(source)
                                score = self._calculate_score(memory_data, 1, path_length=2)
                                memories.append(MemoryRecord(
                                    text=memory_data.get("text", ""),
                                    metadata={
                                        "agent_id": mem_agent,
                                        "importance": memory_data.get("importance", 0.5),
                                    },
                                    score=score,
                                    entities=[entity_id],
                                    path_context=f"Connected through: {entity_id}",
                                ))
        
        # Strategy 3: Include memories from agents who told this agent something
        if include_connections and self.graph.has_node(agent_node_id):
            # Find who has told this agent things
            for source, _, edge_data in self.graph.in_edges(agent_node_id, data=True):
                if edge_data.get("type") == "told":
                    # Get memories from that conversation
                    content = edge_data.get("content", "")
                    if content and self._text_matches(content, topic):
                        source_name = self.graph.nodes.get(source, {}).get("name", source)
                        # Create a synthetic memory record for the conversation
                        mem_id = f"told:{source}:{agent_node_id}"
                        if mem_id not in seen_memory_ids:
                            seen_memory_ids.add(mem_id)
                            memories.append(MemoryRecord(
                                text=f"Heard from {source_name}: {content}",
                                metadata={"source": source_name, "type": "hearsay"},
                                score=0.6,
                                entities=[source, agent_node_id],
                                path_context=f"Told by {source_name}",
                            ))
        
        # Sort by score and return top results
        memories.sort(key=lambda m: m.score, reverse=True)
        return memories[:limit]
    
    def _text_matches(self, text: str, topic: str) -> bool:
        """Check if text contains topic keywords."""
        text_lower = text.lower()
        topic_words = set(topic.lower().split())
        # Match if any significant word appears
        significant_words = {w for w in topic_words if len(w) > 3}
        return any(word in text_lower for word in significant_words)
    
    def _calculate_score(
        self,
        memory_data: Dict[str, Any],
        entity_overlap: int,
        path_length: int,
    ) -> float:
        """Calculate relevance score for a memory."""
        importance = memory_data.get("importance", 0.5)
        
        # Base score from importance
        score = importance * 0.4
        
        # Bonus for entity overlap
        score += min(entity_overlap * 0.2, 0.4)
        
        # Penalty for longer paths
        score -= (path_length - 1) * 0.1
        
        # Recency bonus (if we have timestamp)
        created_at = memory_data.get("created_at")
        if created_at:
            try:
                created = datetime.fromisoformat(created_at)
                age_hours = (datetime.now() - created).total_seconds() / 3600
                recency_bonus = max(0, 0.2 - age_hours * 0.01)
                score += recency_bonus
            except:
                pass
        
        return max(0, min(1, score))
    
    def get_entity_context(self, entity_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get context about an entity by traversing its relationships."""
        if not self.graph.has_node(entity_id):
            return {}
        
        context = {
            "entity": self.graph.nodes[entity_id],
            "relationships": [],
            "connected_entities": [],
        }
        
        # Get direct relationships
        for _, target, edge_data in self.graph.out_edges(entity_id, data=True):
            if edge_data.get("type") != "remembers":  # Skip memory links
                context["relationships"].append({
                    "type": edge_data.get("type"),
                    "target": target,
                    "target_name": self.graph.nodes.get(target, {}).get("name", target),
                })
        
        # Get entities connected within depth
        if depth > 1:
            visited = {entity_id}
            queue = [(entity_id, 0)]
            while queue:
                current, d = queue.pop(0)
                if d >= depth:
                    continue
                for _, neighbor in self.graph.out_edges(current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        neighbor_data = self.graph.nodes.get(neighbor, {})
                        if neighbor_data.get("type") != "memory":
                            context["connected_entities"].append({
                                "id": neighbor,
                                "name": neighbor_data.get("name", neighbor),
                                "type": neighbor_data.get("type"),
                                "distance": d + 1,
                            })
                        queue.append((neighbor, d + 1))
        
        return context
    
    def get_relationship_path(self, source_id: str, target_id: str) -> List[Tuple[str, str, str]]:
        """Find the shortest path between two entities."""
        if not self.graph.has_node(source_id) or not self.graph.has_node(target_id):
            return []
        
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            result = []
            for i in range(len(path) - 1):
                edge_data = self.graph.get_edge_data(path[i], path[i + 1])
                if edge_data:
                    # Get first edge if multiple
                    first_edge = list(edge_data.values())[0]
                    result.append((path[i], first_edge.get("type", "related"), path[i + 1]))
            return result
        except nx.NetworkXNoPath:
            return []
    
    def seed(self, agent_id: str, entries: List[str]) -> None:
        """Seed an agent with initial memories."""
        for text in entries:
            self.add_memory(agent_id, text, importance=0.8)
    
    def reset(self) -> None:
        """Clear all graph data."""
        self.graph.clear()
        self._memory_counter = 0
        self._save_graph()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        node_types = {}
        for node_id in self.graph.nodes:
            node_type = self.graph.nodes[node_id].get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        edge_types = {}
        for _, _, edge_data in self.graph.edges(data=True):
            edge_type = edge_data.get("type", "unknown")
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
        }


# Compatibility alias
MemoryStore = GraphMemoryStore
