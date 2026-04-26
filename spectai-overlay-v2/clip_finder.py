#!/usr/bin/env python3
"""
clip_finder.py — Find 5 key improvement moments in a recorded match.

Usage:
    python clip_finder.py sessions/<id>/
    python clip_finder.py sessions/<id>/match_summary.json
"""

import json
import os
import sys

import dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

dotenv.load_dotenv()

MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are a Valorant coaching analyst reviewing post-match AI coaching logs.
Your job is to identify exactly 5 moments where the player made mistakes or showed clear areas for improvement.

Focus on:
- Repeated poor positioning or over-extension (same mistake flagged multiple times = one moment)
- Missed rotations or failing to regroup with the team
- Economy mismanagement (buying in a save round, not buying in a full-buy round, sitting on excess credits)
- Taking unnecessary duels while low HP or low ammo
- Failing to use utility at critical windows

Do NOT select highlights or moments where the player performed well.
Prioritize the 5 moments that, if corrected, would have the highest impact on improvement.

Each moment may span several coaching events. Set a generous clip window:
- start_s: ~10 seconds before the first relevant event in the cluster
- end_s: ~5 seconds after the last relevant event in the cluster
- Clamp both values to [0, session_duration_s]
- Make sure the clip is not too short (<5s) or too long (>1minute); adjust the window as needed.

For each moment provide:
  title       — 5 words max label
  description — 1-2 sentence summary of the mistake
  paragraph   — full coaching paragraph covering:
                  (a) what the player did right in this stretch, if anything
                  (b) exactly what went wrong and why it cost them
                  (c) a specific, actionable drill or habit to fix it next game
  start_s     — clip start in seconds (float)
  end_s       — clip end in seconds (float)"""


class KeyMoment(BaseModel):
    title: str
    description: str
    paragraph: str
    start_s: float
    end_s: float


class KeyMomentsResponse(BaseModel):
    moments: list[KeyMoment]


def _resolve_path(path: str) -> str:
    if os.path.isdir(path):
        return os.path.join(path, "match_summary.json")
    return path


def _load_summary(json_path: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _clean_events(events: list[dict]) -> list[dict]:
    """Drop malformed voice events that leaked raw JSON/code blocks."""
    return [
        ev for ev in events
        if not ev.get("text", "").lstrip().startswith(("```", '{"should_coach"'))
    ]


def _build_prompt(summary: dict) -> str:
    events = _clean_events(summary.get("events", []))
    duration = events[-1]["elapsed_s"] if events else 0

    lines = [
        f"Map: {summary.get('map') or 'unknown'}",
        f"Session duration: {duration:.1f}s",
        "",
        "Coaching events (elapsed_s = seconds into the recording):",
    ]
    for ev in events:
        lines.append(f"  [{ev['elapsed_s']:.1f}s] [{ev['source']}] {ev['text']}")

    return "\n".join(lines)


def find_key_moments(summary_path: str) -> list[KeyMoment]:
    summary = _load_summary(summary_path)
    prompt = _build_prompt(summary)

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=KeyMomentsResponse,
        ),
        contents=prompt,
    )

    return response.parsed.moments


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    json_path = _resolve_path(sys.argv[1])
    summary = _load_summary(json_path)

    print(f"Analyzing {summary.get('match_id', json_path)}…")
    moments = find_key_moments(json_path)

    print(f"\n5 Key Moments — {summary.get('match_id', '')}\n{'─' * 50}")
    for i, m in enumerate(moments, 1):
        print(f"\n{i}. {m.title}  [{m.start_s:.1f}s → {m.end_s:.1f}s]")
        print(f"   {m.description}")
        print(f"   {m.paragraph}")

    out_path = os.path.join(os.path.dirname(json_path), "key_moments.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([m.model_dump() for m in moments], f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
