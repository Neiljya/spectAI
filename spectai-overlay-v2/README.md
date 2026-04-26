# SpectAI Overlay

Real-time Valorant coaching overlay powered by Gemini Live.

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys:
   - `GEMINI_API_KEY`
   - `ELEVENLABS_API_KEY`
2. Install dependencies: `pip install -r requirements.txt`
3. Launch Valorant, then run: `python main.py`

## Hotkeys

| Key | Action |
|-----|--------|
| **F8** | Start / stop session — enables AI coaching and begins video recording |
| **F9** | Push-to-talk — hold to ask the AI a voice question |
| **F10** | Toggle AI voice mute (coaching text still shows; TTS is silenced) |
| **F12** | Kill the app |
| **ALT + M** | Cycle through demo plays on the minimap |
| **ALT + H** | Hide / show the minimap panel |
| **ALT + X** | Toggle the speech bubble overlay |

## Sessions

Each session (F8 start → F8 stop) writes two files to `sessions/`:

- `<id>.json` — timestamped coaching events, grouped with `elapsed_s` relative to session start
- `<id>.mp4` — screen recording at 24 FPS (same timeline as the JSON)

The `elapsed_s` value in each event maps directly to the video timestamp, making it easy to seek to any moment of interest for clip extraction.
