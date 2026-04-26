import os, ctypes, tempfile, httpx, dotenv
dotenv.load_dotenv('../.env')
KEY = os.getenv('ELEVENLABS_API_KEY')
VOICE = 'JBFqnCBsd6RMkjVDRZzb'
text = 'Support your team: heal, block sites with wall, slow pushes.'
resp = httpx.post(f'https://api.elevenlabs.io/v1/text-to-speech/{VOICE}',
    headers={'xi-api-key': KEY, 'Content-Type': 'application/json'},
    json={'text': text, 'model_id': 'eleven_flash_v2_5', 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}},
    timeout=15)
resp.raise_for_status()
with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
    f.write(resp.content); path = f.name
mci = ctypes.windll.winmm.mciSendStringW
mci(f'open "{path}" type mpegvideo alias t', None, 0, None)
mci('play t wait', None, 0, None)
mci('close t', None, 0, None)
print('Done')
