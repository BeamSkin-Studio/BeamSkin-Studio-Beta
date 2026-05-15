"""
updater.py — GitHub update checker with in-app download/extract/restart
(PySide6 edition)
"""
from __future__ import annotations

import os
import re
import sys
import shutil
import zipfile
import logging
import subprocess
import threading
import webbrowser

import requests
from PySide6.QtCore    import Qt, QObject, QThread, Signal, QTimer
from PySide6.QtGui     import QFont
from PySide6.QtWidgets import (
    QDialog, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QProgressBar,
    QStackedWidget, QApplication,
)

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return kw.get("default", key)

log = logging.getLogger(__name__)

try:
    from gui.theme import COLORS, font, fade_in
except ImportError:
    COLORS = {
        "card_bg": "#1e1e2e", "frame_bg": "#181825",
        "accent": "#7c3aed", "accent_hover": "#6d28d9", "accent_dim": "#5b21b6",
        "accent_text": "#ffffff", "text": "#cdd6f4", "text_secondary": "#a6adc8",
        "border": "#313244", "card_hover": "#27273a",
        "success": "#a6e3a1", "error": "#f38ba8", "warning": "#f9e2af",
    }
    def font(size=13, weight="normal"):
        f = QFont("Segoe UI", size); f.setBold(weight == "bold"); return f
    def fade_in(w, duration=200): pass


# ── path helpers ──────────────────────────────────────────────────────────── #

def get_github_repo():
    if sys.platform == "win32":
        return "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Beta"
    return "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Linux-Beta"

def get_releases_api_url():
    repo = "BeamSkin-Studio-Beta" if sys.platform == "win32" else "BeamSkin-Studio-Linux-Beta"
    return f"https://api.github.com/repos/BeamSkin-Studio/{repo}/releases/latest"

# Populated by fetch_latest_release(); used by get_zip_url().
_latest_release_zip_url: str = ""

def get_zip_url():
    """Return the zip download URL from the latest GitHub release.

    Falls back to a sensible URL if fetch_latest_release() has not been
    called yet (e.g. in headless / fallback flows).
    """
    if _latest_release_zip_url:
        return _latest_release_zip_url
    repo = "BeamSkin-Studio-Beta" if sys.platform == "win32" else "BeamSkin-Studio-Linux-Beta"
    return f"https://github.com/BeamSkin-Studio/{repo}/releases/latest/download/BeamSkin-Studio.zip"

def fetch_latest_release():
    """Call the GitHub Releases API and return (version_string, zip_url).

    Also caches the zip URL in ``_latest_release_zip_url`` so that
    ``get_zip_url()`` can return it without making a second API call.

    Raises ``requests.HTTPError`` or ``KeyError`` on failure.
    """
    global _latest_release_zip_url
    resp = requests.get(
        get_releases_api_url(),
        timeout=10,
        headers={"Accept": "application/vnd.github+json"},
    )
    resp.raise_for_status()
    data = resp.json()

    tag = re.sub(r"^[Vv]\.?", "", data["tag_name"])  # "V.0.7.11.Beta" → "0.7.11.Beta"
    version = _format_version_string(tag)

    # Prefer an explicit .zip release asset; fall back to the auto-generated
    # zipball (source archive) which GitHub always provides.
    zip_url = data.get("zipball_url", "")
    for asset in data.get("assets", []):
        if asset.get("name", "").endswith(".zip"):
            zip_url = asset["browser_download_url"]
            break

    _latest_release_zip_url = zip_url
    log.debug("fetch_latest_release: version=%s  zip_url=%s", version, zip_url)
    return version, zip_url

def get_base_path():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(os.path.abspath(__file__))

def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # updater.py lives in core/ — parent of parent is app root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_downloads_folder():
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            ) as key:
                return winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Downloads")


# ── version helpers ───────────────────────────────────────────────────────── #

def _format_version_string(raw: str) -> str:
    """Parse a raw version.txt string into a canonical 'M.m.p.Status' form."""
    content = raw.strip().replace("Version:", "").strip()
    parts = content.split(".")
    if len(parts) >= 3:
        major, minor, patch = parts[0], parts[1], parts[2]
        if len(parts) >= 4:
            try:
                build  = int(parts[3])
                status = "Beta" if build == 0 else f"Build {build}"
            except ValueError:
                status = parts[3].capitalize()
        else:
            status = "Stable"
        return f"{major}.{minor}.{patch}.{status}"
    return content


def read_version():
    log.debug("read_version called")
    for p in [os.path.join(get_base_path(), "version.txt"),
              os.path.join(os.getcwd(), "version.txt"), "version.txt"]:
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r") as f:
                return _format_version_string(f.read())
        except Exception as e:
            log.debug("Failed to read %s: %s", p, e)
    return "0.0.0.Unknown"

