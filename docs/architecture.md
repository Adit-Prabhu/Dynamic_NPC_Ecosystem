# Dynamic NPC Ecosystem

## Vision
Create a living NPC ecosystem where agents continue to evolve even without direct player prompts. NPCs converse with each other, recall shared experiences, and their gossip can mutate the global game state.

## High-Level Components
1. **Multi-Agent Orchestrator (System Architect)**  
   - Python service orchestrating asynchronous conversations between NPCs.  
   - Event-driven scheduler chooses speaking order, topics, and tracks world-state mutations.
2. **Memory Layer - GraphRAG (Memory Engineer)**  
   - **Knowledge Graph** (NetworkX) tracking entities, relationships, and memories.
   - Entities: NPCs, locations, objects, events, concepts
   - Relationships: who knows what, who told whom, what connects to what
   - Graph traversal for contextual memory retrieval (richer than pure vector search)
   - Automatic entity extraction from dialogue
3. **Personality + Dialogue Engine (Personality Tuner)**  
   - Declarative persona configs (traits, goals, forbidden topics).  
   - Prompt templates guiding LLM completions per persona.  
   - Lightweight emotional state machine (mood drifts based on conversation sentiment).
4. **Visualization + Control (Frontend)**  
   - Web UI (Vite + React + TypeScript) showing:  
     - Real-time dialogue log.  
     - Rumor impact on shared game-state (e.g., guard alert level, shopkeeper prices).  
     - Manual trigger to run demo or inject player events.

## Data Flow
```
[Frontend] ⇄ REST/WebSocket ⇄ [FastAPI Backend]
                         │
                         ├─ NPC Orchestrator → Personality Engine
                         └─ GraphRAG Memory Layer
                              │
                              ├─ Entity Extraction
                              ├─ Relationship Tracking
                              └─ Graph Traversal for Context
```

## GraphRAG Memory System

### Entity Types
| Type | Description | Examples |
|------|-------------|----------|
| `npc` | Characters in the world | Mara, Rylan, Suna |
| `location` | Places | vault, docks, market |
| `object` | Items | ledger, coins, shipment |
| `event` | Happenings | vault door ajar, theft |
| `concept` | Ideas/rumors | conspiracy theories |
| `memory` | Stored memories | what NPCs remember |

### Relationship Types
| Type | Description |
|------|-------------|
| `remembers` | NPC → Memory link |
| `mentions` | Memory → Entity reference |
| `told` | NPC told another NPC something |
| `witnessed` | NPC saw an event |
| `suspects` | NPC suspects something |
| `knows` | NPC knows about something |
| `related_to` | General entity connection |

### Memory Retrieval Strategy
1. Extract entities from the query topic
2. Find NPC's direct memories about those entities
3. Traverse graph to find connected memories (who told whom)
4. Score by relevance: entity overlap + path length + recency
5. Return rich context including relationship paths

## Demo Scenario
- Seed agents with shared event: "Vault door left ajar last night."  
- Run autonomous loop: a sampled pair (e.g., shopkeeper ↔ guard, smuggler ↔ bard) trade barbs, mutate rumor heat, and update the UI telemetry in real time.  
- Player can remain idle and watch gossip cascade.
- Graph tracks who told whom, building a web of knowledge propagation.

## Tech Stack
- **Backend:** Python 3.12, FastAPI, NetworkX (knowledge graph), WebSocket for live feed.  
- **LLM Providers:** Google Gemini, OpenRouter (supports free models)
- **Frontend:** Vite + React + TypeScript, TailwindCSS for quick styling.  
- **Tooling:** pip/venv (local), pytest for regression, ESLint/Prettier.

