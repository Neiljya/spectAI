import os
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
    player_query: str = None
) -> str:
    """
    Takes all 3 inputs:
      - screenshot_b64   : raw base64 JPEG of the game screen
      - profile          : full player profile (rank, agent, playstyle, weaknesses)
      - player_query     : optional voice/text question from the player

    Returns one rich plain-text game-state summary for Fetch.ai agents.
    Gemini is the ONLY component that ever sees images.
    """

    prompt = f"""You are a Valorant game state analyzer.

PLAYER PROFILE:
- Player ID  : {profile.player_id}
- Rank       : {profile.rank}
- Agent      : {profile.agent_name}
- Playstyle  : {profile.playstyle}
- IGL        : {"Yes" if profile.igl else "No"}
- Strengths  : {", ".join(profile.strengths)}
- Weak areas : {", ".join(profile.weak_areas)}

{"PLAYER QUESTION: " + player_query if player_query else ""}

Analyze the screenshot above in the full context of this player's profile.
Describe in plain text, covering ALL of the following:

GAME STATE:
- Map area and player's current location
- Visible enemies and their positions
- Visible teammates and their positions
- Minimap state: rotations, coverage gaps
- Round number, time remaining, spike status (planted / held / none)
- Current score (attacker vs defender rounds)

ECONOMY:
- Player credits, weapon equipped, armor status
- Visible teammate loadouts if shown

MECHANICS OBSERVATIONS:
- Crosshair placement relative to likely enemy angles
- Whether player is moving or stationary
- Any spray or aim patterns visible in the frame

MENTAL / BEHAVIORAL SIGNALS:
- Any patterns suggesting tilt, aggression, or passivity
- Communication indicators if visible (muted teammates, etc.)

PROFILE FIT:
- How the current situation relates to this player's known weak areas
- Whether their playstyle is appropriate for the current round state

Be factual and specific. Do NOT give coaching advice yet.
This text will be passed to three specialist coaching agents (gamesense, mechanics, mental)
who will each produce targeted coaching calls from it."""

    img_bytes = base64.b64decode(screenshot_b64)
    img = Image.open(io.BytesIO(img_bytes))

    response = model.generate_content([prompt, img])
    return response.text
