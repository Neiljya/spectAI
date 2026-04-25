import sys
import cv2
import numpy as np
sys.path.insert(0, ".")

from stream import WindowCapture

# (left, top, right, bottom) as fractions of frame width/height
REGIONS = {
    # "hp_bar":       (0.008, 0.916, 0.160, 0.944),
    # "shield_bar":   (0.008, 0.890, 0.160, 0.917),
    "hp_number":    (0.28, 0.92, 0.34, 0.96),
    "shield_number":(0.34, 0.92, 0.38, 0.96),
    "credits":      (0.92, 0.95, 0.99, 0.98),
    "timer":        (0.46, 0.00, 0.54, 0.05),
    "score_left":   (0.42, 0.02, 0.44, 0.05),
    "score_right":  (0.56, 0.02, 0.58, 0.05),
    "spike":        (0.45, 0.05, 0.55, 0.09),
    "phase_bar":    (0.35, 0.06, 0.65, 0.09),
    "ult_orbs":     (0.57, 0.90, 0.62, 0.97),
}

COLOURS = {
    # "hp_bar":       (0, 255, 0),
    # "shield_bar":   (255, 200, 0),
    "hp_number":    (0, 200, 0),
    "shield_number":(200, 160, 0),
    "credits":      (0, 200, 255),
    "timer":        (255, 255, 0),
    "score_left":   (255, 100, 0),
    "score_right":  (255, 100, 0),
    "spike":        (0, 0, 255),
    "phase_bar":    (200, 0, 200),
    "ult_orbs":     (0, 215, 255),
}


def draw_grid(frame: np.ndarray, step: float = 0.05) -> np.ndarray:
    h, w = frame.shape[:2]
    out = frame.copy()
    colour = (60, 60, 60)
    label_colour = (180, 180, 180)
    n_x = int(1.0 / step)
    n_y = int(1.0 / step)
    for i in range(1, n_x):
        x = int(i * step * w)
        cv2.line(out, (x, 0), (x, h), colour, 1)
        cv2.putText(out, f"{i*step:.2f}", (x + 2, 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, label_colour, 1, cv2.LINE_AA)
    for i in range(1, n_y):
        y = int(i * step * h)
        cv2.line(out, (0, y), (w, y), colour, 1)
        cv2.putText(out, f"{i*step:.2f}", (2, y - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, label_colour, 1, cv2.LINE_AA)
    return out


def draw_regions(frame: np.ndarray) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    for name, (l, t, r, b) in REGIONS.items():
        x1, y1 = int(l * w), int(t * h)
        x2, y2 = int(r * w), int(b * h)
        colour = COLOURS.get(name, (128, 128, 128))
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(out, name, (x1 + 2, max(y1 + 14, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1, cv2.LINE_AA)
    return out


TARGET = "VALORANT  "
print(f"Connecting to '{TARGET}'...")
cap = WindowCapture(TARGET)

cv2.namedWindow("SpectAI - HUD", cv2.WINDOW_NORMAL)

print("Running — press Q to quit, D to toggle overlay, G to toggle grid")

show_overlay = True
show_grid    = False

while True:
    frame = cap.capture()
    if frame is None:
        continue

    display = frame
    if show_grid:
        display = draw_grid(display)
    if show_overlay:
        display = draw_regions(display)

    cv2.imshow("SpectAI - HUD", display)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key == ord("d"):
        show_overlay = not show_overlay
    elif key == ord("g"):
        show_grid = not show_grid

cv2.destroyAllWindows()
