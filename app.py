"""Channel Soundboard - desktop version. Every channel can play to a different output device at the same time."""
import ctypes, json, os, random, sys, threading, time
from datetime import datetime, timedelta
import soundfile as sf
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRectF, QTime
from PySide6.QtGui import QPainter, QColor, QIcon, QFont, QAction, QLinearGradient, QPen
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                               QSlider, QScrollArea, QFrame, QMenu, QComboBox, QFileDialog, QMessageBox,
                               QDialog, QTimeEdit, QToolButton, QCheckBox, QTabWidget, QTextBrowser, QLineEdit)
import engine
from engine import Chan, Master, Fx, Cfg, ClipPlayer, fmt

APP = "Channel Soundboard"
DATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), "ChannelSoundboard")
LIB = os.path.join(DATA, "library.json")
CSS = """
QMainWindow,QWidget#root{background:#13151a} QLabel{color:#e6e8ee}
QFrame#left{background:#1c1f26} QFrame#strip{background:#2a2e37;border-radius:14px}
QFrame#strip[on="true"]{border:2px solid #f2b53d}
QPushButton,QToolButton,QComboBox{background:#13151a;color:#e6e8ee;border:1px solid #343843;border-radius:13px;padding:4px 8px}
QPushButton:hover,QToolButton:hover{border-color:#f2b53d} QPushButton:checked,QToolButton:checked{background:#f2b53d;color:#1b1300}
QPushButton#play{border-radius:23px;font-size:18px;background:#13151a} QPushButton#play[on="true"]{background:#f2b53d;color:#1b1300}
QPushButton#main{border-radius:23px;font-size:18px;background:#f2b53d;color:#1b1300;border:0}
QSlider::groove:vertical{width:6px;background:#13151a;border-radius:3px} QSlider::sub-page:vertical{background:#13151a}
QSlider::add-page:vertical{background:#f2b53d;border-radius:3px} QSlider::handle:vertical{background:#e6e8ee;height:18px;margin:0 -14px;border-radius:6px}
QSlider::groove:horizontal{height:6px;background:#13151a;border-radius:3px} QSlider::sub-page:horizontal{background:#f2b53d;border-radius:3px}
QSlider::handle:horizontal{background:#e6e8ee;width:16px;margin:-6px 0;border-radius:8px}
QPushButton#mini{padding:3px 4px;border-radius:10px;font-size:11px} QPushButton#mini:disabled{color:#555a66}
QDialog,QMessageBox{background:#1c1f26} QCheckBox{color:#e6e8ee}
QTabWidget::pane{border:1px solid #343843} QTabBar::tab{background:#13151a;color:#e6e8ee;padding:6px 12px;border-radius:6px} QTabBar::tab:selected{background:#f2b53d;color:#1b1300}
QTextBrowser{background:#13151a;color:#e6e8ee;border:0}
QLineEdit{background:#13151a;color:#e6e8ee;border:1px solid #343843;border-radius:6px;padding:3px}
QPushButton#page{border-radius:14px;padding:4px 14px} QPushButton#page:checked{background:#f2b53d;color:#1b1300}
QTimeEdit{background:#13151a;color:#e6e8ee;border:1px solid #343843;border-radius:6px;padding:3px}
QScrollArea{border:0;background:transparent} QMenu{background:#1c1f26;color:#e6e8ee;border:1px solid #343843} QMenu::item:selected{background:#f2b53d;color:#1b1300}
"""

VERSION, AUTHOR = "11", "Balram Sevak"
DARK = dict(bg="#13151a", surface="#1c1f26", strip="#2a2e37", border="#343843", text="#e6e8ee", accent="#f2b53d", on="#1b1300", muted="#9aa0ad")
THEMES = {
    "Dark": DARK,
    "Light": dict(bg="#e8eef3", surface="#ffffff", strip="#d3dde7", border="#c9d4de", text="#14212e", accent="#0a6c8f", on="#ffffff", muted="#5a6b7b"),
    "Blue": dict(bg="#0b1a2b", surface="#112640", strip="#1b3a5c", border="#2b4c75", text="#e8f1fb", accent="#4cc9f0", on="#00212b", muted="#8fb0d0"),
    "Green": dict(bg="#0f1a14", surface="#15261c", strip="#1f3a2a", border="#2c5039", text="#e7f5ec", accent="#4ade80", on="#04210f", muted="#8fb89e"),
}
PAL = dict(DARK)


def T(css):
    """Map the default (dark) colours in a style string to the current theme."""
    for i, k in enumerate(DARK): css = css.replace(DARK[k], f"@{i}@")
    for i, k in enumerate(DARK): css = css.replace(f"@{i}@", PAL[k])
    return css


def set_theme(name):
    PAL.clear(); PAL.update(THEMES.get(name, DARK))
    QApplication.instance().setStyleSheet(T(CSS))


def _a(c, a):
    q = QColor(c); q.setAlpha(a); return q


ABOUT_HTML = """<h2>Channel Soundboard v{v}</h2><p><b>Creator: {a}</b></p>
<h3>About</h3><p>A free, offline soundboard mixer. Every song is a channel with its own fader, mute and play button, and every channel can play to a different output device at the same time.</p>
<h3>Features</h3><ul><li>Pages with their own song lists, timers and a Duplicate button</li><li>Clips: dialogue sounds that play at set times of a song, even when it is muted</li><li>Crossfade or gapless Continue, song numbers with running totals</li><li>Unlimited channels, per-channel volume, mute and output device</li><li>DJ pre-listen: hear a song in the headset, then send it to the Main output</li><li>Multiplay, crossfade, shuffle, repeat, continue</li><li>Equalizer presets and bass boost</li><li>Timer and per-song start/stop times</li><li>Waveform seek bar with elapsed and remaining time</li></ul>
<h3>How to play</h3><ol><li>Click <b>+ Add song</b> (or drag audio files into the window).</li><li>Press the round play button of a channel.</li><li>Use the fader for volume; the speaker button mutes only that song.</li><li>Pick Stop, Repeat or Continue for what happens when a song ends.</li><li>Choose your Main and Headset outputs on the left panel. Press the headphone button on a channel to pre-listen, then send it to Main.</li></ol>
<h3>Why it is useful</h3><p>Prepare the next song in the headset while the party continues on the speakers, run a programme with timers, and play many sounds together, all without internet.</p>
<h3>Other</h3><ul><li>Songs are referenced by file location. The list and settings are saved in %APPDATA%\\ChannelSoundboard.</li><li>Space = play/pause all. Click rewind/forward = 10 s, hold = fast scrub.</li><li>MP3, WAV, FLAC, OGG and OPUS files are supported.</li></ul>"""


class Wave(QWidget):
    seek = Signal(float)

    def __init__(s):
        super().__init__()
        s.setMinimumHeight(72); s.peaks, s.frac, s.left, s.right = [], 0.0, "0:00", "-0:00"

    def paintEvent(s, e):
        p = QPainter(s); p.setRenderHint(QPainter.Antialiasing)
        w, h = s.width(), s.height(); p.fillRect(s.rect(), QColor(PAL["surface"]))
        n = len(s.peaks)
        for i in range(n):
            bh = max(2.0, s.peaks[i] * h * 0.8)
            p.fillRect(QRectF(i * w / n, (h - bh) / 2, max(1.0, w / n - 1), bh), QColor(PAL["accent"] if i / n < s.frac else PAL["border"]))
        if not n:
            p.fillRect(QRectF(0, h / 2 - 1, w, 2), QColor(PAL["border"])); p.fillRect(QRectF(0, h / 2 - 1, w * s.frac, 2), QColor(PAL["accent"]))
        p.fillRect(QRectF(max(0, s.frac * w - 1), 0, 2, h), QColor(PAL["accent"]))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        for txt, x in ((s.left, 6), (s.right, w - 6 - p.fontMetrics().horizontalAdvance(s.right) - 10)):
            p.fillRect(QRectF(x - 4, 3, p.fontMetrics().horizontalAdvance(txt) + 8, 18), _a(PAL["surface"], 220))
            p.setPen(QColor(PAL["text"])); p.drawText(x, 16, txt)

    def mousePressEvent(s, e): s.seek.emit(max(0.0, min(1.0, e.position().x() / max(1, s.width()))))
    def mouseMoveEvent(s, e): s.mousePressEvent(e)


