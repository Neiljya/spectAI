# overlay.py
# Single coach widget: circle avatar + one message box, top-right, transparent.
# New message replaces the current one — no stacking.

import sys
import ctypes

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy
from PyQt6.QtCore    import (
    Qt, QPoint, QSize, QRect, QTimer,
    QPropertyAnimation, QEasingCurve,
    pyqtProperty, pyqtSignal
)
from PyQt6.QtGui import (
    QPainter, QColor, QPainterPath, QPen, QBrush,
    QLinearGradient, QPixmap, QFont, QFontMetrics,
    QRadialGradient
)
from PyQt6.QtWidgets import QApplication


# ── Config ────────────────────────────────────────────────
OFFSET_X      = 28       # from right edge
OFFSET_Y      = 28       # from top
AVATAR_SIZE   = 52       # diameter of circle
BOX_WIDTH     = 300      # message box width
FADE_MS       = 280      # fade duration
HOLD_MS       = 7000     # how long message stays

# Accent colors per kind
KIND_COLORS = {
    "coach":    "#E63946",
    "warning":  "#FFB703",
    "positive": "#06D6A0",
    "info":     "#7B8896",
}

import os as _os
AVATAR_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'avatar.png')   # drop a PNG here — fallback draws initials


def _click_through(hwnd: int):
    if sys.platform != "win32":
        return
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)


# ── Avatar circle ─────────────────────────────────────────

