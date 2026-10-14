# -*- coding: utf-8 -*-
"""What's New

Behavior
--------
- First normal run: show every installed production-ready feature.
- Later normal runs: show newly added features and existing features whose help.html changed.
- Shift-click/config mode: always show the full feature catalog and do
  not change the seen-state.

A production-ready feature is a folder containing help.html. Bundle folders
can also provide icon.png (preferred), icon.dark.png, icon.svg, icon.jpg, or
icon.jpeg. The feature title is read from help.html <title>, falling back to
its folder name. A trailing " - Help" is removed from displayed titles.
"""
__title__ = "What's\nNew"
__author__ = "Aaron"
__doc__ = ("Shows all installed production-ready features on first run, then "
           "newly added or improved features. Shift-click to see the full catalog.")

import io
import os
import re
import json
import codecs
import hashlib
import tempfile
import webbrowser
import uuid
from datetime import datetime

from pyrevit import forms, script

try:
    unicode  # IronPython 2
except NameError:
    unicode = str

# --------------------------------------------------------------------------
# WPF loading support
# --------------------------------------------------------------------------
try:
    import clr
    clr.AddReference("PresentationFramework")
    clr.AddReference("PresentationCore")
    clr.AddReference("WindowsBase")

    from System import Action, Uri, UriKind
    from System.Windows.Threading import DispatcherPriority
    from System.Windows.Media.Imaging import BitmapImage, BitmapCacheOption
    WPF_AVAILABLE = True
except Exception:
    WPF_AVAILABLE = False


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_TITLE = "What's New"
HELP_FILE_NAME = "help.html"          # matched case-insensitively
EXTRA_ROOTS = []                       # optional additional extension roots

BUNDLE_EXTS = (".pushbutton", ".smartbutton", ".toggle",
               ".linkbutton", ".invokebutton", ".urlbutton")
ICON_NAMES = ("icon.png", "icon.dark.png", "icon.svg", "icon.jpg", "icon.jpeg")

WELCOME_XAML = os.path.join(HERE, "Welcome.xaml")



# --------------------------------------------------------------------------
# Loading window
# --------------------------------------------------------------------------
class LoadingWindow(object):
    """Use Welcome.xaml as the modeless determinate loading screen."""

    def __init__(self):
        self.window = None
        self.status = None
        self.percent = None
        self.bar = None
        if not WPF_AVAILABLE or not os.path.exists(WELCOME_XAML):
            return
        try:
            self.window = forms.WPFWindow(WELCOME_XAML)
            self.status = self.window.StatusText
            self.percent = self.window.PercentText
            self.bar = self.window.LoadProgress

            # Use the PyPiPie brand logo in the splash screen when present.
            # Fall back to the local button icon for older installs.
            icon_path = self._find_local_logo()
            if icon_path:
                try:
                    bmp = BitmapImage()
                    bmp.BeginInit()
                    bmp.UriSource = Uri(icon_path, UriKind.Absolute)
                    bmp.CacheOption = BitmapCacheOption.OnLoad
                    bmp.EndInit()
                    bmp.Freeze()
                    self.window.LogoImage.Source = bmp
                except Exception:
                    try:
                        self.window.LogoImage.Source = BitmapImage(Uri(icon_path, UriKind.Absolute))
                    except Exception:
                        pass

            self.window.Show()
            self._pump()
        except Exception:
            self.window = None
            self.status = None
            self.percent = None
            self.bar = None

    def _find_local_logo(self):
        # Preferred branding file supplied with the What's New tool.
        # Keep icon.* fallbacks so older installs still display something.
        for name in ("PyPiPie_Logo.png", "pypipie_logo.png",
                     "icon.png", "icon.dark.png", "icon.jpg", "icon.jpeg"):
            path = os.path.join(HERE, name)
            if os.path.exists(path):
                return os.path.abspath(path)
        return None

    def _pump(self):
        if not self.window:
            return
        try:
            self.window.Dispatcher.Invoke(
                DispatcherPriority.Background,
                Action(lambda: None))
        except Exception:
            pass

    def update(self, value, message=None):
        if not self.window:
            return
        try:
            value = max(0, min(100, int(value)))
            self.bar.Value = value
            self.percent.Text = "%d%%" % value
            if message:
                self.status.Text = message
            self._pump()
        except Exception:
            pass

    def close(self):
        if not self.window:
            return
        try:
            self.update(100, "Complete")
            self.window.Close()
        except Exception:
            pass
        self.window = None


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def read_text(path):
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return u""


