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
import time
import getpass
from PyQt6.QtWidgets import QApplication
from pynput import keyboard

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Vision-Model'))
from live_llm_s import SpectAI
from supabase_auth import sign_in_with_email_password
from match_uploader import UploadConfig, upload_latest_match

from overlay import Overlay
from minimap import MinimapOverlay
from plays   import list_plays
import coach

# ── Demo play cycle (remove when LLM is live) ─────────────
_all_plays  = list_plays()   # [(map, play), ...]
_play_index = 0
_app = None

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
        elif ch == 'e': # ALT+E — end session
            if _app is not None:
                _app.quit()

def _on_release(key):
    _held.discard(key)


def _prompt_text(prompt: str, default: str = "") -> str:
    val = input(prompt).strip()
    return val or default


def _authenticate_user() -> str | None:
    email = os.getenv("SPECTAI_EMAIL", "").strip() or input("Supabase email: ").strip()
    if not email:
        return None

    password = os.getenv("SPECTAI_PASSWORD", "").strip()
    if not password:
        password = getpass.getpass("Supabase password: ")

    ctx = sign_in_with_email_password(email, password)
    print(f"[Auth] Signed in: {ctx.email} (profile_id={ctx.profile_id})")
    return ctx.profile_id


def _run_end_session_upload(profile_id: str, region: str, name: str, tag: str, mode: str):
    try:
        print("[End Session] Uploading latest match to Supabase...")
        result = upload_latest_match(
            UploadConfig(
                profile_id=profile_id,
                region=region,
                name=name,
                tag=tag,
                mode=mode,
                size=10,
            )
        )
        print(
            "[End Session] Upload complete:",
            f"match_id={result.get('match_id')}",
            f"map={result.get('map')}",
            f"agent={result.get('agent')}",
        )
    except Exception as e:
        print(f"[End Session] Upload failed: {e}")

def _auto_match_monitor(profile_id: str, region: str, name: str, tag: str):
    """Runs in the background and auto-uploads when an actual match finishes."""
    try:
        client = ValorantLocalClient()
    except Exception:
        return
        
    was_in_game = False
    while True:
        try:
            phase = client.get_game_phase()
            if phase == GamePhase.IN_GAME:
                if not was_in_game:
                    print("\n[SpectAI] Live match detected! Monitoring for completion...")
                was_in_game = True
            elif was_in_game and phase == GamePhase.MENUS:
                print("\n[SpectAI] Match ended! Waiting 45s for Riot servers to process stats...")
                was_in_game = False
                time.sleep(45)  # Give Riot/Henrik API time to update database
                _run_end_session_upload(profile_id, region, name, tag, "all")
        except Exception:
            pass
        time.sleep(10)

def main():
    global _overlay, _app

    profile_id = None
    riot_region = os.getenv("RIOT_REGION", "na").strip().lower()
    riot_name = os.getenv("RIOT_NAME", "").strip()
    riot_tag = os.getenv("RIOT_TAG", "").strip()
    match_mode = os.getenv("RIOT_MATCH_MODE", "competitive").strip().lower()

    try:
        profile_id = _authenticate_user()
    except Exception as e:
        print(f"[Auth] Sign-in failed: {e}")

    if profile_id:
        riot_region = _prompt_text(f"Riot region [{riot_region}]: ", riot_region).lower()
        riot_name = _prompt_text(f"Riot username [{riot_name or 'Prany4'}]: ", riot_name or "Prany4")
        riot_tag = _prompt_text(f"Riot tag [{riot_tag or '2573'}]: ", riot_tag or "2573")
        match_mode = _prompt_text(f"Match mode [{match_mode}]: ", match_mode).lower()

    app = QApplication(sys.argv)
    _app = app
    app.setQuitOnLastWindowClosed(False)

    _overlay = Overlay()
    minimap  = MinimapOverlay()
    coach.init(_overlay, minimap)

    spect_ai = SpectAI(response_callback=lambda text: coach.push(text, "coach"))
    spect_ai.start()

    # Start Auto-Match Monitor
    if profile_id:
        monitor_thread = threading.Thread(target=_auto_match_monitor, args=(profile_id, riot_region, riot_name, riot_tag), daemon=True)
        monitor_thread.start()

    # Global hotkey listener
    listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    listener.daemon = True
    listener.start()

    coach.push("SpectAI ready. ALT+M play | ALT+H hide map | ALT+X overlay | ALT+E end session", "info")

    exit_code = app.exec()
    spect_ai.stop()

    if profile_id:
        _run_end_session_upload(
            profile_id=profile_id,
            region=riot_region,
            name=riot_name,
            tag=riot_tag,
            mode=match_mode,
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()