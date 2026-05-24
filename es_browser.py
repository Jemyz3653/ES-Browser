#!/usr/bin/env python3
"""
PyBrowser v3
Install: pip install PyQt5 PyQtWebEngine
Run:     python pybrowser.py
"""

import sys, os, re, json, fnmatch
from datetime import datetime
from urllib.parse import quote_plus

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLineEdit, QToolButton, QLabel, QStatusBar, QToolBar,
    QAction, QDialog, QListWidget, QListWidgetItem, QCheckBox,
    QComboBox, QSpinBox, QFormLayout, QDialogButtonBox, QFileDialog,
    QMessageBox, QProgressBar, QSizePolicy, QShortcut, QTextEdit,
    QSplitter, QFrame, QScrollArea, QGridLayout, QPushButton,
    QGroupBox, QPlainTextEdit, QAbstractItemView,
)
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView, QWebEngineProfile, QWebEnginePage,
    QWebEngineSettings, QWebEngineScript,
)
from PyQt5.QtCore import Qt, QUrl, QSize, QRect, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import (
    QIcon, QKeySequence, QColor, QPalette, QPixmap, QPainter, QFont,
    QFontMetrics,
)
from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog

# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR      = os.path.join(os.path.expanduser("~"), ".pybrowser")
BOOKMARKS_F   = os.path.join(DATA_DIR, "bookmarks.json")
HISTORY_F     = os.path.join(DATA_DIR, "history.json")
SETTINGS_F    = os.path.join(DATA_DIR, "settings.json")
SESSIONS_F    = os.path.join(DATA_DIR, "sessions.json")
USER_SCRIPTS_F= os.path.join(DATA_DIR, "userscripts.json")
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
os.makedirs(DATA_DIR, exist_ok=True)

RUFFLE_CDN = "https://unpkg.com/@ruffle-rs/ruffle"

DEFAULTS = {
    "homepage":          "about:newtab",
    "search_engine":     "https://www.google.com/search?q=",
    "theme":             "Catppuccin Mocha",
    "zoom":              100,
    "ad_block":          True,
    "https_everywhere":  False,
    "ruffle":            True,
    "dark_reader":       False,
    "user_agent":        "",
    "restore_session":   False,
}
SEARCH_ENGINES = {
    "Google":     "https://www.google.com/search?q=",
    "DuckDuckGo": "https://duckduckgo.com/?q=",
    "Bing":       "https://www.bing.com/search?q=",
    "Yandex":     "https://yandex.ru/search/?text=",
    "Brave":      "https://search.brave.com/search?q=",
    "Startpage":  "https://www.startpage.com/search?q=",
}

# ── Huge ad/tracker domain list ────────────────────────────────────────────────
AD_DOMAINS = {
    "doubleclick.net","googlesyndication.com","googleadservices.com",
    "adnxs.com","advertising.com","outbrain.com","taboola.com",
    "scorecardresearch.com","quantserve.com","amazon-adsystem.com",
    "moatads.com","mc.yandex.ru","counter.yadro.ru","pagead2.googlesyndication.com",
    "ads.twitter.com","pixel.facebook.com","pixel.advertising.com",
    "analytics.google.com","stats.g.doubleclick.net","adservice.google.com",
    "adbrite.com","zedo.com","yieldmanager.com","adroll.com","criteo.com",
    "pubmatic.com","openx.net","rubiconproject.com","spotxchange.com",
    "sharethrough.com","revcontent.com","mgid.com","valueclick.com",
    "buysellads.com","media.net","bidswitch.net","smartadserver.com",
    "eyeota.net","adsafeprotected.com","moatpixel.com",
    "chartbeat.com","hotjar.com","mouseflow.com","fullstory.com",
    "tracking.crazyegg.com","cdn.segment.com","go.microsoft.com/fwlink",
}

# ── Theme system ───────────────────────────────────────────────────────────────
def make_qss(p: dict) -> str:
    bg,bg2,bg3 = p["bg"],p["bg2"],p["bg3"]
    fg,fg2     = p["fg"],p["fg2"]
    ac         = p["ac"]
    bd         = p["bd"]
    tab_bg     = p.get("tab_bg", bg2)
    tab_sel    = p.get("tab_sel", bg3)
    priv_bg    = p.get("priv_bg", "#2d1b69")
    return f"""
QMainWindow,QDialog,QWidget {{font-family:'Segoe UI','Ubuntu',sans-serif;
    background:{bg};color:{fg};}}
QLabel {{color:{fg};}}
QToolBar {{background:{bg2};border:none;border-bottom:1px solid {bd};
    padding:4px 8px;spacing:3px;}}
NavButton {{background:transparent;border:none;border-radius:8px;
    color:{fg2};font-size:15px;padding:3px 8px;min-width:32px;min-height:32px;}}
NavButton:hover   {{background:{bg3};}}
NavButton:pressed {{background:{bd};}}
NavButton:disabled{{color:{bd};}}
NavButton:checked {{background:{ac};color:white;border-radius:8px;}}
URLBarEdit {{background:{bg3};border:1.5px solid transparent;border-radius:20px;
    padding:5px 36px 5px 32px;font-size:13px;color:{fg};}}
URLBarEdit:focus {{background:{bg2};border-color:{ac};}}
QTabWidget::pane {{border:none;background:{bg};}}
QTabBar {{background:{bg2};}}
QTabBar::tab {{background:{tab_bg};color:{fg2};border:none;
    border-radius:8px 8px 0 0;padding:7px 16px;margin:3px 2px 0;
    min-width:100px;max-width:200px;font-size:12px;}}
QTabBar::tab:selected        {{background:{tab_sel};color:{fg};font-weight:600;}}
QTabBar::tab:hover:!selected {{background:{bg3};color:{fg};}}
QTabBar::close-button        {{subcontrol-position:right;}}
QTabBar::close-button:hover  {{background:rgba(220,80,80,.22);border-radius:3px;}}
QStatusBar {{background:{bg2};border-top:1px solid {bd};
    color:{fg2};font-size:11px;padding:1px 8px;}}
QMenuBar {{background:{bg2};border-bottom:1px solid {bd};padding:2px 6px;}}
QMenuBar::item           {{padding:4px 12px;border-radius:5px;color:{fg};}}
QMenuBar::item:selected  {{background:{bg3};}}
QMenu {{background:{bg};border:1px solid {bd};border-radius:10px;
    padding:5px;color:{fg};}}
QMenu::item          {{padding:7px 24px;border-radius:5px;}}
QMenu::item:selected {{background:{ac};color:white;}}
QMenu::separator     {{height:1px;background:{bd};margin:3px 10px;}}
QMenu::indicator     {{width:16px;height:16px;}}
QProgressBar        {{border:none;background:{bd};border-radius:2px;max-height:4px;}}
QProgressBar::chunk {{background:{ac};border-radius:2px;}}
QScrollBar:vertical               {{width:7px;background:transparent;}}
QScrollBar::handle:vertical       {{background:{bd};border-radius:3px;min-height:22px;}}
QScrollBar::handle:vertical:hover {{background:{fg2};}}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
QListWidget {{background:{bg2};border:1px solid {bd};border-radius:8px;
    color:{fg};outline:none;}}
QListWidget::item            {{padding:7px 12px;border-radius:5px;}}
QListWidget::item:selected   {{background:{ac};color:white;}}
QListWidget::item:hover:!selected {{background:{bg3};}}
QLineEdit  {{background:{bg2};border:1.5px solid {bd};border-radius:7px;
    padding:5px 10px;color:{fg};}}
QLineEdit:focus  {{border-color:{ac};}}
QPlainTextEdit {{background:{bg2};border:1px solid {bd};color:{fg};}}
QTextEdit  {{background:{bg2};border:1px solid {bd};color:{fg};}}
QComboBox  {{background:{bg2};border:1.5px solid {bd};border-radius:7px;
    padding:5px 10px;color:{fg};}}
QComboBox QAbstractItemView {{background:{bg};color:{fg};
    selection-background-color:{ac};selection-color:white;border:1px solid {bd};}}
QSpinBox   {{background:{bg2};border:1.5px solid {bd};border-radius:7px;
    padding:5px 8px;color:{fg};}}
QCheckBox  {{spacing:8px;color:{fg};}}
QCheckBox::indicator {{width:17px;height:17px;border:1.5px solid {bd};
    border-radius:4px;background:{bg2};}}
QCheckBox::indicator:checked {{background:{ac};border-color:{ac};}}
QGroupBox {{border:1px solid {bd};border-radius:8px;margin-top:16px;
    padding:12px 8px 8px;color:{fg};}}
QGroupBox::title {{subcontrol-origin:margin;left:12px;padding:0 4px;color:{fg2};}}
QDialogButtonBox QPushButton {{background:{ac};color:white;border:none;
    border-radius:7px;padding:6px 22px;font-weight:600;min-width:80px;}}
QDialogButtonBox QPushButton:hover {{opacity:.85;}}
QPushButton#cancel {{background:{bg3};color:{fg};}}
QFrame#priv_bar {{background:{priv_bg};}}
"""

