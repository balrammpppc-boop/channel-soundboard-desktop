"""Channel Soundboard - desktop version. Every channel can play to a different output device at the same time."""
import ctypes, json, os, random, sys, threading
from datetime import datetime, timedelta
import soundfile as sf
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRectF, QTime
from PySide6.QtGui import QPainter, QColor, QIcon, QFont, QAction
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                               QSlider, QScrollArea, QFrame, QMenu, QComboBox, QFileDialog, QMessageBox,
                               QDialog, QTimeEdit, QToolButton, QCheckBox, QTabWidget, QTextBrowser)
import engine
from engine import Chan, Master, Fx, Cfg, fmt

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
QTimeEdit{background:#13151a;color:#e6e8ee;border:1px solid #343843;border-radius:6px;padding:3px}
QScrollArea{border:0;background:transparent} QMenu{background:#1c1f26;color:#e6e8ee;border:1px solid #343843} QMenu::item:selected{background:#f2b53d;color:#1b1300}
"""

VERSION, AUTHOR = "8", "Balram Sevak"
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
<h3>Features</h3><ul><li>Unlimited channels, per-channel volume, mute and output device</li><li>DJ pre-listen: hear a song in the headset, then send it to the Main output</li><li>Multiplay, crossfade, shuffle, repeat, continue</li><li>Equalizer presets and bass boost</li><li>Timer and per-song start/stop times</li><li>Waveform seek bar with elapsed and remaining time</li></ul>
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


class Bridge(QObject):
    peaks = Signal(object, list)


class Strip(QFrame):
    def __init__(s, ch, m):
        super().__init__(); s.ch, s.m = ch, m; s.setObjectName("strip"); s.setFixedWidth(112)
        v = QVBoxLayout(s); v.setContentsMargins(6, 8, 6, 8); v.setSpacing(6)
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
        s.nm = QPushButton(); s.nm.clicked.connect(lambda: m.name_menu(ch, s.nm)); v.addWidget(s.nm)
        s.du = QLabel(fmt(ch.dur)); s.du.setAlignment(Qt.AlignCenter); s.du.setStyleSheet(T("color:#9aa0ad;font-size:11px")); v.addWidget(s.du)
        s.refresh()

    def setm(s, x, save=True):
        s.ch.mute = bool(x); s.mute.setText("🔇 Muted" if x else "🔊 Mute")
        if save: s.m.save()

    def setv(s, x): s.ch.vol = x / 100; s.pc.setText(f"{x}%")

    def refresh(s):
        c = s.ch; s.pc.setText(f"{int(c.vol * 100)}%")
        s.dev.setText("🔈 " + ((c.dev[:11] + "…") if c.dev and len(c.dev) > 12 else (c.dev or "Main"))); s.dev.setToolTip(c.dev or "Follows the Main output")
        s.nm.setText(s.fontMetrics().elidedText(("⏰ " if (c.start_at or c.stop_at) else "") + c.name, Qt.ElideRight, 80)); s.nm.setToolTip(c.name)
        for w, on in ((s, c.playing), (s.play, c.playing)):
            w.setProperty("on", on); w.style().unpolish(w); w.style().polish(w)
        s.play.setText("⏸" if c.playing else "▶")
        s.cue.setChecked(bool(c.cue and c.cue.playing)); s.send.setEnabled(c.cue is not None)


class Main(QMainWindow):
    def __init__(s):
        super().__init__(); s.setWindowTitle(f"{APP} v{VERSION} - {AUTHOR}"); s.resize(1120, 660); s.setAcceptDrops(True)
        s.chs, s.cur, s.mode, s.multi, s.shuf, s.stop_at, s.held, s.strips = [], None, 2, False, False, None, [], []
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
        s.bmain = QPushButton(); s.bmain.clicked.connect(lambda: s.out_menu(False)); l.addWidget(s.bmain)
        s.bhead = QPushButton(); s.bhead.clicked.connect(lambda: s.out_menu(True)); l.addWidget(s.bhead)
        s.warn = QLabel(""); s.warn.setWordWrap(True); s.warn.setStyleSheet("color:#ff8a65;font-size:11px"); l.addWidget(s.warn)
        s.bt = QPushButton("⏲ Timer"); s.bt.clicked.connect(s.timer_dialog); l.addWidget(s.bt)
        s.be = QPushButton("EQ / Bass boost"); s.be.clicked.connect(s.eq_dialog); l.addWidget(s.be)
        s.bset = QPushButton("⚙ Settings"); s.bset.clicked.connect(s.settings_dialog); l.addWidget(s.bset)
        r = QHBoxLayout(); l.addLayout(r); s.tot = QPushButton("⏱ 0:00 / 0:00"); s.tot.setFlat(True); s.tot.setStyleSheet(T("text-align:left;border:0;color:#9aa0ad;font-size:11px")); s.tot.setToolTip("Played / total. Click to reset the played time"); s.tot.clicked.connect(s.reset_played); r.addWidget(s.tot, 1)
        c = QPushButton("Clear"); c.clicked.connect(s.clear_all); r.addWidget(c)
        l.addStretch(1)
        ml = QHBoxLayout(); l.addLayout(ml); ml.addWidget(QLabel("Master"))
        s.mv = QSlider(Qt.Horizontal); s.mv.setRange(0, 100); s.mv.setValue(100); s.mv.valueChanged.connect(s.set_master); s.mv.sliderReleased.connect(s.save); ml.addWidget(s.mv, 1)
        s.mp = QLabel("100%"); ml.addWidget(s.mp)
        hl = QHBoxLayout(); l.addLayout(hl); hl.addWidget(QLabel("🎧 Level"))
        s.hv = QSlider(Qt.Horizontal); s.hv.setRange(0, 100); s.hv.setValue(100); s.hv.valueChanged.connect(s.set_cue_level); s.hv.sliderReleased.connect(s.save); hl.addWidget(s.hv, 1)
        s.hp = QLabel("100%"); hl.addWidget(s.hp)
        # ---- channels
        s.area = QScrollArea(); s.area.setWidgetResizable(True); h.addWidget(s.area, 1)
        s.load(); set_theme(s.theme); s.rebuild(); s.upd_out()
        t = QTimer(s); t.timeout.connect(s.tick); t.start(100)

    # ---- library
    def save(s):
        try:
            os.makedirs(DATA, exist_ok=True)
            json.dump({"mode": s.mode, "multi": s.multi, "shuf": s.shuf, "master": Master.v, "eq": Fx.gains, "bass": Fx.bass, "fade": Cfg.fade, "theme": s.theme, "main_dev": Master.main_dev, "cue_dev": Master.cue_dev, "cue_level": Master.cue,
                       "songs": [{"path": c.path, "name": c.name, "dur": c.dur, "vol": c.vol, "dev": c.dev, "mute": c.mute,
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
                c = Chan(x["path"], x.get("name"), x.get("dur", 0), x.get("vol", 1.0), x.get("dev")); c.mute = x.get("mute", False)
                try:
                    c.start_at = datetime.fromisoformat(x["start"]) if x.get("start") else None
                    c.stop_at = datetime.fromisoformat(x["stop"]) if x.get("stop") else None
                except Exception: pass
                s.chs.append(c)
        s.mode, s.multi, s.shuf = d.get("mode", 2), d.get("multi", False), d.get("shuf", False)
        Master.v = d.get("master", 1.0)
        Fx.gains, Fx.bass = d.get("eq", [0] * 5), d.get("bass", 0.0); Fx.ver += 1
        Master.main_dev, Master.cue_dev, Master.cue = d.get("main_dev"), d.get("cue_dev"), d.get("cue_level", 1.0)
        Cfg.fade, s.theme = d.get("fade", 1.2), d.get("theme", "Dark")
        s.endc.setCurrentIndex(s.mode); s.bm.setChecked(s.multi); s.bs.setChecked(s.shuf); s.mv.setValue(int(Master.v * 100)); s.hv.setValue(int(Master.cue * 100))

    def add_files(s, paths):
        bad = []
        for p in paths:
            try: s.chs.append(Chan(p, dur=sf.info(p).duration))
            except Exception: bad.append(os.path.basename(p))
        s.rebuild(); s.save()
        if bad: QMessageBox.warning(s, APP, "These files could not be opened (use MP3, WAV, FLAC or OGG):\n\n" + "\n".join(bad))

    def pick(s):
        f, _ = QFileDialog.getOpenFileNames(s, "Add songs", "", "Audio (*.mp3 *.wav *.flac *.ogg *.opus);;All files (*)")
        if f: s.add_files(f)

    def dragEnterEvent(s, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(s, e): s.add_files([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def rebuild(s):
        w = QWidget(); w.setObjectName("root"); hl = QHBoxLayout(w); hl.setContentsMargins(10, 10, 10, 10); hl.setSpacing(10)
        s.strips = [Strip(c, s) for c in s.chs]
        for x in s.strips: hl.addWidget(x)
        a = QPushButton("+\nAdd song"); a.setFixedWidth(104); a.setMinimumHeight(200); a.clicked.connect(s.pick); hl.addWidget(a); hl.addStretch(1)
        s.area.setWidget(w); s.upd_tot()

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
        m = QMenu(s); i = s.chs.index(ch)
        m.addAction("◀ Move left", lambda: s.move(i, -1)); m.addAction("Move right ▶", lambda: s.move(i, 1)); m.addSeparator()
        m.addAction("⏰ Start / stop time…", lambda: s.sched_dialog(ch))
        if ch.start_at or ch.stop_at: m.addAction("Clear start / stop time", lambda: s.clear_sched(ch))
        m.addSeparator(); m.addAction("Remove", lambda: s.remove(ch)); m.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def move(s, i, d):
        j = i + d
        if 0 <= j < len(s.chs): s.chs.insert(j, s.chs.pop(i)); s.rebuild(); s.save()

    def remove(s, ch):
        ch.close(); ch.cue and ch.cue.close(); s.chs.remove(ch)
        if s.cur is ch: s.cur = None
        s.rebuild(); s.save()

    def clear_all(s):
        if s.chs and QMessageBox.question(s, APP, "Remove all songs from the list?") == QMessageBox.Yes:
            for c in s.chs: c.close(); c.cue and c.cue.close()
            s.chs, s.cur, s.held = [], None, []; s.rebuild(); s.save()

    # ---- playback
    def toggle(s, ch):
        try:
            if ch.playing: ch.pause(); return
            if not s.multi:
                for o in s.chs:
                    if o is not ch and o.playing: o.pause(Cfg.fade)
            ch.play(); s.cur = ch; s.load_peaks(ch)
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
        if not s.chs: return
        if d < 0 and s.cur and s.cur.pos() > 3: s.cur.seek(0); return
        i = s.chs.index(s.cur) if s.cur in s.chs else -1
        if d > 0 and s.shuf and len(s.chs) > 1:
            j = i
            while j == i: j = random.randrange(len(s.chs))
        else: j = 0 if i < 0 else (i + d) % len(s.chs)
        ch = s.chs[j]
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

    # ---- timer
    def timer_dialog(s):
        d = QDialog(s); d.setWindowTitle("Stop everything at"); v = QVBoxLayout(d)
        te = QTimeEdit(); te.setDisplayFormat("hh:mm"); v.addWidget(te)
        row = QHBoxLayout(); v.addLayout(row)
        ok, no = QPushButton("Set"), QPushButton("Cancel timer"); row.addWidget(ok); row.addWidget(no)
        def setit():
            t = te.time(); n = datetime.now(); x = n.replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)
            s.stop_at = x if x > n else x + timedelta(days=1); d.accept()
        ok.clicked.connect(setit); no.clicked.connect(lambda: (setattr(s, "stop_at", None), d.accept())); d.exec()

    # ---- settings
    theme = "Dark"

    def settings_dialog(s):
        d = QDialog(s); d.setWindowTitle("Settings"); d.resize(600, 520); v = QVBoxLayout(d); tabs = QTabWidget(); v.addWidget(tabs)
        p = QWidget(); pl = QVBoxLayout(p)
        pl.addWidget(QLabel("Fade in / fade out time (play, pause, crossfade between songs)"))
        r = QHBoxLayout(); fs = QSlider(Qt.Horizontal); fs.setRange(0, 12); fs.setValue(int(round(Cfg.fade * 2))); fl = QLabel(); r.addWidget(fs, 1); r.addWidget(fl); pl.addLayout(r)
        def fchg():
            Cfg.fade = fs.value() / 2; fl.setText("Off" if not Cfg.fade else f"{Cfg.fade:g} s"); s.save()
        fs.valueChanged.connect(lambda _: fchg()); fchg(); pl.addStretch(1); tabs.addTab(p, "Playback")
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
            ch.start_at, ch.stop_at = a, b; s.save(); s.refresh(); d.accept()
        ok.clicked.connect(done); d.exec()

    def clear_sched(s, ch): ch.start_at = ch.stop_at = None; s.save(); s.refresh()

    def next_after(s, c):
        s.round.add(c)
        if s.shuf:
            left = [x for x in s.chs if x not in s.round and not x.playing]
            if not left: s.round.clear()
            return random.choice(left) if left else None
        i = s.chs.index(c)
        return next((x for x in s.chs[i + 1:] if not x.playing and x not in s.round), None)        # last song: nothing follows -> player stops

    def launch(s, n):
        try:
            if not s.multi:
                for o in s.chs:
                    if o is not n and o.playing: o.pause(Cfg.fade)
            if not n.playing: n.play(restart=True)
            s.cur = n; s.load_peaks(n)
        except Exception as e: s.statusBar().showMessage(f"Could not play {n.name}: {e}", 8000)

    def keep_awake(s, on):
        if sys.platform != "win32" or on == s._aw: return
        s._aw = on
        try: ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if on else 0x80000000)   # keep the PC from sleeping
        except Exception: pass

    def run_schedules(s):
        now = datetime.now()
        for c in s.chs:
            if c.start_at and now >= c.start_at:
                late = (now - c.start_at).total_seconds(); c.start_at = None; s.save()
                if late < 600 and not c.playing: s.launch(c)
            if c.stop_at and now >= c.stop_at:
                late = (now - c.stop_at).total_seconds(); c.stop_at = None; s.save()
                if late < 600 and c.playing:
                    c.pause(2.5)
                    if s.mode == 2:
                        n = s.next_after(c)
                        if n and not n.playing: s.launch(n)
        s.keep_awake(bool(s.stop_at) or any(x.playing or x.start_at or x.stop_at for x in s.chs))

    # ---- periodic work
    def upd_tot(s):
        s.tot.setText(f"⏱ {fmt(sum(min(c.played, c.dur) for c in s.chs))} / {fmt(sum(c.dur for c in s.chs))}")

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
                c.ended = False; s.round.add(c)
                if s.mode == 1: c.play(restart=True)
                elif s.mode == 2 and not any(x.playing for x in s.chs if x is not c):   # Continue: if another song is still playing, it carries the list on
                    s.round.add(c)
                    if s.shuf:                  # shuffle: every song once, then stop
                        left = [x for x in s.chs if x not in s.round]
                        n = random.choice(left) if left else None
                        if not left: s.round.clear()
                    else:
                        i = s.chs.index(c); n = next((x for x in s.chs[i + 1:] if not x.playing and x not in s.round), None)
                    if n and not n.playing: n.play(restart=True); s.cur = n; s.load_peaks(n)
        if s.stop_at and datetime.now() >= s.stop_at:
            s.stop_at = None; [c.pause(4.0) for c in s.chs if c.playing]
        s.bt.setText("⏲ " + fmt((s.stop_at - datetime.now()).total_seconds()) if s.stop_at else "⏲ Timer")
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
        s.save(); [(c.close(), c.cue and c.cue.close()) for c in s.chs]; super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyleSheet(CSS); app.setApplicationName(APP)
    ic = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "icon.png")
    if os.path.exists(ic): app.setWindowIcon(QIcon(ic))
    w = Main(); w.show(); sys.exit(app.exec())
