"""
Valorant UUID Resolver
Fetches and caches data from valorant-api.com to resolve raw UUIDs
into human-readable names, roles, abilities, weapon stats, and more.

Works standalone or alongside valorant_local_api.py.

Requirements:
    pip install requests

Usage:
    resolver = ValorantResolver()
    print(resolver.resolve_agent("8e253930-4c05-31dd-1b6c-968525494517"))
    print(resolver.resolve_weapon("9c82e19d-4575-0200-1a81-3eacf00cf872"))
    print(resolver.resolve_map("/Game/Maps/Ascent/Ascent"))
    print(resolver.resolve_mode("/Game/GameModes/Bomb/BombGameMode.BombGameMode_C"))
"""

import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import requests

log = logging.getLogger(__name__)

VALORANT_API_BASE = "https://valorant-api.com/v1"

# ---------------------------------------------------------------------------
# Known socket type UUIDs from the loadout data
# These identify what slot a chroma/buddy/etc occupies in the loadout
# ---------------------------------------------------------------------------
SOCKET_TYPES = {
    "3ad1b2b2-acdb-4524-852f-954a76ddae0a": "skin_chroma",
    "77258665-71d1-4623-bc72-44db9bd5b3b3": "skin_level",
    "bcef87d6-209b-46c6-8b19-fbe40bd95abc": "gun_buddy",
    "dd3bf334-87f3-40bd-b043-682a57a8dc3a": "gun_charm",
    "e7c63390-eda7-46e0-bb7a-a6abdacd2433": "skin_base",
}

# Map game mode asset paths to clean names
MODE_NAMES = {
    "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C":           "Standard",
    "/Game/GameModes/QuickBomb/QuickBombGameMode.QuickBombGameMode_C": "Spike Rush",
    "/Game/GameModes/Deathmatch/DeathmatchGameMode.DeathmatchGameMode_C": "Deathmatch",
    "/Game/GameModes/GunGame/GunGameTeamGameMode.GunGameTeamGameMode_C": "Escalation",
    "/Game/GameModes/OneForAll/OneForAll_GameMode.OneForAll_GameMode_C": "Replication",
    "/Game/GameModes/ShootingRange/ShootingRangeGameMode.ShootingRangeGameMode_C": "The Range",
    "/Game/GameModes/HURM/HURM_GameMode.HURM_GameMode_C": "Team Deathmatch",
    "/Game/GameModes/Swiftplay/SwiftplayGameMode.SwiftplayGameMode_C": "Swiftplay",
}


# ---------------------------------------------------------------------------
# Resolved data classes
# ---------------------------------------------------------------------------

@dataclass
class AbilityInfo:
    slot:        str   # "Ability1", "Ability2", "Grenade", "Ultimate"
    name:        str
    description: str
    icon_url:    str = ""


@dataclass
class AgentInfo:
    uuid:         str
    name:         str
    role:         str
    role_icon:    str = ""
    portrait_url: str = ""
    abilities:    list = field(default_factory=list)  # List[AbilityInfo]


@dataclass
class WeaponInfo:
    uuid:         str
    name:         str
    category:     str   # "EEquippableCategory::Heavy", etc — cleaned below
    cost:         int = 0
    fire_rate:    float = 0.0
    magazine:     int = 0
    wall_penetration: str = ""
    damage_ranges: list = field(default_factory=list)


@dataclass
class SkinInfo:
    uuid:        str
    name:        str
    tier:        str = ""   # e.g. "Premium", "Select", "Exclusive"
    icon_url:    str = ""


@dataclass
class Callout:
    region_name:       str        # specific name, e.g. "A Heaven"
    super_region_name: str        # broader zone, e.g. "A Site"
    x:                 float = 0.0
    y:                 float = 0.0


@dataclass
class MapInfo:
    uuid:            str
    name:            str
    coordinates:     str = ""
    splash_url:      str = ""
    minimap_url:     str = ""
    asset_path:      str = ""     # raw path used for matching
    # Minimap projection factors (converts in-game world coords → minimap 0-1 space)
    x_multiplier:    float = 0.0
    y_multiplier:    float = 0.0
    x_scalar:        float = 0.0
    y_scalar:        float = 0.0
    callouts:        list = field(default_factory=list)  # List[Callout]


