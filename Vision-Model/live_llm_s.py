import asyncio
import json
import os
import re
import dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from typing import Literal
from stream import WindowCapture

# --- Config ---
dotenv.load_dotenv()
TARGET_WINDOW = "VALORANT  "
CAPTURE_FPS = 2
COOLDOWN_SECONDS = 4
MODEL = "gemini-3.1-flash-live-preview"

SYSTEM_PROMPT = """You are SpectAI, the vision layer of a real-time competitive FPS coaching system.
You analyze game frames and extract structured information for specialist coaching agents.
You are a precise observer, not a coach. Extract what you see accurately.
Use information from the HUD, like health, ammo, agent icon, team/enemy outlines, player icons, killfeed, and minimap to inform your analysis.
You will sometimes receive the PREVIOUS game state. Use it to infer what changed.

OUTPUT RULES — follow these exactly:
- Respond with ONLY a valid JSON object. Nothing else.
- No markdown, no code fences, no commentary, no preamble.
- Every string value must use double quotes.
- Use these exact keys and value types:

should_coach: boolean
agent: one of "gamesense", "mechanics", "mental", "none"
urgency: one of "low", "medium", "high", "critical"
game_state: string, 1-2 sentence tactical summary
narrative_update: string, what changed since last context
phase: one of "buy", "live", "post_round", "unknown"
round_number: integer
player_health: integer 0-150, or -1 if unknown
player_armor: boolean
player_credits: integer, -1 if unknown
player_weapon: string
player_alive: boolean
player_position: string
spike_status: one of "planted", "carried", "dropped", "unknown"
teammates_alive: integer, -1 if unknown
enemies_alive: integer, -1 if unknown
visible_enemies: integer
is_shooting: boolean
is_moving: boolean
crosshair_placement: one of "head_level", "too_low", "too_high", "off_angle", "unknown"
in_gunfight: boolean
recent_death: boolean
kill_feed_events: string, empty string if none

Example response (respond exactly like this, only JSON):
{"should_coach":true,"agent":"gamesense","urgency":"medium","game_state":"Player holding B site with Vandal, 3v3 situation.","narrative_update":"Teammate just died on A, enemy likely rotating.","phase":"live","round_number":8,"player_health":100,"player_armor":true,"player_credits":-1,"player_weapon":"Vandal","player_alive":true,"player_position":"B site","spike_status":"unknown","teammates_alive":2,"enemies_alive":3,"visible_enemies":0,"is_shooting":false,"is_moving":false,"crosshair_placement":"head_level","in_gunfight":false,"recent_death":false,"kill_feed_events":"Teammate eliminated by enemy Jett"}"""

# --- Schema ---
class GameContext(BaseModel):
    should_coach: bool = Field(description="Whether anything worth coaching is happening")
    agent: Literal["gamesense", "mechanics", "mental", "none"] = Field(
        description="Which specialist agent should handle this"
    )
    urgency: Literal["low", "medium", "high", "critical"] = Field(
        description="How urgently the player needs coaching"
    )
    game_state: str = Field(description="A 1-2 sentence rich summary of the exact situation")
    narrative_update: str = Field(description="What specifically changed since the previous context")
    phase: Literal["buy", "live", "post_round", "unknown"] = Field(
        description="Current phase of the round"
    )
    round_number: int = Field(description="Current round number if visible, else 0")
    player_health: int = Field(description="Player HP 0-150, or -1 if unknown")
    player_armor: bool = Field(description="Whether player has armor equipped")
    player_credits: int = Field(description="Credits visible in buy phase, else -1")
    player_weapon: str = Field(description="Current weapon name or 'unknown'")
    player_alive: bool = Field(description="Whether the player is alive")
    player_position: str = Field(description="Where on map player appears to be, or 'unknown'")
    spike_status: Literal["planted", "carried", "dropped", "unknown"] = Field(
        description="Current spike status"
    )
    teammates_alive: int = Field(description="Number of teammates alive if visible, else -1")
    enemies_alive: int = Field(description="Number of enemies alive if visible, else -1")
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
    print(f"[SpectAI] Phase: {ctx.phase} | Round: {ctx.round_number}")
    print(f"[SpectAI] State: {ctx.game_state}")
    print(f"[SpectAI] Update: {ctx.narrative_update}")
    print(f"[SpectAI] Agent: {ctx.agent} | Urgency: {ctx.urgency}")
    print(f"[SpectAI] Health: {ctx.player_health} | Armor: {ctx.player_armor} | Weapon: {ctx.player_weapon}")
    print(f"[SpectAI] Position: {ctx.player_position} | Spike: {ctx.spike_status}")
    print(f"[SpectAI] Teammates: {ctx.teammates_alive} | Enemies: {ctx.enemies_alive} | Visible: {ctx.visible_enemies}")
    print(f"[SpectAI] Gunfight: {ctx.in_gunfight} | Shooting: {ctx.is_shooting} | Moving: {ctx.is_moving}")
    print(f"[SpectAI] Crosshair: {ctx.crosshair_placement} | Recent death: {ctx.recent_death}")
    if ctx.kill_feed_events:
        print(f"[SpectAI] Killfeed: {ctx.kill_feed_events}")
    print(f"[SpectAI] Should coach: {ctx.should_coach}")
    print(f"[SpectAI] ─────────────────────────────────")


# --- Core ---
async def run_spect_ai():
    print("[SpectAI] Starting vision layer (Live API)...")
    screen_capture = WindowCapture(TARGET_WINDOW)
    last_coached = 0.0
    last_ctx: GameContext | None = None

    async with client.aio.live.connect(model=MODEL, config=LIVE_CONFIG) as session:
        print("[SpectAI] Live session connected.")

        while True:
            now = asyncio.get_event_loop().time()

            if (now - last_coached) < COOLDOWN_SECONDS:
                await asyncio.sleep(0.5)
                continue

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

                # Send prompt as text input
                if last_ctx:
                    prompt = (
                        f"Previous context (~{COOLDOWN_SECONDS}s ago):\n"
                        f"{last_ctx.model_dump_json()}\n\n"
                        "Analyze the CURRENT frame. Focus on changes. Respond with JSON only."
                    )
                else:
                    prompt = "Extract the current game context from this frame. Respond with JSON only."

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
                        last_ctx = ctx
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