import asyncio
import os
import subprocess
import tempfile

import httpx
from uagents import Agent, Context
from dotenv import load_dotenv

from shared.models import AnalysisRequest, PlayerQuery, AgentReport
from shared.player_store import PLAYER_PROFILES

load_dotenv()

# ── ElevenLabs TTS ────────────────────────────────────────────────────────────
_ELEVENLABS_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
_ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George — deep, clear coaching voice


def _speak_sync(text: str):
    """Calls ElevenLabs REST API, saves MP3, plays via ffplay. Runs in a thread."""
    if not _ELEVENLABS_KEY:
        return
    resp = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{_ELEVENLABS_VOICE}",
        headers={"xi-api-key": _ELEVENLABS_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=15,
    )
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(resp.content)
        tmp_path = f.name
    subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path]
    )


# Paste each specialist agent's printed address here after running them first
GAMESENSE_ADDR = "agent1qftwnuxfh4weyqqc9pmeswmlug4vtk28fcxm7ywl6s38gxr5cf8lcy69jes"
MECHANICS_ADDR = "agent1qt7afg76l48n8h60w682zr28wwt2anw2kupltl5tgv8uqzk60eh4uc29a5r"
MENTAL_ADDR    = "agent1q28kxlqfyl60z9fap0058fh2wa7zkpd9dx3h9n6j5nu7w7656qlwyu69du0"

orchestrator = Agent(
    name="orchestrator",
    seed="spectai_orchestrator_siddharth_2026",
    port=8000,
    endpoint=["http://127.0.0.1:8000/submit"]
)

# Buffer to collect reports from all 3 agents before synthesizing output
reports_buffer: dict[str, list[AgentReport]] = {}


@orchestrator.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Orchestrator running at: {orchestrator.address}")
    ctx.logger.info("Waiting for analysis requests...")


# ── Receive text analysis from collector, fan out to all 3 agents ─────────────
@orchestrator.on_message(model=AnalysisRequest)
async def handle_analysis(ctx: Context, sender: str, msg: AnalysisRequest):
    ctx.logger.info(
        f"Received analysis for player {msg.profile.player_id} "
        f"— dispatching to all 3 agents..."
    )

    # Inject shared context already in msg.profile — dispatch to all 3 in parallel
    await asyncio.gather(
        ctx.send(GAMESENSE_ADDR, msg),
        ctx.send(MECHANICS_ADDR, msg),
        ctx.send(MENTAL_ADDR, msg)
    )


# ── Receive on-demand player query directly (fallback if not via collector) ───
@orchestrator.on_message(model=PlayerQuery)
async def handle_direct_query(ctx: Context, sender: str, msg: PlayerQuery):
    profile = PLAYER_PROFILES.get(msg.player_id)
    if not profile:
        ctx.logger.error(f"No profile for {msg.player_id}")
        return

    req = AnalysisRequest(
        profile=profile,
        game_state_text=f"Player asked: {msg.text}",
        round_num=0,
        map_name="",
        player_query=msg.text
    )
    await asyncio.gather(
        ctx.send(GAMESENSE_ADDR, req),
        ctx.send(MECHANICS_ADDR, req),
        ctx.send(MENTAL_ADDR, req)
    )


# ── Collect reports from agents, synthesize when all 3 arrive ────────────────
@orchestrator.on_message(model=AgentReport)
async def collect_report(ctx: Context, sender: str, msg: AgentReport):
    pid = msg.player_id
    if pid not in reports_buffer:
        reports_buffer[pid] = []

    reports_buffer[pid].append(msg)
    ctx.logger.info(
        f"Report received from {msg.agent_type} agent "
        f"({len(reports_buffer[pid])}/3)"
    )

    # Once all 3 agents have reported, synthesize and deliver coaching output
    if len(reports_buffer[pid]) >= 3:
        reports = reports_buffer.pop(pid)

        # Prioritise high-priority calls first
        high   = [r for r in reports if r.priority == "high"]
        medium = [r for r in reports if r.priority == "medium"]
        low    = [r for r in reports if r.priority == "low"]
        ordered = high or medium or low

        ctx.logger.info("━" * 60)
        ctx.logger.info("[COACHING OUTPUT]")
        for r in ordered:
            ctx.logger.info(f"  [{r.agent_type.upper()}] {r.action_call}")
        ctx.logger.info("━" * 60)

        # Speak the highest-priority action call via ElevenLabs
        top = ordered[0].action_call
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _speak_sync, top)


if __name__ == "__main__":
    orchestrator.run()
