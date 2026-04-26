import json
import os
from typing import Any

import dotenv
import requests


dotenv.load_dotenv()


def _fallback_summary(match_payload: dict[str, Any]) -> dict[str, Any]:
    meta = match_payload.get("metadata", {})
    map_name = meta.get("map", "Unknown")
    return {
        "summary": f"Match on {map_name}. Review opening duels and trade timing.",
        "strengths": ["Maintained engagement across rounds"],
        "weaknesses": ["Positioning consistency under pressure"],
        "next_steps": [
            "Play 3 deathmatches focusing head-level crosshair.",
            "Review first 6 rounds for avoidable peeks.",
            "Practice one default and one retake setup per site."
        ]
    }


def summarize_match_with_claude(match_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Returns normalized summary JSON used for DB persistence.
    If Claude is unavailable, returns a deterministic fallback summary.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("CLAUDE_API_KEY", "").strip()
    if not api_key:
        return _fallback_summary(match_payload)

    prompt = (
        "You are a Valorant performance analyst. Given this match JSON, produce concise coaching output in JSON only. "
        "Format: {\"summary\": str, \"strengths\": [str], \"weaknesses\": [str], \"next_steps\": [str]}. "
        "Keep each list to 3 items max. Match data:\n"
        + json.dumps(match_payload, ensure_ascii=True)
    )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
                "max_tokens": 600,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=35,
        )
        resp.raise_for_status()
        data = resp.json()
        text = ""
        for item in data.get("content", []):
            if item.get("type") == "text":
                text += item.get("text", "")

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return _fallback_summary(match_payload)

        parsed = json.loads(text[start:end + 1])
        if not isinstance(parsed, dict):
            return _fallback_summary(match_payload)

        return {
            "summary": str(parsed.get("summary", "")).strip() or _fallback_summary(match_payload)["summary"],
            "strengths": [str(x) for x in (parsed.get("strengths") or [])][:3],
            "weaknesses": [str(x) for x in (parsed.get("weaknesses") or [])][:3],
            "next_steps": [str(x) for x in (parsed.get("next_steps") or [])][:3],
        }
    except Exception:
        return _fallback_summary(match_payload)
