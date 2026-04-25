"""
Quick test for SpectAI features without Valorant:
  - ElevenLabs TTS speaks a test coaching line on startup
  - Hold F9 to ask Gemini a voice question, release to get a spoken answer
  Ctrl+C to exit.
"""
import asyncio
import os
import threading
import ctypes
import tempfile
import sys

import dotenv
import httpx
import numpy as np

dotenv.load_dotenv()

try:
    import sounddevice as sd
    from pynput import keyboard as kb
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    print("[Test] sounddevice/pynput not installed — voice input disabled")

from google import genai
from google.genai import types

_ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
_ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"
_tts_lock = threading.Lock()
MIC_SAMPLE_RATE = 16000
PTT_KEY = kb.Key.f9 if VOICE_AVAILABLE else None


def _play_mp3(path: str):
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
                json={"text": text, "model_id": "eleven_flash_v2_5",
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
                timeout=15,
            )
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name
            _play_mp3(tmp_path)
        except Exception as e:
            print(f"[Test] TTS error: {e}")


def start_ptt_listener(loop: asyncio.AbstractEventLoop, voice_queue: asyncio.Queue):
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
            print("[Test] Recording... release F9 to send")

    def on_release(key):
        nonlocal recording
        if key == PTT_KEY and recording:
            recording = False
            if audio_chunks:
                audio_data = np.concatenate(audio_chunks, axis=0)
                pcm_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                asyncio.run_coroutine_threadsafe(voice_queue.put(pcm_bytes), loop)
                print("[Test] Sent to Gemini...")

    with sd.InputStream(samplerate=MIC_SAMPLE_RATE, channels=1, dtype='float32', callback=audio_callback):
        with kb.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()


async def handle_voice_query(session, pcm_bytes: bytes, loop):
    await session.send_realtime_input(activity_start=types.ActivityStart())
    await session.send_realtime_input(
        audio=types.Blob(data=pcm_bytes, mime_type=f"audio/pcm;rate={MIC_SAMPLE_RATE}")
    )
    await session.send_realtime_input(activity_end=types.ActivityEnd())

    full_text = ""
    async for msg in session.receive():
        if msg.server_content:
            sc = msg.server_content
            if sc.output_transcription:
                full_text += sc.output_transcription.text or ""
            if sc.model_turn:
                for part in sc.model_turn.parts or []:
                    if part.text:
                        full_text += part.text
            if sc.turn_complete:
                break
    if full_text:
        print(f"[Test] Gemini: {full_text}")
        await loop.run_in_executor(None, _speak_sync, full_text)
    else:
        print("[Test] No text in response")


async def main():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={"api_version": "v1alpha"})
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(
            text="You are SpectAI, an elite Valorant coach. Answer questions in 12 words or fewer — sharp and actionable."
        )]),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
        ),
    )

    loop = asyncio.get_event_loop()
    voice_queue: asyncio.Queue = asyncio.Queue()

    if VOICE_AVAILABLE:
        threading.Thread(target=start_ptt_listener, args=(loop, voice_queue), daemon=True).start()
        print("[Test] Push-to-talk ready — hold F9 to ask a question")
    else:
        print("[Test] Voice unavailable — testing TTS only")

    async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as session:
        print("[Test] Gemini Live connected.")

        # TTS smoke test
        print("[Test] Speaking test line via ElevenLabs...")
        await loop.run_in_executor(None, _speak_sync, "SpectAI is online. Hold F9 to ask me anything.")
        print("[Test] TTS done. Waiting for voice input (Ctrl+C to quit)...")

        while True:
            if not voice_queue.empty():
                pcm = await voice_queue.get()
                await handle_voice_query(session, pcm, loop)
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Test] Exiting.")