def esc(text):
    if text is None:
        return u""
    if not isinstance(text, (str, unicode)):
        text = unicode(text)
    return (text.replace(u"&", u"&amp;").replace(u"<", u"&lt;")
                .replace(u">", u"&gt;").replace(u'"', u"&quot;"))


def unesc(text):
    return (text.replace(u"&lt;", u"<").replace(u"&gt;", u">")
                .replace(u"&quot;", u'"').replace(u"&#39;", u"'")
                .replace(u"&amp;", u"&"))


def file_uri(path):
    path = os.path.abspath(path).replace("\\", "/")
    return u"file:///" + path.replace("%", "%25").replace(" ", "%20").replace("#", "%23")


def clean_value(val):
    val = unesc((val or u"").strip())
    return re.sub(r"\s+", u" ", val).strip()


def clean_title(title):
    """Remove help-page suffixes so the card shows only the feature name."""
    title = clean_value(title)
    title = re.sub(u"\\s*[-\u2013\u2014]\\s*help\\s*$", u"", title,
                   flags=re.I)
    return title.strip()


def pretty_date(dt):
    return dt.strftime("%b %d, %Y") if isinstance(dt, datetime) else u""


def parse_date(text):
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d")
    except Exception:
        return None


# --------------------------------------------------------------------------
# help.html parsing
# --------------------------------------------------------------------------
def html_meta(text):
    info = {}
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if m and m.group(1).strip():
        info["title"] = clean_value(m.group(1))
    for tag in re.findall(r"<meta\b[^>]*>", text, re.I):
        n = re.search(r"name\s*=\s*[\"']([^\"']+)[\"']", tag, re.I)
        c = re.search(r"content\s*=\s*[\"']([^\"']*)[\"']", tag, re.I)
        if n and c:
            info[n.group(1).strip().lower()] = clean_value(c.group(1))
    return info


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
def find_extension_root():
    p = HERE
    while True:
        if os.path.basename(p).lower().endswith(".extension"):
            return p
        parent = os.path.dirname(p)
        if not parent or parent == p:
            return None
        p = parent


def nice_name(folder_name):
    stem = os.path.splitext(folder_name)[0]
    return stem.replace("_", " ").replace("-", " ").strip() or stem


def crumb_for(root, folder):
    rel = os.path.relpath(os.path.dirname(folder), root)
    if rel in (".", ""):
        return u""
    parts = [os.path.splitext(x)[0] for x in rel.split(os.sep) if x]
    return u" › ".join(parts)


def find_icon(dirpath, filenames):
    by_lower = dict((name.lower(), name) for name in filenames)
    for wanted in ICON_NAMES:
        actual = by_lower.get(wanted.lower())
        if actual:
            return os.path.join(dirpath, actual)
    return None


def collect_help_dirs(root):
    """Collect candidate folders first so the parsing pass has real % progress."""
    found = []
    self_dir = os.path.normcase(HERE)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d != "__pycache__"]
        help_name = None
        for name in filenames:
            if name.lower() == HELP_FILE_NAME:
                help_name = name
                break
        if help_name and os.path.normcase(dirpath) != self_dir:
            found.append((dirpath, filenames, help_name))
    return found


