import os
import ctypes
import tempfile
import httpx
from dotenv import load_dotenv

load_dotenv()

KEY   = os.environ["ELEVENLABS_API_KEY"]
VOICE = "JBFqnCBsd6RMkjVDRZzb"

print("Calling ElevenLabs...")
resp = httpx.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}",
    headers={"xi-api-key": KEY, "Content-Type": "application/json"},
    json={"text": "Push B now, spike timer is low.", "model_id": "eleven_flash_v2_5"},
    timeout=15,
)
resp.raise_for_status()
print(f"Got {len(resp.content)} bytes — playing...")

with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
    f.write(resp.content)
    tmp = f.name

mci = ctypes.windll.winmm.mciSendStringW
mci(f'open "{tmp}" type mpegvideo alias test', None, 0, None)
mci("play test wait", None, 0, None)
mci("close test", None, 0, None)
print("Done")