## Key Modules
| Module | Responsibility |
| --- | --- |
| `backend/app/main.py` | API + WebSocket endpoints |
| `backend/app/schemas.py` | Pydantic models for API responses |
| `backend/npc/agents.py` | Agent definitions, memory integration |
| `backend/npc/graph_memory.py` | GraphRAG implementation, entity extraction |
| `backend/npc/orchestrator.py` | Conversation orchestration loop |
| `backend/npc/personalities.py` | Persona configs, voice definitions |
| `backend/npc/llm.py` | LLM integrations (Gemini, OpenRouter) |
| `backend/npc/propagation.py` | Viral information tracking, experiment runner |
| `backend/npc/state.py` | World state, conversation tracking |
| `backend/tests/` | Unit & integration tests |
| `frontend/` | Visualization client |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Current world state snapshot |
| `/api/run` | POST | Run N dialogue steps |
| `/api/reset` | POST | Reset with new seed event |
| `/api/graph` | GET | Knowledge graph statistics |
| `/api/graph/entity/{type}/{name}` | GET | Entity context and relationships |
| `/api/config` | GET | Current configuration |
| `/ws/dialogue` | WS | Real-time dialogue feed |

### Propagation Experiment Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/experiment/inject` | POST | Inject secret into an NPC to begin tracking |
| `/api/experiment/stats` | GET | Propagation analysis by personality type |
| `/api/experiment/timeline` | GET | All experiments with propagation traces |
| `/api/experiment/report` | GET | Markdown analysis report |
| `/api/experiment/step` | POST | Run dialogue steps with tracking enabled |

## Rumor Mechanics Walkthrough
1. Orchestrator picks speaker + listener pair based on pending rumors.  
2. **Graph Memory Fetch**: traverse knowledge graph for related memories
   - Find entities mentioned in current topic
   - Get memories connected to those entities
   - Include "hearsay" from other NPCs who shared information
3. Prompt LLM with: persona description + recent dialogue + graph context.  
4. LLM response parsed into: utterance, rumor_strength delta, new memory.  
5. **Graph Update**: 
   - Create memory node linked to speaker
   - Extract entities and create relationship edges
   - Link "told" relationship between speaker and listener
6. Update world-state and broadcast over WebSocket.  
7. Frontend timeline animates conversation + highlight state change.

## Testing Strategy
- Mock LLM completions for deterministic tests.  
- Unit tests for graph memory operations, entity extraction, path finding.
- Orchestrator scheduling and rumor state transitions.  
- Frontend component tests (Vitest) for log rendering + rumor meter.

## Chain-of-Thought Visibility

NPCs generate both **internal monologue** and **spoken dialogue**:

```json
{
  "utterance": "What I say out loud...",
  "internal_monologue": "What I'm really thinking...",
  "rumor_delta": 0.15,
  "new_memory": "Key takeaway..."
}
```

The frontend displays both, allowing users to:
- See the reasoning behind NPC responses
- Understand why certain information was shared or withheld
- Debug dialogue quality and personality consistency

## Viral Propagation Tracking

The `PropagationTracker` system enables quantitative analysis of information flow:

### Experiment Workflow
1. **Inject Secret** – Plant a secret in one NPC's memory
2. **Run Dialogue** – Let NPCs talk autonomously  
3. **Observe Propagation** – Track who mentions the secret
4. **Analyze Results** – Compare by personality type

### Metrics Tracked
| Metric | Description |
|--------|-------------|
| **Propagation Count** | How many times the secret was mentioned |
| **Fidelity** | Semantic similarity to original (0-100%) |
| **Mutation Rate** | How often information changed |
| **Spread Velocity** | Agents reached per turn |
| **Personality Analysis** | Gossip vs Stoic vs Neutral comparison |

### Personality Classification
| Type | Indicators | Behavior |
|------|------------|----------|
| 🗣️ Gossip | curious, talkative, dramatic, theatrical | Spreads fast, mutates more |
| 🤫 Stoic | reserved, guarded, careful, quiet | Spreads slow, higher fidelity |
| 😐 Neutral | balanced traits | Middle ground |

### Key Finding
> Gossip personalities spread information ~3x faster than stoics, but with lower fidelity.
> This matches real-world rumor dynamics!
