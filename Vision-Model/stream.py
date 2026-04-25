import io
import win32gui
import numpy as np
import mss

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    from PIL import Image

class WindowCapture:
    def __init__(self, window_title: str):
        self.window_title = window_title
        self.hwnd = win32gui.FindWindow(None, window_title)
        if not self.hwnd:
            raise Exception(f"Window '{window_title}' not found")
        
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        self.width = right - left
        self.height = bottom - top
        self.monitor = {"top": top, "left": left, "width": self.width, "height": self.height}
        self.sct = mss.mss()

    def capture(self):
        # Update the window position every frame in case it moved or was resized
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        self.width = right - left
        self.height = bottom - top
        self.monitor = {"top": top, "left": left, "width": self.width, "height": self.height}

        # Handle minimized windows to prevent crashing
        if self.width <= 0 or self.height <= 0:
            return None

        sct_img = self.sct.grab(self.monitor)
        bgra = np.array(sct_img)
        if _CV2_AVAILABLE:
            return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
        # Pillow fallback: drop alpha, swap B and R → RGB
        return bgra[:, :, [2, 1, 0]]

    # def frame_to_jpeg(self, frame, quality=80):
    #     encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    #     success, encoded_image = cv2.imencode('.jpg', frame, encode_param)
    #     if success:
    #         return encoded_image.tobytes()
    #     return None
    
    def frame_to_jpeg(self, frame, size=(768, 768)) -> bytes:
        if _CV2_AVAILABLE:
            resized = cv2.resize(frame, size)
            _, jpeg = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return jpeg.tobytes()
        img = Image.fromarray(frame)
        img = img.resize(size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    
    def list_windows(): 
        """Run this first to find your exact window title"""
        windows = []
        win32gui.EnumWindows(lambda hwnd, _: windows.append(win32gui.GetWindowText(hwnd)), None)
        for w in windows:
            if w:  # filter empty titles
                print(w)

    def change_window(self, new_window_title: str):
        self.window_title = new_window_title
        self.hwnd = win32gui.FindWindow(None, new_window_title)
        if not self.hwnd:
            raise Exception(f"Window '{new_window_title}' not found")
        
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        self.width = right - left
        self.height = bottom - top
        self.monitor = {"top": top, "left": left, "width": self.width, "height": self.height}


if __name__ == "__main__":
    print("=== Open Windows ===")
    # list_windows()
    
    # Replace with a window title from the list above
    TARGET_WINDOW = "VALORANT  "

    screen_capture = WindowCapture(TARGET_WINDOW)
    
    # Create the window once before the loop
    cv2.namedWindow("SpectAI - Capture Test", cv2.WINDOW_NORMAL)
    
    while True:
        frame = screen_capture.capture()
        cv2.imshow("SpectAI - Capture Test", frame)
        # print(type(frame))
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()