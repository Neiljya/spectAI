import asyncio
import os
import dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal
from stream import WindowCapture

# --- Config ---
dotenv.load_dotenv()
TARGET_WINDOW = "VALORANT  "
CAPTURE_FPS = 2
COOLDOWN_SECONDS = 8
MODEL = "gemini-2.5-flash" # Consider switching to Gemini 2.0 Flash Experimental or Multimodal Live API for streaming

SYSTEM_PROMPT = """
You are SpectAI, the vision layer of a real-time competitive FPS coaching system.
You analyze sequences of game screenshots and extract structured information to pass to specialist coaching agents.

Your job is to be a precise observer — not a coach. Extract what you see accurately.
You will be provided with the CURRENT screenshot, and potentially the PREVIOUS game state from ~8 seconds ago.
Use the previous state to infer what has changed (e.g., did they just get a kill? Did they rotate?).

Be concise but descriptive. game_state should provide a rich tactical summary.
"""

# --- Schema ---
class GameContext(BaseModel):
    # Routing
    should_coach: bool = Field(description="Whether anything worth coaching is happening")
    agent: Literal["gamesense", "mechanics", "mental", "none"] = Field(
        description="Which specialist agent should handle this"
    )
    urgency: Literal["low", "medium", "high", "critical"] = Field(
        description="How urgently the player needs coaching"
    )

    # Rich narrative context
    game_state: str = Field(description="A 1-2 sentence rich summary of the exact situation and recent changes. (e.g. 'Player rotated to B site and is holding an off angle with an Operator. Just secured a kill.')")
    narrative_update: str = Field(description="What specifically changed since the previous context provided (if any).")
    
    # Game state
    phase: Literal["buy", "live", "post_round", "unknown"] = Field(
        description="Current phase of the round"
    )
    round_number: int = Field(description="Current round number if visible, else 0")

    # Player state
    player_health: int = Field(description="Player HP 0-150, or -1 if unknown")
    player_armor: bool = Field(description="Whether player has armor equipped")
    player_credits: int = Field(description="Credits visible in buy phase, else -1")
    player_weapon: str = Field(description="Current weapon name or 'unknown'")
    player_alive: bool = Field(description="Whether the player is alive")

    # Tactical context — gamesense agent
    player_position: str = Field(description="Where on map player appears to be, or 'unknown'")
    spike_status: Literal["planted", "carried", "dropped", "unknown"] = Field(
        description="Current spike status"
    )
    teammates_alive: int = Field(description="Number of teammates alive if visible, else -1")
    enemies_alive: int = Field(description="Number of enemies alive if visible, else -1")
    visible_enemies: int = Field(description="Number of enemies currently on screen")

    # Mechanical context — mechanics agent
    is_shooting: bool = Field(description="Whether player appears to be firing")
    is_moving: bool = Field(description="Whether player appears to be moving")
    crosshair_placement: Literal["head_level", "too_low", "too_high", "off_angle", "unknown"] = Field(
        description="Where crosshair is positioned relative to where enemies would be"
    )
    in_gunfight: bool = Field(description="Whether a gunfight is actively happening")

    # Mental context — mental agent
    recent_death: bool = Field(description="Whether death screen or respawn is visible")
    kill_feed_events: str = Field(description="Brief summary of recent killfeed, or empty string")


# --- Client ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GENERATE_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    temperature=0.1,
    # max_output_tokens=512,
    response_mime_type="application/json",
    response_schema=GameContext,
)

# --- Core ---
async def get_game_context(
    jpeg_bytes: bytes,
    previous_context: GameContext | None = None
) -> GameContext | None:
    
    contents = [
        types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")
    ]
    
    if previous_context:
        prompt_str = (
            f"Here is the context we extracted ~8 seconds ago:\n"
            f"{previous_context.model_dump_json()}\n\n"
            f"Analyze the CURRENT screenshot. Focus on what has changed or remained the same. Provide an updated context."
        )
    else:
        prompt_str = "Extract the current game context from this screenshot."
        
    contents.append(types.Part.from_text(text=prompt_str))

    try:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=contents,
            config=GENERATE_CONFIG,
        )
    except Exception as e:
        print(f"[SpectAI] API call failed: {e}")
        return None

    if not response.candidates:
        print(f"[SpectAI] Response blocked: {response.prompt_feedback}")
        return None

    if response.parsed:
        return response.parsed

    print(f"[SpectAI] Structured parse failed. Finish reason: {response.candidates[0].finish_reason}")
    print(f"[SpectAI] Raw output: {response.text[:200]}")
    return None

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

async def run_spect_ai():
    print("[SpectAI] Starting vision layer...")
    screen_capture = WindowCapture(TARGET_WINDOW)
    interval = 1.0 / CAPTURE_FPS
    last_coached = 0.0
    last_ctx: GameContext | None = None

    while True:
        loop_start = asyncio.get_event_loop().time()
        frame = screen_capture.capture()

        if frame is not None and (loop_start - last_coached) >= COOLDOWN_SECONDS:
            try:
                jpeg_bytes = screen_capture.frame_to_jpeg(frame)
                ctx = await get_game_context(jpeg_bytes, previous_context=last_ctx)

                if ctx:
                    log_context(ctx)
                    last_ctx = ctx
                    # TODO: pass ctx to agent router

            except Exception as e:
                print(f"[SpectAI] Unexpected error: {e}")
            finally:
                last_coached = asyncio.get_event_loop().time()

        await asyncio.sleep(max(0, interval - (asyncio.get_event_loop().time() - loop_start)))

if __name__ == "__main__":
    asyncio.run(run_spect_ai())