# main.py
# Run: python main.py
# Valorant must be in Borderless Windowed mode (Settings → Video → Display Mode).

import sys
from PyQt6.QtWidgets import QApplication
from overlay import Overlay
import coach


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = Overlay()
    coach.init(overlay)

    # ── Swap this line when going live ────────────────────
    # Currently runs the demo loop.
    # Replace with your LLM pipeline startup instead.
    coach.start_demo()
    # ─────────────────────────────────────────────────────

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
