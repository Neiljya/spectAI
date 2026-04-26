import os
import time
import threading

try:
    import cv2
    import mss
    import numpy as np
    import win32gui
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

RECORD_FPS    = 24
TARGET_WINDOW = "VALORANT  "


def _grab_frame(hwnd, sct):
    """Capture the window rect and return a BGR numpy frame, or None if minimised."""
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    if w <= 0 or h <= 0:
        return None, w, h
    monitor = {"top": top, "left": left, "width": w, "height": h}
    bgra = np.array(sct.grab(monitor))
    return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR), w, h


class ScreenRecorder:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self.output_path: str | None = None

    def start(self, output_path: str) -> bool:
        if not _AVAILABLE:
            print("[Recorder] Required libs (cv2/mss/win32gui) unavailable.")
            return False

        hwnd = win32gui.FindWindow(None, TARGET_WINDOW)
        if not hwnd:
            print(f"[Recorder] Window '{TARGET_WINDOW}' not found.")
            return False

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Probe frame size from a one-off grab
        with mss.mss() as sct:
            _, w, h = _grab_frame(hwnd, sct)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, RECORD_FPS, (w, h))
        if not writer.isOpened():
            print(f"[Recorder] VideoWriter failed to open: {output_path}")
            return False

        self.output_path = output_path
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._loop, args=(hwnd, writer), daemon=True
        )
        self._thread.start()
        print(f"[Recorder] Recording → {output_path} @ {RECORD_FPS} FPS")
        return True

    def stop(self):
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=8)
            self._thread = None
        self.output_path = None
        print("[Recorder] Recording stopped.")

    def _loop(self, hwnd: int, writer: "cv2.VideoWriter"):
        """
        Write frames keyed to wall-clock time so the video duration always
        matches real elapsed time, even when encoding stalls.  If a write
        takes longer than one frame interval the last captured frame is
        duplicated to fill the gap; if the loop runs fast it sleeps.
        """
        interval = 1.0 / RECORD_FPS
        start_t = time.perf_counter()
        frames_written = 0
        last_frame = None

        with mss.mss() as sct:
            try:
                while not self._stop_flag.is_set():
                    frame, _, _ = _grab_frame(hwnd, sct)
                    if frame is not None:
                        last_frame = frame

                    if last_frame is not None:
                        # Write as many frames as wall-clock says we owe
                        frames_due = int((time.perf_counter() - start_t) * RECORD_FPS) + 1
                        while frames_written < frames_due:
                            writer.write(last_frame)
                            frames_written += 1

                    # Sleep until the next frame slot
                    next_slot = start_t + frames_written * interval
                    sleep_for = next_slot - time.perf_counter()
                    if sleep_for > 0:
                        time.sleep(sleep_for)
            finally:
                writer.release()
