# main.py
# ============================================================
# HOTKEYS
#   ALT + M  — cycle through demo plays (remove when using LLM)
#   ALT + H  — hide / show minimap
#   ALT + X  — toggle speech bubble overlay
# ============================================================

import sys
import os
import threading
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from pynput import keyboard

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Vision-Model'))
from live_llm_s import SpectAI

from overlay import Overlay
from minimap import MinimapOverlay
from plays   import list_plays, get_plays_summary
import coach

# ── Custom Voice Overlay ──────────────────────────────────
class VoiceOverlay(QWidget):
    """A dedicated, thread-safe overlay just for Direct Voice Responses."""
    response_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Set up a transparent, click-through window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Styled to match a standard, clean dialog box
        self.label = QLabel("", self)
        self.label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: rgba(20, 20, 20, 220);
                padding: 15px 25px;
                border-radius: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 18px;
                border: 1px solid rgba(255, 255, 255, 40);
            }
        """)
        self.label.setWordWrap(True)
        self.label.setMinimumWidth(500)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        self.hide()
        
        # Timer to auto-hide the voice response after 8 seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)
        
        # Connect cross-thread signal
        self.response_received.connect(self.show_response)

    def show_response(self, text):
        self.label.setText(text)  # Removed the "Response:" prefix for a cleaner look
        self.adjustSize()
        
        # Position near the bottom-center of the screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - 120  # 120px from bottom edge
        self.move(x, y)
        
        self.show()
        self.timer.start(8000)

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
    global _overlay, _voice_overlay

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # UI Components
    _overlay = Overlay()
    _voice_overlay = VoiceOverlay()
    minimap  = MinimapOverlay()
    coach.init(_overlay, minimap)

    # Initialize SpectAI with callbacks for both coach nudges and voice queries
    spect_ai = SpectAI(
        response_callback=lambda text: coach.push(text, "coach"),
        voice_callback=lambda text: _voice_overlay.response_received.emit(text),
        play_callback=lambda m, p: coach.show_play(m, p),
        plays_summary=get_plays_summary(),
    )
    spect_ai.start()

    # Global hotkey listener
    listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    listener.daemon = True
    listener.start()

    coach.push("SpectAI ready.  ALT+M → show play  |  ALT+H → hide", "info")

    exit_code = app.exec()
    spect_ai.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()