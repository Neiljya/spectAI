# minimap.py
import os, sys, ctypes, math

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QApplication, QSizePolicy
)
from PyQt6.QtCore import (
    QObject, Qt, QPoint, QRect, QSize, QTimer,
    QPropertyAnimation, QEasingCurve,
    pyqtProperty, pyqtSignal,
    QPointF, QRectF
)
from PyQt6.QtGui import (
    QPainter, QColor, QPainterPath, QPen, QBrush,
    QPixmap, QFont, QFontMetrics, QLinearGradient,
    QRadialGradient, QImage
)

from plays import PLAYS, MAP_IMAGES, AGENT_COLORS, get_play

# ── Config ─────────────────────────────────────────────────
MAP_IMG_W     = 460
MAP_IMG_H     = 400
AGENT_TAG_R   = 18
PANEL_OFFSET_X = 36
PANEL_OFFSET_Y = 100
FADE_MS        = 250

ROUTE_COLORS = [
    QColor(230,  57,  70, 200),
    QColor(  6, 214, 160, 200),
    QColor(255, 183,   3, 200),
    QColor( 67,  97, 238, 200),
    QColor(155,  89, 182, 200),
]


# ── Draw helpers ───────────────────────────────────────────

def _draw_agent_circle(p, cx, cy, r, agent, role, color, index):
    # Glow
    glow = QRadialGradient(cx, cy, r + 8)
    gc = QColor(color); gc.setAlpha(55)
    glow.setColorAt(0, gc); glow.setColorAt(1, QColor(0,0,0,0))
    p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(cx - r - 8, cy - r - 8, (r+8)*2, (r+8)*2)

    # Circle clip
    clip = QPainterPath()
    clip.addEllipse(cx - r + 2, cy - r + 2, (r-2)*2, (r-2)*2)

    # Agent logo or fallback
    logo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'assets', 'agents', f"{agent.lower().replace('/','')}.png")
    if os.path.exists(logo):
        px = QPixmap(logo).scaled((r-2)*2, (r-2)*2,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        p.setClipPath(clip)
        p.drawPixmap(cx-r+2, cy-r+2, px)
        p.setClipping(False)
    else:
        p.setClipPath(clip)
        p.fillPath(clip, QColor(12,16,22,240))
        p.setClipping(False)
        p.setPen(color)
        f = QFont("Segoe UI", 8); f.setBold(True); p.setFont(f)
        p.drawText(QRect(cx-r, cy-r, r*2, r*2), Qt.AlignmentFlag.AlignCenter, agent[:2].upper())

    # Ring
    p.setPen(QPen(color, 2.5))
    p.drawEllipse(cx-r+1, cy-r+1, (r-1)*2, (r-1)*2)

    # Index badge
    bx, by = cx+r-8, cy-r+2
    bpath = QPainterPath(); bpath.addEllipse(bx, by, 13, 13)
    p.fillPath(bpath, color)
    p.setPen(QColor(0,0,0,220))
    f2 = QFont("Courier New", 7); f2.setBold(True); p.setFont(f2)
    p.drawText(QRect(bx, by, 13, 13), Qt.AlignmentFlag.AlignCenter, str(index+1))

    # Role label
    p.setPen(QColor(220, 225, 230, 200))
    f3 = QFont("Courier New", 7); p.setFont(f3)
    p.drawText(QRect(cx-30, cy+r+2, 60, 14), Qt.AlignmentFlag.AlignCenter, role.upper())


def _draw_route(p, waypoints, color, w, h):
    if len(waypoints) < 2:
        return
    pts = [QPointF(wx*w, wy*h) for wx, wy in waypoints]
    pen = QPen(color, 2); pen.setStyle(Qt.PenStyle.DashLine)
    pen.setDashPattern([6, 4]); p.setPen(pen)
    for i in range(len(pts)-1):
        p.drawLine(pts[i], pts[i+1])
    # Arrow
    end = pts[-1]; start = pts[-2]
    dx = end.x()-start.x(); dy = end.y()-start.y()
    angle = math.atan2(dy, dx)
    alen = 10
    p1 = QPointF(end.x()+alen*math.cos(angle+math.radians(145)),
                 end.y()+alen*math.sin(angle+math.radians(145)))
    p2 = QPointF(end.x()+alen*math.cos(angle-math.radians(145)),
                 end.y()+alen*math.sin(angle-math.radians(145)))
    arrow = QPainterPath()
    arrow.moveTo(end); arrow.lineTo(p1); arrow.lineTo(p2); arrow.closeSubpath()
    p.setBrush(QBrush(color)); p.setPen(Qt.PenStyle.NoPen)
    p.drawPath(arrow)


# ── Map canvas ────────────────────────────────────────────

class MapCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(MAP_IMG_W, MAP_IMG_H)
        self._map_px   = None
        self._play     = None

    def load(self, map_name, play_data):
        img = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'assets', 'maps', f"{map_name.lower()}.svg")
        if os.path.exists(img):
            self._map_px = QPixmap(img).scaled(MAP_IMG_W, MAP_IMG_H,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        else:
            self._map_px = None
        self._play = play_data
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._map_px:
            p.drawPixmap(0, 0, self._map_px)
            p.fillRect(0, 0, w, h, QColor(0,0,0,60))
        else:
            p.fillRect(0, 0, w, h, QColor(10,14,18))
            p.setPen(QPen(QColor(255,255,255,14)))
            for x in range(0, w, 40): p.drawLine(x,0,x,h)
            for y in range(0, h, 40): p.drawLine(0,y,w,y)
            p.setPen(QColor(255,255,255,50))
            f = QFont("Segoe UI", 10); p.setFont(f)
            p.drawText(QRect(0,0,w,h), Qt.AlignmentFlag.AlignCenter,
                       "Place map PNG in\nassets/maps/")

        if not self._play:
            return

        agents = self._play.get("agents", [])
        for i, ag in enumerate(agents):
            path = ag.get("path")
            if path:
                _draw_route(p, path, ROUTE_COLORS[i % len(ROUTE_COLORS)], w, h)
        for i, ag in enumerate(agents):
            ax = int(ag["pos"][0]*w); ay = int(ag["pos"][1]*h)
            color = QColor(AGENT_COLORS.get(ag["agent"], "#E63946"))
            _draw_agent_circle(p, ax, ay, AGENT_TAG_R,
                               ag["agent"], ag.get("role",""), color, i)


# ── Legend ────────────────────────────────────────────────

class Legend(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []

    def load(self, agents):
        self._entries = agents
        self.setFixedHeight(max(40, len(agents)*22+16))
        self.update()

    def paintEvent(self, _):
        if not self._entries: return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 6, 6)
        p.fillPath(path, QColor(8,12,17,200))
        p.setPen(QPen(QColor(255,255,255,14)))
        p.drawPath(path)
        y = 10
        for i, ag in enumerate(self._entries):
            color = QColor(AGENT_COLORS.get(ag["agent"], "#E63946"))
            dot = QPainterPath(); dot.addEllipse(10, y+3, 10, 10)
            p.fillPath(dot, color)
            p.setPen(color)
            f = QFont("Courier New", 8); f.setBold(True); p.setFont(f)
            p.drawText(QRect(10,y,10,16), Qt.AlignmentFlag.AlignCenter, str(i+1))
            p.setPen(QColor(220,225,230,220))
            f2 = QFont("Segoe UI", 9); f2.setBold(True); p.setFont(f2)
            label = f"{ag['agent']}  ·  {ag.get('role','')}"
            p.drawText(26, y+13, label)
            p.setPen(QColor(120,135,145,180))
            f3 = QFont("Segoe UI", 8); p.setFont(f3)
            note_x = 26 + QFontMetrics(f2).horizontalAdvance(label) + 6
            p.drawText(note_x, y+13, ag.get("note",""))
            y += 22


# ── Panel window ──────────────────────────────────────────

class MinimapPanel(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        # Solid dark background — no WA_TranslucentBackground conflict
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(MAP_IMG_W + 28)

        self._drag_pos = None
        self._anim     = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        self._title = QLabel("MAP — PLAY")
        self._title.setStyleSheet("color:#E63946;font-family:'Segoe UI';font-size:11px;"
                                  "font-weight:700;letter-spacing:2px;background:transparent;")
        self._desc = QLabel("")
        self._desc.setStyleSheet("color:#7B8896;font-family:'Courier New';font-size:9px;"
                                 "background:transparent;")
        self._desc.setWordWrap(True)

        close = QPushButton("✕")
        close.setFixedSize(22, 22)
        close.setStyleSheet("QPushButton{background:rgba(255,255,255,0.06);"
                            "border:1px solid rgba(255,255,255,0.1);border-radius:11px;"
                            "color:#7B8896;font-size:11px;}"
                            "QPushButton:hover{background:rgba(230,57,70,0.2);color:#E63946;}")
        close.clicked.connect(self.hide)

        hdr.addWidget(self._title); hdr.addStretch(); hdr.addWidget(close)

        self._canvas = MapCanvas()
        self._legend = Legend()
        self._legend.setFixedWidth(MAP_IMG_W)

        root.addLayout(hdr)
        root.addWidget(self._desc)
        root.addWidget(self._canvas)
        root.addWidget(self._legend)

    def load_and_show(self, map_name, play_name, play_data):
        self._title.setText(f"{map_name.upper()}  ·  {play_name.upper()}")
        self._desc.setText(play_data.get("description", ""))
        self._canvas.load(map_name, play_data)
        self._legend.load(play_data.get("agents", []))
        self.adjustSize()
        self._fade_in()

    def _fade_in(self):
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        a = QPropertyAnimation(self, b"windowOpacity")
        a.setDuration(FADE_MS)
        a.setStartValue(0.0); a.setEndValue(0.95)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start()
        self._anim = a

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        p.fillPath(path, QColor(8, 12, 17, 240))
        # Top accent
        p.setPen(QPen(QColor(230, 57, 70, 200), 1.5))
        p.drawLine(14, 0, self.width()-14, 0)
        # Border
        p.setPen(QPen(QColor(255,255,255,14), 1))
        p.drawPath(path)

    # Drag
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.pos()
    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
    def mouseReleaseEvent(self, _):
        self._drag_pos = None


# ── Public controller ─────────────────────────────────────

class MinimapOverlay(QObject):
    _show_sig = pyqtSignal(str, str)
    _hide_sig = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._panel = MinimapPanel()
        self._show_sig.connect(self._do_show)
        self._hide_sig.connect(self._panel.hide)
        self._place()

    def _place(self):
        sw = QApplication.primaryScreen().geometry().width()
        self._panel.move(sw - self._panel.width() - PANEL_OFFSET_X, PANEL_OFFSET_Y)

    def show_play(self, map_name: str, play_name: str):
        """Thread-safe. Call from LLM pipeline."""
        self._show_sig.emit(map_name, play_name)

    def hide_map(self):
        """Thread-safe."""
        self._hide_sig.emit()

    def _do_show(self, map_name: str, play_name: str):
        play = get_play(map_name, play_name)
        if not play:
            print(f"[minimap] not found: {map_name} / {play_name}")
            return
        self._panel.load_and_show(map_name, play_name, play)
        self._place()