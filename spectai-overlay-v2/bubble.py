# bubble.py
# One speech bubble. Slides in, holds, fades out.
# Call show_bubble(text, kind) from coach.py — that's the only integration point.

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui     import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen


# ── Bubble kinds → visual accent color + icon ─────────────
# Swap in whatever kinds your LLM output produces.
# Just make sure the "kind" string you pass to show_bubble() matches a key here.
KINDS = {
    "coach":    {"color": "#E63946", "icon": "◈"},   # red   — proactive tip
    "warning":  {"color": "#FFB703", "icon": "▲"},   # gold  — danger
    "positive": {"color": "#06D6A0", "icon": "◉"},   # teal  — good play
    "info":     {"color": "#7B8896", "icon": "○"},   # gray  — neutral
}

DURATION_MS = 6000   # how long bubble stays visible
FADE_MS     = 350    # fade in/out duration


class SpeechBubble(QWidget):

    def __init__(self, text: str, kind: str = "coach", parent=None):
        super().__init__(parent)
        self.kind_   = KINDS.get(kind, KINDS["coach"])
        self._alpha  = 0.0
        self._on_done = None

        self._init_window()
        self._build_ui(text)
        self._fade_in()
        QTimer.singleShot(DURATION_MS, self._fade_out)

    # ── Window flags ─────────────────────────────────────

    def _init_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint       |
            Qt.WindowType.WindowStaysOnTopHint      |
            Qt.WindowType.Tool                      |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMaximumWidth(360)
        self.setMinimumWidth(260)

    # ── UI ────────────────────────────────────────────────

    def _build_ui(self, text: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 14)
        root.setSpacing(7)

        # Header: icon + "AI COACH" tag
        header = QHBoxLayout()
        header.setSpacing(7)

        icon = QLabel(self.kind_["icon"])
        icon.setStyleSheet(f"""
            color: {self.kind_['color']};
            font-size: 12px;
            background: transparent;
        """)

        tag = QLabel("AI COACH")
        tag.setStyleSheet(f"""
            color: {self.kind_['color']};
            font-family: 'DM Mono', 'Courier New', monospace;
            font-size: 9px;
            letter-spacing: 2.5px;
            background: transparent;
        """)

        header.addWidget(icon)
        header.addWidget(tag)
        header.addStretch()

        # Message
        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        msg.setStyleSheet("""
            color: #EDF0F3;
            font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
            font-size: 13px;
            font-weight: 400;
            line-height: 1.5;
            background: transparent;
        """)

        root.addLayout(header)
        root.addWidget(msg)
        self.adjustSize()

    # ── Paint ─────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._alpha)

        w, h, r = self.width(), self.height(), 14

        # Shape
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, r, r)

        # Fill — dark translucent
        p.fillPath(path, QColor(8, 12, 17, 215))

        # Subtle top-to-bottom shimmer
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(255, 255, 255, 10))
        grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillPath(path, QBrush(grad))

        # Left accent bar
        c = QColor(self.kind_["color"])
        p.setPen(QPen(c, 2))
        p.drawLine(1, r, 1, h - r)

        # Top accent dash
        c.setAlpha(160)
        p.setPen(QPen(c, 1))
        p.drawLine(2, 1, 80, 1)

        # Outer border
        p.setPen(QPen(QColor(255, 255, 255, 16), 1))
        p.drawPath(path)

    # ── Alpha property for animation ──────────────────────

    def _get_alpha(self): return self._alpha
    def _set_alpha(self, v: float):
        self._alpha = v
        self.update()

    alpha = pyqtProperty(float, _get_alpha, _set_alpha)

    # ── Animations ────────────────────────────────────────

    def _fade_in(self):
        a = QPropertyAnimation(self, b"alpha")
        a.setDuration(FADE_MS)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start()
        self._anim = a   # keep ref

    def _fade_out(self):
        a = QPropertyAnimation(self, b"alpha")
        a.setDuration(FADE_MS)
        a.setStartValue(1.0)
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.Type.InCubic)
        a.finished.connect(self._cleanup)
        a.start()
        self._anim_out = a   # keep ref

    def _cleanup(self):
        if self._on_done:
            self._on_done(self)
        self.hide()
        self.deleteLater()

    def on_done(self, cb):
        """Register callback for when bubble finishes. Used by Overlay to update stack."""
        self._on_done = cb
        return self