def parse_help_dir(root, dirpath, filenames, help_name):
    path = os.path.join(dirpath, help_name)
    folder_name = os.path.basename(dirpath)
    info = html_meta(read_text(path))
    in_bundle = os.path.splitext(folder_name)[1].lower() in BUNDLE_EXTS

    date = parse_date(info.get("date", u""))
    if date is None:
        try:
            date = datetime.fromtimestamp(os.path.getmtime(path))
        except Exception:
            date = None

    raw_title = info.get("title") or nice_name(folder_name)
    title = clean_title(raw_title) or nice_name(folder_name)
    icon_path = find_icon(dirpath, filenames)

    try:
        with open(path, "rb") as hf:
            help_hash = hashlib.md5(hf.read()).hexdigest()
    except Exception:
        help_hash = u""

    return {
        "id": u"help:" + os.path.relpath(dirpath, root).replace("\\", "/"),
        "title": title,
        "desc": info.get("description", u""),
        "chip": info.get("type") or (u"Tool" if in_bundle else u"Feature"),
        "crumb": crumb_for(root, dirpath),
        "date": date,
        "hash": help_hash,
        "link": file_uri(path),
        "icon": file_uri(icon_path) if icon_path else None,
    }


def discover(progress=None):
    roots = []
    own = find_extension_root()
    if own:
        roots.append(own)
    roots.extend(r for r in EXTRA_ROOTS if os.path.isdir(r))

    if progress:
        progress.update(5, "Finding extension folders...")

    candidates = []
    for root in roots:
        if progress:
            progress.update(10, "Indexing installed features...")
        for dirpath, filenames, help_name in collect_help_dirs(root):
            candidates.append((root, dirpath, filenames, help_name))

    if progress:
        progress.update(20, "Reading feature help and icons...")

    items = []
    total = len(candidates)
    for index, data in enumerate(candidates):
        root, dirpath, filenames, help_name = data
        it = parse_help_dir(root, dirpath, filenames, help_name)
        if len(roots) > 1:
            it["id"] = os.path.basename(root) + u"::" + it["id"]
        items.append(it)
        if progress and total:
            pct = 20 + int((float(index + 1) / float(total)) * 65.0)
            progress.update(pct, "Loading %s..." % it["title"])

    return items, roots


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
STATE_VERSION = 7
STATE_SOURCE = u"not loaded"
STATE_COUNT = 0
STATE_STATUS = u"not checked"
RUN_MODE = u"Normal"


def _normalize_feature_id(value):
    if value is None:
        return None
    value = unicode(value).replace(u"\\", u"/").strip()
    return value.lower()


def _normalize_seen(values):
    result = {}
    for key in values or []:
        norm = _normalize_feature_id(key)
        if norm:
            result[norm] = True
    return result


def _normalize_hashes(values):
    result = {}
    if not isinstance(values, dict):
        return result
    for key, value in values.items():
        norm = _normalize_feature_id(key)
        if norm and value:
            result[norm] = unicode(value).strip().lower()
    return result


def _windows_roaming_appdata():
    """Resolve Roaming AppData through .NET first, then environment fallback."""
    try:
        from System import Environment
        path = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
        if path:
            return unicode(path)
    except Exception:
        pass
    return unicode(os.environ.get("APPDATA") or os.path.expanduser("~"))


STATE_DIR = os.path.join(_windows_roaming_appdata(), "PyPiPie", "WhatsNew")
STATE_FILE = os.path.join(STATE_DIR, "state.json")

# Previous builds are migration sources only.
_LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
V3_STATE_FILE = os.path.join(_LOCALAPPDATA, "PyPiPie", "WhatsNew", "state.json")
LEGACY_STATE_FILE = os.path.join((os.environ.get("APPDATA") or os.path.expanduser("~")), "pyRevit", "whats_new_state.json")


