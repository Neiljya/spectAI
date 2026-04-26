# coach.py
# ============================================================
# THE ONLY FILE YOU TOUCH when integrating your LLM.
#
# Two surfaces exposed:
#   push(text, kind)              — show a speech bubble
#   show_play(map_name, play_name) — show a minimap play diagram
#
# Swap the demo loop at the bottom for your actual pipeline.
# ============================================================

import time
import threading
from overlay  import Overlay
from minimap  import MinimapOverlay
from plays    import list_plays

_overlay:  Overlay | None        = None
_minimap:  MinimapOverlay | None = None


def init(overlay: Overlay, minimap: MinimapOverlay):
    global _overlay, _minimap
    _overlay = overlay
    _minimap = minimap


# ── Speech bubble ─────────────────────────────────────────

def push(text: str, kind: str = "coach"):
    """
    Show a coach speech bubble.
    kind: "coach" | "warning" | "positive" | "info"

    Example:
        push("Rotate B now.", "coach")
        push("Low HP — disengage!", "warning")
        push("Clean clutch.", "positive")
    """
    assert _overlay, "call init() first"
    _overlay.push(text, kind)


# ── Minimap play ──────────────────────────────────────────

def show_play(map_name: str, play_name: str):
    """
    Show a play diagram on the minimap overlay.
    map_name:  "Split" | "Pearl" | "Ascent" | "Bind" | "Haven"
    play_name: "B Split" | "Mid Push" | "B Default" | etc.

    All available plays:
        from plays import list_plays
        print(list_plays())

    Example:
        show_play("Split", "B Split")
        show_play("Pearl", "Mid Push")
    """
    assert _minimap, "call init() first"
    _minimap.show_play(map_name, play_name)


def hide_map():
    """Dismiss the minimap overlay."""
    assert _minimap, "call init() first"
    _minimap.hide_map()


# ── DEMO LOOP — delete when going live ────────────────────

def run_demo():
    time.sleep(1.5)
    push("Setting up attack round — let's run B Split.", "coach")

    time.sleep(2.5)
    show_play("Split", "B Split")   # minimap pops up

    time.sleep(4)
    push("Smoke back CT, ropes and main hit simultaneously.", "coach")

    time.sleep(4)
    push("Low HP — save the rifle!", "warning")

    time.sleep(3)
    hide_map()

    time.sleep(1.5)
    push("Nice clutch. Let's look at mid for next round.", "positive")

    time.sleep(2)
    show_play("Split", "Mid Control")

    time.sleep(5)
    push("Control mail then decide A or B.", "info")

    time.sleep(4)
    hide_map()


def start_demo():
    t = threading.Thread(target=run_demo, daemon=True)
    t.start()