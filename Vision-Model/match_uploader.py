import os
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import dotenv
import requests
from google import genai
from google.genai import types
from auth_manager import get_supabase_client

dotenv.load_dotenv(dotenv.find_dotenv())

@dataclass
class UploadConfig:
    profile_id: str
    region: str
    name: str
    tag: str
    access_token: str = ""
    mode: str = "competitive"
    size: int = 10

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _extract_match_id(match: dict[str, Any]) -> str:
    for key in ("match_id", "matchId", "id"):
        if key in match and match[key]:
            return str(match[key])
    meta = match.get("metadata") or {}
    for key in ("matchid", "match_id", "id"):
        if key in meta and meta[key]:
            return str(meta[key])
    return ""

def _extract_played_at(match: dict[str, Any]) -> Optional[str]:
    meta = match.get("metadata", {})
    candidates = [
        meta.get("game_start_patched"),
        meta.get("started_at"),
        match.get("started_at"),
    ]
    for c in candidates:
        if c:
            return str(c)
    ts = meta.get("game_start") or match.get("game_start")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return None

def _extract_player_stats(match: dict[str, Any], name: str, tag: str) -> dict[str, Any]:
    target_name = (name or "").strip().lower()
    target_tag = (tag or "").strip().lower()

    players = match.get("players") or []
    for p in players:
        p_name = str(p.get("name", "")).strip().lower()
        p_tag = str(p.get("tag", "")).strip().lower()
        if p_name == target_name and p_tag == target_tag:
            return p

    return players[0] if players else {}

def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val)
    except Exception:
        return None

def _safe_int(val: Any) -> Optional[int]:
    try:
        return int(val)
    except Exception:
        return None

def _compute_outcome(match: dict[str, Any], player: dict[str, Any]) -> Optional[str]:
    won = player.get("won")
    if isinstance(won, bool):
        return "win" if won else "loss"

    teams = match.get("teams") or []
    player_team = player.get("team")
    for t in teams:
        if t.get("team") == player_team and isinstance(t.get("won"), bool):
            return "win" if t.get("won") else "loss"
    return "draw"

def _compute_score(match: dict[str, Any]) -> Optional[str]:
    teams = match.get("teams") or []
    if len(teams) < 2:
        return None
    s1 = teams[0].get("rounds", {}).get("won")
    s2 = teams[1].get("rounds", {}).get("won")
    if s1 is None or s2 is None:
        return None
    return f"{s1}-{s2}"

