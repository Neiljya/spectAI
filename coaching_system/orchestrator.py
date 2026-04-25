import asyncio
import os
import subprocess
import tempfile
from typing import Optional

import httpx
from uagents import Agent, Context
from dotenv import load_dotenv
from supabase import create_client, Client

from shared.models import AnalysisRequest, PlayerQuery, AgentReport
from shared.player_store import PLAYER_PROFILES

load_dotenv()

# ── ElevenLabs TTS ────────────────────────────────────────────────────────────
_ELEVENLABS_KEY   = os.environ.get("ELEVENLABS_API_KEY", "")
_ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George — deep, clear coaching voice


def _speak_sync(text: str):
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


# ── Supabase ──────────────────────────────────────────────────────────────────
_sb: Optional[Client] = None
_profile_id_cache: dict[str, str] = {}   # riot_puuid → Supabase profiles.id
_current_match_uuid: Optional[str] = None
_current_map: str = ""


def _get_supabase() -> Optional[Client]:
    global _sb
    if _sb is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if url and key:
            _sb = create_client(url, key)
    return _sb


def _get_profile_id(riot_puuid: str) -> Optional[str]:
    if not riot_puuid:
        return None
    if riot_puuid in _profile_id_cache:
        return _profile_id_cache[riot_puuid]
    sb = _get_supabase()
    if not sb:
        return None
    try:
        result = sb.table("profiles").select("id").eq("riot_puuid", riot_puuid).maybe_single().execute()
        if result.data:
            _profile_id_cache[riot_puuid] = result.data["id"]
            return result.data["id"]
    except Exception as e:
        pass
    return None


def _get_or_create_match(profile_id: str, map_name: str, agent_name: str) -> Optional[str]:
    global _current_match_uuid, _current_map
    sb = _get_supabase()
    if not sb or not profile_id:
        return None
    if _current_match_uuid and _current_map == map_name:
        return _current_match_uuid
    try:
        result = sb.table("match_data").insert({
            "profile_id": profile_id,
            "data": {"map": map_name, "agent": agent_name},
        }).execute()
        _current_match_uuid = result.data[0]["id"]
        _current_map = map_name
    except Exception as e:
        pass
    return _current_match_uuid


def _write_to_supabase_sync(req: AnalysisRequest, reports: list):
    sb = _get_supabase()
    if not sb:
        return

    riot_puuid = req.profile.riot_puuid
    profile_id = _get_profile_id(riot_puuid)
    if not profile_id:
        return

    match_uuid = _get_or_create_match(profile_id, req.map_name, req.profile.agent_name)
    if not match_uuid:
        return

    try:
        event_result = sb.table("coaching_events").insert({
            "match_id": match_uuid,
            "profile_id": profile_id,
            "round_num": req.round_num,
            "position": req.position,
            "agent_name": req.profile.agent_name,
            "weapon": req.weapon,
            "health": req.health,
            "armor": req.armor,
            "spike_status": req.spike_status,
            "time_remaining": req.time_remaining,
            "urgency": req.urgency,
            "score": req.score,
            "credits": req.credits,
            "crosshair_placement": req.crosshair_placement,
            "in_gunfight": req.in_gunfight,
            "game_state_text": req.game_state_text,
            "recent_log_events": req.recent_events,
        }).execute()
        event_id = event_result.data[0]["id"]

        sb.table("agent_reports").insert([
            {
                "event_id": event_id,
                "agent_type": r.agent_type,
                "findings": r.findings,
                "priority": r.priority,
                "action_call": r.action_call,
            }
            for r in reports
        ]).execute()
    except Exception as e:
        pass


# ── Agent addresses ───────────────────────────────────────────────────────────
GAMESENSE_ADDR = "agent1qftwnuxfh4weyqqc9pmeswmlug4vtk28fcxm7ywl6s38gxr5cf8lcy69jes"
MECHANICS_ADDR = "agent1qt7afg76l48n8h60w682zr28wwt2anw2kupltl5tgv8uqzk60eh4uc29a5r"
MENTAL_ADDR    = "agent1q28kxlqfyl60z9fap0058fh2wa7zkpd9dx3h9n6j5nu7w7656qlwyu69du0"

orchestrator = Agent(
    name="orchestrator",
    seed="spectai_orchestrator_siddharth_2026",
    port=8000,
    endpoint=["http://127.0.0.1:8000/submit"]
)

# Buffer: player_id → {"req": AnalysisRequest, "reports": list[AgentReport]}
reports_buffer: dict[str, dict] = {}


@orchestrator.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Orchestrator running at: {orchestrator.address}")
    sb = _get_supabase()
    ctx.logger.info(f"Supabase: {'connected' if sb else 'not configured — set SUPABASE_URL + SUPABASE_ANON_KEY'}")


# ── Receive analysis from collector, store request, fan out to 3 agents ───────
@orchestrator.on_message(model=AnalysisRequest)
async def handle_analysis(ctx: Context, sender: str, msg: AnalysisRequest):
    pid = msg.profile.player_id
    reports_buffer[pid] = {"req": msg, "reports": []}
    ctx.logger.info(
        f"Analysis received — player {pid}, round {msg.round_num}, "
        f"urgency={msg.urgency}, spike={msg.spike_status}"
    )
    await asyncio.gather(
        ctx.send(GAMESENSE_ADDR, msg),
        ctx.send(MECHANICS_ADDR, msg),
        ctx.send(MENTAL_ADDR, msg)
    )


# ── On-demand player query ────────────────────────────────────────────────────
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
    pid = msg.player_id
    reports_buffer[pid] = {"req": req, "reports": []}
    await asyncio.gather(
        ctx.send(GAMESENSE_ADDR, req),
        ctx.send(MECHANICS_ADDR, req),
        ctx.send(MENTAL_ADDR, req)
    )


# ── Collect reports, synthesize + write to Supabase when all 3 arrive ─────────
@orchestrator.on_message(model=AgentReport)
async def collect_report(ctx: Context, sender: str, msg: AgentReport):
    pid = msg.player_id
    if pid not in reports_buffer:
        reports_buffer[pid] = {"req": None, "reports": []}

    reports_buffer[pid]["reports"].append(msg)
    count = len(reports_buffer[pid]["reports"])
    ctx.logger.info(f"Report from {msg.agent_type} ({count}/3)")

    if count >= 3:
        entry   = reports_buffer.pop(pid)
        reports = entry["reports"]
        req     = entry["req"]

        high    = [r for r in reports if r.priority == "high"]
        medium  = [r for r in reports if r.priority == "medium"]
        low     = [r for r in reports if r.priority == "low"]
        ordered = high or medium or low

        ctx.logger.info("━" * 60)
        ctx.logger.info("[COACHING OUTPUT]")
        for r in ordered:
            ctx.logger.info(f"  [{r.agent_type.upper()}] {r.action_call}")
        ctx.logger.info("━" * 60)

        # Speak top coaching call
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _speak_sync, ordered[0].action_call)

        # Write coaching event + all 3 agent reports to Supabase
        if req:
            loop.run_in_executor(None, _write_to_supabase_sync, req, reports)


if __name__ == "__main__":
    orchestrator.run()
