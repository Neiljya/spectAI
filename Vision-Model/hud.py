import sys
import os
import cv2
import numpy as np
import json

from stream import WindowCapture
from core.ocr import extract_text as easyocr_extract_text, initialize_ocr
from core.image_processing import enhance_for_ocr

# (left, top, right, bottom) as fractions of frame width/height
REGIONS = {
    # "hp_bar":       (0.008, 0.916, 0.160, 0.944),
    # "shield_bar":   (0.008, 0.890, 0.160, 0.917),
    "hp_number":    (0.30, 0.93, 0.34, 0.97),
    "shield_number":(0.28, 0.93, 0.30, 0.97),
    "credits":      (0.945, 0.96, 0.98, 0.98),
    "timer":        (0.47, 0.03, 0.53, 0.06),
    "score_left":   (0.42, 0.03, 0.44, 0.06),
    "score_right":  (0.56, 0.03, 0.58, 0.06),
    # "spike":        (0.45, 0.05, 0.55, 0.09),
    # "phase_bar":    (0.35, 0.06, 0.65, 0.09),
    # "ult_orbs":     (0.56, 0.95, 0.62, 0.97),
    "loaded_ammo": (0.665, 0.93, 0.695, 0.97),
    "stored_ammo": (0.703, 0.94, 0.72, 0.96),
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
    # "spike":        (0, 0, 255),
    # "phase_bar":    (200, 0, 200),
    # "ult_orbs":     (0, 215, 255),
    "loaded_ammo":  (0, 255, 0),
    "stored_ammo":  (0, 200, 255),
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


# --- Skeleton for Extraction Logistics ---
# Uncomment and install pytesseract / easyocr as needed:
# import pytesseract

class ValorantHUDScanner:
    def __init__(self, templates=None):
        """
        Store templates for opencv matching (spike, ult icons, abilities, phases).
        e.g., self.spike_template = cv2.imread('templates/spike_planted.png', 0)
        """
        self.templates = templates or {}
        # Ensure OCR is initialized
        initialize_ocr()

    def get_roi_image(self, frame: np.ndarray, region_name: str) -> np.ndarray:
        if region_name not in REGIONS:
            return None
        h, w = frame.shape[:2]
        l, t, r, b = REGIONS[region_name]
        return frame[int(t*h):int(b*h), int(l*w):int(r*w)]

    def extract_text(self, roi_img: np.ndarray, is_number=False, region_name="unnamed") -> str:
        """
        OCR text extraction using the valorant-data-extraction engine.
        """
        if roi_img is None or roi_img.size == 0: 
            return ""
        
        # Preprocess the ROI
        enhanced_img = enhance_for_ocr(roi_img, region_name=region_name)
        
        # Configure EasyOCR arguments depending on if we are looking for numbers
        kwargs = {}
        if is_number:
            kwargs["allowlist"] = "0123456789"
            
        # extract_text returns a List[str]. Join them into a single string.
        results = easyocr_extract_text(enhanced_img, detail=0, region_name=region_name, **kwargs)
        if results:
            return " ".join(results).strip()
        
        return ""

    def parse_hud(self, frame: np.ndarray) -> dict:
        """Main method to parse all HUD elements."""
        credits_str = self.extract_text(self.get_roi_image(frame, "credits"), is_number=True, region_name="credits")
        
        # Hack to fix '$' often read as '5' in larger credit counts resulting in e.g. 35800 instead of 3800
        if credits_str.isdigit() and int(credits_str) > 9000 and len(credits_str) >= 2 and credits_str[1] == '5':
            credits_str = credits_str[0] + credits_str[2:]

        data = {
            "hp": self.extract_text(self.get_roi_image(frame, "hp_number"), is_number=True, region_name="hp"),
            "shield": self.extract_text(self.get_roi_image(frame, "shield_number"), is_number=True, region_name="shield"),
            "credits": credits_str,
            "match_timer": self.extract_text(self.get_roi_image(frame, "timer"), is_number=False, region_name="match_timer"),
            "my_team_score": self.extract_text(self.get_roi_image(frame, "score_left"), is_number=True, region_name="my_team_score"),
            "enemy_team_score": self.extract_text(self.get_roi_image(frame, "score_right"), is_number=True, region_name="enemy_team_score"),
            "game_phase": self.extract_text(self.get_roi_image(frame, "phase_bar"), is_number=False, region_name="game_phase"),
            "loaded_ammo": self.extract_text(self.get_roi_image(frame, "loaded_ammo"), is_number=True, region_name="loaded_ammo"),
            "stored_ammo": self.extract_text(self.get_roi_image(frame, "stored_ammo"), is_number=True, region_name="stored_ammo"),
        }
        return data


if __name__ == "__main__":
    TARGET = "VALORANT  "
    print(f"Connecting to '{TARGET}'...")
    cap = WindowCapture(TARGET)

    cv2.namedWindow("SpectAI - HUD", cv2.WINDOW_NORMAL)

    print("Running — press Q to quit, D to toggle overlay, G to toggle grid")

    show_overlay = True
    show_grid    = False
    scanner      = ValorantHUDScanner()

    while True:
        frame = cap.capture()
        if frame is None:
            continue

        # HUD Parsing (Skeleton disabled by default or logging sparingly)
        data = scanner.parse_hud(frame)
        # Clear the console/print structured JSON so it updates in real time relatively cleanly
        os.system('cls' if os.name == 'nt' else 'clear')
        print(json.dumps(data, indent=4))

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
