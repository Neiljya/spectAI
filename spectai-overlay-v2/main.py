# main.py
# ============================================================
# HOTKEYS
#   F8       — start / stop session (SpectAI + recording)
#   F9       — push-to-talk voice query (hold)
#   F10      — toggle AI voice mute
#   F12      — kill / close the app
#   ALT + M  — cycle through demo plays
#   ALT + H  — hide / show minimap
#   ALT + X  — toggle speech bubble overlay
# ============================================================

import sys
import os
import threading
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QMetaObject, pyqtSignal
from pynput import keyboard

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Vision-Model'))
from live_llm_s import SpectAI, set_muted

from overlay import Overlay
from minimap import MinimapOverlay
from plays   import list_plays, get_plays_summary
from session  import GameSession
from recorder import ScreenRecorder
from lineups import LineupOverlay
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

# ── Session / SpectAI toggle ───────────────────────────────
_session_active  = False
_current_session: GameSession    | None = None
_spect_ai:        SpectAI        | None = None
_recorder:        ScreenRecorder | None = None
_lineups_overlay: LineupOverlay  | None = None
_is_muted = False

def _on_coach_response(text: str):
    coach.push(text, "coach")
    if _current_session:
        _current_session.add_event(text, source="coach")

def _on_voice_response(text: str):
    _voice_overlay.response_received.emit(text)
    if _current_session:
        _current_session.add_event(text, source="voice")


def _on_lineup_request(map_name: str, position: str):
    agent = "Sova"

    if _lineups_overlay:
        _lineups_overlay.show(map_name, agent, position)

    msg = f"Showing {agent} lineups for {position} on {map_name}."
    coach.push(msg, "coach")
    if _current_session:
        _current_session.add_event(msg, source="lineup")

def _toggle_session():
    global _session_active, _current_session
    if not _session_active:
        _session_active = True
        session = GameSession()
        _current_session = session

        video_path = os.path.join("sessions", session.match_id, "match_recording.mp4")
        started = _recorder.start(video_path)
        if started:
            session.video_path = video_path

        _spect_ai.start()
        coach.push("Session started — SpectAI active.  F8 to stop  |  F10 mute.", "info")
    else:
        _session_active = False
        session = _current_session
        _current_session = None
        coach.push("Stopping session…", "info")
        def _stop():
            _recorder.stop()
            _spect_ai.stop()
            if session:
                path = session.save()
                coach.push(f"Session saved → {path}", "positive")
        threading.Thread(target=_stop, daemon=True).start()

def _toggle_mute():
    global _is_muted
    _is_muted = not _is_muted
    set_muted(_is_muted)
    label = "MUTED" if _is_muted else "unmuted"
    coach.push(f"AI voice {label}.  F10 to toggle.", "info")

# ── Hotkey state ───────────────────────────────────────────
_held = set()

def _on_press(key):
    _held.add(key)

    if key == keyboard.Key.f8:
        _toggle_session()
        return

    if key == keyboard.Key.f10:
        _toggle_mute()
        return

    if key == keyboard.Key.f12:
        QMetaObject.invokeMethod(
            QApplication.instance(), "quit",
            Qt.ConnectionType.QueuedConnection,
        )
        return

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
    global _overlay, _voice_overlay, _spect_ai, _recorder, _lineups_overlay

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # UI Components
    _overlay = Overlay()
    _voice_overlay = VoiceOverlay()
    _lineups_overlay = LineupOverlay()
    minimap  = MinimapOverlay()
    coach.init(_overlay, minimap)

    _recorder = ScreenRecorder()

    # Build SpectAI — not started until F8
    _spect_ai = SpectAI(
        response_callback=_on_coach_response,
        voice_callback=_on_voice_response,
        play_callback=lambda m, p: coach.show_play(m, p),
        lineup_callback=_on_lineup_request,
        frame_callback=_recorder.write_frame,
        plays_summary=get_plays_summary(),
    )

    # Global hotkey listener
    listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    listener.daemon = True
    listener.start()

    coach.push("SpectAI ready.  F8 → start session  |  ALT+M → play  |  ALT+H → hide", "info")

    exit_code = app.exec()
    _spect_ai.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()