class ConsoleFader(QWidget):
    """Standing mixer fader: dark panel, scale marks on both sides, metal knob (same interface as a QSlider)."""
    valueChanged = Signal(int)
    sliderReleased = Signal()
    PAD = 14

    def __init__(s):
        super().__init__(); s.v = 100; s.setFixedSize(76, 176); s.setCursor(Qt.PointingHandCursor)

    def setRange(s, a, b): pass
    def value(s): return s.v

    def setValue(s, x):
        x = max(0, min(100, int(x)))
        if x != s.v: s.v = x; s.update(); s.valueChanged.emit(x)

    def _y(s, e): return 1 - (e.position().y() - s.PAD) / max(1, s.height() - 2 * s.PAD)

    def mousePressEvent(s, e): s.setValue(round(max(0, min(1, s._y(e))) * 100))
    def mouseMoveEvent(s, e): s.mousePressEvent(e)
    def mouseReleaseEvent(s, e): s.sliderReleased.emit()
    def wheelEvent(s, e): s.setValue(s.v + (2 if e.angleDelta().y() > 0 else -2)); s.sliderReleased.emit()

    def paintEvent(s, e):
        p = QPainter(s); p.setRenderHint(QPainter.Antialiasing)
        w, hh, P = s.width(), s.height(), s.PAD
        g = QLinearGradient(0, 0, 0, hh); g.setColorAt(0, QColor("#262626")); g.setColorAt(1, QColor("#151515"))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(0, 0, w, hh, 8, 8)
        p.setBrush(QColor("#000000")); p.drawRoundedRect(QRectF(w / 2 - 5, P, 10, hh - 2 * P), 5, 5)       # slot
        p.setPen(QPen(QColor("#cfcfcf"), 2))
        for i in range(11):                                                                              # scale marks
            y = P + i * (hh - 2 * P) / 10
            p.drawLine(6, int(y), 24, int(y)); p.drawLine(w - 24, int(y), w - 6, int(y))
        ky = P + (1 - s.v / 100) * (hh - 2 * P)                                                          # metal knob
        k = QRectF(w / 2 - 26, ky - 14, 52, 28)
        kg = QLinearGradient(0, k.top(), 0, k.bottom())
        for pos, col in ((0, "#f4f4f4"), (0.45, "#b9b9b9"), (0.55, "#7a7a7a"), (1, "#cacaca")): kg.setColorAt(pos, QColor(col))
        p.setPen(QPen(QColor("#2a2a2a"), 1)); p.setBrush(kg); p.drawRoundedRect(k, 5, 5)
        p.setPen(QPen(QColor("#2b2b2b"), 2)); p.drawLine(int(k.left() + 9), int(ky), int(k.right() - 9), int(ky))


class Hold(QToolButton):
    """Click = jump 10 s, hold = fast scrub."""
    def __init__(s, text, step, fn):
        super().__init__(); s.setText(text); s.step, s.fn, s.held = step, fn, False
        s.t = QTimer(s); s.t.setInterval(120); s.t.timeout.connect(lambda: s.fn(s.step * 0.4))
        s.d = QTimer(s); s.d.setSingleShot(True); s.d.timeout.connect(lambda: (setattr(s, "held", True), s.t.start()))
        s.pressed.connect(lambda: (setattr(s, "held", False), s.d.start(350)))
        s.released.connect(s.up)

    def up(s):
        s.d.stop(); s.t.stop()
        if not s.held: s.fn(s.step)


class Grip(QLabel):
    """Hold and drag to move the song left or right inside its page."""
    def __init__(s, strip):
        super().__init__("⠿ ⠿ ⠿"); s.strip = strip; s.drag = False; s.setAlignment(Qt.AlignCenter); s.setCursor(Qt.OpenHandCursor)
        s.setToolTip("Hold and drag to move this song"); s.setStyleSheet(T("color:#9aa0ad;font-size:13px;padding:2px"))
    def mousePressEvent(s, e): s.drag = True; s.setCursor(Qt.ClosedHandCursor)
    def mouseMoveEvent(s, e):
        if s.drag: s.strip.m.drag_strip(s.strip, int(e.globalPosition().x()))
    def mouseReleaseEvent(s, e): s.drag = False; s.setCursor(Qt.OpenHandCursor); s.strip.m.end_drag()


class VGrip(QLabel):
    """Hold and drag a clip row up or down."""
    def __init__(s, row, moved):
        super().__init__("⋮⋮"); s.row, s.moved, s.drag = row, moved, False; s.setCursor(Qt.OpenHandCursor); s.setToolTip("Hold and drag to move up or down")
        s.setStyleSheet(T("color:#9aa0ad;font-size:16px;padding:0 4px"))
    def mousePressEvent(s, e): s.drag = True
    def mouseMoveEvent(s, e):
        if not s.drag: return
        lay = s.row.parentWidget().layout(); y = int(s.mapTo(s.row.parentWidget(), e.position().toPoint()).y())
        rows = [lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget() is not None]
        idx = sum(1 for r in rows if r is not s.row and r.y() + r.height() / 2 < y)
        if rows.index(s.row) != idx: lay.insertWidget(idx, s.row)
    def mouseReleaseEvent(s, e): s.drag = False; s.moved()


class Bridge(QObject):
    peaks = Signal(object, list)


