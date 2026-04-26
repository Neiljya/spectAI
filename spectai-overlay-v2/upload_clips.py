"""
upload_clips.py — One-off script to upload already-extracted clips from
sessions/20260426_053046 to Supabase Storage and insert a match_data row.

Run from spectai-overlay-v2/:
    python upload_clips.py
"""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))

SUPABASE_URL    = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY    = os.getenv("SUPABASE_SERVICE_KEY", "")
PROFILE_ID      = os.getenv("SUPABASE_PROFILE_ID", "")
CLIPS_BUCKET    = "match-clips"
SESSION_DIR     = os.path.join(os.path.dirname(__file__), "..", "sessions", "20260426_053046")
NUM_CLIPS       = 5

if not all([SUPABASE_URL, SUPABASE_KEY, PROFILE_ID]):
    print("Missing SUPABASE_URL, SUPABASE_SERVICE_KEY, or SUPABASE_PROFILE_ID in .env")
    sys.exit(1)

from supabase import create_client
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

summary_path = os.path.join(SESSION_DIR, "match_summary.json")
with open(summary_path, "r", encoding="utf-8") as f:
    summary = json.load(f)

match_id = summary["match_id"]
print(f"Session: {match_id}")

clips_with_urls = []

for i in range(1, NUM_CLIPS + 1):
    mp4_path = os.path.join(SESSION_DIR, f"clip_{i}", f"clip_{i}.mp4")
    txt_path = os.path.join(SESSION_DIR, f"clip_{i}", f"clip_{i}.txt")

    # Parse txt: line 1 = title, blank line, line 3 = short description, blank line, rest = paragraph
    with open(txt_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    parts = raw.split("\n\n", 2)
    title       = parts[0].strip() if len(parts) > 0 else ""
    description = parts[1].strip() if len(parts) > 1 else ""
    paragraph   = parts[2].strip() if len(parts) > 2 else ""

    # Upload mp4 to Supabase Storage
    storage_path = f"{match_id}/clip_{i}.mp4"
    print(f"Uploading clip_{i}...", end=" ", flush=True)
    with open(mp4_path, "rb") as video_file:
        sb.storage.from_(CLIPS_BUCKET).upload(
            path=storage_path,
            file=video_file,
            file_options={"content-type": "video/mp4", "upsert": "true"},
        )
    url = sb.storage.from_(CLIPS_BUCKET).get_public_url(storage_path)
    print(f"done → {url}")

    clips_with_urls.append({
        "url":         url,
        "title":       title,
        "description": description,
        "paragraph":   paragraph,
    })

attachments = [c["url"] for c in clips_with_urls]

# coach_notes must be a JSON array so the dashboard can index notes[i] → clips[i]
# Each element uses the "note" key that RecentMatches.tsx reads
coach_notes = [
    {
        "note":      f"{c['title']}\n\n{c['description']}\n\n{c['paragraph']}".strip(),
        "title":     c["title"],
    }
    for c in clips_with_urls
]

# Write URLs back to match_summary.json
summary["clips"] = clips_with_urls
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

# Insert into match_data
sb.table("match_data").insert({
    "profile_id":  PROFILE_ID,
    "match_id":    match_id,
    "attachments": attachments,
    "coach_notes": coach_notes,
    "data": {
        "map":    summary.get("map"),
        "source": "overlay",
    },
}).execute()

print(f"\nmatch_data row inserted for match {match_id}")
print(f"{len(clips_with_urls)} clips attached.")
