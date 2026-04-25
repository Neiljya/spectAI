# Valorant AI Coaching System

## Stack
- **Gemini Flash** — multimodal vision layer (reads screenshots + profile + query → text)
- **Fetch.ai / ASI:one** — text-only LLM orchestrator + 3 specialist agents

## File Structure
```
coaching_system/
├── shared/
│   ├── __init__.py
│   ├── models.py          # all uAgent message models
│   └── player_store.py    # player profiles (shared context)
├── vision/
│   ├── __init__.py
│   └── gemini_vision.py   # all 3 inputs → Gemini → text
├── gamesense_agent.py
├── mechanics_agent.py
├── mental_agent.py
├── orchestrator.py
├── collector.py
└── requirements.txt
```

## API Keys
1. `vision/gemini_vision.py` → replace `"your_gemini_api_key"` → https://aistudio.google.com
2. `gamesense_agent.py`, `mechanics_agent.py`, `mental_agent.py` → replace `"your_asi_one_key"` → https://asi1.ai

## Startup Order (5 terminals, in this exact order)

```bash
# Terminal 1
python gamesense_agent.py
# Copy the printed agent1q... address → paste into orchestrator.py GAMESENSE_ADDR

# Terminal 2
python mechanics_agent.py
# Copy address → paste into orchestrator.py MECHANICS_ADDR

# Terminal 3
python mental_agent.py
# Copy address → paste into orchestrator.py MENTAL_ADDR

# Terminal 4
python orchestrator.py
# Copy the printed agent1q... address → paste into collector.py ORCHESTRATOR_ADDRESS

# Terminal 5
python collector.py
# System is now live
```

## Install
```bash
pip install -r requirements.txt
```

## Data Flow
```
Live footage ──┐
Player profile ─┼──► Gemini Flash ──► (text only) ──► Fetch.ai Orchestrator
Player query ──┘                                              │
                                               ┌─────────────┼─────────────┐
                                         Gamesense      Mechanics       Mental
                                           agent          agent          agent
                                               └─────────────┼─────────────┘
                                                       Orchestrator
                                                     synthesizes output
                                                    (coaching call / TTS)
```

## Customise Player Profile
Edit `shared/player_store.py` to update rank, agent, playstyle, strengths and weak areas.
In production, load these from your database or game API.