PALETTES = {
    "Catppuccin Mocha": dict(
        bg="#1e1e2e",bg2="#181825",bg3="#313244",fg="#cdd6f4",fg2="#6c7086",
        ac="#89b4fa",bd="#45475a",tab_bg="#1e1e2e",tab_sel="#313244",priv_bg="#251038"),
    "Catppuccin Latte": dict(
        bg="#eff1f5",bg2="#e6e9ef",bg3="#dce0e8",fg="#4c4f69",fg2="#8c8fa1",
        ac="#1e66f5",bd="#bcc0cc",tab_bg="#e6e9ef",tab_sel="#eff1f5",priv_bg="#e0d4f5"),
    "Firefox Dark": dict(
        bg="#1c1b22",bg2="#2b2a33",bg3="#3d3d4e",fg="#fbfbfe",fg2="#9e9e9e",
        ac="#00ddff",bd="#52525e",tab_bg="#2b2a33",tab_sel="#1c1b22",priv_bg="#2d1e5e"),
    "Firefox Light": dict(
        bg="#f9f9fb",bg2="#ffffff",bg3="#ebebeb",fg="#15141a",fg2="#5b5b66",
        ac="#0060df",bd="#d7d7db",tab_bg="#ebebeb",tab_sel="#ffffff",priv_bg="#e8e0f5"),
    "Nord": dict(
        bg="#2e3440",bg2="#3b4252",bg3="#434c5e",fg="#eceff4",fg2="#9099a7",
        ac="#88c0d0",bd="#4c566a",tab_bg="#2e3440",tab_sel="#3b4252",priv_bg="#2a2050"),
    "Dracula": dict(
        bg="#282a36",bg2="#1e1f29",bg3="#44475a",fg="#f8f8f2",fg2="#6272a4",
        ac="#bd93f9",bd="#44475a",tab_bg="#282a36",tab_sel="#44475a",priv_bg="#1a0f2e"),
    "Tokyo Night": dict(
        bg="#1a1b26",bg2="#16161e",bg3="#24283b",fg="#c0caf5",fg2="#565f89",
        ac="#7aa2f7",bd="#292e42",tab_bg="#1a1b26",tab_sel="#24283b",priv_bg="#1a1030"),
    "Solarized Dark": dict(
        bg="#002b36",bg2="#073642",bg3="#094e5c",fg="#839496",fg2="#657b83",
        ac="#268bd2",bd="#094e5c",tab_bg="#002b36",tab_sel="#073642",priv_bg="#0d0838"),
}

THEME_NAMES = list(PALETTES.keys())

# ── Extension scripts ──────────────────────────────────────────────────────────
DARK_READER_JS = r"""
(function(){
  var id='__pb_dr__';
  if(!document.getElementById(id)){
    var s=document.createElement('style');s.id=id;
    s.textContent='html{filter:invert(90%) hue-rotate(180deg)!important;}' +
      'img,video,iframe,canvas,svg,embed,object,picture{filter:invert(111%) hue-rotate(180deg)!important;}';
    (document.head||document.documentElement).appendChild(s);
  }
})();
"""

RUFFLE_JS = f"""
(function(){{
  if(document.__pb_ruffle__)return;document.__pb_ruffle__=true;
  window.RufflePlayer=window.RufflePlayer||{{}};
  window.RufflePlayer.config={{autoplay:'auto',unmuteOverlay:'hidden'}};
  var s=document.createElement('script');s.src='{RUFFLE_CDN}';
  document.head.appendChild(s);
}})();
"""

# ── New Tab Page ───────────────────────────────────────────────────────────────
SPEED_DIAL = [
    ("Google",    "google.com"),
    ("YouTube",   "youtube.com"),
    ("GitHub",    "github.com"),
    ("Reddit",    "reddit.com"),
    ("Wikipedia", "wikipedia.org"),
    ("DuckDuckGo","duckduckgo.com"),
    ("Twitch",    "twitch.tv"),
    ("X / Twitter","x.com"),
]

def build_newtab_html(dial=None, theme_name="Catppuccin Mocha") -> str:
    p = PALETTES.get(theme_name, PALETTES["Catppuccin Mocha"])
    if dial is None:
        dial = SPEED_DIAL
    tiles_html = "\n".join(
        f"""<a class="tile" href="https://{domain}" title="{name}">
  <img src="https://www.google.com/s2/favicons?sz=96&domain={domain}"
       onerror="this.style.visibility='hidden'" loading="lazy">
  <span>{name}</span>
</a>"""
        for name, domain in dial
    )
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><title>New Tab</title>
<style>
:root{{--bg:{p['bg']};--card:{p['bg2']};--card2:{p['bg3']};--fg:{p['fg']};
  --fg2:{p['fg2']};--ac:{p['ac']};--bd:{p['bd']};}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--fg);
  min-height:100vh;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:28px;padding:40px 20px;}}
#clock{{font-size:72px;font-weight:200;letter-spacing:-3px;line-height:1;opacity:.9}}
#date{{font-size:15px;color:var(--fg2);margin-top:-10px}}
.search{{display:flex;align-items:center;gap:10px;background:var(--card);
  border-radius:32px;box-shadow:0 2px 18px rgba(0,0,0,.15);
  width:min(560px,92vw);padding:7px 10px 7px 20px;}}
.search span{{font-size:18px;opacity:.45}}
.search input{{border:none;outline:none;background:transparent;font-size:15px;
  color:var(--fg);flex:1;padding:5px 0;}}
.search input::placeholder{{color:var(--fg2)}}
.search button{{background:var(--ac);color:white;border:none;border-radius:24px;
  padding:9px 22px;font-size:14px;font-weight:600;cursor:pointer;
  transition:filter .15s;}}
.search button:hover{{filter:brightness(1.12)}}
.tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;
  width:min(560px,92vw);}}
.tile{{background:var(--card);border-radius:14px;
  box-shadow:0 2px 12px rgba(0,0,0,.12);padding:18px 10px 12px;
  display:flex;flex-direction:column;align-items:center;gap:8px;
  cursor:pointer;text-decoration:none;color:var(--fg);font-size:12px;
  font-weight:500;transition:transform .15s,box-shadow .15s;border:none;}}
.tile:hover{{transform:translateY(-4px);box-shadow:0 8px 24px rgba(0,0,0,.18)}}
.tile img{{width:40px;height:40px;border-radius:10px;}}
.hint{{font-size:11px;color:var(--fg2);opacity:.6}}
</style></head><body>
<div id="clock">00:00</div>
<div id="date"></div>
<form class="search" onsubmit="go(event)">
  <span>&#128269;</span>
  <input id="q" type="text" placeholder="Search or enter URL&hellip;" autofocus>
  <button type="submit">Go</button>
</form>
<div class="tiles">{tiles_html}</div>
<p class="hint">Ctrl+T&nbsp;new tab&nbsp;&bull;&nbsp;Ctrl+L&nbsp;address bar&nbsp;&bull;&nbsp;F12&nbsp;devtools&nbsp;&bull;&nbsp;Ctrl+Shift+N&nbsp;private window</p>
<script>
(function tick(){{
  var n=new Date(),h=String(n.getHours()).padStart(2,'0'),m=String(n.getMinutes()).padStart(2,'0');
  document.getElementById('clock').textContent=h+':'+m;
  var D=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  var M=['January','February','March','April','May','June','July','August','September','October','November','December'];
  document.getElementById('date').textContent=D[n.getDay()]+', '+n.getDate()+' '+M[n.getMonth()]+' '+n.getFullYear();
  setTimeout(tick,1000);
}})();
function go(e){{
  e.preventDefault();
  var v=document.getElementById('q').value.trim();if(!v)return;
  var re=/^(https?:\/\/|[a-zA-Z0-9]([a-zA-Z0-9\-]*\\.)+[a-zA-Z]{{2,}})/;
  window.location.href=re.test(v)?(v.startsWith('http')?v:'https://'+v):'https://www.google.com/search?q='+encodeURIComponent(v);
}}
</script></body></html>"""

def swf_player_html(swf_url: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>SWF Player</title>
<script src="{RUFFLE_CDN}"></script>
<style>*{{margin:0;padding:0}}body{{background:#000;display:flex;
align-items:center;justify-content:center;min-height:100vh;}}
#c{{width:100%;height:100vh;}}</style></head>
<body><div id="c"></div>
<script>
window.RufflePlayer=window.RufflePlayer||{{}};
window.RufflePlayer.config={{autoplay:'on',unmuteOverlay:'hidden'}};
window.addEventListener('load',function(){{
  var r=window.RufflePlayer.newest(),p=r.createPlayer();
  p.style.width='100%';p.style.height='100vh';
  document.getElementById('c').appendChild(p);
  p.load('{swf_url}');
}});
</script></body></html>"""

