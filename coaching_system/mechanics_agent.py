import os
import httpx
from dotenv import load_dotenv
from uagents import Agent, Context

from shared.models import AnalysisRequest, AgentReport

load_dotenv()
ASI_ONE_API_KEY = os.environ["ASI_ONE_API_KEY"]
ASI_ONE_URL     = "https://api.asi1.ai/v1/chat/completions"

mechanics = Agent(
    name="mechanics_agent",
    seed="mechanics_seed_phrase",
    port=8002,
    endpoint=["http://127.0.0.1:8002/submit"],
    mailbox=True,
)


@mechanics.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Mechanics agent running at: {mechanics.address}")


@mechanics.on_message(model=AnalysisRequest)
async def analyze(ctx: Context, sender: str, msg: AnalysisRequest):
    system_prompt = f"""You are an elite Valorant mechanics coach.

Player profile:
- Rank       : {msg.profile.rank}
- Agent      : {msg.profile.agent_name}
- Playstyle  : {msg.profile.playstyle}
- Strengths  : {", ".join(msg.profile.strengths)}
- Weak areas : {", ".join(msg.profile.weak_areas)}

You will receive a plain-text game state description (already analyzed from footage).
Analyze ONLY: aim, crosshair placement, movement, spray control, counter-strafing,
peeking mechanics, and reaction timing.

Look for:
- Moving while shooting (no counter-strafe)
- Crosshair too high, low, or off common angles
- Peeking before crosshair is pre-aimed on the target
- Spraying when a tap would win
- Tapping when a spray is needed (close range)
- Jumping or crouching at wrong moments

Respond with:
1. FINDINGS: One concise sentence on the mechanics issue you see.
2. ACTION: One short, direct mechanical fix the player must apply RIGHT NOW (max 12 words).
3. PRIORITY: Rate urgency as high, medium, or low.
   high = player must fix this immediately or will lose the gunfight
   medium = important habit to correct but not round-ending
   low = minor adjustment for long-term improvement

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

    findings    = ""
    action_call = raw
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
        agent_type="mechanics",
        player_id=msg.profile.player_id,
        findings=findings or raw,
        priority=priority,
        action_call=action_call
    )
    await ctx.send(sender, report)
    ctx.logger.info(f"Report sent → [{priority.upper()}] {action_call}")


if __name__ == "__main__":
    mechanics.run()
