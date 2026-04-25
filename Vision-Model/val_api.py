"""
Valorant Local API Client
Extracts game context: agents, loadouts, match state, party, and auth tokens.

Requirements:
    pip install requests urllib3

Usage:
    client = ValorantLocalClient()
    state = client.get_full_game_state()
    print(state)
"""

import os
import base64
import time
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

import requests
import urllib3

# Suppress SSL warnings for the self-signed local cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------

class GamePhase(Enum):
    MENUS       = "MENUS"
    PRE_GAME    = "PRE_GAME"       # Agent select
    IN_GAME     = "IN_GAME"        # Active match
    UNKNOWN     = "UNKNOWN"


@dataclass
class LockfileData:
    name:     str
    pid:      int
    port:     int
    password: str
    protocol: str


@dataclass
class AuthTokens:
    access_token:      str = ""
    entitlement_token: str = ""
    puuid:             str = ""
    region:            str = ""


@dataclass
class PlayerLoadout:
    puuid:       str = ""
    gun_ids:     list = field(default_factory=list)   # Weapon item UUIDs equipped
    spray_ids:   list = field(default_factory=list)
    card_id:     str = ""
    title_id:    str = ""


@dataclass
class PreGamePlayer:
    puuid:            str = ""
    team_id:          str = ""
    character_id:     str = ""   # Agent UUID
    character_locked: bool = False
    competitive_tier: int = 0


@dataclass
class PreGameMatch:
    match_id:    str = ""
    map_id:      str = ""
    mode:        str = ""
    team_one:    list = field(default_factory=list)   # List[PreGamePlayer]
    team_two:    list = field(default_factory=list)


@dataclass
class CurrentGamePlayer:
    puuid:        str = ""
    team_id:      str = ""
    character_id: str = ""
    is_coach:     bool = False


@dataclass
class CurrentGameMatch:
    match_id:          str = ""
    map_id:            str = ""
    mode:              str = ""
    provisioning_flow: str = ""
    game_pod_id:       str = ""
    all_players:       list = field(default_factory=list)  # List[CurrentGamePlayer]
    team_one:          list = field(default_factory=list)
    team_two:          list = field(default_factory=list)
    loadouts:          list = field(default_factory=list)  # List[PlayerLoadout]


@dataclass
class PartyMember:
    puuid:            str = ""
    is_owner:         bool = False
    competitive_tier: int = 0
    player_identity:  dict = field(default_factory=dict)


@dataclass
class PartyState:
    party_id:        str = ""
    state:           str = ""   # e.g. "DEFAULT", "MATCHMAKING"
    queue_id:        str = ""
    members:         list = field(default_factory=list)  # List[PartyMember]
    accessibility:   str = ""


@dataclass
class FullGameState:
    phase:            GamePhase = GamePhase.UNKNOWN
    puuid:            str = ""
    auth:             AuthTokens = field(default_factory=AuthTokens)
    party:            Optional[PartyState] = None
    pre_game_match:   Optional[PreGameMatch] = None
    current_game:     Optional[CurrentGameMatch] = None
    raw_errors:       list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lockfile Reader
# ---------------------------------------------------------------------------

LOCKFILE_PATH = os.path.expandvars(
    r"%LOCALAPPDATA%\Riot Games\Riot Client\Config\lockfile"
)


def read_lockfile() -> LockfileData:
    """
    Parse the Riot Client lockfile.
    Valorant must be running — the file is created on launch, deleted on exit.
    """
    if not os.path.exists(LOCKFILE_PATH):
        raise FileNotFoundError(
            "Lockfile not found. Make sure Valorant is running.\n"
            f"Expected path: {LOCKFILE_PATH}"
        )
    with open(LOCKFILE_PATH, "r") as f:
        parts = f.read().strip().split(":")
    if len(parts) != 5:
        raise ValueError(f"Unexpected lockfile format: {parts}")
    return LockfileData(
        name=parts[0],
        pid=int(parts[1]),
        port=int(parts[2]),
        password=parts[3],
        protocol=parts[4],
    )


# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------

