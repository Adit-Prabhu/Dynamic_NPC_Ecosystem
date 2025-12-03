from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import List, Protocol

from .memory import MemoryRecord
from .personalities import PersonalityProfile
from .state import WorldState

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional dependency
    genai = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None


@dataclass(slots=True)
class DialogueResult:
    utterance: str
    rumor_delta: float
    sentiment: str
    new_memory: str


class DialogueModel(Protocol):
    def generate(
        self,
        speaker: PersonalityProfile,
        listener: PersonalityProfile,
        memories: List[MemoryRecord],
        world_state: WorldState,
        topic: str,
    ) -> DialogueResult: ...


class TemplateDialogueModel:
    """Lightweight templated narrative model used for offline demos."""

    # Voice-specific openers based on character type
    OPENERS = {
        "anxious": ["Look—", "Between you and me—", "I shouldn't say this, but—", "Don't repeat this—"],
        "grumpy": ["Hmph. ", "Typical. ", "You won't believe— actually, you will. ", "Silver says "],
        "smooth": ["Hypothetically speaking... ", "A little bird mentioned ", "If one were curious... ", "Word at the docks is "],
        "theatrical": ["Picture this, my friend: ", "Ah, a tale unfolds! ", "Dear heart, have you heard? ", "The whispers compose themselves: "],
        "scattered": ["No no no wait— ", "So here's the thing— three things actually— ", "I was just calibrating when— ", "Between explosions, I noticed "],
        "calm": ["Interesting... ", "I've been noticing ", "The symptoms suggest ", "One hears things, tending to the unwell... "],
    }
    
    REACTIONS = {
        "worried": ["and it keeps gnawing at me", "and I can't shake it", "and nobody's doing anything about it"],
        "suspicious": ["and I don't like what it implies", "and someone's covering tracks", "and the timing is too convenient"],
        "excited": ["and this changes everything", "and we could turn this to our advantage", "and imagine the possibilities"],
        "bitter": ["and of course nobody listens", "and here we are again", "and they'll blame us when it goes wrong"],
        "knowing": ["and I've seen this pattern before", "and it connects to something bigger", "and you're smart enough to see it too"],
    }

    def __init__(self, seed: int | None = None) -> None:
        self._rand = random.Random(seed)

    def _get_voice_type(self, personality: PersonalityProfile) -> str:
        name_lower = personality.name.lower()
        if "anxious" in name_lower or "guard" in name_lower:
            return "anxious"
        elif "grumpy" in name_lower or "shopkeeper" in name_lower:
            return "grumpy"
        elif "smuggler" in name_lower or "harbor" in name_lower:
            return "smooth"
        elif "bard" in name_lower or "storyweaver" in name_lower:
            return "theatrical"
        elif "artificer" in name_lower or "tinkerer" in name_lower:
            return "scattered"
        elif "herbalist" in name_lower or "apothecary" in name_lower:
            return "calm"
        return "anxious"  # default

    def generate(
        self,
        speaker: PersonalityProfile,
        listener: PersonalityProfile,
        memories: List[MemoryRecord],
        world_state: WorldState,
        topic: str,
    ) -> DialogueResult:
        memory_snippet = memories[0].text if memories else world_state.last_event
        
        voice_type = self._get_voice_type(speaker)
        opener = self._rand.choice(self.OPENERS.get(voice_type, self.OPENERS["anxious"]))
        
        # Mood affects the reaction
        mood_to_reaction = {
            "irritable": "bitter", "calculating": "knowing", "secretly thrilled": "excited",
            "suspicious": "suspicious", "sleep-deprived": "worried", "determined": "knowing",
            "paranoid": "suspicious", "grimly focused": "worried", "playful": "excited",
            "defiant": "bitter", "dangerously amused": "knowing", "melodramatic": "excited",
            "mischievous": "knowing", "wistful": "worried", "gleefully conspiratorial": "excited",
            "wired": "excited", "hopeful": "excited", "frazzled": "worried",
            "manically focused": "suspicious", "serene": "knowing", "concerned": "worried",
            "quietly furious": "bitter", "knowingly patient": "knowing",
        }
        reaction_type = mood_to_reaction.get(speaker.mood, "worried")
        reaction = self._rand.choice(self.REACTIONS[reaction_type])
        
        # Build the core of the message
        details = self._rand.choice([
            f"that business with {memory_snippet}",
            f"what happened with {memory_snippet}",
            f"the {memory_snippet.lower()} situation",
        ])
        
        topic_hint = topic or world_state.last_event
        connection = self._rand.choice([
            f"It ties back to {topic_hint}",
            f"Same pattern as {topic_hint}",
            f"Can't be coincidence with {topic_hint}",
            f"Right after {topic_hint}? Please.",
        ])
        
        mood_boost = 1.15 if speaker.mood in {"wired", "melodramatic", "defiant", "paranoid"} else 0.9 if speaker.mood in {"serene", "tired"} else 1.0
        rumor_delta = round(self._rand.uniform(0.05, 0.25) * speaker.rumor_bias * mood_boost, 2)
        rumor_delta = max(0.05, min(0.35, rumor_delta))
        
        utterance = f"{opener}{details}— {connection.lower()}, {reaction}."
        
        new_memory = (
            f"{speaker.name.split(',')[0]} ({speaker.profession}) confided while feeling {speaker.mood} "
            f"that {topic_hint} connects to {memory_snippet}."
        )
        sentiment = "urgent" if rumor_delta > 0.28 else "tense" if rumor_delta > 0.18 else "worried"
        return DialogueResult(
            utterance=utterance,
            rumor_delta=rumor_delta,
            sentiment=sentiment,
            new_memory=new_memory,
        )


