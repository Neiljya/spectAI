import asyncio
import json
import os
import re
import logging
import threading
import warnings
import dotenv
from collections import deque
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Callable

from stream import WindowCapture
from hud import ValorantHUDScanner

warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
logging.disable(logging.WARNING)

# --- HUD Smoothing & Config ---
_HUD_NUMERIC_FIELDS = {"hp", "shield", "credits", "loaded_ammo", "stored_ammo", "my_team_score", "enemy_team_score"}
_HUD_STRING_FIELDS = {"match_timer", "game_phase"}
HUD_SMOOTHING_WINDOW = 5

class HUDSmoother:
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

dotenv.load_dotenv()
TARGET_WINDOW = "VALORANT  "
CAPTURE_FPS = 1
NUDGE_INTERVAL = 6
MODEL = "gemini-3.1-flash-live-preview"

SYSTEM_PROMPT = """You are SpectAI, a real-time competitive FPS coaching system (Valorant).
You watch the video stream and track HUD data. Every few seconds, you will be nudged to analyze the situation.

Prioritize player positioning, map control, gamesense. Focus less on weapon choice. Positioning and
awareness are key!

OUTPUT RULES:
- Respond with ONLY a valid JSON object. No markdown, no code blocks, no extra text.
- Pay attention to positioning (minimap data, player exposure) in relation to the game state (post plant, defense, clearing)
- Give advice if the player might be neglecting flanks, has bad positioning (cant fall back to cover easily or has no util to)
- Give advice when suspecting if enemies might have rotated from a site or not based on the timer, player count, and typical enemy behavior.
- Tell player specific places to position themselves based on game state and map knowledge (e.g. "Hold an aggressive angle like B Main to punish common rushes" or "Consider playing close to the box for cover after planting")
- Decide if the player needs immediate, actionable coaching based on the current context (e.g., low ammo, bad crosshair placement, enemy rotation spotted, economy failure).
- If no immediate advice is needed, set should_coach to false.
- Use this exact JSON format:
{"should_coach": true, "advice": "Your crosshair is too low, aim at head level. Also, reload your Vandal before peeking."}
"""

# --- Schema ---
class CoachResponse(BaseModel):
    should_coach: bool = Field(description="Whether anything worth coaching is happening right now.")
    advice: Optional[str] = Field(None, description="Short, actionable coaching callout if should_coach is true. Null otherwise.")

# --- Parsing ---
def parse_coach_response(text: str) -> CoachResponse | None:
    text = text.strip()
    try:
        return CoachResponse.model_validate_json(text)
    except (ValidationError, json.JSONDecodeError):
        pass

    match = re.search(r'`{3}(?:json)?\s*(.*?)\s*`{3}', text, re.DOTALL)
    if match:
        try:
            return CoachResponse.model_validate_json(match.group(1))
        except (ValidationError, json.JSONDecodeError):
            pass

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try:
            return CoachResponse.model_validate_json(text[start:end + 1])
        except (ValidationError, json.JSONDecodeError):
            pass

    return None


class SpectAI:
    def __init__(self, response_callback: Callable[[str], None]):
        self._response_callback = response_callback
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

    def wait(self):
        try:
            while self._thread and self._thread.is_alive():
                self._thread.join(timeout=1)
        except KeyboardInterrupt:
            self.stop()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._run())
        finally:
            self._loop.close()
            self._loop = None

    async def _run(self):
        print("[SpectAI] Starting vision layer (Live API)...")
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={"api_version": "v1alpha"})

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=SYSTEM_PROMPT)]),
            temperature=0.1,
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        screen_capture = WindowCapture(TARGET_WINDOW)
        hud_scanner = ValorantHUDScanner()
        hud_smoother = HUDSmoother()
        shared_context = {"hud_text": ""}
        coaching_history = deque(maxlen=3)

        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("[SpectAI] Live session connected.")

            push_task = asyncio.create_task(
                self._push_info_task(session, screen_capture, hud_scanner, hud_smoother, shared_context)
            )
            nudge_task = asyncio.create_task(
                self._nudge_and_receive_task(session, shared_context, coaching_history)
            )

            await self._stop_event.wait()

            push_task.cancel()
            nudge_task.cancel()
            await asyncio.gather(push_task, nudge_task, return_exceptions=True)

        print("[SpectAI] Session closed.")

    async def _push_info_task(self, session, screen_capture, hud_scanner, hud_smoother, shared_context):
        while True:
            frame = await asyncio.to_thread(screen_capture.capture)
            if frame is not None:
                jpeg_bytes = await asyncio.to_thread(screen_capture.frame_to_jpeg, frame)
                try:
                    await session.send_realtime_input(
                        video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                    )
                except Exception as e:
                    print(f"Error sending frame: {e}")

                try:
                    raw_hud = await asyncio.to_thread(hud_scanner.parse_hud, frame)
                    hud_smoother.update(raw_hud)
                    smoothed = hud_smoother.get_smoothed()
                    shared_context["hud_text"] = (
                        f"HP:{smoothed.get('hp')} | "
                        f"Ammo:{smoothed.get('loaded_ammo')}/{smoothed.get('stored_ammo')} | "
                        f"Creds:{smoothed.get('credits')}"
                    )
                except Exception:
                    pass

            await asyncio.sleep(1.0 / CAPTURE_FPS)

    def _extract_text_from_msg(self, msg) -> str:
        if not msg.server_content:
            return ""
        if msg.server_content.output_transcription:
            return msg.server_content.output_transcription.text or ""
        if msg.server_content.model_turn:
            return "".join(p.text for p in msg.server_content.model_turn.parts if p.text)
        return ""

    async def _collect_turn_response(self, session) -> str:
        full_response = ""
        async for msg in session.receive():
            full_response += self._extract_text_from_msg(msg)
            if msg.server_content and msg.server_content.turn_complete:
                break
        return full_response

    def _handle_coach_response(self, full_response: str, coaching_history: deque):
        ctx = parse_coach_response(full_response)
        if not ctx:
            print(f"\n[Parse Failed]: {full_response.strip()}")
            return
        if ctx.should_coach and ctx.advice:
            coaching_history.append(ctx.advice)
            self._response_callback(ctx.advice)
        else:
            print(".", end="", flush=True)

    async def _nudge_and_receive_task(self, session, shared_context, coaching_history):
        while True:
            await asyncio.sleep(NUDGE_INTERVAL)

            history_text = " | ".join(coaching_history) if coaching_history else "None"
            nudge_prompt = (
                f"Analyze. Current HUD context: {shared_context['hud_text']}. "
                f"Recent advice given: {history_text}. "
                "Do NOT repeat recent advice unless the situation has drastically worsened. "
                "Respond strictly in JSON."
            )

            try:
                await session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(text=nudge_prompt)]
                    ),
                    turn_complete=True
                )

                full_response = await self._collect_turn_response(session)
                if full_response:
                    self._handle_coach_response(full_response, coaching_history)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"\n[SpectAI] Nudge/Receive error: {e}")


if __name__ == "__main__":
    def on_response(advice: str):
        print(f"\n[COACH]: {advice}")

    ai = SpectAI(response_callback=on_response)
    ai.start()
    ai.wait()