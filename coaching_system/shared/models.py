from uagents import Model
from typing import Optional, List


class PlayerProfile(Model):
    player_id: str
    rank: str
    agent_name: str        # e.g. "Jett", "Sova"
    playstyle: str         # e.g. "aggressive entry"
    igl: bool
    strengths: List[str]
    weak_areas: List[str]


class GameFrame(Model):
    player_id: str
    screenshot_b64: str    # raw base64 — only used inside collector before Gemini
    timestamp: float
    map_name: str
    round_num: int


class PlayerQuery(Model):
    player_id: str
    text: str              # transcribed voice or typed query
    timestamp: float


class AnalysisRequest(Model):
    profile: PlayerProfile
    game_state_text: str   # Gemini's synthesized text — only thing Fetch.ai sees
    round_num: int
    map_name: str
    player_query: Optional[str] = None


class AgentReport(Model):
    agent_type: str        # "gamesense" | "mechanics" | "mental"
    player_id: str
    findings: str
    priority: str          # "high" | "medium" | "low"
    action_call: str       # the actual live coaching line to deliver