def get_ai_match_summary(player_name: str, agent: str, map_name: str, outcome: str, player: dict[str, Any]) -> dict:
    """Uses Gemini to generate post-match coaching insights."""
    print("[SpectAI] Generating post-match AI summary using Gemini...")
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    stats = player.get("stats", {})
    kills = stats.get("kills", 0)
    deaths = stats.get("deaths", 0)
    assists = stats.get("assists", 0)
    score = stats.get("score", 0)
    
    total_shots = stats.get("headshots", 0) + stats.get("bodyshots", 0) + stats.get("legshots", 0)
    headshot_pct = round((stats.get("headshots", 0) / total_shots * 100)) if total_shots > 0 else 0
    
    prompt = f"""
    You are a professional Valorant coach. Analyze this recent match for {player_name}:
    Map: {map_name} | Agent: {agent} | Outcome: {outcome}
    Stats: {kills} Kills, {deaths} Deaths, {assists} Assists. 
    Score: {score}. Headshot %: {headshot_pct}%.
    
    Provide a short, constructive summary of their performance, exactly 2 strengths, exactly 2 weaknesses, and 2 next steps.
    Respond ONLY with valid JSON in this exact format:
    {{"summary": "...", "strengths": ["...", "..."], "weaknesses": ["...", "..."], "next_steps": ["...", "..."]}}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n", 1)[0]
            
        parsed = json.loads(text)
        return {
            "summary": str(parsed.get("summary", "")).strip(),
            "strengths": [str(x) for x in (parsed.get("strengths") or [])][:3],
            "weaknesses": [str(x) for x in (parsed.get("weaknesses") or [])][:3],
            "next_steps": [str(x) for x in (parsed.get("next_steps") or [])][:3],
        }
    except Exception as e:
        print(f"[SpectAI] Failed to generate AI summary: {e}")
        return {
            "summary": "Match recorded successfully, but AI insights failed to generate.",
            "strengths": [],
            "weaknesses": [],
            "next_steps": []
        }

def _normalize_local_match(match: dict[str, Any]) -> dict[str, Any]:
    """Normalize Riot internal PD API match data to our shared format."""
    try:
        from valorant_resolver import ValorantResolver
        resolver = ValorantResolver()
    except Exception:
        resolver = None

    info = match.get("matchInfo", {})
    map_id = info.get("mapId", "")
    if resolver:
        map_info = resolver.resolve_map(map_id)
        map_name = map_info.name if map_info else map_id.split("/")[-1]
    else:
        map_name = map_id.split("/")[-1]

    teams_raw = match.get("teams", [])
    team_won = {t["teamId"]: t.get("won", False) for t in teams_raw}

    # Aggregate headshots/bodyshots/legshots from round damage events
    player_shots: dict[str, dict] = {}
    for rnd in match.get("roundResults", []):
        for ps in rnd.get("playerStats", []):
            puuid = ps.get("subject", "")
            if puuid not in player_shots:
                player_shots[puuid] = {"headshots": 0, "bodyshots": 0, "legshots": 0}
            for dmg in ps.get("damage", []):
                player_shots[puuid]["headshots"] += dmg.get("headshots", 0)
                player_shots[puuid]["bodyshots"] += dmg.get("bodyshots", 0)
                player_shots[puuid]["legshots"]  += dmg.get("legshots", 0)

    players = []
    for p in match.get("players", []):
        puuid = p.get("subject", "")
        tid   = p.get("teamId", "")
        s     = p.get("stats", {})
        char_id = p.get("characterId", "")
        if resolver:
            agent_info = resolver.resolve_agent(char_id)
            agent_name = agent_info.name if agent_info else char_id
        else:
            agent_name = char_id
        shots = player_shots.get(puuid, {})
        players.append({
            "name":              p.get("gameName", ""),
            "tag":               p.get("tagLine", ""),
            "team":              tid,
            "character":         agent_name,
            "won":               team_won.get(tid, False),
            "currenttier":       p.get("competitiveTier", 0),
            "currenttierpatched": str(p.get("competitiveTier", 0)),
            "stats": {
                "kills":    s.get("kills", 0),
                "deaths":   s.get("deaths", 0),
                "assists":  s.get("assists", 0),
                "score":    s.get("score", 0),
                "headshots": shots.get("headshots", 0),
                "bodyshots": shots.get("bodyshots", 0),
                "legshots":  shots.get("legshots", 0),
            },
        })

    teams = [
        {"team": t["teamId"], "won": t.get("won", False), "rounds": {"won": t.get("roundsWon", 0)}}
        for t in teams_raw
    ]
    ms = info.get("gameStartMillis", 0)
    return {
        "metadata": {
            "matchid":    info.get("matchId", ""),
            "map":        map_name,
            "game_start": ms / 1000 if ms else None,
            "queue_id":   info.get("queueID", ""),
        },
        "players": players,
        "teams":   teams,
    }


def _fetch_via_local_api(size: int, mode: str) -> list[dict[str, Any]]:
    """Use the running Valorant client's local API + Riot PD endpoints (no API key)."""
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        from valorant_local_api import ValorantLocalClient

        client = ValorantLocalClient()
        puuid  = client.auth.puuid
        if not puuid:
            return []

        region = client.auth.region or "na"
        shard  = client.REGION_SHARD.get(region, "na")
        pd_url = f"https://pd.{shard}.a.pvp.net"
        hdrs   = client._remote_headers

        # 1. Get recent match IDs via competitive updates
        params: dict[str, Any] = {"startIndex": 0, "endIndex": size}
        if mode and mode.lower() not in ("all", ""):
            params["queue"] = mode.lower()
        r = requests.get(
            f"{pd_url}/mmr/v1/players/{puuid}/competitiveupdates",
            headers=hdrs, params=params, timeout=15, verify=False,
        )
        r.raise_for_status()
        match_ids = [m["MatchID"] for m in r.json().get("Matches", [])]

        # 2. Fetch full details for each match
        matches = []
        for mid in match_ids[:size]:
            dr = requests.get(
                f"{pd_url}/match-details/v1/matches/{mid}",
                headers=hdrs, timeout=15, verify=False,
            )
            if dr.status_code == 200:
                matches.append(_normalize_local_match(dr.json()))

        print(f"[SpectAI] Local API: fetched {len(matches)} match(es).")
        return matches
    except Exception as e:
        print(f"[SpectAI] Local API unavailable ({e}), trying Henrik...")
        return []


