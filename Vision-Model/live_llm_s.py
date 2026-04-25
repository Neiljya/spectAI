import asyncio
import json
import os
import re
import logging
import dotenv
from dataclasses import asdict
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from typing import Literal
from stream import WindowCapture
from valorant_local_api import ValorantLocalClient, GamePhase
from valorant_resolver import ValorantResolver

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'coaching_system'))
from uagents import Agent, Context as AgentContext
from shared.models import AnalysisRequest
from shared.player_store import PLAYER_PROFILES

log = logging.getLogger(__name__)

# --- uAgent setup ---
ORCHESTRATOR_ADDRESS = "agent1qv3vml6d7av788k4yyhwrwssmj4tsct7z9nw8eyva9h6jc29quka5wmh6am"

_vision_agent = Agent(
    name="vision_collector",
    seed="spectai_vision_collector_2026",
    port=8010,
    endpoint=["http://127.0.0.1:8010/submit"],
    mailbox=True,
)
_agent_ctx: AgentContext | None = None

def _parse_time(t: str) -> float | None:
    if not t or t == "unknown":
        return None
    try:
        m, s = t.split(":") if ":" in t else (0, t)
        return float(m) * 60 + float(s)
    except Exception:
        return None

@_vision_agent.on_event("startup")
async def on_start(ctx: AgentContext):
    global _agent_ctx
    _agent_ctx = ctx
    ctx.logger.info(f"Vision collector running at: {_vision_agent.address}")
    asyncio.create_task(run_spect_ai())

# --- Config ---
dotenv.load_dotenv()
TARGET_WINDOW = "VALORANT  "
CAPTURE_FPS = 2
COOLDOWN_SECONDS = 8
GAME_STATE_REFRESH_SECONDS = 10  # How often to re-poll the Valorant API
MAX_HISTORY = 10  # Number of past states to keep in the buffer
MODEL = "gemini-3.1-flash-live-preview"

SYSTEM_PROMPT = """You are SpectAI, the vision layer of a real-time competitive FPS coaching system (Valorant).
You analyze game frames and extract structured information for specialist coaching agents.
You are a precise observer, not a coach. Extract what you see accurately.
Use information from the HUD, like health, ammo, top bar (for agent icons, ult status, time, scores), killfeed, and minimap.
IMPORTANT: To identify the player's agent (character), look at the top bar icon or the center of the minimap.
You will sometimes receive a RECENT HISTORY buffer of previous game states. Use it to infer what changed over time. Note that previous states may be inaccurate, so prioritize the current frame over history.
You may also receive LIVE GAME DATA from the Valorant API. This gives you ground-truth about the map, agents, and teams. Use it to fill in map_name, player_character, and team compositions accurately instead of guessing from vision alone. Use the provided callout names when describing player_position.

OUTPUT RULES — follow these exactly:
- Respond with ONLY a valid JSON object. Nothing else.
- No markdown, no code fences, no commentary, no preamble.
- Every string value must use double quotes.
- Use these exact keys and value types:

should_coach: boolean
agent: one of "gamesense", "mechanics", "mental", "none" (which coaching agent to route to)
urgency: one of "low", "medium", "high", "critical"
game_state: string, ~1 paragraph tactical summary focusing on player positions, enemy positions, and urgent game context
narrative_update: string, what changed since last context
phase: one of "buy", "live", "post_round", "unknown"
round_number: integer
time_remaining: string (e.g. "1:30" or "unknown")
team_score: integer
enemy_score: integer
map_name: string (or "unknown")
player_character: string (the Valorant agent the player is controlling)
player_health: integer 0-150, or -1 if unknown
player_armor: boolean
player_credits: integer, -1 if unknown (crucial for economy coaching)
player_weapon: string
player_ammo: integer, -1 if unknown (amount of ammo in current magazine)
ultimate_status: string (e.g., "ready", "3/8", "unknown")
player_alive: boolean
player_position: string
spike_status: one of "planted", "carried", "dropped", "defusing", "unknown" (crucial for tactical decisions)
teammates_alive: integer, -1 if unknown (must not exceed total teammates in match)
enemies_alive: integer, -1 if unknown (must not exceed total enemies in match)
visible_enemies: integer
is_shooting: boolean
is_moving: boolean
crosshair_placement: one of "head_level", "too_low", "too_high", "off_angle", "unknown"
in_gunfight: boolean
recent_death: boolean
kill_feed_events: string, empty string if none

Example response (respond exactly like this, only JSON):
{"should_coach":true,"agent":"gamesense","urgency":"medium","game_state":"Player is holding B site. Two teammates are positioned at B link and C site. The enemy team has been spotted pushing A main aggressively with the spike. Urgently need to watch for potential flanks through mid.","narrative_update":"Teammate just died on A, enemy likely rotating.","phase":"live","round_number":8,"time_remaining":"0:45","team_score":4,"enemy_score":3,"map_name":"Haven","player_character":"Omen","player_health":100,"player_armor":true,"player_credits":4500,"player_weapon":"Vandal","player_ammo":25,"ultimate_status":"ready","player_alive":true,"player_position":"B site","spike_status":"carried","teammates_alive":2,"enemies_alive":3,"visible_enemies":0,"is_shooting":false,"is_moving":false,"crosshair_placement":"head_level","in_gunfight":false,"recent_death":false,"kill_feed_events":"Teammate eliminated by enemy Jett"}"""

