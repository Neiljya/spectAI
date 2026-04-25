# coach.py
# ============================================================
# THIS IS THE ONLY FILE YOU TOUCH WHEN INTEGRATING YOUR LLM.
#
# Right now it runs a demo loop with dummy text.
# When your vision model + Gemini pipeline is ready:
#   1. Delete or disable the demo loop at the bottom.
#   2. Call push(text, kind) from your model output handler.
#   3. That's it. The overlay handles the rest.
# ============================================================

import time
import threading
from overlay import Overlay

# The overlay instance. coach.py holds a reference so it can push to it.
_overlay: Overlay | None = None


def init(overlay: Overlay):
    """Called once from main.py. Registers the overlay instance."""
    global _overlay
    _overlay = overlay


def push(text: str, kind: str = "coach"):
    """
    ── CALL THIS WITH YOUR LLM OUTPUT ──
    text: the coach message to display
    kind: "coach" | "warning" | "positive" | "info"

    Thread-safe — call from any thread, async callback, wherever.

    Example when Gemini responds:
        response = model.generate_content(prompt)
        push(response.text.strip(), "coach")

    Example for a danger signal from vision model:
        push("Low HP — fall back.", "warning")
    """
    if _overlay is None:
        raise RuntimeError("coach.init() must be called before push()")
    _overlay.push(text, kind)


# ── DEMO LOOP — replace this with your LLM integration ────
# Fires a sequence of fake messages to show the overlay works.
# Delete this function when going live.

def run_demo():
    time.sleep(1.5)
    push("Rotate B — 3 enemies pushing mid.", "coach")
    time.sleep(3)
    push("Low HP — don't peek long!", "warning")
    time.sleep(3)
    push("Clean trade. Nice positioning.", "positive")
    time.sleep(4)
    push("Spike planted A. Hold post-plant angles.", "info")
    time.sleep(4)
    push("One left — he's playing corner on site.", "coach")


def start_demo():
    """Starts the demo loop in a background thread."""
    t = threading.Thread(target=run_demo, daemon=True)
    t.start()