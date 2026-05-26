#!/usr/bin/env python3
"""
ES-Browser v4
Install: pip install PyQt5 PyQtWebEngine
Run:     python ES-Browser.py
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
from PyQt5.QtCore import Qt, QUrl, QSize, QRect, pyqtSignal, QTimer, QPoint, QEvent, QObject
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

# Chrome 120 UA — без него YouTube / Google видят «неизвестный браузер» и режут JS
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# JS для защиты от утечки реального IP через WebRTC
WEBRTC_PROTECTION_JS = """
(function(){
  // Whitelist: X.com/Twitter детектирует любые изменения RTCPeerConnection
  var h=location.hostname;
  if(h==='x.com'||h==='twitter.com'||h.endsWith('.x.com')||h.endsWith('.twitter.com'))return;

  if(typeof RTCPeerConnection==='undefined')return;
  var _orig=RTCPeerConnection;

  function _patch(cfg){
    if(!cfg)return{};
    var c=Object.assign({},cfg);
    if(c.iceServers){
      var t=c.iceServers.filter(function(s){
        return [].concat(s.urls||[]).some(function(u){return u&&u.indexOf('turn:')===0;});
      });
      c.iceServers=t;
    }
    return c;
  }

  try{
    var _p=new Proxy(_orig,{
      construct:function(T,a){return Reflect.construct(T,[_patch(a[0])].concat(Array.from(a).slice(1)));},
      get:function(T,k,R){
        if(k==='toString')return function(){return 'function RTCPeerConnection() { [native code] }';};
        if(k==='name')return 'RTCPeerConnection';
        return Reflect.get(T,k,R);
      }
    });
    Object.defineProperty(window,'RTCPeerConnection',{value:_p,writable:true,configurable:true,enumerable:false});
    if(window.webkitRTCPeerConnection)Object.defineProperty(window,'webkitRTCPeerConnection',{value:_p,writable:true,configurable:true,enumerable:false});
  }catch(e){}
})();
"""

# Паттерны опасных URL для Safe Browsing (базовый список)
SAFE_BROWSING_PATTERNS = [
    r"(?:password|passwd|credential|login)[_-]?(?:stealer|dump|hack)",
    r"(?:free[_-]?(?:v[_-]?bucks?|robux|gems?|coins?)|gift[_-]?card[_-]?gen)",
    r"(?:ransomware|cryptolocker|wannacry|petya)",
    r"(?:phish(?:ing)?|pharming)[_-]?(?:kit|page|site)",
    r"(?:\.(?:tk|ml|ga|cf|gq|pw|top|click|download))/.*(?:login|signin|account|verify|secure|update|password)",
    r"(?:bit\.ly|tinyurl\.com|goo\.gl|t\.co)/[a-zA-Z0-9]{4,8}$",  # подозрительные сокращения без пути
]

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
    "downloads_dir":     DOWNLOADS_DIR,
    "javascript":        True,
    "block_popups":      True,
    "lang":              "en_US",
    # ── Безопасность ──────────────────────────────────────────────────────────
    "block_mixed_content":       True,   # HTTP-ресурсы на HTTPS-странице → заблокировать
    "webrtc_protection":         True,   # Предотвратить утечку IP через WebRTC
    "dnt":                       True,   # Заголовок Do Not Track
    "referrer_policy":           "strict-origin",  # full / strict-origin / no-referrer
    "safe_browsing":             True,   # Блокировать подозрительные URL
    "permission_camera":         "ask",  # ask / deny / allow
    "permission_mic":            "ask",
    "permission_location":       "deny",
    "permission_notifications":  "ask",
}

# ── i18n ───────────────────────────────────────────────────────────────────────
STRINGS = {
    "en_US": {
        # Menus
        "menu_file": "File", "menu_new_tab": "New Tab",
        "menu_new_priv_tab": "New Private Tab",
        "menu_new_priv_win": "New Private Window",
        "menu_close_tab": "Close Tab",
        "menu_reopen_tab": "Reopen Closed Tab",
        "menu_save_page": "Save Page", "menu_screenshot": "Screenshot",
        "menu_print": "Print", "menu_quit": "Quit",
        "menu_edit": "Edit", "menu_find": "Find in Page",
        "menu_select_all": "Select All", "menu_copy": "Copy",
        "menu_view": "View", "menu_zoom_in": "Zoom In",
        "menu_zoom_out": "Zoom Out", "menu_zoom_reset": "Reset Zoom",
        "menu_fullscreen": "Full Screen",
        "menu_bm_sidebar": "Bookmarks Sidebar",
        "menu_reader": "Reader Mode", "menu_translate": "Translate Page",
        "menu_dark_mode": "Site Dark Mode (Dark Reader)",
        "menu_history": "History", "menu_show_history": "Show History",
        "menu_clear_data": "Clear Browsing Data",
        "menu_save_session": "Save Session",
        "menu_restore_session": "Restore Session",
        "menu_bookmarks": "Bookmarks",
        "menu_bm_page": "Bookmark This Page",
        "menu_flash": "Flash",
        "menu_ruffle": "Enable Ruffle Flash emulation",
        "menu_open_swf": "Open SWF File…",
        "menu_tools": "Tools", "menu_downloads": "Downloads",
        "menu_extensions": "Extensions", "menu_themes": "Themes",
        "menu_user_scripts": "User Scripts",
        "menu_tab_search": "Tab Search", "menu_settings": "Settings",
        "menu_devtools": "Developer Tools",
        "menu_view_source": "View Page Source",
        "menu_page_info": "Page Info",
        "menu_help": "Help", "menu_about": "About ES-Browser",
        # Toolbar
        "tip_back": "Back  Alt+←", "tip_forward": "Forward  Alt+→",
        "tip_home": "Home",
        "url_ph": "Search or enter URL…",
        "tip_bookmark": "Bookmark  Ctrl+D",
        "tip_dark": "Toggle site dark mode",
        "tip_new_tab": "New tab  Ctrl+T",
        # Tabs
        "tab_new": "New Tab", "tab_private": "\U0001f575 Private",
        # Status bar
        "st_bookmarked": "Bookmarked: {0}",
        "st_bm_removed": "Bookmark removed",
        "st_dark_on": "Site dark mode ON — reload pages",
        "st_dark_off": "Site dark mode OFF",
        "st_settings_saved": "Settings saved",
        "st_data_cleared": "Browsing data cleared",
        "st_session_saved": "Session saved ({0} tabs)",
        # Settings dialog
        "set_title": "Settings",
        "set_sec_general": "General", "set_sec_content": "Content",
        "set_sec_advanced": "Advanced",
        "set_homepage": "Homepage:", "set_hp_newtab": "New Tab (built-in)",
        "set_hp_custom": "Custom URL:", "set_engine": "Search engine:",
        "set_zoom": "Default zoom:", "set_restore": "Restore last session on startup",
        "set_dl_folder": "Downloads folder:", "set_lang": "Language:",
        "set_js": "Enable JavaScript",
        "set_popups": "Block pop-up windows",
        "set_dark": "Dark Reader  (site-wide dark mode)",
        "set_ua": "User-Agent override:",
        "set_ua_ph": "Leave empty for Chrome 120 default",
        "set_lang_restart": "Language change will take effect after restarting ES-Browser.",
        # Private window bar
        "priv_bar": "<b>Private Browsing</b> — history and cookies won’t be saved",
        # Dialogs common
        "dlg_ok": "OK", "dlg_cancel": "Cancel", "dlg_close": "Close",
        "dlg_open": "Open", "dlg_delete": "Delete",
        "dlg_clear_done": "Clear completed", "dlg_clear_all": "Clear all",
        "dlg_new": "New", "dlg_save": "Save",
        # History
        "hist_title": "History", "hist_search_ph": "Search history…",
        # Downloads
        "dl_title": "Downloads",
        # Clear data
        "clr_title": "Clear Browsing Data",
        "clr_history": "Browsing history",
        "clr_cache": "Cache (clears Chromium cache)",
        "clr_cookies": "Cookies and site data",
        # Page info
        "pi_title": "Page Info",
        "pi_secure": "\U0001f512 Secure (HTTPS)",
        "pi_insecure": "⚠ Not secure (HTTP)",
        # Sessions
        "sess_title": "Restore Session", "sess_choose": "Choose session:",
        "sess_none": "No saved sessions found.",
        # Find bar
        "find_label": "  Find:", "find_ph": "Find in page…",
        "find_not_found": "Not found", "find_case": "Case sensitive",
        # Bookmarks sidebar
        "bm_title": "Bookmarks",
        # History confirm
        "hist_confirm_title": "Clear History", "hist_confirm_msg": "Delete all history?",
        # User Scripts
        "us_title": "User Scripts",
        "us_hint": "Injected on pages matching the URL pattern (glob, e.g. *google.com*)",
        "us_manage": "⚙️  Manage User Scripts (Tampermonkey)",
        "us_form_name": "Name:", "us_form_pattern": "URL pattern:", "us_form_code": "Code:",
        # Extensions / Themes
        "ext_title": "Extensions",
        "themes_title": "Themes", "themes_choose": "Choose a Theme",
        # Tab search
        "tab_search_ph": "Search open tabs…",
        # Window titles
        "priv_win_title": "Private Browsing — ES-Browser",
        "devtools_title": "Developer Tools", "pagesrc_title": "Page Source",
        # Security settings
        "set_sec_security": "Security",
        "set_mixed":   "Block mixed content (HTTP resources on HTTPS pages)",
        "set_webrtc":  "WebRTC IP leak protection",
        "set_dnt":     "Send Do Not Track (DNT) header",
        "set_referrer": "Referrer policy:",
        "set_safe_browsing": "Safe browsing (block dangerous URLs)",
        "set_cam":     "Camera:", "set_mic": "Microphone:",
        "set_loc":     "Location:", "set_notif": "Notifications:",
        "perm_ask": "Ask", "perm_deny": "Deny", "perm_allow": "Allow",
        "ref_full":   "Full URL",
        "ref_origin": "Origin only (recommended)",
        "ref_none":   "No referrer",
        "sb_title": "Dangerous Site Warning",
        "sb_msg": "The site {0} matches a known dangerous pattern.\n\nProceed anyway?",
        "perm_cam": "Camera", "perm_mic": "Microphone",
        "perm_cam_mic": "Camera + Microphone",
        "perm_geo": "Location", "perm_notif": "Notifications",
        "perm_ask_title": "Permission Request",
        "perm_ask_msg": "{0} wants access to {1}.\n\nAllow?",
        # New tab
        "newtab_go": "Go",
        "newtab_ph": "Search or enter URL…",
        "newtab_hint": "Ctrl+T new tab • Ctrl+L address bar • F12 devtools • Ctrl+Shift+N private window",
    },
    "ru_RU": {
        # Меню
        "menu_file": "Файл", "menu_new_tab": "Новая вкладка",
        "menu_new_priv_tab": "Новая приватная вкладка",
        "menu_new_priv_win": "Новое приватное окно",
        "menu_close_tab": "Закрыть вкладку",
        "menu_reopen_tab": "Открыть закрытую вкладку",
        "menu_save_page": "Сохранить страницу",
        "menu_screenshot": "Скриншот",
        "menu_print": "Печать", "menu_quit": "Выход",
        "menu_edit": "Правка", "menu_find": "Поиск по странице",
        "menu_select_all": "Выделить всё", "menu_copy": "Копировать",
        "menu_view": "Вид", "menu_zoom_in": "Увеличить масштаб",
        "menu_zoom_out": "Уменьшить масштаб",
        "menu_zoom_reset": "Сбросить масштаб",
        "menu_fullscreen": "Полный экран",
        "menu_bm_sidebar": "Панель закладок",
        "menu_reader": "Режим чтения",
        "menu_translate": "Перевести страницу",
        "menu_dark_mode": "Тёмный режим сайтов (Dark Reader)",
        "menu_history": "Журнал",
        "menu_show_history": "Показать журнал",
        "menu_clear_data": "Очистить данные браузера",
        "menu_save_session": "Сохранить сессию",
        "menu_restore_session": "Восстановить сессию",
        "menu_bookmarks": "Закладки",
        "menu_bm_page": "Добавить страницу в закладки",
        "menu_flash": "Flash",
        "menu_ruffle": "Включить эмуляцию Ruffle Flash",
        "menu_open_swf": "Открыть SWF файл…",
        "menu_tools": "Инструменты",
        "menu_downloads": "Загрузки",
        "menu_extensions": "Расширения", "menu_themes": "Темы",
        "menu_user_scripts": "Пользовательские скрипты",
        "menu_tab_search": "Поиск по вкладкам",
        "menu_settings": "Настройки",
        "menu_devtools": "Инструменты разработчика",
        "menu_view_source": "Исходный код страницы",
        "menu_page_info": "Информация о странице",
        "menu_help": "Справка", "menu_about": "О ES-Browser",
        # Панель инструментов
        "tip_back": "Назад  Alt+←",
        "tip_forward": "Вперёд  Alt+→",
        "tip_home": "Домой",
        "url_ph": "Поиск или адрес сайта…",
        "tip_bookmark": "Закладка  Ctrl+D",
        "tip_dark": "Тёмный режим сайта",
        "tip_new_tab": "Новая вкладка  Ctrl+T",
        # Вкладки
        "tab_new": "Новая вкладка", "tab_private": "\U0001f575 Приватная",
        # Статусная строка
        "st_bookmarked": "Добавлено в закладки: {0}",
        "st_bm_removed": "Закладка удалена",
        "st_dark_on": "Тёмный режим ВКЛЮЧЁН — перезагрузите страницы",
        "st_dark_off": "Тёмный режим ВЫКЛЮЧЕН",
        "st_settings_saved": "Настройки сохранены",
        "st_data_cleared": "Данные браузера очищены",
        "st_session_saved": "Сессия сохранена ({0} вкладок)",
        # Диалог настроек
        "set_title": "Настройки",
        "set_sec_general": "Основные", "set_sec_content": "Контент",
        "set_sec_advanced": "Дополнительно",
        "set_homepage": "Домашняя страница:", "set_hp_newtab": "Новая вкладка (встроенная)",
        "set_hp_custom": "Мой сайт (URL):",
        "set_engine": "Поисковик:",
        "set_zoom": "Масштаб по умолчанию:",
        "set_restore": "Восстанавливать последнюю сессию при запуске",
        "set_dl_folder": "Папка загрузок:",
        "set_lang": "Язык:",
        "set_js": "Включить JavaScript",
        "set_popups": "Блокировать всплывающие окна",
        "set_dark": "Dark Reader  (тёмный режим сайтов)",
        "set_ua": "Свой User-Agent:",
        "set_ua_ph": "Оставьте пустым для Chrome 120",
        "set_lang_restart": "Смена языка применится после перезапуска ES-Browser.",
        # Приватный режим
        "priv_bar": "<b>Приватный режим</b> — история и куки не сохраняются",
        # Общие кнопки
        "dlg_ok": "ОК", "dlg_cancel": "Отмена", "dlg_close": "Закрыть",
        "dlg_open": "Открыть", "dlg_delete": "Удалить",
        "dlg_clear_done": "Удалить завершённые",
        "dlg_clear_all": "Очистить всё",
        "dlg_new": "Новый", "dlg_save": "Сохранить",
        # История
        "hist_title": "Журнал", "hist_search_ph": "Поиск в журнале…",
        # Загрузки
        "dl_title": "Загрузки",
        # Очистка данных
        "clr_title": "Очистить данные браузера",
        "clr_history": "История посещений",
        "clr_cache": "Кэш (очищает кэш Chromium)",
        "clr_cookies": "Куки и данные сайтов",
        # Информация о странице
        "pi_title": "Информация о странице",
        "pi_secure": "\U0001f512 Защищённое (HTTPS)",
        "pi_insecure": "⚠ Незащищённое (HTTP)",
        # Сессии
        "sess_title": "Восстановить сессию",
        "sess_choose": "Выберите сессию:",
        "sess_none": "Сохранённых сессий не найдено.",
        # Строка поиска
        "find_label": "  Найти:", "find_ph": "Поиск по странице…",
        "find_not_found": "Не найдено", "find_case": "С учётом регистра",
        # Закладки
        "bm_title": "Закладки",
        # История
        "hist_confirm_title": "Очистить журнал", "hist_confirm_msg": "Удалить всю историю?",
        # Пользовательские скрипты
        "us_title": "Пользовательские скрипты",
        "us_hint": "Вставляется на страницах по шаблону URL (glob, напр. *google.com*)",
        "us_manage": "⚙️  Управление скриптами (Tampermonkey)",
        "us_form_name": "Имя:", "us_form_pattern": "URL шаблон:", "us_form_code": "Код:",
        # Расширения / Темы
        "ext_title": "Расширения",
        "themes_title": "Темы", "themes_choose": "Выбор темы",
        # Поиск вкладок
        "tab_search_ph": "Поиск по вкладкам…",
        # Заголовки окон
        "priv_win_title": "Приватный режим — ES-Browser",
        "devtools_title": "Инструменты разработчика", "pagesrc_title": "Исходный код",
        # Настройки безопасности
        "set_sec_security": "Безопасность",
        "set_mixed":   "Блокировать смешанный контент (HTTP на HTTPS-страницах)",
        "set_webrtc":  "Защита от утечки IP через WebRTC",
        "set_dnt":     "Отправлять заголовок Do Not Track (DNT)",
        "set_referrer": "Политика Referer:",
        "set_safe_browsing": "Безопасный просмотр (блокировать опасные URL)",
        "set_cam":     "Камера:", "set_mic": "Микрофон:",
        "set_loc":     "Геолокация:", "set_notif": "Уведомления:",
        "perm_ask": "Спрашивать", "perm_deny": "Запрещать", "perm_allow": "Разрешать",
        "ref_full":   "Полный URL",
        "ref_origin": "Только домен (рекомендуется)",
        "ref_none":   "Не отправлять",
        "sb_title": "Предупреждение об опасном сайте",
        "sb_msg": "Сайт {0} соответствует паттерну опасного ресурса.\n\nВсё равно перейти?",
        "perm_cam": "Камера", "perm_mic": "Микрофон",
        "perm_cam_mic": "Камера + Микрофон",
        "perm_geo": "Геолокация", "perm_notif": "Уведомления",
        "perm_ask_title": "Запрос разрешения",
        "perm_ask_msg": "{0} запрашивает доступ к {1}.\n\nРазрешить?",
        # Новая вкладка
        "newtab_go": "Вперёд",
        "newtab_ph": "Поиск или адрес сайта…",
        "newtab_hint": "Ctrl+T новая вкладка • Ctrl+L адресная строка • F12 devtools • Ctrl+Shift+N приватное окно",
    },
}

_current_lang = "en_US"

def tr(key: str, *args) -> str:
    """Вернуть переведённую строку по ключу."""
    lang = STRINGS.get(_current_lang, STRINGS["en_US"])
    text = lang.get(key) or STRINGS["en_US"].get(key, key)
    return text.format(*args) if args else text

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
    "pixel.facebook.com","pixel.advertising.com",
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

# ── Chrome spoof — инжектируется на DocumentCreation, до любых скриптов страницы
# Без этого Google/YouTube видят QtWebEngine и блокируют вход
CHROME_SPOOF_JS = r"""
(function() {
'use strict';

function def(obj, prop, value) {
  try {
    Object.defineProperty(obj, prop, {
      get: function() { return value; },
      configurable: true, enumerable: true
    });
  } catch(e) { try { obj[prop] = value; } catch(e2) {} }
}

/* 1. navigator.webdriver */
def(navigator, 'webdriver', undefined);

/* 2. navigator.vendor */
def(navigator, 'vendor', 'Google Inc.');

/* 3. navigator.languages */
def(navigator, 'languages', ['ru-RU', 'ru', 'en-US', 'en']);

/* 4. navigator.plugins */
function makePlugin(name, desc, filename, mts) {
  var p = { name: name, description: desc, filename: filename, length: mts.length };
  mts.forEach(function(m, i) { p[i] = m; });
  return p;
}
var fakePlugins = [
  makePlugin('Chrome PDF Plugin',   'Portable Document Format', 'internal-pdf-viewer',
    [{ type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' }]),
  makePlugin('Chrome PDF Viewer',   '', 'mhjfbmdgcfjbbpaeojofohoefgiehjai', []),
  makePlugin('Native Client',       '', 'internal-nacl-plugin',
    [{ type: 'application/x-nacl',  suffixes: '', description: 'Native Client Executable' },
     { type: 'application/x-pnacl', suffixes: '', description: 'Portable Native Client Executable' }]),
  makePlugin('WebKit built-in PDF', '', 'WebKit built-in PDF', []),
  makePlugin('Widevine Content Decryption Module',
    'Enables Widevine licenses for playback of HTML audio/video content.',
    'widevinecdmadapter.dll',
    [{ type: 'application/x-ppapi-widevine-cdm', suffixes: '', description: '' }]),
];
def(navigator, 'plugins', fakePlugins);

/* 5. navigator.userAgentData (Client Hints) */
var _brands = [
  { brand: 'Not_A Brand',    version: '8'   },
  { brand: 'Chromium',       version: '120' },
  { brand: 'Google Chrome',  version: '120' }
];
var _uaData = {
  brands:   _brands,
  mobile:   false,
  platform: 'Windows',
  getHighEntropyValues: function(hints) {
    return Promise.resolve({
      architecture: 'x86', bitness: '64',
      brands: _brands,
      fullVersionList: [
        { brand: 'Not_A Brand',   version: '8.0.0.0'      },
        { brand: 'Chromium',      version: '120.0.6099.71' },
        { brand: 'Google Chrome', version: '120.0.6099.71' }
      ],
      mobile: false, model: '', platform: 'Windows',
      platformVersion: '15.0.0', uaFullVersion: '120.0.6099.71', wow64: false
    });
  },
  toJSON: function() {
    return { brands: _brands, mobile: false, platform: 'Windows' };
  }
};
def(navigator, 'userAgentData', _uaData);

/* 6. Permissions API — не трогаем нативный объект (детектируется X.com) */

/* 7. window.chrome (через defineProperty — перезаписывает QtWebEngine) */
var _chr = {
  app: {
    isInstalled: false,
    getDetails:     function() { return null; },
    getIsInstalled: function() { return false; },
    installState:   function(cb) { if (cb) cb('not_installed'); },
    runningState:   function() { return 'cannot_run'; }
  },
  runtime: {
    id: undefined, lastError: null,
    connect: function() {
      return {
        postMessage: function() {}, disconnect: function() {}, name: '', sender: null,
        onMessage:    { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
        onDisconnect: { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } }
      };
    },
    sendMessage:        function() {},
    getManifest:        function() { return {}; },
    getURL:             function(p) { return p || ''; },
    reload:             function() {},
    requestUpdateCheck: function(cb) { if (cb) cb('no_update'); },
    getPlatformInfo:    function(cb) {
      var i = { os: 'win', arch: 'x86-64', nacl_arch: 'x86-64' };
      if (cb) cb(i); else return Promise.resolve(i);
    },
    openOptionsPage:    function() {},
    setUninstallURL:    function() {},
    onInstalled:        { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
    onStartup:          { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
    onMessage:          { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
    onConnect:          { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
    onSuspend:          { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
    onUpdateAvailable:  { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } }
  },
  webstore: {
    install: function() {},
    onInstallStageChanged: { addListener: function() {} },
    onDownloadProgress:    { addListener: function() {} }
  },
  csi: function() {
    return {
      startE: performance.timing ? performance.timing.navigationStart : Date.now(),
      onloadT: Date.now(), pageT: performance.now(), tran: 15
    };
  },
  loadTimes: function() {
    return {
      requestTime:      performance.timeOrigin / 1000,
      startLoadTime:    performance.timeOrigin / 1000,
      commitLoadTime:   (performance.timeOrigin + 50) / 1000,
      finishDocumentLoadTime: 0, finishLoadTime: 0,
      firstPaintTime: 0, firstPaintAfterLoadTime: 0,
      navigationType: 'Other',
      wasFetchedViaSpdy: true, wasNpnNegotiated: true,
      npnNegotiatedProtocol: 'h2',
      wasAlternateProtocolAvailable: false, connectionInfo: 'h2'
    };
  }
};
try {
  Object.defineProperty(window, 'chrome', {
    value: _chr, writable: true, configurable: true, enumerable: true
  });
} catch(e) {
  try { window.chrome = _chr; } catch(e2) {}
}

})();
"""

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

def build_newtab_html(dial=None, theme_name="Catppuccin Mocha",
                      search_engine="https://www.google.com/search?q=") -> str:
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
  var re=/^(https?:\\/\\/|[a-zA-Z0-9]([a-zA-Z0-9-]*[.])+[a-zA-Z]{{2,}})/;
  window.location.href=re.test(v)?(v.startsWith('http')?v:'https://'+v):'{search_engine}'+encodeURIComponent(v);
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
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ES-Browser] save_json error: {e}", file=sys.stderr)

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
            self.dnt              = True
            self.referrer_policy  = "strict-origin"   # full / strict-origin / no-referrer
            self.domains          = set(AD_DOMAINS)

        def interceptRequest(self, info):
            url = info.requestUrl()
            first = info.firstPartyUrl()

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

            # Do Not Track (DNT)
            # Sec-GPC убран — X.com детектирует его как privacy extension
            if self.dnt:
                info.setHttpHeader(b"DNT", b"1")

            # Referrer policy
            try:
                if self.referrer_policy == "no-referrer":
                    info.setHttpHeader(b"Referer", b"")
                elif self.referrer_policy == "strict-origin":
                    if first.isValid() and url.host() != first.host():
                        origin = (first.scheme() + "://" + first.host()).encode()
                        info.setHttpHeader(b"Referer", origin)
            except Exception:
                pass

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
    def __init__(self, settings_ref: dict, parent=None):
        super().__init__(parent)
        self._settings = settings_ref
        self.setWindowTitle(tr("dl_title"))
        self.resize(660, 460)
        lay = QVBoxLayout(self); lay.setSpacing(10)
        lay.addWidget(QLabel(f"<b style='font-size:15px'>{tr('dl_title')}</b>"))
        self.list = QListWidget(); lay.addWidget(self.list)
        b = NavButton(); b.setText(tr("dlg_clear_done")); b.clicked.connect(self._clear)
        lay.addWidget(b, alignment=Qt.AlignRight)
        self._items: dict = {}

    def add_download(self, dl):
        name = dl.suggestedFileName()
        dl_dir = self._settings.get("downloads_dir", DOWNLOADS_DIR)
        os.makedirs(dl_dir, exist_ok=True)
        try:
            dl.setPath(os.path.join(dl_dir, name))
        except AttributeError:
            try:
                dl.setDownloadDirectory(dl_dir)
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
        self.setWindowTitle(tr("hist_title")); self.resize(720, 560)
        self._h = history; self._q = ""
        lay = QVBoxLayout(self); lay.setSpacing(10)
        lay.addWidget(QLabel(f"<b style='font-size:15px'>{tr('hist_title')}</b>"))
        s = URLBarEdit(); s.setPlaceholderText(tr("hist_search_ph"))
        s.textChanged.connect(lambda t: (setattr(self,'_q',t), self._refresh()))
        lay.addWidget(s)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda i: self.open_url.emit(i.data(Qt.UserRole)))
        lay.addWidget(self.list)
        btns = QHBoxLayout()
        for lbl, slot in ((tr("dlg_open"),self._open),(tr("dlg_delete"),self._delete),(tr("dlg_clear_all"),self._clear)):
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
        if QMessageBox.question(self,tr("hist_confirm_title"),tr("hist_confirm_msg"),
                                QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self._h.clear(); self._refresh()

# ── Bookmark Sidebar ───────────────────────────────────────────────────────────
class BookmarkSidebar(QWidget):
    open_url = pyqtSignal(str)

    def __init__(self, bm: list, parent=None):
        super().__init__(parent)
        self._bm = bm; self.setFixedWidth(240)
        lay = QVBoxLayout(self); lay.setContentsMargins(8,10,8,8); lay.setSpacing(8)
        lay.addWidget(QLabel(f"<b>{tr('bm_title')}</b>"))
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda i: self.open_url.emit(i.data(Qt.UserRole)))
        lay.addWidget(self.list)
        btns = QHBoxLayout()
        for lbl, slot in ((tr("dlg_open"),self._open),(tr("dlg_delete"),self._delete)):
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
        self.setWindowTitle(tr("us_title"))
        self.resize(720, 540); self._scripts = scripts

        lay = QVBoxLayout(self); lay.setSpacing(8)
        lay.addWidget(QLabel(f"<b style='font-size:14px'>{tr('us_title')}</b>"))
        lay.addWidget(QLabel(tr("us_hint")))

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._load_selected)
        lay.addWidget(self.list, 1)

        form = QFormLayout()
        self.name_e    = URLBarEdit(); self.name_e.setPlaceholderText("My Script")
        self.pattern_e = URLBarEdit(); self.pattern_e.setPlaceholderText("*example.com*")
        self.code_e    = QPlainTextEdit()
        self.code_e.setPlaceholderText("// JavaScript injected when URL matches pattern\nconsole.log('hello');")
        font = QFont("Consolas",9); self.code_e.setFont(font)
        form.addRow(tr("us_form_name"),    self.name_e)
        form.addRow(tr("us_form_pattern"), self.pattern_e)
        form.addRow(tr("us_form_code"),   self.code_e)
        lay.addLayout(form, 2)

        btns = QHBoxLayout()
        b_new  = NavButton(); b_new.setText(tr("dlg_new"));    b_new.clicked.connect(self._new)
        b_save = NavButton(); b_save.setText(tr("dlg_save"));  b_save.clicked.connect(self._save_current)
        b_del  = NavButton(); b_del.setText(tr("dlg_delete")); b_del.clicked.connect(self._delete)
        b_ok   = NavButton(); b_ok.setText(tr("dlg_close"));   b_ok.clicked.connect(self.accept)
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
        self.setWindowTitle(tr("ext_title")); self.resize(620, 480)
        self._s = settings
        lay = QVBoxLayout(self); lay.setSpacing(12)
        lay.addWidget(QLabel(f"<b style='font-size:15px'>{tr('ext_title')}</b>"))

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
        b_us = NavButton(); b_us.setText(tr("us_manage"))
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
        self.setWindowTitle(tr("themes_title")); self.resize(560, 420)
        lay = QVBoxLayout(self); lay.setSpacing(12)
        lay.addWidget(QLabel(f"<b style='font-size:15px'>{tr('themes_choose')}</b>"))

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
        self.setWindowTitle(tr("clr_title")); self.resize(400, 300)
        self._h = history
        lay = QVBoxLayout(self); lay.setSpacing(12)
        lay.addWidget(QLabel(f"<b style='font-size:14px'>{tr('clr_title')}</b>"))

        self.cb_hist  = QCheckBox(tr("clr_history"));  self.cb_hist.setChecked(True)
        self.cb_cache = QCheckBox(tr("clr_cache"))
        self.cb_cook  = QCheckBox(tr("clr_cookies"))
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
        self.search = URLBarEdit(); self.search.setPlaceholderText(tr("tab_search_ph"))
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
        self._prev_lang = s.get("lang", "en_US")
        self.setWindowTitle(tr("set_title"))
        self.resize(600, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Tab widget ────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        tabs.setTabPosition(QTabWidget.North)
        root.addWidget(tabs, 1)

        # helper: returns (QScrollArea, QFormLayout) for a tab page
        def _page():
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            inner = QWidget()
            form = QFormLayout(inner)
            form.setSpacing(12)
            form.setContentsMargins(20, 16, 20, 20)
            form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            scroll.setWidget(inner)
            return scroll, form

        # ── Tab 1: General ────────────────────────────────────────────────────
        p1, f1 = _page()
        tabs.addTab(p1, tr("set_sec_general"))

        self.lang = QComboBox()
        self.lang.addItem("English (US)", "en_US")
        self.lang.addItem("Русский (Россия)", "ru_RU")
        cur_lang = s.get("lang", "en_US")
        self.lang.setCurrentIndex(0 if cur_lang == "en_US" else 1)
        f1.addRow(tr("set_lang"), self.lang)

        # Homepage
        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        cur_hp = s.get("homepage", "about:newtab")
        is_newtab = (cur_hp in ("about:newtab", "about:blank", ""))
        hp_wrap = QWidget()
        hp_lay = QVBoxLayout(hp_wrap)
        hp_lay.setContentsMargins(0, 0, 0, 0)
        hp_lay.setSpacing(4)
        self._hp_group  = QButtonGroup(self)
        self._hp_newtab = QRadioButton(tr("set_hp_newtab"))
        self._hp_custom = QRadioButton(tr("set_hp_custom"))
        self._hp_group.addButton(self._hp_newtab, 0)
        self._hp_group.addButton(self._hp_custom, 1)
        self.homepage = URLBarEdit(cur_hp if not is_newtab else "")
        self.homepage.setPlaceholderText("https://example.com")
        self.homepage.setEnabled(not is_newtab)
        self._hp_newtab.setChecked(is_newtab)
        self._hp_custom.setChecked(not is_newtab)
        def _on_hp_toggle():
            use_custom = self._hp_custom.isChecked()
            self.homepage.setEnabled(use_custom)
            if use_custom: self.homepage.setFocus()
        self._hp_group.buttonClicked.connect(lambda _: _on_hp_toggle())
        hp_lay.addWidget(self._hp_newtab)
        hp_lay.addWidget(self._hp_custom)
        hp_lay.addWidget(self.homepage)
        f1.addRow(tr("set_homepage"), hp_wrap)

        self.engine = QComboBox()
        for name, url in SEARCH_ENGINES.items():
            self.engine.addItem(name, url)
        cur = s.get("search_engine", DEFAULTS["search_engine"])
        if cur in SEARCH_ENGINES.values():
            self.engine.setCurrentIndex(list(SEARCH_ENGINES.values()).index(cur))
        f1.addRow(tr("set_engine"), self.engine)

        self.zoom = QSpinBox()
        self.zoom.setRange(25, 500)
        self.zoom.setSuffix(" %")
        self.zoom.setValue(s.get("zoom", 100))
        f1.addRow(tr("set_zoom"), self.zoom)

        self.restore = QCheckBox(tr("set_restore"))
        self.restore.setChecked(s.get("restore_session", False))
        f1.addRow("", self.restore)

        dl_row = QWidget()
        dl_lay = QHBoxLayout(dl_row)
        dl_lay.setContentsMargins(0, 0, 0, 0)
        self.dl_dir = URLBarEdit(s.get("downloads_dir", DOWNLOADS_DIR))
        btn_browse = NavButton()
        btn_browse.setText("…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(self._browse)
        dl_lay.addWidget(self.dl_dir, 1)
        dl_lay.addWidget(btn_browse)
        f1.addRow(tr("set_dl_folder"), dl_row)

        # ── Tab 2: Content ────────────────────────────────────────────────────
        p2, f2 = _page()
        tabs.addTab(p2, tr("set_sec_content"))

        self.javascript = QCheckBox(tr("set_js"))
        self.javascript.setChecked(s.get("javascript", True))
        f2.addRow("", self.javascript)

        self.popups = QCheckBox(tr("set_popups"))
        self.popups.setChecked(s.get("block_popups", True))
        f2.addRow("", self.popups)

        self.dark_reader = QCheckBox(tr("set_dark"))
        self.dark_reader.setChecked(s.get("dark_reader", False))
        f2.addRow("", self.dark_reader)

        # ── Tab 3: Security ───────────────────────────────────────────────────
        p3, f3 = _page()
        tabs.addTab(p3, tr("set_sec_security"))

        self.mixed = QCheckBox(tr("set_mixed"))
        self.mixed.setChecked(s.get("block_mixed_content", True))
        f3.addRow("", self.mixed)

        self.webrtc = QCheckBox(tr("set_webrtc"))
        self.webrtc.setChecked(s.get("webrtc_protection", True))
        f3.addRow("", self.webrtc)

        self.dnt = QCheckBox(tr("set_dnt"))
        self.dnt.setChecked(s.get("dnt", True))
        f3.addRow("", self.dnt)

        self.referrer = QComboBox()
        for lbl, val in ((tr("ref_full"), "full"),
                         (tr("ref_origin"), "strict-origin"),
                         (tr("ref_none"), "no-referrer")):
            self.referrer.addItem(lbl, val)
        cur_ref = s.get("referrer_policy", "strict-origin")
        self.referrer.setCurrentIndex(
            next((i for i in range(self.referrer.count())
                  if self.referrer.itemData(i) == cur_ref), 1))
        f3.addRow(tr("set_referrer"), self.referrer)

        self.safe_browsing = QCheckBox(tr("set_safe_browsing"))
        self.safe_browsing.setChecked(s.get("safe_browsing", True))
        f3.addRow("", self.safe_browsing)

        # Permissions sub-header
        _perms_title = "Разрешения" if s.get("lang","en_US") == "ru_RU" else "Permissions"
        sep_lbl = QLabel("<b style='font-size:11px; color:gray;'>— " + _perms_title + " —</b>")
        f3.addRow(sep_lbl)

        perm_opts = [(tr("perm_ask"), "ask"), (tr("perm_deny"), "deny"), (tr("perm_allow"), "allow")]
        self._perms = {}
        for pkey, lkey, default in (
            ("permission_camera",        "set_cam",   "ask"),
            ("permission_mic",           "set_mic",   "ask"),
            ("permission_location",      "set_loc",   "deny"),
            ("permission_notifications", "set_notif", "ask"),
        ):
            cb = QComboBox()
            for pl, pv in perm_opts:
                cb.addItem(pl, pv)
            cur = s.get(pkey, default)
            cb.setCurrentIndex(next((i for i in range(cb.count()) if cb.itemData(i) == cur), 0))
            self._perms[pkey] = cb
            f3.addRow(tr(lkey), cb)

        # ── Tab 4: Advanced ───────────────────────────────────────────────────
        p4, f4 = _page()
        tabs.addTab(p4, tr("set_sec_advanced"))

        self.ua = URLBarEdit(s.get("user_agent", ""))
        self.ua.setPlaceholderText(tr("set_ua_ph"))
        f4.addRow(tr("set_ua"), self.ua)

        # ── Button box ────────────────────────────────────────────────────────
        bb_wrap = QWidget()
        bb_lay = QHBoxLayout(bb_wrap)
        bb_lay.setContentsMargins(16, 8, 16, 12)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb_lay.addWidget(bb)
        root.addWidget(bb_wrap)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("set_dl_folder"), self.dl_dir.text())
        if d: self.dl_dir.setText(d)

    def result(self) -> dict:
        d = {
            "lang":                  self.lang.currentData(),
            "homepage":              "about:newtab" if self._hp_newtab.isChecked()
                                     else (self.homepage.text().strip() or "about:newtab"),
            "search_engine":         self.engine.currentData(),
            "zoom":                  self.zoom.value(),
            "restore_session":       self.restore.isChecked(),
            "downloads_dir":         self.dl_dir.text(),
            "javascript":            self.javascript.isChecked(),
            "block_popups":          self.popups.isChecked(),
            "dark_reader":           self.dark_reader.isChecked(),
            "user_agent":            self.ua.text(),
            # Security
            "block_mixed_content":   self.mixed.isChecked(),
            "webrtc_protection":     self.webrtc.isChecked(),
            "dnt":                   self.dnt.isChecked(),
            "referrer_policy":       self.referrer.currentData(),
            "safe_browsing":         self.safe_browsing.isChecked(),
        }
        for pkey, cb in self._perms.items():
            d[pkey] = cb.currentData()
        return d

    def lang_changed(self) -> bool:
        return self.lang.currentData() != self._prev_lang

# ── About Dialog ──────────────────────────────────────────────────────────────
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("menu_about"))
        self.setFixedSize(400, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 20)
        lay.setSpacing(0)

        # ── Logo row ──
        logo_lbl = QLabel("🌐")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("font-size:56px; margin-bottom:4px;")
        lay.addWidget(logo_lbl)

        # ── Name ──
        name_lbl = QLabel("ES-Browser")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet("font-size:22px; font-weight:700; letter-spacing:1px;")
        lay.addWidget(name_lbl)

        # ── Version ──
        ver_lbl = QLabel("Version 4.0  •  Built with PyQt5 + Chromium")
        ver_lbl.setAlignment(Qt.AlignCenter)
        ver_lbl.setStyleSheet("font-size:11px; opacity:.7; margin-top:4px; margin-bottom:18px;")
        lay.addWidget(ver_lbl)

        # ── Divider ──
        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: rgba(128,128,128,0.3);")
        lay.addWidget(line)
        lay.addSpacing(14)

        # ── Info grid ──
        info = [
            ("Engine",   "Chromium  (PyQtWebEngine)"),
            ("UI",       "PyQt5"),
            ("Platform", f"{sys.platform.title()}  •  Python {sys.version.split()[0]}"),
            ("Author",   "Jemyz3653"),
        ]
        for label, value in info:
            row = QHBoxLayout()
            k = QLabel(label + ":")
            k.setFixedWidth(80)
            k.setStyleSheet("font-weight:600; font-size:12px;")
            v = QLabel(value)
            v.setStyleSheet("font-size:12px;")
            row.addWidget(k); row.addWidget(v); row.addStretch()
            lay.addLayout(row)
            lay.addSpacing(4)

        lay.addSpacing(16)

        # ── Close button ──
        btn = QPushButton("Close")
        btn.setFixedWidth(100)
        btn.setStyleSheet(
            "QPushButton{border-radius:7px;padding:7px 0;font-weight:600;font-size:13px;}"
        )
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignCenter)


# ── Mouse back/forward button filter ──────────────────────────────────────────
class _NavMouseFilter(QObject):
    """Перехватывает XButton1/XButton2 (боковые кнопки мыши) на уровне приложения.
    Работает даже когда фокус внутри QWebEngineView (Chromium не перехватывает XButton).
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            btn = event.button()
            # Qt.BackButton == Qt.XButton1, Qt.ForwardButton == Qt.XButton2
            if btn in (Qt.BackButton, Qt.XButton1):
                win = QApplication.activeWindow()
                if isinstance(win, MainWindow):
                    win.go_back()
                return True
            if btn in (Qt.ForwardButton, Qt.XButton2):
                win = QApplication.activeWindow()
                if isinstance(win, MainWindow):
                    win.go_forward()
                return True
        return False

# ── Custom Page (fullscreen + popups) ─────────────────────────────────────────
class BrowserPage(QWebEnginePage):
    """QWebEnginePage с поддержкой полноэкранного режима и попапов."""
    open_in_new_tab = pyqtSignal(str)   # url для открытия в новой вкладке

    def createWindow(self, win_type):
        """Перехватываем window.open() и target="_blank" — открываем новую вкладку."""
        tmp = BrowserPage(self.profile(), None)
        # Как только временная страница получит URL — передаём его наверх
        tmp.urlChanged.connect(
            lambda u: self.open_in_new_tab.emit(u.toString()) if u.isValid() and u.scheme() not in ('', 'about') else None
        )
        return tmp

    def javaScriptConsoleMessage(self, level, msg, line, source):
        pass   # подавляем шум в консоли

# ── Find Bar ───────────────────────────────────────────────────────────────────
class FindBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(6,3,6,3); lay.setSpacing(4)
        self.input = URLBarEdit(); self.input.setPlaceholderText(tr("find_ph"))
        self.input.returnPressed.connect(self._next)
        self.input.textChanged.connect(self._live)
        self._case = NavButton(); self._case.setText("Aa"); self._case.setCheckable(True)
        self._case.setToolTip(tr("find_case"))
        self._result = QLabel(); self._result.setMinimumWidth(80)
        b_prev  = NavButton(); b_prev.setText("▲");  b_prev.clicked.connect(self._prev)
        b_next  = NavButton(); b_next.setText("▼");  b_next.clicked.connect(self._next)
        b_close = NavButton(); b_close.setText("✕"); b_close.clicked.connect(self.hide_bar)
        for w in (QLabel(tr("find_label")),self.input,self._case,b_prev,b_next,self._result,b_close):
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
                lambda ok: self._result.setText("" if ok else tr("find_not_found")))

    def _next(self):
        if self.view:
            self.view.findText(self.input.text(), self._flags(),
                lambda ok: self._result.setText("" if ok else tr("find_not_found")))

    def _prev(self):
        if self.view:
            self.view.findText(self.input.text(), self._flags(bwd=True),
                lambda ok: self._result.setText("" if ok else tr("find_not_found")))

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
        page = BrowserPage(profile, self.view)
        self.view.setPage(page)
        # Попапы → новая вкладка в MainWindow
        page.open_in_new_tab.connect(self._open_popup)
        # Полноэкранный режим (YouTube, видеоплееры)
        try:
            page.fullScreenRequested.connect(self._handle_fullscreen)
        except AttributeError:
            pass
        ws = self.view.settings()

        # Базовые атрибуты (AllowRunningInsecureContent управляется профилем)
        for attr in (
            QWebEngineSettings.JavascriptEnabled,
            QWebEngineSettings.PluginsEnabled,
            QWebEngineSettings.FullScreenSupportEnabled,
            QWebEngineSettings.ScrollAnimatorEnabled,
            QWebEngineSettings.LocalStorageEnabled,
            QWebEngineSettings.JavascriptCanAccessClipboard,
            QWebEngineSettings.JavascriptCanOpenWindows,
        ):
            ws.setAttribute(attr, True)

        # Атрибуты, которых может не быть в старых версиях PyQtWebEngine
        for _name in ("WebGLEnabled", "ServiceWorkerEnabled",
                      "AllowWindowActivationFromJavaScript",
                      "PdfViewerEnabled"):
            try:
                ws.setAttribute(getattr(QWebEngineSettings, _name), True)
            except AttributeError:
                pass

        # Автоматически принимать разрешения (камера, микрофон и т.д.)
        self.view.page().featurePermissionRequested.connect(self._grant_permission)

        self.view.titleChanged.connect(self.title_changed)
        self.view.urlChanged.connect(lambda u: self.url_changed.emit(u.toString()))
        self.view.iconChanged.connect(self.icon_changed)
        self.view.page().linkHovered.connect(self.status_msg)
        self.view.loadStarted.connect(self.load_started)
        self.view.loadProgress.connect(self.load_progress)
        self.view.loadFinished.connect(self.load_finished)
        # Применять зум при каждой загрузке страницы
        self.view.loadStarted.connect(self._apply_zoom)

        self.find_bar = FindBar(); self.find_bar.attach(self.view)
        lay.addWidget(self.view); lay.addWidget(self.find_bar)

    def _apply_zoom(self):
        self.view.setZoomFactor(self._s.get("zoom", 100) / 100.0)

    def _open_popup(self, url: str):
        """Открыть попап (window.open) в новой вкладке."""
        if url and url not in ("about:blank", ""):
            win = self.window()
            if hasattr(win, "new_tab"):
                win.new_tab(url=url)

    def _handle_fullscreen(self, request):
        """Обработка fullscreen-запросов от страниц (YouTube, видеоплееры)."""
        request.accept()
        win = self.window()
        if not hasattr(win, "_enter_fullscreen"):
            return
        try:
            going_fs = request.toggleOn()
        except AttributeError:
            going_fs = not win.isFullScreen()
        if going_fs:
            win._enter_fullscreen()
        else:
            win._exit_fullscreen()

    def navigate(self, url: str):
        if url in ("about:newtab", "about:blank", ""):
            theme = self._s.get("theme", "Catppuccin Mocha")
            se    = self._s.get("search_engine", "https://www.google.com/search?q=")
            self.load_new_tab(theme, se); return
        u = QUrl(url)
        if not u.scheme(): u = QUrl("https://" + url)
        self.view.load(u)

    def load_new_tab(self, theme="Catppuccin Mocha",
                     search_engine="https://www.google.com/search?q="):
        html = build_newtab_html(theme_name=theme, search_engine=search_engine)
        self.view.setHtml(html, QUrl("about:newtab"))

    def _grant_permission(self, url, feature):
        """Обрабатывать разрешения согласно настройкам (ask/deny/allow)."""
        feature_map = {
            QWebEnginePage.MediaAudioCapture:      ("permission_mic",           "perm_mic"),
            QWebEnginePage.MediaVideoCapture:      ("permission_camera",        "perm_cam"),
            QWebEnginePage.MediaAudioVideoCapture: ("permission_camera",        "perm_cam_mic"),
            QWebEnginePage.Geolocation:            ("permission_location",      "perm_geo"),
            QWebEnginePage.Notifications:          ("permission_notifications", "perm_notif"),
        }
        entry = feature_map.get(feature)
        if entry:
            policy    = self._s.get(entry[0], "ask")
            feat_name = tr(entry[1])
        else:
            policy    = "ask"
            feat_name = "Permission"

        if policy == "allow":
            grant = True
        elif policy == "deny":
            grant = False
        else:  # ask
            reply = QMessageBox.question(
                self,
                tr("perm_ask_title"),
                tr("perm_ask_msg").format(url.host(), feat_name),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            grant = (reply == QMessageBox.Yes)

        perm = (QWebEnginePage.PermissionGrantedByUser if grant
                else QWebEnginePage.PermissionDeniedByUser)
        self.view.page().setFeaturePermission(url, feature, perm)

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
        # Устанавливаем язык до построения UI
        global _current_lang
        _current_lang = self.settings.get("lang", "en_US")
        self._closed_tabs: list = []
        self._is_loading  = False
        self._zoom_timer  = None

        # Profiles
        if private_window:
            self.profile = QWebEngineProfile(self)        # off-the-record
        else:
            self.profile = QWebEngineProfile("ESBrowser", self)

        self.private_profile = QWebEngineProfile(self)    # always off-the-record

        # Применяем настройки WebEngine на уровне профиля (до создания вкладок)
        self._init_profile_settings(self.profile)
        self._init_profile_settings(self.private_profile)
        # Mixed content согласно настройкам
        for _p in (self.profile, self.private_profile):
            _p.settings().setAttribute(
                QWebEngineSettings.AllowRunningInsecureContent,
                not self.settings.get("block_mixed_content", True))

        # Chrome-спуфинг: window.chrome, navigator.vendor и т.д.
        # Нужен чтобы Google/YouTube не блокировали вход через «небезопасный браузер»
        for _p in (self.profile, self.private_profile):
            add_profile_script(_p, "__pb_chrome_spoof__", CHROME_SPOOF_JS,
                               QWebEngineScript.DocumentCreation)

        # User-Agent: Chrome 120 по умолчанию — нужен для YouTube и современных сайтов
        ua = self.settings.get("user_agent") or CHROME_UA
        self.profile.setHttpUserAgent(ua)
        self.private_profile.setHttpUserAgent(ua)

        # Interceptor
        self._interceptor = None
        if _has_interceptor:
            self._interceptor = RequestInterceptor()
            self._interceptor.ad_block         = self.settings.get("ad_block", True)
            self._interceptor.https_everywhere = self.settings.get("https_everywhere", False)
            self._interceptor.dnt              = self.settings.get("dnt", True)
            self._interceptor.referrer_policy  = self.settings.get("referrer_policy", "strict-origin")
            install_interceptor(self.profile, self._interceptor)
            install_interceptor(self.private_profile, self._interceptor)

        self._dl_mgr = DownloadManager(self.settings, self)
        self.profile.downloadRequested.connect(self._dl_mgr.add_download)
        self.private_profile.downloadRequested.connect(self._dl_mgr.add_download)

        self._build_ui()
        self._apply_theme(self.settings.get("theme", "Catppuccin Mocha"))
        self._apply_all_scripts()

        if private_window:
            self.setWindowTitle(tr("priv_win_title"))
            self.new_tab()
        elif self.settings.get("restore_session") and self.sessions.get("last"):
            for entry in self.sessions["last"]:
                self.new_tab(url=entry.get("url"))
        else:
            self.new_tab()

    # ── Script management ──────────────────────────────────────────────────────
    # ── Profile-level WebEngine settings ──────────────────────────────────────
    def _init_profile_settings(self, profile):
        """Включить JS, WebGL, Service Workers и прочее на уровне профиля."""
        ps = profile.settings()
        for attr in (
            QWebEngineSettings.JavascriptEnabled,
            QWebEngineSettings.PluginsEnabled,
            QWebEngineSettings.FullScreenSupportEnabled,
            QWebEngineSettings.ScrollAnimatorEnabled,
            QWebEngineSettings.LocalStorageEnabled,
            QWebEngineSettings.JavascriptCanAccessClipboard,
            QWebEngineSettings.JavascriptCanOpenWindows,
        ):
            ps.setAttribute(attr, True)
        # Смешанный контент: по умолчанию заблокирован (настраивается)
        ps.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, False)
        for _name in ("WebGLEnabled", "ServiceWorkerEnabled",
                      "AllowWindowActivationFromJavaScript",
                      "PdfViewerEnabled"):
            try:
                ps.setAttribute(getattr(QWebEngineSettings, _name), True)
            except AttributeError:
                pass

    def _apply_all_scripts(self):
        # WebRTC IP leak protection
        if self.settings.get("webrtc_protection", True):
            add_profile_script(self.profile, "__pb_webrtc__", WEBRTC_PROTECTION_JS,
                               QWebEngineScript.DocumentCreation)
            add_profile_script(self.private_profile, "__pb_webrtc__", WEBRTC_PROTECTION_JS,
                               QWebEngineScript.DocumentCreation)
        else:
            remove_profile_script(self.profile, "__pb_webrtc__")
            remove_profile_script(self.private_profile, "__pb_webrtc__")
        # Dark Reader
        if self.settings.get("dark_reader"):
            add_profile_script(self.profile, "__pb_dr__", DARK_READER_JS,
                               QWebEngineScript.DocumentReady)
        else:
            remove_profile_script(self.profile, "__pb_dr__")
        # Ruffle — DocumentReady, иначе document.head ещё null
        if self.settings.get("ruffle"):
            add_profile_script(self.profile, "__pb_ruffle__", RUFFLE_JS,
                               QWebEngineScript.DocumentReady)
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
            lbl = QLabel(tr("priv_bar"))
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
        btn_plus.setToolTip(tr("tip_new_tab")); btn_plus.setFixedSize(30,28)
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

        self._btn_back  = nav("◀", tr("tip_back"),    self.go_back)
        self._btn_fwd   = nav("▶", tr("tip_forward"), self.go_forward)
        self._btn_home  = nav("⌂", tr("tip_home"),    self.go_home)

        # URL bar
        self._url_bar = URLBarEdit()
        self._url_bar.setPlaceholderText(tr("url_ph"))
        self._url_bar.returnPressed.connect(self._navigate_from_bar)
        self._url_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._url_bar.setFixedHeight(34)

        self._sec_action = self._url_bar.addAction(
            emoji_icon("🔒","#4caf50"), QLineEdit.LeadingPosition)
        self._rl_action  = self._url_bar.addAction(
            emoji_icon("↻","#888"), QLineEdit.TrailingPosition)
        self._rl_action.triggered.connect(self._reload_or_stop)

        self._btn_star  = nav("☆", tr("tip_bookmark"), self.toggle_bookmark)
        self._btn_dark  = nav("🌙", tr("tip_dark"), self._toggle_dark_reader, checkable=True)
        self._btn_dark.setChecked(self.settings.get("dark_reader",False))

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
        fm = mb.addMenu(tr("menu_file"))
        act(fm, tr("menu_new_tab"),        "Ctrl+T",           self.new_tab)
        act(fm, tr("menu_new_priv_tab"),   "Ctrl+Shift+P",     lambda: self.new_tab(private=True))
        act(fm, tr("menu_new_priv_win"),   "Ctrl+Shift+N",     self.open_private_window)
        act(fm, tr("menu_close_tab"),      "Ctrl+W",           lambda: self.close_tab(self.tabs.currentIndex()))
        act(fm, tr("menu_reopen_tab"),     "Ctrl+Shift+T",     self._restore_closed_tab)
        fm.addSeparator()
        act(fm, tr("menu_save_page"),      "Ctrl+S",           lambda: (t:=self._cur()) and t.save_page())
        act(fm, tr("menu_screenshot"),     "Ctrl+Shift+S",     lambda: (t:=self._cur()) and t.screenshot())
        act(fm, tr("menu_print"),          "Ctrl+P",           lambda: (t:=self._cur()) and t.print_page())
        fm.addSeparator()
        act(fm, tr("menu_quit"),           "Ctrl+Q",           self.close)

        # Edit
        em = mb.addMenu(tr("menu_edit"))
        act(em, tr("menu_find"),           "Ctrl+F",           lambda: (t:=self._cur()) and t.toggle_find())
        em.addSeparator()
        act(em, tr("menu_select_all"),     "Ctrl+A",
            lambda: self._cur() and self._cur().view.page().triggerAction(QWebEnginePage.SelectAll))
        act(em, tr("menu_copy"),           "Ctrl+C",
            lambda: self._cur() and self._cur().view.page().triggerAction(QWebEnginePage.Copy))

        # View
        vm = mb.addMenu(tr("menu_view"))
        act(vm, tr("menu_zoom_in"),        "Ctrl+=",           lambda: (t:=self._cur()) and t.zoom_in())
        act(vm, tr("menu_zoom_out"),       "Ctrl+-",           lambda: (t:=self._cur()) and t.zoom_out())
        act(vm, tr("menu_zoom_reset"),     "Ctrl+0",           lambda: (t:=self._cur()) and t.zoom_reset())
        vm.addSeparator()
        act(vm, tr("menu_fullscreen"),     "F11",              self.toggle_fullscreen)
        vm.addSeparator()
        act(vm, tr("menu_bm_sidebar"),     "Ctrl+B",           self.toggle_sidebar)
        act(vm, tr("menu_reader"),         "Alt+R",            lambda: (t:=self._cur()) and t.reader_mode())
        act(vm, tr("menu_translate"),      "Alt+T",            lambda: (t:=self._cur()) and t.translate_page())
        vm.addSeparator()
        self._dark_menu_act = act(vm, tr("menu_dark_mode"),    "Alt+D",
                                  self._toggle_dark_reader, checkable=True)
        self._dark_menu_act.setChecked(self.settings.get("dark_reader", False))

        # History
        hm = mb.addMenu(tr("menu_history"))
        act(hm, tr("menu_show_history"),   "Ctrl+H",           self.show_history)
        act(hm, tr("menu_clear_data"),     "Ctrl+Shift+Delete", self.show_clear_data)
        hm.addSeparator()
        act(hm, tr("menu_save_session"),   "",                 lambda: self._save_session("last"))
        act(hm, tr("menu_restore_session"),"",                 self._restore_session_dialog)

        # Bookmarks
        bkm = mb.addMenu(tr("menu_bookmarks"))
        act(bkm, tr("menu_bm_page"),       "Ctrl+D",           self.toggle_bookmark)
        act(bkm, tr("menu_bm_sidebar"),    "Ctrl+Shift+B",     self.toggle_sidebar)

        # Flash
        flm = mb.addMenu(tr("menu_flash"))
        self._ruffle_act = flm.addAction(tr("menu_ruffle"))
        self._ruffle_act.setCheckable(True)
        self._ruffle_act.setChecked(self.settings.get("ruffle", True))
        self._ruffle_act.triggered.connect(self._toggle_ruffle)
        flm.addSeparator()
        act(flm, tr("menu_open_swf"),      "Ctrl+Shift+F",     self.open_swf)

        # Tools
        tm = mb.addMenu(tr("menu_tools"))
        act(tm, tr("menu_downloads"),      "Ctrl+J",           self._dl_mgr.show)
        act(tm, tr("menu_extensions"),     "Ctrl+Shift+E",     self.show_extensions)
        act(tm, tr("menu_themes"),         "",                 self.show_themes)
        act(tm, tr("menu_user_scripts"),   "",                 self._open_user_scripts)
        act(tm, tr("menu_tab_search"),     "Ctrl+Shift+A",     self.show_tab_search)
        tm.addSeparator()
        act(tm, tr("menu_settings"),       "Ctrl+,",           self.show_settings)
        tm.addSeparator()
        act(tm, tr("menu_devtools"),       "F12",              self.open_devtools)
        act(tm, tr("menu_view_source"),    "Ctrl+U",           self._view_source)
        act(tm, tr("menu_page_info"),      "Ctrl+I",           self.show_page_info)

        # Help
        hpm = mb.addMenu(tr("menu_help"))
        act(hpm, tr("menu_about"),         "F1",               self.show_about)

    def _build_shortcuts(self):
        def sc(key, slot, ctx=Qt.WindowShortcut):
            s = QShortcut(QKeySequence(key), self)
            s.setContext(ctx)
            s.activated.connect(slot)
            return s

        # ── Escape: fullscreen → выход; иначе → остановить загрузку ─────────
        sc("Escape", self._on_escape)

        # ── Навигация ────────────────────────────────────────────────────────
        sc("Alt+Left",        self.go_back,     Qt.ApplicationShortcut)
        sc("Alt+Right",       self.go_forward,  Qt.ApplicationShortcut)
        sc("Backspace",       self.go_back)          # как в Chrome
        sc("F5",              self.reload)
        sc("Ctrl+R",          self.reload)
        sc("Ctrl+Shift+R",    self._hard_reload)
        sc("Ctrl+L",          self._focus_bar,  Qt.ApplicationShortcut)
        sc("F6",              self._focus_bar,  Qt.ApplicationShortcut)
        sc("Alt+Home",        self.go_home)
        sc("Ctrl+Enter",      self._nav_dotcom)

        # ── Вкладки ──────────────────────────────────────────────────────────
        sc("Ctrl+Tab",        self._next_tab,   Qt.ApplicationShortcut)
        sc("Ctrl+Shift+Tab",  self._prev_tab,   Qt.ApplicationShortcut)
        # Ctrl+Shift+T уже в меню — НЕ дублируем (избегаем ambiguous shortcut)
        for i in range(1, 9):
            sc(f"Ctrl+{i}", lambda _, n=i-1: self.tabs.setCurrentIndex(n))
        sc("Ctrl+9", lambda: self.tabs.setCurrentIndex(self.tabs.count()-1))

        # ── Зум (Ctrl+= для клавиатур без отдельного +) ─────────────────────
        sc("Ctrl++",  lambda: (t := self._cur()) and t.zoom_in())
        sc("Ctrl+=",  lambda: (t := self._cur()) and t.zoom_in())   # alias
        sc("Ctrl+-",  lambda: (t := self._cur()) and t.zoom_out())
        sc("Ctrl+0",  lambda: (t := self._cur()) and t.zoom_reset())

        # ── Прочее ───────────────────────────────────────────────────────────
        sc("Ctrl+Shift+A",      self.show_tab_search)
        sc("Ctrl+Shift+N",      self.open_private_window)
        sc("Ctrl+Shift+Delete", self.show_clear_data)
        sc("F3",                lambda: (t := self._cur()) and t.find_bar.show_bar())
        sc("Ctrl+F",            lambda: (t := self._cur()) and t.toggle_find(),
           Qt.ApplicationShortcut)

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

        label = tr("tab_private") if (private or self._is_private_window) else tr("tab_new")
        idx = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(idx)

        if url and url not in ("about:newtab", "about:blank"):
            tab.navigate(url)
        else:
            theme = self.settings.get("theme", "Catppuccin Mocha")
            se    = self.settings.get("search_engine", DEFAULTS["search_engine"])
            tab.load_new_tab(theme, se)
        return tab

    def close_tab(self, idx: int):
        tab = self.tabs.widget(idx)
        if isinstance(tab, BrowserTab):
            url = tab.view.url().toString()
            title = tab.view.title()
            if url not in ("","about:newtab","about:blank") and not tab.private:
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
        if tab is self._cur(): self.setWindowTitle(f"{title} — ES-Browser")

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
        url = resolve_url(text, self.settings["search_engine"])
        tab = self._cur()
        if not tab: return
        # Safe Browsing — базовая проверка подозрительных URL
        if self.settings.get("safe_browsing", True):
            for pat in SAFE_BROWSING_PATTERNS:
                if re.search(pat, url, re.IGNORECASE):
                    reply = QMessageBox.warning(
                        self, tr("sb_title"),
                        tr("sb_msg").format(url),
                        QMessageBox.Ignore | QMessageBox.Abort,
                        QMessageBox.Abort,
                    )
                    if reply == QMessageBox.Abort:
                        return
                    break
        tab.navigate(url)

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

    def _on_escape(self):
        """Escape: выход из fullscreen → иначе закрыть find bar → иначе стоп."""
        if self.isFullScreen():
            self._exit_fullscreen(); return
        t = self._cur()
        if t and t.find_bar.isVisible():
            t.find_bar.hide_bar(); return
        self.stop_load()

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

    def _enter_fullscreen(self):
        """Полноэкранный режим: скрыть панели, развернуть окно."""
        self._fs_had_toolbar = self._toolbar.isVisible()
        self._fs_had_menu    = self.menuBar().isVisible()
        self._toolbar.hide()
        self.menuBar().hide()
        self.tabs.tabBar().hide()
        self.statusBar().hide()
        self.showFullScreen()

    def _exit_fullscreen(self):
        """Выйти из полноэкранного режима, восстановить панели."""
        self.showNormal()
        if getattr(self, "_fs_had_toolbar", True):
            self._toolbar.show()
        if getattr(self, "_fs_had_menu", True):
            self.menuBar().show()
        self.tabs.tabBar().show()
        self.statusBar().show()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    # ── Bookmarks ──────────────────────────────────────────────────────────────
    def toggle_bookmark(self):
        tab = self._cur()
        if not tab: return
        url = tab.view.url().toString(); title = tab.view.title() or url
        if any(b["url"]==url for b in self.bookmarks):
            self.bookmarks[:] = [b for b in self.bookmarks if b["url"]!=url]
            self._btn_star.setText("☆")
            self.statusBar().showMessage(tr("st_bm_removed"),2000)
        else:
            self.bookmarks.append({"url":url,"title":title,
                "date":datetime.now().strftime("%Y-%m-%d")})
            self._btn_star.setText("★")
            self.statusBar().showMessage(tr("st_bookmarked", title),2000)
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
            self.statusBar().showMessage(tr("st_data_cleared"),2000)

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
        self.statusBar().showMessage(tr("st_session_saved", len(entries)),2000)

    def _restore_session_dialog(self):
        names = [k for k in self.sessions if self.sessions[k]]
        if not names:
            QMessageBox.information(self,tr("sess_title"),tr("sess_none")); return
        name, ok = QComboBox(), False
        dlg = QDialog(self); dlg.setWindowTitle(tr("sess_title"))
        lay = QVBoxLayout(dlg); lay.addWidget(QLabel(tr("sess_choose")))
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
        msg = tr("st_dark_on") if new_val else tr("st_dark_off")
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
                    se = self.settings.get("search_engine", DEFAULTS["search_engine"])
                    tab.load_new_tab(name, se)

    # ── Settings ───────────────────────────────────────────────────────────────
    def show_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_() == QDialog.Accepted:
            prev_dark = self.settings.get("dark_reader", False)
            lang_changed = dlg.lang_changed()
            self.settings.update(dlg.result())

            # User-Agent
            ua = self.settings.get("user_agent") or CHROME_UA
            self.profile.setHttpUserAgent(ua)
            self.private_profile.setHttpUserAgent(ua)

            # JavaScript + pop-ups
            for _prof in (self.profile, self.private_profile):
                _ps = _prof.settings()
                _ps.setAttribute(QWebEngineSettings.JavascriptEnabled,
                                 self.settings.get("javascript", True))
                _ps.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows,
                                 not self.settings.get("block_popups", True))
                # Mixed content
                _ps.setAttribute(QWebEngineSettings.AllowRunningInsecureContent,
                                 not self.settings.get("block_mixed_content", True))

            # Interceptor — DNT + Referrer
            if self._interceptor:
                self._interceptor.dnt             = self.settings.get("dnt", True)
                self._interceptor.referrer_policy = self.settings.get("referrer_policy", "strict-origin")
                self._interceptor.https_everywhere= self.settings.get("https_everywhere", False)
                self._interceptor.ad_block        = self.settings.get("ad_block", True)

            # Dark Reader — если изменился, перезаписываем скрипты
            if self.settings.get("dark_reader") != prev_dark:
                self._apply_all_scripts()
                self._btn_dark.setChecked(self.settings.get("dark_reader", False))
                self._dark_menu_act.setChecked(self.settings.get("dark_reader", False))

            # Обновляем открытые вкладки «Новая вкладка» — чтобы поисковик применился сразу
            se    = self.settings.get("search_engine", DEFAULTS["search_engine"])
            theme = self.settings.get("theme", "Catppuccin Mocha")
            for i in range(self.tabs.count()):
                t = self.tabs.widget(i)
                if isinstance(t, BrowserTab):
                    u = t.view.url().toString()
                    if u in ("about:newtab", "about:blank", ""):
                        t.load_new_tab(theme, se)

            # Применяем зум и JS/попапы ко всем уже открытым вкладкам
            new_zoom = self.settings.get("zoom", 100) / 100
            js_on    = self.settings.get("javascript", True)
            pop_on   = not self.settings.get("block_popups", True)
            for i in range(self.tabs.count()):
                t = self.tabs.widget(i)
                if isinstance(t, BrowserTab):
                    t.view.setZoomFactor(new_zoom)
                    t.view.settings().setAttribute(
                        QWebEngineSettings.JavascriptEnabled, js_on)
                    t.view.settings().setAttribute(
                        QWebEngineSettings.JavascriptCanOpenWindows, pop_on)

            save_json(SETTINGS_F, self.settings)
            self.statusBar().showMessage(tr("st_settings_saved"), 2000)

            # Language change — notify user that restart is needed
            if lang_changed:
                QMessageBox.information(
                    self, tr("set_title"), tr("set_lang_restart")
                )

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
        dlg = QDialog(self); dlg.setWindowTitle(tr("devtools_title")); dlg.resize(1100,660)
        lay = QVBoxLayout(dlg); lay.addWidget(dev); dlg.show()

    def _view_source(self):
        if t := self._cur(): t.view.page().toHtml(self._show_source_win)

    def _show_source_win(self, html):
        dlg = QDialog(self); dlg.setWindowTitle(tr("pagesrc_title")); dlg.resize(920,660)
        lay = QVBoxLayout(dlg)
        te = QTextEdit(); te.setReadOnly(True); te.setPlainText(html)
        te.setFont(QFont("Consolas",10)); lay.addWidget(te); dlg.show()

    def show_page_info(self):
        tab = self._cur()
        if not tab: return
        url  = tab.view.url().toString()
        title= tab.view.title()
        is_secure = url.startswith("https://")
        conn = tr("pi_secure") if is_secure else tr("pi_insecure")
        msg = (f"<b>Title:</b> {title}<br>"
               f"<b>URL:</b> {url}<br>"
               f"<b>Connection:</b> {conn}<br>"
               f"<b>Zoom:</b> {int(tab.view.zoomFactor()*100)}%")
        QMessageBox.information(self, tr("pi_title"), msg)

    def show_tab_search(self):
        dlg = TabSearchDialog(self.tabs, self)
        dlg.tab_chosen.connect(self.tabs.setCurrentIndex)
        # Center over window
        pos = self.frameGeometry().center() - dlg.rect().center()
        dlg.move(pos); dlg.exec_()

    def show_about(self):
        dlg = AboutDialog(self)
        dlg.exec_()

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
    # ── Должны быть ДО QApplication ──────────────────────────────────────────
    # Отключаем sandbox — на Windows часто мешает JS
    os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
    # Флаги Chromium: включаем NetworkService (нужен для YouTube)
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        # Сеть
        "--enable-features=NetworkService,NetworkServiceInProcess"
        # Рендеринг
        " --force-color-profile=srgb"
        " --enable-gpu-rasterization"
        " --enable-accelerated-2d-canvas"
        " --ignore-gpu-blocklist"
        " --ignore-gpu-driver-bug-workarounds"
        # Убрать флаг автоматизации (нужен для Google Login)
        " --disable-blink-features=AutomationControlled"
        # Медиа: autoplay без жеста, Media Foundation для видео на Windows
        " --autoplay-policy=no-user-gesture-required"
        " --enable-features=MediaFoundationVideoCapture"
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ES-Browser")
    app.setStyle("Fusion")
    f = app.font(); f.setFamily("Segoe UI"); f.setPointSize(10); app.setFont(f)

    # Глобальный фильтр доп. кнопок мыши (назад/вперёд)
    _mouse_filter = _NavMouseFilter()
    app.installEventFilter(_mouse_filter)

    win = MainWindow()
    win.resize(1300, 840)
    win.show()
    sys.exit(app.exec_())
