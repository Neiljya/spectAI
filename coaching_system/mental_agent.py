import os
import httpx
from dotenv import load_dotenv
from uagents import Agent, Context

from shared.models import AnalysisRequest, AgentReport

load_dotenv()
ASI_ONE_API_KEY = os.environ["ASI_ONE_API_KEY"]
ASI_ONE_URL     = "https://api.asi1.ai/v1/chat/completions"

mental = Agent(
    name="mental_agent",
    seed="mental_seed_phrase",
    port=8003,
    endpoint=["http://127.0.0.1:8003/submit"],
    mailbox=True,
)


@mental.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Mental agent running at: {mental.address}")


@mental.on_message(model=AnalysisRequest)
async def analyze(ctx: Context, sender: str, msg: AnalysisRequest):
    system_prompt = f"""You are an elite Valorant mental performance coach.

Player profile:
- Rank       : {msg.profile.rank}
- Agent      : {msg.profile.agent_name}
- Playstyle  : {msg.profile.playstyle}
- IGL        : {"Yes" if msg.profile.igl else "No"}
- Strengths  : {", ".join(msg.profile.strengths)}
- Weak areas : {", ".join(msg.profile.weak_areas)}

You will receive a plain-text game state description (already analyzed from footage).
Analyze ONLY: mental state, decision-making under pressure, tilt signals,
confidence patterns, and behavioral indicators.

Look for:
- Forced peeks or aggression immediately after dying (revenge mentality)
- Going passive or hiding after losing rounds (fear-based play)
- Rushed eco buys that break team economy
- Over-holding angles long after the info window closed
- Any language or behavioral cues suggesting frustration or blame
- IGL making reactive calls instead of proactive ones (if IGL)

Respond with:
1. FINDINGS: One concise sentence on the mental state issue you observe.
2. ACTION: One calm, direct mental reset or focus cue the player needs RIGHT NOW.
   Max 12 words. Be constructive — no blame, no negativity.
3. PRIORITY: Rate urgency as high, medium, or low.
   high = player is visibly tilting or making emotion-driven decisions right now
   medium = pattern emerging that needs correction soon
   low = general mental note for post-match reflection

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
        agent_type="mental",
        player_id=msg.profile.player_id,
        findings=findings or raw,
        priority=priority,
        action_call=action_call
    )
    await ctx.send(sender, report)
    ctx.logger.info(f"Report sent → [{priority.upper()}] {action_call}")


if __name__ == "__main__":
    mental.run()
