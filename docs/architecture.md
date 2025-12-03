# Dynamic NPC Ecosystem

## Vision
Create a living NPC ecosystem where agents continue to evolve even without direct player prompts. NPCs converse with each other, recall shared experiences, and their gossip can mutate the global game state.

## High-Level Components
1. **Multi-Agent Orchestrator (System Architect)**  
   - Python service orchestrating asynchronous conversations between NPCs.  
   - Event-driven scheduler chooses speaking order, topics, and tracks world-state mutations.
2. **Memory Layer (Memory Engineer)**  
   - Vector database (Chroma) storing semantic memories tagged per NPC + global ledger.  
   - Retrieval augmented context for dialogue generation and rumor propagation.
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
                         └─ Memory Layer (Chroma) ⇄ Embedding Service
```

## Demo Scenario
- Seed agents with shared event: "Vault door left ajar last night."  
- Run autonomous loop: a sampled pair (e.g., shopkeeper ↔ guard, smuggler ↔ bard) trade barbs, mutate rumor heat, and update the UI telemetry in real time.  
- Player can remain idle and watch gossip cascade.

## Tech Stack
- **Backend:** Python 3.11, FastAPI, LangChain (prompting + memory abstraction), ChromaDB, sentence-transformers, WebSocket for live feed.  
- **Frontend:** Vite + React + TypeScript, TailwindCSS for quick styling.  
- **Tooling:** Poetry/venv (local), pytest for regression, ESLint/Prettier.

## Key Modules
| Module | Responsibility |
| --- | --- |
| `backend/app/main.py` | API + WebSocket endpoints |
| `backend/npc/agents.py` | Agent definitions, orchestrator loop |
| `backend/npc/memory.py` | Chroma interface, embedding helpers |
| `backend/npc/personality.py` | Persona configs, prompt assembly |
| `backend/tests/` | Unit & integration tests |
| `frontend/` | Visualization client |

## Rumor Mechanics Walkthrough
1. Orchestrator picks speaker + listener pair based on pending rumors.  
2. Memory fetch: retrieve top-k memories from both agents + global ledger.  
3. Prompt LLM with: persona description + recent dialogue + retrieved memories.  
4. LLM response parsed into: utterance, rumor_strength delta, new memory embeddings.  
5. Update world-state (e.g., `settlement_alert_level`) and broadcast over WebSocket.  
6. Frontend timeline animates conversation + highlight state change.

## Testing Strategy
- Mock LLM completions (YAML transcripts) for deterministic tests.  
- Unit tests for memory read/write, orchestrator scheduling, rumor state transitions.  
- Frontend component tests (Vitest) for log rendering + rumor meter.
