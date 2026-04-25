from shared.models import PlayerProfile

# Central player profile store — shared across collector and orchestrator.
# In production, load these from a database or API.

PLAYER_PROFILES: dict[str, PlayerProfile] = {
    "player_001": PlayerProfile(
        player_id="player_001",
        rank="Diamond 2",
        agent_name="Jett",
        playstyle="aggressive entry",
        igl=False,
        strengths=["aim", "movement"],
        weak_areas=["util usage", "rotation timing"]
    )
}