class ValorantLocalClient:
    """
    Client for the Valorant Local (in-process) API and the remote PVP/Party APIs.
    Automatically reads the lockfile on construction.
    """

    LOCAL_BASE  = "https://127.0.0.1:{port}"
    REMOTE_BASE = "https://glz-{region}-1.{shard}.a.pvp.net"
    PD_BASE     = "https://pd.{shard}.a.pvp.net"

    # Mapping of region strings to shard
    REGION_SHARD = {
        "na": "na", "latam": "na", "br": "na",
        "eu": "eu", "ap": "ap", "kr": "kr",
    }

    def __init__(self):
        self.lockfile = read_lockfile()
        self._session = requests.Session()
        self._session.verify = False  # Self-signed local cert

        raw = f"riot:{self.lockfile.password}"
        encoded = base64.b64encode(raw.encode()).decode()
        self._local_headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type":  "application/json",
        }

        self.auth = AuthTokens()
        self._remote_headers: dict = {}
        self._refresh_auth()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _local(self, path: str) -> str:
        return f"https://127.0.0.1:{self.lockfile.port}{path}"

    def _get_local(self, path: str) -> Optional[dict]:
        try:
            r = self._session.get(self._local(path), headers=self._local_headers, timeout=3)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            log.debug("Local GET %s → %s", path, e.response.status_code)
            return None
        except Exception as e:
            log.debug("Local GET %s error: %s", path, e)
            return None

    def _get_remote(self, url: str) -> Optional[dict]:
        try:
            r = self._session.get(url, headers=self._remote_headers, timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.debug("Remote GET %s error: %s", url, e)
            return None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _refresh_auth(self):
        """Fetch auth tokens from the local entitlements endpoint."""
        data = self._get_local("/entitlements/v1/token")
        if not data:
            log.warning("Could not fetch auth tokens — is Valorant fully loaded?")
            return

        self.auth.access_token      = data.get("accessToken", "")
        self.auth.entitlement_token = data.get("token", "")
        self.auth.puuid             = data.get("subject", "")

        # Get region from client region endpoint
        region_data = self._get_local("/rso-auth/v1/authorization/userinfo")
        if region_data:
            acct = region_data.get("acct", {})
            self.auth.region = acct.get("country", "na")

        self._remote_headers = {
            "Authorization":               f"Bearer {self.auth.access_token}",
            "X-Riot-Entitlements-JWT":     self.auth.entitlement_token,
            "X-Riot-ClientVersion":        self._get_client_version(),
            "X-Riot-ClientPlatform":       self._get_client_platform(),
            "Content-Type":                "application/json",
        }

        log.info("Auth loaded for PUUID: %s", self.auth.puuid)

    def _get_client_version(self) -> str:
        data = self._get_local("/product-session/v1/external-sessions")
        if data:
            for v in data.values():
                version = v.get("version", "")
                if version:
                    # Format: branch-shipping-version-build
                    parts = version.split(".")
                    if len(parts) >= 4:
                        return f"release-{parts[0]}.{parts[1]}-shipping-{parts[2]}-{parts[3]}"
        return "release-00.00-shipping-00-000000"

    def _get_client_platform(self) -> str:
        platform = {
            "platformType": "PC",
            "platformOS": "Windows",
            "platformOSVersion": "10.0.19042.1.256.64bit",
            "platformChipset": "Unknown"
        }
        return base64.b64encode(json.dumps(platform).encode()).decode()

    def _glz_url(self, path: str) -> str:
        region = self.auth.region or "na"
        shard  = self.REGION_SHARD.get(region, "na")
        return f"https://glz-{region}-1.{shard}.a.pvp.net{path}"

    def _pd_url(self, path: str) -> str:
        region = self.auth.region or "na"
        shard  = self.REGION_SHARD.get(region, "na")
        return f"https://pd.{shard}.a.pvp.net{path}"

    # ------------------------------------------------------------------
    # Local API — Identity & Sessions
    # ------------------------------------------------------------------

    def get_puuid(self) -> str:
        return self.auth.puuid

    def get_sessions(self) -> Optional[dict]:
        """All active Riot client sessions (Valorant, client, etc.)."""
        return self._get_local("/product-session/v1/external-sessions")

    def get_chat_session(self) -> Optional[dict]:
        """Local chat session info including game_name and tag line."""
        return self._get_local("/chat/v1/session")

    def get_friends(self) -> list:
        """Full friends list with presence data."""
        data = self._get_local("/chat/v6/friends")
        if data:
            return data.get("friends", [])
        return []

    def get_presence(self) -> list:
        """
        Presence for all friends — contains encoded game state JSON
        showing queue, party size, rank, etc.
        """
        data = self._get_local("/chat/v4/presences")
        if not data:
            return []
        presences = data.get("presences", [])
        # Decode the private field (base64 JSON) for each presence
        for p in presences:
            private = p.get("private", "")
            if private:
                try:
                    p["private_decoded"] = json.loads(
                        base64.b64decode(private).decode()
                    )
                except Exception:
                    p["private_decoded"] = {}
        return presences

    # ------------------------------------------------------------------
    # Local API — Party
    # ------------------------------------------------------------------

    def get_party_player(self) -> Optional[dict]:
        """Raw party player data for the local player."""
        puuid = self.get_puuid()
        if not puuid:
            return None
        return self._get_remote(self._glz_url(f"/parties/v1/players/{puuid}"))

    def get_party(self, party_id: str) -> Optional[dict]:
        """Full party state by party ID."""
        return self._get_remote(self._glz_url(f"/parties/v1/parties/{party_id}"))

    def get_party_state(self) -> Optional[PartyState]:
        """Structured party state for the local player's current party."""
        player_data = self.get_party_player()
        if not player_data:
            return None

        party_id = player_data.get("CurrentPartyID", "")
        if not party_id:
            return None

        raw = self.get_party(party_id)
        if not raw:
            return None

        members = []
        for m in raw.get("Members", []):
            members.append(PartyMember(
                puuid=m.get("Subject", ""),
                is_owner=(m.get("Subject") == raw.get("MembersByTeam", {}).get("TeamOne", [None])[0]),
                competitive_tier=m.get("CompetitiveTier", 0),
                player_identity=m.get("PlayerIdentity", {}),
            ))

        return PartyState(
            party_id=party_id,
            state=raw.get("State", ""),
            queue_id=raw.get("MatchmakingData", {}).get("QueueID", ""),
            members=members,
            accessibility=raw.get("Accessibility", ""),
        )

    # ------------------------------------------------------------------
    # Pre-Game (Agent Select)
    # ------------------------------------------------------------------

    def get_pregame_player(self) -> Optional[dict]:
        """Returns the pre-game match ID if in agent select."""
        puuid = self.get_puuid()
        if not puuid:
            return None
        return self._get_remote(self._glz_url(f"/pregame/v1/players/{puuid}"))

    def get_pregame_match(self, match_id: str) -> Optional[dict]:
        return self._get_remote(self._glz_url(f"/pregame/v1/matches/{match_id}"))

    def get_pregame_loadouts(self, match_id: str) -> Optional[dict]:
        return self._get_remote(self._glz_url(f"/pregame/v1/matches/{match_id}/loadouts"))

    def get_pregame_state(self) -> Optional[PreGameMatch]:
        """Structured pre-game state: all players, agents, lock status."""
        player_data = self.get_pregame_player()
        if not player_data:
            return None

        match_id = player_data.get("MatchID", "")
        if not match_id:
            return None

        raw = self.get_pregame_match(match_id)
        if not raw:
            return None

        team_one, team_two = [], []
        for team in raw.get("Teams", []):
            team_id = team.get("TeamID", "")
            for p in team.get("Players", []):
                player = PreGamePlayer(
                    puuid=p.get("Subject", ""),
                    team_id=team_id,
                    character_id=p.get("CharacterID", ""),
                    character_locked=p.get("CharacterSelectionState", "") == "locked",
                    competitive_tier=p.get("CompetitiveTier", 0),
                )
                if team_id == "TeamOne":
                    team_one.append(player)
                else:
                    team_two.append(player)

        return PreGameMatch(
            match_id=match_id,
            map_id=raw.get("MapID", ""),
            mode=raw.get("Mode", ""),
            team_one=team_one,
            team_two=team_two,
        )

    # ------------------------------------------------------------------
    # Current Game (In Match)
    # ------------------------------------------------------------------

    def get_coregame_player(self) -> Optional[dict]:
        """Returns current game match ID if in an active match."""
        puuid = self.get_puuid()
        if not puuid:
            return None
        return self._get_remote(self._glz_url(f"/core-game/v1/players/{puuid}"))

    def get_coregame_match(self, match_id: str) -> Optional[dict]:
        return self._get_remote(self._glz_url(f"/core-game/v1/matches/{match_id}"))

    def get_coregame_loadouts(self, match_id: str) -> Optional[dict]:
        return self._get_remote(self._glz_url(f"/core-game/v1/matches/{match_id}/loadouts"))

    def get_current_game_state(self) -> Optional[CurrentGameMatch]:
        """
        Structured current game state:
        - All players with agent assignments
        - Per-player loadouts (weapons, sprays, card, title)
        """
        player_data = self.get_coregame_player()
        if not player_data:
            return None

        match_id = player_data.get("MatchID", "")
        if not match_id:
            return None

        raw          = self.get_coregame_match(match_id)
        raw_loadouts = self.get_coregame_loadouts(match_id)
        if not raw:
            return None

        all_players, team_one, team_two = [], [], []
        for p in raw.get("Players", []):
            team_id = p.get("TeamID", "")
            player = CurrentGamePlayer(
                puuid=p.get("Subject", ""),
                team_id=team_id,
                character_id=p.get("CharacterID", ""),
                is_coach=p.get("IsCoach", False),
            )
            all_players.append(player)
            if team_id == "Red":
                team_one.append(player)
            else:
                team_two.append(player)

        # Parse loadouts
        loadouts = []
        if raw_loadouts:
            for lo in raw_loadouts.get("Loadouts", []):
                items  = lo.get("Loadout", {}).get("Items", {})
                gun_ids, spray_ids = [], []
                card_id, title_id  = "", ""

                for item_type_id, item_data in items.items():
                    # Weapon type IDs start with known prefixes
                    # We store all item IDs with their type for downstream resolution
                    gun_ids.append({
                        "type_id": item_type_id,
                        "item_id": item_data.get("ID", ""),
                        "chroma":  item_data.get("Sockets", {})
                    })

                loadouts.append(PlayerLoadout(
                    puuid=lo.get("Subject", ""),
                    gun_ids=gun_ids,
                    spray_ids=spray_ids,
                    card_id=card_id,
                    title_id=title_id,
                ))

        return CurrentGameMatch(
            match_id=match_id,
            map_id=raw.get("MapID", ""),
            mode=raw.get("ModeID", ""),
            provisioning_flow=raw.get("ProvisioningFlow", ""),
            game_pod_id=raw.get("GamePodID", ""),
            all_players=all_players,
            team_one=team_one,
            team_two=team_two,
            loadouts=loadouts,
        )

    # ------------------------------------------------------------------
    # Phase Detection
    # ------------------------------------------------------------------

    def get_game_phase(self) -> GamePhase:
        """Determine whether the player is in menus, agent select, or in-game."""
        if self.get_coregame_player():
            return GamePhase.IN_GAME
        if self.get_pregame_player():
            return GamePhase.PRE_GAME
        return GamePhase.MENUS

    # ------------------------------------------------------------------
    # Full State (single call)
    # ------------------------------------------------------------------

    def get_full_game_state(self) -> FullGameState:
        """
        Top-level call that returns everything relevant for the current phase.
        Refreshes auth tokens before fetching to avoid stale tokens.
        """
        self._refresh_auth()
        state = FullGameState(puuid=self.auth.puuid, auth=self.auth)

        try:
            state.phase = self.get_game_phase()
            log.info("Game phase: %s", state.phase.value)

            state.party = self.get_party_state()

            if state.phase == GamePhase.PRE_GAME:
                state.pre_game_match = self.get_pregame_state()

            elif state.phase == GamePhase.IN_GAME:
                state.current_game = self.get_current_game_state()

        except Exception as e:
            state.raw_errors.append(str(e))
            log.error("Error building game state: %s", e)

        return state


# ---------------------------------------------------------------------------
# Polling Loop
# ---------------------------------------------------------------------------

def poll_game_state(interval_seconds: float = 1.0, on_state=None):
    """
    Continuously poll for game state at the given interval.

    Args:
        interval_seconds: How often to poll (default 1s).
        on_state: Optional callback(FullGameState) called on each update.
                  If None, state is printed as JSON.
    """
    client = ValorantLocalClient()
    log.info("Starting poll loop every %.1fs — Ctrl+C to stop", interval_seconds)

    while True:
        try:
            state = client.get_full_game_state()

            if on_state:
                on_state(state)
            else:
                # Default: pretty-print as JSON
                def _default(o):
                    if isinstance(o, GamePhase):
                        return o.value
                    if hasattr(o, "__dataclass_fields__"):
                        return asdict(o)
                    return str(o)

                print(json.dumps(asdict(state), indent=2, default=str))

        except FileNotFoundError as e:
            log.warning("Waiting for Valorant to launch... (%s)", e)
        except Exception as e:
            log.error("Unexpected error: %s", e)

        time.sleep(interval_seconds)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Valorant Local API Client")
    parser.add_argument("--poll", action="store_true",
                        help="Continuously poll game state")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Poll interval in seconds (default: 1.0)")
    args = parser.parse_args()

    if args.poll:
        poll_game_state(interval_seconds=args.interval)
    else:
        try:
            client = ValorantLocalClient()
            state  = client.get_full_game_state()

            def _default(o):
                if isinstance(o, GamePhase): return o.value
                if hasattr(o, "__dataclass_fields__"): return asdict(o)
                return str(o)

            print(json.dumps(asdict(state), indent=2, default=str))
        except FileNotFoundError as e:
            print(f"Error: {e}")