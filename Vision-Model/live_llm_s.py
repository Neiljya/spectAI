import asyncio
import json
import os
import re
import sys
import ctypes
import tempfile
import threading
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

import httpx
import numpy as np

try:
    import sounddevice as sd
    from pynput import keyboard as kb
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    print("[SpectAI] Voice input unavailable — pip install sounddevice pynput")

log = logging.getLogger(__name__)

# --- Config ---
dotenv.load_dotenv()
TARGET_WINDOW = "VALORANT  "
CAPTURE_FPS = 2
COOLDOWN_SECONDS = 8
GAME_STATE_REFRESH_SECONDS = 10
MAX_HISTORY = 10
MODEL = "gemini-2.5-flash-native-audio-latest"

# --- PTT ---
PTT_KEY = kb.Key.f9 if VOICE_AVAILABLE else None  # F9 — never used in Valorant
MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1

# --- ElevenLabs TTS ---
_ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
_ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George
_tts_lock = threading.Lock()


def _play_mp3(path: str):
    if sys.platform == "win32":
        mci = ctypes.windll.winmm.mciSendStringW
        mci(f'open "{path}" type mpegvideo alias spectai_tts', None, 0, None)
        mci('play spectai_tts wait', None, 0, None)
        mci('close spectai_tts', None, 0, None)


def _speak_sync(text: str):
    if not _ELEVENLABS_KEY or not text.strip():
        return
    with _tts_lock:
        try:
            resp = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{_ELEVENLABS_VOICE}",
                headers={"xi-api-key": _ELEVENLABS_KEY, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": "eleven_flash_v2_5",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=15,
            )
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name
            _play_mp3(tmp_path)
        except Exception as e:
            print(f"[SpectAI] TTS error: {e}")


# --- System Prompt ---
SYSTEM_PROMPT = """You are SpectAI, an elite real-time Valorant coach with vision access to the player's screen.
You watch game frames and deliver precise, actionable coaching in the moment.
Use the HUD: health, ammo, top bar (agent icons, ult status, time, scores), killfeed, and minimap.
IMPORTANT: To identify the player's agent, look at the top bar icon or the center of the minimap.
You will sometimes receive a RECENT HISTORY buffer of previous game states. Use it to understand context and changes over time. Always prioritize the current frame over history.
You may also receive LIVE GAME DATA from the Valorant API. Use it to fill in map_name, player_character, and team compositions accurately. Use the provided callout names for player_position.
When the player asks a voice question (marked PLAYER VOICE QUESTION), answer it directly in plain conversational text, 12 words or fewer — do NOT respond with JSON for voice questions.

OUTPUT RULES for screen analysis — follow these exactly:
- Respond with ONLY a valid JSON object. Nothing else.
- No markdown, no code fences, no commentary, no preamble.
- Every string value must use double quotes.
- Use these exact keys and value types:

should_coach: boolean
agent: one of "gamesense", "mechanics", "mental", "none"
urgency: one of "low", "medium", "high", "critical"
game_state: string, max 12 words, direct coaching call telling the player exactly what to do RIGHT NOW. Be specific and actionable (e.g. "Rotate A now — spike carrier mid, no support.")
narrative_update: string, what changed since last context
phase: one of "buy", "live", "post_round", "unknown"
round_number: integer
time_remaining: string (e.g. "1:30" or "unknown")
team_score: integer
enemy_score: integer
map_name: string (or "unknown")
player_character: string
player_health: integer 0-150, or -1 if unknown
player_armor: boolean
player_credits: integer, -1 if unknown
player_weapon: string
player_ammo: integer, -1 if unknown
ultimate_status: string (e.g. "ready", "3/8", "unknown")
player_alive: boolean
player_position: string
spike_status: one of "planted", "carried", "dropped", "defusing", "unknown"
teammates_alive: integer, -1 if unknown
enemies_alive: integer, -1 if unknown
visible_enemies: integer
is_shooting: boolean
is_moving: boolean
crosshair_placement: one of "head_level", "too_low", "too_high", "off_angle", "unknown"
in_gunfight: boolean
recent_death: boolean
kill_feed_events: string, empty string if none

Example response:
{"should_coach":true,"agent":"gamesense","urgency":"high","game_state":"Push B short right now — Sage is the only defender and your team has a 3v1 advantage with 40 seconds left.","narrative_update":"Teammate just cleared B main, one enemy confirmed B short.","phase":"live","round_number":8,"time_remaining":"0:40","team_score":4,"enemy_score":3,"map_name":"Haven","player_character":"Omen","player_health":100,"player_armor":true,"player_credits":4500,"player_weapon":"Vandal","player_ammo":25,"ultimate_status":"ready","player_alive":true,"player_position":"B site","spike_status":"carried","teammates_alive":2,"enemies_alive":1,"visible_enemies":0,"is_shooting":false,"is_moving":false,"crosshair_placement":"head_level","in_gunfight":false,"recent_death":false,"kill_feed_events":""}"""


