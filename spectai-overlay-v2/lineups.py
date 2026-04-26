import json
import urllib.request
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QApplication
)
from PyQt6.QtCore import (
    QObject, Qt, QPropertyAnimation,
    QEasingCurve, pyqtSignal, QThread, pyqtSlot
)
from PyQt6.QtGui import (
    QPainter, QColor, QPainterPath, QPen,
    QPixmap, QImage
)

BASE = Path(__file__).parent
JSON_PATH = BASE / "lineups_data.json"

_DB: list[dict] = []

def _clean(value) -> str:
    return str(value or "").strip().lower()

def _load():
    global _DB
    if not JSON_PATH.exists():
        print("[lineups] lineups_data.json not found — run scrape_lineups.py")
        _DB = []
        return
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            _DB = []
            return
        _DB = [item for item in data if isinstance(item, dict)]
    except Exception as e:
        print(f"[lineups] Load error: {e}")
        _DB = []

_load()

def query(map_name: str, agent: str, position: str, max_results: int = 4) -> list[dict]:
    map_q = _clean(map_name)
    agent_q = _clean(agent)
    pos_q = _clean(position)
    scored = []

    for lu in _DB:
        if _clean(lu.get("map")) != map_q: continue
        if _clean(lu.get("agent")) != agent_q: continue

        from_l = _clean(lu.get("from"))
        to_l = _clean(lu.get("to"))
        title_l = _clean(lu.get("title"))
        score = 0

        if pos_q:
            if pos_q in from_l: score += 10
            if pos_q in to_l: score += 8
            if pos_q in title_l: score += 4

        for word in pos_q.split():
            if len(word) < 2: continue
            if word in from_l: score += 3
            if word in to_l: score += 2
            if word in title_l: score += 1

        if score > 0:
            scored.append((score, lu))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [lu for _, lu in scored[:max_results]]

def get_all_for(map_name: str, agent: str, max_results: int = 4) -> list[dict]:
    map_q = _clean(map_name)
    agent_q = _clean(agent)
    return [lu for lu in _DB if _clean(lu.get("map")) == map_q and _clean(lu.get("agent")) == agent_q][:max_results]


class ImageLoader(QThread):
    loaded = pyqtSignal(str, int, QPixmap) 

    def __init__(self, lineup_id: str, lu_data: dict):
        super().__init__()
        self.lineup_id = lineup_id
        self.lu_data = lu_data

    def run(self):
        all_images = self.lu_data.get("all_images", [])
        if all_images:
            for i, img_path in enumerate(all_images):
                local = BASE / img_path
                if local.exists():
                    px = QPixmap(str(local))
                    if not px.isNull():
                        self.loaded.emit(self.lineup_id, i, px)
            return

        px = None
        img_local = self.lu_data.get("img_local", "")
        if img_local:
            local = BASE / img_local
            if local.exists(): px = QPixmap(str(local))

        if (not px or px.isNull()) and self.lu_data.get("img_url"):
            try:
                req = urllib.request.Request(self.lu_data["img_url"], headers={"User-Agent": "Mozilla/5.0 Chrome/120.0"})
                with urllib.request.urlopen(req, timeout=8) as response:
                    img = QImage.fromData(response.read())
                    if not img.isNull(): px = QPixmap.fromImage(img)
            except Exception: pass

        if px and not px.isNull():
            self.loaded.emit(self.lineup_id, 0, px)


