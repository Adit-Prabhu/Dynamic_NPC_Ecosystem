from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from npc.llm import GeminiDialogueModel, OpenRouterDialogueModel, TemplateDialogueModel
from npc.orchestrator import Orchestrator
from npc.personalities import list_personality_keys, sample_personality_keys

from .schemas import (
    DialogueTurnModel, 
    ResetRequest, 
    RunRequest, 
    RunResponse,
    InjectSecretRequest,
    InjectSecretResponse,
    PropagationStatsResponse,
    ExperimentRequest,
    ExperimentResponse,
)

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_RUMOR_SEEDS = [
    "Vault door left ajar last night.",
    "Supply caravan spotted smoke near the marsh.",
    "Guard captain seen bribing the tax clerk.",
    "Somebody swapped the shop ledgers with counterfeits.",
    "A wyvern shadow skimmed over the market at dawn.",
]

app = FastAPI(title="Dynamic NPC Ecosystem", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def pick_personality_keys() -> list[str]:
    roster = list_personality_keys()
    env_pool = os.getenv("NPC_PERSONA_POOL", "").strip()
    if env_pool:
        requested = [key.strip() for key in env_pool.split("|") if key.strip()]
        pool = [key for key in requested if key in roster]
        if not pool:
            logger.warning("NPC_PERSONA_POOL had no valid personas; using full roster")
            pool = roster
    else:
        pool = roster
    if len(pool) < 2:
        logger.warning("Need at least two personas; reverting to default roster")
        pool = roster
    desired = os.getenv("NPC_PARTY_SIZE", "2").strip()
    try:
        desired_size = int(desired)
    except ValueError:
        logger.warning("NPC_PARTY_SIZE='%s' invalid; defaulting to 2", desired)
        desired_size = 2
    desired_size = max(2, desired_size)
    desired_size = min(desired_size, len(pool))
    return sample_personality_keys(desired_size, allowed_keys=pool)
def pick_seed(event: str | None = None) -> str:
    if event:
        return event
    env_seeds = os.getenv("NPC_RUMOR_SEEDS", "").strip()
    if env_seeds:
        candidates = [seed.strip() for seed in env_seeds.split("|") if seed.strip()]
    else:
        candidates = DEFAULT_RUMOR_SEEDS
    return random.choice(candidates)


def build_orchestrator(seed_event: str | None = None) -> Orchestrator:
    provider = (os.getenv("NPC_MODEL_PROVIDER") or "template").lower()
    
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        model_name = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
        temperature = float(os.getenv("OPENROUTER_TEMPERATURE", "0.7"))
        if not api_key:
            logger.warning("OPENROUTER_API_KEY missing; falling back to template dialogue model")
            model = TemplateDialogueModel()
        else:
            model = OpenRouterDialogueModel(api_key=api_key, model_name=model_name, temperature=temperature)
            logger.info("Using OpenRouter dialogue model %s", model_name)
    elif provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
        if not api_key:
            logger.warning("GEMINI_API_KEY missing; falling back to template dialogue model")
            model = TemplateDialogueModel()
        else:
            model = GeminiDialogueModel(api_key=api_key, model_name=model_name, temperature=temperature)
            logger.info("Using Gemini dialogue model %s", model_name)
    else:
        model = TemplateDialogueModel()
    hook = pick_seed(seed_event)
    party = pick_personality_keys()
    logger.info("Initializing orchestrator with rumor seed '%s' and roster %s", hook, party)
    return Orchestrator(model=model, rumor_hook=hook, personalities=party)


orchestrator = build_orchestrator()


def get_dialogue_delay() -> float:
    """Get the delay between dialogue exchanges in seconds."""
    try:
        return float(os.getenv("NPC_DIALOGUE_DELAY", "5"))
    except ValueError:
        return 5.0


def reset_orchestrator(event: str | None = None) -> None:
    global orchestrator
    orchestrator = build_orchestrator(seed_event=event)


@app.get("/api/state" )
async def get_state() -> Dict[str, Any]:
    return orchestrator.snapshot()


@app.post("/api/run", response_model=RunResponse)
async def run_steps(request: RunRequest) -> RunResponse:
    history = orchestrator.run_steps(request.steps)
    snapshot = orchestrator.snapshot()
    return RunResponse(
        history=[DialogueTurnModel(**turn) for turn in history],
        world_state=snapshot["world_state"],
    )


@app.post("/api/reset")
async def reset_state(request: ResetRequest) -> Dict[str, Any]:
    reset_orchestrator(request.event)
    return orchestrator.snapshot()


@app.websocket("/ws/dialogue")
async def dialogue_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    delay = get_dialogue_delay()
    logger.info(f"Starting dialogue feed with {delay}s delay between exchanges")
    try:
        while True:
            turn = orchestrator.step()
            payload = {
                "turn": DialogueTurnModel(**turn.as_dict()).model_dump(),
                "world_state": orchestrator.world_state.snapshot(),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(delay)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


@app.get("/api/config")
async def get_config() -> Dict[str, Any]:
    """Get current configuration values."""
    return {
        "dialogue_delay": get_dialogue_delay(),
        "model_provider": os.getenv("NPC_MODEL_PROVIDER", "template"),
        "model_name": os.getenv("OPENROUTER_MODEL") or os.getenv("GEMINI_MODEL", "template"),
    }


@app.get("/api/graph")
async def get_graph_stats() -> Dict[str, Any]:
    """Get knowledge graph statistics."""
    return orchestrator.memory_store.get_stats()


@app.get("/api/graph/entity/{entity_type}/{entity_name}")
async def get_entity_context(entity_type: str, entity_name: str) -> Dict[str, Any]:
    """Get context about a specific entity in the knowledge graph."""
    entity_id = f"{entity_type}:{entity_name.lower()}"
    context = orchestrator.memory_store.get_entity_context(entity_id, depth=2)
    if not context:
        return {"error": f"Entity {entity_id} not found"}
    return context


@app.get("/health")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


# =========== Propagation Experiment Endpoints ===========

@app.post("/api/experiment/inject", response_model=InjectSecretResponse)
async def inject_secret(request: InjectSecretRequest) -> InjectSecretResponse:
    """
    Inject a secret into an NPC and begin tracking its propagation.
    The secret will spread through the NPC network as they gossip.
    """
    # Get list of available NPCs
    available_npcs = [a.agent_id for a in orchestrator.agents]
    source = request.source_npc or available_npcs[0]
    
    if source not in available_npcs:
        return InjectSecretResponse(
            success=False,
            message=f"NPC '{source}' not found. Available: {available_npcs}",
            source_npc=source,
            secret=request.secret
        )
    
    exp_id = orchestrator.inject_secret(request.secret, source)
    return InjectSecretResponse(
        success=exp_id is not None,
        message=f"Secret injected into {source} (experiment: {exp_id})" if exp_id else "Failed to inject secret",
        source_npc=source,
        secret=request.secret
    )


@app.get("/api/experiment/stats")
async def get_propagation_stats() -> Dict[str, Any]:
    """
    Get current propagation statistics for all active experiments.
    Tracks spread rate, mutation count, and NPC exposure by personality type.
    """
    stats = orchestrator.get_propagation_stats()
    if not stats:
        return {
            "active": False,
            "message": "No active propagation experiment. Use /api/experiment/inject first."
        }
    
    return {
        "active": True,
        "message": "Propagation tracking active",
        **stats
    }


@app.get("/api/experiment/timeline")
async def get_propagation_timeline() -> Dict[str, Any]:
    """
    Get the full timeline of propagation events from all experiments.
    Shows who told whom, and how the message mutated.
    """
    experiments = orchestrator.get_propagation_timeline()
    return {
        "experiments": experiments,
        "total_experiments": len(experiments)
    }


@app.get("/api/experiment/report")
async def get_propagation_report() -> Dict[str, str]:
    """
    Generate a markdown report of all propagation experiments.
    Includes personality-based analysis and key findings.
    """
    report = orchestrator.get_propagation_report()
    return {"report": report}


@app.post("/api/experiment/step", response_model=RunResponse)
async def experiment_step(request: RunRequest) -> RunResponse:
    """
    Run dialogue steps with propagation tracking enabled.
    Use this instead of /api/run when conducting experiments.
    """
    history = []
    for _ in range(max(1, request.steps)):
        turn = orchestrator.step_with_tracking()
        history.append(turn.as_dict())
    
    snapshot = orchestrator.snapshot()
    return RunResponse(
        history=[DialogueTurnModel(**turn) for turn in history],
        world_state=snapshot["world_state"],
    )


@app.post("/api/experiment/run")
async def run_full_experiment(request: ExperimentRequest) -> Dict[str, Any]:
    """
    Run a complete propagation experiment with the specified parameters.
    Injects a secret into the first NPC and runs multiple dialogue rounds.
    Returns comprehensive statistics about how the information spread.
    """
    # Reset the orchestrator with a fresh state
    reset_orchestrator()
    
    # Get available NPCs
    available_npcs = [a.agent_id for a in orchestrator.agents]
    
    # Inject the secret
    secret = request.secret or "The mayor has been secretly meeting with the rebel faction."
    exp_id = orchestrator.inject_secret(secret, available_npcs[0])
    
    if not exp_id:
        return {
            "success": False,
            "error": "Failed to inject secret"
        }
    
    # Run dialogue rounds with tracking
    rounds = request.rounds or 10
    history = []
    for _ in range(rounds):
        turn = orchestrator.step_with_tracking()
        history.append(turn.as_dict())
    
    # Get final statistics
    stats = orchestrator.get_propagation_stats()
    timeline = orchestrator.get_propagation_timeline()
    report = orchestrator.get_propagation_report()
    
    return {
        "success": True,
        "experiment_id": exp_id,
        "secret": secret,
        "rounds": rounds,
        "history_sample": history[:5],  # First 5 turns
        "stats": stats,
        "experiments": timeline,
        "report": report
    }