# --- Schema ---
class GameContext(BaseModel):
    should_coach: bool = Field(description="Whether there is an actionable coaching moment right now")
    agent: Literal["gamesense", "mechanics", "mental", "none"] = Field(
        description="Which type of coaching this falls under"
    )
    urgency: Literal["low", "medium", "high", "critical"] = Field(
        description="How urgently the player needs this coaching"
    )
    game_state: str = Field(description="Max 12 words. Direct coaching call telling the player what to do RIGHT NOW.")
    narrative_update: str = Field(description="What specifically changed since the previous context")
    phase: Literal["buy", "live", "post_round", "unknown"] = Field(
        description="Current phase of the round"
    )
    round_number: int = Field(description="Current round number if visible, else 0")
    time_remaining: str = Field(description="Time remaining in current phase, e.g. '1:30' or 'unknown'")
    team_score: int = Field(description="Player's team score, -1 if unknown")
    enemy_score: int = Field(description="Enemy team score, -1 if unknown")
    map_name: str = Field(description="Name of the map, or 'unknown'")
    player_character: str = Field(description="Valorant agent being played")
    player_health: int = Field(description="Player HP 0-150, or -1 if unknown")
    player_armor: bool = Field(description="Whether player has armor equipped")
    player_credits: int = Field(description="Credits visible, else -1")
    player_weapon: str = Field(description="Current weapon name or 'unknown'")
    player_ammo: int = Field(description="Ammo in magazine, or -1 if unknown")
    ultimate_status: str = Field(description="Ultimate charge status e.g. 'ready', '7/8', 'unknown'")
    player_alive: bool = Field(description="Whether the player is alive")
    player_position: str = Field(description="Where on map player appears to be, or 'unknown'")
    spike_status: Literal["planted", "carried", "dropped", "defusing", "unknown"] = Field(
        description="Current spike status"
    )
    teammates_alive: int = Field(description="Number of teammates alive, else -1")
    enemies_alive: int = Field(description="Number of enemies alive, else -1")
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
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={"api_version": "v1alpha"})

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=types.Content(
        parts=[types.Part(text=SYSTEM_PROMPT)]
    ),
    temperature=0.1,
    output_audio_transcription=types.AudioTranscriptionConfig(),
)


# --- Parsing ---
def parse_game_context(text: str) -> GameContext | None:
    text = text.strip()
    try:
        return GameContext.model_validate_json(text)
    except (ValidationError, json.JSONDecodeError):
        pass
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return GameContext.model_validate_json(match.group(1))
        except (ValidationError, json.JSONDecodeError):
            pass
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
    print(f"[SpectAI] Coaching: {ctx.game_state}")
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

    lines.append(f"Total Players: {len(valid_players)} (Do NOT guess 4 teammates and 5 enemies. Use these exact numbers!)")

    if resolved.map and resolved.map.callouts:
        callout_names = sorted(set(c.region_name for c in resolved.map.callouts))
        lines.append(f"Map callouts: {', '.join(callout_names)}")

    return "\n".join(lines), len(allies), len(enemies)


# --- Voice Input (PTT) ---
def start_ptt_listener(loop: asyncio.AbstractEventLoop, voice_queue: asyncio.Queue):
    """Background thread: records mic while Insert held, puts PCM bytes in queue."""
    if not VOICE_AVAILABLE:
        return

    recording = False
    audio_chunks = []

    def audio_callback(indata, _frames, _time, _status):
        if recording:
            audio_chunks.append(indata.copy())

    def on_press(key):
        nonlocal recording, audio_chunks
        if key == PTT_KEY and not recording:
            recording = True
            audio_chunks = []
            print("[SpectAI] Listening... (release Insert to send)")

    def on_release(key):
        nonlocal recording
        if key == PTT_KEY and recording:
            recording = False
            if audio_chunks:
                audio_data = np.concatenate(audio_chunks, axis=0)
                pcm_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                asyncio.run_coroutine_threadsafe(voice_queue.put(pcm_bytes), loop)
                print("[SpectAI] Voice query received — processing...")

    with sd.InputStream(samplerate=MIC_SAMPLE_RATE, channels=MIC_CHANNELS,
                        dtype='float32', callback=audio_callback):
        with kb.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()


# --- Voice Query Handler ---
async def handle_voice_query(session, pcm_bytes: bytes, loop: asyncio.AbstractEventLoop):
    """Send player voice audio to Gemini, TTS the plain-text coaching response."""
    await session.send_realtime_input(
        audio=types.Blob(data=pcm_bytes, mime_type=f"audio/pcm;rate={MIC_SAMPLE_RATE}")
    )
    await session.send_realtime_input(
        text="PLAYER VOICE QUESTION — answer this directly as their Valorant coach. Be concise and actionable. Respond in plain conversational text, NOT JSON."
    )

    full_text = ""
    async for msg in session.receive():
        if msg.server_content:
            if msg.server_content.output_transcription:
                full_text += msg.server_content.output_transcription.text or ""
            if msg.server_content.turn_complete:
                break

    if full_text:
        print(f"[SpectAI] Voice response: {full_text}")
        loop.run_in_executor(None, _speak_sync, full_text)