class AvatarCircle(QWidget):
    """Circular avatar. Loads avatar.png, falls back to a styled ring."""

    def __init__(self, size: int, parent=None):
        super().__init__(parent)
        self._size  = size
        self._color = QColor(KIND_COLORS["coach"])
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pixmap = None
        try:
            px = QPixmap(AVATAR_PATH)
            if not px.isNull():
                self._pixmap = px.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
        except Exception:
            pass

    def set_accent(self, color: str):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self._size

        # Clip to circle
        clip = QPainterPath()
        clip.addEllipse(3, 3, s - 6, s - 6)
        p.setClipPath(clip)

        if self._pixmap:
            p.drawPixmap(3, 3, s - 6, s - 6, self._pixmap)
        else:
            # Fallback: dark fill + "AI" text
            p.fillPath(clip, QColor(14, 20, 26, 230))
            p.setClipping(False)
            p.setPen(QColor(self._color))
            f = QFont("Syne", 13)
            f.setWeight(QFont.Weight.Bold)
            p.setFont(f)
            p.drawText(QRect(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "AI")

        p.setClipping(False)

        # Accent ring
        pen = QPen(self._color, 2.5)
        p.setPen(pen)
        p.drawEllipse(3, 3, s - 6, s - 6)

        # Outer glow
        glow = QColor(self._color)
        glow.setAlpha(40)
        p.setPen(QPen(glow, 5))
        p.drawEllipse(1, 1, s - 2, s - 2)


# ── Message box ───────────────────────────────────────────

class MessageBox(QWidget):
    """
    Single dark rounded box that shows the coach message.
    Fades in on new message, auto-dismisses after HOLD_MS.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alpha      = 0.0
        self._color      = QColor(KIND_COLORS["coach"])
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._fade_out)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(BOX_WIDTH)
        self._build_ui()
        self.hide()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 13)
        layout.setSpacing(5)

        self._tag = QLabel("AI COACH")
        self._tag.setStyleSheet(f"""
            color: {KIND_COLORS['coach']};
            font-family: 'DM Mono', 'Courier New', monospace;
            font-size: 9px;
            letter-spacing: 2.5px;
            background: transparent;
        """)

        self._msg = QLabel()
        self._msg.setWordWrap(True)
        self._msg.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._msg.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._msg.setStyleSheet("""
            color: #EDF0F3;
            font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
            font-size: 13px;
            font-weight: 400;
            background: transparent;
            line-height: 1.5;
        """)

        layout.addWidget(self._tag)
        layout.addWidget(self._msg)

    def display(self, text: str, kind: str):
        # Cancel pending dismiss
        self._dismiss_timer.stop()

        # Update accent color + tag
        color_hex    = KIND_COLORS.get(kind, KIND_COLORS["coach"])
        self._color  = QColor(color_hex)
        self._tag.setStyleSheet(f"""
            color: {color_hex};
            font-family: 'DM Mono', 'Courier New', monospace;
            font-size: 9px; letter-spacing: 2.5px; background: transparent;
        """)
        self._msg.setText(text)
        self.adjustSize()
        self.update()

        # Fade in
        self.show()
        self._animate(0.0, 1.0)
        self._dismiss_timer.start(HOLD_MS)

    def _fade_out(self):
        self._animate(1.0, 0.0, on_done=self.hide)

    def _animate(self, start: float, end: float, on_done=None):
        a = QPropertyAnimation(self, b"alpha")
        a.setDuration(FADE_MS)
        a.setStartValue(start)
        a.setEndValue(end)
        a.setEasingCurve(
            QEasingCurve.Type.OutCubic if end > start else QEasingCurve.Type.InCubic
        )
        if on_done:
            a.finished.connect(on_done)
        a.start()
        self._anim = a   # keep ref

    # Alpha property
    def _get_alpha(self): return self._alpha
    def _set_alpha(self, v):
        self._alpha = v
        self.update()

    alpha = pyqtProperty(float, _get_alpha, _set_alpha)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._alpha)

        w, h, r = self.width(), self.height(), 12
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, r, r)

        # Dark fill
        p.fillPath(path, QColor(8, 12, 17, 210))

        # Subtle shimmer
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(255, 255, 255, 9))
        grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillPath(path, QBrush(grad))

        # Top accent line
        c = QColor(self._color)
        c.setAlpha(200)
        p.setPen(QPen(c, 1.5))
        p.drawLine(r, 0, w - r, 0)

        # Outer border
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.drawPath(path)


# ── Main overlay ──────────────────────────────────────────

class Overlay(QWidget):
    """
    Full-screen transparent canvas.
    Holds avatar circle + single message box in top-right.
    """

    _enqueue = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._enqueue.connect(self._on_message)
        self._init_window()
        self._build_widgets()

    def _init_window(self):
        geo = QApplication.primaryScreen().geometry()
        self.setGeometry(geo)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint       |
            Qt.WindowType.WindowStaysOnTopHint      |
            Qt.WindowType.Tool                      |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        super().show()
        _click_through(int(self.winId()))

    def _build_widgets(self):
        sw = self.width()

        # Avatar — anchored top-right
        self._avatar = AvatarCircle(AVATAR_SIZE, parent=self)
        ax = sw - AVATAR_SIZE - OFFSET_X
        self._avatar.move(ax, OFFSET_Y)
        self._avatar.show()

        # Message box — sits left of avatar, vertically centered to it
        self._box = MessageBox(parent=self)
        # Will be positioned in _on_message once we know the box height

    def push(self, text: str, kind: str = "coach"):
        """Thread-safe. Call with your LLM output."""
        self._enqueue.emit(text, kind)

    def _on_message(self, text: str, kind: str):
        sw = self.width()

        # Update avatar accent ring color
        self._avatar.set_accent(KIND_COLORS.get(kind, KIND_COLORS["coach"]))

        # Show message box
        self._box.display(text, kind)
        self._box.adjustSize()

        # Position: right-aligned next to avatar, vertically centered
        bw = self._box.width()
        bh = self._box.height()
        bx = sw - AVATAR_SIZE - OFFSET_X - bw - 10
        by = OFFSET_Y + (AVATAR_SIZE - bh) // 2
        by = max(OFFSET_Y, by)   # don't go above top edge
        self._box.move(bx, by)

    def toggle(self):
        """Show/hide the entire overlay including avatar and message box."""
        self._visible = not getattr(self, '_visible', True)
        self._avatar.setVisible(self._visible)
        self._box.setVisible(self._visible if self._box.isVisible() else False)