def _state_from_payload(payload):
    if not isinstance(payload, dict):
        return False, {}, {}

    initialized = bool(payload.get("initialized", False))
    hashes = _normalize_hashes(payload.get("feature_hashes", {}))
    raw = payload.get("seen_ids")
    if isinstance(raw, list):
        return initialized, _normalize_seen(raw), hashes

    # Migrate the old {"items": {...}} format. Older builds may have stored
    # hashes as values, so preserve those when they look usable.
    raw = payload.get("items")
    if isinstance(raw, dict):
        values = raw.keys()
        if not hashes:
            possible = {}
            for key, value in raw.items():
                if isinstance(value, (str, unicode)) and value:
                    possible[key] = value
            hashes = _normalize_hashes(possible)
    elif isinstance(raw, list):
        values = raw
    else:
        values = []

    seen = _normalize_seen(values)
    if seen:
        initialized = True
    return initialized, seen, hashes


def _read_json_file(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_state_file(path):
    payload = _read_json_file(path)
    if payload is None:
        return None
    initialized, seen, hashes = _state_from_payload(payload)
    return {"initialized": initialized, "seen": seen, "hashes": hashes}


def load_state():
    """Load the explicit per-user state file, with one-time legacy migration."""
    global STATE_SOURCE, STATE_COUNT, STATE_STATUS

    current = _read_state_file(STATE_FILE)
    if current is not None and current.get("initialized"):
        STATE_SOURCE = u"Roaming AppData"
        STATE_COUNT = len(current.get("seen", {}))
        STATE_STATUS = u"loaded"
        return current

    # Migration sources from previous revisions.
    migration_paths = []
    for path in (V3_STATE_FILE, LEGACY_STATE_FILE):
        if os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.abspath(STATE_FILE)):
            migration_paths.append(path)

    for path in migration_paths:
        old = _read_state_file(path)
        if old is not None and old.get("initialized"):
            STATE_SOURCE = u"legacy state"
            STATE_COUNT = len(old.get("seen", {}))
            STATE_STATUS = u"migration pending"
            return old

    STATE_SOURCE = u"new state"
    STATE_COUNT = 0
    STATE_STATUS = u"not initialized"
    return {"initialized": False, "seen": {}}


def _ensure_state_dir():
    if not os.path.isdir(STATE_DIR):
        try:
            from System.IO import Directory
            Directory.CreateDirectory(STATE_DIR)
        except Exception:
            if not os.path.isdir(STATE_DIR):
                os.makedirs(STATE_DIR)


def _write_text_atomic(path, text):
    """Write with .NET when available, then replace the target atomically."""
    _ensure_state_dir()
    temp_path = path + ".tmp"

    try:
        from System.IO import File
        from System.Text import UTF8Encoding
        enc = UTF8Encoding(False)
        File.WriteAllText(temp_path, unicode(text), enc)
        if File.Exists(path):
            File.Delete(path)
        File.Move(temp_path, path)
        return
    except Exception:
        pass

    with io.open(temp_path, "w", encoding="utf-8") as f:
        f.write(unicode(text))
    if os.path.exists(path):
        os.remove(path)
    os.rename(temp_path, path)


