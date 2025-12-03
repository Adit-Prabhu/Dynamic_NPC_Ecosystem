# 🎭 Dynamic NPC Ecosystem

A demo sandbox where autonomous NPCs gossip, scheme, and spread rumors without player intervention. Each character has a distinct personality, voice, and memory—powered by LLMs and vector search.

![Python](https://img.shields.io/badge/python-3.12-blue) ![React](https://img.shields.io/badge/react-18-61dafb) ![FastAPI](https://img.shields.io/badge/fastapi-0.115-009688)

## ✨ Features

- **Autonomous Conversations** – NPCs talk to each other based on personality, mood, and shared memories
- **Persistent Memory** – Vector database (ChromaDB) stores what each NPC knows and heard
- **Evolving World State** – Rumors spread, guard alerts rise, shop prices fluctuate
- **Distinctive Voices** – Each character has unique speech patterns, quirks, and motivations
- **Real-time Dashboard** – Watch the gossip unfold with live telemetry

## 🏗️ Architecture

| Path | Purpose |
|------|---------|
| `backend/` | FastAPI service with multi-agent orchestrator, memory layer, and WebSocket stream |
| `frontend/` | Vite + React dashboard visualizing the gossip timeline and world telemetry |
| `docs/` | Architecture documentation and design notes |

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20.19+ or 22.12+
- An LLM API key (Gemini or OpenRouter)

### Backend Setup

```bash
cd backend
python -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the server
python -m uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 to see the dashboard.

## ⚙️ Configuration

Create a `.env` file in `backend/` with:

```bash
# Model Provider: "gemini", "openrouter", or "template"
NPC_MODEL_PROVIDER=gemini

# Delay between dialogue exchanges (seconds)
# Free tier APIs: use 5+ to avoid rate limits
NPC_DIALOGUE_DELAY=5

# === GEMINI (recommended) ===
GEMINI_API_KEY=your-api-key
GEMINI_MODEL=gemini-2.0-flash-lite
GEMINI_TEMPERATURE=0.7

# === OPENROUTER (alternative) ===
# Get free key at: https://openrouter.ai/keys
OPENROUTER_API_KEY=your-api-key
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
OPENROUTER_TEMPERATURE=0.7

# === RUMOR SEEDS (pipe-delimited) ===
NPC_RUMOR_SEEDS="Vault door left ajar|Smuggler spotted in the sewers|Temple bells rang at midnight"

# === OPTIONAL: Control NPC roster ===
# NPC_PERSONA_POOL="shopkeeper|guard|smuggler|bard|artificer|herbalist"
# NPC_PARTY_SIZE=2
```

## 🎮 Usage

1. **Start the backend** – `cd backend && python -m uvicorn app.main:app --reload`
2. **Start the frontend** – `cd frontend && npm run dev`
3. **Watch the magic** – Click "Autoplay Gossip" to see NPCs chat autonomously
4. **Manual control** – Use "Single Exchange" to step through one conversation at a time

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Current world state and conversation history |
| `/api/run` | POST | Trigger N dialogue exchanges |
| `/api/reset` | POST | Reset with new NPCs and rumor seed |
| `/api/config` | GET | Current configuration |
| `/ws/dialogue` | WS | Real-time dialogue stream |

## 🎭 The Cast

| Character | Role | Voice |
|-----------|------|-------|
| **Mara** | Grumpy Shopkeeper | Clipped, sarcastic, talks about silver and taxes |
| **Rylan** | Anxious Guard | Hushed, urgent, always checking over his shoulder |
| **Iris** | Harbor Smuggler | Smooth, coy, speaks in implications |
| **Theron** | Itinerant Bard | Theatrical, quotes ballads, dramatic pauses |
| **Kel** | Exhausted Artificer | Rapid-fire, scattered, caffeine-fueled tangents |
| **Suna** | Listening Herbalist | Soft, uses plant metaphors for people |

## 🧪 Testing

```bash
cd backend
python -m pytest
```

## 📝 License

MIT

---

*Watch the townsfolk gossip without lifting a finger—each reset assembles a fresh duo with new secrets to share.*
