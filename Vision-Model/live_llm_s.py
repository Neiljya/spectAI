import asyncio
import json
import os
import re
import sys
import ctypes
import tempfile
import threading
import logging
import warnings
import dotenv
from collections import deque
from dataclasses import asdict
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Callable
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

warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
logging.disable(logging.WARNING)

dotenv.load_dotenv()
TARGET_WINDOW = "VALORANT  "
CAPTURE_FPS = 2
COOLDOWN_SECONDS = 8
GAME_STATE_REFRESH_SECONDS = 10
MAX_HISTORY = 10
MODEL = "gemini-2.5-flash-native-audio-latest"

PTT_KEY = kb.Key.f9 if VOICE_AVAILABLE else None
MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1

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


SYSTEM_PROMPT = """You are SpectAI, an elite real-time Valorant coach with vision access to the player's screen.
You watch game frames and deliver precise, actionable coaching in the moment.
Use the HUD: health, ammo, top bar (agent icons, ult status, time, scores), killfeed, and minimap.
IMPORTANT: To identify the player's agent, look at the top bar icon or the center of the minimap.
You will sometimes receive a RECENT COACHING HISTORY buffer. Use it to avoid repeating yourself.
You may also receive LIVE GAME DATA from the Valorant API. Use it for accurate map, agent, and team info.
When the player asks a voice question (marked PLAYER VOICE QUESTION), answer in 1-2 sentences max — direct and actionable. Do NOT respond with JSON for voice questions.

OUTPUT RULES for screen analysis:
- Respond with ONLY a valid JSON object. No markdown, no code blocks, no extra text.
- If there is nothing actionable, set should_coach to false and omit advice.
- Use this exact format:
{"should_coach": true, "advice": "Hold B Main — spike is planted and your team has a 3v1 with 40s left."}
"""


class CoachResponse(BaseModel):
    should_coach: bool = Field(description="Whether there is an actionable coaching moment right now.")
    advice: Optional[str] = Field(None, description="Short, actionable coaching callout. Null if should_coach is false.")


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


def build_game_context_summary(val_client: ValorantLocalClient, resolver: ValorantResolver) -> tuple[str, int, int] | None:
    try:
        raw_state = val_client.get_full_game_state()
    except Exception:
        return None

    if raw_state.phase == GamePhase.MENUS:
        return None

    resolved = resolver.resolve_game_state(asdict(raw_state))
    lines = [f"Phase: {resolved.phase}"]

    my_puuid = resolved.puuid
    my_team_id = None
    valid_players = [p for p in resolved.players if p.puuid and p.agent and p.agent.name != "Unknown"]

    for p in valid_players:
        if p.puuid == my_puuid:
            my_team_id = p.team_id
            break

    allies, enemies = [], []
    for p in valid_players:
        if p.puuid == my_puuid:
            continue
        name = p.agent.name if p.agent else "Unknown"
        role = p.agent.role if p.agent else ""
        entry = f"{name} ({role})" if role else name
        (allies if my_team_id and p.team_id == my_team_id else enemies).append(entry)

    lines.append(f"Teammates ({len(allies)}): {', '.join(allies)}" if allies else "Teammates: 0")
    lines.append(f"Enemies ({len(enemies)}): {', '.join(enemies)}" if enemies else "Enemies: 0")
    lines.append(f"Total Players: {len(valid_players)}")

    if resolved.map and resolved.map.callouts:
        callout_names = sorted(set(c.region_name for c in resolved.map.callouts))
        lines.append(f"Map callouts: {', '.join(callout_names)}")

    return "\n".join(lines), len(allies), len(enemies)


def start_ptt_listener(loop: asyncio.AbstractEventLoop, voice_queue: asyncio.Queue):
    if not VOICE_AVAILABLE:
        return

    recording = False
    audio_chunks: list = []

    def audio_callback(indata, _frames, _time, _status):
        if recording:
            audio_chunks.append(indata.copy())

    def on_press(key):
        nonlocal recording, audio_chunks
        if key == PTT_KEY and not recording:
            recording = True
            audio_chunks = []
            print("[SpectAI] Listening... (release F9 to send)")

    def on_release(key):
        nonlocal recording
        if key == PTT_KEY and recording:
            recording = False
            if audio_chunks:
                pcm = (np.concatenate(audio_chunks, axis=0) * 32767).astype(np.int16).tobytes()
                asyncio.run_coroutine_threadsafe(voice_queue.put(pcm), loop)
                print("[SpectAI] Voice query received — processing...")

    with sd.InputStream(samplerate=MIC_SAMPLE_RATE, channels=MIC_CHANNELS,
                        dtype='float32', callback=audio_callback):
        with kb.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()


