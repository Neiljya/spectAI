# plays.py
# ============================================================
# PLAY LIBRARY
# AI calls minimap.show_play(map_name, play_name) to pull one up.
# Add new plays here — nothing else needs to change.
#
# Coordinates are normalized 0.0–1.0 (fraction of map image size).
# x=0 is left edge, y=0 is top edge.
#
# Each agent entry:
#   agent:    agent name (must match a key in AGENT_COLORS)
#   role:     display hint ("Entry", "Support", "Flash", etc.)
#   pos:      [x, y] normalized position on map image
#   note:     short callout shown on hover / in box
#   path:     optional list of [x,y] waypoints showing movement route
# ============================================================

AGENT_COLORS = {
    # Duelists
    "Jett":    "#A8D8EA",
    "Reyna":   "#9B59B6",
    "Raze":    "#E67E22",
    "Neon":    "#3498DB",
    "Yoru":    "#2C3E50",
    "Phoenix": "#F39C12",
    "Iso":     "#8E44AD",
    # Controllers
    "Omen":    "#5D6D7E",
    "Brimstone":"#E74C3C",
    "Viper":   "#27AE60",
    "Astra":   "#8E44AD",
    "Harbor":  "#1ABC9C",
    "Clove":   "#9B59B6",
    # Initiators
    "Sova":    "#2980B9",
    "Breach":  "#D35400",
    "Skye":    "#2ECC71",
    "Fade":    "#1C2833",
    "KAY/O":   "#AAB7B8",
    "Gekko":   "#F1C40F",
    # Sentinels
    "Sage":    "#76D7C4",
    "Killjoy": "#F4D03F",
    "Cypher":  "#95A5A6",
    "Chamber": "#B7950B",
    "Deadlock":"#717D7E",
}

# ── PLAYS ──────────────────────────────────────────────────
# Map image paths — drop PNGs into assets/maps/
MAP_IMAGES = {
    "Ascent":   "assets/maps/ascent.png",
    "Bind":     "assets/maps/bind.png",
    "Haven":    "assets/maps/haven.png",
    "Split":    "assets/maps/split.svg",
    "Fracture": "assets/maps/fracture.png",
    "Icebox":   "assets/maps/icebox.png",
    "Breeze":   "assets/maps/breeze.png",
    "Pearl":    "assets/maps/pearl.png",
    "Lotus":    "assets/maps/lotus.png",
    "Sunset":   "assets/maps/sunset.png",
}

