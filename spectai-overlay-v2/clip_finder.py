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

dotenv.load_dotenv()

MODEL = "gemini-2.5-flash-preview-05-20"

SYSTEM_PROMPT = """You are a Valorant coaching analyst reviewing post-match AI coaching logs.
Your job is to identify exactly 5 moments where the player made mistakes or showed clear areas for improvement.

Focus on:
- Repeated poor positioning or over-extension (same mistake flagged multiple times is one moment)
- Missed rotations or failing to regroup with the team
- Economy mismanagement (buying in a save round, not buying in a full-buy round, sitting on excess credits)
- Taking unnecessary duels while low HP or low ammo
- Failing to use utility at critical windows

Do NOT select highlights or moments where the player performed well.
Prioritize the 5 moments that, if corrected, would have the highest impact on improvement.

Each moment may span several coaching events. Use the surrounding events to set a generous clip window:
- "start_s": ~10 seconds before the first relevant event in the cluster
- "end_s": ~5 seconds after the last relevant event in the cluster
- Clamp both values to [0, session_duration_s]

Return ONLY a valid JSON array of exactly 5 objects, each with:
  "title"       — 5 words max
  "description" — 1-2 sentences: what went wrong and the specific fix
  "start_s"     — clip start (float, seconds)
  "end_s"       — clip end (float, seconds)

No markdown, no code fences, no extra text — raw JSON array only."""


def _resolve_path(path: str) -> str:
    if os.path.isdir(path):
        return os.path.join(path, "match_summary.json")
    return path


def _load_summary(json_path: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _clean_events(events: list[dict]) -> list[dict]:
    """Drop malformed voice events that leaked raw JSON/code blocks."""
    clean = []
    for ev in events:
        text = ev.get("text", "")
        if text.lstrip().startswith("```") or text.lstrip().startswith('{"should_coach"'):
            continue
        clean.append(ev)
    return clean


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


def find_key_moments(summary_path: str) -> list[dict]:
    summary = _load_summary(summary_path)
    prompt = _build_prompt(summary)

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
        ),
        contents=prompt,
    )

    text = response.text.strip()
    # Strip markdown fences if the model ignores the instruction
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)


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
        print(f"\n{i}. {m['title']}  [{m['start_s']:.1f}s → {m['end_s']:.1f}s]")
        print(f"   {m['description']}")

    out_path = os.path.join(os.path.dirname(json_path), "key_moments.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(moments, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
