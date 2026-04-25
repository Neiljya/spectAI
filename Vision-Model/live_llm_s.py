import asyncio
import json
import os
import re
import sys
import logging
import dotenv
from collections import deque
from dataclasses import asdict
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from typing import Literal
from stream import WindowCapture
from valorant_local_api import ValorantLocalClient, GamePhase
from valorant_resolver import ValorantResolver
from hud import ValorantHUDScanner

log = logging.getLogger(__name__)


# --- HUD Smoothing ---
_HUD_NUMERIC_FIELDS = {"hp", "shield", "credits", "loaded_ammo", "stored_ammo", "my_team_score", "enemy_team_score"}
_HUD_STRING_FIELDS = {"match_timer", "game_phase"}
HUD_SMOOTHING_WINDOW = 5  # number of recent valid readings to average


class HUDSmoother:
    """Smooths noisy OCR readings with a rolling average per field."""

    def __init__(self, window: int = HUD_SMOOTHING_WINDOW):
        self._numeric: dict[str, deque] = {f: deque(maxlen=window) for f in _HUD_NUMERIC_FIELDS}
        self._string: dict[str, str] = {f: "" for f in _HUD_STRING_FIELDS}

    def update(self, raw: dict):
        for field in _HUD_NUMERIC_FIELDS:
            val = str(raw.get(field, "")).strip()
            if val.isdigit():
                self._numeric[field].append(int(val))
        for field in _HUD_STRING_FIELDS:
            val = str(raw.get(field, "")).strip()
            if val:
                self._string[field] = val

    def get_smoothed(self) -> dict:
        result = {}
        for field in _HUD_NUMERIC_FIELDS:
            readings = self._numeric[field]
            result[field] = round(sum(readings) / len(readings)) if readings else None
        for field in _HUD_STRING_FIELDS:
            result[field] = self._string[field] or None
        return result


def format_hud_context(smoothed: dict) -> str:
    """Format smoothed HUD data as a concise LLM context string."""
    lines = []

    hp = smoothed.get("hp")
    shield = smoothed.get("shield")
    if hp is not None:
        shield_str = f" | Shield: {shield}" if shield is not None else ""
        lines.append(f"  HP: {hp}{shield_str}")

    credits = smoothed.get("credits")
    if credits is not None:
        lines.append(f"  Credits: {credits}")

    timer = smoothed.get("match_timer")
    if timer:
        lines.append(f"  Round Timer: {timer}")

    left_score = smoothed.get("my_team_score")
    right_score = smoothed.get("enemy_team_score")
    if left_score is not None or right_score is not None:
        l = str(left_score) if left_score is not None else "?"
        r = str(right_score) if right_score is not None else "?"
        lines.append(f"  Score: {l} - {r}")

    loaded = smoothed.get("loaded_ammo")
    stored = smoothed.get("stored_ammo")
    if loaded is not None:
        ammo_str = f"{loaded}/{stored}" if stored is not None else str(loaded)
        lines.append(f"  Ammo: {ammo_str}")

    if not lines:
        return ""

    header = "HUD OCR DATA (screen-scraped — averaged over recent frames, may still be inaccurate):"
    footer = "  (OCR can misread digits. Cross-reference with what you actually see in the frame.)"
    return "\n".join([header] + lines + [footer])


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
You are a precise observer. Extract what you see accurately, then reason tactically about what it implies.
Use information from the HUD, like health, ammo, top bar (for agent icons, ult status, time, scores), killfeed, and minimap.
IMPORTANT: To identify the player's agent (character), look at the top bar icon or the center of the minimap.
You will sometimes receive a RECENT HISTORY buffer of previous game states. Use it to infer what changed over time. Note that previous states may be inaccurate, so prioritize the current frame over history.
You may also receive LIVE GAME DATA from the Valorant API. This gives you ground-truth about the map, agents, and teams. Use it to fill in map_name, player_character, and team compositions accurately instead of guessing from vision alone. Use the provided callout names when describing player_position.

TACTICAL REASONING GUIDELINES for game_state and narrative_update:
- Always state WHERE the player is using precise map callout names (e.g. "A Main", "B Link", "Mid Courtyard").
- Reason about what the ENEMY TEAM is likely doing based on all available signals: kill feed deaths, sound cues visible in-game, spike carrier status, time remaining, score pressure, and recent history. Use language like "enemy likely rotating A", "they may be faking B", "two unaccounted enemies — possible flank through mid".
- Reason about what TEAMMATES are doing if visible on minimap or top bar.
- Factor in TIME PRESSURE: late round with spike unplanted means attackers are forced; low time on a planted spike means defenders must defuse or die.
- Factor in ECONOMY signals: player or team on low credits likely means eco or force buy next round.
- Use natural, concise coaching language. Not "player is in location X". Instead: "Player is deep in B site holding the back-plant spot. With 0:30 left and spike unplanted, enemies must push — expect contact from B Main or Short immediately."

OUTPUT RULES — follow these exactly:
- Respond with ONLY a valid JSON object. Nothing else.
- No markdown, no code fences, no commentary, no preamble.
- Every string value must use double quotes.
- Use these exact keys and value types:

