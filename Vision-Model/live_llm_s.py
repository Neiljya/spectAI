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
import time
import dotenv
import httpx
import numpy as np
from collections import deque
from dataclasses import asdict

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Callable

from stream import WindowCapture
from hud import ValorantHUDScanner
from valorant_local_api import ValorantLocalClient, GamePhase
from valorant_resolver import ValorantResolver

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

# --- Configuration & Constants ---
dotenv.load_dotenv()
TARGET_WINDOW = "VALORANT  "
CAPTURE_FPS = 1
NUDGE_INTERVAL = 6
GAME_STATE_REFRESH_SECONDS = 10
MODEL = "gemini-3.1-flash-live-preview"

PTT_KEY = kb.Key.f9 if VOICE_AVAILABLE else None
MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1

_ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
_ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George
_tts_lock = threading.Lock()

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


# --- Text-to-Speech & Voice Helpers ---
def _play_mp3(path: str):
    print(f"[Voice Telemetry] Playing MP3 audio via MCI from {path}...")
    if sys.platform == "win32":
        mci = ctypes.windll.winmm.mciSendStringW
        mci(f'open "{path}" type mpegvideo alias spectai_tts', None, 0, None)
        mci('play spectai_tts wait', None, 0, None)
        mci('close spectai_tts', None, 0, None)
    print("[Voice Telemetry] Audio playback complete.")


