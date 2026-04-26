import os

try:
    import cv2
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

RECORD_FPS = 24  # keep in sync with live_llm_s.RECORD_FPS


class ScreenRecorder:
    def __init__(self):
        self._writer = None
        self._output_path: str | None = None
        self.output_path: str | None = None

    def start(self, output_path: str):
        """Arm the recorder. VideoWriter is created lazily on the first write_frame call."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        self._output_path = output_path
        self.output_path = output_path
        self._writer = None

    def write_frame(self, frame):
        """Called from SpectAI's capture loop with each raw BGR frame."""
        if not _AVAILABLE or not self._output_path:
            return
        if self._writer is None:
            h, w = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self._writer = cv2.VideoWriter(self._output_path, fourcc, RECORD_FPS, (w, h))
            if not self._writer.isOpened():
                print(f"[Recorder] VideoWriter failed to open: {self._output_path}")
                self._writer = None
                self._output_path = None
                return
            print(f"[Recorder] Recording → {self._output_path} @ {RECORD_FPS} FPS")
        self._writer.write(frame)

    def stop(self):
        if self._writer:
            self._writer.release()
            self._writer = None
        self._output_path = None
        print("[Recorder] Recording stopped.")