class Strip(QFrame):
    def __init__(s, ch, m):
        super().__init__(); s.ch, s.m = ch, m; s.setObjectName("strip"); s.setFixedWidth(112)
        v = QVBoxLayout(s); v.setContentsMargins(6, 8, 6, 8); v.setSpacing(6)
        s.nb = QLabel(); s.nb.setAlignment(Qt.AlignCenter); s.nb.setStyleSheet(T("color:#f2b53d;font-weight:bold;font-size:11px")); v.addWidget(s.nb)
        s.dev = QPushButton(); s.dev.clicked.connect(lambda: m.dev_menu(ch, s.dev)); v.addWidget(s.dev)
        s.mute = QPushButton(); s.mute.setCheckable(True); s.mute.setChecked(ch.mute); s.mute.toggled.connect(s.setm); v.addWidget(s.mute); s.setm(ch.mute, False)
        cr = QHBoxLayout(); cr.setSpacing(4)
        s.cue = QPushButton("🎧"); s.cue.setObjectName("mini"); s.cue.setCheckable(True); s.cue.setToolTip("Pre-listen in the headset"); s.cue.clicked.connect(lambda: m.toggle_cue(ch))
        s.send = QPushButton("⇒ Main"); s.send.setObjectName("mini"); s.send.setToolTip("Send to the main output from this point"); s.send.clicked.connect(lambda: m.send_main(ch))
        cr.addWidget(s.cue); cr.addWidget(s.send); v.addLayout(cr)
        s.play = QPushButton("▶"); s.play.setObjectName("play"); s.play.setFixedSize(46, 46); s.play.clicked.connect(lambda: m.toggle(ch))
        v.addWidget(s.play, 0, Qt.AlignHCenter); v.addSpacing(12)
        s.fad = QSlider(Qt.Vertical); s.fad.setRange(0, 100); s.fad.setValue(int(ch.vol * 100)); s.fad.valueChanged.connect(s.setv)
        s.fad.sliderReleased.connect(m.save); v.addWidget(s.fad, 1, Qt.AlignHCenter)
        s.pc = QLabel(); s.pc.setAlignment(Qt.AlignCenter); v.addWidget(s.pc)
        s.clb = QPushButton(); s.clb.setObjectName("mini"); s.clb.clicked.connect(lambda: m.clips_dialog(ch)); v.addWidget(s.clb)
        s.nm = QPushButton(); s.nm.clicked.connect(lambda: m.name_menu(ch, s.nm)); v.addWidget(s.nm)
        s.du = QLabel(fmt(ch.dur)); s.du.setAlignment(Qt.AlignCenter); s.du.setStyleSheet(T("color:#9aa0ad;font-size:10px")); v.addWidget(s.du)
        s.grip = Grip(s); v.addWidget(s.grip)
        s.refresh()

    def setm(s, x, save=True):
        s.ch.mute = bool(x); s.mute.setText("🔇 Muted" if x else "🔊 Mute")
        if save: s.m.save()

    def setv(s, x): s.ch.vol = x / 100; s.pc.setText(f"{x}%")

    def refresh(s):
        c = s.ch; s.pc.setText(f"{int(c.vol * 100)}%")
        s.dev.setText("🔈 " + ((c.dev[:11] + "…") if c.dev and len(c.dev) > 12 else (c.dev or "Main"))); s.dev.setToolTip(c.dev or "Follows the Main output")
        s.nm.setText(s.fontMetrics().elidedText(("⏰ " if (c.start_at or c.stop_at or c.only) else "") + c.name, Qt.ElideRight, 80)); s.nm.setToolTip(c.name)
        s.clb.setText("🎙 Clips" + (f" ({len(c.clips)})" if c.clips else "") + (" ✓" if c.clips_on else ""))
        for w, on in ((s, c.playing), (s.play, c.playing)):
            w.setProperty("on", on); w.style().unpolish(w); w.style().polish(w)
        s.play.setText("⏸" if c.playing else "▶")
        s.cue.setChecked(bool(c.cue and c.cue.playing)); s.send.setEnabled(c.cue is not None)