class SpectAI:
    def __init__(self, response_callback: Callable[[str], None]):
        self._response_callback = response_callback
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._session = None

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

    def inject_voice_query(self, pcm_bytes: bytes) -> str:
        """Trigger an on-demand voice query on the live session. Speaks and returns the response."""
        if not self._loop or not self._loop.is_running():
            return ""
        future = asyncio.run_coroutine_threadsafe(
            self._handle_voice_query_async(pcm_bytes), self._loop
        )
        try:
            return future.result(timeout=30)
        except Exception:
            return ""

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
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
            ),
        )

        screen_capture = WindowCapture(TARGET_WINDOW)

        val_client = None
        resolver = None
        try:
            val_client = ValorantLocalClient()
            resolver = ValorantResolver()
            print("[SpectAI] Valorant API connected — game context enabled.")
        except Exception as e:
            print(f"[SpectAI] Valorant API unavailable ({e}) — running vision-only mode.")

        voice_queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        if VOICE_AVAILABLE:
            threading.Thread(
                target=start_ptt_listener, args=(loop, voice_queue), daemon=True
            ).start()
            print("[SpectAI] Push-to-talk ready — hold F9 to ask a question.")

        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("[SpectAI] Live session connected.")
            self._session = session

            analysis_task = asyncio.create_task(
                self._analysis_loop(session, screen_capture, val_client, resolver, voice_queue)
            )

            await self._stop_event.wait()

            analysis_task.cancel()
            await asyncio.gather(analysis_task, return_exceptions=True)
            self._session = None

        print("[SpectAI] Session closed.")

    async def _analysis_loop(
        self,
        session,
        screen_capture: WindowCapture,
        val_client,
        resolver,
        voice_queue: asyncio.Queue,
    ):
        last_coached = 0.0
        history_buffer: list[str] = []
        game_context_summary: str | None = None
        max_allies, max_enemies = 4, 5
        last_game_state_fetch = 0.0
        loop = asyncio.get_event_loop()

        while True:
            now = loop.time()

            # Voice query takes priority over screen analysis
            if not voice_queue.empty():
                pcm_bytes = await voice_queue.get()
                await self._handle_voice_query_async(pcm_bytes)
                last_coached = loop.time()
                continue

            if (now - last_coached) < COOLDOWN_SECONDS:
                await asyncio.sleep(0.1)
                continue

            # Refresh Valorant API context periodically
            if val_client and resolver and (now - last_game_state_fetch) >= GAME_STATE_REFRESH_SECONDS:
                try:
                    result = build_game_context_summary(val_client, resolver)
                    last_game_state_fetch = now
                    if result:
                        game_context_summary, max_allies, max_enemies = result
                        print("[SpectAI] Game context refreshed.")
                except Exception:
                    pass

            frame = await asyncio.to_thread(screen_capture.capture)
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            try:
                jpeg_bytes = await asyncio.to_thread(screen_capture.frame_to_jpeg, frame)
                await session.send_realtime_input(
                    video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                )

                parts = []
                if game_context_summary:
                    parts.append(f"LIVE GAME DATA (from Valorant API):\n{game_context_summary}")
                if history_buffer:
                    history_lines = "\n".join(f"T-{len(history_buffer)-i}: {h}" for i, h in enumerate(history_buffer))
                    parts.append(f"RECENT COACHING HISTORY:\n{history_lines}")
                parts.append("Analyze the CURRENT frame. Respond with JSON only.")

                await session.send_realtime_input(text="\n\n".join(parts))

                full_text = await self._collect_turn_response(session)
                if full_text:
                    ctx = parse_coach_response(full_text)
                    if ctx:
                        if ctx.should_coach and ctx.advice:
                            loop.run_in_executor(None, _speak_sync, ctx.advice)
                            self._response_callback(ctx.advice)
                            history_buffer.append(ctx.advice)
                            if len(history_buffer) > MAX_HISTORY:
                                history_buffer.pop(0)
                        else:
                            print(".", end="", flush=True)
                    else:
                        print(f"\n[Parse Failed]: {full_text[:200]}")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[SpectAI] Error: {e}")
            finally:
                last_coached = loop.time()

    async def _handle_voice_query_async(self, pcm_bytes: bytes) -> str:
        """Send player voice to Gemini, speak the response via TTS, and return it."""
        if self._session is None:
            return ""

        session = self._session
        await session.send_realtime_input(activity_start=types.ActivityStart())
        await session.send_realtime_input(
            audio=types.Blob(data=pcm_bytes, mime_type=f"audio/pcm;rate={MIC_SAMPLE_RATE}")
        )
        await session.send_realtime_input(activity_end=types.ActivityEnd())

        full_text = await self._collect_turn_response(session)
        if full_text:
            sentences = re.split(r'(?<=[.!?])\s+', full_text.strip())
            spoken = sentences[-1] if sentences else full_text
            print(f"[SpectAI] Voice response: {spoken}")
            asyncio.get_event_loop().run_in_executor(None, _speak_sync, spoken)
            return spoken

        return ""

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


if __name__ == "__main__":
    def on_response(advice: str):
        print(f"\n[COACH]: {advice}")

    ai = SpectAI(response_callback=on_response)
    ai.start()
    ai.wait()