# --- Schema ---
class GameContext(BaseModel):
    should_coach: bool = Field(description="Whether anything worth coaching is happening")
    agent: Literal["gamesense", "mechanics", "mental", "none"] = Field(
        description="Which specialist agent should handle this"
    )
    urgency: Literal["low", "medium", "high", "critical"] = Field(
        description="How urgently the player needs coaching"
    )
    game_state: str = Field(description="A ~1 paragraph rich summary including player positions, enemy positions, and urgent info")
    narrative_update: str = Field(description="What specifically changed since the previous context")
    phase: Literal["buy", "live", "post_round", "unknown"] = Field(
        description="Current phase of the round"
    )
    round_number: int = Field(description="Current round number if visible, else 0")
    time_remaining: str = Field(description="Time remaining in current phase, e.g. '1:30' or 'unknown'")
    team_score: int = Field(description="Player's team score, -1 if unknown")
    enemy_score: int = Field(description="Enemy team score, -1 if unknown")
    map_name: str = Field(description="Name of the map, or 'unknown'")
    player_character: str = Field(description="Valorant agent being played (from top bar or minimap center)")
    player_health: int = Field(description="Player HP 0-150, or -1 if unknown")
    player_armor: bool = Field(description="Whether player has armor equipped")
    player_credits: int = Field(description="Credits visible, else -1. Crucial for buy phase")
    player_weapon: str = Field(description="Current weapon name or 'unknown'")
    player_ammo: int = Field(description="Amount of ammo currently in the magazine, or -1 if unknown")
    ultimate_status: str = Field(description="Ultimate charge status (e.g. 'ready', '7/8', 'unknown')")
    player_alive: bool = Field(description="Whether the player is alive")
    player_position: str = Field(description="Where on map player appears to be, or 'unknown'")
    spike_status: Literal["planted", "carried", "dropped", "defusing", "unknown"] = Field(
        description="Current spike status"
    )
    teammates_alive: int = Field(description="Number of teammates alive if visible (cannot exceed actual teammates), else -1")
    enemies_alive: int = Field(description="Number of enemies alive if visible (cannot exceed actual enemies), else -1")
    visible_enemies: int = Field(description="Number of enemies currently on screen")
    is_shooting: bool = Field(description="Whether player appears to be firing")
    is_moving: bool = Field(description="Whether player appears to be moving")
    crosshair_placement: Literal["head_level", "too_low", "too_high", "off_angle", "unknown"] = Field(
        description="Where crosshair is positioned relative to where enemies would be"
    )
    in_gunfight: bool = Field(description="Whether a gunfight is actively happening")
    recent_death: bool = Field(description="Whether death screen or respawn is visible")
    kill_feed_events: str = Field(description="Brief summary of recent killfeed, or empty string")


# --- Client ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=types.Content(
        parts=[types.Part.from_text(text=SYSTEM_PROMPT)]
    ),
    temperature=0.1,
    output_audio_transcription=types.AudioTranscriptionConfig(),
)