# --- Core ---
async def run_spect_ai():
    print("[SpectAI] Starting vision layer (Live API)...")
    screen_capture = WindowCapture(TARGET_WINDOW)
    last_coached = 0.0
    history_buffer: list[str] = []
    loop = asyncio.get_event_loop()

    tracked_player_state = {
        "health": -1, "armor": False, "weapon": "unknown", "ammo_in_mag": -1,
        "ultimate": "unknown", "credits": -1, "alive": True,
        "teammates_alive": -1, "enemies_alive": -1,
        "team_score": -1, "enemy_score": -1, "spike_status": "unknown"
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
    max_allies = 4
    max_enemies = 5
    last_game_state_fetch = 0.0

    # Voice queue + PTT listener
    voice_queue: asyncio.Queue = asyncio.Queue()
    if VOICE_AVAILABLE:
        ptt_thread = threading.Thread(
            target=start_ptt_listener, args=(loop, voice_queue), daemon=True
        )
        ptt_thread.start()
        print(f"[SpectAI] Push-to-talk ready — hold F9 to ask a question.")
    else:
        print("[SpectAI] Voice input disabled (missing packages).")

    async with client.aio.live.connect(model=MODEL, config=LIVE_CONFIG) as session:
        print("[SpectAI] Live session connected.")

        while True:
            now = loop.time()

            # Voice query takes priority over screen analysis
            if not voice_queue.empty():
                pcm_bytes = await voice_queue.get()
                await handle_voice_query(session, pcm_bytes, loop)
                last_coached = loop.time()
                continue

            if (now - last_coached) < COOLDOWN_SECONDS:
                await asyncio.sleep(0.1)
                continue

            # Refresh game state from Valorant API
            if val_client and resolver and (now - last_game_state_fetch) >= GAME_STATE_REFRESH_SECONDS:
                try:
                    result = build_game_context_summary(val_client, resolver)
                    last_game_state_fetch = now
                    if result:
                        game_context_summary, max_allies, max_enemies = result
                        if tracked_player_state["teammates_alive"] > max_allies:
                            tracked_player_state["teammates_alive"] = max_allies
                        if tracked_player_state["enemies_alive"] > max_enemies:
                            tracked_player_state["enemies_alive"] = max_enemies
                        print("[SpectAI] Game context refreshed.")
                except Exception as e:
                    log.debug("Game state refresh error: %s", e)

            frame = screen_capture.capture()
            if frame is None:
                await asyncio.sleep(0.5)
                continue

            try:
                jpeg_bytes = screen_capture.frame_to_jpeg(frame)

                await session.send_realtime_input(
                    video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                )

                parts = []
                if game_context_summary:
                    parts.append(f"LIVE GAME DATA (from Valorant API):\n{game_context_summary}")

                parts.append(
                    "CURRENT TRACKED PLAYER STATE (Contextual Guide):\n"
                    "Note: This is the most recently detected state. Use it as a guide but always prioritize the current frame.\n"
                    f"{json.dumps(tracked_player_state, indent=2)}"
                )

                if history_buffer:
                    history_text = "\n".join(f"T-{len(history_buffer)-i}: {h}" for i, h in enumerate(history_buffer))
                    parts.append(
                        "RECENT HISTORY (Buffer of previous states):\n"
                        "Note: AI-generated and may contain inaccuracies. Always prioritize current frame.\n"
                        f"{history_text}"
                    )

                parts.append("Analyze the CURRENT frame. game_state must be 12 words or fewer — sharp and actionable. Respond with JSON only.")
                prompt = "\n\n".join(parts)

                await session.send_realtime_input(text=prompt)

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

                        # Speak coaching call via ElevenLabs
                        if ctx.should_coach and ctx.game_state:
                            loop.run_in_executor(None, _speak_sync, ctx.game_state)

                        # Update tracked state
                        if ctx.player_health != -1 and ctx.player_alive:
                            tracked_player_state["health"] = ctx.player_health
                            tracked_player_state["armor"] = ctx.player_armor
                        if ctx.player_weapon != "unknown":
                            tracked_player_state["weapon"] = ctx.player_weapon
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

                        tracked_player_state["alive"] = ctx.player_alive
                        if not ctx.player_alive or ctx.recent_death:
                            tracked_player_state["health"] = 0
                            tracked_player_state["armor"] = False

                        history_entry = f"Phase: {ctx.phase} | Round: {ctx.round_number} | Time: {ctx.time_remaining} | Coaching: {ctx.game_state} | Update: {ctx.narrative_update}"
                        history_buffer.append(history_entry)
                        if len(history_buffer) > MAX_HISTORY:
                            history_buffer.pop(0)
                    else:
                        print(f"[SpectAI] Parse failed. Raw: {full_text[:300]}")
                else:
                    print("[SpectAI] Empty response received")

            except Exception as e:
                print(f"[SpectAI] Error: {e}")
            finally:
                last_coached = loop.time()


if __name__ == "__main__":
    asyncio.run(run_spect_ai())
