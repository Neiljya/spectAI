from stream import WindowCapture
from pydantic import BaseModel
from typing import Literal
import asyncio
import ollama
import dotenv
import base64

dotenv.load_dotenv()

TARGET_WINDOW = "VALORANT  "
CAPTURE_FPS = 2
COOLDOWN_SECONDS = 8

OLLAMA_MODEL = "gemma4:e2b"
# OLLAMA_MODEL = "gemma4:26b-a4b-instruct-q4_K_M"

SYSTEM_PROMPT = """
You are SpectAI, an elite real-time competitive FPS coach watching
a player's screen live. You receive a continuous stream of game frames.

Your job:
- Analyze the current game state from the frames
- Identify the single most important actionable insight RIGHT NOW
- Be specific to what you actually see, never give generic advice

Coaching rules:
- Prioritize: immediate threats > positioning > economy > mechanics
- Keep callouts under 15 words, calm and direct
- If nothing important is happening, set should_coach to false
- Never repeat advice you just gave in the same round
- Speak as if you're in the player's ear mid-game, no preamble

Respond ONLY with valid JSON matching this exact schema:
{
    "should_coach": true or false,
    "agent": "gamesense" | "mechanics" | "mental" | "none",
    "urgency": "low" | "medium" | "high" | "critical",
    "game_state": "<one sentence description>",
    "callout": "<coaching tip under 15 words, or empty string>"
}
"""


class CoachingResponse(BaseModel):
    should_coach: bool
    agent: Literal["gamesense", "mechanics", "mental", "none"]
    urgency: Literal["low", "medium", "high", "critical"]
    game_state: str
    callout: str


async def analyze_frame_ollama(jpeg_bytes: bytes, last_callout: str | None) -> CoachingResponse | None:
    b64_image = base64.b64encode(jpeg_bytes).decode()

    user_content = (
        f'Analyze this game frame. Do not repeat: "{last_callout}"'
        if last_callout
        else "Analyze this game frame."
    )

    response = await asyncio.to_thread(
        ollama.chat,
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "images": [b64_image], "content": user_content},
        ],
        format="json",
        options={
            "temperature": 0.2,
            "num_predict": 256,
        },
    )

    raw = response["message"]["content"].strip()
    print(f"[SpectAI] Raw Ollama response: '{raw}'")  # add this
    
    if not raw:
        print("[SpectAI] Empty response from Ollama")
        return None
    
    try:
        return CoachingResponse.model_validate_json(raw)
    except Exception as e:
        print(f"[SpectAI] JSON parse error: {e}")
        print(f"[SpectAI] Raw was: {raw[:500]}")
        return None

async def run_spect_ai():
    print(f"[SpectAI] Starting Gemma 4 local coaching pipeline ({OLLAMA_MODEL})...")

    screen_capture = WindowCapture(TARGET_WINDOW)
    interval = 1.0 / CAPTURE_FPS
    last_coached = 0.0
    last_callout: str | None = None

    print("[SpectAI] Entering main loop...")  # add this

    while True:
        loop = asyncio.get_event_loop()
        start = loop.time()

        frame = screen_capture.capture()
        print(f"[SpectAI] Frame: {frame is not None}, shape: {frame.shape if frame is not None else 'None'}")  # add this

        if frame is not None:
            now = loop.time()
            print(f"[SpectAI] Time since last coached: {now - last_coached:.1f}s / {COOLDOWN_SECONDS}s")  # add this

            if now - last_coached >= COOLDOWN_SECONDS:
                try:
                    print("[SpectAI] Sending frame to Ollama...")  # add this
                    jpeg_bytes = screen_capture.frame_to_jpeg(frame)
                    result = await analyze_frame_ollama(jpeg_bytes, last_callout)
                    print(f"[SpectAI] Got result: {result}")  # add this

                    if result:
                        print(f"[SpectAI] Game state: {result.game_state}")
                        print(f"[SpectAI] Agent: {result.agent} | Urgency: {result.urgency}")

                        if result.should_coach and result.callout and result.callout != last_callout:
                            print(f"\n[SpectAI] {result.callout}\n")
                            last_callout = result.callout
                            # TODO: pipe callout to Fetch.ai / ElevenLabs

                    last_coached = now

                except Exception as e:
                    print(f"[SpectAI] Error: {e}")

        elapsed = loop.time() - start
        await asyncio.sleep(max(0, interval - elapsed))


if __name__ == "__main__":
    asyncio.run(run_spect_ai())
