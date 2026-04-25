# main.py
# ============================================================
# HOTKEYS
#   ALT + M  — cycle through demo plays (remove when using LLM)
#   ALT + H  — hide / show minimap
#   ALT + X  — toggle speech bubble overlay
# ============================================================

import sys
import threading
from PyQt6.QtWidgets import QApplication
from pynput import keyboard

from overlay import Overlay
from minimap import MinimapOverlay
from plays   import list_plays
import coach

# ── Demo play cycle (remove when LLM is live) ─────────────
_all_plays  = list_plays()   # [(map, play), ...]
_play_index = 0

def _cycle_play():
    global _play_index
    map_name, play_name = _all_plays[_play_index % len(_all_plays)]
    coach.show_play(map_name, play_name)
    coach.push(f"{map_name} — {play_name}", "coach")
    _play_index += 1

# ── Hotkey state ───────────────────────────────────────────
_held = set()

def _on_press(key):
    _held.add(key)

    alt = keyboard.Key.alt_l in _held or keyboard.Key.alt_r in _held

    if alt:
        try:
            ch = key.char.lower()
        except AttributeError:
            return

        if ch == 'm':   # ALT+M — show next play
            _cycle_play()
        elif ch == 'h': # ALT+H — hide minimap
            coach.hide_map()
        elif ch == 'x': # ALT+X — toggle overlay visibility
            _overlay.toggle()

def _on_release(key):
    _held.discard(key)


def main():
    global _overlay

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    _overlay = Overlay()
    minimap  = MinimapOverlay()
    coach.init(_overlay, minimap)

    # Global hotkey listener
    listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    listener.daemon = True
    listener.start()

    coach.push("SpectAI ready.  ALT+M → show play  |  ALT+H → hide", "info")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()