# ── Helpers ────────────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def resolve_url(text: str, search_engine: str) -> str:
    t = text.strip()
    if t == "about:newtab": return t
    if re.match(r"^https?://", t): return t
    if re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*\.)+[a-zA-Z]{2,}(/.*)?$", t):
        return "https://" + t
    return search_engine + quote_plus(t)

def emoji_icon(char: str, color: str = "#888", size: int = 18) -> QIcon:
    px = QPixmap(size, size); px.fill(Qt.transparent)
    p = QPainter(px)
    f = QFont("Segoe UI Emoji"); f.setPixelSize(int(size * .78)); p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, char)
    p.end()
    return QIcon(px)

# ── Custom widgets ─────────────────────────────────────────────────────────────
class NavButton(QToolButton):
    pass

class URLBarEdit(QLineEdit):
    pass

# ── Request interceptor (ad block + HTTPS Everywhere) ─────────────────────────
_has_interceptor = False
try:
    from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor

    class RequestInterceptor(QWebEngineUrlRequestInterceptor):
        def __init__(self):
            super().__init__()
            self.ad_block         = True
            self.https_everywhere = False
            self.domains          = set(AD_DOMAINS)

        def interceptRequest(self, info):
            url = info.requestUrl()
            # HTTPS Everywhere
            if self.https_everywhere and url.scheme() == "http":
                upgraded = QUrl(url); upgraded.setScheme("https")
                try:
                    info.redirect(upgraded)
                except Exception:
                    pass
                return
            # Ad block
            if self.ad_block:
                host = url.host()
                for d in self.domains:
                    if host == d or host.endswith("." + d):
                        info.block(True)
                        return

    _has_interceptor = True
except ImportError:
    RequestInterceptor = None  # type: ignore

def install_interceptor(profile, interceptor):
    for name in ("setUrlRequestInterceptor", "setRequestInterceptor"):
        fn = getattr(profile, name, None)
        if fn:
            fn(interceptor); return

# ── Script injection helpers ───────────────────────────────────────────────────
def make_script(name: str, code: str,
                point=QWebEngineScript.DocumentCreation,
                world=QWebEngineScript.MainWorld) -> QWebEngineScript:
    sc = QWebEngineScript()
    sc.setName(name); sc.setSourceCode(code)
    sc.setInjectionPoint(point); sc.setWorldId(world)
    sc.setRunsOnSubFrames(False)
    return sc

def add_profile_script(profile, name, code, point=QWebEngineScript.DocumentCreation):
    remove_profile_script(profile, name)
    profile.scripts().insert(make_script(name, code, point))

def remove_profile_script(profile, name):
    for sc in profile.scripts().toList():
        if sc.name() == name:
            profile.scripts().remove(sc)

# ── Download Manager ───────────────────────────────────────────────────────────
class DownloadManager(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.resize(660, 460)
        lay = QVBoxLayout(self); lay.setSpacing(10)
        lay.addWidget(QLabel("<b style='font-size:15px'>Downloads</b>"))
        self.list = QListWidget(); lay.addWidget(self.list)
        b = NavButton(); b.setText("Clear completed"); b.clicked.connect(self._clear)
        lay.addWidget(b, alignment=Qt.AlignRight)
        self._items: dict = {}

    def add_download(self, dl):
        name = dl.suggestedFileName()
        try:
            dl.setPath(os.path.join(DOWNLOADS_DIR, name))
        except AttributeError:
            try:
                dl.setDownloadDirectory(DOWNLOADS_DIR)
                dl.setDownloadFileName(name)
            except Exception: pass
        dl.accept()

        w = QWidget(); cl = QVBoxLayout(w); cl.setContentsMargins(10,6,10,6)
        lbl = QLabel(f"⬇  {name}"); prog = QProgressBar(); prog.setRange(0,100)
        cl.addWidget(lbl); cl.addWidget(prog)
        item = QListWidgetItem(self.list); item.setSizeHint(w.sizeHint())
        self.list.addItem(item); self.list.setItemWidget(item, w)
        did = id(dl); self._items[did] = (item, lbl, prog)
        dl.downloadProgress.connect(lambda r,t,d=did,n=name: self._prog(d,r,t,n))
        dl.finished.connect(lambda d=did,n=name: self._done(d,n))
        self.show()

    def _prog(self, did, recv, total, name):
        if did not in self._items: return
        _, lbl, prog = self._items[did]
        if total > 0:
            prog.setValue(int(recv/total*100))
            lbl.setText(f"⬇  {name}  —  {recv//1024} KB / {total//1024} KB")

    def _done(self, did, name):
        if did not in self._items: return
        _, lbl, prog = self._items[did]
        prog.setValue(100); lbl.setText(f"✓  {name}")

    def _clear(self):
        for did, (item,_,prog) in list(self._items.items()):
            if prog.value() == 100:
                self.list.takeItem(self.list.row(item)); del self._items[did]

# ── History Window ─────────────────────────────────────────────────────────────
class HistoryWindow(QDialog):
    open_url = pyqtSignal(str)

    def __init__(self, history: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("History"); self.resize(720, 560)
        self._h = history; self._q = ""
        lay = QVBoxLayout(self); lay.setSpacing(10)
        lay.addWidget(QLabel("<b style='font-size:15px'>History</b>"))
        s = URLBarEdit(); s.setPlaceholderText("Search history…")
        s.textChanged.connect(lambda t: (setattr(self,'_q',t), self._refresh()))
        lay.addWidget(s)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda i: self.open_url.emit(i.data(Qt.UserRole)))
        lay.addWidget(self.list)
        btns = QHBoxLayout()
        for lbl, slot in (("Open",self._open),("Delete",self._delete),("Clear all",self._clear)):
            b = NavButton(); b.setText(lbl); b.clicked.connect(slot); btns.addWidget(b)
        btns.addStretch(); lay.addLayout(btns)
        self._refresh()

    def _refresh(self):
        self.list.clear(); q = self._q.lower()
        for e in reversed(self._h):
            t = e.get("title", e["url"])
            if q and q not in t.lower() and q not in e["url"].lower(): continue
            item = QListWidgetItem(f"  {e['date']}   {t}")
            item.setData(Qt.UserRole, e["url"]); item.setToolTip(e["url"])
            self.list.addItem(item)

    def _open(self):
        [self.open_url.emit(i.data(Qt.UserRole)) for i in self.list.selectedItems()]

    def _delete(self):
        for i in self.list.selectedItems():
            self._h[:] = [e for e in self._h if e["url"] != i.data(Qt.UserRole)]
        self._refresh()

    def _clear(self):
        if QMessageBox.question(self,"Clear History","Delete all history?",
                                QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self._h.clear(); self._refresh()

# ── Bookmark Sidebar ───────────────────────────────────────────────────────────
class BookmarkSidebar(QWidget):
    open_url = pyqtSignal(str)

    def __init__(self, bm: list, parent=None):
        super().__init__(parent)
        self._bm = bm; self.setFixedWidth(240)
        lay = QVBoxLayout(self); lay.setContentsMargins(8,10,8,8); lay.setSpacing(8)
        lay.addWidget(QLabel("<b>Bookmarks</b>"))
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda i: self.open_url.emit(i.data(Qt.UserRole)))
        lay.addWidget(self.list)
        btns = QHBoxLayout()
        for lbl, slot in (("Open",self._open),("Delete",self._delete)):
            b = NavButton(); b.setText(lbl); b.clicked.connect(slot); btns.addWidget(b)
        btns.addStretch(); lay.addLayout(btns); self.refresh()

    def refresh(self):
        self.list.clear()
        for b in self._bm:
            item = QListWidgetItem(b.get("title",b["url"]))
            item.setData(Qt.UserRole, b["url"]); item.setToolTip(b["url"])
            self.list.addItem(item)

    def _open(self):
        [self.open_url.emit(i.data(Qt.UserRole)) for i in self.list.selectedItems()]

    def _delete(self):
        for i in self.list.selectedItems():
            self._bm[:] = [b for b in self._bm if b["url"] != i.data(Qt.UserRole)]
        save_json(BOOKMARKS_F, self._bm); self.refresh()

# ── User Scripts Dialog ────────────────────────────────────────────────────────
class UserScriptsDialog(QDialog):
    def __init__(self, scripts: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Scripts (Tampermonkey-like)")
        self.resize(720, 540); self._scripts = scripts

        lay = QVBoxLayout(self); lay.setSpacing(8)
        lay.addWidget(QLabel("<b style='font-size:14px'>User Scripts</b>"))
        lay.addWidget(QLabel("Injected on pages matching the URL pattern (glob, e.g. *google.com*)"))

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._load_selected)
        lay.addWidget(self.list, 1)

        form = QFormLayout()
        self.name_e    = URLBarEdit(); self.name_e.setPlaceholderText("My Script")
        self.pattern_e = URLBarEdit(); self.pattern_e.setPlaceholderText("*example.com*")
        self.code_e    = QPlainTextEdit()
        self.code_e.setPlaceholderText("// JavaScript injected when URL matches pattern\nconsole.log('hello');")
        font = QFont("Consolas",9); self.code_e.setFont(font)
        form.addRow("Name:",    self.name_e)
        form.addRow("URL pattern:", self.pattern_e)
        form.addRow("Code:",   self.code_e)
        lay.addLayout(form, 2)

        btns = QHBoxLayout()
        b_new  = NavButton(); b_new.setText("New");    b_new.clicked.connect(self._new)
        b_save = NavButton(); b_save.setText("Save");  b_save.clicked.connect(self._save_current)
        b_del  = NavButton(); b_del.setText("Delete"); b_del.clicked.connect(self._delete)
        b_ok   = NavButton(); b_ok.setText("Close");   b_ok.clicked.connect(self.accept)
        for b in (b_new, b_save, b_del, b_ok): btns.addWidget(b)
        btns.addStretch(); lay.addLayout(btns)
        self._refresh_list()

    def _refresh_list(self):
        self.list.clear()
        for s in self._scripts:
            self.list.addItem(QListWidgetItem(
                f"{'✓' if s.get('enabled',True) else '✗'}  {s['name']}  [{s['pattern']}]"))

    def _load_selected(self, row):
        if 0 <= row < len(self._scripts):
            s = self._scripts[row]
            self.name_e.setText(s["name"])
            self.pattern_e.setText(s["pattern"])
            self.code_e.setPlainText(s["code"])

    def _new(self):
        self._scripts.append({"name":"New Script","pattern":"*","code":"","enabled":True})
        self._refresh_list(); self.list.setCurrentRow(len(self._scripts)-1)

    def _save_current(self):
        row = self.list.currentRow()
        if 0 <= row < len(self._scripts):
            self._scripts[row].update({
                "name": self.name_e.text(),
                "pattern": self.pattern_e.text(),
                "code": self.code_e.toPlainText(),
            })
            save_json(USER_SCRIPTS_F, self._scripts); self._refresh_list()

    def _delete(self):
        row = self.list.currentRow()
        if 0 <= row < len(self._scripts):
            del self._scripts[row]
            save_json(USER_SCRIPTS_F, self._scripts); self._refresh_list()

# ── Extensions Dialog ──────────────────────────────────────────────────────────
class ExtensionsDialog(QDialog):
    changed = pyqtSignal()

    EXTENSIONS = [
        ("ad_block",        "uBlock Enhanced",         "🛡",
         "Block ads, trackers, and malware domains (expanded list)"),
        ("dark_reader",     "Dark Reader",             "🌙",
         "Apply dark mode filter to all websites"),
        ("https_everywhere","HTTPS Everywhere",        "🔐",
         "Automatically upgrade HTTP connections to HTTPS"),
        ("ruffle",          "Ruffle Flash Player",     "⚡",
         "Play embedded Flash (SWF) content using the Ruffle emulator"),
    ]

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extensions"); self.resize(620, 480)
        self._s = settings
        lay = QVBoxLayout(self); lay.setSpacing(12)
        lay.addWidget(QLabel("<b style='font-size:15px'>Extensions</b>"))

        self._checks: dict = {}
        for key, name, icon, desc in self.EXTENSIONS:
            row = QFrame(); rl = QHBoxLayout(row); rl.setContentsMargins(12,10,12,10)
            row.setStyleSheet("QFrame{border:1px solid;border-radius:10px;}")
            icon_lbl = QLabel(icon); icon_lbl.setFixedSize(36,36)
            icon_lbl.setAlignment(Qt.AlignCenter)
            icon_lbl.setStyleSheet("font-size:22px;")
            vl = QVBoxLayout()
            vl.addWidget(QLabel(f"<b>{name}</b>"))
            vl.addWidget(QLabel(f"<small>{desc}</small>"))
            cb = QCheckBox()
            cb.setChecked(settings.get(key, True))
            cb.stateChanged.connect(lambda _,k=key,c=cb: self._toggle(k,c))
            self._checks[key] = cb
            rl.addWidget(icon_lbl); rl.addLayout(vl,1); rl.addWidget(cb)
            lay.addWidget(row)

        # User scripts button
        b_us = NavButton(); b_us.setText("⚙  Manage User Scripts (Tampermonkey)")
        b_us.clicked.connect(lambda: self.parent()._open_user_scripts() if self.parent() else None)
        lay.addWidget(b_us); lay.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.accept); lay.addWidget(bb)

    def _toggle(self, key, cb):
        self._s[key] = cb.isChecked()
        self.changed.emit()

