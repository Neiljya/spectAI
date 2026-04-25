import asyncio
import base64
import io
import time

import mss
from PIL import Image
from uagents import Agent, Context

from shared.models import PlayerQuery, AnalysisRequest
from shared.player_store import PLAYER_PROFILES
from vision.gemini_vision import analyze_all

# Paste the orchestrator's printed address here after running orchestrator.py first
ORCHESTRATOR_ADDRESS = "agent1qv3vml6d7av788k4yyhwrwssmj4tsct7z9nw8eyva9h6jc29quka5wmh6am"

collector = Agent(
    name="collector",
    seed="collector_seed_phrase",
    port=8010,
    endpoint=["http://127.0.0.1:8010/submit"]
)


def grab_screenshot() -> str:
    """Captures primary monitor and returns base64 JPEG string."""
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        img = img.resize((1280, 720))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        return base64.b64encode(buf.getvalue()).decode()


# ── Passive frame capture every 3 seconds ────────────────────────────────────
@collector.on_interval(period=3.0)
async def capture_and_synthesize(ctx: Context):
    player_id = "player_001"
    profile = PLAYER_PROFILES.get(player_id)
    if not profile:
        ctx.logger.error(f"No profile found for {player_id}")
        return

    # 1. Grab screenshot
    ctx.logger.info("Capturing screen...")
    b64 = grab_screenshot()

    # 2. All 3 inputs → Gemini → one text summary
    ctx.logger.info("Sending screenshot + profile to Gemini for synthesis...")
    game_state_text = await analyze_all(
        screenshot_b64=b64,
        profile=profile,
        player_query=None       # no query on passive interval frames
    )
    ctx.logger.info(f"Gemini output preview: {game_state_text[:150]}...")

    # 3. Send pure text to Fetch.ai orchestrator — no image ever leaves this file
    req = AnalysisRequest(
        profile=profile,
        game_state_text=game_state_text,
        round_num=7,            # production: parse from game API or OCR
        map_name="ascent",      # production: parse from game API or OCR
        player_query=None
    )
    await ctx.send(ORCHESTRATOR_ADDRESS, req)
    ctx.logger.info("Text analysis sent to orchestrator.")


# ── On-demand: player asks a question ────────────────────────────────────────
@collector.on_message(model=PlayerQuery)
async def handle_player_query(ctx: Context, sender: str, msg: PlayerQuery):
    profile = PLAYER_PROFILES.get(msg.player_id)
    if not profile:
        ctx.logger.error(f"No profile found for {msg.player_id}")
        return

    ctx.logger.info(f"Player query received: '{msg.text}'")

    # 1. Grab a fresh screenshot at the moment of the query
    b64 = grab_screenshot()

    # 2. All 3 inputs → Gemini: screenshot + profile + player's actual question
    ctx.logger.info("Sending screenshot + profile + query to Gemini...")
    game_state_text = await analyze_all(
        screenshot_b64=b64,
        profile=profile,
        player_query=msg.text   # player question baked into Gemini prompt
    )
    ctx.logger.info(f"Gemini output preview: {game_state_text[:150]}...")

    # 3. Single text payload to Fetch.ai — query also passed for agent context
    req = AnalysisRequest(
        profile=profile,
        game_state_text=game_state_text,
        round_num=0,
        map_name="",
        player_query=msg.text
    )
    await ctx.send(ORCHESTRATOR_ADDRESS, req)
    ctx.logger.info("Query-triggered analysis sent to orchestrator.")


if __name__ == "__main__":
    collector.run()