@dataclass
class ResolvedLoadout:
    puuid:       str
    weapons:     list = field(default_factory=list)   # List[ResolvedWeaponSlot]


@dataclass
class ResolvedWeaponSlot:
    weapon:    Optional[WeaponInfo]
    skin:      Optional[SkinInfo]
    buddy_id:  str = ""   # buddy UUID, resolved separately if needed


@dataclass
class ResolvedPlayer:
    puuid:       str
    team_id:     str
    agent:       Optional[AgentInfo]
    is_coach:    bool = False


@dataclass
class ResolvedGameState:
    phase:       str
    puuid:       str
    map:         Optional[MapInfo]
    mode:        str   # clean name
    players:     list = field(default_factory=list)   # List[ResolvedPlayer]
    loadouts:    list = field(default_factory=list)   # List[ResolvedLoadout]


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

class ValorantResolver:
    """
    Fetches data from valorant-api.com once, caches in memory (and optionally
    on disk), then resolves UUIDs from the local API into rich objects.

    Cache is refreshed automatically if older than `cache_ttl_hours`.
    """

    CACHE_FILE = Path("valorant_api_cache.json")

    def __init__(self, language: str = "en-US", cache_ttl_hours: float = 24.0):
        self.language = language
        self.cache_ttl = cache_ttl_hours * 3600
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "ValorantLocalAPIClient/1.0"

        # In-memory lookup dicts — keyed by UUID (lower-cased)
        self._agents:  dict[str, dict] = {}
        self._weapons: dict[str, dict] = {}
        self._skins:   dict[str, dict] = {}   # skin UUID → skin data
        self._maps:    dict[str, dict] = {}   # asset_path → map data
        self._buddies: dict[str, dict] = {}

        self._load_cache()

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _load_cache(self):
        """Load from disk cache if fresh, otherwise fetch from API."""
        if self.CACHE_FILE.exists():
            try:
                data = json.loads(self.CACHE_FILE.read_text())
                age = time.time() - data.get("_fetched_at", 0)
                if age < self.cache_ttl:
                    self._agents  = data.get("agents", {})
                    self._weapons = data.get("weapons", {})
                    self._skins   = data.get("skins", {})
                    self._maps    = data.get("maps", {})
                    self._buddies = data.get("buddies", {})
                    log.info("Loaded resolver cache (%.0fh old)", age / 3600)
                    return
            except Exception as e:
                log.warning("Cache read failed: %s", e)

        log.info("Fetching fresh data from valorant-api.com...")
        self.refresh()

    def refresh(self):
        """Re-fetch all data from valorant-api.com and rebuild caches."""
        self._fetch_agents()
        self._fetch_weapons()
        self._fetch_maps()
        self._fetch_buddies()
        self._save_cache()
        log.info("Resolver data refreshed.")

    def _save_cache(self):
        try:
            self.CACHE_FILE.write_text(json.dumps({
                "_fetched_at": time.time(),
                "agents":  self._agents,
                "weapons": self._weapons,
                "skins":   self._skins,
                "maps":    self._maps,
                "buddies": self._buddies,
            }, indent=2))
        except Exception as e:
            log.warning("Cache write failed: %s", e)

    def _get(self, path: str, params: dict = None) -> Optional[dict]:
        try:
            r = self._session.get(
                f"{VALORANT_API_BASE}{path}",
                params={"language": self.language, **(params or {})},
                timeout=10
            )
            r.raise_for_status()
            return r.json().get("data")
        except Exception as e:
            log.error("valorant-api.com %s error: %s", path, e)
            return None

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    def _fetch_agents(self):
        data = self._get("/agents", {"isPlayableCharacter": "true"})
        if not data:
            return
        self._agents = {a["uuid"].lower(): a for a in data}
        log.info("Loaded %d agents", len(self._agents))

    def _fetch_weapons(self):
        data = self._get("/weapons")
        if not data:
            return
        for w in data:
            uuid = w["uuid"].lower()
            self._weapons[uuid] = w
            # Also index all skins by their UUID for loadout resolution
            for skin in w.get("skins", []):
                skin_uuid = skin["uuid"].lower()
                self._skins[skin_uuid] = {**skin, "_weapon_uuid": uuid}
                # Index each chroma and level too
                for chroma in skin.get("chromas", []):
                    self._skins[chroma["uuid"].lower()] = {
                        **chroma,
                        "_is_chroma": True,
                        "_skin_name": skin["displayName"],
                        "_weapon_uuid": uuid,
                    }
                for level in skin.get("levels", []):
                    self._skins[level["uuid"].lower()] = {
                        **level,
                        "_is_level": True,
                        "_skin_name": skin["displayName"],
                        "_weapon_uuid": uuid,
                    }
        log.info("Loaded %d weapons, %d skins/chromas/levels",
                 len(self._weapons), len(self._skins))

    def _fetch_maps(self):
        data = self._get("/maps")
        if not data:
            return
        for m in data:
            # Index by asset path (what the local API returns)
            asset = m.get("mapUrl", "").lower()
            self._maps[asset] = m
            # Also index by UUID
            self._maps[m["uuid"].lower()] = m
        log.info("Loaded %d maps", len(data))

    def _fetch_buddies(self):
        data = self._get("/buddies")
        if not data:
            return
        for b in data:
            parent_name = b["displayName"]
            self._buddies[b["uuid"].lower()] = {**b, "_buddy_name": parent_name}
            for level in b.get("levels", []):
                self._buddies[level["uuid"].lower()] = {
                    **level,
                    "_buddy_name": parent_name,
                }
        log.info("Loaded %d buddies", len(self._buddies))

    # ------------------------------------------------------------------
    # Public resolvers
    # ------------------------------------------------------------------

    def resolve_agent(self, uuid: str) -> Optional[AgentInfo]:
        """Resolve an agent character_id UUID to a rich AgentInfo object."""
        if not uuid:
            return None
        raw = self._agents.get(uuid.lower())
        if not raw:
            log.debug("Agent UUID not found: %s", uuid)
            return None

        abilities = []
        for ab in raw.get("abilities", []):
            abilities.append(AbilityInfo(
                slot=ab.get("slot", ""),
                name=ab.get("displayName", ""),
                description=ab.get("description", ""),
                icon_url=ab.get("displayIcon", "") or "",
            ))

        return AgentInfo(
            uuid=uuid,
            name=raw.get("displayName", "Unknown"),
            role=raw.get("role", {}).get("displayName", "Unknown") if raw.get("role") else "Unknown",
            role_icon=raw.get("role", {}).get("displayIcon", "") or "",
            portrait_url=raw.get("fullPortrait", "") or raw.get("displayIcon", "") or "",
            abilities=abilities,
        )

    def resolve_weapon(self, uuid: str) -> Optional[WeaponInfo]:
        """Resolve a weapon type_id UUID to a WeaponInfo object."""
        if not uuid:
            return None
        raw = self._weapons.get(uuid.lower())
        if not raw:
            log.debug("Weapon UUID not found: %s", uuid)
            return None

        stats = raw.get("weaponStats") or {}
        shop  = raw.get("shopData") or {}

        # Clean category string: "EEquippableCategory::Heavy" → "Heavy"
        raw_cat = raw.get("category", "")
        category = raw_cat.split("::")[-1] if "::" in raw_cat else raw_cat

        damage_ranges = []
        for dr in stats.get("damageRanges", []):
            damage_ranges.append({
                "range":  f"{dr.get('rangeStartMeters', 0)}–{dr.get('rangeEndMeters', 0)}m",
                "head":   dr.get("headDamage", 0),
                "body":   dr.get("bodyDamage", 0),
                "leg":    dr.get("legDamage", 0),
            })

        # Clean wall penetration string
        raw_pen = stats.get("wallPenetration", "")
        penetration = raw_pen.split("::")[-1] if "::" in raw_pen else raw_pen

        return WeaponInfo(
            uuid=uuid,
            name=raw.get("displayName", "Unknown"),
            category=category,
            cost=shop.get("cost", 0),
            fire_rate=stats.get("fireRate", 0.0),
            magazine=stats.get("magazineSize", 0),
            wall_penetration=penetration,
            damage_ranges=damage_ranges,
        )

    def resolve_skin(self, item_id: str) -> Optional[SkinInfo]:
        """
        Resolve a skin/chroma/level item UUID to a SkinInfo.
        The loadout returns item IDs inside socket entries — these are
        chroma or level UUIDs, not the skin UUID directly.
        """
        if not item_id:
            return None
        raw = self._skins.get(item_id.lower())
        if not raw:
            return None

        # Get the display name — prefer the parent skin name for chromas/levels
        name = (raw.get("_skin_name")
                or raw.get("displayName", "Default Skin"))

        # Strip " Standard" suffix from default skins for cleanliness
        if name.endswith(" Standard"):
            name = name[: -len(" Standard")]

        return SkinInfo(
            uuid=item_id,
            name=name,
            tier="",   # tier requires a separate contentTiers lookup; omitted for now
            icon_url=raw.get("displayIcon", "") or raw.get("fullRender", "") or "",
        )

    def resolve_map(self, map_path_or_uuid: str) -> Optional[MapInfo]:
        """
        Resolve a map asset path (e.g. '/Game/Maps/Ascent/Ascent')
        or UUID to a MapInfo object.
        """
        if not map_path_or_uuid:
            return None
        raw = self._maps.get(map_path_or_uuid.lower())
        if not raw:
            log.debug("Map not found: %s", map_path_or_uuid)
            return None
        # Sanitize coordinates — the API value contains Unicode degree symbols
        # that can render as garbage in some terminals. Keep it clean.
        raw_coords = raw.get("coordinates", "") or ""
        # The coordinates from the API sometimes have weirdly encoded degree minutes/seconds
        # e.g., 'BF' instead of '15"'. Let's clean up common garbled characters if present
        coords = raw_coords.replace("BF", "15\"").replace("Q", "9\"")

        # Parse callouts
        callouts = []
        for c in raw.get("callouts", []):
            loc = c.get("location", {})
            callouts.append(Callout(
                region_name=c.get("regionName", ""),
                super_region_name=c.get("superRegionName", ""),
                x=float(loc.get("x", 0)),
                y=float(loc.get("y", 0)),
            ))

        return MapInfo(
            uuid=raw.get("uuid", ""),
            name=raw.get("displayName", "Unknown"),
            coordinates=coords,
            splash_url=raw.get("splash", "") or "",
            minimap_url=raw.get("displayIcon", "") or "",
            asset_path=raw.get("mapUrl", ""),
            x_multiplier=float(raw.get("xMultiplier", 0)),
            y_multiplier=float(raw.get("yMultiplier", 0)),
            x_scalar=float(raw.get("xScalarToAdd", 0)),
            y_scalar=float(raw.get("yScalarToAdd", 0)),
            callouts=callouts,
        )

    def resolve_mode(self, mode_path: str) -> str:
        """Resolve a game mode asset path to a clean display name."""
        return MODE_NAMES.get(mode_path, mode_path.split(".")[-1] if mode_path else "Unknown")

    def resolve_buddy(self, buddy_uuid: str) -> str:
        """Return the display name of a gun buddy."""
        if not buddy_uuid:
            return ""
        raw = self._buddies.get(buddy_uuid.lower())
        if not raw:
            return buddy_uuid
        return raw.get("_buddy_name") or raw.get("displayName", buddy_uuid)

    def nearest_callout(self, map_info: "MapInfo", world_x: float, world_y: float,
                        max_distance: float = 3000.0) -> Optional[Callout]:
        """
        Given an in-game world coordinate (x, y), return the nearest named
        callout on the map.

        world_x / world_y are Unreal Engine world-space units as reported by
        the game (same coordinate space used in ShooterGame.log positions).

        max_distance: ignore callouts further than this (in world units).
        Returns None if no callout is within range or map has no callouts.
        """
        if not map_info or not map_info.callouts:
            return None

        best: Optional[Callout] = None
        best_dist = float("inf")

        for c in map_info.callouts:
            dx = c.x - world_x
            dy = c.y - world_y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = c

        if best_dist > max_distance:
            return None
        return best

    def callout_name(self, map_info: "MapInfo", world_x: float, world_y: float,
                     max_distance: float = 3000.0) -> str:
        """
        Convenience wrapper — returns a formatted string like:
        "A Heaven (A Site)" or "B Main" if super_region == region.
        Returns empty string if no callout found.
        """
        c = self.nearest_callout(map_info, world_x, world_y, max_distance)
        if not c:
            return ""
        if c.super_region_name and c.super_region_name != c.region_name:
            return f"{c.region_name} ({c.super_region_name})"
        return c.region_name

    def list_callouts(self, map_info: "MapInfo") -> list:
        """Return all callout names for a map, sorted alphabetically."""
        if not map_info:
            return []
        return sorted(
            f"{c.region_name} — {c.super_region_name}" if c.super_region_name != c.region_name
            else c.region_name
            for c in map_info.callouts
        )

    # ------------------------------------------------------------------
    # Loadout resolver
    # ------------------------------------------------------------------

    def resolve_loadout(self, raw_loadout: dict) -> ResolvedLoadout:
        """
        Takes a raw loadout dict from CurrentGameMatch.loadouts and
        returns a ResolvedLoadout with weapon + skin info per slot.
        """
        slots = []
        for item in raw_loadout.get("gun_ids", []):
            weapon_uuid = item.get("type_id", "")
            weapon_info = self.resolve_weapon(weapon_uuid)

            # Extract skin and buddy from socket data
            sockets = item.get("chroma", {})
            skin_info  = None
            buddy_name = ""

            for socket_type_id, socket_data in sockets.items():
                socket_role = SOCKET_TYPES.get(socket_type_id, "unknown")
                item_id     = socket_data.get("Item", {}).get("ID", "")

                if socket_role == "skin_base" and not skin_info:
                    skin_info = self.resolve_skin(item_id)
                elif socket_role == "skin_chroma" and not skin_info:
                    skin_info = self.resolve_skin(item_id)
                elif socket_role == "gun_buddy":
                    buddy_name = self.resolve_buddy(item_id)

            slots.append(ResolvedWeaponSlot(
                weapon=weapon_info,
                skin=skin_info,
                buddy_id=buddy_name,
            ))

        return ResolvedLoadout(
            puuid=raw_loadout.get("puuid", ""),
            weapons=slots,
        )

    # ------------------------------------------------------------------
    # Full game state resolver
    # ------------------------------------------------------------------

    def resolve_game_state(self, raw_state: dict) -> ResolvedGameState:
        """
        Takes the dict output of ValorantLocalClient.get_full_game_state()
        (already converted with asdict()) and returns a fully resolved state.
        """
        current = raw_state.get("current_game") or {}

        map_info = self.resolve_map(current.get("map_id", ""))
        mode     = self.resolve_mode(current.get("mode", ""))

        # Resolve players
        resolved_players = []
        for p in current.get("all_players", []):
            # Skip completely empty placeholder slots
            if not p.get("Subject") and not p.get("puuid"):
                continue
                
            resolved_players.append(ResolvedPlayer(
                puuid=p.get("puuid") or p.get("Subject", ""),
                team_id=p.get("team_id") or p.get("TeamID", ""),
                agent=self.resolve_agent(p.get("character_id") or p.get("CharacterID", "")),
                is_coach=p.get("is_coach") or p.get("IsCoach", False),
            ))

        # Resolve loadouts
        resolved_loadouts = []
        for lo in current.get("loadouts", []):
            resolved_loadouts.append(self.resolve_loadout(lo))

        # Strip "GamePhase." prefix if phase was serialised as enum repr
        raw_phase = raw_state.get("phase", "UNKNOWN")
        clean_phase = str(raw_phase).replace("GamePhase.", "")

        return ResolvedGameState(
            phase=clean_phase,
            puuid=raw_state.get("puuid", ""),
            map=map_info,
            mode=mode,
            players=resolved_players,
            loadouts=resolved_loadouts,
        )

    # ------------------------------------------------------------------
    # Pretty printer
    # ------------------------------------------------------------------

    def print_game_summary(self, resolved: ResolvedGameState):
        """Print a clean human-readable game summary."""
        print("\n" + "="*60)
        print(f"  VALORANT GAME STATE  |  Phase: {resolved.phase}")
        print("="*60)

        if resolved.map:
            coords = f" ({resolved.map.coordinates})" if resolved.map.coordinates else ""
            print(f"  Map    : {resolved.map.name}{coords}")
            callout_list = self.list_callouts(resolved.map)
            if callout_list:
                col_w = max(len(c) for c in callout_list) + 2
                cols  = 3
                rows  = [callout_list[i:i+cols] for i in range(0, len(callout_list), cols)]
                print(f"  Callouts ({len(callout_list)}):")
                for row in rows:
                    print("    " + "".join(c.ljust(col_w) for c in row))
        print(f"  Mode   : {resolved.mode}")
        print(f"  PUUID  : {resolved.puuid}")

        print("\n--- PLAYERS ---")
        # Build loadout index for quick lookup
        loadout_by_puuid = {lo.puuid: lo for lo in resolved.loadouts}

        for p in resolved.players:
            agent_name = p.agent.name if p.agent else "Unknown"
            role       = p.agent.role if p.agent else ""
            me         = " ← YOU" if p.puuid == resolved.puuid else ""
            print(f"\n  [{p.team_id}] {agent_name} ({role}){me}")

            if p.agent and p.agent.abilities:
                ab_names = [f"{a.slot}: {a.name}" for a in p.agent.abilities]
                print(f"    Abilities : {', '.join(ab_names)}")

            lo = loadout_by_puuid.get(p.puuid)
            if lo:
                print(f"    Loadout ({len(lo.weapons)} weapon slots):")
                for slot in lo.weapons:
                    if not slot.weapon:
                        continue
                    w = slot.weapon
                    skin_name = slot.skin.name if slot.skin else "Default"
                    # Only show buddy if it resolved to a real name (not a raw UUID fallback)
                    buddy_val = slot.buddy_id or ""
                    is_uuid   = len(buddy_val) == 36 and buddy_val.count("-") == 4
                    buddy     = f" | Buddy: {buddy_val}" if buddy_val and not is_uuid else ""
                    print(f"      • {w.name:<20} ${w.cost:<5} "
                          f"[{w.category}]  Skin: {skin_name}{buddy}")
                    if w.damage_ranges:
                        dr = w.damage_ranges[0]
                        print(f"        Damage ({dr['range']}): "
                              f"Head {dr['head']} / Body {dr['body']} / Leg {dr['leg']}")

        print("\n" + "="*60 + "\n")


