"""
clip_extractor.py — Extract video clips for each key moment in a session.
Compatible with MoviePy 2.1.2
"""

import json
import os
from moviepy import VideoFileClip

def extract_clips(session_dir: str) -> None:
    moments_path   = os.path.join(session_dir, "key_moments.json")
    recording_path = os.path.join(session_dir, "match_recording.mp4")

    if not os.path.exists(recording_path):
        print(f"[Extractor] No recording found at {recording_path}")
        return

    with open(moments_path, "r", encoding="utf-8") as f:
        moments = json.load(f)

    try:
        with VideoFileClip(recording_path) as video:
            for i, moment in enumerate(moments, 1):
                clip_dir = os.path.join(session_dir, f"clip_{i}")
                os.makedirs(clip_dir, exist_ok=True)

                clip_video_path = os.path.join(clip_dir, f"clip_{i}.mp4")
                clip_text_path  = os.path.join(clip_dir, f"clip_{i}.txt")

                start_s = float(moment["start_s"])
                end_s   = float(moment["end_s"])

                # --- MoviePy 2.1.2 Method ---
                # 'subclipped' is the standard in the latest 2.x releases
                new_clip = video.subclipped(start_s, end_s)

                new_clip.write_videofile(
                    clip_video_path, 
                    codec="libx264", 
                    audio_codec="aac",
                    logger=None
                )

                with open(clip_text_path, "w", encoding="utf-8") as f:
                    f.write(f"{moment['title']}\n\n{moment['description']}\n\n{moment.get('paragraph', '')}\n")

                print(f"[Extractor] clip_{i} saved ({start_s:.1f}s → {end_s:.1f}s)")
                
                # Clean up the subclip object
                new_clip.close()

    except Exception as e:
        print(f"[Extractor] Failed to process video: {e}")

# if __name__ == "__main__":
#     target_session = "sessions/20260426_030240"
#     if os.path.exists(target_session):
#         extract_clips(target_session)