class Main(QMainWindow):
    def __init__(s):
        super().__init__(); s.setWindowTitle(f"{APP} v{VERSION} - {AUTHOR}"); s.resize(1120, 660); s.setAcceptDrops(True)
        s.chs, s.cur, s.mode, s.multi, s.shuf, s.stop_at, s.held, s.strips = [], None, 2, False, False, None, [], []
        s.pages = [{"id": 1, "name": "Page 1", "start": None, "stop": None}]; s.cur_pg = 1; s.pg_mode = 0
        s.round = set(); s.br = Bridge(); s.br.peaks.connect(s.got_peaks)
        root = QWidget(); root.setObjectName("root"); s.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        s.wave = Wave(); s.wave.seek.connect(s.seek_frac); v.addWidget(s.wave)
        h = QHBoxLayout(); h.setSpacing(0); v.addLayout(h, 1)
        # ---- left panel
        left = QFrame(); left.setObjectName("left"); left.setFixedWidth(250); h.addWidget(left)
        l = QVBoxLayout(left); l.setContentsMargins(12, 12, 12, 12); l.setSpacing(8)
        s.now = QLabel("Nothing playing"); s.now.setStyleSheet("font-weight:bold"); l.addWidget(s.now)
        tr = QHBoxLayout(); l.addLayout(tr)
        s.pp = QPushButton("▶"); s.pp.setObjectName("main"); s.pp.setFixedSize(46, 46); s.pp.clicked.connect(s.play_pause_all)
        for w in (QPushButton("⏮"), Hold("⏪", -10, s.seek_by), s.pp, Hold("⏩", 10, s.seek_by), QPushButton("⏭")):
            if isinstance(w, QPushButton) and w is not s.pp: w.setFixedSize(34, 34); w.clicked.connect(lambda _, a=w.text(): s.go(-1 if a == "⏮" else 1))
            if isinstance(w, Hold): w.setFixedSize(34, 34)
            tr.addWidget(w)
        g = QHBoxLayout(); l.addLayout(g)
        s.bm = QPushButton("Multiplay"); s.bm.setCheckable(True); s.bm.toggled.connect(s.set_multi)
        s.bs = QPushButton("Shuffle"); s.bs.setCheckable(True); s.bs.toggled.connect(lambda x: (setattr(s, "shuf", x), s.save()))
        g.addWidget(s.bm); g.addWidget(s.bs)
        s.endc = QComboBox(); s.endc.addItems(["⏹ Stop", "🔁 Repeat", "⏭ Continue"]); s.endc.setCurrentIndex(2); s.endc.currentIndexChanged.connect(lambda i: (setattr(s, "mode", i), s.save())); l.addWidget(s.endc)
        s.pmc = QComboBox(); s.pmc.addItems(["⏹ Stop page play", "⏭ Continue page play", "⧉ Multiple page play"]); s.pmc.currentIndexChanged.connect(lambda i: (setattr(s, "pg_mode", i), s.save())); l.addWidget(s.pmc)
        s.bmain = QPushButton(); s.bmain.clicked.connect(lambda: s.out_menu(False)); l.addWidget(s.bmain)
        s.bhead = QPushButton(); s.bhead.clicked.connect(lambda: s.out_menu(True)); l.addWidget(s.bhead)
        s.warn = QLabel(""); s.warn.setWordWrap(True); s.warn.setStyleSheet("color:#ff8a65;font-size:11px"); l.addWidget(s.warn)
        s.be = QPushButton("EQ / Bass boost"); s.be.clicked.connect(s.eq_dialog); l.addWidget(s.be)
        s.bset = QPushButton("⚙ Settings"); s.bset.clicked.connect(s.settings_dialog); l.addWidget(s.bset)
        r = QHBoxLayout(); l.addLayout(r); s.tot = QPushButton("⏱ 0:00 / 0:00"); s.tot.setFlat(True); s.tot.setStyleSheet(T("text-align:left;border:0;color:#9aa0ad;font-size:11px")); s.tot.setToolTip("Played / total. Click to reset the played time"); s.tot.clicked.connect(s.reset_played); r.addWidget(s.tot, 1)
        c = QPushButton("Clear"); c.clicked.connect(s.clear_all); r.addWidget(c)
        l.addStretch(1)
        fr = QHBoxLayout(); fr.setSpacing(18); l.addLayout(fr)
        def vcol(title, icon, setter):
            col = QVBoxLayout(); col.setSpacing(3)
            sl = ConsoleFader(); sl.setValue(100); sl.valueChanged.connect(setter); sl.sliderReleased.connect(s.save)
            ic = QLabel(icon); ic.setAlignment(Qt.AlignCenter); ic.setStyleSheet("font-size:18px")
            lb = QLabel("100%"); lb.setAlignment(Qt.AlignCenter); tt = QLabel(title); tt.setAlignment(Qt.AlignCenter); tt.setStyleSheet("font-size:11px")
            col.addWidget(sl, 0, Qt.AlignHCenter); col.addWidget(ic); col.addWidget(lb); col.addWidget(tt); fr.addLayout(col); return sl, lb
        s.mv, s.mp = vcol("Master", "🔊", s.set_master); s.hv, s.hp = vcol("Level", "🎧", s.set_cue_level)
        # ---- channels
        rt = QWidget(); rv = QVBoxLayout(rt); rv.setContentsMargins(0, 0, 0, 0); rv.setSpacing(0); h.addWidget(rt, 1)
        s.pgbar = QWidget(); s.pgl = QHBoxLayout(s.pgbar); s.pgl.setContentsMargins(10, 8, 10, 0); s.pgl.setSpacing(6); rv.addWidget(s.pgbar)
        s.area = QScrollArea(); s.area.setWidgetResizable(True); rv.addWidget(s.area, 1)
        s.load(); set_theme(s.theme); s.rebuild(); s.upd_out()
        t = QTimer(s); t.timeout.connect(s.tick); t.start(100)

    # ---- library
    def save(s):
        try:
            os.makedirs(DATA, exist_ok=True)
            json.dump({"mode": s.mode, "multi": s.multi, "shuf": s.shuf, "master": Master.v, "xf": Cfg.xf, "duck": Cfg.duck, "pg_mode": s.pg_mode, "cur_pg": s.cur_pg,
                       "pages": [{"id": p["id"], "name": p["name"], "start": p["start"].isoformat() if p["start"] else None, "stop": p["stop"].isoformat() if p["stop"] else None} for p in s.pages], "eq": Fx.gains, "bass": Fx.bass, "fade": Cfg.fade, "theme": s.theme, "main_dev": Master.main_dev, "cue_dev": Master.cue_dev, "cue_level": Master.cue,
                       "songs": [{"path": c.path, "name": c.name, "dur": c.dur, "vol": c.vol, "dev": c.dev, "mute": c.mute, "pg": c.pg, "only": c.only, "clips_on": c.clips_on, "clips": [{"path": k["path"], "name": k["name"], "at": k["at"]} for k in c.clips],
                                   "start": c.start_at.isoformat() if c.start_at else None, "stop": c.stop_at.isoformat() if c.stop_at else None} for c in s.chs]},
                      open(LIB, "w", encoding="utf8"), ensure_ascii=False)
        except Exception: pass

    def load(s):
        try:
            d = json.load(open(LIB, encoding="utf8"))
        except Exception:
            return
        s.chs = []
        for x in d.get("songs", []):
            if os.path.exists(x["path"]):
                c = Chan(x["path"], x.get("name"), x.get("dur", 0), x.get("vol", 1.0), x.get("dev")); c.mute = x.get("mute", False); c.pg = x.get("pg", 1); c.only = x.get("only", False); c.clips_on = x.get("clips_on", False)
                c.clips = [{"path": k["path"], "name": k.get("name", "clip"), "at": k.get("at", 0), "pd": False} for k in x.get("clips", []) if os.path.exists(k["path"])]
                try:
                    c.start_at = datetime.fromisoformat(x["start"]) if x.get("start") else None
                    c.stop_at = datetime.fromisoformat(x["stop"]) if x.get("stop") else None
                except Exception: pass
                s.chs.append(c)
        s.mode, s.multi, s.shuf = d.get("mode", 2), d.get("multi", False), d.get("shuf", False)
        Master.v = d.get("master", 1.0); Cfg.xf, Cfg.duck = d.get("xf", 3.0), d.get("duck", 0.35)
        try:
            ps = [{"id": p["id"], "name": p["name"], "start": datetime.fromisoformat(p["start"]) if p.get("start") else None,
                   "stop": datetime.fromisoformat(p["stop"]) if p.get("stop") else None} for p in d.get("pages", [])]
            if ps: s.pages = ps
        except Exception: pass
        ids = [p["id"] for p in s.pages]; s.cur_pg = d.get("cur_pg", ids[0]); s.cur_pg = s.cur_pg if s.cur_pg in ids else ids[0]
        s.pg_mode = d.get("pg_mode", 0); s.pmc.setCurrentIndex(s.pg_mode)
        for c in s.chs:
            if c.pg not in ids: c.pg = ids[0]
        Fx.gains, Fx.bass = d.get("eq", [0] * 5), d.get("bass", 0.0); Fx.ver += 1
        Master.main_dev, Master.cue_dev, Master.cue = d.get("main_dev"), d.get("cue_dev"), d.get("cue_level", 1.0)
        Cfg.fade, s.theme = d.get("fade", 1.2), d.get("theme", "Dark")
        s.endc.setCurrentIndex(s.mode); s.bm.setChecked(s.multi); s.bs.setChecked(s.shuf); s.mv.setValue(int(Master.v * 100)); s.hv.setValue(int(Master.cue * 100))

    def add_files(s, paths):
        bad = []
        for p in paths:
            try: c = Chan(p, dur=sf.info(p).duration); c.pg = s.cur_pg; s.chs.append(c)
            except Exception: bad.append(os.path.basename(p))
        s.rebuild(); s.save()
        if bad: QMessageBox.warning(s, APP, "These files could not be opened (use MP3, WAV, FLAC or OGG):\n\n" + "\n".join(bad))

    def pick(s):
        f, _ = QFileDialog.getOpenFileNames(s, "Add songs", "", "Audio (*.mp3 *.wav *.flac *.ogg *.opus);;All files (*)")
        if f: s.add_files(f)

    def dragEnterEvent(s, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(s, e): s.add_files([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def page_list(s, pg=None): return [c for c in s.chs if c.pg == (s.cur_pg if pg is None else pg)]

    def build_pgbar(s):
        while s.pgl.count():
            it = s.pgl.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        for p in s.pages:
            b = QPushButton(("⏰ " if (p["start"] or p["stop"]) else "") + p["name"]); b.setObjectName("page"); b.setCheckable(True); b.setChecked(p["id"] == s.cur_pg)
            b.clicked.connect(lambda _, i=p["id"]: s.pg_click(i)); s.pgl.addWidget(b)
        a = QPushButton("+ Page"); a.setObjectName("page"); a.clicked.connect(s.add_page); s.pgl.addWidget(a); s.pgl.addStretch(1)

    def pg_click(s, i):
        if i == s.cur_pg: s.page_dialog()
        else: s.cur_pg = i; s.rebuild(); s.save()

    def add_page(s):
        i = max(p["id"] for p in s.pages) + 1
        s.pages.append({"id": i, "name": f"Page {len(s.pages) + 1}", "start": None, "stop": None}); s.cur_pg = i; s.rebuild(); s.save()

    def rebuild(s):
        s.build_pgbar()
        w = QWidget(); w.setObjectName("root"); hl = QHBoxLayout(w); hl.setContentsMargins(10, 10, 10, 10); hl.setSpacing(10); s.hlay = hl
        s.strips = [Strip(c, s) for c in s.page_list()]
        for x in s.strips: hl.addWidget(x)
        a = QPushButton("+\nAdd song"); a.setFixedWidth(104); a.setMinimumHeight(200); a.clicked.connect(s.pick); hl.addWidget(a); hl.addStretch(1)
        s.area.setWidget(w); s.label_strips(); s.upd_tot()

    def label_strips(s):
        tot = 0.0
        for i, x in enumerate(s.strips, 1):
            tot += x.ch.dur; x.nb.setText(f"#{i}"); x.du.setText(fmt(x.ch.dur) if i == 1 else f"{fmt(x.ch.dur)}/{fmt(tot)}")

    def drag_strip(s, strip, gx):
        lay = s.hlay; ws = [lay.itemAt(i).widget() for i in range(lay.count()) if isinstance(lay.itemAt(i).widget(), Strip)]
        idx = sum(1 for w in ws if w is not strip and w.mapToGlobal(w.rect().center()).x() < gx)
        if ws.index(strip) != idx: lay.insertWidget(idx, strip)
        bar = s.area.horizontalScrollBar(); r = s.area.mapToGlobal(s.area.rect().topLeft()).x()
        if gx < r + 40: bar.setValue(bar.value() - 25)
        elif gx > r + s.area.width() - 40: bar.setValue(bar.value() + 25)

    def end_drag(s):
        lay = s.hlay; ps = [lay.itemAt(i).widget().ch for i in range(lay.count()) if isinstance(lay.itemAt(i).widget(), Strip)]
        k = 0; new = []
        for c in s.chs:
            if c.pg == s.cur_pg: new.append(ps[k]); k += 1
            else: new.append(c)
        s.chs = new; s.strips = [lay.itemAt(i).widget() for i in range(lay.count()) if isinstance(lay.itemAt(i).widget(), Strip)]
        s.label_strips(); s.save()

    # ---- menus
    def dev_menu(s, ch, btn):
        m = QMenu(s); a = m.addAction("Main output"); a.setCheckable(True); a.setChecked(not ch.dev)
        a.triggered.connect(lambda: s.set_dev(ch, None))
        for _, n in engine.outputs():
            a = m.addAction(n); a.setCheckable(True); a.setChecked(ch.dev == n); a.triggered.connect(lambda _, n=n: s.set_dev(ch, n))
        m.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def set_dev(s, ch, name):
        try: ch.set_device(name); engine.beep(name or Master.main_dev)
        except Exception as e: QMessageBox.warning(s, APP, f"Could not open that device:\n{e}")
        s.refresh(); s.save()

    def name_menu(s, ch, btn):
        m = QMenu(s)
        m.addAction("⏰ Start / stop time…", lambda: s.sched_dialog(ch))
        if ch.start_at or ch.stop_at: m.addAction("Clear start / stop time", lambda: s.clear_sched(ch))
        a = m.addAction("Only at its own time (Continue and Shuffle skip it)"); a.setCheckable(True); a.setChecked(ch.only); a.triggered.connect(lambda x: s.set_only(ch, x))
        pm = m.addMenu("Move to page")
        for p in s.pages:
            act = pm.addAction(p["name"], lambda pid=p["id"]: s.move_to_page(ch, pid)); act.setEnabled(p["id"] != ch.pg)
        m.addSeparator(); m.addAction("Remove", lambda: s.remove(ch)); m.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def set_only(s, ch, x): ch.only = bool(x); s.save(); s.refresh()

    def move_to_page(s, ch, pid): ch.pg = pid; s.rebuild(); s.save()

    def remove(s, ch):
        s.clip_stop(ch); ch.close(); ch.cue and ch.cue.close(); s.chs.remove(ch)
        if s.cur is ch: s.cur = None
        s.rebuild(); s.save()

    def clear_all(s):
        L = s.page_list()
        if L and QMessageBox.question(s, APP, f"Remove the {len(L)} song(s) of this page?") == QMessageBox.Yes:
            for c in L: s.clip_stop(c); c.close(); c.cue and c.cue.close(); s.chs.remove(c)
            if s.cur in L: s.cur = None
            s.held = [c for c in s.held if c in s.chs]; s.rebuild(); s.save()

    # ---- playback
    def lane(s, o, n): return s.pg_mode != 2 or o.pg == n.pg

    def toggle(s, ch):
        try:
            if ch.playing: ch.pause(); return
            s.round.clear()                           # a song started by hand begins a new run: Continue goes on from here
            if not s.multi:
                for o in s.chs:
                    if o is not ch and o.playing and s.lane(o, ch): o.pause(Cfg.fade)
            ch.play(); s.cur = ch; s.load_peaks(ch); s.round.add(ch)
        except Exception as e: QMessageBox.warning(s, APP, f"Could not play on that device:\n{e}")

    def play_pause_all(s):
        playing = [c for c in s.chs if c.playing]
        if playing: s.held = playing; [c.pause() for c in playing]; return
        for c in (s.held or ([s.cur] if s.cur else [])):
            if c in s.chs: s.toggle_play(c)
        s.held = []

    def toggle_play(s, c):
        try: c.play(); s.cur = s.cur or c
        except Exception as e: QMessageBox.warning(s, APP, str(e))

    def go(s, d):
        L = s.page_list(s.cur.pg if s.cur else s.cur_pg)
        if not L: return
        if d < 0 and s.cur and s.cur.pos() > 3: s.cur.seek(0); return
        i = L.index(s.cur) if s.cur in L else -1
        if d > 0 and s.shuf and len(L) > 1:
            j = i
            while j == i: j = random.randrange(len(L))
        else: j = 0 if i < 0 else (i + d) % len(L)
        ch = L[j]
        if ch.playing: ch.seek(0); s.cur = ch; return
        if s.multi and s.cur and s.cur.playing: s.cur.pause(Cfg.fade)
        s.toggle(ch) if not s.multi else (ch.seek(0), s.toggle(ch))

    def view(s):
        """The channel the waveform and seek buttons control: the headset cue while it plays, otherwise the main song."""
        cc = s.cue_ch.cue if (s.cue_ch and s.cue_ch.cue) else None
        if cc and (cc.playing or not (s.cur and s.cur.playing)): return cc
        return s.cur

    def seek_by(s, d):
        v = s.view()
        if v: v.seek(v.pos() + d)

    def seek_frac(s, f):
        v = s.view()
        if v and v.dur: v.seek(f * v.dur)

    def set_multi(s, x):
        s.multi = x; s.save()
        if not x and s.cur:
            for o in s.chs:
                if o is not s.cur and o.playing: o.pause(Cfg.fade)

    def set_master(s, x): Master.v = x / 100; s.mp.setText(f"{x}%")

    def load_peaks(s, ch):
        if ch.peaks is not None: return
        ch.peaks = []
        def job():
            p = engine.peaks(ch.path)
            try: s.br.peaks.emit(ch, p)
            except RuntimeError: pass
        threading.Thread(target=job, daemon=True).start()

    def got_peaks(s, ch, p): ch.peaks = p

    # ---- settings
    theme = "Dark"

    def settings_dialog(s):
        d = QDialog(s); d.setWindowTitle("Settings"); d.resize(600, 520); v = QVBoxLayout(d); tabs = QTabWidget(); v.addWidget(tabs)
        p = QWidget(); pl = QVBoxLayout(p)
        pl.addWidget(QLabel("Fade in / fade out time (play, pause, crossfade between songs)"))
        r = QHBoxLayout(); fs = QSlider(Qt.Horizontal); fs.setRange(0, 12); fs.setValue(int(round(Cfg.fade * 2))); fl = QLabel(); r.addWidget(fs, 1); r.addWidget(fl); pl.addLayout(r)
        def fchg():
            Cfg.fade = fs.value() / 2; fl.setText("Off" if not Cfg.fade else f"{Cfg.fade:g} s"); s.save()
        fs.valueChanged.connect(lambda _: fchg()); fchg()
        pl.addWidget(QLabel("Crossfade between songs (Continue); 0 = gapless"))
        r2 = QHBoxLayout(); xs = QSlider(Qt.Horizontal); xs.setRange(0, 20); xs.setValue(int(round(Cfg.xf * 2))); xl = QLabel(); r2.addWidget(xs, 1); r2.addWidget(xl); pl.addLayout(r2)
        def xchg(): Cfg.xf = xs.value() / 2; xl.setText("Gapless" if not Cfg.xf else f"{Cfg.xf:g} s"); s.save()
        xs.valueChanged.connect(lambda _: xchg()); xchg()
        pl.addWidget(QLabel("Song level while a clip plays"))
        r3 = QHBoxLayout(); ds = QSlider(Qt.Horizontal); ds.setRange(0, 100); ds.setValue(int(Cfg.duck * 100)); dl = QLabel(); r3.addWidget(ds, 1); r3.addWidget(dl); pl.addLayout(r3)
        def dchg(): Cfg.duck = ds.value() / 100; dl.setText(f"{ds.value()}%"); s.save()
        ds.valueChanged.connect(lambda _: dchg()); dchg()
        pl.addStretch(1); tabs.addTab(p, "Playback")
        q = QWidget(); ql = QVBoxLayout(q); ql.addWidget(QLabel("Display theme")); tc = QComboBox(); tc.addItems(list(THEMES)); tc.setCurrentText(s.theme); ql.addWidget(tc)
        def tchg(name): s.theme = name; set_theme(name); s.rebuild(); s.save()
        tc.currentTextChanged.connect(tchg); ql.addStretch(1); tabs.addTab(q, "Display")
        a = QWidget(); al = QVBoxLayout(a)
        for text, fn in (("Main output (dance floor / speakers)…", lambda: s.out_menu(False)), ("Headset output (pre-listen)…", lambda: s.out_menu(True)),
                         ("Test sound on Main", lambda: engine.beep(Master.main_dev)), ("Test sound on Headset", lambda: engine.beep(Master.cue_dev)),
                         ("↻ Refresh device list", s.rescan), ("Equalizer / Bass boost…", s.eq_dialog)):
            b = QPushButton(text); b.clicked.connect(lambda _, f=fn: f()); al.addWidget(b)
        tip = QLabel("Tip: a headset plugged into the laptop's 3.5 mm jack mutes the laptop speaker (Windows treats both as one output). Use HDMI, USB or Bluetooth for Main and the jack for the headset.")
        tip.setWordWrap(True); al.addWidget(tip); al.addStretch(1); tabs.addTab(a, "Audio")
        t = QTextBrowser(); t.setHtml(ABOUT_HTML.format(v=VERSION, a=AUTHOR)); tabs.addTab(t, "About")
        d.exec()

    # ---- equalizer, per-song schedule, keep awake
    PRESETS = [("Flat", [0, 0, 0, 0, 0]), ("Pop", [-1, 2, 4, 2, -1]), ("Rock", [4, 2, -1, 3, 4]), ("Jazz", [3, 2, -2, 2, 4]),
               ("Classical", [4, 2, -2, 2, 3]), ("Vocal", [-3, -1, 4, 3, 0]), ("Dance", [6, 4, 0, 2, 3])]
    _aw = False
    cue_ch = None

    # ---- DJ pre-listen (cue): hear a song in the headset, then send it to the Main output
    def out_menu(s, head):
        cur = Master.cue_dev if head else Master.main_dev
        btn = s.bhead if head else s.bmain
        m = QMenu(s); a = m.addAction("Windows default"); a.setCheckable(True); a.setChecked(not cur); a.triggered.connect(lambda: s.set_out(head, None))
        for _, n in engine.outputs():
            a = m.addAction(n); a.setCheckable(True); a.setChecked(cur == n); a.triggered.connect(lambda _, n=n: s.set_out(head, n))
        m.addSeparator(); m.addAction("↻ Refresh device list (after connecting Bluetooth / USB)", s.rescan)
        m.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def set_out(s, head, name):
        try:
            if head:
                Master.cue_dev = name
                for c in s.chs:
                    if c.cue and c.cue.stream is not None: c.cue.set_device(None)
            else:
                Master.main_dev = name
                for c in s.chs:
                    if not c.dev and c.stream is not None: c.set_device(None)
        except Exception as e: QMessageBox.warning(s, APP, f"Could not open that device:\n{e}")
        engine.beep(name); s.upd_out(); s.save()

    def rescan(s):
        allc = s.chs + [c.cue for c in s.chs if c.cue]
        was = [c for c in allc if c.stream is not None]
        for c in was: c.close_stream()
        engine.rescan()
        for c in was:
            try: c.ensure_stream()
            except Exception: pass
        s.upd_out()

    def upd_out(s):
        fm = s.fontMetrics()
        s.bmain.setText(fm.elidedText("🔈 Main: " + (Master.main_dev or "Windows default"), Qt.ElideMiddle, 210)); s.bmain.setToolTip(Master.main_dev or "Windows default output")
        s.bhead.setText(fm.elidedText("🎧 Headset: " + (Master.cue_dev or "not set"), Qt.ElideMiddle, 210)); s.bhead.setToolTip(Master.cue_dev or "Choose the headset output")
        a, b = engine.resolve(Master.main_dev), engine.resolve(Master.cue_dev)
        if not Master.cue_dev: s.warn.setText("Choose a Headset output, otherwise pre-listening plays on the Windows default output.")
        elif a is not None and a == b: s.warn.setText("Main and Headset are the same output: the dance floor would hear the pre-listen. Choose different devices.")
        else: s.warn.setText("")

    def set_cue_level(s, x): Master.cue = x / 100; s.hp.setText(f"{x}%")

    def toggle_cue(s, ch):
        try:
            if ch.cue and ch.cue.playing: ch.cue.pause(0.2); return
            for o in s.chs:
                if o is not ch and o.cue and o.cue.playing: o.cue.pause(0.2)
            if not ch.cue:
                c = Chan(ch.path, ch.name, ch.dur, 1.0); c.is_cue = True; ch.cue = c
            ch.cue.play(fade=0.2); s.cue_ch = ch; s.load_peaks(ch)
        except Exception as e: QMessageBox.warning(s, APP, f"Could not play in the headset:\n{e}")

    def send_main(s, ch):
        c = ch.cue
        if not c: return
        try:
            pos = c.pos(); c.pause(Cfg.fade); QTimer.singleShot(int(Cfg.fade * 1000) + 400, lambda: s.close_cue(ch))
            ch.seek(pos)
            if not s.multi:
                for o in s.chs:
                    if o is not ch and o.playing: o.pause(Cfg.fade)
            ch.play(); s.cur = ch; s.load_peaks(ch)
        except Exception as e: QMessageBox.warning(s, APP, f"Could not send to the main output:\n{e}")

    def close_cue(s, ch):
        if ch.cue and not ch.cue.playing: ch.cue.close(); ch.cue = None
        if s.cue_ch is ch and not ch.cue: s.cue_ch = None

    def eq_dialog(s):
        d = QDialog(s); d.setWindowTitle("Equalizer"); v = QVBoxLayout(d)
        cb = QComboBox(); cb.addItems([p[0] for p in s.PRESETS]); v.addWidget(cb)
        cb.setCurrentIndex(next((i for i, p in enumerate(s.PRESETS) if p[1] == list(Fx.gains)), 0))
        row = QHBoxLayout(); row.addWidget(QLabel("Bass boost")); sl = QSlider(Qt.Horizontal); sl.setRange(0, 12); sl.setValue(int(Fx.bass))
        lab = QLabel(f"+{int(Fx.bass)} dB"); row.addWidget(sl, 1); row.addWidget(lab); v.addLayout(row)
        def changed():
            Fx.gains = list(s.PRESETS[cb.currentIndex()][1]); Fx.bass = float(sl.value()); lab.setText(f"+{sl.value()} dB"); Fx.ver += 1; s.save()
        cb.currentIndexChanged.connect(lambda _: changed()); sl.valueChanged.connect(lambda _: changed()); d.exec()

    def sched_dialog(s, ch):
        d = QDialog(s); d.setWindowTitle("Start / stop time"); v = QVBoxLayout(d); rows = []
        for label, val in (("Start at", ch.start_at), ("Stop at", ch.stop_at)):
            r = QHBoxLayout(); cb = QCheckBox(label); te = QTimeEdit(); te.setDisplayFormat("hh:mm")
            if val: cb.setChecked(True); te.setTime(QTime(val.hour, val.minute))
            r.addWidget(cb); r.addWidget(te); v.addLayout(r); rows.append((cb, te))
        ok = QPushButton("Save"); v.addWidget(ok)
        def nxt(te):
            t = te.time(); n = datetime.now(); x = n.replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)
            return x if x > n else x + timedelta(days=1)
        def done():
            a = nxt(rows[0][1]) if rows[0][0].isChecked() else None
            b = nxt(rows[1][1]) if rows[1][0].isChecked() else None
            if a and b and b < a: b += timedelta(days=1)
            ch.start_at, ch.stop_at = a, b
            if a: ch.only = True
            s.save(); s.refresh(); d.accept()
        ok.clicked.connect(done); d.exec()

    def clear_sched(s, ch): ch.start_at = ch.stop_at = None; s.save(); s.refresh()

    def others_playing(s, c): return any(x.playing for x in s.chs if x is not c and s.lane(x, c))

    def next_of(s, c):
        L = s.page_list(c.pg)
        ok = lambda x: x is not c and not x.only and not x.playing
        if s.shuf:
            C = [x for x in L if ok(x) and x not in s.round]
            return random.choice(C) if C else None
        i = L.index(c)
        for x in L[i + 1:]:
            if ok(x): return x
        if s.pg_mode == 1:                                   # Continue page play: first song of the next page that has songs
            ids = [p["id"] for p in s.pages]
            for pid in ids[ids.index(c.pg) + 1:]:
                C = [x for x in s.page_list(pid) if ok(x)]
                if C: return C[0]
        return None                                          # last song: nothing follows, the player stops

    def pick_next(s, c):
        k = c.nx
        if k is not None and k in s.chs and k is not c and not k.only and not k.playing and (not s.shuf or k not in s.round): return k
        c.nx = s.next_of(c); return c.nx

    def launch(s, n, fade=None):
        try:
            if not s.multi:
                for o in s.chs:
                    if o is not n and o.playing and s.lane(o, n): o.pause(Cfg.fade if fade is None else fade)
            if not n.playing: n.play(restart=True, fade=fade)
            s.round.add(n); s.cur = n; s.load_peaks(n)
        except Exception as e: s.statusBar().showMessage(f"Could not play {n.name}: {e}", 8000)

    def continue_check(s):
        """Start the next song a little before this one ends: crossfade, or no gap at all."""
        for c in s.chs:
            if not c.playing or c.xfd or s.mode != 2 or not c.dur: continue
            rem = c.dur - c.pos(); lead = max(Cfg.xf, 0.3)
            if rem > lead + 3 or s.others_playing(c): continue
            n = s.pick_next(c)
            if n is None or n.playing: continue
            if rem > lead:                                    # still a few seconds: get the next song ready
                n.idle_t = time.time()
                try: n.ensure_stream()
                except Exception: pass
                continue
            c.xfd = True; s.clip_stop(c); s.round.add(c)
            c.pause(max(rem, 0.08))                           # the old song fades out until its end
            s.launch(n, fade=Cfg.xf if Cfg.xf > 0 else 0.06)

    # ---- clips: dialogue sounds that play at set times of a song
    def clip_stop(s, c):
        if c.cp: c.cp.stop(); c.cp = None
        c.duck_t, c.cp_held = 1.0, False
        if c.clips_on: c.clips_on = False; s.save()

    def play_clip(s, c, k):
        try:
            cp = ClipPlayer(k["path"], c.dev or Master.main_dev); cp.start()
            c.cp, c.cp_held, c.duck_t = cp, False, Cfg.duck
        except Exception as e: s.statusBar().showMessage(f"Could not play the clip: {e}", 6000)

    def clip_tick(s):
        for c in s.chs:
            p = c.pos(); d = p - c._lp; c._lp = p
            if abs(d) > 2:                                    # the song was moved: skip or re-arm clips
                for k in c.clips: k["pd"] = (k["pd"] or k["at"] < p - 1) if d > 0 else (k["at"] < p - 1)
            cp = c.cp
            if cp and cp.done: cp.stop(); c.cp = cp = None; c.duck_t = 1.0
            if cp:
                if c.playing and cp.paused and c.cp_held: cp.resume(); c.cp_held = False      # the song plays again: the clip goes on
                elif not c.playing and not cp.paused: cp.pause(); c.cp_held = True           # the song is paused: the clip pauses too
            elif c.clips_on and c.playing and not c.xfd:
                for k in c.clips:
                    if not k["pd"] and k["at"] <= p < k["at"] + 600: k["pd"] = True; s.play_clip(c, k); break

    pv = None
    pv_key = None

    def preview(s, key, path, head):
        if s.pv and not s.pv.done and s.pv_key == key:        # pressed again: pause / resume
            s.pv.resume() if s.pv.paused else s.pv.pause(); return
        if s.pv: s.pv.stop()
        try: s.pv = ClipPlayer(path, Master.cue_dev if head else Master.main_dev, head); s.pv.start(); s.pv_key = key
        except Exception as e: s.pv = None; QMessageBox.warning(s, APP, f"Could not play the clip:\n{e}")

    def clips_dialog(s, ch):
        d = QDialog(s); d.setWindowTitle(f"Clips - {ch.name}"); d.resize(600, 480); v = QVBoxLayout(d)
        info = QLabel("Set the time (m:ss of this song) for every clip, then press Apply. A clip plays once at its time, even when the song is muted. "
                      "Pausing the song pauses the clip; when the song ends the clips become inactive.")
        info.setWordWrap(True); v.addWidget(info)
        top = QHBoxLayout(); v.addLayout(top); add = QPushButton("+ Add Clip"); clr = QPushButton("Clear Clips"); top.addWidget(add); top.addWidget(clr)
        sc = QScrollArea(); sc.setWidgetResizable(True); box = QWidget(); bl = QVBoxLayout(box); bl.addStretch(1); sc.setWidget(box); v.addWidget(sc, 1)
        ap = QPushButton(); v.addWidget(ap)
        def refresh_ap(): ap.setText("Apply (active)" if ch.clips_on else "Apply")
        def dirty(): ch.clips_on = False; refresh_ap(); s.save(); s.refresh()
        def tmin(t):
            try: return sum(float(x) * 60 ** i for i, x in enumerate(reversed(t.strip().split(":"))))
            except Exception: return None
        def order():
            ch.clips = [bl.itemAt(i).widget().clip for i in range(bl.count()) if getattr(bl.itemAt(i).widget(), "clip", None) is not None]; dirty()
        def make_row(k):
            r = QFrame(); r.clip = k; rl = QHBoxLayout(r); rl.setContentsMargins(6, 4, 6, 4)
            nm = QLabel(k["name"]); nm.setMinimumWidth(140)
            pl = QPushButton("▶"); pl.setObjectName("mini"); pl.setToolTip("Play / pause this clip"); pl.clicked.connect(lambda: s.preview(id(k), k["path"], False))
            hd = QPushButton("🎧"); hd.setObjectName("mini"); hd.setToolTip("Pre-listen in the headset"); hd.clicked.connect(lambda: s.preview(id(k), k["path"], True))
            te = QLineEdit(fmt(k["at"])); te.setFixedWidth(64); te.setAlignment(Qt.AlignCenter); te.setToolTip("Play at (m:ss)")
            def edited():
                t = tmin(te.text())
                if t is not None: k["at"], k["pd"] = t, False; dirty()
                te.setText(fmt(k["at"]))
            te.editingFinished.connect(edited)
            dl = QPushButton("✕"); dl.setObjectName("mini"); dl.setToolTip("Remove")
            def rm(): ch.clips.remove(k); r.setParent(None); r.deleteLater(); dirty()
            dl.clicked.connect(rm)
            for w in (VGrip(r, order), nm): rl.addWidget(w, 1 if w is nm else 0)
            for w in (pl, hd, te, dl): rl.addWidget(w)
            bl.insertWidget(bl.count() - 1, r)
        for k in ch.clips: make_row(k)
        def do_add():
            fs, _ = QFileDialog.getOpenFileNames(d, "Add clips", "", "Audio (*.mp3 *.wav *.flac *.ogg *.opus);;All files (*)")
            for p in fs:
                k = {"path": p, "name": os.path.splitext(os.path.basename(p))[0], "at": (ch.clips[-1]["at"] if ch.clips else 0) + 60, "pd": False}
                ch.clips.append(k); make_row(k)
            if fs: dirty()
        def do_clear():
            if ch.clips and QMessageBox.question(d, APP, "Remove all clips of this song?") == QMessageBox.Yes:
                ch.clips = []
                for i in range(bl.count() - 1, -1, -1):
                    w = bl.itemAt(i).widget()
                    if w is not None: w.setParent(None); w.deleteLater()
                dirty()
        def do_apply():
            ch.clips_on = True; p = ch.pos()
            for k in ch.clips: k["pd"] = k["at"] < p - 1
            s.save(); s.refresh(); d.accept()
        add.clicked.connect(do_add); clr.clicked.connect(do_clear); ap.clicked.connect(do_apply); refresh_ap()
        d.exec()
        if s.pv: s.pv.stop(); s.pv = None

    # ---- pages
    def page_dialog(s):
        p = next(x for x in s.pages if x["id"] == s.cur_pg)
        d = QDialog(s); d.setWindowTitle("Page"); v = QVBoxLayout(d)
        r = QHBoxLayout(); ne = QLineEdit(p["name"]); rb = QPushButton("Rename"); r.addWidget(ne, 1); r.addWidget(rb); v.addLayout(r)
        v.addWidget(QLabel("Page timer: the page starts at its start time and stops at its stop time")); rows = []
        for label, val in (("Start at", p["start"]), ("Stop at", p["stop"])):
            hr = QHBoxLayout(); cb = QCheckBox(label); te = QTimeEdit(); te.setDisplayFormat("hh:mm")
            if val: cb.setChecked(True); te.setTime(QTime(val.hour, val.minute))
            hr.addWidget(cb); hr.addWidget(te); v.addLayout(hr); rows.append((cb, te))
        st = QPushButton("Save page timer"); dup = QPushButton("Duplicate this page"); dl = QPushButton("Delete this page (its songs move to another page)")
        for w in (st, dup, dl): v.addWidget(w)
        def rename():
            p["name"] = ne.text().strip() or p["name"]; s.rebuild(); s.save()
        def nxt(te):
            t = te.time(); n = datetime.now(); x = n.replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)
            return x if x > n else x + timedelta(days=1)
        def timer():
            a = nxt(rows[0][1]) if rows[0][0].isChecked() else None
            b = nxt(rows[1][1]) if rows[1][0].isChecked() else None
            if a and b and b < a: b += timedelta(days=1)
            p["start"], p["stop"] = a, b; s.build_pgbar(); s.save(); d.accept()
        def duplicate():
            i = max(q["id"] for q in s.pages) + 1; s.pages.append({"id": i, "name": p["name"] + " (copy)", "start": None, "stop": None})
            for c in s.page_list(p["id"]):
                n = Chan(c.path, c.name, c.dur, c.vol, c.dev); n.mute, n.only, n.pg = c.mute, c.only, i
                n.clips = [dict(k, pd=False) for k in c.clips]; s.chs.append(n)
            s.cur_pg = i; s.rebuild(); s.save(); d.accept()
        def delete():
            if len(s.pages) < 2: return
            first = next(q for q in s.pages if q["id"] != p["id"])
            for c in s.page_list(p["id"]): c.pg = first["id"]
            s.pages.remove(p); s.cur_pg = first["id"]; s.rebuild(); s.save(); d.accept()
        rb.clicked.connect(rename); st.clicked.connect(timer); dup.clicked.connect(duplicate); dl.clicked.connect(delete); d.exec()

    def keep_awake(s, on):
        if sys.platform != "win32" or on == s._aw: return
        s._aw = on
        try: ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if on else 0x80000000)   # keep the PC from sleeping
        except Exception: pass

    def run_schedules(s):
        now = datetime.now(); changed = False
        for p in s.pages:
            if p["start"] and now >= p["start"]:
                late = (now - p["start"]).total_seconds(); p["start"] = None; changed = True
                L = s.page_list(p["id"]); f = next((x for x in L if not x.only), L[0] if L else None)
                if late < 600 and f and not f.playing: s.round.clear(); s.launch(f)
            if p["stop"] and now >= p["stop"]:
                late = (now - p["stop"]).total_seconds(); p["stop"] = None; changed = True
                if late < 600:
                    for x in s.page_list(p["id"]):
                        if x.playing: x.pause(2.5)
        if changed: s.build_pgbar(); s.save()
        for c in s.chs:
            if c.start_at and now >= c.start_at:
                late = (now - c.start_at).total_seconds(); c.start_at = None; s.save()
                if late < 600 and not c.playing: s.round.clear(); s.launch(c)
            if c.stop_at and now >= c.stop_at:
                late = (now - c.stop_at).total_seconds(); c.stop_at = None; s.save()
                if late < 600 and c.playing:
                    c.pause(2.5)
                    if s.mode == 2:
                        n = s.pick_next(c)
                        if n and not n.playing: s.launch(n)
        s.keep_awake(any(x.playing or x.start_at or x.stop_at for x in s.chs) or any(p["start"] or p["stop"] for p in s.pages))

    # ---- periodic work
    def upd_tot(s):
        L = s.page_list()
        s.tot.setText(f"⏱ {fmt(sum(min(c.played, c.dur) for c in L))} / {fmt(sum(c.dur for c in L))}")

    def reset_played(s):
        for c in s.chs: c.played = 0.0
        s.round.clear(); s.upd_tot()

    def refresh(s):
        for x in s.strips: x.refresh()
        s.pp.setText("⏸" if any(c.playing for c in s.chs) else "▶")

    def tick(s):
        s.upd_tot(); s.run_schedules()
        for c in s.chs: c.idle_close(); c.cue and c.cue.idle_close()
        for c in s.chs:
            if c.ended:
                c.ended = False; s.clip_stop(c)               # the song's time is over: its clips stop and become inactive
                if c.xfd: c.xfd = False; continue             # already handed over (crossfade)
                s.round.add(c)
                if s.mode == 1: c.play(restart=True)
                elif s.mode == 2 and not s.others_playing(c):  # Continue: if another song is still playing, it carries the list on
                    n = s.pick_next(c)
                    if n and not n.playing: s.launch(n)
        s.continue_check(); s.clip_tick()
        v = s.view(); c = s.cur
        n = sum(1 for x in s.chs if x.playing)
        if v is not None and v.is_cue: s.now.setText("🎧 " + v.name + "  (pre-listen)")
        else: s.now.setText((c.name + (f"  +{n - 1}" if n > 1 else "")) if c else "Nothing playing")
        if v is not None:
            owner = s.cue_ch if v.is_cue else v
            s.wave.peaks, s.wave.frac = owner.peaks or [], (v.pos() / v.dur if v.dur else 0)
            s.wave.left, s.wave.right = fmt(v.pos()), "-" + fmt(v.dur - v.pos())
        else: s.wave.peaks, s.wave.frac, s.wave.left, s.wave.right = [], 0, "0:00", "-0:00"
        s.wave.update(); s.refresh()

    def keyPressEvent(s, e):
        if e.key() == Qt.Key_Space: s.play_pause_all()
        else: super().keyPressEvent(e)

    def closeEvent(s, e):
        s.save()
        for c in s.chs: c.cp and c.cp.stop()
        s.pv and s.pv.stop()
        [(c.close(), c.cue and c.cue.close()) for c in s.chs]; super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyleSheet(CSS); app.setApplicationName(APP)
    ic = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "icon.png")
    if os.path.exists(ic): app.setWindowIcon(QIcon(ic))
    w = Main(); w.show(); sys.exit(app.exec())