# ── Themes Dialog ──────────────────────────────────────────────────────────────
class ThemesDialog(QDialog):
    theme_selected = pyqtSignal(str)

    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Themes"); self.resize(560, 420)
        lay = QVBoxLayout(self); lay.setSpacing(12)
        lay.addWidget(QLabel("<b style='font-size:15px'>Choose a Theme</b>"))

        grid = QGridLayout(); grid.setSpacing(10)
        for i, name in enumerate(THEME_NAMES):
            p = PALETTES[name]
            swatch = QFrame()
            swatch.setFixedHeight(70)
            swatch.setStyleSheet(
                f"background:{p['bg']};border:2px solid "
                f"{'#89b4fa' if name==current else p['bd']};"
                f"border-radius:10px;")
            sl = QVBoxLayout(swatch)
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color:{p['fg']};font-weight:600;font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            sl.addWidget(lbl)
            swatch.mousePressEvent = lambda e, n=name: self._pick(n)
            swatch.setCursor(Qt.PointingHandCursor)
            grid.addWidget(swatch, i//2, i%2)
        lay.addLayout(grid); lay.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.accept); lay.addWidget(bb)

    def _pick(self, name):
        self.theme_selected.emit(name); self.accept()

# ── Clear Data Dialog ──────────────────────────────────────────────────────────
class ClearDataDialog(QDialog):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clear Browsing Data"); self.resize(400, 300)
        self._h = history
        lay = QVBoxLayout(self); lay.setSpacing(12)
        lay.addWidget(QLabel("<b style='font-size:14px'>Clear Browsing Data</b>"))

        self.cb_hist  = QCheckBox("Browsing history");  self.cb_hist.setChecked(True)
        self.cb_cache = QCheckBox("Cache (clears Chromium cache)")
        self.cb_cook  = QCheckBox("Cookies and site data")
        for cb in (self.cb_hist, self.cb_cache, self.cb_cook):
            lay.addWidget(cb)

        lay.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def apply(self, profile):
        if self.cb_hist.isChecked():
            self._h.clear(); save_json(HISTORY_F, self._h)
        if self.cb_cache.isChecked():
            profile.clearHttpCache()
        if self.cb_cook.isChecked():
            profile.cookieStore().deleteAllCookies()

