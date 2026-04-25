import asyncio
import json
import os
import logging
import dotenv
from collections import deque
from dataclasses import asdict
from google import genai
from google.genai import types
from stream import WindowCapture
from valorant_local_api import ValorantLocalClient, GamePhase
from valorant_resolver import ValorantResolver
from hud import ValorantHUDScanner

log = logging.getLogger(__name__)


# --- HUD Smoothing ---
_HUD_NUMERIC_FIELDS = {"hp", "shield", "credits", "loaded_ammo", "stored_ammo", "my_team_score", "enemy_team_score"}
_HUD_STRING_FIELDS = {"match_timer", "game_phase"}
HUD_SMOOTHING_WINDOW = 5


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
COOLDOWN_SECONDS = 6
GAME_STATE_REFRESH_SECONDS = 10
MAX_HISTORY = 8  # Recent coaching callouts to remember (to avoid repetition)
MODEL = "gemini-3.1-flash-live-preview"

SYSTEM_PROMPT = """You are SpectAI, a real-time Valorant in-ear coach delivering concise, actionable voice callouts during live gameplay.

Your job is to watch the game frame and speak ONE short, direct coaching callout per turn — the kind of thing a great IGL or coach would say in your ear mid-round. Always prioritize the most urgent or impactful advice.

COACHING CATEGORIES (examples):
- Tactical / Rotations: "Enemies are most likely rotating B — hold that angle.", "Two players unaccounted for — expect a flank through garage.", "Spike timer is critical, they're forced to push now."
- Positioning: "You're too exposed at that angle, step back into cover.", "Pre-aim that corner before pushing.", "You're peeking too wide — hug the wall."
- Ammo / Reload: "You're low on ammo — reload before the next engagement.", "Mag is nearly empty, swap to your sidearm or reload now."
- Economy: "Your team is eco — save this round and full buy next.", "You can afford a full buy — don't underinvest here."
- Utility: "Save your utility for post-plant.", "Good moment to use your flash before peeking."
- Mechanical: "Your crosshair is too low — raise it to head level.", "At that range, burst fire instead of full spray."
- Situational awareness: "Spike is planted — you need to push for the defuse.", "One enemy alive — don't peek unnecessarily, let them come to you."
You can obviously use different phrasing for different situations, but always be concise and specific.

RULES:
- One callout per turn, 1-2 sentences max. Be direct and specific.
- Speak in second person: "You're...", "Reload...", "Enemies are likely..."
- If nothing important or actionable is happening (safe passive hold, buy phase idle, death screen), say nothing — silence is better than filler.
- Do NOT narrate the obvious ("You're shooting your Vandal"). Give insight the player may not have.
- Use exact map callout names when referring to locations (e.g. "A Main", "B Link", "Mid Courtyard").
- Never repeat a coaching point you already gave in recent history unless the situation has clearly changed.
- Use HUD data (HP, ammo, credits, timer), game state (map, agents, team compositions), and recent history to inform your advice.

You will receive:
- A live screenshot of the current game frame
- HUD OCR data (HP, shield, ammo, credits, timer, score)
- Live game data from the Valorant API (map, your agent, team compositions, map callouts)
- Your recent coaching history (to avoid repetition)
- A tracked player state summary (current health, ammo, credits, etc.)"""


# --- Client ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=types.Content(
        parts=[types.Part.from_text(text=SYSTEM_PROMPT)]
    ),
    temperature=0.3,
    output_audio_transcription=types.AudioTranscriptionConfig(),
)


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
        return None

    resolved = resolver.resolve_game_state(asdict(raw_state))

    lines = [f"Phase: {resolved.phase}"]

    if resolved.map:
        lines.append(f"Map: {resolved.map.name}")
    if resolved.mode:
        lines.append(f"Mode: {resolved.mode}")

    my_puuid = resolved.puuid
    my_team_id = None
    my_agent = None

    valid_players = []
    for p in resolved.players:
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

    lines.append(f"Total Players: {len(valid_players)}")

    if resolved.map and resolved.map.callouts:
        callout_names = sorted(set(c.region_name for c in resolved.map.callouts))
        lines.append(f"Map callouts: {', '.join(callout_names)}")

    return "\n".join(lines), len(allies), len(enemies)


