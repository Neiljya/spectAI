import asyncio
import base64
import io
import os
import re
from pathlib import Path

import aiofiles
import httpx
import mss
from PIL import Image
from uagents import Agent, Context
from dotenv import load_dotenv

from shared.models import PlayerQuery, AnalysisRequest
from shared.player_store import PLAYER_PROFILES
from vision.gemini_vision import analyze_all

load_dotenv()

# ── File paths (Valorant writes these automatically while running) ─────────────
LOG_PATH = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "VALORANT" / "Saved" / "Logs" / "ShooterGame.log"
)
LOCKFILE_PATH = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Riot Games" / "Riot Client" / "Config" / "lockfile"
)

ORCHESTRATOR_ADDRESS = "agent1qv3vml6d7av788k4yyhwrwssmj4tsct7z9nw8eyva9h6jc29quka5wmh6am"

# ShooterGame.log lines we care about — kills, round events, spike
_INTERESTING = re.compile(
    r"(Kill|RoundPhase|RoundEnd|Spike|BombPlant|BombDefuse|DamageTaken|DamageDealt)",
    re.IGNORECASE,
)

# Rolling buffer of recent log events — passed to Gemini for context
_recent_log_events: list[str] = []


# ── Valorant local API (lockfile) ─────────────────────────────────────────────

def _read_lockfile() -> tuple[str | None, str | None]:
    if not LOCKFILE_PATH.exists():
        return None, None
    parts = LOCKFILE_PATH.read_text().strip().split(":")
    if len(parts) < 5:
        return None, None
    _, _, port, password, _ = parts
    return port, password


async def _fetch_api(port: str, password: str) -> dict:
    auth = base64.b64encode(f"riot:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    result = {}
    try:
        async with httpx.AsyncClient(verify=False, timeout=3.0) as client:
            # Player presences — includes in-game state, map, round info
            r = await client.get(
                f"https://127.0.0.1:{port}/chat/v6/presences",
                headers=headers,
            )
            if r.status_code == 200:
                result["presences"] = r.json()
    except Exception:
        pass
    return result


# ── Screenshot ────────────────────────────────────────────────────────────────

def _grab_screenshot() -> str:
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        img = img.resize((1280, 720))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        return base64.b64encode(buf.getvalue()).decode()


# ── Core analysis trigger ─────────────────────────────────────────────────────

async def _trigger_analysis(ctx: Context, player_id: str = "player_001", player_query: str = None):
    profile = PLAYER_PROFILES.get(player_id)
    if not profile:
        ctx.logger.error(f"No profile for {player_id}")
        return

    port, password = _read_lockfile()
    api_data = {}
    if port and password:
        api_data = await _fetch_api(port, password)

    b64 = _grab_screenshot()
    log_summary = "\n".join(_recent_log_events[-15:]) if _recent_log_events else None

    ctx.logger.info("Sending to Gemini...")
    result = await analyze_all(
        screenshot_b64=b64,
        profile=profile,
        log_events=log_summary,
        api_data=api_data or None,
        player_query=player_query,
    )

    # Override hardcoded agent_name with whatever Gemini detected from the HUD
    detected_agent = result.get("agent_name", "")
    if detected_agent and detected_agent.lower() not in ("none", "unknown", ""):
        profile = profile.model_copy(update={"agent_name": detected_agent})
        ctx.logger.info(f"Agent detected from HUD: {detected_agent}")

    if not player_query and not result.get("should_coach", False):
        ctx.logger.info(f"should_coach=False, urgency={result.get('urgency')} — skipping")
        return

    req = AnalysisRequest(
        profile=profile,
        game_state_text=result.get("game_state_text", ""),
        round_num=result.get("round_num") or 0,
        map_name=result.get("map_name") or "",
        time_remaining=result.get("time_remaining"),
        score=result.get("score"),
        credits=result.get("credits"),
        spike_status=result.get("spike_status"),
        recent_events=log_summary,
        urgency=result.get("urgency"),
        player_query=player_query,
    )
    await ctx.send(ORCHESTRATOR_ADDRESS, req)
    ctx.logger.info(
        f"Analysis sent — round {req.round_num}, urgency={req.urgency}, spike={req.spike_status}"
    )


# ── ShooterGame.log tail loop ─────────────────────────────────────────────────

async def _tail_log(ctx: Context):
    if not LOG_PATH.exists():
        ctx.logger.warning(f"ShooterGame.log not found at {LOG_PATH} — log tailing disabled")
        return

    ctx.logger.info(f"Tailing {LOG_PATH}")
    async with aiofiles.open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
        await f.seek(0, 2)  # jump to end — skip old history
        while True:
            line = await f.readline()
            if line:
                line = line.strip()
                if _INTERESTING.search(line):
                    _recent_log_events.append(line)
                    if len(_recent_log_events) > 20:
                        _recent_log_events.pop(0)
                    ctx.logger.info(f"Log event: {line[:80]}")
                    await _trigger_analysis(ctx)
            else:
                await asyncio.sleep(0.05)


# ── Agent setup ───────────────────────────────────────────────────────────────

collector = Agent(
    name="collector",
    seed="collector_seed_phrase",
    port=8010,
    endpoint=["http://127.0.0.1:8010/submit"],
)


@collector.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Collector running at: {collector.address}")
    asyncio.create_task(_tail_log(ctx))


# ── On-demand: player asks a question ────────────────────────────────────────

@collector.on_message(model=PlayerQuery)
async def handle_player_query(ctx: Context, sender: str, msg: PlayerQuery):
    ctx.logger.info(f"Player query: '{msg.text}'")
    await _trigger_analysis(ctx, player_id=msg.player_id, player_query=msg.text)


if __name__ == "__main__":
    collector.run()
