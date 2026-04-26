# coach.py
# ============================================================
# Integration point for your LLM pipeline.
# No demo loop. Keybinds handled in main.py.
#
# Call from anywhere:
#   push(text, kind)               — speech bubble
#   show_play(map_name, play_name) — minimap diagram
#   hide_map()                     — dismiss minimap
# ============================================================

from overlay import Overlay
from minimap import MinimapOverlay

_overlay: Overlay | None       = None
_minimap: MinimapOverlay | None = None


def init(overlay: Overlay, minimap: MinimapOverlay):
    global _overlay, _minimap
    _overlay = overlay
    _minimap = minimap


def push(text: str, kind: str = "coach"):
    """
    Show a speech bubble.
    kind: "coach" | "warning" | "positive" | "info"
    """
    assert _overlay, "call init() first"
    _overlay.push(text, kind)


def show_play(map_name: str, play_name: str):
    """
    Show a play diagram on the minimap.
    e.g. show_play("Split", "B Split")
         show_play("Pearl", "Mid Push")
    """
    assert _minimap, "call init() first"
    _minimap.show_play(map_name, play_name)


def hide_map():
    """Dismiss the minimap panel."""
    assert _minimap, "call init() first"
    _minimap.hide_map()