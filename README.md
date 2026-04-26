# SpectAI

Real-time Valorant coaching overlay powered by Gemini. Watches your screen during a match, gives live voice and text advice, records the session, extracts key moment clips, and syncs everything to a web dashboard.

---

## Project Structure

```
spectAI/
├── spectai-overlay-v2/   # PyQt6 overlay — runs during your game
├── Vision-Model/         # Gemini vision + OCR pipeline
├── Dashboard/spectAI/    # React/Vite web dashboard
├── sessions/             # Auto-generated session recordings & clips
└── requirements.txt      # All Python dependencies
```

---

## Requirements

- Python 3.11+
- Node.js 18+
- Valorant running on Windows
- Supabase project (for dashboard sync)

---

## Setup

### 1. Environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=
ELEVENLABS_API_KEY=
HENRIK_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SUPABASE_ANON_KEY=
SUPABASE_PROFILE_ID=
RIOT_API_KEY=
```

### 2. Python dependencies

```bash
pip install -r requirements.txt
playwright install
```

### 3. Dashboard dependencies

```bash
cd Dashboard/spectAI
npm install
```

### 4. Supabase Storage

Create a public bucket named `match-clips` in your Supabase project:
Supabase Dashboard → Storage → New bucket → name: `match-clips` → Public: on

---

## Running the Overlay

Launch Valorant first, then:

```bash
cd spectai-overlay-v2
python main.py
```

The overlay starts in standby — no recording or AI until you press **F8**.

---

## Hotkeys

| Key | Action |
|-----|--------|
| `F8` | Start / stop session (recording + AI coaching) |
| `F9` | Push-to-talk — hold to ask the AI a question |
| `F10` | Toggle AI voice mute |
| `F12` | Quit SpectAI |
| `ALT + M` | Cycle through demo plays |
| `ALT + H` | Hide / show minimap overlay |
| `ALT + X` | Toggle speech bubble overlay |

---

## Running the Dashboard

```bash
cd Dashboard/spectAI
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Session Flow

1. Press **F8** to start — begins screen recording and AI coaching
2. AI gives real-time coaching via overlay text and voice
3. Press **F8** again to stop — session is saved to `sessions/<match_id>/`
4. Analysis pipeline runs automatically:
   - Finds key moments → `key_moments.json`
   - Extracts video clips → `clip_1/` through `clip_5/`
   - Uploads clips to Supabase Storage
   - Inserts a new row into `match_data` with clip URLs and coaching notes
5. Open the dashboard to review clips and AI feedback

---

## Uploading Existing Clips Manually

If you have a session with clips already extracted but not yet uploaded:

```bash
cd spectai-overlay-v2
python upload_clips.py
```

---

## Dashboard Features

- Match history with expandable clip review
- Per-clip coaching feedback panel
- AI-generated player summary (strengths / weaknesses)
- Tracker.gg stat sync
- Training plan generation