PLAYS: dict[str, dict[str, dict]] = {

# ── SPLIT ──────────────────────────────────────────────
    "Split": {
        "B Split": {
            "description": "Full B site split — ropes + main simultaneous push",
            "agents": [
                {
                    "agent": "Jett",
                    "role":  "Entry",
                    "pos":   [0.18, 0.30],
                    "note":  "Dash onto site through main",
                    "path":  [[0.20, 0.72], [0.10, 0.56], [0.18, 0.30]], # B Lobby -> B Main -> B Site
                },
                {
                    "agent": "Raze",
                    "role":  "Entry",
                    "pos":   [0.30, 0.38],
                    "note":  "Ropes push — satchel into Heaven",
                    "path":  [[0.45, 0.67], [0.38, 0.48], [0.30, 0.38]], # Bottom Mid -> Mid Mail -> B Heaven
                },
                {
                    "agent": "Omen",
                    "role":  "Smoke",
                    "pos":   [0.25, 0.85],
                    "note":  "Smoke back CT and heaven",
                    "path":  None,
                },
                {
                    "agent": "Skye",
                    "role":  "Flash",
                    "pos":   [0.30, 0.67],
                    "note":  "Flash for ropes entry from B Link",
                    "path":  None,
                },
                {
                    "agent": "Killjoy",
                    "role":  "Post-plant",
                    "pos":   [0.18, 0.35],
                    "note":  "Turret on default plant",
                    "path":  [[0.20, 0.72], [0.18, 0.35]], # B Lobby -> B Site default
                },
            ],
        },
        "A Default": {
            "description": "A site default setup — spread control",
            "agents": [
                {
                    "agent": "Jett",
                    "role":  "Entry",
                    "pos":   [0.95, 0.25],
                    "note":  "Dash into A Site",
                    "path":  [[0.88, 0.70], [0.80, 0.53], [0.95, 0.25]], # A Lobby -> A Main -> A Site
                },
                {
                    "agent": "Breach",
                    "role":  "Flash",
                    "pos":   [0.85, 0.65],
                    "note":  "Fault Line into heaven from Lobby",
                    "path":  None,
                },
                {
                    "agent": "Viper",
                    "role":  "Smoke",
                    "pos":   [0.70, 0.70],
                    "note":  "Wall across A Ramp + Screens",
                    "path":  None,
                },
                {
                    "agent": "Sage",
                    "role":  "Support",
                    "pos":   [0.80, 0.53],
                    "note":  "Wall boost or block A Main choke",
                    "path":  [[0.88, 0.70], [0.80, 0.53]],
                },
                {
                    "agent": "Sova",
                    "role":  "Info",
                    "pos":   [0.75, 0.75],
                    "note":  "Recon dart back site from Sewer/Lobby",
                    "path":  None,
                },
            ],
        },
        "Mid Control": {
            "description": "Mid takeover then decide — mail + vent control",
            "agents": [
                {
                    "agent": "Neon",
                    "role":  "Entry",
                    "pos":   [0.55, 0.42],
                    "note":  "Sprint through mid to Vent",
                    "path":  [[0.45, 0.90], [0.45, 0.67], [0.46, 0.48], [0.55, 0.42]], # Attack -> Bot Mid -> Top Mid -> Vent
                },
                {
                    "agent": "Omen",
                    "role":  "Smoke",
                    "pos":   [0.40, 0.85],
                    "note":  "Smoke top mid + mail",
                    "path":  None,
                },
                {
                    "agent": "KAY/O",
                    "role":  "Suppress",
                    "pos":   [0.45, 0.67],
                    "note":  "Knife mid then push",
                    "path":  [[0.45, 0.80], [0.45, 0.67]],
                },
                {
                    "agent": "Chamber",
                    "role":  "Anchor",
                    "pos":   [0.30, 0.68],
                    "note":  "Hold B Link / flank watch",
                    "path":  None,
                },
                {
                    "agent": "Fade",
                    "role":  "Info",
                    "pos":   [0.50, 0.75],
                    "note":  "Haunt into mid before push",
                    "path":  None,
                },
            ],
        },
    },
    # ── PEARL ──────────────────────────────────────────────
    "Pearl": {
        "Mid Push": {
            "description": "Mid control — art + link simultaneous pressure",
            "agents": [
                {
                    "agent": "Jett",
                    "role":  "Entry",
                    "pos":   [0.50, 0.48],
                    "note":  "Dash into art",
                    "path":  [[0.42, 0.65], [0.50, 0.55], [0.50, 0.48]],
                },
                {
                    "agent": "Viper",
                    "role":  "Smoke",
                    "pos":   [0.40, 0.70],
                    "note":  "Wall cuts mid connector",
                    "path":  None,
                },
                {
                    "agent": "Fade",
                    "role":  "Info",
                    "pos":   [0.48, 0.60],
                    "note":  "Haunt mid before commit",
                    "path":  None,
                },
                {
                    "agent": "Breach",
                    "role":  "Flash",
                    "pos":   [0.36, 0.68],
                    "note":  "Flash link for teammate",
                    "path":  None,
                },
                {
                    "agent": "Killjoy",
                    "role":  "Post-plant",
                    "pos":   [0.62, 0.42],
                    "note":  "Turret B default",
                    "path":  [[0.55, 0.65], [0.62, 0.42]],
                },
            ],
        },
        "B Default": {
            "description": "B site default — link control into site",
            "agents": [
                {
                    "agent": "Raze",
                    "role":  "Entry",
                    "pos":   [0.72, 0.58],
                    "note":  "Satchel through B main",
                    "path":  [[0.72, 0.82], [0.72, 0.70], [0.72, 0.58]],
                },
                {
                    "agent": "Astra",
                    "role":  "Smoke",
                    "pos":   [0.30, 0.80],
                    "note":  "Stars on CT + B heaven",
                    "path":  None,
                },
                {
                    "agent": "Skye",
                    "role":  "Flash",
                    "pos":   [0.68, 0.70],
                    "note":  "Guided wolf into site",
                    "path":  None,
                },
                {
                    "agent": "Sova",
                    "role":  "Info",
                    "pos":   [0.60, 0.75],
                    "note":  "Dart through B tunnel",
                    "path":  None,
                },
                {
                    "agent": "Sage",
                    "role":  "Support",
                    "pos":   [0.65, 0.65],
                    "note":  "Slow orb B main choke",
                    "path":  [[0.60, 0.82], [0.65, 0.65]],
                },
            ],
        },
        "A Fake → B": {
            "description": "A side noise into fast B rotate",
            "agents": [
                {
                    "agent": "Omen",
                    "role":  "Fake",
                    "pos":   [0.28, 0.38],
                    "note":  "Paranoia + smokes A — fake",
                    "path":  [[0.20, 0.55], [0.28, 0.38]],
                },
                {
                    "agent": "Neon",
                    "role":  "Rotate",
                    "pos":   [0.70, 0.55],
                    "note":  "Sprint B after fake noise",
                    "path":  [[0.40, 0.65], [0.58, 0.62], [0.70, 0.55]],
                },
                {
                    "agent": "Jett",
                    "role":  "Entry",
                    "pos":   [0.72, 0.52],
                    "note":  "Dash in after Neon clears",
                    "path":  [[0.65, 0.70], [0.72, 0.52]],
                },
                {
                    "agent": "Fade",
                    "role":  "Info",
                    "pos":   [0.50, 0.60],
                    "note":  "Haunt mid — info before rotate",
                    "path":  None,
                },
                {
                    "agent": "Killjoy",
                    "role":  "Post-plant",
                    "pos":   [0.75, 0.48],
                    "note":  "Turret B default on site",
                    "path":  None,
                },
            ],
        },
    },

    # ── ASCENT ─────────────────────────────────────────────
    "Ascent": {
        "B Default": {
            "description": "B site default setup — market control",
            "agents": [
                {
                    "agent": "Jett",
                    "role":  "Entry",
                    "pos":   [0.62, 0.42],
                    "note":  "Dash B main",
                    "path":  [[0.62, 0.72], [0.62, 0.55], [0.62, 0.42]],
                },
                {
                    "agent": "Omen",
                    "role":  "Smoke",
                    "pos":   [0.45, 0.72],
                    "note":  "Smoke market + CT",
                    "path":  None,
                },
                {
                    "agent": "Skye",
                    "role":  "Flash",
                    "pos":   [0.58, 0.58],
                    "note":  "Guided wolf pre-entry",
                    "path":  None,
                },
                {
                    "agent": "Sova",
                    "role":  "Info",
                    "pos":   [0.50, 0.68],
                    "note":  "Dart through B tunnel",
                    "path":  None,
                },
                {
                    "agent": "Killjoy",
                    "role":  "Post-plant",
                    "pos":   [0.65, 0.38],
                    "note":  "Turret default — deny retake",
                    "path":  None,
                },
            ],
        },
        "Mid Control": {
            "description": "Market + catwalk control — then pick a site",
            "agents": [
                {
                    "agent": "Reyna",
                    "role":  "Lurk",
                    "pos":   [0.50, 0.50],
                    "note":  "Market lurk for pick",
                    "path":  [[0.48, 0.72], [0.50, 0.60], [0.50, 0.50]],
                },
                {
                    "agent": "Astra",
                    "role":  "Smoke",
                    "pos":   [0.30, 0.78],
                    "note":  "Stars catwalk + mid",
                    "path":  None,
                },
                {
                    "agent": "KAY/O",
                    "role":  "Suppress",
                    "pos":   [0.44, 0.62],
                    "note":  "Knife market before push",
                    "path":  [[0.40, 0.80], [0.44, 0.62]],
                },
                {
                    "agent": "Chamber",
                    "role":  "Anchor",
                    "pos":   [0.65, 0.70],
                    "note":  "TP B main — hold push",
                    "path":  None,
                },
                {
                    "agent": "Fade",
                    "role":  "Info",
                    "pos":   [0.46, 0.68],
                    "note":  "Haunt market + catwalk",
                    "path":  None,
                },
            ],
        },
    },

    # ── HAVEN ──────────────────────────────────────────────
    "Haven": {
        "C Long Control": {
            "description": "C long pressure to open up mid and B",
            "agents": [
                {
                    "agent": "Jett",
                    "role":  "Entry",
                    "pos":   [0.78, 0.55],
                    "note":  "Dash C long",
                    "path":  [[0.78, 0.82], [0.78, 0.68], [0.78, 0.55]],
                },
                {
                    "agent": "Brimstone",
                    "role":  "Smoke",
                    "pos":   [0.40, 0.80],
                    "note":  "Smoke C garage + CT",
                    "path":  None,
                },
                {
                    "agent": "Breach",
                    "role":  "Flash",
                    "pos":   [0.72, 0.72],
                    "note":  "Fault Line + flash C long",
                    "path":  None,
                },
                {
                    "agent": "Sova",
                    "role":  "Info",
                    "pos":   [0.55, 0.75],
                    "note":  "Dart C site pre-round",
                    "path":  None,
                },
                {
                    "agent": "Sage",
                    "role":  "Support",
                    "pos":   [0.68, 0.78],
                    "note":  "Slow C long choke",
                    "path":  None,
                },
            ],
        },
        "3 Mid": {
            "description": "Triple mid execute — garage + window + mid",
            "agents": [
                {
                    "agent": "Neon",
                    "role":  "Entry",
                    "pos":   [0.50, 0.48],
                    "note":  "Sprint B mid window",
                    "path":  [[0.45, 0.75], [0.50, 0.60], [0.50, 0.48]],
                },
                {
                    "agent": "Phoenix",
                    "role":  "Entry",
                    "pos":   [0.42, 0.52],
                    "note":  "Flash + push garage",
                    "path":  [[0.38, 0.72], [0.42, 0.60], [0.42, 0.52]],
                },
                {
                    "agent": "Omen",
                    "role":  "Smoke",
                    "pos":   [0.30, 0.80],
                    "note":  "Smoke CT + A link",
                    "path":  None,
                },
                {
                    "agent": "KAY/O",
                    "role":  "Suppress",
                    "pos":   [0.46, 0.68],
                    "note":  "Knife B before push",
                    "path":  None,
                },
                {
                    "agent": "Killjoy",
                    "role":  "Post-plant",
                    "pos":   [0.55, 0.42],
                    "note":  "Turret B default",
                    "path":  None,
                },
            ],
        },
    },

    # ── BIND ───────────────────────────────────────────────
    "Bind": {
        "B Teleporter Rush": {
            "description": "TP flank + main push simultaneous",
            "agents": [
                {
                    "agent": "Raze",
                    "role":  "TP Entry",
                    "pos":   [0.62, 0.38],
                    "note":  "TP flank through B teleport",
                    "path":  [[0.28, 0.62], [0.62, 0.38]],
                },
                {
                    "agent": "Jett",
                    "role":  "Entry",
                    "pos":   [0.70, 0.55],
                    "note":  "Dash B main simultaneous",
                    "path":  [[0.70, 0.82], [0.70, 0.68], [0.70, 0.55]],
                },
                {
                    "agent": "Viper",
                    "role":  "Smoke",
                    "pos":   [0.38, 0.78],
                    "note":  "Wall B main + CT",
                    "path":  None,
                },
                {
                    "agent": "Skye",
                    "role":  "Flash",
                    "pos":   [0.65, 0.68],
                    "note":  "Flash B for both pushes",
                    "path":  None,
                },
                {
                    "agent": "Cypher",
                    "role":  "Post-plant",
                    "pos":   [0.68, 0.45],
                    "note":  "Trip wire default plant",
                    "path":  None,
                },
            ],
        },
        "A Hookah": {
            "description": "A site hookah push with support",
            "agents": [
                {
                    "agent": "Reyna",
                    "role":  "Entry",
                    "pos":   [0.32, 0.35],
                    "note":  "Dismiss through hookah",
                    "path":  [[0.25, 0.58], [0.28, 0.45], [0.32, 0.35]],
                },
                {
                    "agent": "Brimstone",
                    "role":  "Smoke",
                    "pos":   [0.20, 0.72],
                    "note":  "Smoke CT + A short",
                    "path":  None,
                },
                {
                    "agent": "Breach",
                    "role":  "Flash",
                    "pos":   [0.22, 0.60],
                    "note":  "Flash hookah pre-entry",
                    "path":  None,
                },
                {
                    "agent": "Sova",
                    "role":  "Info",
                    "pos":   [0.18, 0.65],
                    "note":  "Dart A site",
                    "path":  None,
                },
                {
                    "agent": "Killjoy",
                    "role":  "Post-plant",
                    "pos":   [0.35, 0.30],
                    "note":  "Turret A default",
                    "path":  None,
                },
            ],
        },
    },
}

# ── AI helper ─────────────────────────────────────────────

def list_plays() -> list[tuple[str, str]]:
    """Returns all available (map, play) pairs. AI can reference this."""
    out = []
    for map_name, plays in PLAYS.items():
        for play_name in plays:
            out.append((map_name, play_name))
    return out

def get_play(map_name: str, play_name: str) -> dict | None:
    """Lookup a play. Returns None if not found."""
    return PLAYS.get(map_name, {}).get(play_name)