def _speak_sync(text: str):
    if not _ELEVENLABS_KEY or not text.strip():
        print("[Voice Telemetry] Aborting TTS: No ElevenLabs key or empty text.")
        return
        
    print(f"[Voice Telemetry] Acquiring TTS lock to speak: '{text[:30]}...'")
    with _tts_lock:
        print("[Voice Telemetry] TTS lock acquired. Sending POST request to ElevenLabs API...")
        start_time = time.time()
        try:
            resp = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{_ELEVENLABS_VOICE}",
                headers={"xi-api-key": _ELEVENLABS_KEY, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": "eleven_flash_v2_5",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            elapsed = time.time() - start_time
            print(f"[Voice Telemetry] ElevenLabs API responded successfully in {elapsed:.2f} seconds.")
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name
            
            print("[Voice Telemetry] Audio saved to temp file. Routing to playback...")
            _play_mp3(tmp_path)
            
        except httpx.ReadTimeout:
            elapsed = time.time() - start_time
            print(f"[Voice Telemetry] ERROR: ElevenLabs API read operation timed out after {elapsed:.2f} seconds.")
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[Voice Telemetry] ERROR: TTS request failed after {elapsed:.2f} seconds. Details: {e}")


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
            print("\n[Voice Telemetry] PTT Key pressed. Recording audio...")

    def on_release(key):
        nonlocal recording
        if key == PTT_KEY and recording:
            recording = False
            if audio_chunks:
                print(f"[Voice Telemetry] PTT Key released. Captured {len(audio_chunks)} audio chunks. Queuing for AI...")
                pcm = (np.concatenate(audio_chunks, axis=0) * 32767).astype(np.int16).tobytes()
                asyncio.run_coroutine_threadsafe(voice_queue.put(pcm), loop)
            else:
                print("[Voice Telemetry] PTT Key released, but no audio was captured.")

    with sd.InputStream(samplerate=MIC_SAMPLE_RATE, channels=MIC_CHANNELS, dtype='float32', callback=audio_callback):
        with kb.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()


# --- Game State Resolvers ---
def _classify_players(valid_players, my_puuid: str, my_team_id) -> tuple[list, list]:
    allies, enemies = [], []
    for p in valid_players:
        if p.puuid == my_puuid:
            continue
        name = p.agent.name if p.agent else "Unknown"
        role = p.agent.role if p.agent else ""
        entry = f"{name} ({role})" if role else name
        (allies if my_team_id and p.team_id == my_team_id else enemies).append(entry)
    return allies, enemies


def build_game_context_summary(val_client: ValorantLocalClient, resolver: ValorantResolver) -> str | None:
    try:
        raw_state = val_client.get_full_game_state()
    except Exception:
        return None

    if raw_state.phase == GamePhase.MENUS:
        return None

    resolved = resolver.resolve_game_state(asdict(raw_state))
    valid_players = [p for p in resolved.players if p.puuid and p.agent and p.agent.name != "Unknown"]

    my_puuid = resolved.puuid
    my_team_id = next((p.team_id for p in valid_players if p.puuid == my_puuid), None)
    my_agent = next((p.agent.name for p in valid_players if p.puuid == my_puuid), None)
    allies, enemies = _classify_players(valid_players, my_puuid, my_team_id)

    lines = [f"Phase: {resolved.phase}"]
    if resolved.map:
        lines.append(f"Map: {resolved.map.name}")
    if my_agent:
        lines.append(f"Your agent: {my_agent}")
    lines.append(f"Teammates ({len(allies)}): {', '.join(allies)}" if allies else "Teammates: 0")
    lines.append(f"Enemies ({len(enemies)}): {', '.join(enemies)}" if enemies else "Enemies: 0")
    lines.append(f"Total Players: {len(valid_players)}")

    if resolved.map and resolved.map.callouts:
        callout_names = sorted({c.region_name for c in resolved.map.callouts})
        lines.append(f"Map callouts: {', '.join(callout_names)}")

    return "\n".join(lines)


# --- System Prompt & Models ---
_SYSTEM_PROMPT_BASE = """You are SpectAI, a real-time competitive FPS coaching system (Valorant).
You watch the video stream, track HUD data, and receive LIVE GAME DATA. Every few seconds, you will be nudged to analyze the situation.

Prioritize player positioning, map control, gamesense. Focus less on weapon choice. Positioning and awareness are key!
IMPORTANT: To identify the player's agent, look at the top bar icon, the center of the minimap, or the LIVE GAME DATA.

OUTPUT RULES:
- Respond with ONLY a valid JSON object. No markdown, no code blocks, no extra text.
- Pay attention to positioning (minimap data, player exposure) in relation to the game state (post plant, defense, clearing)
- Give advice if the player might be neglecting flanks, has bad positioning (cant fall back to cover easily or has no util to)
- Give advice when suspecting if enemies might have rotated from a site or not based on the timer, player count, and typical enemy behavior.
- Tell player specific places to position themselves based on game state and map knowledge (e.g. "Hold an aggressive angle like B Main to punish common rushes" or "Consider playing close to the box for cover after planting")
- Decide if the player needs immediate, actionable coaching based on the current context (e.g., low ammo, bad crosshair placement, enemy rotation spotted, economy failure).
- If no immediate advice is needed, set should_coach to false.
- Use this exact JSON format:
{{"should_coach": true, "advice": "Your crosshair is too low, aim at head level. Also, reload your Vandal before peeking."}}

VOICE EXCEPTION: If the user speaks to you directly (via audio), answer in 1-2 sentences max — direct and actionable. Do NOT respond with JSON for voice questions.

PLAY RECOMMENDATION: When the user asks which play to run (e.g. "what play should I make?", "what should we execute?"), follow this exact process:
1. Note the current map and the FULL team composition from LIVE GAME DATA (Your agent + all Teammates).
2. Scan the Available plays below for the current map. For each play, count how many of its agents are present on the actual team.
3. AGENT MATCH REQUIRED: Only recommend a play from the list if at least 2 of its agents match agents on the actual team. Pick the play with the highest overlap.
4. If a matching play exists: respond in 1-2 natural sentences recommending it and explaining the agent fit, then on a new line append: [SHOW_PLAY:MapName:PlayName] using exact names from the list.
5. If NO play has sufficient agent overlap (e.g. solo lobby, unusual comp, or map not in the list): do NOT output [SHOW_PLAY:]. Instead, describe a 1-2 sentence custom strategy tailored to the actual agents and their abilities.

{plays_summary}
"""

def _build_system_prompt(plays_summary: str) -> str:
    return _SYSTEM_PROMPT_BASE.format(plays_summary=plays_summary)

class CoachResponse(BaseModel):
    should_coach: bool = Field(description="Whether anything worth coaching is happening right now.")
    advice: Optional[str] = Field(None, description="Short, actionable coaching callout if should_coach is true. Null otherwise.")

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
    def __init__(
        self,
        response_callback: Callable[[str], None],
        voice_callback: Callable[[str], None] = None,
        play_callback: Callable[[str, str], None] = None,
        plays_summary: str = "",
    ):
        self._response_callback = response_callback
        self._voice_callback = voice_callback
        self._play_callback = play_callback
        self._plays_summary = plays_summary
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._session = None

        # State routing variables
        self._expecting_voice_response = False
        self._voice_query_timestamp = 0.0
        self._last_voice_time = 0.0

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
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        system_prompt = _build_system_prompt(self._plays_summary)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part.from_text(text=system_prompt)]),
            temperature=0.1,
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
            ),
        )

        screen_capture = WindowCapture(TARGET_WINDOW)
        hud_scanner = ValorantHUDScanner()
        hud_smoother = HUDSmoother()
        
        shared_context = {"hud_text": "None", "api_text": "None"}
        coaching_history = deque(maxlen=3)
        voice_queue: asyncio.Queue = asyncio.Queue()

        val_client = None
        resolver = None
        try:
            val_client = ValorantLocalClient()
            resolver = ValorantResolver()
            print("[SpectAI] Valorant API connected — game context enabled.")
        except Exception as e:
            print(f"[SpectAI] Valorant API unavailable ({e}) — running vision-only mode.")

        if VOICE_AVAILABLE:
            loop = asyncio.get_event_loop()
            threading.Thread(
                target=start_ptt_listener, args=(loop, voice_queue), daemon=True
            ).start()
            print("[SpectAI] Push-to-talk ready — hold F9 to ask a question.")

        # --- AUTO-RECONNECT LOOP ---
        while not self._stop_event.is_set():
            try:
                async with client.aio.live.connect(model=MODEL, config=config) as session:
                    print("[SpectAI] Live session connected.")
                    self._session = session

                    receive_task = asyncio.create_task(self._continuous_receive_task(session, coaching_history))
                    push_task = asyncio.create_task(self._push_info_task(session, screen_capture, hud_scanner, hud_smoother, shared_context))
                    api_task = asyncio.create_task(self._api_fetch_task(val_client, resolver, shared_context))
                    nudge_task = asyncio.create_task(self._nudge_task(session, shared_context, coaching_history))
                    voice_task = asyncio.create_task(self._voice_queue_processor(voice_queue, session))
                    
                    stop_task = asyncio.create_task(self._stop_event.wait())

                    tasks = [receive_task, push_task, api_task, nudge_task, voice_task, stop_task]

                    # Wait for the first task to finish (or crash)
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                    # A task completed (likely a disconnect error), so we clean up pending tasks
                    for t in pending:
                        t.cancel()
                    
                    # Ensure cleanup finishes
                    await asyncio.gather(*pending, return_exceptions=True)
                    self._session = None

                    # If the stop event was triggered, exit the loop
                    if self._stop_event.is_set():
                        break
                    
                    print("[SpectAI] Connection lost. Reconnecting in 3 seconds...")
                    await asyncio.sleep(3)

            except Exception as e:
                if not self._stop_event.is_set():
                    print(f"[SpectAI] Connection failed: {e}. Retrying in 3 seconds...")
                    await asyncio.sleep(3)

        print("[SpectAI] Session closed.")

    async def _continuous_receive_task(self, session, coaching_history):
        current_turn_text = ""
        try:
            async for msg in session.receive():
                text = self._extract_text_from_msg(msg)
                if text:
                    current_turn_text += text
                
                if msg.server_content and msg.server_content.turn_complete:
                    response_text = current_turn_text.strip()
                    current_turn_text = ""  
                    
                    if not response_text:
                        continue
                    
                    if self._expecting_voice_response:
                        self._expecting_voice_response = False
                        self._last_voice_time = time.time()
                        self._process_voice_response(response_text)
                    else:
                        self._process_coach_response(response_text, coaching_history)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"\n[SpectAI] Receive loop closed ({e}).")
            # Exiting this function triggers the FIRST_COMPLETED in the main loop to initiate a reconnect.

    def _extract_text_from_msg(self, msg) -> str:
        if not msg.server_content:
            return ""
        if msg.server_content.output_transcription:
            return msg.server_content.output_transcription.text or ""
        if msg.server_content.model_turn:
            return "".join(p.text for p in msg.server_content.model_turn.parts if p.text)
        return ""

    async def _push_info_task(self, session, screen_capture, hud_scanner, hud_smoother, shared_context):
        try:
            while True:
                frame = await asyncio.to_thread(screen_capture.capture)
                if frame is not None:
                    jpeg_bytes = await asyncio.to_thread(screen_capture.frame_to_jpeg, frame)
                    try:
                        await session.send_realtime_input(
                            video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                        )
                    except Exception:
                        pass # Ignore individual frame drops

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
        except asyncio.CancelledError:
            pass

    async def _api_fetch_task(self, val_client, resolver, shared_context):
        if not val_client or not resolver:
            return
        try:
            while True:
                try:
                    summary = await asyncio.to_thread(build_game_context_summary, val_client, resolver)
                    if summary:
                        shared_context["api_text"] = summary
                except Exception:
                    pass
                await asyncio.sleep(GAME_STATE_REFRESH_SECONDS)
        except asyncio.CancelledError:
            pass

    async def _nudge_task(self, session, shared_context, coaching_history):
        try:
            while True:
                await asyncio.sleep(NUDGE_INTERVAL)

                if self._expecting_voice_response and (time.time() - self._voice_query_timestamp > 15.0):
                    print("\n[Voice Telemetry] Warning: Voice response timed out. Resuming normal coach operations.")
                    self._expecting_voice_response = False

                if self._expecting_voice_response or (time.time() - self._last_voice_time < 8.0):
                    continue

                history_text = " | ".join(coaching_history) if coaching_history else "None"
                nudge_prompt = (
                    f"Analyze. Current HUD context: {shared_context['hud_text']}. "
                    f"LIVE GAME DATA: {shared_context['api_text']}. "
                    f"Recent advice given: {history_text}. "
                    "Do NOT repeat recent advice unless the situation has drastically worsened. "
                    "Respond strictly in JSON."
                )

                try:
                    await session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=nudge_prompt)]
                        ),
                        turn_complete=True
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"\n[SpectAI] Nudge error: {e}")
                    break # Break loop to trigger a reconnect

        except asyncio.CancelledError:
            pass

    async def _voice_queue_processor(self, voice_queue, session):
        try:
            while True:
                pcm_bytes = await voice_queue.get()
                print("\n[Voice Telemetry] Audio popped from queue. Dispatching to Gemini...")
                
                self._expecting_voice_response = True
                self._voice_query_timestamp = time.time()
                
                try:
                    await session.send_realtime_input(activity_start=types.ActivityStart())
                    await session.send_realtime_input(
                        audio=types.Blob(data=pcm_bytes, mime_type=f"audio/pcm;rate={MIC_SAMPLE_RATE}")
                    )
                    await session.send_realtime_input(activity_end=types.ActivityEnd())
                    print("[Voice Telemetry] Audio payload sent. Awaiting response in receive loop...")
                except Exception as e:
                    print(f"[Voice Telemetry] Error sending audio: {e}")
                    self._expecting_voice_response = False
                    break # Break loop to trigger a reconnect

        except asyncio.CancelledError:
            pass

    def _process_voice_response(self, full_response: str):
        print(f"[Voice Telemetry] Raw Gemini Text: {full_response}")

        play_match = re.search(r'\[SHOW_PLAY:([^:\]]+):([^\]]+)\]', full_response)
        clean = re.sub(r'\[SHOW_PLAY:[^\]]+\]', '', full_response).strip()

        sentences = re.split(r'(?<=[.!?])\s+', clean)
        spoken = sentences[-1] if sentences else clean
        print(f"[Voice Telemetry] Filtered text for TTS: {spoken}")

        if self._voice_callback:
            self._voice_callback(clean)

        if play_match and self._play_callback:
            map_name = play_match.group(1).strip()
            play_name = play_match.group(2).strip()
            print(f"[Voice Telemetry] Play recommendation: {map_name} — {play_name}")
            self._play_callback(map_name, play_name)

        asyncio.get_event_loop().run_in_executor(None, _speak_sync, spoken)

    def _process_coach_response(self, full_response: str, coaching_history: deque):
        if time.time() - self._last_voice_time < 8.0:
            return

        ctx = parse_coach_response(full_response)
        if not ctx:
            print(f"\n[Parse Failed]: {full_response}")
            return
            
        if ctx.should_coach and ctx.advice:
            coaching_history.append(ctx.advice)
            asyncio.get_event_loop().run_in_executor(None, _speak_sync, ctx.advice)
            if self._response_callback:
                self._response_callback(ctx.advice)
        else:
            print(".", end="", flush=True)


if __name__ == "__main__":
    def on_coach_response(advice: str):
        print(f"\n[COACH]: {advice}")

    def on_voice_response(advice: str):
        print(f"\n[VOICE]: Response: {advice}")

    ai = SpectAI(response_callback=on_coach_response, voice_callback=on_voice_response)
    ai.start()
    ai.wait()