import os
import httpx
from dotenv import load_dotenv
from uagents import Agent, Context

from shared.models import AnalysisRequest, AgentReport

load_dotenv()
ASI_ONE_API_KEY = os.environ["ASI_ONE_API_KEY"]
ASI_ONE_URL     = "https://api.asi1.ai/v1/chat/completions"

gamesense = Agent(
    name="gamesense_agent",
    seed="gamesense_seed_phrase",
    port=8001,
    endpoint=["http://127.0.0.1:8001/submit"],
    mailbox=True,
)


@gamesense.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Gamesense agent running at: {gamesense.address}")


@gamesense.on_message(model=AnalysisRequest)
async def analyze(ctx: Context, sender: str, msg: AnalysisRequest):
    system_prompt = f"""You are an elite Valorant gamesense coach.

Player profile:
- Rank       : {msg.profile.rank}
- Agent      : {msg.profile.agent_name}
- Playstyle  : {msg.profile.playstyle}
- IGL        : {"Yes" if msg.profile.igl else "No"}
- Strengths  : {", ".join(msg.profile.strengths)}
- Weak areas : {", ".join(msg.profile.weak_areas)}

You will receive a plain-text game state description (already analyzed from footage).
Analyze ONLY: positioning, rotations, map control, utility usage, and site reads.

Look for:
- Wrong rotation timing given round state
- Playing too passive or aggressive for the economy
- Uncovered flanks or map gaps
- Utility being wasted or saved incorrectly
- Misread of spike/round state

Respond with:
1. FINDINGS: One concise sentence on the gamesense issue you see.
2. ACTION: One short, direct call the player must act on RIGHT NOW (max 12 words).
3. PRIORITY: Rate urgency as high, medium, or low.
   high = player must act in the next 5 seconds or loses the round
   medium = important but can wait until next round
   low = general improvement note

Format exactly:
FINDINGS: <your finding>
ACTION: <your call>
PRIORITY: <high | medium | low>"""

    user_text = msg.game_state_text
    if msg.player_query:
        user_text += f"\n\nPlayer asked: {msg.player_query}"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            ASI_ONE_URL,
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            json={
                "model": "asi1-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_text}
                ]
            }
        )

    raw = resp.json()["choices"][0]["message"]["content"]

    # Parse structured response
    findings   = ""
    action_call = raw  # fallback to full text
    for line in raw.splitlines():
        if line.startswith("FINDINGS:"):
            findings = line.replace("FINDINGS:", "").strip()
        elif line.startswith("ACTION:"):
            action_call = line.replace("ACTION:", "").strip()

    priority = "medium"
    for line in raw.splitlines():
        if line.startswith("PRIORITY:"):
            p = line.replace("PRIORITY:", "").strip().lower()
            if p in ("high", "medium", "low"):
                priority = p

    report = AgentReport(
        agent_type="gamesense",
        player_id=msg.profile.player_id,
        findings=findings or raw,
        priority=priority,
        action_call=action_call
    )
    await ctx.send(sender, report)
    ctx.logger.info(f"Report sent → [{priority.upper()}] {action_call}")


if __name__ == "__main__":
    gamesense.run()