# --- Parsing ---
def parse_game_context(text: str) -> GameContext | None:
    """Extract and validate a GameContext JSON from the model's text response."""
    text = text.strip()

    # Try direct parse
    try:
        return GameContext.model_validate_json(text)
    except (ValidationError, json.JSONDecodeError):
        pass

    # Try extracting from markdown code block
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return GameContext.model_validate_json(match.group(1))
        except (ValidationError, json.JSONDecodeError):
            pass

    # Try extracting first complete JSON object
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try:
            return GameContext.model_validate_json(text[start:end + 1])
        except (ValidationError, json.JSONDecodeError):
            pass

    return None


# --- Logging ---
def log_context(ctx: GameContext):
    print(f"[SpectAI] ─────────────────────────────────")
    print(f"[SpectAI] Map: {ctx.map_name} | Phase: {ctx.phase} | Round: {ctx.round_number} | Time: {ctx.time_remaining}")
    print(f"[SpectAI] Score: {ctx.team_score}-{ctx.enemy_score}")
    print(f"[SpectAI] State: {ctx.game_state}")
    print(f"[SpectAI] Update: {ctx.narrative_update}")
    print(f"[SpectAI] Agent: {ctx.agent} | Urgency: {ctx.urgency}")
    print(f"[SpectAI] Character: {ctx.player_character} | Ult: {ctx.ultimate_status}")
    print(f"[SpectAI] Health: {ctx.player_health} | Armor: {ctx.player_armor} | Weapon: {ctx.player_weapon} (Ammo: {ctx.player_ammo}) | Credits: {ctx.player_credits}")
    print(f"[SpectAI] Position: {ctx.player_position} | Spike: {ctx.spike_status}")
    print(f"[SpectAI] Teammates: {ctx.teammates_alive} | Enemies: {ctx.enemies_alive} | Visible: {ctx.visible_enemies}")
    print(f"[SpectAI] Gunfight: {ctx.in_gunfight} | Shooting: {ctx.is_shooting} | Moving: {ctx.is_moving}")
    print(f"[SpectAI] Crosshair: {ctx.crosshair_placement} | Recent death: {ctx.recent_death}")
    if ctx.kill_feed_events:
        print(f"[SpectAI] Killfeed: {ctx.kill_feed_events}")
    print(f"[SpectAI] Should coach: {ctx.should_coach}")
    print(f"[SpectAI] ─────────────────────────────────")


# --- Game State Integration ---
def build_game_context_summary(val_client: ValorantLocalClient, resolver: ValorantResolver) -> tuple[str, int, int] | None:
    """
    Fetch live game state from the Valorant local API, resolve UUIDs,
    and return a compact text summary suitable for LLM context injection
    along with the (ally_count, enemy_count) to enforce bounds.
    Returns None if not in a game or if the API is unavailable.
    """
    try:
        raw_state = val_client.get_full_game_state()
    except Exception as e:
        log.debug("Could not fetch game state: %s", e)
        return None

    phase = raw_state.phase
    if phase == GamePhase.MENUS:
        return None  # No useful context in menus

    resolved = resolver.resolve_game_state(asdict(raw_state))

    lines = [f"Phase: {resolved.phase}"]

    if resolved.map:
        lines.append(f"Map: {resolved.map.name}")
    if resolved.mode:
        lines.append(f"Mode: {resolved.mode}")

    # Split players into our team vs enemy team
    my_puuid = resolved.puuid
    my_team_id = None
    my_agent = None
    
    # Filter to only include actual loaded players (ignore empty custom match slots)
    valid_players = []
    for p in resolved.players:
        # A valid player usually has a real puuid and isn't just an empty string
        # Also need to check if character_id/agent actually resolved to something
        if p.puuid and p.agent and p.agent.name != "Unknown":
            valid_players.append(p)
    
    for p in valid_players:
        if p.puuid == my_puuid:
            my_team_id = p.team_id
            my_agent = p.agent.name if p.agent else "Unknown"
            break

    if my_agent:
        lines.append(f"Your team: {my_team_id}")
        lines.append(f"Your agent: {my_agent}")

    allies = []
    enemies = []
    for p in valid_players:
        if p.puuid == my_puuid:
            continue
            
        name = p.agent.name if p.agent else "Unknown"
        role = p.agent.role if p.agent else ""
        entry = f"{name} ({role})" if role else name
        
        if my_team_id and p.team_id == my_team_id:
            allies.append(entry)
        else:
            enemies.append(entry)

    if allies:
        lines.append(f"Teammates ({len(allies)}): {', '.join(allies)}")
    else:
        lines.append("Teammates: 0 (You have no teammates in this match)")
        
    if enemies:
        lines.append(f"Enemies ({len(enemies)}): {', '.join(enemies)}")
    else:
        lines.append("Enemies: 0 (There are no enemies in this match)")
        
    lines.append(f"Total Players: {len(valid_players)} (Do NOT guess 4 teammates and 5 enemies. Use these exact numbers!)")

    # Include map callout names so the LLM can reference real callouts
    if resolved.map and resolved.map.callouts:
        callout_names = sorted(set(c.region_name for c in resolved.map.callouts))
        lines.append(f"Map callouts: {', '.join(callout_names)}")

    return "\n".join(lines), len(allies), len(enemies)