def parse_version(s: str):
    s = s.lower().strip().replace("version:", "").replace("v", "").strip()
    m = re.match(r"(\d+)\.(\d+)\.(\d+)\.?(.*)", s)
    if m:
        major, minor, patch, suffix = m.groups()
        prio = {"stable": 0, "": 0, "rc": 1, "beta": 2, "alpha": 3}.get(
            (suffix or "stable").lower().strip(), 2)
        return (int(major), int(minor), int(patch), prio)
    return (0, 0, 0, 999)

def is_newer_version(remote: str, current: str) -> bool:
    try:
        r, c = parse_version(remote), parse_version(current)
        log.debug("Parsed current: %s -> %s", current, c)
        log.debug("Parsed remote:  %s -> %s", remote, r)
        return r[:3] > c[:3] if r[:3] != c[:3] else r[3] < c[3]
    except Exception as e:
        log.debug("Version comparison error: %s", e)
        return remote != current

CURRENT_VERSION = read_version()

_app_instance      = None
_colors            = None
_pending_signaller = None   # kept alive until the update check resolves

def set_app_instance(app, colors):
    global _app_instance, _colors
    _app_instance = app
    _colors       = colors
    log.debug("set_app_instance called")


# ── skip-version helpers ──────────────────────────────────────────────────── #

def get_skipped_version() -> str:
    """Return the version string the user chose to skip, or '' if none."""
    try:
        import core.settings as _s
        return _s.app_settings.get("skipped_update_version", "")
    except Exception:
        return ""


def set_skipped_version(version: str) -> None:
    """Persist the version the user wants to skip (pass '' to clear)."""
    log.debug("set_skipped_version: %r", version)
    try:
        import core.settings as _s
        _s.app_settings["skipped_update_version"] = version
        _s.save_settings()
    except Exception as e:
        log.warning("set_skipped_version: could not persist: %s", e)


# ── background workers ────────────────────────────────────────────────────── #

