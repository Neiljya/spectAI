"""
clip_extractor.py — Extract video clips for each key moment in a session,
then upload them to Supabase Storage and persist URLs + descriptions into
match_data (attachments + coach_notes).

Env vars (loaded from .env at the project root):
    SUPABASE_URL           — project URL
    SUPABASE_SERVICE_KEY   — service-role key (bypasses RLS for overlay writes)
    SUPABASE_PROFILE_ID    — user's profile UUID (optional; also read from
                             spectai_config.json if present)
"""

import json
import os

from moviepy import VideoFileClip

try:
    from dotenv import load_dotenv
    # .env lives one level up at the project root
    _ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(os.path.abspath(_ENV_PATH))
except ImportError:
    pass

_SUPABASE_URL  = os.getenv("SUPABASE_URL", "").rstrip("/")   # strip trailing slash
_SUPABASE_KEY  = os.getenv("SUPABASE_SERVICE_KEY", "")
_CLIPS_BUCKET  = "match-clips"

# ---------------------------------------------------------------------------
# Supabase client (lazy, returns None when credentials are missing)
# ---------------------------------------------------------------------------

def _get_supabase():
    if not (_SUPABASE_URL and _SUPABASE_KEY):
        return None
    try:
        from supabase import create_client
        return create_client(_SUPABASE_URL, _SUPABASE_KEY)
    except ImportError:
        print("[Extractor] supabase-py not installed — skipping cloud upload.")
        return None


def _load_profile_id() -> str | None:
    """Try env var first, then spectai_config.json next to this file."""
    pid = os.getenv("SUPABASE_PROFILE_ID", "")
    if pid:
        return pid
    config_path = os.path.join(os.path.dirname(__file__), "spectai_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f).get("profile_id")
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_clips(session_dir: str) -> list[dict]:
    """Extract clips and upload to Supabase. Returns list of clip metadata."""
    moments_path   = os.path.join(session_dir, "key_moments.json")
    recording_path = os.path.join(session_dir, "match_recording.mp4")

    if not os.path.exists(recording_path):
        print(f"[Extractor] No recording found at {recording_path}")
        return []

    with open(moments_path, "r", encoding="utf-8") as f:
        moments = json.load(f)

    clip_info_list: list[dict] = []

    try:
        with VideoFileClip(recording_path) as video:
            for i, moment in enumerate(moments, 1):
                clip_dir = os.path.join(session_dir, f"clip_{i}")
                os.makedirs(clip_dir, exist_ok=True)

                clip_video_path = os.path.join(clip_dir, f"clip_{i}.mp4")
                clip_text_path  = os.path.join(clip_dir, f"clip_{i}.txt")

                start_s = float(moment["start_s"])
                end_s   = float(moment["end_s"])

                new_clip = video.subclipped(start_s, end_s)
                new_clip.write_videofile(
                    clip_video_path,
                    codec="libx264",
                    audio_codec="aac",
                    logger=None,
                )

                with open(clip_text_path, "w", encoding="utf-8") as f:
                    f.write(
                        f"{moment['title']}\n\n"
                        f"{moment['description']}\n\n"
                        f"{moment.get('paragraph', '')}\n"
                    )

                clip_info_list.append({
                    "index":       i,
                    "title":       moment["title"],
                    "description": moment["description"],
                    "paragraph":   moment.get("paragraph", ""),
                    "local_path":  clip_video_path,
                    "start_s":     start_s,
                    "end_s":       end_s,
                })

                print(f"[Extractor] clip_{i} saved ({start_s:.1f}s → {end_s:.1f}s)")
                new_clip.close()

    except Exception as e:
        print(f"[Extractor] Failed to process video: {e}")

    _upload_and_save(session_dir, clip_info_list)
    return clip_info_list


# ---------------------------------------------------------------------------
# Internal: upload clips + persist to match_data
# ---------------------------------------------------------------------------

def _upload_and_save(session_dir: str, clip_info_list: list[dict]) -> None:
    if not clip_info_list:
        return

    summary_path = os.path.join(session_dir, "match_summary.json")
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    match_id   = summary.get("match_id", os.path.basename(session_dir))
    profile_id = _load_profile_id()
    sb         = _get_supabase()

    clips_with_urls: list[dict] = []

    for info in clip_info_list:
        url = info["local_path"]  # fallback — local path until upload succeeds

        if sb:
            try:
                storage_path = f"{match_id}/clip_{info['index']}.mp4"
                with open(info["local_path"], "rb") as video_file:
                    sb.storage.from_(_CLIPS_BUCKET).upload(
                        path=storage_path,
                        file=video_file,
                        file_options={"content-type": "video/mp4", "upsert": "true"},
                    )
                url = sb.storage.from_(_CLIPS_BUCKET).get_public_url(storage_path)
                print(f"[Uploader] clip_{info['index']} → {url}")
            except Exception as e:
                print(f"[Uploader] Upload failed for clip_{info['index']}: {e}")

        clips_with_urls.append({
            "url":         url,
            "title":       info["title"],
            "description": info["description"],
            "paragraph":   info.get("paragraph", ""),
            "start_s":     info["start_s"],
            "end_s":       info["end_s"],
        })

    # Always write back to match_summary.json so the dashboard can pick it up
    summary["clips"] = clips_with_urls
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("[Uploader] Clip metadata saved to match_summary.json")

    if not sb:
        return

    attachments = [c["url"] for c in clips_with_urls[:5]]  # schema allows max 5

    # coach_notes must be a JSON array so the dashboard indexes notes[i] → clips[i]
    coach_notes = [
        {
            "note":  f"{c['title']}\n\n{c['description']}\n\n{c['paragraph']}".strip(),
            "title": c["title"],
        }
        for c in clips_with_urls[:5]
    ]

    _insert_match_data(sb, match_id, profile_id, attachments, coach_notes, summary)


def _insert_match_data(
    sb,
    match_id: str,
    profile_id: str | None,
    attachments: list[str],
    coach_notes: dict,
    summary: dict,
) -> None:
    if not profile_id:
        print("[Uploader] No profile_id — skipping match_data insert.")
        return

    try:
        sb.table("match_data").insert({
            "profile_id":  profile_id,
            "match_id":    match_id,
            "attachments": attachments,
            "coach_notes": coach_notes,
            "data": {
                "map":    summary.get("map"),
                "source": "overlay",
            },
        }).execute()
        print(f"[Uploader] match_data row inserted for match {match_id}")
    except Exception as e:
        print(f"[Uploader] match_data insert failed: {e}")
