import json
import os
import time
from datetime import datetime


class GameSession:
    def __init__(self, match_id: str | None = None, map_name: str | None = None):
        self.match_id = match_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.map_name = map_name
        self.started_at = datetime.now().isoformat()
        self._start_epoch = time.time()
        self.video_path: str | None = None
        self.events: list[dict] = []

    def add_event(self, text: str, source: str = "coach", round_num: int | None = None):
        elapsed = round(time.time() - self._start_epoch, 2)
        self.events.append({
            "elapsed_s": elapsed,
            "round": round_num,
            "source": source,
            "text": text,
        })

    def save(self) -> str:
        folder = os.path.join("sessions", self.match_id)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "match_summary.json")
        data = {
            "match_id": self.match_id,
            "map": self.map_name,
            "started_at": self.started_at,
            "ended_at": datetime.now().isoformat(),
            "video": self.video_path,
            "event_count": len(self.events),
            "events": self.events,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return path
