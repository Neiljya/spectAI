"""
Fire a single fake AnalysisRequest at the orchestrator to test the full pipeline:
  trigger → orchestrator → gamesense/mechanics/mental agents → TTS
Run this after starting orchestrator.py and all 3 agent scripts.
"""
from uagents import Agent, Context
from shared.models import AnalysisRequest, PlayerProfile
from shared.player_store import PLAYER_PROFILES

ORCHESTRATOR_ADDR = "agent1qv3vml6d7av788k4yyhwrwssmj4tsct7z9nw8eyva9h6jc29quka5wmh6am"

trigger = Agent(name="trigger", seed="spectai_trigger_once", port=8010)

_sent = False

@trigger.on_event("startup")
async def send_test(ctx: Context):
    global _sent
    if _sent:
        return
    _sent = True

    profile = PLAYER_PROFILES["player_001"]
    req = AnalysisRequest(
        profile=profile,
        game_state_text=(
            "Round 8 on Bind, score 4-3. Player is playing B site on Jett. "
            "Spike just planted at B long. 35 seconds remain. "
            "Two enemies alive, one teammate alive. Player has Vandal, 80 HP. "
            "Enemy Sage is holding B short, second enemy unknown position. "
            "Player is crouched at B site boxes — rotation window is closing fast."
        ),
        round_num=8,
        map_name="Bind",
        spike_status="planted",
        time_remaining=35.0,
        score="4-3",
        urgency="high",
        health=80,
        weapon="Vandal",
        position="B Site",
        in_gunfight=False,
    )
    ctx.logger.info("Sending test AnalysisRequest to orchestrator...")
    await ctx.send(ORCHESTRATOR_ADDR, req)


if __name__ == "__main__":
    trigger.run()