def save_state(known, hashes=None, initialized=True):
    """Persist state and immediately prove that it can be read back."""
    global STATE_SOURCE, STATE_COUNT, STATE_STATUS

    items = sorted(set(_normalize_feature_id(key) for key in known.keys() if key))
    normalized_hashes = _normalize_hashes(hashes or {})
    payload = {
        "version": STATE_VERSION,
        "initialized": bool(initialized),
        "seen_ids": items,
        "feature_hashes": normalized_hashes,
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_text_atomic(STATE_FILE, json.dumps(payload, indent=2))

    check = _read_state_file(STATE_FILE)
    if check is None:
        raise Exception("State file was written but could not be read back: {}".format(STATE_FILE))
    if not check.get("initialized"):
        raise Exception("State file read back as uninitialized: {}".format(STATE_FILE))

    expected = set(items)
    actual = set(check.get("seen", {}).keys())
    if expected != actual:
        raise Exception("State verification failed. Expected {} feature IDs but read back {}.\n{}".format(
            len(expected), len(actual), STATE_FILE))

    actual_hashes = check.get("hashes", {}) or {}
    for key, value in normalized_hashes.items():
        if actual_hashes.get(key) != value:
            raise Exception("State hash verification failed for {}.\n{}".format(key, STATE_FILE))

    STATE_SOURCE = u"Roaming AppData"
    STATE_COUNT = len(actual)
    STATE_STATUS = u"saved + verified"
    return True


def try_save(known, hashes=None, initialized=True):
    global STATE_STATUS
    try:
        save_state(known, hashes, initialized)
        return True
    except Exception as ex:
        STATE_STATUS = u"SAVE FAILED: " + unicode(ex)
        forms.alert(
            "What's New could not save its feature history.\n\n{}\n\nState file:\n{}".format(ex, STATE_FILE),
            title=PAGE_TITLE)
        return False


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
CSS = u"""
:root { --bg:#f4f6f9; --card:#fff; --ink:#1d2733; --muted:#6b7785;
        --accent:#0b6bcb; --warn:#b36b00; --line:#e3e8ee; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#14181d; --card:#1d232a; --ink:#e8edf2; --muted:#8d99a6;
          --accent:#4aa3ff; --warn:#f0a63a; --line:#2b333c; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:15px/1.5 "Segoe UI",system-ui,sans-serif; }
.wrap { max-width:820px; margin:0 auto; padding:32px 20px 60px; }
header { margin-bottom:18px; }
.brand-header { display:flex; align-items:center; gap:18px; }
.brand-logo { width:92px; height:auto; max-height:106px; object-fit:contain; flex:0 0 auto; }
.brand-copy { min-width:0; }
header h1 { margin:0; font-size:28px; }
header p { margin:4px 0 8px; color:var(--muted); }
h3.section { margin:28px 0 10px; font-size:13px; letter-spacing:.08em;
             text-transform:uppercase; color:var(--muted); }
.card { background:var(--card); border:1px solid var(--line);
        border-radius:10px; padding:16px 20px; margin-bottom:12px; }
.feature { display:flex; align-items:flex-start; gap:14px; }
.feature-icon { width:48px; height:48px; flex:0 0 48px; object-fit:contain;
                border-radius:7px; }
.feature-body { min-width:0; flex:1; }
.row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.card h2 { margin:0; font-size:18px; }
.badge { display:inline-block; color:#fff; text-decoration:none; font-size:11px;
         font-weight:700; padding:2px 8px; border-radius:99px;
         background:var(--accent); }
.badge:hover { text-decoration:underline; }
.badge.improved { background:var(--warn); }
.meta { color:var(--muted); font-size:13px; margin:2px 0 8px; }
.chip { margin-left:8px; padding:1px 8px; border:1px solid var(--line);
        border-radius:6px; font-size:12px; }
.card p { margin:0 0 6px; }
a { color:var(--accent); }
.empty { text-align:center; padding:36px 20px; color:var(--muted); }
footer { margin-top:28px; color:var(--muted); font-size:12px; text-align:center; }
"""


def render_card(it, status):
    badge = u""
    if status == "new":
        badge = u'<a class="badge" href="%s" title="Open help">NEW</a>' % it["link"]
    elif status == "improved":
        badge = u'<a class="badge improved" href="%s" title="Open revised help">IMPROVED</a>' % it["link"]

    meta = [pretty_date(it.get("date")), it.get("crumb")]
    meta_html = u" &middot; ".join(esc(m) for m in meta if m)
    chip = (u'<span class="chip">%s</span>' % esc(it["chip"])) if it.get("chip") else u""
    icon = (u'<img class="feature-icon" src="%s" alt="">' % it["icon"])
    if not it.get("icon"):
        icon = u""

    html = (u'<div class="card"><div class="feature">%s<div class="feature-body">'
            u'<div class="row"><h2>%s</h2>%s</div>'
            u'<div class="meta">%s%s</div>') % (
                icon, esc(it["title"]), badge, meta_html, chip)
    if it.get("desc"):
        html += u"<p>%s</p>" % esc(it["desc"])
    html += u'<p><a href="%s">Open help</a></p>' % it["link"]
    return html + u"</div></div></div>"


def build_html(sections, subtitle, message=None):
    parts = []
    for heading, entries in sections:
        if not entries:
            continue
        parts.append(u'<h3 class="section">%s (%d)</h3>' % (esc(heading), len(entries)))
        parts.extend(render_card(it, status) for it, status in entries)
    if message:
        parts.insert(0, u'<div class="card empty"><h2>%s</h2><p>%s</p></div>' % (
            esc(message[0]), esc(message[1])))
    brand_path = os.path.join(HERE, "PyPiPie_Logo.png")
    if not os.path.exists(brand_path):
        brand_path = os.path.join(HERE, "pypipie_logo.png")
    if os.path.exists(brand_path):
        brand_html = (u'<img class="brand-logo" src="%s" alt="PyPiPie">' %
                      file_uri(brand_path))
    else:
        brand_html = u""

    return (u'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            u'<meta name="viewport" content="width=device-width,initial-scale=1">'
            u'<title>%s</title><style>%s</style></head><body><div class="wrap">'
            u'<header><div class="brand-header">%s<div class="brand-copy">'
            u'<h1>%s</h1><p>%s</p></div></div></header>%s'
            u'<footer>Generated %s<br><span style="opacity:.72">Mode: %s<br>State: %s &middot; %d seen &middot; %s<br>File: %s</span></footer>'
            u'</div></body></html>') % (
        esc(PAGE_TITLE), CSS, brand_html, esc(PAGE_TITLE), esc(subtitle),
        u"".join(parts), datetime.now().strftime("%b %d, %Y %I:%M %p"),
        esc(RUN_MODE), esc(STATE_SOURCE), STATE_COUNT, esc(STATE_STATUS), esc(STATE_FILE))


def _cleanup_old_html(prefix="pyrevit_whats_new"):
    """Remove older temporary What's New pages so stale files do not accumulate."""
    temp_dir = tempfile.gettempdir()
    try:
        for name in os.listdir(temp_dir):
            low = name.lower()
            if low.startswith(prefix.lower()) and low.endswith(".html"):
                try:
                    os.remove(os.path.join(temp_dir, name))
                except Exception:
                    # An already-open browser tab can keep a file locked. That is
                    # harmless because every run gets a brand-new filename below.
                    pass
    except Exception:
        pass


def show_html(html, stem="pyrevit_whats_new"):
    """Write and open a fresh HTML file every run.

    Using a unique filename is intentional: browsers often reuse an existing
    file:// tab without refreshing it when os.startfile() is given the same path.
    A fresh path guarantees the user sees the HTML generated by this execution.
    """
    _cleanup_old_html()
    unique = uuid.uuid4().hex
    name = "%s_%s.html" % (stem, unique)
    path = os.path.join(tempfile.gettempdir(), name)
    with codecs.open(path, "w", "utf-8") as f:
        f.write(html)
    try:
        os.startfile(path)
    except Exception:
        webbrowser.open(file_uri(path))
    return path


def sort_key(it):
    d = it.get("date")
    return d.strftime("%Y-%m-%d") if isinstance(d, datetime) else u""


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main(show_all=False):
    loader = LoadingWindow()
    try:
        loader.update(2, "Starting...")
        items, roots = discover(loader)
        if not roots:
            loader.close()
            forms.alert("Could not find the .extension folder this button lives in.",
                        title=PAGE_TITLE)
            return

        loader.update(88, "Checking what you have already seen...")
        # Execution mode is explicit. Normal script calls main(False);
        # config.py loads this module without auto-running it and then calls
        # main(True). Never infer mode from pyRevit runtime/global state.
        show_all = bool(show_all)
        global RUN_MODE
        RUN_MODE = u"Shift catalog" if show_all else u"Normal"
        state = load_state()
        first_run = not bool(state.get("initialized"))
        known = state.get("seen", {}) or {}
        known_hashes = state.get("hashes", {}) or {}

        # Normalize every discovered ID before comparing with persisted state.
        for it in items:
            it["id"] = _normalize_feature_id(it.get("id"))

        ordered_items = sorted(items, key=sort_key, reverse=True)

        def status_for(it):
            fid = it["id"]
            if fid not in known:
                return "new"
            old_hash = known_hashes.get(fid)
            new_hash = (it.get("hash") or u"").lower()
            if old_hash and new_hash and old_hash != new_hash:
                return "improved"
            return "seen"

        if show_all:
            # Read-only catalog. NEW and IMPROVED badges reflect current state,
            # but Shift-click never changes what has been seen.
            entries = [(it, status_for(it)) for it in ordered_items]
            html = build_html(
                [("All features", entries)],
                "All installed production-ready features (%d)" % len(items))
            loader.update(96, "Building the full feature list...")
            loader.close()
            show_html(html, "pyrevit_whats_new_all")
            return

        if first_run:
            # First normal run intentionally shows everything as NEW, then records
            # both the feature IDs and the current help-file hashes.
            entries = [(it, "new") for it in ordered_items]
            for it in items:
                known[it["id"]] = True
                if it.get("hash"):
                    known_hashes[it["id"]] = it["hash"].lower()
            loader.update(94, "Saving feature history...")
            try_save(known, known_hashes)
            html = build_html(
                [("Installed features", entries)],
                "Installed production-ready features (%d)" % len(items))
            loader.update(98, "Building your feature list...")
            loader.close()
            show_html(html)
            return

        new_items = []
        improved_items = []
        baseline_only = []
        for it in ordered_items:
            fid = it["id"]
            current_hash = (it.get("hash") or u"").lower()
            if fid not in known:
                new_items.append(it)
            else:
                old_hash = known_hashes.get(fid)
                if old_hash:
                    if current_hash and old_hash != current_hash:
                        improved_items.append(it)
                else:
                    # Migration from an older state version: the feature was
                    # already seen, but no help hash existed yet. Establish the
                    # baseline silently so upgrading does not mark everything
                    # IMPROVED once.
                    baseline_only.append(it)

        # Always refresh the complete current state after determining statuses.
        for it in items:
            known[it["id"]] = True
            if it.get("hash"):
                known_hashes[it["id"]] = it["hash"].lower()

        loader.update(94, "Saving feature history...")
        try_save(known, known_hashes)

        sections = []
        if new_items:
            sections.append(("New", [(it, "new") for it in new_items]))
        if improved_items:
            sections.append(("Improved", [(it, "improved") for it in improved_items]))

        if new_items or improved_items:
            pieces = []
            if new_items:
                pieces.append("%d new feature%s" % (len(new_items), "" if len(new_items) == 1 else "s"))
            if improved_items:
                pieces.append("%d improved feature%s" % (len(improved_items), "" if len(improved_items) == 1 else "s"))
            subtitle = " and ".join(pieces) + " since you last checked"
            html = build_html(sections, subtitle)
            loader.update(98, "Building the feature update list...")
        else:
            html = build_html(
                [], "You're all caught up",
                message=("Nothing new",
                         "No new or improved features have been added since you last checked. "
                         "Shift-click What's New to see the full feature set."))
            loader.update(98, "Nothing new found...")

        loader.close()
        show_html(html)

    except Exception:
        loader.close()
        raise


# Normal pyRevit execution always uses normal mode.
# config_script.py sets WHATS_NEW_LIBRARY_MODE only to suppress this automatic
# call while loading the shared functions, then explicitly calls main(True).
if not bool(globals().get("WHATS_NEW_LIBRARY_MODE", False)):
    main(False)