should_coach: boolean
agent: one of "gamesense", "mechanics", "mental", "none" (which coaching agent to route to)
urgency: one of "low", "medium", "high", "critical"
game_state: string, rich tactical paragraph — describe player position by callout, what the enemy team is likely doing and why, what teammates are doing, time/economy pressure, and any imminent threats or opportunities. Aim for 2-3 sentences of dense tactical context.
narrative_update: string, what tactically changed since last context — not just "player moved" but WHY it matters (e.g. "Player retreated from A Main to Haven — enemy Jett was pushing aggressively, now player is isolated with no util and low time")
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
{"should_coach":true,"agent":"gamesense","urgency":"high","game_state":"Player is holding B Long on Haven with a Vandal, two teammates covering B Short and C Long. The spike carrier is unaccounted for — with 0:45 left and no plant, the enemy is time-pressured and likely to force a push or fake B to pull rotations. One unconfirmed enemy on the killfeed last died at A Main, suggesting a potential 3-man B execute incoming. Player should expect contact within 10 seconds.","narrative_update":"Teammate just died at A Main — enemy Jett likely rotated or the team is executing B. Two enemies are now unaccounted for near B, raising flank risk through Garage.","phase":"live","round_number":8,"time_remaining":"0:45","team_score":4,"enemy_score":3,"map_name":"Haven","player_character":"Omen","player_health":100,"player_armor":true,"player_credits":4500,"player_weapon":"Vandal","player_ammo":25,"ultimate_status":"ready","player_alive":true,"player_position":"B Long","spike_status":"carried","teammates_alive":2,"enemies_alive":3,"visible_enemies":0,"is_shooting":false,"is_moving":false,"crosshair_placement":"head_level","in_gunfight":false,"recent_death":false,"kill_feed_events":"Teammate eliminated by enemy Jett at A Main"}"""

# --- Schema ---
class GameContext(BaseModel):
    should_coach: bool = Field(description="Whether anything worth coaching is happening")
    agent: Literal["gamesense", "mechanics", "mental", "none"] = Field(
        description="Which specialist agent should handle this"
    )
    urgency: Literal["low", "medium", "high", "critical"] = Field(
        description="How urgently the player needs coaching"
    )
    game_state: str = Field(description="Rich tactical paragraph: player position by callout, likely enemy movements and reasoning, teammate positions, time/economy pressure, imminent threats")
    narrative_update: str = Field(description="What tactically changed and why it matters — not just what happened but the implication (e.g. enemy rotation, flank risk, forced push)")
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
    response_modalities=["TEXT"],
    system_instruction=types.Content(
        parts=[types.Part.from_text(text=SYSTEM_PROMPT)]
    ),
    temperature=0.1,
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
    coach_flag = f"  [COACH → {ctx.agent.upper()} | {ctx.urgency.upper()}]" if ctx.should_coach else ""
    print(f"[SpectAI] ─────────────────────────────────")
    print(f"[SpectAI] {ctx.map_name} | {ctx.phase} | R{ctx.round_number} | {ctx.time_remaining} | {ctx.team_score}-{ctx.enemy_score}{coach_flag}")
    print(f"[SpectAI] {ctx.player_character} | HP:{ctx.player_health} | Armor:{ctx.player_armor} | {ctx.player_weapon}({ctx.player_ammo}) | Credits:{ctx.player_credits} | Ult:{ctx.ultimate_status}")
    print(f"[SpectAI] Pos:{ctx.player_position} | Spike:{ctx.spike_status} | TM:{ctx.teammates_alive} | ENE:{ctx.enemies_alive} | Vis:{ctx.visible_enemies}")
    print(f"[SpectAI] {ctx.game_state}")
    print(f"[SpectAI] ↳ {ctx.narrative_update}")
    if ctx.kill_feed_events:
        print(f"[SpectAI] Killfeed: {ctx.kill_feed_events}")
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

    # HUD OCR scanner + smoother
    hud_scanner = ValorantHUDScanner()
    hud_smoother = HUDSmoother()
    
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

            # Run HUD OCR scan and update smoother
            try:
                raw_hud = hud_scanner.parse_hud(frame)
                hud_smoother.update(raw_hud)
            except Exception as e:
                log.debug("HUD scan error: %s", e)

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

                hud_context = format_hud_context(hud_smoother.get_smoothed())
                if hud_context:
                    parts.append(hud_context)
                    
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

                # Collect text response
                full_text = ""
                async for msg in session.receive():
                    if msg.server_content:
                        if msg.server_content.model_turn:
                            for part in (msg.server_content.model_turn.parts or []):
                                if part.text:
                                    full_text += part.text
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
                            
                        # TODO: pass ctx to agent router
                    else:
                        print(f"[SpectAI] Parse failed. Raw: {full_text[:300]}")
                else:
                    print("[SpectAI] Empty response received")

            except Exception as e:
                print(f"[SpectAI] Error: {e}")
            finally:
                last_coached = asyncio.get_event_loop().time()


if __name__ == "__main__":
    asyncio.run(run_spect_ai())