class LineupCard(QWidget):
    IMG_W, IMG_H = 256, 144

    def __init__(self, lu: dict, parent=None):
        super().__init__(parent)
        self._lu = lu
        self._loader = None
        all_imgs = self._lu.get("all_images", [])
        self.images_count = max(1, len(all_imgs))
        self.current_idx = 0
        self.pixmaps = {} 

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(280)
        self._build()
        self._load_images()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 12)
        root.setSpacing(7)

        ability = self._lu.get("ability", "")
        if ability:
            ab = QLabel(str(ability).upper())
            ab.setStyleSheet("color:#E63946; font-family:'Courier New'; font-size:9px; letter-spacing:2px;")
            root.addWidget(ab)

        self.img_container = QWidget()
        self.img_container.setFixedSize(self.IMG_W, self.IMG_H)

        self._img = QLabel(self.img_container)
        self._img.setFixedSize(self.IMG_W, self.IMG_H)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setStyleSheet("background:#0A0D10; border-radius:5px; color:#2A3038; font-size:10px;")
        self._img.setText("Loading...")

        btn_style = "QPushButton { background:rgba(0,0,0,160); color:white; border-radius:12px; font-weight:bold; } QPushButton:hover { background:rgba(230,57,70,200); }"
        
        self.btn_prev = QPushButton("◀", self.img_container)
        self.btn_prev.setFixedSize(24, 24)
        self.btn_prev.move(4, self.IMG_H // 2 - 12)
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_prev.clicked.connect(self.prev_image)

        self.btn_next = QPushButton("▶", self.img_container)
        self.btn_next.setFixedSize(24, 24)
        self.btn_next.move(self.IMG_W - 28, self.IMG_H // 2 - 12)
        self.btn_next.setStyleSheet(btn_style)
        self.btn_next.clicked.connect(self.next_image)

        self.lbl_counter = QLabel("1/1", self.img_container)
        self.lbl_counter.setFixedSize(40, 20)
        self.lbl_counter.move(self.IMG_W - 44, 4)
        self.lbl_counter.setStyleSheet("background:rgba(0,0,0,160); color:white; border-radius:4px; font-size:10px; qproperty-alignment: AlignCenter;")

        if self.images_count <= 1:
            self.btn_prev.hide()
            self.btn_next.hide()
            self.lbl_counter.hide()

        root.addWidget(self.img_container)

        title = QLabel(str(self._lu.get("title", "")))
        title.setWordWrap(True)
        title.setStyleSheet("color:#EDF0F3; font-family:'Segoe UI'; font-size:12px; font-weight:600;")
        root.addWidget(title)

        from_l, to_l = str(self._lu.get("from", "")), str(self._lu.get("to", ""))
        if from_l or to_l:
            route = QLabel(f"{from_l}  →  {to_l}" if to_l else from_l)
            route.setWordWrap(True)
            route.setStyleSheet("color:#7B8896; font-family:'Courier New'; font-size:10px;")
            root.addWidget(route)

    def _load_images(self):
        self._loader = ImageLoader(str(self._lu.get("id", "")), self._lu)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.finished.connect(self._loader.deleteLater)
        self._loader.start()

    @pyqtSlot(str, int, QPixmap)
    def _on_loaded(self, _id: str, idx: int, px: QPixmap):
        scaled = px.scaled(self.IMG_W, self.IMG_H, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.pixmaps[idx] = scaled
        if idx == self.current_idx:
            self.update_display()

    def prev_image(self):
        if self.images_count > 1:
            self.current_idx = (self.current_idx - 1) % self.images_count
            self.update_display()

    def next_image(self):
        if self.images_count > 1:
            self.current_idx = (self.current_idx + 1) % self.images_count
            self.update_display()

    def update_display(self):
        self.lbl_counter.setText(f"{self.current_idx + 1}/{self.images_count}")
        if self.current_idx in self.pixmaps:
            self._img.setPixmap(self.pixmaps[self.current_idx])
            self._img.setText("")
        else:
            self._img.clear()
            self._img.setText("Loading...")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        p.fillPath(path, QColor(10, 14, 18, 225))
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.drawPath(path)

class LineupPanel(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._drag_pos = None
        self.setFixedWidth(308)
        self._build()
        self.hide()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        hdr = QHBoxLayout()
        self._title = QLabel("LINEUPS")
        self._title.setStyleSheet("color:#E63946; font-size:11px; font-weight:700; letter-spacing:2px;")
        
        self._sub = QLabel("")
        self._sub.setStyleSheet("color:#7B8896; font-family:'Courier New'; font-size:9px;")
        self._sub.setWordWrap(True)

        close = QPushButton("✕")
        close.setFixedSize(22, 22)
        close.setStyleSheet("QPushButton{background:rgba(255,255,255,0.06); border-radius:11px; color:#7B8896;} QPushButton:hover{background:rgba(230,57,70,0.2); color:#E63946;}")
        close.clicked.connect(self.hide)

        hdr.addWidget(self._title)
        hdr.addStretch()
        hdr.addWidget(close)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollBar:vertical{background:#0A0D10;width:4px;border-radius:2px;} QScrollBar::handle:vertical{background:#3A4852;border-radius:2px;}")

        self._cards_w = QWidget()
        self._cards_w.setStyleSheet("background:transparent;")
        self._cards_l = QVBoxLayout(self._cards_w)
        self._cards_l.setSpacing(8)
        self._cards_l.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._cards_w)

        root.addLayout(hdr)
        root.addWidget(self._sub)
        root.addWidget(scroll)

    def load(self, lineups: list[dict], agent: str, position: str):
        while self._cards_l.count():
            item = self._cards_l.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if not lineups:
            empty = QLabel(f"No lineups found\n{agent} · {position}")
            empty.setStyleSheet("color:#3A4852; font-size:12px; padding:20px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._cards_l.addWidget(empty)
        else:
            for lu in lineups: self._cards_l.addWidget(LineupCard(lu))
            self._cards_l.addStretch()

        self._title.setText(f"{agent.upper()}  ·  LINEUPS")
        self._sub.setText(f"Position: {position}  ·  {len(lineups)} result{'s' if len(lineups) != 1 else ''}")

        self.adjustSize()
        self.setFixedHeight(min(600, max(200, self.sizeHint().height())))
        self._fade_in()

    def cycle_images(self, forward=True):
        for i in range(self._cards_l.count()):
            widget = self._cards_l.itemAt(i).widget()
            if isinstance(widget, LineupCard):
                if forward: widget.next_image()
                else: widget.prev_image()

    def _fade_in(self):
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        a = QPropertyAnimation(self, b"windowOpacity")
        a.setDuration(250)
        a.setStartValue(0.0)
        a.setEndValue(0.95)
        a.start()
        self._anim = a

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        p.fillPath(path, QColor(8, 12, 17, 245))
        p.setPen(QPen(QColor(230, 57, 70, 200), 1.5))
        p.drawLine(14, 0, self.width() - 14, 0)
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        p.drawPath(path)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None

class LineupOverlay(QObject):
    _show_sig = pyqtSignal(str, str, str)
    _hide_sig = pyqtSignal()
    _cycle_sig = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._panel = LineupPanel()
        self._show_sig.connect(self._do_show)
        self._hide_sig.connect(self._panel.hide)
        self._cycle_sig.connect(self._panel.cycle_images)
        self._place()

    def _place(self):
        screen = QApplication.primaryScreen()
        if screen:
            self._panel.move(screen.geometry().width() - self._panel.width() - 36, 100)

    def show(self, map_name: str, agent: str, position: str):
        self._show_sig.emit(map_name, agent, position)

    def hide(self):
        self._hide_sig.emit()

    def next_image(self):
        self._cycle_sig.emit(True)

    def prev_image(self):
        self._cycle_sig.emit(False)

    def _do_show(self, map_name: str, agent: str, position: str):
        results = query(map_name, agent, position)
        if not results: results = get_all_for(map_name, agent)
        self._panel.load(results, agent, position)
        self._place()