# ── Tab Search Dialog ──────────────────────────────────────────────────────────
class TabSearchDialog(QDialog):
    tab_chosen = pyqtSignal(int)

    def __init__(self, tab_widget, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.resize(440, 320); self._tw = tab_widget
        lay = QVBoxLayout(self); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        self.search = URLBarEdit(); self.search.setPlaceholderText("Search open tabs…")
        self.search.textChanged.connect(self._fill)
        lay.addWidget(self.search)
        self.list = QListWidget()
        self.list.itemActivated.connect(self._pick)
        lay.addWidget(self.list)
        self.search.returnPressed.connect(lambda: self._pick(self.list.currentItem()))
        self._fill()

    def _fill(self, q=""):
        self.list.clear()
        for i in range(self._tw.count()):
            title = self._tw.tabText(i)
            tab = self._tw.widget(i)
            url = tab.view.url().toString() if hasattr(tab,"view") else ""
            if q and q.lower() not in title.lower() and q.lower() not in url.lower():
                continue
            item = QListWidgetItem(f"  {title}\n  {url}")
            item.setData(Qt.UserRole, i); self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _pick(self, item):
        if item:
            self.tab_chosen.emit(item.data(Qt.UserRole)); self.accept()

# ── Settings Dialog ────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, s: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings"); self.resize(520, 420)
        lay = QFormLayout(self); lay.setSpacing(12); lay.setContentsMargins(20,20,20,20)
        lay.addRow(QLabel("<b style='font-size:15px'>Settings</b>"))

        self.homepage = URLBarEdit(s.get("homepage","about:newtab"))
        lay.addRow("Homepage:", self.homepage)

        self.engine = QComboBox()
        for name, url in SEARCH_ENGINES.items(): self.engine.addItem(name, url)
        cur = s.get("search_engine", DEFAULTS["search_engine"])
        if cur in SEARCH_ENGINES.values():
            self.engine.setCurrentIndex(list(SEARCH_ENGINES.values()).index(cur))
        lay.addRow("Search engine:", self.engine)

        self.zoom = QSpinBox(); self.zoom.setRange(25,500); self.zoom.setSuffix(" %")
        self.zoom.setValue(s.get("zoom",100)); lay.addRow("Default zoom:", self.zoom)

        self.restore = QCheckBox("Restore last session on startup")
        self.restore.setChecked(s.get("restore_session",False)); lay.addRow(self.restore)

        self.ua = URLBarEdit(s.get("user_agent",""))
        self.ua.setPlaceholderText("Leave empty for default")
        lay.addRow("User-Agent override:", self.ua)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def result(self) -> dict:
        return {"homepage": self.homepage.text(),
                "search_engine": self.engine.currentData(),
                "zoom": self.zoom.value(),
                "restore_session": self.restore.isChecked(),
                "user_agent": self.ua.text()}

# ── Find Bar ───────────────────────────────────────────────────────────────────
class FindBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(6,3,6,3); lay.setSpacing(4)
        self.input = URLBarEdit(); self.input.setPlaceholderText("Find in page…")
        self.input.returnPressed.connect(self._next)
        self.input.textChanged.connect(self._live)
        self._case = NavButton(); self._case.setText("Aa"); self._case.setCheckable(True)
        self._case.setToolTip("Case sensitive")
        self._result = QLabel(); self._result.setMinimumWidth(80)
        b_prev  = NavButton(); b_prev.setText("▲");  b_prev.clicked.connect(self._prev)
        b_next  = NavButton(); b_next.setText("▼");  b_next.clicked.connect(self._next)
        b_close = NavButton(); b_close.setText("✕"); b_close.clicked.connect(self.hide_bar)
        for w in (QLabel("  Find:"),self.input,self._case,b_prev,b_next,self._result,b_close):
            lay.addWidget(w)
        self.view: QWebEngineView = None  # type: ignore
        self.hide()

    def attach(self, v): self.view = v
    def show_bar(self): self.show(); self.input.setFocus(); self.input.selectAll()
    def hide_bar(self):
        if self.view: self.view.findText("")
        self.hide()

    def _flags(self, bwd=False):
        f = QWebEnginePage.FindFlags()
        if bwd: f |= QWebEnginePage.FindBackward
        if self._case.isChecked(): f |= QWebEnginePage.FindCaseSensitively
        return f

    def _live(self, t):
        if self.view:
            self.view.findText(t, self._flags(),
                lambda ok: self._result.setText("" if ok else "Not found"))

    def _next(self):
        if self.view:
            self.view.findText(self.input.text(), self._flags(),
                lambda ok: self._result.setText("" if ok else "Not found"))

    def _prev(self):
        if self.view:
            self.view.findText(self.input.text(), self._flags(bwd=True),
                lambda ok: self._result.setText("" if ok else "Not found"))

# ── Browser Tab ────────────────────────────────────────────────────────────────
class BrowserTab(QWidget):
    title_changed  = pyqtSignal(str)
    url_changed    = pyqtSignal(str)
    icon_changed   = pyqtSignal(QIcon)
    status_msg     = pyqtSignal(str)
    load_started   = pyqtSignal()
    load_progress  = pyqtSignal(int)
    load_finished  = pyqtSignal(bool)

    def __init__(self, profile, settings_ref: dict, private=False, parent=None):
        super().__init__(parent)
        self._s = settings_ref; self.private = private
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        self.view = QWebEngineView()
        self.view.setPage(QWebEnginePage(profile, self.view))
        ws = self.view.settings()
        for attr in (QWebEngineSettings.JavascriptEnabled,
                     QWebEngineSettings.PluginsEnabled,
                     QWebEngineSettings.FullScreenSupportEnabled,
                     QWebEngineSettings.ScrollAnimatorEnabled,
                     QWebEngineSettings.LocalStorageEnabled):
            ws.setAttribute(attr, True)

        self.view.titleChanged.connect(self.title_changed)
        self.view.urlChanged.connect(lambda u: self.url_changed.emit(u.toString()))
        self.view.iconChanged.connect(self.icon_changed)
        self.view.page().linkHovered.connect(self.status_msg)
        self.view.loadStarted.connect(self.load_started)
        self.view.loadProgress.connect(self.load_progress)
        self.view.loadFinished.connect(self.load_finished)

        self.find_bar = FindBar(); self.find_bar.attach(self.view)
        lay.addWidget(self.view); lay.addWidget(self.find_bar)

    def navigate(self, url: str):
        if url == "about:newtab":
            self.load_new_tab(); return
        u = QUrl(url)
        if not u.scheme(): u = QUrl("https://" + url)
        self.view.load(u)

    def load_new_tab(self, theme="Catppuccin Mocha"):
        html = build_newtab_html(theme_name=theme)
        self.view.setHtml(html, QUrl("about:newtab"))

    def zoom_in(self):   self.view.setZoomFactor(min(5.0, self.view.zoomFactor()+0.1))
    def zoom_out(self):  self.view.setZoomFactor(max(0.25,self.view.zoomFactor()-0.1))
    def zoom_reset(self):self.view.setZoomFactor(self._s.get("zoom",100)/100)

    def toggle_find(self):
        self.find_bar.hide_bar() if self.find_bar.isVisible() else self.find_bar.show_bar()

    def reader_mode(self):
        self.view.page().runJavaScript(r"""(function(){
var id='__pb_rd__';if(document.getElementById(id))return;
var s=document.createElement('style');s.id=id;
s.textContent='body{max-width:760px!important;margin:48px auto!important;'
+'font:1.18rem/1.8 Georgia,serif!important;background:#fdf6e3!important;'
+'color:#333!important;padding:0 24px!important;}'
+'img{max-width:100%!important;}'
+'header,footer,nav,aside,[class*="ad"],[id*="ad"],'
+'[class*="banner"],[class*="cookie"],[class*="sidebar"]{display:none!important;}';
document.head.appendChild(s);})();""")

    def print_page(self):
        p = QPrinter(); dlg = QPrintPreviewDialog(p, self)
        dlg.paintRequested.connect(lambda pr: self.view.page().print(pr, lambda ok: None))
        dlg.exec_()

    def save_page(self):
        path, _ = QFileDialog.getSaveFileName(self,"Save Page","","HTML (*.html);;All (*)")
        if path: self.view.page().save(path)

    def screenshot(self):
        path, _ = QFileDialog.getSaveFileName(self,"Screenshot","","PNG (*.png)")
        if path: self.view.grab().save(path,"PNG")

    def translate_page(self):
        url = self.view.url().toString()
        self.navigate(f"https://translate.google.com/translate?sl=auto&tl=en&u={quote_plus(url)}")

# ── Main Window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, private_window: bool = False):
        super().__init__()
        self._is_private_window = private_window

        self.settings     = {**DEFAULTS, **load_json(SETTINGS_F, {})}
        self.bookmarks    = load_json(BOOKMARKS_F, [])
        self.history      = load_json(HISTORY_F, [])
        self.sessions     = load_json(SESSIONS_F, {})
        self.user_scripts = load_json(USER_SCRIPTS_F, [])
        self._closed_tabs: list = []
        self._is_loading  = False
        self._zoom_timer  = None

        # Profiles
        if private_window:
            self.profile = QWebEngineProfile(self)        # off-the-record
        else:
            self.profile = QWebEngineProfile("PyBrowser", self)

        self.private_profile = QWebEngineProfile(self)    # always off-the-record

        # Interceptor
        self._interceptor = None
        if _has_interceptor:
            self._interceptor = RequestInterceptor()
            self._interceptor.ad_block         = self.settings.get("ad_block", True)
            self._interceptor.https_everywhere = self.settings.get("https_everywhere", False)
            install_interceptor(self.profile, self._interceptor)

        if self.settings.get("user_agent"):
            self.profile.setHttpUserAgent(self.settings["user_agent"])

        self._dl_mgr = DownloadManager(self)
        self.profile.downloadRequested.connect(self._dl_mgr.add_download)
        self.private_profile.downloadRequested.connect(self._dl_mgr.add_download)

        self._build_ui()
        self._apply_theme(self.settings.get("theme", "Catppuccin Mocha"))
        self._apply_all_scripts()

        if private_window:
            self.setWindowTitle("Private Browsing — PyBrowser")
            self.new_tab()
        elif self.settings.get("restore_session") and self.sessions.get("last"):
            for entry in self.sessions["last"]:
                self.new_tab(url=entry.get("url"))
        else:
            self.new_tab()

    # ── Script management ──────────────────────────────────────────────────────
    def _apply_all_scripts(self):
        # Dark Reader
        if self.settings.get("dark_reader"):
            add_profile_script(self.profile, "__pb_dr__", DARK_READER_JS,
                               QWebEngineScript.DocumentReady)
        else:
            remove_profile_script(self.profile, "__pb_dr__")
        # Ruffle
        if self.settings.get("ruffle"):
            add_profile_script(self.profile, "__pb_ruffle__", RUFFLE_JS)
        else:
            remove_profile_script(self.profile, "__pb_ruffle__")
        # User scripts
        for sc in list(self.profile.scripts().toList()):
            if sc.name().startswith("__pb_us_"):
                self.profile.scripts().remove(sc)
        for s in self.user_scripts:
            if s.get("enabled", True) and s.get("code"):
                wrapped = f"""(function(){{
var _url=window.location.href;
if(!_url.match({json.dumps(fnmatch.translate(s.get("pattern","*")))})) return;
{s['code']}
}})();"""
                add_profile_script(self.profile, f"__pb_us_{s['name']}",
                                   wrapped, QWebEngineScript.DocumentReady)

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget(); root.setObjectName("central")
        self.setCentralWidget(root)
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0,0,0,0); root_lay.setSpacing(0)

        self._sidebar = BookmarkSidebar(self.bookmarks)
        self._sidebar.open_url.connect(self._load_in_cur)
        self._sidebar.hide()

        right = QWidget(); rl = QVBoxLayout(right)
        rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)

        # Private indicator bar
        if self._is_private_window:
            priv_bar = QFrame(); priv_bar.setObjectName("priv_bar")
            priv_bar.setFixedHeight(32)
            pl = QHBoxLayout(priv_bar); pl.setContentsMargins(12,0,12,0)
            pl.addWidget(QLabel("🕵"))
            lbl = QLabel("<b>Private Browsing</b> — history and cookies won't be saved")
            lbl.setStyleSheet("color:#d0c0ff;")
            pl.addWidget(lbl); pl.addStretch()
            rl.addWidget(priv_bar)

        self._build_toolbar(rl)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True); self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_tab_switch)
        rl.addWidget(self.tabs)

        btn_plus = NavButton(); btn_plus.setText("+")
        btn_plus.setToolTip("New tab  Ctrl+T"); btn_plus.setFixedSize(30,28)
        btn_plus.clicked.connect(self.new_tab)
        self.tabs.setCornerWidget(btn_plus, Qt.TopRightCorner)

        root_lay.addWidget(self._sidebar)
        root_lay.addWidget(right, 1)

        sb = QStatusBar(); self.setStatusBar(sb)
        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setFixedWidth(48)
        self._zoom_lbl.setAlignment(Qt.AlignCenter)
        self._prog = QProgressBar(); self._prog.setMaximumWidth(240); self._prog.hide()
        sb.addPermanentWidget(self._zoom_lbl)
        sb.addPermanentWidget(self._prog)

        self._build_menubar()
        self._build_shortcuts()

    def _build_toolbar(self, parent_lay):
        self._toolbar = QToolBar(); self._toolbar.setMovable(False)

        def nav(label, tip, slot, checkable=False):
            b = NavButton(); b.setText(label); b.setToolTip(tip)
            b.setFixedSize(34,34); b.setCheckable(checkable)
            b.clicked.connect(slot); return b

        self._btn_back  = nav("◀","Back  Alt+←",     self.go_back)
        self._btn_fwd   = nav("▶","Forward  Alt+→",   self.go_forward)
        self._btn_home  = nav("⌂","Home",             self.go_home)

        # URL bar
        self._url_bar = URLBarEdit()
        self._url_bar.setPlaceholderText("Search or enter URL…")
        self._url_bar.returnPressed.connect(self._navigate_from_bar)
        self._url_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._url_bar.setFixedHeight(34)

        self._sec_action = self._url_bar.addAction(
            emoji_icon("🔒","#4caf50"), QLineEdit.LeadingPosition)
        self._rl_action  = self._url_bar.addAction(
            emoji_icon("↻","#888"), QLineEdit.TrailingPosition)
        self._rl_action.triggered.connect(self._reload_or_stop)

        self._btn_star  = nav("☆","Bookmark  Ctrl+D", self.toggle_bookmark)
        self._btn_dark  = nav("🌙","Toggle site dark mode", self._toggle_dark_reader, checkable=True)
        self._btn_dark.setChecked(self.settings.get("dark_reader",False))
        self._btn_dark.setToolTip("Dark mode for websites")

        for w in (self._btn_back,self._btn_fwd,self._btn_home):
            self._toolbar.addWidget(w)
        self._toolbar.addWidget(self._url_bar)
        self._toolbar.addWidget(self._btn_star)
        self._toolbar.addWidget(self._btn_dark)
        parent_lay.addWidget(self._toolbar)

    def _build_menubar(self):
        mb = self.menuBar()

        def act(menu, label, sc, slot, checkable=False):
            a = QAction(label, self)
            if sc: a.setShortcut(sc)
            a.setCheckable(checkable); a.triggered.connect(slot)
            menu.addAction(a); return a

        # File
        fm = mb.addMenu("File")
        act(fm,"New Tab",              "Ctrl+T",       self.new_tab)
        act(fm,"New Private Tab",      "Ctrl+Shift+P", lambda: self.new_tab(private=True))
        act(fm,"New Private Window",   "Ctrl+Shift+N", self.open_private_window)
        act(fm,"Close Tab",            "Ctrl+W",       lambda: self.close_tab(self.tabs.currentIndex()))
        act(fm,"Reopen Closed Tab",    "Ctrl+Shift+T", self._restore_closed_tab)
        fm.addSeparator()
        act(fm,"Save Page",            "Ctrl+S",       lambda: (t:=self._cur()) and t.save_page())
        act(fm,"Screenshot",           "Ctrl+Shift+S", lambda: (t:=self._cur()) and t.screenshot())
        act(fm,"Print",                "Ctrl+P",       lambda: (t:=self._cur()) and t.print_page())
        fm.addSeparator()
        act(fm,"Quit",                 "Ctrl+Q",       self.close)

        # Edit
        em = mb.addMenu("Edit")
        act(em,"Find in Page",         "Ctrl+F",       lambda: (t:=self._cur()) and t.toggle_find())
        em.addSeparator()
        act(em,"Select All",           "Ctrl+A",
            lambda: self._cur() and self._cur().view.page().triggerAction(QWebEnginePage.SelectAll))
        act(em,"Copy",                 "Ctrl+C",
            lambda: self._cur() and self._cur().view.page().triggerAction(QWebEnginePage.Copy))

        # View
        vm = mb.addMenu("View")
        act(vm,"Zoom In",              "Ctrl+=",       lambda: (t:=self._cur()) and t.zoom_in())
        act(vm,"Zoom Out",             "Ctrl+-",       lambda: (t:=self._cur()) and t.zoom_out())
        act(vm,"Reset Zoom",           "Ctrl+0",       lambda: (t:=self._cur()) and t.zoom_reset())
        vm.addSeparator()
        act(vm,"Full Screen",          "F11",          self.toggle_fullscreen)
        vm.addSeparator()
        act(vm,"Bookmarks Sidebar",    "Ctrl+B",       self.toggle_sidebar)
        act(vm,"Reader Mode",          "Alt+R",        lambda: (t:=self._cur()) and t.reader_mode())
        act(vm,"Translate Page",       "Alt+T",        lambda: (t:=self._cur()) and t.translate_page())
        vm.addSeparator()
        self._dark_menu_act = act(vm,"Site Dark Mode (Dark Reader)","Alt+D",
                                  self._toggle_dark_reader, checkable=True)
        self._dark_menu_act.setChecked(self.settings.get("dark_reader",False))

        # History
        hm = mb.addMenu("History")
        act(hm,"Show History",         "Ctrl+H",       self.show_history)
        act(hm,"Clear Browsing Data",  "Ctrl+Shift+Delete", self.show_clear_data)
        hm.addSeparator()
        act(hm,"Save Session",         "",             lambda: self._save_session("last"))
        act(hm,"Restore Session",      "",             self._restore_session_dialog)

        # Bookmarks
        bkm = mb.addMenu("Bookmarks")
        act(bkm,"Bookmark This Page",  "Ctrl+D",       self.toggle_bookmark)
        act(bkm,"Bookmarks Sidebar",   "Ctrl+Shift+B", self.toggle_sidebar)

        # Flash
        flm = mb.addMenu("Flash")
        self._ruffle_act = flm.addAction("Enable Ruffle Flash emulation")
        self._ruffle_act.setCheckable(True)
        self._ruffle_act.setChecked(self.settings.get("ruffle",True))
        self._ruffle_act.triggered.connect(self._toggle_ruffle)
        flm.addSeparator()
        act(flm,"Open SWF File…",      "Ctrl+Shift+F", self.open_swf)

        # Tools
        tm = mb.addMenu("Tools")
        act(tm,"Downloads",            "Ctrl+J",       self._dl_mgr.show)
        act(tm,"Extensions",           "Ctrl+Shift+E", self.show_extensions)
        act(tm,"Themes",               "",             self.show_themes)
        act(tm,"User Scripts",         "",             self._open_user_scripts)
        act(tm,"Tab Search",           "Ctrl+Shift+A", self.show_tab_search)
        tm.addSeparator()
        act(tm,"Settings",             "Ctrl+,",       self.show_settings)
        tm.addSeparator()
        act(tm,"Developer Tools",      "F12",          self.open_devtools)
        act(tm,"View Page Source",     "Ctrl+U",       self._view_source)
        act(tm,"Page Info",            "Ctrl+I",       self.show_page_info)

    def _build_shortcuts(self):
        sc = QShortcut
        # Navigation
        sc(QKeySequence("Alt+Left"),   self).activated.connect(self.go_back)
        sc(QKeySequence("Alt+Right"),  self).activated.connect(self.go_forward)
        sc(QKeySequence("F5"),         self).activated.connect(self.reload)
        sc(QKeySequence("Ctrl+R"),     self).activated.connect(self.reload)
        sc(QKeySequence("Ctrl+Shift+R"),self).activated.connect(self._hard_reload)
        sc(QKeySequence("Ctrl+L"),     self).activated.connect(self._focus_bar)
        sc(QKeySequence("F6"),         self).activated.connect(self._focus_bar)
        sc(QKeySequence("Alt+Home"),   self).activated.connect(self.go_home)
        sc(QKeySequence("Escape"),     self).activated.connect(self.stop_load)
        sc(QKeySequence("Ctrl+Enter"), self).activated.connect(self._nav_dotcom)
        # Tabs
        sc(QKeySequence("Ctrl+Tab"),        self).activated.connect(self._next_tab)
        sc(QKeySequence("Ctrl+Shift+Tab"),  self).activated.connect(self._prev_tab)
        sc(QKeySequence("Ctrl+Shift+T"),    self).activated.connect(self._restore_closed_tab)
        for i in range(1,9):
            sc(QKeySequence(f"Ctrl+{i}"),self).activated.connect(
                lambda _,n=i-1: self.tabs.setCurrentIndex(n))
        sc(QKeySequence("Ctrl+9"),self).activated.connect(
            lambda: self.tabs.setCurrentIndex(self.tabs.count()-1))
        # Zoom
        sc(QKeySequence("Ctrl++"),self).activated.connect(
            lambda: (t:=self._cur()) and t.zoom_in())
        sc(QKeySequence("Ctrl+-"),self).activated.connect(
            lambda: (t:=self._cur()) and t.zoom_out())
        sc(QKeySequence("Ctrl+0"),self).activated.connect(
            lambda: (t:=self._cur()) and t.zoom_reset())
        # Other
        sc(QKeySequence("Ctrl+Shift+A"),self).activated.connect(self.show_tab_search)
        sc(QKeySequence("Ctrl+Shift+N"),self).activated.connect(self.open_private_window)
        sc(QKeySequence("Ctrl+Shift+Delete"),self).activated.connect(self.show_clear_data)

    # ── Tab management ─────────────────────────────────────────────────────────
    def new_tab(self, url: str = None, private: bool = False) -> BrowserTab:
        profile = self.private_profile if (private or self._is_private_window) else self.profile
        tab = BrowserTab(profile, self.settings, private=private or self._is_private_window)
        tab.title_changed.connect(lambda t, _t=tab: self._set_title(_t,t))
        tab.icon_changed.connect( lambda ic, _t=tab: self._set_icon(_t,ic))
        tab.url_changed.connect(  lambda u,  _t=tab: self._on_url(_t,u))
        tab.status_msg.connect(   lambda m: self.statusBar().showMessage(m,2500))
        tab.load_started.connect( lambda _t=tab: self._on_start(_t))
        tab.load_progress.connect(self._prog.setValue)
        tab.load_finished.connect(lambda ok, _t=tab: self._on_done(_t,ok))

        label = "🕵 Private" if (private or self._is_private_window) else "New Tab"
        idx = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(idx)

        if url:
            tab.navigate(url)
        else:
            theme = self.settings.get("theme","Catppuccin Mocha")
            tab.load_new_tab(theme)
        return tab

    def close_tab(self, idx: int):
        tab = self.tabs.widget(idx)
        if isinstance(tab, BrowserTab):
            url = tab.view.url().toString()
            title = tab.view.title()
            if url not in ("","about:newtab","about:blank"):
                self._closed_tabs.append((url,title))
                if len(self._closed_tabs) > 30: self._closed_tabs.pop(0)
        if self.tabs.count() <= 1: self.close(); return
        w = self.tabs.widget(idx); self.tabs.removeTab(idx); w.deleteLater()

    def _cur(self) -> BrowserTab:
        return self.tabs.currentWidget()

    def _next_tab(self):
        n = (self.tabs.currentIndex()+1) % self.tabs.count()
        self.tabs.setCurrentIndex(n)

    def _prev_tab(self):
        n = (self.tabs.currentIndex()-1) % self.tabs.count()
        self.tabs.setCurrentIndex(n)

    def _restore_closed_tab(self):
        if self._closed_tabs:
            url, _ = self._closed_tabs.pop()
            self.new_tab(url=url)

    def _on_tab_switch(self, idx: int):
        tab = self.tabs.widget(idx)
        if not isinstance(tab, BrowserTab): return
        url = tab.view.url().toString()
        self._url_bar.setText("" if url in ("about:newtab","about:blank","") else url)
        self._update_sec_icon(url)
        self._update_star(url)
        self._update_zoom_label(tab.view.zoomFactor())

    def _set_title(self, tab, title):
        idx = self.tabs.indexOf(tab)
        if idx < 0: return
        short = (title[:22]+"…") if len(title)>25 else title
        pfx = "🕵 " if (tab.private or self._is_private_window) else ""
        self.tabs.setTabText(idx, pfx+short)
        if tab is self._cur(): self.setWindowTitle(f"{title} — PyBrowser")

    def _set_icon(self, tab, icon):
        idx = self.tabs.indexOf(tab)
        if idx >= 0 and not icon.isNull(): self.tabs.setTabIcon(idx, icon)

    def _on_url(self, tab, url):
        if tab is self._cur():
            self._url_bar.setText("" if url in ("about:newtab","about:blank","") else url)
            self._update_sec_icon(url); self._update_star(url)
        if url and url not in ("","about:blank","about:newtab") and not tab.private:
            self._push_history(url, tab.view.title())

    def _on_start(self, tab):
        if tab is self._cur():
            self._is_loading = True
            self._rl_action.setIcon(emoji_icon("✕","#e55"))
            self._prog.show(); self._prog.setValue(0)

    def _on_done(self, tab, _ok):
        if tab is self._cur():
            self._is_loading = False
            self._rl_action.setIcon(emoji_icon("↻","#888"))
            self._prog.hide()
        tab.view.setZoomFactor(self.settings.get("zoom",100)/100)
        if tab is self._cur():
            self._update_zoom_label(tab.view.zoomFactor())

    def _update_sec_icon(self, url):
        if url.startswith("https://"):
            self._sec_action.setIcon(emoji_icon("🔒","#4caf50"))
        elif url.startswith("http://"):
            self._sec_action.setIcon(emoji_icon("⚠","#ff9800"))
        else:
            self._sec_action.setIcon(emoji_icon("ℹ","#aaa"))

    def _update_zoom_label(self, factor):
        self._zoom_lbl.setText(f"{int(factor*100)}%")

    # ── Navigation ─────────────────────────────────────────────────────────────
    def _navigate_from_bar(self):
        text = self._url_bar.text().strip()
        if not text: return
        tab = self._cur()
        if tab: tab.navigate(resolve_url(text, self.settings["search_engine"]))

    def _reload_or_stop(self):
        if self._is_loading: self.stop_load()
        else: self.reload()

    def _hard_reload(self):
        if t := self._cur():
            t.view.page().triggerAction(QWebEnginePage.ReloadAndBypassCache)

    def _load_in_cur(self, url):
        if t := self._cur(): t.navigate(url)

    def _nav_dotcom(self):
        text = self._url_bar.text().strip()
        if text and "." not in text:
            self._url_bar.setText("www."+text+".com")
        self._navigate_from_bar()

    def go_back(self):
        if t := self._cur(): t.view.back()

    def go_forward(self):
        if t := self._cur(): t.view.forward()

    def reload(self):
        if t := self._cur(): t.view.reload()

    def stop_load(self):
        if t := self._cur(): t.view.stop()

    def go_home(self):
        hp = self.settings.get("homepage","about:newtab")
        if t := self._cur(): t.navigate(hp)

    def _focus_bar(self):
        self._url_bar.setFocus(); self._url_bar.selectAll()

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # ── Bookmarks ──────────────────────────────────────────────────────────────
    def toggle_bookmark(self):
        tab = self._cur()
        if not tab: return
        url = tab.view.url().toString(); title = tab.view.title() or url
        if any(b["url"]==url for b in self.bookmarks):
            self.bookmarks[:] = [b for b in self.bookmarks if b["url"]!=url]
            self._btn_star.setText("☆")
            self.statusBar().showMessage("Bookmark removed",2000)
        else:
            self.bookmarks.append({"url":url,"title":title,
                "date":datetime.now().strftime("%Y-%m-%d")})
            self._btn_star.setText("★")
            self.statusBar().showMessage(f"Bookmarked: {title}",2000)
        save_json(BOOKMARKS_F,self.bookmarks); self._sidebar.refresh()

    def _update_star(self, url):
        self._btn_star.setText("★" if any(b["url"]==url for b in self.bookmarks) else "☆")

    def toggle_sidebar(self):
        self._sidebar.setVisible(not self._sidebar.isVisible())

    # ── History ────────────────────────────────────────────────────────────────
    def _push_history(self, url, title):
        if self.history and self.history[-1]["url"]==url: return
        self.history.append({"url":url,"title":title or url,
            "date":datetime.now().strftime("%Y-%m-%d %H:%M")})
        if len(self.history)>5000: self.history=self.history[-5000:]
        save_json(HISTORY_F,self.history)

    def show_history(self):
        win = HistoryWindow(self.history, self)
        win.open_url.connect(self._load_in_cur); win.exec_()
        save_json(HISTORY_F,self.history)

    def show_clear_data(self):
        dlg = ClearDataDialog(self.history, self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply(self.profile)
            self.statusBar().showMessage("Browsing data cleared",2000)

    # ── Sessions ───────────────────────────────────────────────────────────────
    def _save_session(self, name="last"):
        entries = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab,BrowserTab):
                url = tab.view.url().toString()
                if url not in ("","about:newtab","about:blank"):
                    entries.append({"url":url,"title":tab.view.title()})
        self.sessions[name] = entries
        save_json(SESSIONS_F,self.sessions)
        self.statusBar().showMessage(f"Session saved ({len(entries)} tabs)",2000)

    def _restore_session_dialog(self):
        names = [k for k in self.sessions if self.sessions[k]]
        if not names:
            QMessageBox.information(self,"Sessions","No saved sessions found."); return
        name, ok = QComboBox(), False
        dlg = QDialog(self); dlg.setWindowTitle("Restore Session")
        lay = QVBoxLayout(dlg); lay.addWidget(QLabel("Choose session:"))
        cb = QComboBox()
        for n in names: cb.addItem(n)
        lay.addWidget(cb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec_() == QDialog.Accepted:
            for entry in self.sessions.get(cb.currentText(),[]):
                self.new_tab(url=entry.get("url"))

    # ── Extensions & Scripts ───────────────────────────────────────────────────
    def show_extensions(self):
        dlg = ExtensionsDialog(self.settings, self)
        dlg.changed.connect(self._on_extension_changed)
        dlg.exec_()
        save_json(SETTINGS_F, self.settings)

    def _on_extension_changed(self):
        if self._interceptor:
            self._interceptor.ad_block         = self.settings.get("ad_block",True)
            self._interceptor.https_everywhere = self.settings.get("https_everywhere",False)
        # Dark reader / ruffle need script re-apply
        self._apply_all_scripts()
        self._btn_dark.setChecked(self.settings.get("dark_reader",False))
        self._dark_menu_act.setChecked(self.settings.get("dark_reader",False))
        if hasattr(self,"_ruffle_act"):
            self._ruffle_act.setChecked(self.settings.get("ruffle",True))

    def _toggle_dark_reader(self, checked=None):
        new_val = not self.settings.get("dark_reader",False) if checked is None else checked
        self.settings["dark_reader"] = new_val
        self._btn_dark.setChecked(new_val)
        self._dark_menu_act.setChecked(new_val)
        self._apply_all_scripts()
        save_json(SETTINGS_F,self.settings)
        msg = "Site dark mode ON — reload pages" if new_val else "Site dark mode OFF"
        self.statusBar().showMessage(msg,2500)

    def _toggle_ruffle(self, checked):
        self.settings["ruffle"] = checked
        self._apply_all_scripts()
        save_json(SETTINGS_F,self.settings)

    def _open_user_scripts(self):
        dlg = UserScriptsDialog(self.user_scripts, self)
        dlg.exec_()
        save_json(USER_SCRIPTS_F,self.user_scripts)
        self._apply_all_scripts()

    # ── Themes ─────────────────────────────────────────────────────────────────
    def show_themes(self):
        cur = self.settings.get("theme","Catppuccin Mocha")
        dlg = ThemesDialog(cur, self)
        dlg.theme_selected.connect(self._apply_theme)
        dlg.exec_()

    def _apply_theme(self, name: str):
        p = PALETTES.get(name, PALETTES["Catppuccin Mocha"])
        QApplication.instance().setStyleSheet(make_qss(p))
        self.settings["theme"] = name
        save_json(SETTINGS_F,self.settings)
        # Reload new tab pages to reflect theme
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab,BrowserTab):
                url = tab.view.url().toString()
                if url in ("about:newtab","about:blank",""):
                    tab.load_new_tab(name)

    # ── Settings ───────────────────────────────────────────────────────────────
    def show_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_() == QDialog.Accepted:
            self.settings.update(dlg.result())
            if self.settings.get("user_agent"):
                self.profile.setHttpUserAgent(self.settings["user_agent"])
            save_json(SETTINGS_F,self.settings)
            self.statusBar().showMessage("Settings saved",2000)

    # ── Flash ──────────────────────────────────────────────────────────────────
    def open_swf(self):
        path, _ = QFileDialog.getOpenFileName(self,"Open SWF","","Flash File (*.swf)")
        if not path: return
        swf_url = QUrl.fromLocalFile(path).toString()
        base    = QUrl.fromLocalFile(os.path.dirname(path)+"/")
        tab = self.new_tab(); tab.view.setHtml(swf_player_html(swf_url), base)
        self.tabs.setTabText(self.tabs.indexOf(tab), "▶ "+os.path.basename(path))

    # ── Private window ─────────────────────────────────────────────────────────
    def open_private_window(self):
        win = MainWindow(private_window=True)
        win.resize(1200, 800); win.show()
        app = QApplication.instance()
        if not hasattr(app,"_private_wins"): app._private_wins = []
        app._private_wins.append(win)

    # ── Devtools, source, page info ────────────────────────────────────────────
    def open_devtools(self):
        tab = self._cur()
        if not tab: return
        dev = QWebEngineView()
        tab.view.page().setDevToolsPage(dev.page())
        dlg = QDialog(self); dlg.setWindowTitle("Developer Tools"); dlg.resize(1100,660)
        lay = QVBoxLayout(dlg); lay.addWidget(dev); dlg.show()

    def _view_source(self):
        if t := self._cur(): t.view.page().toHtml(self._show_source_win)

    def _show_source_win(self, html):
        dlg = QDialog(self); dlg.setWindowTitle("Page Source"); dlg.resize(920,660)
        lay = QVBoxLayout(dlg)
        te = QTextEdit(); te.setReadOnly(True); te.setPlainText(html)
        te.setFont(QFont("Consolas",10)); lay.addWidget(te); dlg.show()

    def show_page_info(self):
        tab = self._cur()
        if not tab: return
        url  = tab.view.url().toString()
        title= tab.view.title()
        is_secure = url.startswith("https://")
        msg = (f"<b>Title:</b> {title}<br>"
               f"<b>URL:</b> {url}<br>"
               f"<b>Connection:</b> {'🔒 Secure (HTTPS)' if is_secure else '⚠ Not secure (HTTP)'}<br>"
               f"<b>Zoom:</b> {int(tab.view.zoomFactor()*100)}%")
        QMessageBox.information(self,"Page Info",msg)

    def show_tab_search(self):
        dlg = TabSearchDialog(self.tabs, self)
        dlg.tab_chosen.connect(self.tabs.setCurrentIndex)
        # Center over window
        pos = self.frameGeometry().center() - dlg.rect().center()
        dlg.move(pos); dlg.exec_()

    # ── Persistence ────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self.settings.get("restore_session") and not self._is_private_window:
            self._save_session("last")
        save_json(BOOKMARKS_F, self.bookmarks)
        save_json(HISTORY_F,   self.history)
        save_json(SESSIONS_F,  self.sessions)
        save_json(SETTINGS_F,  self.settings)
        event.accept()

# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
        "--enable-gpu-rasterization --enable-zero-copy")

    app = QApplication(sys.argv)
    app.setApplicationName("PyBrowser")
    app.setStyle("Fusion")
    f = app.font(); f.setFamily("Segoe UI"); f.setPointSize(10); app.setFont(f)

    win = MainWindow()
    win.resize(1300, 840)
    win.show()
    sys.exit(app.exec_())