def fetch_recent_matches(region: str, name: str, tag: str, size: int = 10, mode: str = "competitive") -> list[dict[str, Any]]:
    # 1. Try local Valorant client API (no key, richest data)
    matches = _fetch_via_local_api(size, mode)
    if matches:
        return matches

    # 2. Fall back to Henrik
    base    = os.getenv("HENRIK_BASE_URL", "https://api.henrikdev.xyz/valorant")
    api_key = os.getenv("HENRIK_API_KEY", "").strip() or os.getenv("HDEV_API_KEY", "").strip()
    headers: dict[str, str] = {}
    if api_key:
        url = f"{base}/v3/matches/{region}/{requests.utils.quote(name)}/{requests.utils.quote(tag)}"
        headers["Authorization"] = api_key
    else:
        url = f"{base}/v1/stored-matches/{region}/{requests.utils.quote(name)}/{requests.utils.quote(tag)}"
    params: dict[str, Any] = {"size": size}
    if mode and mode.lower() != "all":
        params["mode"] = mode
    resp = requests.get(url, headers=headers, params=params, timeout=25)
    resp.raise_for_status()
    payload = resp.json()
    raw = payload.get("data") or []
    return [m for m in raw if m.get("is_available", True) and m.get("metadata")]

def _mock_match(name: str, tag: str) -> dict[str, Any]:
    return {
        "metadata": {"matchid": "mock-match-001", "map": "Ascent", "game_start": 1745000000},
        "players": [{
            "name": name, "tag": tag, "team": "Blue", "character": "Jett", "won": True,
            "currenttierpatched": "Gold 2", "currenttier": 14,
            "stats": {"kills": 18, "deaths": 10, "assists": 4, "score": 4200,
                      "headshots": 8, "bodyshots": 20, "legshots": 2}
        }],
        "teams": [{"team": "Blue", "won": True, "rounds": {"won": 13}},
                  {"team": "Red",  "won": False, "rounds": {"won": 8}}],
    }