# ---------------------------------------------------------------------------
# Integration helper — use with valorant_local_api.py
# ---------------------------------------------------------------------------

def get_resolved_state():
    """
    Convenience function: pull raw state from local API,
    resolve it, and return a ResolvedGameState.
    """
    from dataclasses import asdict
    from valorant_local_api import ValorantLocalClient

    client   = ValorantLocalClient()
    resolver = ValorantResolver()

    raw   = client.get_full_game_state()
    state = resolver.resolve_game_state(asdict(raw))
    return state, resolver


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # If a JSON file path is passed, resolve from that (for testing without
    # Valorant running — e.g. python valorant_resolver.py output.json)
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.exists():
            raw_state = json.loads(path.read_text())
            resolver  = ValorantResolver()
            resolved  = resolver.resolve_game_state(raw_state)
            resolver.print_game_summary(resolved)
            sys.exit(0)

    # Otherwise try to connect live
    try:
        # Delete stale cache to force a fresh buddy index if needed
        # (safe to remove this line after first successful run)
        if Path("valorant_api_cache.json").exists():
            age = time.time() - json.loads(Path("valorant_api_cache.json").read_text()).get("_fetched_at", 0)
            if age > 60:  # re-fetch if cache older than 60s on first run after fix
                Path("valorant_api_cache.json").unlink()
                log.info("Cleared stale cache — will re-fetch.")

        state, resolver = get_resolved_state()
        resolver.print_game_summary(state)
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ImportError:
        print("valorant_local_api.py not found. Pass a JSON file as argument to test offline.")