class GeminiDialogueModel:
    """Gemini-powered dialogue generator that emits structured responses."""

    SYSTEM_PROMPT = """You are a master dialogue writer for a living medieval fantasy town. 
Your job is to write ONE line of naturalistic, in-character dialogue.

CRITICAL RULES:
1. Write ONLY the spoken words - no narration, no "he said", no stage directions, no asterisks
2. Each character has a distinct VOICE pattern you must capture:
   - Vocabulary choices (educated vs street slang)
   - Sentence rhythm (clipped vs flowing)  
   - Verbal tics and catchphrases
   - How they express emotion (directly vs through subtext)
3. Characters should:
   - Use contractions naturally ("don't" not "do not")
   - Trail off, interrupt themselves, use filler words when nervous
   - Reference specific sensory details (smells, sounds, textures)
   - Have opinions colored by their profession and biases
4. AVOID:
   - Generic phrases like "I heard a rumor" or "Word on the street"
   - Exposition dumps - drop hints, don't explain everything
   - Perfect grammar if the character wouldn't speak that way
   - Starting with the listener's name (people rarely do this in real speech)

The dialogue should feel like eavesdropping on a real conversation, not reading a script."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.7,
    ) -> None:
        if genai is None:  # pragma: no cover - import error makes test noisy
            raise ImportError("google-generativeai package is not installed")
        if not api_key:
            raise ValueError("Gemini API key is required")
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": temperature,
                "response_mime_type": "application/json",
            },
            system_instruction=self.SYSTEM_PROMPT,
        )

    def generate(
        self,
        speaker: PersonalityProfile,
        listener: PersonalityProfile,
        memories: List[MemoryRecord],
        world_state: WorldState,
        topic: str,
    ) -> DialogueResult:
        memory_lines = "\n".join(f"- {record.text}" for record in memories) or "- No prior memories"
        
        # Build a richer character context
        speaker_context = (
            f"{speaker.name} - {speaker.profession}\n"
            f"Voice: {speaker.voice}\n"
            f"Current mood: {speaker.mood}\n"
            f"What drives them: {', '.join(speaker.motivations)}\n"
            f"Quirks/habits: {', '.join(speaker.quirks)}\n"
            f"Usually talks about: {', '.join(speaker.default_topics)}"
        )
        
        listener_context = (
            f"{listener.name} - {listener.profession}\n"
            f"Voice: {listener.voice}\n"
            f"Current mood: {listener.mood}\n"
            f"What drives them: {', '.join(listener.motivations)}"
        )
        
        world_snapshot = world_state.snapshot()
        tension_level = "high" if world_snapshot.get("rumor_heat", 0) > 0.6 else "moderate" if world_snapshot.get("rumor_heat", 0) > 0.3 else "low"
        
        # Get recent conversation flow
        recent_beats = world_state.get_recent_beats(limit=4)
        conversation_flow = ""
        if recent_beats:
            conversation_flow = "\n\nRECENT CONVERSATION (respond to this, don't repeat it):\n"
            for i, beat in enumerate(recent_beats, 1):
                conversation_flow += f"{i}. \"{beat}\"\n"
            conversation_flow += "\nIMPORTANT: Build on what was just said. React, add new information, challenge it, or take it in a new direction. Do NOT repeat the same ideas."
        
        prompt = f"""SCENE CONTEXT:
Town tension level: {tension_level}
The inciting incident: {world_snapshot.get("last_event", topic)}
What they're currently discussing: {topic}
{conversation_flow}

