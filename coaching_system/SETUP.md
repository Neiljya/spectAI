# How to Run SpectAI on Your Machine

## Requirements

- Python 3.10+ on **Windows** (needed for screen capture and Valorant log access)
- Valorant installed and running during use
- ffmpeg for voice coaching — download from https://ffmpeg.org/download.html and add to PATH

## Setup

1. Copy the `coaching_system/` folder and the `.env` file to your machine.

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Fill in `.env` — all values must be real:
   ```
   GEMINI_API_KEY=...
   AGENTVERSE_API_KEY=...
   ASI_ONE_API_KEY=...
   ELEVENLABS_API_KEY=...
   SUPABASE_URL=...
   SUPABASE_ANON_KEY=...
   ```

## Running

Open 5 separate terminals, all from the `coaching_system/` directory:

```
python orchestrator.py
python gamesense_agent.py
python mechanics_agent.py
python mental_agent.py
python collector.py
```

Start orchestrator first — confirm the address it prints matches `ORCHESTRATOR_ADDRESS` in `collector.py`.

## What to expect on startup

- **orchestrator** — prints address, then `Supabase: connected`
- **gamesense / mechanics / mental** — print address and start listening
- **collector** — prints address, then `Tailing ShooterGame.log` once Valorant is running

## What happens in-game

When a kill, round change, or spike event fires:
1. Collector grabs screenshot + log context + Valorant API data
2. Gemini analyzes everything and returns structured game state
3. AnalysisRequest fans out to all 3 specialist agents simultaneously
4. Top priority coaching call is spoken aloud via ElevenLabs
5. Full event + all 3 agent reports are written to Supabase

## Before the demo

Make sure the player's `riot_puuid` in `shared/player_store.py` matches their row in the Supabase `profiles` table — otherwise database writes will silently skip.
