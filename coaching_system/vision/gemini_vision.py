import os
import json
import google.generativeai as genai
import base64
import io
from PIL import Image
from dotenv import load_dotenv
from shared.models import PlayerProfile

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")


async def analyze_all(
    screenshot_b64: str,
    profile: PlayerProfile,
    log_events: str = None,
    api_data: dict = None,
    player_query: str = None,
) -> dict:
    """
    Takes all data sources and returns a structured dict.
    Gemini is the ONLY component that ever sees images.

    Returns dict with keys: should_coach, urgency, game_state_text,
    round_num, map_name, time_remaining, score, credits, spike_status,
    agent_name, health, armor, weapon, position, crosshair_placement,
    in_gunfight, is_shooting, is_moving, teammates_alive, enemies_alive,
    visible_enemies, recent_death
    """

    api_section = ""
    if api_data:
        api_section = f"\nVALORANT API DATA:\n{json.dumps(api_data, indent=2)}\n"

    log_section = ""
    if log_events:
        log_section = f"\nRECENT SHOOTERGAME.LOG EVENTS:\n{log_events}\n"

    prompt = f"""You are a Valorant game state analyzer. Analyze all provided data sources and return a single JSON object.

PLAYER PROFILE:
- Player ID  : {profile.player_id}
- Rank       : {profile.rank}
- Agent      : {profile.agent_name}
- Playstyle  : {profile.playstyle}
- IGL        : {"Yes" if profile.igl else "No"}
- Strengths  : {", ".join(profile.strengths)}
- Weak areas : {", ".join(profile.weak_areas)}
{api_section}{log_section}
{"PLAYER QUESTION: " + player_query if player_query else ""}

Analyze the screenshot and all other data sources above.

Return ONLY a valid JSON object with these exact keys (no markdown, no extra text):
{{
  "should_coach": true or false,
  "urgency": "high" or "medium" or "low",
  "game_state_text": "3-5 sentence narrative summary of the full game state for coaching agents",
  "round_num": integer or null,
  "map_name": "map name or empty string",
  "time_remaining": float seconds or null,
  "score": "attacker-defender e.g. 5-3" or null,
  "credits": integer or null,
  "spike_status": "none" or "planted" or "defusing" or "held",
  "agent_name": "Valorant agent name e.g. Jett",
  "health": integer 0-100,
  "armor": true or false,
  "weapon": "weapon name e.g. Vandal",
  "position": "map area e.g. B Site",
  "crosshair_placement": "head_level" or "off_angle" or "ground" or "unknown",
  "in_gunfight": true or false,
  "is_shooting": true or false,
  "is_moving": true or false,
  "teammates_alive": integer,
  "enemies_alive": integer,
  "visible_enemies": integer,
  "recent_death": true or false
}}

Set should_coach=true only when there is an actionable coaching moment right now (gunfight, spike event, positional mistake, economic decision, tilt signal).
Set urgency based on how time-sensitive the coaching call is."""

    img_bytes = base64.b64decode(screenshot_b64)
    img = Image.open(io.BytesIO(img_bytes))

    response = model.generate_content([prompt, img])
    raw = response.text.strip()

    # Strip markdown code fences if Gemini wraps the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "should_coach": False,
            "urgency": "low",
            "game_state_text": raw,
            "round_num": 0,
            "map_name": "",
            "spike_status": "none",
        }