SPEAKER (the one talking now):
{speaker_context}

LISTENER (who they're talking to):
{listener_context}

WHAT THE SPEAKER REMEMBERS:
{memory_lines}

TASK:
Write what {speaker.name.split(',')[0]} says to {listener.name.split(',')[0]} RIGHT NOW in this ongoing conversation.

CRITICAL: This is a back-and-forth conversation. You must:
1. RESPOND to what was just said (agree, disagree, add to it, question it)
2. Add NEW information, theories, or personal observations
3. Move the conversation FORWARD - don't just echo the same points
4. Let your character's unique perspective shine through

Their {speaker.mood} mood should color HOW they say it.
Their profession ({speaker.profession}) colors WHAT details they notice.
Their quirks should occasionally peek through.

Return JSON with:
- "utterance": The actual spoken dialogue (1-3 sentences, no narration, MUST advance the conversation)
- "rumor_delta": How much this spreads/intensifies the rumor (0.05 = idle chat, 0.35 = explosive revelation)
- "sentiment": The emotional undertone ("curious", "worried", "conspiratorial", "dismissive", "excited", "bitter", "knowing", "anxious", "defiant")
- "new_memory": A brief note about the NEW information or theory shared (not a repeat)"""

        response = self._model.generate_content(prompt)
        content = getattr(response, "text", None) or response.candidates[0].content.parts[0].text  # type: ignore[index]
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = {
                "utterance": f"{speaker.name} confides in {listener.name}: {topic}",
                "rumor_delta": 0.15,
                "sentiment": "worried",
                "new_memory": f"Discussed {topic}",
            }
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        rumor_delta = float(payload.get("rumor_delta", 0.15))
        return DialogueResult(
            utterance=str(payload.get("utterance", "")),
            rumor_delta=max(0.05, min(0.35, rumor_delta)),
            sentiment=str(payload.get("sentiment", "worried")),
            new_memory=str(payload.get("new_memory", topic)),
        )


class OpenRouterDialogueModel:
    """OpenRouter-powered dialogue generator using OpenAI-compatible API."""

    SYSTEM_PROMPT = """You are a master dialogue writer for a living medieval fantasy town. 
Your job is to write ONE line of naturalistic, in-character dialogue.

CRITICAL RULES:
1. Write ONLY the spoken words - no narration, no "he said", no stage directions, no asterisks
2. Each character has a distinct VOICE pattern you must capture:
   - Vocabulary choices (educated vs street slang)
   - Sentence rhythm (clipped vs flowing)  
   - Verbal tics and catchphrases
   - How they express emotion (directly vs through subtext)
3. Characters should:
   - Use contractions naturally ("don't" not "do not")
   - Trail off, interrupt themselves, use filler words when nervous
   - Reference specific sensory details (smells, sounds, textures)
   - Have opinions colored by their profession and biases
4. AVOID:
   - Generic phrases like "I heard a rumor" or "Word on the street"
   - Exposition dumps - drop hints, don't explain everything
   - Perfect grammar if the character wouldn't speak that way
   - Starting with the listener's name (people rarely do this in real speech)

The dialogue should feel like eavesdropping on a real conversation, not reading a script.

IMPORTANT: Always respond with valid JSON only, no markdown formatting."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "google/gemini-2.0-flash-exp:free",
        temperature: float = 0.7,
        site_url: str = "http://localhost:8000",
        site_name: str = "Dynamic NPC Ecosystem",
    ) -> None:
        if OpenAI is None:
            raise ImportError("openai package is not installed")
        if not api_key:
            raise ValueError("OpenRouter API key is required")
        
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self._model_name = model_name
        self._temperature = temperature
        self._extra_headers = {
            "HTTP-Referer": site_url,
            "X-Title": site_name,
        }
        self._fallback_openers = [
            "Look, about {topic}—",
            "Hmph. {topic}, you say?",
            "Between you and me... {topic} has me thinking.",
            "*leans in* That {topic} situation...",
            "You heard about {topic}? Well...",
        ]
    
    def _generate_fallback_line(self, speaker: PersonalityProfile, listener: PersonalityProfile, topic: str) -> str:
        """Generate a simple fallback line when API fails."""
        import random
        opener = random.choice(self._fallback_openers).format(topic=topic)
        reactions = [
            "Something's not right.",
            "I've got a bad feeling about this.",
            "Mark my words, there's more to it.",
            "The town's buzzing, and not in a good way.",
            "Keep your eyes open.",
        ]
        return f"{opener} {random.choice(reactions)}"

    def generate(
        self,
        speaker: PersonalityProfile,
        listener: PersonalityProfile,
        memories: List[MemoryRecord],
        world_state: WorldState,
        topic: str,
    ) -> DialogueResult:
        memory_lines = "\n".join(f"- {record.text}" for record in memories) or "- No prior memories"
        
        speaker_context = (
            f"{speaker.name} - {speaker.profession}\n"
            f"Voice: {speaker.voice}\n"
            f"Current mood: {speaker.mood}\n"
            f"What drives them: {', '.join(speaker.motivations)}\n"
            f"Quirks/habits: {', '.join(speaker.quirks)}\n"
            f"Usually talks about: {', '.join(speaker.default_topics)}"
        )
        
        listener_context = (
            f"{listener.name} - {listener.profession}\n"
            f"Voice: {listener.voice}\n"
            f"Current mood: {listener.mood}\n"
            f"What drives them: {', '.join(listener.motivations)}"
        )
        
        world_snapshot = world_state.snapshot()
        tension_level = "high" if world_snapshot.get("rumor_heat", 0) > 0.6 else "moderate" if world_snapshot.get("rumor_heat", 0) > 0.3 else "low"
        
        recent_beats = world_state.get_recent_beats(limit=4)
        conversation_flow = ""
        if recent_beats:
            conversation_flow = "\n\nRECENT CONVERSATION (respond to this, don't repeat it):\n"
            for i, beat in enumerate(recent_beats, 1):
                conversation_flow += f"{i}. \"{beat}\"\n"
            conversation_flow += "\nIMPORTANT: Build on what was just said. React, add new information, challenge it, or take it in a new direction. Do NOT repeat the same ideas."
        
        user_prompt = f"""SCENE CONTEXT:
Town tension level: {tension_level}
The inciting incident: {world_snapshot.get("last_event", topic)}
What they're currently discussing: {topic}
{conversation_flow}

SPEAKER (the one talking now):
{speaker_context}

LISTENER (who they're talking to):
{listener_context}

WHAT THE SPEAKER REMEMBERS:
{memory_lines}

TASK:
Write what {speaker.name.split(',')[0]} says to {listener.name.split(',')[0]} RIGHT NOW in this ongoing conversation.

CRITICAL: This is a back-and-forth conversation. You must:
1. RESPOND to what was just said (agree, disagree, add to it, question it)
2. Add NEW information, theories, or personal observations
3. Move the conversation FORWARD - don't just echo the same points
4. Let your character's unique perspective shine through

Their {speaker.mood} mood should color HOW they say it.
Their profession ({speaker.profession}) colors WHAT details they notice.
Their quirks should occasionally peek through.

Return JSON with these exact keys:
{{"utterance": "the dialogue", "rumor_delta": 0.15, "sentiment": "worried", "new_memory": "what was shared"}}

- "utterance": The actual spoken dialogue (1-3 sentences, no narration, MUST advance the conversation)
- "rumor_delta": How much this spreads/intensifies the rumor (0.05 = idle chat, 0.35 = explosive revelation)
- "sentiment": The emotional undertone ("curious", "worried", "conspiratorial", "dismissive", "excited", "bitter", "knowing", "anxious", "defiant")
- "new_memory": A brief note about the NEW information or theory shared"""

        # Use the original incident for fallbacks, not the evolving topic
        original_incident = world_snapshot.get("last_event", "strange happenings")
        
        try:
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self._temperature,
                extra_headers=self._extra_headers,
            )
            content = response.choices[0].message.content or ""
            # Strip markdown code blocks if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content
                if content.endswith("```"):
                    content = content.rsplit("```", 1)[0]
                content = content.strip()
            payload = json.loads(content)
        except json.JSONDecodeError as e:
            import logging
            logging.getLogger(__name__).warning(f"OpenRouter JSON parse error: {e}. Raw content: {content[:200] if 'content' in dir() else 'N/A'}")
            payload = None
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"OpenRouter API error: {type(e).__name__}: {e}")
            payload = None
        
        # Fallback with original incident to avoid nesting
        if not payload:
            payload = {
                "utterance": self._generate_fallback_line(speaker, listener, original_incident),
                "rumor_delta": 0.15,
                "sentiment": "worried",
                "new_memory": f"Mentioned {original_incident}",
            }
        
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        
        rumor_delta = float(payload.get("rumor_delta", 0.15))
        return DialogueResult(
            utterance=str(payload.get("utterance", "")),
            rumor_delta=max(0.05, min(0.35, rumor_delta)),
            sentiment=str(payload.get("sentiment", "worried")),
            new_memory=str(payload.get("new_memory", topic)),
        )