# --- Core ---
async def run_spect_ai():
    print("[SpectAI] Starting vision layer (Live API)...")
    screen_capture = WindowCapture(TARGET_WINDOW)
    last_coached = 0.0
    history_buffer: list[str] = []
    
    # Maintain a rolling state of the player to act as a sanity check guide for the LLM
    tracked_player_state = {
        "health": -1,
        "armor": False,
        "weapon": "unknown",
        "ammo_in_mag": -1,
        "ultimate": "unknown",
        "credits": -1,
        "alive": True,
        "teammates_alive": -1,
        "enemies_alive": -1,
        "team_score": -1,
        "enemy_score": -1,
        "spike_status": "unknown"
    }

    # Initialize Valorant API client and resolver (graceful if Valorant isn't running)
    val_client = None
    resolver = None
    try:
        val_client = ValorantLocalClient()
        resolver = ValorantResolver()
        print("[SpectAI] Valorant API connected — game context enabled.")
    except Exception as e:
        print(f"[SpectAI] Valorant API unavailable ({e}) — running vision-only mode.")

    game_context_summary: str | None = None
    max_allies = 4
    max_enemies = 5
    last_game_state_fetch = 0.0

    async with client.aio.live.connect(model=MODEL, config=LIVE_CONFIG) as session:
        print("[SpectAI] Live session connected.")

        while True:
            now = asyncio.get_event_loop().time()

            if (now - last_coached) < COOLDOWN_SECONDS:
                await asyncio.sleep(0.5)
                continue

            # Periodically refresh game state from Valorant API
            if val_client and resolver and (now - last_game_state_fetch) >= GAME_STATE_REFRESH_SECONDS:
                try:
                    result = build_game_context_summary(val_client, resolver)
                    last_game_state_fetch = now
                    if result:
                        game_context_summary, max_allies, max_enemies = result
                        # Hard cap the tracked state so the LLM doesn't feed itself hallucinated constraints over time
                        if tracked_player_state["teammates_alive"] > max_allies:
                            tracked_player_state["teammates_alive"] = max_allies
                        if tracked_player_state["enemies_alive"] > max_enemies:
                            tracked_player_state["enemies_alive"] = max_enemies
                        print(f"[SpectAI] Game context refreshed.")
                except Exception as e:
                    log.debug("Game state refresh error: %s", e)

            frame = screen_capture.capture()
            if frame is None:
                await asyncio.sleep(0.5)
                continue

            try:
                jpeg_bytes = screen_capture.frame_to_jpeg(frame)

                # Send frame as video input
                await session.send_realtime_input(
                    video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                )

                # Build prompt with optional API context + previous state
                parts = []
                if game_context_summary:
                    parts.append(f"LIVE GAME DATA (from Valorant API):\n{game_context_summary}")
                    
                # Include the tracked player state as a guide
                parts.append(
                    "CURRENT TRACKED PLAYER STATE (Contextual Guide):\n"
                    "Note: This is the most recently detected state of the player. Use it as a guide to verify what you see. "
                    "However, it might be outdated or inaccurate if the player recently bought an item, took damage, died, etc. "
                    "Always prioritize what you explicitly see in the CURRENT frame.\n"
                    f"{json.dumps(tracked_player_state, indent=2)}"
                )

                if history_buffer:
                    history_text = "\n".join(f"T-{len(history_buffer)-i}: {h}" for i, h in enumerate(history_buffer))
                    parts.append(
                        "RECENT HISTORY (Buffer of previous states):\n"
                        "Note: These past states are AI-generated and may contain inaccuracies. "
                        "Do not fixate on past errors; always prioritize the current visual frame and LIVE GAME DATA.\n"
                        f"{history_text}"
                    )
                parts.append("Analyze the CURRENT frame. Focus on changes. Respond with JSON only.")
                prompt = "\n\n".join(parts)

                await session.send_realtime_input(text=prompt)

                # Collect transcription from audio response
                full_text = ""
                async for msg in session.receive():
                    if msg.server_content:
                        if msg.server_content.output_transcription:
                            full_text += msg.server_content.output_transcription.text or ""
                        if msg.server_content.turn_complete:
                            break

                if full_text:
                    ctx = parse_game_context(full_text)
                    if ctx:
                        log_context(ctx)
                        
                        # Update tracked player state (ignoring invalid or 'unknown' if we can)
                        if ctx.player_health != -1 and ctx.player_alive:
                            tracked_player_state["health"] = ctx.player_health
                            tracked_player_state["armor"] = ctx.player_armor
                        if ctx.player_weapon != "unknown":
                            tracked_player_state["weapon"] = ctx.player_weapon
                            # Reset ammo to -1 or update it if weapon changed vs ammo detected
                        if ctx.player_ammo != -1:
                            tracked_player_state["ammo_in_mag"] = ctx.player_ammo
                        if ctx.ultimate_status != "unknown":
                            tracked_player_state["ultimate"] = ctx.ultimate_status
                        if ctx.player_credits != -1:
                            tracked_player_state["credits"] = ctx.player_credits
                        if ctx.teammates_alive != -1:
                            tracked_player_state["teammates_alive"] = min(ctx.teammates_alive, max_allies)
                        if ctx.enemies_alive != -1:
                            tracked_player_state["enemies_alive"] = min(ctx.enemies_alive, max_enemies)
                        if ctx.team_score != -1:
                            tracked_player_state["team_score"] = ctx.team_score
                        if ctx.enemy_score != -1:
                            tracked_player_state["enemy_score"] = ctx.enemy_score
                        if ctx.spike_status != "unknown":
                            tracked_player_state["spike_status"] = ctx.spike_status
                            
                        # Force dead stats when dead
                        tracked_player_state["alive"] = ctx.player_alive
                        if not ctx.player_alive or ctx.recent_death:
                            tracked_player_state["health"] = 0
                            tracked_player_state["armor"] = False
                            
                        history_entry = f"Phase: {ctx.phase} | Round: {ctx.round_number} | Time: {ctx.time_remaining} | Update: {ctx.narrative_update} | State: {ctx.game_state}"
                        history_buffer.append(history_entry)
                        if len(history_buffer) > MAX_HISTORY:
                            history_buffer.pop(0)
                        
                        # Send to orchestrator if should coach
                        if ctx.should_coach and _agent_ctx:
                            profile = PLAYER_PROFILES.get("player_001")
                            if profile:
                                profile = profile.model_copy(update={"agent_name": ctx.player_character or profile.agent_name})
                                score_str = f"{ctx.team_score}-{ctx.enemy_score}" if ctx.team_score >= 0 and ctx.enemy_score >= 0 else None
                                req = AnalysisRequest(
                                    profile=profile,
                                    game_state_text=ctx.game_state,
                                    round_num=ctx.round_number or 0,
                                    map_name=ctx.map_name or "",
                                    time_remaining=_parse_time(ctx.time_remaining),
                                    score=score_str,
                                    credits=ctx.player_credits if ctx.player_credits >= 0 else None,
                                    spike_status=ctx.spike_status if ctx.spike_status != "unknown" else None,
                                    urgency=ctx.urgency,
                                    position=ctx.player_position,
                                    weapon=ctx.player_weapon,
                                    health=ctx.player_health if ctx.player_health >= 0 else None,
                                    armor=ctx.player_armor,
                                    crosshair_placement=ctx.crosshair_placement,
                                    in_gunfight=ctx.in_gunfight,
                                )
                                await _agent_ctx.send(ORCHESTRATOR_ADDRESS, req)
                                _agent_ctx.logger.info(f"[vision] Analysis sent — round {req.round_num}, urgency={req.urgency}")
                    else:
                        print(f"[SpectAI] Parse failed. Raw: {full_text[:300]}")
                else:
                    print("[SpectAI] Empty response received")

            except Exception as e:
                print(f"[SpectAI] Error: {e}")
            finally:
                last_coached = asyncio.get_event_loop().time()


if __name__ == "__main__":
    _vision_agent.run()