def upload_latest_match(config: UploadConfig) -> dict[str, Any]:
    """
    End-session pipeline:
    1) Fetch recent Henrik matches
    2) Pick newest
    3) Ask Gemini for summary
    4) Insert into match_data + player_stats + ai_summaries
    """
    print(f"[SpectAI] Fetching latest {config.mode} match for {config.name}#{config.tag}...")
    try:
        matches = fetch_recent_matches(
            region=config.region,
            name=config.name,
            tag=config.tag,
            size=config.size,
            mode=config.mode,
        )
    except Exception as e:
        print(f"[SpectAI] Henrik API unavailable ({e}) — using mock match for testing.")
        matches = [_mock_match(config.name, config.tag)]
    if not matches:
        matches = [_mock_match(config.name, config.tag)]

    latest = matches[0]

    match_id = _extract_match_id(latest)
    if not match_id:
        raise RuntimeError("Could not determine match_id from Henrik payload.")

    sb = get_supabase_client()
    if config.access_token:
        sb.auth.set_session(config.access_token, config.access_token)

    # GUARD: Check if match is already in database before processing
    print("[SpectAI] Checking if match already exists in database...")
    existing = sb.table("match_data").select("match_id").eq("profile_id", config.profile_id).eq("match_id", match_id).limit(1).execute()
    
    if existing.data:
        print(f"[SpectAI] Match {match_id} already exists. Skipping upload.")
        return {
            "ok": True,
            "skipped": True,
            "profile_id": config.profile_id,
            "match_id": match_id,
            "message": "Match already exists in database."
        }

    player = _extract_player_stats(latest, config.name, config.tag)
    
    metadata = latest.get("metadata", {})
    map_name = metadata.get("map") or metadata.get("map_name")
    agent_name = player.get("character")
    outcome = _compute_outcome(latest, player)
    
    summary = get_ai_match_summary(config.name, agent_name, map_name, outcome, player)

    # 1. INSERT MATCH DATA
    print("[SpectAI] Uploading match stats to database...")
    row = {
        "profile_id": config.profile_id,
        "match_id": match_id,
        "played_at": _extract_played_at(latest),
        "uploaded_at": _utc_now_iso(),
        "schema_version": 1,
        "data": latest,
        "coach_notes": {
            "summary": summary.get("summary", ""),
            "strengths": summary.get("strengths", []),
            "weaknesses": summary.get("weaknesses", []),
        },
        "training_plan": {
            "next_steps": summary.get("next_steps", []),
        },
        "performance_summary": json.dumps({
            "score": _compute_score(latest),
            "k": player.get("stats", {}).get("kills"),
            "d": player.get("stats", {}).get("deaths"),
            "a": player.get("stats", {}).get("assists"),
            "headshots": player.get("stats", {}).get("headshots"),
        }),
    }
    sb.table("match_data").insert(row).execute()

    # 2. INSERT PLAYER STATS
    stats = player.get("stats", {})
    kills = _safe_float(stats.get("kills")) or 0.0
    deaths = _safe_float(stats.get("deaths")) or 0.0
    assists = _safe_float(stats.get("assists")) or 0.0
    headshots = _safe_float(stats.get("headshots")) or 0.0

    kd_ratio = kills / deaths if deaths > 0 else kills
    hs_pct = (headshots / kills * 100.0) if kills > 0 else 0.0

    stats_payload = {
        "profile_id": config.profile_id,
        "synced_at": _utc_now_iso(),
        "current_rank": player.get("currenttierpatched") or player.get("rank"),
        "rank_tier": _safe_int(player.get("currenttier")),
        "kd_ratio": kd_ratio,
        "headshot_pct": hs_pct,
        "avg_score": _safe_float(stats.get("score")),
        "avg_damage": _safe_float(stats.get("damage")),
        "avg_kills": kills,
        "avg_deaths": deaths,
        "avg_assists": assists,
        "aces": _safe_int(stats.get("aces")) or 0,
        "agent_prefs": {"last_agent": agent_name},
        "playstyle_desc": summary.get("summary", ""),
        "ai_summary": summary.get("summary", ""),
        "ai_strengths": summary.get("strengths", []),
        "ai_weaknesses": summary.get("weaknesses", [])
    }
    sb.table("player_stats").insert(stats_payload).execute()

    # 3. UPSERT AI SUMMARIES TABLE
    print("[SpectAI] Uploading AI summary to dashboard...")
    sb.table("ai_summaries").upsert({
        "profile_id": config.profile_id,
        "summary": summary.get("summary", ""),
        "strengths": summary.get("strengths", []),
        "weaknesses": summary.get("weaknesses", []),
        "updated_at": _utc_now_iso()
    }).execute()

    return {
        "ok": True,
        "profile_id": config.profile_id,
        "match_id": match_id,
        "map": map_name,
        "agent": agent_name,
        "summary": summary,
    }


def upload_attachment(profile_id: str, match_id: str, file_path: str, access_token: str = "") -> str:
    """
    Upload a video/clip file to Supabase Storage and attach its URL to the match.
    Returns the public URL of the uploaded file.
    Bucket: match-clips (create it in Supabase Storage dashboard if it doesn't exist)
    """
    import mimetypes
    import httpx

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    # Service role key bypasses Storage RLS; fall back to user JWT
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    auth_key = service_key or access_token or anon_key

    file_name = os.path.basename(file_path)
    storage_path = f"{profile_id}/{match_id}/{file_name}"
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    upload_url = f"{supabase_url}/storage/v1/object/match-clips/{storage_path}"
    headers = {
        "Authorization": f"Bearer {auth_key}",
        "apikey": anon_key,
        "x-upsert": "true",
    }

    print(f"[SpectAI] Uploading attachment {file_name} to Supabase Storage...")
    with open(file_path, "rb") as f:
        data = f.read()
    resp = httpx.post(upload_url, content=data, headers={**headers, "Content-Type": mime_type}, timeout=120)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Storage upload failed {resp.status_code}: {resp.text}")

    public_url = f"{supabase_url}/storage/v1/object/public/match-clips/{storage_path}"
    print(f"[SpectAI] Attachment uploaded: {public_url}")

    # Append URL to match_data.attachments (max 5)
    sb = get_supabase_client()
    if access_token:
        sb.auth.set_session(access_token, access_token)
    existing = sb.table("match_data").select("attachments").eq("profile_id", profile_id).eq("match_id", match_id).limit(1).execute()
    if existing.data:
        current = existing.data[0].get("attachments") or []
        if public_url not in current:
            current = (current + [public_url])[:5]
            sb.table("match_data").update({"attachments": current}).eq("profile_id", profile_id).eq("match_id", match_id).execute()

    return public_url
