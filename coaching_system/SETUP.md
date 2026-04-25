# SpectAI — Setup & Run Guide

SpectAI is a real-time Valorant coaching system. It watches your screen and game logs, analyzes your gameplay with AI, and speaks coaching tips aloud through your speakers during a match.

---

## System Requirements

| Requirement | Notes |
|---|---|
| **Windows 10/11** | Required — screen capture and Valorant log access are Windows-only |
| **Python 3.10 or newer** | [Download here](https://www.python.org/downloads/) — check "Add to PATH" during install |
| **Valorant** | Must be installed and running when you use SpectAI |
| **ffmpeg** | Required for voice coaching — [Download here](https://ffmpeg.org/download.html), add `bin/` folder to your system PATH |

---

## Step 1 — Get the files

Copy the entire repo to your machine. You need both of these folders at the same level:

```
spectAI/
  coaching_system/    ← backend agents
  Vision-Model/       ← Gemini vision layer
```

---

## Step 2 — Install Python dependencies

Open a terminal in the `coaching_system/` folder and run:

```
pip install -r requirements.txt
```

Then open a terminal in the `Vision-Model/` folder and run:

```
pip install -r requirements.txt
```

> If you don't have a `requirements.txt` in `Vision-Model/`, install manually:
> `pip install google-genai uagents python-dotenv pillow mss`

---

## Step 3 — Create the .env file

Create a file called `.env` inside `coaching_system/` with the following contents.
**All values must be filled in — nothing will work without them.**

```
GEMINI_API_KEY=your_google_gemini_api_key
ASI_ONE_API_KEY=your_asi_one_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
AGENTVERSE_API_KEY=optional_leave_blank_if_unsure
```

Where to get each key:
- **GEMINI_API_KEY** → [aistudio.google.com](https://aistudio.google.com/app/apikey)
- **ASI_ONE_API_KEY** → [fetch.ai / ASI:one dashboard](https://asi1.ai)
- **ELEVENLABS_API_KEY** → [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys)
- **SUPABASE_URL / SUPABASE_ANON_KEY** → Your Supabase project → Settings → API

---

## Step 4 — Set your player profile

Open `coaching_system/shared/player_store.py` and update the profile to match **your** Riot account:

```python
"player_001": PlayerProfile(
    player_id="player_001",
    rank="Diamond 2",           # ← your current rank
    agent_name="Jett",          # ← your main agent
    playstyle="aggressive entry",
    strengths=["aim", "movement"],
    weak_areas=["util usage", "rotation timing"],
    riot_puuid="d61f41e1-..."   # ← your Riot PUUID (see note below)
)
```

**Finding your Riot PUUID:**
Go to `https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/YOUR_NAME/YOUR_TAG` (replace with your Riot ID and tagline, no #).

> This PUUID must also match your row in the Supabase `profiles` table, or database writes will be skipped silently.

---

## Step 5 — Run the system

You need **5 terminals open at the same time**. Open each one, navigate to the correct folder, and run the command.

### Terminals 1–4 — Backend agents (all from `coaching_system/`)

**Terminal 1 — Orchestrator (start this first)**
```
cd coaching_system
python orchestrator.py
```
Wait until you see `Supabase: connected` before starting the others.

**Terminal 2 — Gamesense agent**
```
cd coaching_system
python gamesense_agent.py
```

**Terminal 3 — Mechanics agent**
```
cd coaching_system
python mechanics_agent.py
```

**Terminal 4 — Mental agent**
```
cd coaching_system
python mental_agent.py
```

### Terminal 5 — Vision layer (from `Vision-Model/`)

**Terminal 5 — Vision agent (start last)**
```
cd Vision-Model
python live_llm_s.py
```

---

## What to expect on startup

| Agent | Expected output |
|---|---|
| `orchestrator.py` | Prints its agent address, then `Supabase: connected` |
| `gamesense_agent.py` | Prints its agent address and waits |
| `mechanics_agent.py` | Prints its agent address and waits |
| `mental_agent.py` | Prints its agent address and waits |
| `live_llm_s.py` | Prints its agent address, then begins watching your screen |

If any agent fails to start, check that your `.env` is filled in and all dependencies are installed.

---

## How it works in-game

Once all 5 terminals are running and Valorant is open:

1. The vision agent watches your screen every few seconds using Gemini AI
2. When a significant moment happens (kill, spike event, round change), it builds a full game state analysis
3. The analysis is sent to all 3 specialist agents simultaneously:
   - **Gamesense** — positioning, rotations, map control
   - **Mechanics** — aim, crosshair placement, spray patterns
   - **Mental** — tilt, confidence, team communication
4. The highest-priority coaching tip is spoken aloud through your speakers via ElevenLabs
5. All 3 agent reports are saved to Supabase for post-match review

---

## Troubleshooting

**No voice output**
- Make sure ffmpeg is installed and `ffplay` is accessible from the command line (`ffplay -version` to test)
- Check that `ELEVENLABS_API_KEY` is set in `.env`

**Agents not communicating**
- Make sure orchestrator is fully started (shows `Supabase: connected`) before launching other agents
- All 5 agents must be running at the same time

**Vision agent not detecting game**
- Valorant must be the active/focused window
- Make sure `GEMINI_API_KEY` is valid

**Database writes not appearing in Supabase**
- Verify your `riot_puuid` in `player_store.py` matches the `profiles` table in Supabase
- Check Supabase logs for errors

**Import errors on startup**
- Run `pip install -r requirements.txt` again from the correct folder
- Make sure you're using Python 3.10 or newer (`python --version`)