class _DownloadWorker(QThread):
    progress = Signal(int, int)   # bytes_done, total_bytes
    finished = Signal(str)        # filepath on success
    failed   = Signal(str)        # error message on failure

    def __init__(self, url: str, dest: str):
        super().__init__()
        self._url  = url
        self._dest = dest

    def run(self):
        try:
            r = requests.get(self._url, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done  = 0
            with open(self._dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if self.isInterruptionRequested():
                        return
                    f.write(chunk)
                    done += len(chunk)
                    self.progress.emit(done, total)
            self.finished.emit(self._dest)
        except Exception as e:
            self.failed.emit(str(e))


class _ExtractWorker(QThread):
    status   = Signal(str)   # status text
    finished = Signal(int)   # files_updated count
    failed   = Signal(str)   # error message

    # ── Tier 1: individual files whose content is backed up before overwriting
    #           and restored afterwards (user-edited JSON blobs).
    PRESERVE: set = {
        os.path.join("data",     "app_settings.json"),
        os.path.join("vehicles", "added_vehicles.json"),
    }

    # ── Tier 2: directory prefixes that are NEVER overwritten during the copy
    #           step, regardless of what the zip contains.  The files already
    #           on disk are left completely intact.
    #
    #   • data/ — every file in here is user state; the zip has no business
    #             touching any of it (app_settings, project_registry,
    #             seen_changelogs, etc.)
    NEVER_OVERWRITE_PREFIXES: frozenset = frozenset({
        "data",
    })

    # ── Tier 3: directory prefixes where existing files are NEVER deleted
    #           during cleanup, even if the new zip doesn't contain them.
    #           New files shipped by the update ARE still copied in — only
    #           deletions are blocked inside these trees.
    #
    #   • data/               — all user settings / state (also in Tier 2)
    #   • vehicles/           — vehicle template trees (may have user-created ones)
    #   • gui/images/vehicles — bundled vehicle preview images
    NEVER_DELETE_PREFIXES: frozenset = frozenset({
        "data",
        "vehicles",
        os.path.join("gui", "images", "vehicles"),
    })

    def __init__(self, zip_path: str, new_version: str):
        super().__init__()
        self._zip     = zip_path
        self._version = new_version

    # ── helpers ──────────────────────────────────────────────────────────────

    @classmethod
    def _is_overwrite_protected(cls, rel_norm: str) -> bool:
        """Return True if this path must never be overwritten by the zip."""
        parts = rel_norm.split(os.sep)
        for prefix in cls.NEVER_OVERWRITE_PREFIXES:
            prefix_parts = prefix.split(os.sep)
            if parts[: len(prefix_parts)] == prefix_parts:
                return True
        return False

    @classmethod
    def _is_deletion_protected(cls, rel_norm: str) -> bool:
        """Return True if this on-disk relative path must never be deleted."""
        parts = rel_norm.split(os.sep)
        # Always keep __pycache__ and compiled bytecode — not shipped in zip.
        if "__pycache__" in parts or rel_norm.endswith(".pyc"):
            return True
        # Keep anything rooted inside a NEVER_DELETE prefix.
        for prefix in cls.NEVER_DELETE_PREFIXES:
            prefix_parts = prefix.split(os.sep)
            if parts[: len(prefix_parts)] == prefix_parts:
                return True
        return False

    # ── main run ─────────────────────────────────────────────────────────────

    def run(self):
        try:
            app_dir   = get_app_dir()
            dl_folder = os.path.dirname(self._zip)
            temp_dir  = os.path.join(dl_folder, f"BeamSkin-Studio-temp-{self._version}")

            # ── 1. Extract zip to a temp location ────────────────────────── #
            self.status.emit("Extracting archive\u2026")
            with zipfile.ZipFile(self._zip, "r") as z:
                z.extractall(temp_dir)

            contents = os.listdir(temp_dir)
            source   = (os.path.join(temp_dir, contents[0])
                        if len(contents) == 1 and
                           os.path.isdir(os.path.join(temp_dir, contents[0]))
                        else temp_dir)

            # ── 2. Collect every relative path the new version ships ──────── #
            #       (used in step 5 to detect files that no longer exist)
            incoming: set = set()
            for root, _, files in os.walk(source):
                for fname in files:
                    rel = os.path.relpath(os.path.join(root, fname), source)
                    incoming.add(rel.replace("/", os.sep).replace("\\", os.sep))

            # ── 3. Back up Tier-1 preserved files ────────────────────────── #
            backups: dict = {}
            for rel in self.PRESERVE:
                full = os.path.join(app_dir, rel)
                if os.path.exists(full):
                    try:
                        with open(full, "r", encoding="utf-8") as f:
                            backups[rel] = f.read()
                    except Exception:
                        pass

            # ── 4. Copy new / changed files into app_dir ─────────────────── #
            self.status.emit("Copying files\u2026")
            updated = 0
            preserve_norm = {p.replace("/", os.sep).replace("\\", os.sep)
                             for p in self.PRESERVE}
            for root, _, files in os.walk(source):
                if self.isInterruptionRequested():
                    return
                rel_dir    = os.path.relpath(root, source)
                target_dir = app_dir if rel_dir == "." else os.path.join(app_dir, rel_dir)
                os.makedirs(target_dir, exist_ok=True)
                for fname in files:
                    rel_file = fname if rel_dir == "." else os.path.join(rel_dir, fname)
                    rel_norm = rel_file.replace("/", os.sep).replace("\\", os.sep)
                    if rel_norm in preserve_norm:
                        continue   # will be restored from backup in step 6
                    if self._is_overwrite_protected(rel_norm):
                        continue   # entire directory is off-limits for writes
                    try:
                        shutil.copy2(os.path.join(root, fname),
                                     os.path.join(target_dir, fname))
                        updated += 1
                    except Exception:
                        pass

            # ── 5. Remove files the new version no longer ships ───────────── #
            #       Skips anything covered by _is_deletion_protected().
            self.status.emit("Removing obsolete files\u2026")
            for root, dirs, files in os.walk(app_dir, topdown=False):
                if self.isInterruptionRequested():
                    return
                for fname in files:
                    full     = os.path.join(root, fname)
                    rel_norm = os.path.relpath(full, app_dir)
                    if rel_norm in incoming:
                        continue   # still present in new version — keep
                    if rel_norm in preserve_norm:
                        continue   # handled separately
                    if self._is_deletion_protected(rel_norm):
                        continue   # protected tree — never touch
                    try:
                        os.remove(full)
                        log.debug("Removed obsolete file: %s", rel_norm)
                    except Exception as e:
                        log.warning("Could not remove %s: %s", rel_norm, e)
                # Remove directories that are now empty, but only if they
                # are not inside a protected tree.
                for dname in dirs:
                    dpath    = os.path.join(root, dname)
                    rel_norm = os.path.relpath(dpath, app_dir)
                    # Pass a fake child path so the prefix check works for
                    # the directory itself, not just its contents.
                    if self._is_deletion_protected(os.path.join(rel_norm, ".keep")):
                        continue
                    try:
                        if not os.listdir(dpath):
                            os.rmdir(dpath)
                    except Exception:
                        pass

            # ── 6. Restore Tier-1 preserved files ────────────────────────── #
            for rel, content in backups.items():
                full = os.path.join(app_dir, rel)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                try:
                    with open(full, "w", encoding="utf-8") as f:
                        f.write(content)
                except Exception:
                    pass

            # ── 7. Clean up temp extraction folder and downloaded zip ─────── #
            try:   shutil.rmtree(temp_dir)
            except Exception: pass
            try:   os.remove(self._zip)
            except Exception: pass

            self.finished.emit(updated)

        except Exception as e:
            import traceback; traceback.print_exc()
            log.debug("Extract worker error: %s", e)
            self.failed.emit(str(e))


# ── update dialog (all states in one window) ──────────────────────────────── #

_PAGE_MAIN        = 0
_PAGE_DOWNLOADING = 1
_PAGE_DOWNLOADED  = 2
_PAGE_EXTRACTING  = 3
_PAGE_COMPLETE    = 4
_PAGE_DL_ERROR    = 5


class _UpdateDialog(QDialog):
    """Single dialog that transitions through all update states."""

    def __init__(self, parent: QWidget, new_version: str, on_done=None):
        super().__init__(parent)
        self._new_version = new_version
        self._on_done     = on_done
        self._done_fired  = False
        self._zip_path    = None
        self._dl_worker   = None
        self._ex_worker   = None

        self.setWindowTitle(t("update.title", default="Update Available"))
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )
        self.setModal(True)
        self.setFixedWidth(500)
        self._build()
        self.adjustSize()

    # ── on_done wiring — fires exactly once on any close path ─────────────── #

    def _fire_done(self):
        if not self._done_fired:
            self._done_fired = True
            if self._on_done:
                QTimer.singleShot(0, self._on_done)

    def closeEvent(self, event):
        for worker in (self._dl_worker, self._ex_worker):
            if worker and worker.isRunning():
                worker.requestInterruption()
        self._fire_done()
        super().closeEvent(event)

    def reject(self):
        self._fire_done()
        super().reject()

    # ── build ─────────────────────────────────────────────────────────────── #

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header ────────────────────────────────────────────────────────── #
        header = QFrame(self)
        header.setFixedHeight(120)
        header.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['frame_bg']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)

        # accent top stripe — in a VBoxLayout so it tracks dialog width
        header_vlay = QVBoxLayout(header)
        header_vlay.setContentsMargins(0, 0, 0, 0)
        header_vlay.setSpacing(0)

        stripe = QFrame()
        stripe.setFixedHeight(3)
        stripe.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {COLORS['accent']},
                    stop:0.6 {COLORS.get('accent_hover', COLORS['accent'])},
                    stop:1 {COLORS['frame_bg']});
                border:none;
            }}
        """)
        header_vlay.addWidget(stripe)

        hrow = QHBoxLayout()
        hrow.setContentsMargins(28, 0, 28, 0)
        hrow.setSpacing(18)
        header_vlay.addLayout(hrow, 1)

        # icon badge
        badge = QFrame()
        badge.setFixedSize(52, 52)
        badge.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {COLORS['accent']},
                    stop:1 {COLORS.get('accent_dim', COLORS['accent'])});
                border-radius: 14px;
                border: none;
            }}
        """)
        badge_lay = QVBoxLayout(badge)
        badge_lay.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel("↑")
        icon_lbl.setFont(font(24, "bold"))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("color: white; background: transparent; border: none;")
        badge_lay.addWidget(icon_lbl)
        hrow.addWidget(badge)

        # title block
        tcol = QVBoxLayout()
        tcol.setSpacing(4)
        t1 = QLabel(t("update.title", default="Update Available"))
        t1.setFont(font(18, "bold"))
        t1.setStyleSheet(f"color:{COLORS['text']}; background:transparent;")
        t2 = QLabel(t("update.subtitle", default="A new version of BeamSkin Studio is ready to install"))
        t2.setFont(font(11))
        t2.setStyleSheet(f"color:{COLORS['text_secondary']}; background:transparent;")
        tcol.addWidget(t1)
        tcol.addWidget(t2)
        hrow.addLayout(tcol, 1)

        root.addWidget(header)

        # ── stacked pages ─────────────────────────────────────────────────── #
        self._stack = QStackedWidget(self)
        self._stack.setStyleSheet(f"background:{COLORS['card_bg']};")
        self._stack.addWidget(self._page_main())        # 0
        self._stack.addWidget(self._page_downloading()) # 1
        self._stack.addWidget(self._page_downloaded())  # 2
        self._stack.addWidget(self._page_extracting())  # 3
        self._stack.addWidget(self._page_complete())    # 4
        self._stack.addWidget(self._page_dl_error())    # 5
        root.addWidget(self._stack)

        fade_in(self, duration=200)

    # ── widget helpers ────────────────────────────────────────────────────── #

    def _body(self):
        f = QFrame()
        f.setStyleSheet(f"background:{COLORS['card_bg']}; border:none;")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(16)
        return f, lay

    def _sep(self):
        s = QFrame()
        s.setFrameShape(QFrame.Shape.HLine)
        s.setFixedHeight(1)
        s.setStyleSheet(f"background:{COLORS['border']}; border:none;")
        return s

    def _btn(self, text, primary=True):
        b = QPushButton(text)
        b.setFont(font(12, "bold" if primary else "normal"))
        b.setFixedHeight(44)
        b.setCursor(Qt.PointingHandCursor)
        if primary:
            b.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {COLORS['accent']},
                        stop:1 {COLORS.get('accent_hover', COLORS['accent'])});
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 0 20px;
                    letter-spacing: 0.3px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {COLORS.get('accent_hover', COLORS['accent'])},
                        stop:1 {COLORS.get('accent_dim', COLORS['accent'])});
                }}
                QPushButton:pressed {{
                    background: {COLORS.get('accent_dim', COLORS['accent'])};
                }}
                QPushButton:disabled {{
                    background: {COLORS['border']};
                    color: {COLORS['text_secondary']};
                }}
            """)
        else:
            b.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_secondary']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 10px;
                    padding: 0 20px;
                }}
                QPushButton:hover {{
                    background: {COLORS.get('card_hover', COLORS['frame_bg'])};
                    color: {COLORS['text']};
                    border-color: {COLORS['accent']};
                }}
                QPushButton:pressed {{
                    background: {COLORS['frame_bg']};
                }}
                QPushButton:disabled {{
                    color: {COLORS['text_secondary']};
                }}
            """)
        return b

    def _ver_pill(self, label: str, version: str, accent: bool = False):
        """Version chip with label above version string."""
        w = QFrame()
        if accent:
            w.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 {COLORS['accent']},
                        stop:1 {COLORS.get('accent_dim', COLORS['accent'])});
                    border-radius: 10px;
                    border: none;
                }}
            """)
        else:
            w.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['frame_bg']};
                    border-radius: 10px;
                    border: 1px solid {COLORS['border']};
                }}
            """)
        col = QVBoxLayout(w)
        col.setContentsMargins(16, 10, 16, 10)
        col.setSpacing(3)

        lc = "rgba(255,255,255,0.65)" if accent else COLORS["text_secondary"]
        vc = "white" if accent else COLORS["text"]

        lbl = QLabel(label)
        lbl.setFont(font(9))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color:{lc}; background:transparent; border:none; letter-spacing:0.5px;")

        ver = QLabel(version)
        ver.setFont(font(13, "bold"))
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet(f"color:{vc}; background:transparent; border:none;")

        col.addWidget(lbl)
        col.addWidget(ver)
        return w

    def _center_lbl(self, text: str, size: int = 11, bold: bool = False, color: str = None):
        lbl = QLabel(text)
        lbl.setFont(font(size, "bold" if bold else "normal"))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color:{color or COLORS['text_secondary']}; background:transparent; border:none;"
        )
        return lbl

    def _progress_bar(self, indeterminate: bool = False):
        """Styled progress bar — determinate or indeterminate (busy)."""
        bar = QProgressBar()
        if indeterminate:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(0)
        bar.setFixedHeight(6)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS['frame_bg']};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {COLORS['accent']},
                    stop:1 {COLORS.get('accent_hover', COLORS['accent'])});
                border-radius: 3px;
            }}
        """)
        return bar

    def _status_card(self, text: str, color: str = None):
        """Subtle inset card for file path / status text."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['frame_bg']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lbl = QLabel(text)
        lbl.setFont(font(10))
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color:{color or COLORS['text_secondary']}; background:transparent; border:none;"
        )
        lay.addWidget(lbl)
        return card, lbl

    def _success_badge(self):
        """Large circular success indicator."""
        badge = QFrame()
        badge.setFixedSize(64, 64)
        badge.setStyleSheet(f"""
            QFrame {{
                background: {COLORS.get('success', '#a6e3a1')}22;
                border-radius: 32px;
                border: 2px solid {COLORS.get('success', '#a6e3a1')}66;
            }}
        """)
        lay = QVBoxLayout(badge)
        lay.setContentsMargins(0, 0, 0, 0)
        icon = QLabel("✓")
        icon.setFont(font(28, "bold"))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            f"color:{COLORS.get('success', '#a6e3a1')}; background:transparent; border:none;"
        )
        lay.addWidget(icon)
        return badge

    # ── pages ─────────────────────────────────────────────────────────────── #

    def _page_main(self):
        f, lay = self._body()

        # version comparison row
        row = QHBoxLayout()
        row.setSpacing(12)
        current_pill = self._ver_pill(
            t("update.current", default="CURRENT"),
            CURRENT_VERSION,
            accent=False,
        )
        new_pill = self._ver_pill(
            t("update.latest", default="NEW VERSION"),
            self._new_version,
            accent=True,
        )
        arrow = QLabel("→")
        arrow.setFont(font(20, "bold"))
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setFixedWidth(36)
        arrow.setStyleSheet(
            f"color:{COLORS['accent']}; background:transparent; border:none;"
        )
        row.addWidget(current_pill, 1)
        row.addWidget(arrow)
        row.addWidget(new_pill, 1)
        lay.addLayout(row)

        lay.addWidget(self._sep())

        # feature highlights
        highlights = [
            ("⚡", t("update.feat1", default="Latest features & improvements")),
            ("🛡", t("update.feat2", default="Bug fixes & stability updates")),
            ("⚙", t("update.feat3", default="Your settings will be preserved")),
        ]
        for emoji, text in highlights:
            row2 = QHBoxLayout()
            row2.setSpacing(10)
            dot = QLabel(emoji)
            dot.setFont(font(13))
            dot.setFixedWidth(24)
            dot.setStyleSheet("background:transparent; border:none;")
            desc = QLabel(text)
            desc.setFont(font(11))
            desc.setStyleSheet(
                f"color:{COLORS['text_secondary']}; background:transparent; border:none;"
            )
            row2.addWidget(dot)
            row2.addWidget(desc, 1)
            lay.addLayout(row2)

        lay.addWidget(self._sep())

        # "What's New" changelog shortcut
        changelog_btn = self._btn(
            t("update.view_changelog", default="📋  What's New in this version"),
            primary=False,
        )
        changelog_btn.clicked.connect(self._on_view_changelog)
        lay.addWidget(changelog_btn)

        lay.addWidget(self._sep())

        # buttons
        brow = QHBoxLayout()
        brow.setSpacing(10)
        later_btn    = self._btn(t("update.maybe_later",     default="Maybe Later"),     primary=False)
        download_btn = self._btn(t("update.download_update", default="Download Update"), primary=True)
        later_btn.clicked.connect(self.reject)
        download_btn.clicked.connect(self._start_download)
        brow.addWidget(later_btn)
        brow.addWidget(download_btn, 1)
        lay.addLayout(brow)

        # skip link — unobtrusive, below the main buttons
        skip_btn = QPushButton(
            t("update.skip_version", default="Skip this version")
        )
        skip_btn.setFont(font(10))
        skip_btn.setCursor(Qt.PointingHandCursor)
        skip_btn.setFlat(True)
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['text_secondary']};
                background: transparent;
                border: none;
                text-decoration: underline;
                padding: 0;
            }}
            QPushButton:hover {{ color: {COLORS['text']}; }}
        """)
        skip_btn.clicked.connect(self._skip_this_version)
        lay.addWidget(skip_btn, alignment=Qt.AlignCenter)

        return f

    def _page_downloading(self):
        f, lay = self._body()

        lay.addWidget(self._center_lbl(
            t("update.downloading", default="Downloading update…"),
            14, bold=True, color=COLORS["text"],
        ))

        self._dl_file_lbl = self._center_lbl("", 10)
        lay.addWidget(self._dl_file_lbl)

        # progress bar + percentage on same row
        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        self._dl_bar = self._progress_bar()
        self._dl_pct_lbl = QLabel("0%")
        self._dl_pct_lbl.setFont(font(10, "bold"))
        self._dl_pct_lbl.setFixedWidth(36)
        self._dl_pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._dl_pct_lbl.setStyleSheet(
            f"color:{COLORS['accent']}; background:transparent; border:none;"
        )
        prog_row.addWidget(self._dl_bar, 1)
        prog_row.addWidget(self._dl_pct_lbl)
        lay.addLayout(prog_row)

        self._dl_size_lbl = self._center_lbl("0 MB / … MB", 10)
        lay.addWidget(self._dl_size_lbl)
        return f

    def _page_downloaded(self):
        f, lay = self._body()

        # success badge centered
        badge_row = QHBoxLayout()
        badge_row.addStretch()
        badge_row.addWidget(self._success_badge())
        badge_row.addStretch()
        lay.addLayout(badge_row)

        lay.addWidget(self._center_lbl(
            t("update.download_complete", default="Download Complete"),
            15, bold=True, color=COLORS["text"],
        ))

        self._dl_path_card, self._dl_path_lbl = self._status_card("")
        lay.addWidget(self._dl_path_card)

        lay.addWidget(self._sep())

        extract_btn = self._btn(t("update.update_button",        default="Extract & Install"),    primary=True)
        open_btn    = self._btn(t("update.open_download_folder", default="Open Downloads Folder"), primary=False)
        close_btn   = self._btn(t("update.close",                default="Close"),                primary=False)
        extract_btn.clicked.connect(self._start_extract)
        open_btn.clicked.connect(self._open_downloads)
        close_btn.clicked.connect(self.reject)
        lay.addWidget(extract_btn)
        lay.addWidget(open_btn)
        lay.addWidget(close_btn)
        return f

    def _page_extracting(self):
        f, lay = self._body()

        lay.addWidget(self._center_lbl(
            t("update.extracting", default="Installing update…"),
            14, bold=True, color=COLORS["text"],
        ))
        self._ex_status_lbl = self._center_lbl("Please wait…", 11)
        lay.addWidget(self._ex_status_lbl)
        lay.addWidget(self._progress_bar(indeterminate=True))
        return f

    def _page_dl_error(self):
        f, lay = self._body()

        lay.addWidget(self._center_lbl(
            t("update.dl_failed_title", default="Download Failed"),
            15, bold=True, color=COLORS.get("error", "#f38ba8"),
        ))

        self._dl_error_lbl = self._center_lbl("", 10)
        lay.addWidget(self._dl_error_lbl)

        lay.addWidget(self._sep())

        browser_btn = self._btn(
            t("update.download_manually", default="Download Manually in Browser"),
            primary=True,
        )
        close_btn = self._btn(t("update.close", default="Close"), primary=False)
        browser_btn.clicked.connect(self._open_browser_fallback)
        close_btn.clicked.connect(self.reject)
        lay.addWidget(browser_btn)
        lay.addWidget(close_btn)
        return f

    def _open_browser_fallback(self):
        webbrowser.open(get_github_repo())
        self.reject()

    def _page_complete(self):
        f, lay = self._body()

        # success badge
        badge_row = QHBoxLayout()
        badge_row.addStretch()
        badge_row.addWidget(self._success_badge())
        badge_row.addStretch()
        lay.addLayout(badge_row)

        lay.addWidget(self._center_lbl(
            t("update.update_complete", default="Update Complete!"),
            16, bold=True, color=COLORS["text"],
        ))
        self._complete_lbl = self._center_lbl("", 11)
        lay.addWidget(self._complete_lbl)

        lay.addWidget(self._sep())

        restart_btn = self._btn(t("update.restart_now",   default="Restart Now"),   primary=True)
        later_btn   = self._btn(t("update.restart_later", default="Restart Later"), primary=False)
        restart_btn.clicked.connect(self._restart_app)
        later_btn.clicked.connect(self.reject)
        lay.addWidget(restart_btn)
        lay.addWidget(later_btn)
        return f

    # ── changelog preview ─────────────────────────────────────────────────── #

    def _on_view_changelog(self):
        """Fetch and show the changelog for the new version in a ChangelogDialog."""
        try:
            from gui.components.changelog_dialog import show_update_changelog
            show_update_changelog(self, self._new_version)
        except Exception as e:
            log.debug("Could not open changelog: %s", e)
            import webbrowser
            webbrowser.open(get_github_repo())

    # ── actions ───────────────────────────────────────────────────────────── #

    def _skip_this_version(self):
        log.debug("_skip_this_version: skipping %r", self._new_version)
        set_skipped_version(self._new_version)
        self.reject()

    def _start_download(self):
        filename       = f"BeamSkin-Studio-{self._new_version}.zip"
        self._zip_path = os.path.join(get_downloads_folder(), filename)

        self._dl_file_lbl.setText(filename)
        self._dl_bar.setValue(0)
        self._dl_size_lbl.setText("0 MB / … MB")
        self._stack.setCurrentIndex(_PAGE_DOWNLOADING)
        self.adjustSize()

        self._dl_worker = _DownloadWorker(get_zip_url(), self._zip_path)
        self._dl_worker.progress.connect(self._on_dl_progress)
        self._dl_worker.finished.connect(self._on_dl_finished)
        self._dl_worker.failed.connect(self._on_dl_failed)
        self._dl_worker.start()

    def _on_dl_progress(self, done: int, total: int):
        if total > 0:
            pct = int(done * 100 / total)
            self._dl_bar.setValue(pct)
            self._dl_pct_lbl.setText(f"{pct}%")
            self._dl_size_lbl.setText(
                f"{done/1_048_576:.1f} MB / {total/1_048_576:.1f} MB"
            )
        else:
            self._dl_size_lbl.setText(f"{done/1_048_576:.1f} MB")

    def _on_dl_finished(self, filepath: str):
        self._zip_path = filepath
        self._dl_path_lbl.setText(f"Saved to:\n{filepath}")
        self._stack.setCurrentIndex(_PAGE_DOWNLOADED)
        self.adjustSize()

    def _on_dl_failed(self, error: str):
        log.debug("Download failed: %s — showing error page", error)
        self._dl_error_lbl.setText(
            f"Error: {error}\n\nYou can download the update manually from GitHub."
        )
        self._stack.setCurrentIndex(_PAGE_DL_ERROR)
        self.adjustSize()

    def _start_extract(self):
        self._stack.setCurrentIndex(_PAGE_EXTRACTING)
        self.adjustSize()
        self._ex_worker = _ExtractWorker(self._zip_path, self._new_version)
        self._ex_worker.status.connect(self._ex_status_lbl.setText)
        self._ex_worker.finished.connect(self._on_ex_finished)
        self._ex_worker.failed.connect(self._on_ex_failed)
        self._ex_worker.start()

    def _on_ex_finished(self, files_updated: int):
        self._complete_lbl.setText(
            f"Updated {files_updated} files to version {self._new_version}.\n\n"
            "Your settings and custom vehicles have been preserved.\n\n"
            "Please restart BeamSkin Studio to use the new version."
        )
        self._stack.setCurrentIndex(_PAGE_COMPLETE)
        self.adjustSize()

    def _on_ex_failed(self, error: str):
        self._dl_path_lbl.setText(
            f"Extract failed: {error}\nYou can extract manually from the downloads folder."
        )
        self._stack.setCurrentIndex(_PAGE_DOWNLOADED)
        self.adjustSize()

    def _open_downloads(self):
        folder = os.path.dirname(self._zip_path) if self._zip_path else get_downloads_folder()
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _restart_app(self):
        self._fire_done()
        app_dir        = get_app_dir()
        batch_launcher = os.path.join(app_dir, "launchers-scripts", "quick_launcher.bat")
        py_launcher    = os.path.join(app_dir, "launchers-scripts", "quick_launcher.py")
        main_script    = os.path.join(app_dir, "main.py")
        self.accept()

        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable])
        elif sys.platform == "win32" and os.path.exists(batch_launcher):
            subprocess.Popen([batch_launcher], cwd=app_dir, shell=True)
        elif os.path.exists(py_launcher):
            subprocess.Popen(
                ["pythonw" if sys.platform == "win32" else sys.executable, py_launcher],
                cwd=app_dir,
            )
        else:
            subprocess.Popen([sys.executable, main_script], cwd=app_dir)

        QApplication.instance().quit()


# ── public API ────────────────────────────────────────────────────────────── #

class _UpdateSignaller(QObject):
    update_available = Signal(str)
    no_update        = Signal()


def prompt_update(new_version: str, on_done=None):
    log.debug("prompt_update — showing dialog for %s", new_version)
    dlg = _UpdateDialog(_app_instance, new_version, on_done=on_done)
    if _app_instance:
        pg = _app_instance.geometry()
        dlg.move(
            pg.x() + (pg.width()  - dlg.width())  // 2,
            pg.y() + (pg.height() - dlg.height()) // 2,
        )
    dlg.exec()


def check_for_updates(on_done=None):
    """
    Check GitHub for a newer version on a background thread.
    Silently skips the prompt if the remote version was previously skipped by
    the user.  on_done is called on the main thread after the dialog is
    dismissed, or immediately if no update is available / version is skipped.
    """
    _check_for_updates_impl(on_done=on_done, ignore_skip=False)


def check_for_updates_manual(on_done=None):
    """
    Same as check_for_updates() but always shows the dialog even for
    previously skipped versions.  Use this for the "Check for Updates" button.
    """
    _check_for_updates_impl(on_done=on_done, ignore_skip=True)


def _check_for_updates_impl(on_done=None, ignore_skip: bool = False):
    """
    Internal implementation shared by check_for_updates() and
    check_for_updates_manual().
    """
    global _pending_signaller
    log.debug("check_for_updates called")
    log.debug("========== UPDATE CHECK STARTED ==========")
    log.debug("Platform: %s  Repo: %s", sys.platform, get_github_repo())
    log.debug("Current:  %s", CURRENT_VERSION)
    log.debug("ignore_skip=%s  skipped=%r", ignore_skip, get_skipped_version())

    signaller = _UpdateSignaller()
    _pending_signaller = signaller   # prevent GC until thread resolves

    def _on_update(latest: str):
        global _pending_signaller
        log.debug("_on_update — main thread, version=%s", latest)
        _pending_signaller = None
        skipped = get_skipped_version()
        if not ignore_skip and skipped and skipped == latest:
            log.debug("_on_update — version %r is skipped, suppressing dialog", latest)
            if on_done:
                on_done()
            return
        prompt_update(latest, on_done=on_done)

    def _on_none():
        global _pending_signaller
        log.debug("_on_no_update — main thread")
        _pending_signaller = None
        if ignore_skip:
            # Manual check: tell the user they're already up to date.
            _show_up_to_date_toast()
        if on_done:
            on_done()

    signaller.update_available.connect(_on_update, Qt.QueuedConnection)
    signaller.no_update.connect(_on_none,           Qt.QueuedConnection)

    def _worker():
        log.debug("Fetching latest release from: %s", get_releases_api_url())
        try:
            latest, _zip_url = fetch_latest_release()
            log.debug("Remote: %s  zip: %s", latest, _zip_url)
            if is_newer_version(latest, CURRENT_VERSION):
                log.debug("UPDATE AVAILABLE: %s → %s", CURRENT_VERSION, latest)
                log.debug("========== UPDATE CHECK COMPLETE ==========")
                signaller.update_available.emit(latest)
                return

        except Exception as e:
            log.debug("Update check failed: %s", e)

        log.debug("========== UPDATE CHECK COMPLETE ==========")
        signaller.no_update.emit()

    threading.Thread(target=_worker, daemon=True).start()


def _show_up_to_date_toast() -> None:
    """Show a brief toast when a manual check finds no update."""
    try:
        for top in QApplication.topLevelWidgets():
            if hasattr(top, "show_notification"):
                top.show_notification(
                    t("update.up_to_date",
                      version=CURRENT_VERSION,
                      default=f"You're up to date!  (v{CURRENT_VERSION})"),
                    type="success",
                    duration=3500,
                )
                return
    except Exception as e:
        log.debug("_show_up_to_date_toast: %s", e)
