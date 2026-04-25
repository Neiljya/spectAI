"""
Quick smoke-test: calls ASI1 API directly with mock game-state text,
replicating what all 3 specialist agents would produce.
No uAgents / WSL needed.
"""
import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
ASI_ONE_API_KEY = os.environ["ASI_ONE_API_KEY"]
ASI_ONE_URL = "https://api.asi1.ai/v1/chat/completions"

# ── Mock data (simulates what Gemini vision would produce) ───────────────────
MOCK_PROFILE = {
    "rank": "Diamond 2",
    "agent_name": "Jett",
    "playstyle": "aggressive entry",
    "igl": False,
    "strengths": ["aim", "movement"],
    "weak_areas": ["util usage", "rotation timing"],
}

MOCK_GAME_STATE = """
GAME STATE:
- Map: Ascent, B-main / mid-link area, player pushing through B-main alone
- Round 7 of 24, ~55 seconds remaining, spike not planted
- Score: Attackers 3 - Defenders 4
- No visible enemies yet; teammates are split — two holding A-main, one on mid-catwalk
- Minimap: B-site completely uncovered, A-main overloaded with friendlies

ECONOMY:
- Player credits: 3900, equipped: Vandal, full armor
- Teammates appear to have rifles or Specters — no full-buy visible on one teammate

MECHANICS OBSERVATIONS:
- Crosshair is held at stomach height while approaching B-main corner
- Player was walking (not stopped) at the moment the screenshot was taken
- No current spray visible — approaching engagement phase

MENTAL / BEHAVIORAL SIGNALS:
- Player has died twice in the last two rounds; third consecutive push into B-main alone
- Previous two rounds also ended with early, unsupported peeks at B-main entrance
- No utility deployed this round despite having Jett's updraft and smoke available

PROFILE FIT:
- Player's weak area (rotation timing) is apparent — Jett is pushing B solo while team loads A
- Utility not used matches the weak area of 'util usage'
- Aggressive playstyle may be overcorrecting after back-to-back losses (tilt signal)
"""


async def call_asi1(system_prompt: str, user_text: str, label: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            ASI_ONE_URL,
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            json={
                "model": "asi1-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
            },
        )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]

    findings = ""
    action_call = raw
    priority = "medium"
    for line in raw.splitlines():
        if line.startswith("FINDINGS:"):
            findings = line.replace("FINDINGS:", "").strip()
        elif line.startswith("ACTION:"):
            action_call = line.replace("ACTION:", "").strip()
        elif line.startswith("PRIORITY:"):
            p = line.replace("PRIORITY:", "").strip().lower()
            if p in ("high", "medium", "low"):
                priority = p

    return {"label": label, "findings": findings or raw, "action": action_call, "priority": priority, "raw": raw}


def gamesense_prompt(p):
    return f"""You are an elite Valorant gamesense coach.

Player profile:
- Rank       : {p['rank']}
- Agent      : {p['agent_name']}
- Playstyle  : {p['playstyle']}
- IGL        : {"Yes" if p['igl'] else "No"}
- Strengths  : {", ".join(p['strengths'])}
- Weak areas : {", ".join(p['weak_areas'])}

Analyze ONLY: positioning, rotations, map control, utility usage, and site reads.
Respond with:
FINDINGS: <one sentence>
ACTION: <max 12 words>
PRIORITY: <high | medium | low>
high = player must act in the next 5 seconds or loses the round
medium = important but can wait until next round
low = general improvement note"""


def mechanics_prompt(p):
    return f"""You are an elite Valorant mechanics coach.

Player profile:
- Rank       : {p['rank']}
- Agent      : {p['agent_name']}
- Playstyle  : {p['playstyle']}
- Strengths  : {", ".join(p['strengths'])}
- Weak areas : {", ".join(p['weak_areas'])}

Analyze ONLY: aim, crosshair placement, movement, spray control, counter-strafing, peeking mechanics.
Respond with:
FINDINGS: <one sentence>
ACTION: <max 12 words>
PRIORITY: <high | medium | low>
high = player must fix this immediately or will lose the gunfight
medium = important habit to correct but not round-ending
low = minor adjustment for long-term improvement"""


def mental_prompt(p):
    return f"""You are an elite Valorant mental performance coach.

Player profile:
- Rank       : {p['rank']}
- Agent      : {p['agent_name']}
- Playstyle  : {p['playstyle']}
- IGL        : {"Yes" if p['igl'] else "No"}
- Strengths  : {", ".join(p['strengths'])}
- Weak areas : {", ".join(p['weak_areas'])}

Analyze ONLY: mental state, decision-making under pressure, tilt signals, confidence patterns.
Respond with:
FINDINGS: <one sentence>
ACTION: <max 12 words>
PRIORITY: <high | medium | low>
high = player is visibly tilting or making emotion-driven decisions right now
medium = pattern emerging that needs correction soon
low = general mental note for post-match reflection"""


async def main():
    print("=" * 60)
    print("spectAI — Multi-Agent Coaching System Test")
    print("Dispatching to 3 specialist agents in parallel...")
    print("=" * 60)

    p = MOCK_PROFILE
    results = await asyncio.gather(
        call_asi1(gamesense_prompt(p), MOCK_GAME_STATE, "GAMESENSE"),
        call_asi1(mechanics_prompt(p), MOCK_GAME_STATE, "MECHANICS"),
        call_asi1(mental_prompt(p), MOCK_GAME_STATE, "MENTAL"),
    )

    print("\n[COACHING OUTPUT]\n")
    for r in results:
        print(f"  [{r['label']}] priority={r['priority'].upper()}")
        print(f"    Findings : {r['findings']}")
        print(f"    Action   : {r['action']}")
        print()

    print("=" * 60)
    print("All 3 agents responded successfully.")


if __name__ == "__main__":
    asyncio.run(main())