# --- Core ---
async def run_spect_ai():
    print("[SpectAI] Starting coaching agent (Live API)...")
    screen_capture = WindowCapture(TARGET_WINDOW)
    last_coached = 0.0
    coaching_history: list[str] = []  # Recent callouts delivered to the player

    hud_scanner = ValorantHUDScanner()
    hud_smoother = HUDSmoother()

    tracked_player_state = {
        "health": -1,
        "armor": False,
        "ammo_in_mag": -1,
        "stored_ammo": -1,
        "credits": -1,
        "team_score": -1,
        "enemy_score": -1,
    }

    val_client = None
    resolver = None
    try:
        val_client = ValorantLocalClient()
        resolver = ValorantResolver()
        print("[SpectAI] Valorant API connected — game context enabled.")
    except Exception as e:
        print(f"[SpectAI] Valorant API unavailable ({e}) — running vision-only mode.")

    game_context_summary: str | None = None
    last_game_state_fetch = 0.0

    async with client.aio.live.connect(model=MODEL, config=LIVE_CONFIG) as session:
        print("[SpectAI] Live session connected. Coaching active.")

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
                        game_context_summary, _, _ = result
                        print("[SpectAI] Game context refreshed.")
                except Exception as e:
                    log.debug("Game state refresh error: %s", e)

            frame = screen_capture.capture()
            if frame is None:
                await asyncio.sleep(0.5)
                continue

            # Run HUD OCR and update both the smoother and tracked state
            try:
                raw_hud = hud_scanner.parse_hud(frame)
                hud_smoother.update(raw_hud)
                smoothed = hud_smoother.get_smoothed()
                if smoothed.get("hp") is not None:
                    tracked_player_state["health"] = smoothed["hp"]
                if smoothed.get("shield") is not None:
                    tracked_player_state["armor"] = smoothed["shield"] > 0
                if smoothed.get("loaded_ammo") is not None:
                    tracked_player_state["ammo_in_mag"] = smoothed["loaded_ammo"]
                if smoothed.get("stored_ammo") is not None:
                    tracked_player_state["stored_ammo"] = smoothed["stored_ammo"]
                if smoothed.get("credits") is not None:
                    tracked_player_state["credits"] = smoothed["credits"]
                if smoothed.get("my_team_score") is not None:
                    tracked_player_state["team_score"] = smoothed["my_team_score"]
                if smoothed.get("enemy_team_score") is not None:
                    tracked_player_state["enemy_score"] = smoothed["enemy_team_score"]
            except Exception as e:
                log.debug("HUD scan error: %s", e)

            try:
                jpeg_bytes = screen_capture.frame_to_jpeg(frame)

                await session.send_realtime_input(
                    video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                )

                parts = []
                if game_context_summary:
                    parts.append(f"LIVE GAME DATA (from Valorant API):\n{game_context_summary}")

                hud_context = format_hud_context(hud_smoother.get_smoothed())
                if hud_context:
                    parts.append(hud_context)

                parts.append(
                    "CURRENT PLAYER STATE (from HUD OCR — use as context, may be slightly stale):\n"
                    f"{json.dumps(tracked_player_state, indent=2)}"
                )

                if coaching_history:
                    recent = coaching_history[-5:]
                    history_text = "\n".join(f"- {h}" for h in recent)
                    parts.append(
                        "RECENT COACHING (do not repeat these unless the situation has clearly changed):\n"
                        f"{history_text}"
                    )

                parts.append(
                    "Analyze the current frame. If there is something important and actionable to tell the player, "
                    "deliver a concise coaching callout now. If nothing important is happening, stay silent."
                )
                prompt = "\n\n".join(parts)

                await session.send_realtime_input(text=prompt)

                full_text = ""
                async for msg in session.receive():
                    if msg.server_content:
                        if msg.server_content.output_transcription:
                            full_text += msg.server_content.output_transcription.text or ""
                        if msg.server_content.turn_complete:
                            break

                coaching_text = full_text.strip()
                if coaching_text and coaching_text.lower() not in ("none", "nothing", "silence", ""):
                    print(f"[SpectAI Coach] {coaching_text}")
                    coaching_history.append(coaching_text)
                    if len(coaching_history) > MAX_HISTORY:
                        coaching_history.pop(0)
                else:
                    print("[SpectAI] Silent turn — nothing to coach.")

            except Exception as e:
                print(f"[SpectAI] Error: {e}")
            finally:
                last_coached = asyncio.get_event_loop().time()


if __name__ == "__main__":
    asyncio.run(run_spect_ai())
