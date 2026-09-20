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
    QStackedWidget, QApplication, QSizePolicy,
)

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return kw.get('default', key)

log = logging.getLogger(__name__)

try:
    from gui.theme import COLORS, font, fade_in
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    COLORS = {
        'app_bg': '#0d0d0d', 'sidebar_bg': '#141414', 'topbar_bg': '#111111',
        'frame_bg': '#1a1a1a', 'card_bg': '#1f1f1f', 'card_hover': '#2a2a2a',
        'accent': '#ff6a00', 'accent_hover': '#ff8533', 'accent_dim': '#cc5500',
        'accent_text': '#ffffff',
        'text': '#f2f2f2', 'text_secondary': '#a8a8a8', 'text_muted': '#6e6e6e',
        'border': '#2e2e2e', 'border_focus': '#ff6a00',
        'success': '#4ade80', 'error': '#ff4d4f', 'error_hover': '#d93a3c',
        'warning': '#f59e0b', 'warning_hover': '#d97706',
    }
    def font(size=13, weight='normal'):
        f = QFont('Segoe UI', size)
        f.setBold(weight == 'bold')
        return f
    def fade_in(w, duration=200):
        pass


def get_github_repo():
    result = ("https://github.com/BeamSkin-Studio/BeamSkin-Studio-Beta"
              if sys.platform == "win32"
              else "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Linux-Beta")
    log.debug("get_github_repo: platform=%s -> %s", sys.platform, result)
    return result

def get_releases_api_url():
    repo = "BeamSkin-Studio-Beta" if sys.platform == "win32" else "BeamSkin-Studio-Linux-Beta"
    url = f"https://api.github.com/repos/BeamSkin-Studio/{repo}/releases/latest"
    log.debug("get_releases_api_url: repo=%s -> %s", repo, url)
    return url

_latest_release_zip_url: str = ""
_latest_release_exe_url: str = ""

def get_zip_url():
    if _latest_release_zip_url:
        log.debug("get_zip_url: returning cached %s", _latest_release_zip_url)
        return _latest_release_zip_url
    repo = "BeamSkin-Studio-Beta" if sys.platform == "win32" else "BeamSkin-Studio-Linux-Beta"
    url = f"https://github.com/BeamSkin-Studio/{repo}/releases/latest/download/BeamSkin-Studio.zip"
    log.debug("get_zip_url: no cached URL, falling back to %s", url)
    return url

def get_exe_url():
    log.debug("get_exe_url: returning cached %r", _latest_release_exe_url)
    return _latest_release_exe_url

def fetch_latest_release():
    global _latest_release_zip_url, _latest_release_exe_url
    log.debug("fetch_latest_release: GET %s", get_releases_api_url())
    resp = requests.get(
        get_releases_api_url(),
        timeout=10,
        headers={"Accept": "application/vnd.github+json"},
    )
    log.debug("fetch_latest_release: status_code=%s", resp.status_code)
    resp.raise_for_status()
    data = resp.json()
    log.debug("fetch_latest_release: tag_name=%r asset_count=%s",
              data.get("tag_name"), len(data.get("assets", [])))

    tag = re.sub(r"^[Vv]\.?", "", data["tag_name"])
    version = _format_version_string(tag)

    zip_url = data.get("zipball_url", "")
    exe_url = ""
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".zip") and not zip_url_is_asset(zip_url):
            zip_url = asset["browser_download_url"]
            log.debug("fetch_latest_release: matched .zip asset %r", name)
        elif name.endswith(".exe"):
            exe_url = asset["browser_download_url"]
            log.debug("fetch_latest_release: matched .exe asset %r", name)

    _latest_release_zip_url = zip_url
    _latest_release_exe_url = exe_url
    log.debug("fetch_latest_release: version=%s  zip_url=%s  exe_url=%s",
              version, zip_url, exe_url)
    return version, zip_url

def zip_url_is_asset(url: str) -> bool:
    return "/releases/download/" in url or "/releases/latest/download/" in url


def get_base_path():
    frozen = getattr(sys, "frozen", False)
    if frozen:
        result = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    else:
        result = os.path.dirname(os.path.abspath(__file__))
    log.debug("get_base_path: frozen=%s -> %s", frozen, result)
    return result

def get_app_dir():
    frozen = getattr(sys, "frozen", False)
    if frozen:
        result = os.path.dirname(sys.executable)
    else:
        result = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log.debug("get_app_dir: frozen=%s -> %s", frozen, result)
    return result

def get_downloads_folder():
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            ) as key:
                result = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
                log.debug("get_downloads_folder: from registry -> %s", result)
                return result
        except Exception as e:
            log.debug("get_downloads_folder: registry lookup failed: %s", e)
    result = os.path.join(os.path.expanduser("~"), "Downloads")
    log.debug("get_downloads_folder: falling back to %s", result)
    return result


def is_frozen_build() -> bool:
    return bool(getattr(sys, "frozen", False))


def _format_version_string(raw: str) -> str:
    content = raw.strip().replace("Version:", "").strip()
    parts = content.split(".")
    if len(parts) >= 3:
        major, minor, patch = parts[0], parts[1], parts[2]
        if len(parts) >= 4:
            try:
                build  = int(parts[3])
                status = "Beta" if build == 0 else f"Build {build}"
            except ValueError as _exc:
                print(f"[WARNING] _format_version_string: {type(_exc).__name__}: {_exc}")
                status = parts[3].capitalize()
        else:
            status = "Stable"
        result = f"{major}.{minor}.{patch}.{status}"
        log.debug("_format_version_string: raw=%r -> %s", raw, result)
        return result
    log.debug("_format_version_string: raw=%r has <3 parts, returning content=%r", raw, content)
    return content


def read_version():
    log.debug("read_version called")
    for p in [os.path.join(get_base_path(), "version.txt"),
              os.path.join(os.getcwd(), "version.txt"), "version.txt"]:
        log.debug("read_version: checking %s", p)
        if not os.path.exists(p):
            log.debug("read_version: %s does not exist", p)
            continue
        try:
            with open(p, "r") as f:
                result = _format_version_string(f.read())
            log.debug("read_version: read %s -> %s", p, result)
            return result
        except Exception as e:
            log.debug("Failed to read %s: %s", p, e)
    log.debug("read_version: no version.txt found, returning 0.0.0.Unknown")
    return "0.0.0.Unknown"

def parse_version(s: str):
    original = s
    s = s.lower().strip().replace("version:", "").replace("v", "").strip()
    m = re.match(r"(\d+)\.(\d+)\.(\d+)\.?(.*)", s)
    if m:
        major, minor, patch, suffix = m.groups()
        prio = {"stable": 0, "": 0, "rc": 1, "beta": 2, "alpha": 3}.get(
            (suffix or "stable").lower().strip(), 2)
        result = (int(major), int(minor), int(patch), prio)
        log.debug("parse_version: %r -> %s", original, result)
        return result
    log.debug("parse_version: %r did not match pattern, returning (0,0,0,999)", original)
    return (0, 0, 0, 999)

def is_newer_version(remote: str, current: str) -> bool:
    try:
        r, c = parse_version(remote), parse_version(current)
        log.debug("Parsed current: %s -> %s", current, c)
        log.debug("Parsed remote:  %s -> %s", remote, r)
        result = r[:3] > c[:3] if r[:3] != c[:3] else r[3] < c[3]
        log.debug("is_newer_version: remote=%s current=%s -> %s", remote, current, result)
        return result
    except Exception as e:
        log.debug("Version comparison error: %s", e)
        return remote != current

CURRENT_VERSION = read_version()

_app_instance      = None
_colors            = None
_pending_signaller = None

def set_app_instance(app, colors):
    global _app_instance, _colors
    _app_instance = app
    _colors       = colors
    log.debug("set_app_instance called")


def get_skipped_version() -> str:
    try:
        import core.settings as _s
        result = _s.app_settings.get("skipped_update_version", "")
        log.debug("get_skipped_version: %r", result)
        return result
    except Exception as e:
        log.debug("get_skipped_version: could not read setting: %s", e)
        return ""


def set_skipped_version(version: str) -> None:
    log.debug("set_skipped_version: %r", version)
    try:
        import core.settings as _s
        _s.app_settings["skipped_update_version"] = version
        _s.save_settings()
    except Exception as e:
        log.warning("set_skipped_version: could not persist: %s", e)


class _DownloadWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(str)
    failed   = Signal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self._url  = url
        self._dest = dest

    def run(self):
        log.debug("_DownloadWorker.run: url=%s dest=%s", self._url, self._dest)
        try:
            r = requests.get(self._url, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            log.debug("_DownloadWorker.run: content-length=%s", total)
            done  = 0
            with open(self._dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if self.isInterruptionRequested():
                        log.debug("_DownloadWorker.run: interruption requested at done=%s", done)
                        return
                    f.write(chunk)
                    done += len(chunk)
                    self.progress.emit(done, total)
            log.debug("_DownloadWorker.run: complete, %s bytes written to %s", done, self._dest)
            self.finished.emit(self._dest)
        except Exception as e:
            log.debug("_DownloadWorker.run: failed: %s", e)
            self.failed.emit(str(e))


class _ExeSwapWorker(QThread):
    status   = Signal(str)
    finished = Signal(str)
    failed   = Signal(str)

    def __init__(self, new_exe_path: str):
        super().__init__()
        self._new_exe_path = new_exe_path

    def run(self):
        try:
            current_exe = sys.executable
            app_dir     = os.path.dirname(current_exe)
            log.debug("_ExeSwapWorker.run: current_exe=%s new_exe=%s",
                      current_exe, self._new_exe_path)

            self.status.emit("Preparing update\u2026")

            if not os.path.exists(self._new_exe_path):
                self.failed.emit(f"Downloaded file not found: {self._new_exe_path}")
                return

            try:
                new_size = os.path.getsize(self._new_exe_path)
            except OSError as e:
                self.failed.emit(f"Could not read downloaded file: {e}")
                return
            if new_size < 1_000_000:
                log.debug("_ExeSwapWorker.run: downloaded exe suspiciously small (%s bytes)",
                          new_size)
                self.failed.emit(
                    f"Downloaded update looks incomplete ({new_size} bytes). "
                    "Please try downloading again."
                )
                return
            if sys.platform == "win32":
                try:
                    with open(self._new_exe_path, "rb") as f:
                        header = f.read(2)
                    if header != b"MZ":
                        log.debug("_ExeSwapWorker.run: downloaded file missing MZ header")
                        self.failed.emit(
                            "Downloaded update does not look like a valid executable. "
                            "Please try downloading again."
                        )
                        return
                except OSError as e:
                    self.failed.emit(f"Could not read downloaded file: {e}")
                    return

            staged_path = os.path.join(app_dir, os.path.basename(current_exe) + ".new")
            log.debug("_ExeSwapWorker.run: staging new exe at %s", staged_path)
            shutil.copy2(self._new_exe_path, staged_path)

            try:
                os.remove(self._new_exe_path)
                log.debug("_ExeSwapWorker.run: removed downloaded exe %s", self._new_exe_path)
            except Exception as e:
                log.debug("_ExeSwapWorker.run: could not remove downloaded exe %s: %s",
                          self._new_exe_path, e)

            if sys.platform == "win32":
                script_path = os.path.join(app_dir, "_update_swap.bat")
                log_path    = os.path.join(app_dir, "_update_swap.log")
                script = (
                    "@echo off\r\n"
                    "setlocal\r\n"
                    f'echo [%date% %time%] swap started > "{log_path}"\r\n'
                    f'echo current_exe={current_exe} >> "{log_path}"\r\n'
                    f'echo staged_path={staged_path} >> "{log_path}"\r\n'
                    ":wait\r\n"
                    f'tasklist /FI "IMAGENAME eq {os.path.basename(current_exe)}" '
                    f'2>NUL | find /I "{os.path.basename(current_exe)}" >NUL\r\n'
                    "if not errorlevel 1 (\r\n"
                    f'  echo [%date% %time%] still running, waiting >> "{log_path}"\r\n'
                    "  timeout /t 1 /nobreak >NUL\r\n"
                    "  goto wait\r\n"
                    ")\r\n"
                    f'echo [%date% %time%] process no longer listed >> "{log_path}"\r\n'
                    "REM Windows can report the process gone from tasklist a\r\n"
                    "REM moment before it actually releases the exe's file\r\n"
                    "REM lock/mapping. Give it a real pause -- not just 1s --\r\n"
                    "REM before the first move attempt.\r\n"
                    "timeout /t 3 /nobreak >NUL\r\n"
                    "set RETRIES=20\r\n"
                    ":retry_move\r\n"
                    f'del "{staged_path}.movedone" >NUL 2>&1\r\n'
                    f'(move /Y "{staged_path}" "{current_exe}" >> "{log_path}" 2>&1) '
                    f'&& (echo done > "{staged_path}.movedone")\r\n'
                    f'if not exist "{staged_path}.movedone" (\r\n'
                    "  set /a RETRIES-=1\r\n"
                    f'  echo [%date% %time%] move failed, retries left: %RETRIES% >> "{log_path}"\r\n'
                    "  if %RETRIES% gtr 0 (\r\n"
                    "    timeout /t 1 /nobreak >NUL\r\n"
                    "    goto retry_move\r\n"
                    "  )\r\n"
                    f'  echo [%date% %time%] GAVE UP -- move never succeeded >> "{log_path}"\r\n'
                    ") else (\r\n"
                    f'  echo [%date% %time%] move succeeded >> "{log_path}"\r\n'
                    f'  del "{staged_path}.movedone" >NUL 2>&1\r\n'
                    ")\r\n"
                    "del \"%~f0\"\r\n"
                    "exit\r\n"
                )
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script)
            else:
                script_path = os.path.join(app_dir, "_update_swap.sh")
                script = (
                    "#!/bin/sh\n"
                    f'while pgrep -f "{os.path.basename(current_exe)}" >/dev/null; do sleep 1; done\n'
                    "sleep 1\n"
                    f'mv -f "{staged_path}" "{current_exe}"\n'
                    f'chmod +x "{current_exe}"\n'
                    f'rm -- "$0"\n'
                )
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script)
                os.chmod(script_path, 0o755)

            log.debug("_ExeSwapWorker.run: wrote swap script %s", script_path)
            self.finished.emit(script_path)
        except Exception as e:
            log.debug("_ExeSwapWorker.run: failed: %s", e)
            self.failed.emit(str(e))


class _ExtractWorker(QThread):
    status   = Signal(str)
    finished = Signal(int)
    failed   = Signal(str)

    PRESERVE: set = {
        os.path.join("data",     "app_settings.json"),
        os.path.join("vehicles", "added_vehicles.json"),
    }

    NEVER_OVERWRITE_PREFIXES: frozenset = frozenset({
        "data",
    })

    NEVER_DELETE_PREFIXES: frozenset = frozenset({
        "data",
        "vehicles",
        os.path.join("gui", "images", "vehicles"),
    })

    def __init__(self, zip_path: str, new_version: str):
        super().__init__()
        self._zip     = zip_path
        self._version = new_version


    @staticmethod
    def _live_preserve_paths() -> set:
        try:
            from core.settings import get_settings_path, get_added_vehicles_path
            result = {
                os.path.abspath(get_settings_path()),
                os.path.abspath(get_added_vehicles_path()),
            }
            log.debug("_ExtractWorker._live_preserve_paths: %s", result)
            return result
        except ImportError as e:
            log.debug("_ExtractWorker._live_preserve_paths: core.settings unavailable: %s", e)
            return set()

    @classmethod
    def _is_overwrite_protected(cls, rel_norm: str) -> bool:
        parts = rel_norm.split(os.sep)
        for prefix in cls.NEVER_OVERWRITE_PREFIXES:
            prefix_parts = prefix.split(os.sep)
            if parts[: len(prefix_parts)] == prefix_parts:
                return True
        return False

    @classmethod
    def _is_deletion_protected(cls, rel_norm: str) -> bool:
        parts = rel_norm.split(os.sep)
        if "__pycache__" in parts or rel_norm.endswith(".pyc"):
            return True
        for prefix in cls.NEVER_DELETE_PREFIXES:
            prefix_parts = prefix.split(os.sep)
            if parts[: len(prefix_parts)] == prefix_parts:
                return True
        return False


    def run(self):
        log.debug("_ExtractWorker.run: zip=%s version=%s", self._zip, self._version)
        try:
            app_dir   = get_app_dir()
            dl_folder = os.path.dirname(self._zip)
            temp_dir  = os.path.join(dl_folder, f"BeamSkin-Studio-temp-{self._version}")
            log.debug("_ExtractWorker.run: app_dir=%s temp_dir=%s", app_dir, temp_dir)

            self.status.emit("Extracting archive\u2026")
            with zipfile.ZipFile(self._zip, "r") as z:
                z.extractall(temp_dir)
            log.debug("_ExtractWorker.run: extracted %s -> %s", self._zip, temp_dir)

            contents = os.listdir(temp_dir)
            source   = (os.path.join(temp_dir, contents[0])
                        if len(contents) == 1 and
                           os.path.isdir(os.path.join(temp_dir, contents[0]))
                        else temp_dir)
            log.debug("_ExtractWorker.run: temp_dir contents=%s, source=%s", contents, source)

            incoming: set = set()
            for root, _, files in os.walk(source):
                for fname in files:
                    rel = os.path.relpath(os.path.join(root, fname), source)
                    incoming.add(rel.replace("/", os.sep).replace("\\", os.sep))
            log.debug("_ExtractWorker.run: incoming file count=%s", len(incoming))

            backups: dict = {}
            for rel in self.PRESERVE:
                full = os.path.join(app_dir, rel)
                if os.path.exists(full):
                    try:
                        with open(full, "r", encoding="utf-8") as f:
                            backups[rel] = f.read()
                        log.debug("_ExtractWorker.run: backed up Tier-1 file %s", rel)
                    except Exception as e:
                        log.debug("_ExtractWorker.run: could not back up Tier-1 file %s: %s", rel, e)

            live_backups: dict = {}
            for full in self._live_preserve_paths():
                if os.path.exists(full):
                    try:
                        with open(full, "r", encoding="utf-8") as f:
                            live_backups[full] = f.read()
                        log.debug("_ExtractWorker.run: backed up live data file %s", full)
                    except Exception as e:
                        log.warning("Could not back up live data file %s: %s", full, e)

            log.debug("_ExtractWorker.run: backups=%s live_backups=%s",
                       len(backups), len(live_backups))

            self.status.emit("Copying files\u2026")
            updated = 0
            skipped_preserved = 0
            skipped_protected = 0
            copy_errors = 0
            preserve_norm = {p.replace("/", os.sep).replace("\\", os.sep)
                             for p in self.PRESERVE}
            for root, _, files in os.walk(source):
                if self.isInterruptionRequested():
                    log.debug("_ExtractWorker.run: interruption requested during copy step")
                    return
                rel_dir    = os.path.relpath(root, source)
                target_dir = app_dir if rel_dir == "." else os.path.join(app_dir, rel_dir)
                os.makedirs(target_dir, exist_ok=True)
                for fname in files:
                    rel_file = fname if rel_dir == "." else os.path.join(rel_dir, fname)
                    rel_norm = rel_file.replace("/", os.sep).replace("\\", os.sep)
                    if rel_norm in preserve_norm:
                        skipped_preserved += 1
                        continue
                    if self._is_overwrite_protected(rel_norm):
                        skipped_protected += 1
                        continue
                    try:
                        shutil.copy2(os.path.join(root, fname),
                                     os.path.join(target_dir, fname))
                        updated += 1
                    except Exception as e:
                        copy_errors += 1
                        log.debug("_ExtractWorker.run: could not copy %s: %s", rel_norm, e)
            log.debug("_ExtractWorker.run: copy step done — updated=%s skipped_preserved=%s "
                       "skipped_protected=%s copy_errors=%s",
                       updated, skipped_preserved, skipped_protected, copy_errors)

            self.status.emit("Removing obsolete files\u2026")
            live_preserve_abs = {os.path.abspath(p) for p in live_backups.keys()}
            live_preserve_abs |= {os.path.abspath(p) for p in self._live_preserve_paths()}
            removed_count = 0
            for root, dirs, files in os.walk(app_dir, topdown=False):
                if self.isInterruptionRequested():
                    log.debug("_ExtractWorker.run: interruption requested during delete step")
                    return
                for fname in files:
                    full     = os.path.join(root, fname)
                    rel_norm = os.path.relpath(full, app_dir)
                    if rel_norm in incoming:
                        continue
                    if rel_norm in preserve_norm:
                        continue
                    if os.path.abspath(full) in live_preserve_abs:
                        continue
                    if self._is_deletion_protected(rel_norm):
                        continue
                    try:
                        os.remove(full)
                        removed_count += 1
                        log.debug("Removed obsolete file: %s", rel_norm)
                    except Exception as e:
                        log.warning("Could not remove %s: %s", rel_norm, e)
                for dname in dirs:
                    dpath    = os.path.join(root, dname)
                    rel_norm = os.path.relpath(dpath, app_dir)
                    if self._is_deletion_protected(os.path.join(rel_norm, ".keep")):
                        continue
                    try:
                        if not os.listdir(dpath):
                            os.rmdir(dpath)
                            log.debug("_ExtractWorker.run: removed empty dir %s", rel_norm)
                    except Exception as e:
                        log.debug("_ExtractWorker.run: could not rmdir %s: %s", rel_norm, e)

            log.debug("_ExtractWorker.run: delete step done — removed_count=%s", removed_count)

            restored_tier1 = 0
            for rel, content in backups.items():
                full = os.path.join(app_dir, rel)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                try:
                    with open(full, "w", encoding="utf-8") as f:
                        f.write(content)
                    restored_tier1 += 1
                except Exception as e:
                    log.debug("_ExtractWorker.run: could not restore Tier-1 file %s: %s", rel, e)
            log.debug("_ExtractWorker.run: restored_tier1=%s", restored_tier1)

            for full, content in live_backups.items():
                if not os.path.exists(full):
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    try:
                        with open(full, "w", encoding="utf-8") as f:
                            f.write(content)
                        log.debug("Restored live data file: %s", full)
                    except Exception as e:
                        log.warning("Could not restore live data file %s: %s", full, e)

            try:
                shutil.rmtree(temp_dir)
                log.debug("_ExtractWorker.run: removed temp_dir %s", temp_dir)
            except Exception as e:
                log.debug("_ExtractWorker.run: could not remove temp_dir %s: %s", temp_dir, e)
            try:
                os.remove(self._zip)
                log.debug("_ExtractWorker.run: removed downloaded zip %s", self._zip)
            except Exception as e:
                log.debug("_ExtractWorker.run: could not remove zip %s: %s", self._zip, e)

            log.debug("_ExtractWorker.run: complete, emitting finished(updated=%s)", updated)
            self.finished.emit(updated)

        except Exception as e:
            import traceback; traceback.print_exc()
            log.debug("Extract worker error: %s", e)
            self.failed.emit(str(e))


_PAGE_MAIN        = 0
_PAGE_DOWNLOADING = 1
_PAGE_DOWNLOADED  = 2
_PAGE_EXTRACTING  = 3
_PAGE_COMPLETE    = 4
_PAGE_DL_ERROR    = 5


def _c(key: str, fallback: str = "") -> str:
    return COLORS.get(key) or fallback

def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return hex_color
    return f"rgba({r},{g},{b},{int(alpha * 255)})"


def _canvas() -> str:
    return _c("sidebar_bg", _c("app_bg", _c("frame_bg", "#181825")))


class _Panel(QFrame):

    def __init__(self, parent: QWidget = None, tone: str = "card"):
        super().__init__(parent)
        self.setObjectName("updPanel")
        bg     = _c("card_bg") if tone == "card" else _c("frame_bg")
        border = _c("border")
        if tone == "accent":
            bg, border = _c("card_bg"), _c("accent")
        self.setStyleSheet(f"""
            QFrame#updPanel {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
        """)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(8, 8, 8, 8)
        self.lay.setSpacing(6)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)


class _SectionHeader(QFrame):

    def __init__(self, text: str, right: QWidget = None):
        super().__init__()
        self.setFixedHeight(30)
        self.setStyleSheet("background:transparent;border:none;")
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(6)

        marker = QFrame()
        marker.setFixedSize(3, 14)
        marker.setStyleSheet(
            f"background:{_c('accent')};border:none;border-radius:1px;"
        )
        row.addWidget(marker)

        self.label = QLabel(text.upper())
        self.label.setFont(font(10, "bold"))
        self.label.setStyleSheet(
            f"color:{_c('text')};background:transparent;border:none;"
        )
        row.addWidget(self.label)
        row.addStretch()
        if right is not None:
            row.addWidget(right)

    def set_text(self, text: str):
        self.label.setText(text.upper())


class _Chip(QLabel):

    def __init__(self, text: str, kind: str = "muted"):
        super().__init__(text)
        self.setFont(font(9, "bold"))
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(20)
        self.set_kind(kind)

    def set_kind(self, kind: str):
        if kind == "accent":
            fg, bg, bd = _c("accent_text", "#ffffff"), _c("accent"), _c("accent_hover", _c("accent"))
        elif kind == "success":
            s = _c("success", "#4ade80")
            fg, bg, bd = s, _rgba(s, 0.13), _rgba(s, 0.35)
        elif kind == "error":
            e = _c("error", "#e74c3c")
            fg, bg, bd = e, _rgba(e, 0.13), _rgba(e, 0.35)
        else:
            fg, bg, bd = _c("text_secondary"), _c("frame_bg"), _c("border")
        self.setStyleSheet(f"""
            QLabel {{
                color:{fg}; background:{bg};
                border:1px solid {bd}; border-radius:6px;
                padding:0 8px;
            }}
        """)


class _StepRow(QFrame):

    PENDING, ACTIVE, DONE, FAILED = range(4)

    def __init__(self, title: str):
        super().__init__()
        self.setFixedHeight(40)
        self._state = self.PENDING
        self.setObjectName("stepRow")

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(10)

        self._dot = QLabel()
        self._dot.setFixedSize(18, 18)
        self._dot.setAlignment(Qt.AlignCenter)
        row.addWidget(self._dot)

        self._title = QLabel(title)
        self._title.setFont(font(11, "bold"))
        row.addWidget(self._title, 1)

        self._detail = QLabel("")
        self._detail.setFont(font(10))
        row.addWidget(self._detail)

        self.set_state(self.PENDING)

    def set_detail(self, text: str):
        self._detail.setText(text)

    def set_state(self, state: int):
        self._state = state
        accent  = _c("accent")
        success = _c("success", "#a6e3a1")
        error   = _c("error", "#e74c3c")
        muted   = _c("text_muted", _c("text_secondary"))

        if state == self.ACTIVE:
            border, bg = accent, _c("card_hover", _c("frame_bg"))
            glyph, gfg, gbg = "●", _c("accent_text", "#ffffff"), accent
            tfg = _c("text")
        elif state == self.DONE:
            border, bg = _c("border"), _c("frame_bg")
            glyph, gfg, gbg = "✓", "#0b0b0b", success
            tfg = _c("text")
        elif state == self.FAILED:
            border, bg = error, _c("frame_bg")
            glyph, gfg, gbg = "✕", "white", error
            tfg = _c("text")
        else:
            border, bg = _c("border"), _c("frame_bg")
            glyph, gfg, gbg = "", muted, _c("card_bg")
            tfg = _c("text_secondary")

        self.setStyleSheet(f"""
            QFrame#stepRow {{
                background:{bg}; border:1px solid {border}; border-radius:8px;
            }}
        """)
        self._dot.setText(glyph)
        self._dot.setFont(font(9, "bold"))
        self._dot.setStyleSheet(f"""
            QLabel {{
                background:{gbg}; color:{gfg};
                border:1px solid {border if state == self.PENDING else gbg};
                border-radius:9px;
            }}
        """)
        self._title.setStyleSheet(f"color:{tfg};background:transparent;border:none;")
        self._detail.setStyleSheet(
            f"color:{_c('text_secondary')};background:transparent;border:none;"
        )


class _AutoStack(QStackedWidget):

    def sizeHint(self):
        w = self.currentWidget()
        return w.sizeHint() if w is not None else super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        return w.minimumSizeHint() if w is not None else super().minimumSizeHint()


class _UpdateDialog(QDialog):
    def __init__(self, parent: QWidget, new_version: str, on_done=None):
        super().__init__(parent)
        self._new_version = new_version
        self._on_done     = on_done
        self._done_fired  = False
        self._zip_path    = None
        self._dl_worker   = None
        self._ex_worker   = None
        self._swap_worker      = None
        self._swap_script_path = None
        self._drag_pos    = None

        self.setWindowTitle(t("update.title", default="Update Available"))
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(460)
        self._build()
        self._refit()


    def _fire_done(self):
        log.debug("_fire_done: done_fired=%s", self._done_fired)
        if not self._done_fired:
            self._done_fired = True
            if self._on_done:
                QTimer.singleShot(0, self._on_done)

    def closeEvent(self, event):
        log.debug("closeEvent: dl_worker_running=%s ex_worker_running=%s",
                   bool(self._dl_worker and self._dl_worker.isRunning()),
                   bool(self._ex_worker and self._ex_worker.isRunning()))
        for worker in (self._dl_worker, self._ex_worker):
            if worker and worker.isRunning():
                worker.requestInterruption()
        self._fire_done()
        super().closeEvent(event)

    def reject(self):
        log.debug("reject: called")
        self._fire_done()
        super().reject()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 46:
            self._drag_pos = (event.globalPosition().toPoint()
                              - self.frameGeometry().topLeft())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        shell = QFrame(self)
        shell.setObjectName("updShell")
        shell.setStyleSheet(f"""
            QFrame#updShell {{
                background: {_canvas()};
                border: 1px solid {_c('border')};
                border-radius: 12px;
            }}
        """)
        outer.addWidget(shell)

        root = QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._titlebar = self._build_titlebar()
        root.addWidget(self._titlebar)

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        self._body_w = body
        self._shell  = shell
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(14, 14, 14, 14)
        body_lay.setSpacing(8)

        self._stack = _AutoStack()
        self._stack.setStyleSheet("background:transparent;")
        self._stack.addWidget(self._page_main())
        self._stack.addWidget(self._page_downloading())
        self._stack.addWidget(self._page_downloaded())
        self._stack.addWidget(self._page_extracting())
        self._stack.addWidget(self._page_complete())
        self._stack.addWidget(self._page_dl_error())
        self._stack.currentChanged.connect(self._refit)
        body_lay.addWidget(self._stack)
        body_lay.addStretch(1)
        root.addWidget(body)

        fade_in(self, duration=200)

    def _refit(self, _idx=None):
        page = self._stack.currentWidget()
        if page is None:
            return
        lay = page.layout()

        body_m  = self._body_w.layout().contentsMargins()
        shell_m = self._shell.layout().contentsMargins()
        content_w = self.width() - 2 - body_m.left() - body_m.right()

        self._stack.setMinimumHeight(0)
        self._stack.setMaximumHeight(16777215)
        page.setFixedWidth(content_w)
        lay.invalidate()
        lay.activate()

        if lay.hasHeightForWidth():
            page_h = lay.totalHeightForWidth(content_w)
        else:
            page_h = lay.sizeHint().height()
        page_h = max(page_h, lay.minimumSize().height())

        title_h = self._titlebar.height()
        total = (title_h + body_m.top() + page_h + body_m.bottom()
                 + shell_m.top() + shell_m.bottom() + 2)

        self._stack.setFixedHeight(page_h)
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self.setFixedHeight(total)

    def _build_titlebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("updTitle")
        bar.setFixedHeight(46)
        bar.setStyleSheet(f"""
            QFrame#updTitle {{
                background: {_c('topbar_bg', _c('frame_bg'))};
                border: none;
                border-bottom: 1px solid {_c('border')};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }}
        """)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(10)

        brand = QLabel("BEAMSKIN")
        brand.setFont(font(12, "bold"))
        brand.setStyleSheet(
            f"color:{_c('text')};background:transparent;border:none;"
        )
        studio = QLabel("STUDIO")
        studio.setFont(font(12, "bold"))
        studio.setStyleSheet(
            f"color:{_c('accent')};background:transparent;border:none;"
        )
        row.addWidget(brand)
        row.addWidget(studio)

        sep = QFrame()
        sep.setFixedSize(1, 16)
        sep.setStyleSheet(f"background:{_c('border')};border:none;")
        row.addWidget(sep)

        self._title_lbl = QLabel(t("update.title", default="Updater"))
        self._title_lbl.setFont(font(11))
        self._title_lbl.setStyleSheet(
            f"color:{_c('text_secondary')};background:transparent;border:none;"
        )
        row.addWidget(self._title_lbl)
        row.addStretch()

        self._close_x = QPushButton("✕")
        self._close_x.setFixedSize(28, 28)
        self._close_x.setCursor(Qt.PointingHandCursor)
        self._close_x.setFont(font(11, "bold"))
        self._close_x.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_c('text_secondary')};
                border: 1px solid transparent;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: {_c('error', '#e74c3c')};
                color: white;
            }}
        """)
        self._close_x.clicked.connect(self.reject)
        row.addWidget(self._close_x)
        return bar


    def _page(self):
        f = QWidget()
        f.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        f.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._page_layouts = getattr(self, "_page_layouts", [])
        self._page_layouts.append(lay)
        return f, lay

    def _divider(self):
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet(f"background:{_c('border')};border:none;")
        return d

    _sep = _divider

    def _btn(self, text, primary=True, danger=False, height=36):
        b = QPushButton(self._esc_amp(text))
        b.setFont(font(12, "bold"))
        b.setFixedHeight(height)
        b.setCursor(Qt.PointingHandCursor)
        if danger:
            fg, fgh = _c("error", "#e74c3c"), _c("error_hover", "#c0392b")
            tc, bd = "white", "none"
        elif primary:
            fg, fgh = _c("accent"), _c("accent_hover", _c("accent"))
            tc, bd = _c("accent_text", "#ffffff"), "none"
        else:
            fg, fgh = _c("card_bg"), _c("card_hover", _c("frame_bg"))
            tc, bd = _c("text"), f"1px solid {_c('border')}"
        hover_border = (f"border-color:{_c('accent')};" if not primary and not danger else "")
        b.setStyleSheet(f"""
            QPushButton {{
                background:{fg}; color:{tc};
                border:{bd}; border-radius:8px;
                padding:4px 14px;
            }}
            QPushButton:hover {{ background:{fgh}; {hover_border} }}
            QPushButton:disabled {{
                background:{_c('border')};
                color:{_c('text_muted', _c('text_secondary'))};
            }}
        """)
        return b

    @staticmethod
    def _esc_amp(text: str) -> str:
        import re as _re
        return _re.sub(r"(?<!&)&(?!&)", "&&", text or "")

    def _link_btn(self, text):
        b = QPushButton(self._esc_amp(text))
        b.setFont(font(10))
        b.setCursor(Qt.PointingHandCursor)
        b.setFlat(True)
        b.setStyleSheet(f"""
            QPushButton {{
                color:{_c('text_secondary')}; background:transparent;
                border:none; padding:4px 0;
            }}
            QPushButton:hover {{ color:{_c('text')}; text-decoration:underline; }}
        """)
        return b

    def _lbl(self, text="", size=11, bold=False, color=None, wrap=True, align=None):
        lbl = QLabel(text)
        lbl.setFont(font(size, "bold" if bold else "normal"))
        lbl.setWordWrap(wrap)
        lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        if align is not None:
            lbl.setAlignment(align)
        lbl.setStyleSheet(
            f"color:{color or _c('text_secondary')};background:transparent;border:none;"
        )
        return lbl

    def _progress_bar(self, indeterminate: bool = False, height: int = 8):
        bar = QProgressBar()
        if indeterminate:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(0)
        bar.setFixedHeight(height)
        bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {_c('frame_bg')};
                border: 1px solid {_c('border')};
                border-radius: {height // 2 + 1}px;
            }}
            QProgressBar::chunk {{
                background: {_c('accent')};
                border-radius: {height // 2}px;
            }}
        """)
        return bar

    def _stat_tile(self, caption: str, value: str = "—"):
        tile = QFrame()
        tile.setObjectName("statTile")
        tile.setFixedHeight(52)
        tile.setStyleSheet(f"""
            QFrame#statTile {{
                background:{_c('frame_bg')};
                border:1px solid {_c('border')};
                border-radius:8px;
            }}
        """)
        col = QVBoxLayout(tile)
        col.setContentsMargins(10, 6, 10, 6)
        col.setSpacing(1)
        cap = self._lbl(caption.upper(), 8, bold=True,
                        color=_c("text_muted", _c("text_secondary")), wrap=False)
        val = self._lbl(value, 12, bold=True, color=_c("text"), wrap=False)
        col.addWidget(cap)
        col.addWidget(val)
        return tile, val

    def _version_card(self, caption: str, version: str, accent: bool = False):
        card = QFrame()
        card.setObjectName("verCard")
        if accent:
            card.setStyleSheet(f"""
                QFrame#verCard {{
                    background:{_c('frame_bg')};
                    border:1px solid {_c('accent')};
                    border-radius:8px;
                }}
            """)
        else:
            card.setStyleSheet(f"""
                QFrame#verCard {{
                    background:{_c('frame_bg')};
                    border:1px solid {_c('border')};
                    border-radius:8px;
                }}
            """)
        col = QVBoxLayout(card)
        col.setContentsMargins(12, 8, 12, 8)
        col.setSpacing(2)
        cap = self._lbl(caption.upper(), 8, bold=True,
                        color=_c("accent") if accent else _c("text_muted", _c("text_secondary")),
                        wrap=False)
        ver = self._lbl(version, 13, bold=True,
                        color=_c("text"), wrap=False)
        col.addWidget(cap)
        col.addWidget(ver)
        return card

    def _status_banner(self, kind: str = "success"):
        badge = QLabel("✓" if kind == "success" else "!")
        badge.setFixedSize(52, 52)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFont(font(22, "bold"))
        col = _c("success", "#a6e3a1") if kind == "success" else _c("error", "#e74c3c")
        badge.setStyleSheet(f"""
            QLabel {{
                background:{_rgba(col, 0.13)}; color:{col};
                border:2px solid {_rgba(col, 0.4)}; border-radius:26px;
            }}
        """)
        return badge

    def _centered(self, w: QWidget):
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(w)
        row.addStretch()
        return row


    def _page_main(self):
        f, lay = self._page()

        vp = _Panel()
        self._main_chip = _Chip(t("update.chip_new", default="NEW"), "accent")
        vp.lay.addWidget(_SectionHeader(
            t("update.available", default="Update Available"), right=self._main_chip
        ))

        row = QHBoxLayout()
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(8)
        arrow = QLabel("→")
        arrow.setFont(font(16, "bold"))
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setFixedWidth(22)
        arrow.setStyleSheet(
            f"color:{_c('accent')};background:transparent;border:none;"
        )
        row.addWidget(self._version_card(
            t("update.current", default="Installed"), CURRENT_VERSION), 1)
        row.addWidget(arrow)
        row.addWidget(self._version_card(
            t("update.latest", default="Available"), self._new_version, accent=True), 1)
        vp.lay.addLayout(row)

        vp.lay.addSpacing(2)
        vp.lay.addWidget(self._lbl(
            t("update.subtitle",
              default="A new version of BeamSkin Studio is ready to install."),
            10, wrap=True,
        ))
        lay.addWidget(vp)

        lay.addWidget(self._divider())

        ip = _Panel()
        ip.lay.addWidget(_SectionHeader(t("update.whats_included", default="What's Included")))
        highlights = [
            ("⚡", t("update.feat1", default="Latest features & improvements")),
            ("🛡", t("update.feat2", default="Bug fixes & stability updates")),
            ("⚙", t("update.feat3", default="Your settings and custom vehicles are preserved")),
        ]
        for glyph, text in highlights:
            item = QFrame()
            item.setObjectName("featRow")
            item.setFixedHeight(36)
            item.setStyleSheet(f"""
                QFrame#featRow {{
                    background:{_c('frame_bg')};
                    border:1px solid {_c('border')};
                    border-radius:8px;
                }}
            """)
            r = QHBoxLayout(item)
            r.setContentsMargins(10, 0, 10, 0)
            r.setSpacing(10)
            g = QLabel(glyph)
            g.setFont(font(12))
            g.setFixedWidth(20)
            g.setStyleSheet("background:transparent;border:none;")
            r.addWidget(g)
            r.addWidget(self._lbl(text, 10, color=_c("text"), wrap=False), 1)
            ip.lay.addWidget(item)

        changelog_btn = self._btn(
            t("update.view_changelog", default="📋  What's New in this version"),
            primary=False, height=32,
        )
        changelog_btn.clicked.connect(self._on_view_changelog)
        ip.lay.addSpacing(2)
        ip.lay.addWidget(changelog_btn)
        lay.addWidget(ip)

        lay.addWidget(self._divider())

        brow = QHBoxLayout()
        brow.setSpacing(8)
        later_btn    = self._btn(t("update.maybe_later",     default="Maybe Later"),     primary=False)
        download_btn = self._btn(t("update.download_update", default="Download Update"), primary=True)
        later_btn.clicked.connect(self.reject)
        download_btn.clicked.connect(self._start_download)
        brow.addWidget(later_btn, 1)
        brow.addWidget(download_btn, 2)
        lay.addLayout(brow)

        skip_btn = self._link_btn(t("update.skip_version", default="Skip this version"))
        skip_btn.clicked.connect(self._skip_this_version)
        lay.addWidget(skip_btn, alignment=Qt.AlignCenter)
        return f

    def _page_downloading(self):
        f, lay = self._page()

        p = _Panel()
        self._dl_chip = _Chip(t("update.chip_downloading", default="DOWNLOADING"), "accent")
        p.lay.addWidget(_SectionHeader(
            t("update.downloading_title", default="Downloading"), right=self._dl_chip
        ))

        self._dl_file_lbl = self._lbl("", 10, color=_c("text_secondary"), wrap=False)
        p.lay.addWidget(self._dl_file_lbl)

        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        self._dl_bar = self._progress_bar()
        self._dl_pct_lbl = QLabel("0%")
        self._dl_pct_lbl.setFont(font(11, "bold"))
        self._dl_pct_lbl.setFixedWidth(40)
        self._dl_pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._dl_pct_lbl.setStyleSheet(
            f"color:{_c('accent')};background:transparent;border:none;"
        )
        prog_row.addWidget(self._dl_bar, 1)
        prog_row.addWidget(self._dl_pct_lbl)
        p.lay.addLayout(prog_row)
        lay.addWidget(p)

        tiles = QHBoxLayout()
        tiles.setSpacing(8)
        t_size, self._dl_size_lbl  = self._stat_tile(t("update.stat_downloaded", default="Downloaded"), "0.0 MB")
        t_total, self._dl_total_lbl = self._stat_tile(t("update.stat_total", default="Total"), "…")
        t_ver, _ = self._stat_tile(t("update.stat_version", default="Version"), self._new_version)
        tiles.addWidget(t_size, 1)
        tiles.addWidget(t_total, 1)
        tiles.addWidget(t_ver, 1)
        lay.addLayout(tiles)

        lay.addWidget(self._divider())

        cancel_btn = self._btn(t("update.cancel", default="Cancel"), primary=False)
        cancel_btn.clicked.connect(self.reject)
        lay.addWidget(cancel_btn)
        return f

    def _page_downloaded(self):
        f, lay = self._page()

        p = _Panel()
        p.lay.addWidget(_SectionHeader(
            t("update.download_complete", default="Download Complete"),
            right=_Chip(t("update.chip_ready", default="READY"), "success"),
        ))
        self._dl_path_lbl = self._lbl("", 9, color=_c("text_secondary"), wrap=True)
        path_box = QFrame()
        path_box.setObjectName("pathBox")
        path_box.setStyleSheet(f"""
            QFrame#pathBox {{
                background:{_c('frame_bg')};
                border:1px solid {_c('border')};
                border-radius:8px;
            }}
        """)
        pb = QVBoxLayout(path_box)
        pb.setContentsMargins(10, 8, 10, 8)
        pb.addWidget(self._dl_path_lbl)
        path_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        p.lay.addWidget(path_box)
        lay.addWidget(p)

        lay.addWidget(self._divider())

        if is_frozen_build():
            extract_label = t("update.install_button", default="Install")
        else:
            extract_label = t("update.update_button", default="Extract & Install")
        extract_btn = self._btn(extract_label, primary=True, height=40)
        open_btn    = self._btn(t("update.open_download_folder", default="Open Downloads Folder"), primary=False)
        close_btn   = self._btn(t("update.close", default="Close"), primary=False)
        extract_btn.clicked.connect(self._start_extract)
        open_btn.clicked.connect(self._open_downloads)
        close_btn.clicked.connect(self.reject)
        lay.addWidget(extract_btn)

        sub = QHBoxLayout()
        sub.setSpacing(8)
        sub.addWidget(open_btn, 2)
        sub.addWidget(close_btn, 1)
        lay.addLayout(sub)
        return f

    def _page_extracting(self):
        f, lay = self._page()

        p = _Panel()
        self._ex_chip = _Chip(t("update.chip_working", default="WORKING"), "accent")
        p.lay.addWidget(_SectionHeader(
            t("update.extracting", default="Installing Update"), right=self._ex_chip
        ))

        self._steps = [
            ("prepare", _StepRow(t("update.step_prepare", default="Preparing"))),
            ("extract", _StepRow(t("update.step_extract", default="Extracting archive"))),
            ("copy",    _StepRow(t("update.step_copy",    default="Copying files"))),
            ("clean",   _StepRow(t("update.step_clean",   default="Removing obsolete files"))),
        ]
        for _key, row in self._steps:
            p.lay.addWidget(row)
        lay.addWidget(p)

        self._ex_status_lbl = self._lbl(
            t("update.please_wait", default="Please wait…"),
            10, wrap=True,
        )
        self._ex_status_lbl.setAlignment(Qt.AlignCenter)
        self._ex_status_lbl.setFixedHeight(22)
        lay.addWidget(self._ex_status_lbl)
        lay.addWidget(self._progress_bar(indeterminate=True, height=6))
        lay.addSpacing(4)

        self._ex_status_lbl.setText = self._make_status_hook(self._ex_status_lbl)
        self._set_stage("prepare")
        return f

    def _make_status_hook(self, label: QLabel):
        original = label.setText

        def _hook(text: str):
            original(text)
            low = (text or "").lower()
            if "extract" in low:
                self._set_stage("extract")
            elif "copy" in low:
                self._set_stage("copy")
            elif "remov" in low or "obsolete" in low:
                self._set_stage("clean")
            elif "prepar" in low:
                self._set_stage("prepare")
        return _hook

    def _set_stage(self, stage: str):
        keys = [k for k, _ in self._steps]
        if stage not in keys:
            return
        idx = keys.index(stage)
        for i, (_k, row) in enumerate(self._steps):
            if i < idx:
                row.set_state(_StepRow.DONE)
            elif i == idx:
                row.set_state(_StepRow.ACTIVE)
            else:
                row.set_state(_StepRow.PENDING)

    def _finish_stages(self, ok: bool):
        if ok:
            for _k, row in self._steps:
                row.set_state(_StepRow.DONE)
            return
        failed_marked = False
        for _k, row in self._steps:
            if row._state == _StepRow.ACTIVE and not failed_marked:
                row.set_state(_StepRow.FAILED)
                failed_marked = True

    def _page_dl_error(self):
        f, lay = self._page()

        p = _Panel(tone="accent")
        p.setStyleSheet(f"""
            QFrame#updPanel {{
                background:{_c('card_bg')};
                border:1px solid {_c('error', '#e74c3c')};
                border-radius:10px;
            }}
        """)
        p.lay.addWidget(_SectionHeader(
            t("update.dl_failed_title", default="Download Failed"),
            right=_Chip(t("update.chip_error", default="ERROR"), "error"),
        ))

        box = QFrame()
        box.setObjectName("errBox")
        box.setStyleSheet(f"""
            QFrame#errBox {{
                background:{_c('frame_bg')};
                border:1px solid {_c('border')};
                border-radius:8px;
            }}
        """)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(10, 8, 10, 8)
        self._dl_error_lbl = self._lbl("", 10, wrap=True)
        bl.addWidget(self._dl_error_lbl)
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        p.lay.addWidget(box)
        lay.addWidget(p)

        lay.addWidget(self._divider())

        browser_btn = self._btn(
            t("update.download_manually", default="Download Manually in Browser"),
            primary=True, height=40,
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
        f, lay = self._page()

        p = _Panel()
        p.lay.addWidget(_SectionHeader(
            t("update.update_complete", default="Update Complete"),
            right=_Chip(t("update.chip_done", default="DONE"), "success"),
        ))
        p.lay.addSpacing(4)
        p.lay.addLayout(self._centered(self._status_banner("success")))
        p.lay.addSpacing(2)

        self._complete_lbl = self._lbl("", 10, wrap=True, align=Qt.AlignCenter)
        box = QFrame()
        box.setObjectName("doneBox")
        box.setStyleSheet(f"""
            QFrame#doneBox {{
                background:{_c('frame_bg')};
                border:1px solid {_c('border')};
                border-radius:8px;
            }}
        """)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.addWidget(self._complete_lbl)
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        p.lay.addWidget(box)
        lay.addWidget(p)

        lay.addWidget(self._divider())

        self._restart_btn = self._btn(t("update.restart_now", default="Restart Now"),
                                      primary=True, height=40)
        later_btn = self._btn(t("update.restart_later", default="Restart Later"), primary=False)
        self._restart_btn.clicked.connect(self._restart_app)
        later_btn.clicked.connect(self.reject)
        lay.addWidget(self._restart_btn)
        lay.addWidget(later_btn)
        return f


    def _on_view_changelog(self):
        try:
            from gui.components.changelog_dialog import show_update_changelog
            show_update_changelog(self, self._new_version)
        except Exception as e:
            log.debug("Could not open changelog: %s", e)
            import webbrowser
            webbrowser.open(get_github_repo())


    def _skip_this_version(self):
        log.debug("_skip_this_version: skipping %r", self._new_version)
        set_skipped_version(self._new_version)
        self.reject()

    def _start_download(self):
        if is_frozen_build():
            exe_url = get_exe_url()
            if not exe_url:
                log.debug("_start_download: frozen build but no .exe asset on release")
                self._on_dl_failed(
                    "This release has no downloadable .exe update. "
                    "Please update manually from GitHub."
                )
                return
            filename       = f"BeamSkin-Studio-{self._new_version}.exe"
            self._zip_path = os.path.join(get_downloads_folder(), filename)
            download_url   = exe_url
        else:
            filename       = f"BeamSkin-Studio-{self._new_version}.zip"
            self._zip_path = os.path.join(get_downloads_folder(), filename)
            download_url   = get_zip_url()

        log.debug("_start_download: filename=%s dest=%s url=%s",
                  filename, self._zip_path, download_url)

        self._dl_file_lbl.setText(filename)
        self._dl_bar.setValue(0)
        self._dl_pct_lbl.setText("0%")
        self._dl_size_lbl.setText("0.0 MB")
        self._dl_total_lbl.setText("…")
        self._stack.setCurrentIndex(_PAGE_DOWNLOADING)
        self._refit()

        self._dl_worker = _DownloadWorker(download_url, self._zip_path)
        self._dl_worker.progress.connect(self._on_dl_progress)
        self._dl_worker.finished.connect(self._on_dl_finished)
        self._dl_worker.failed.connect(self._on_dl_failed)
        self._dl_worker.start()

    def _on_dl_progress(self, done: int, total: int):
        self._dl_size_lbl.setText(f"{done/1_048_576:.1f} MB")
        if total > 0:
            pct = int(done * 100 / total)
            self._dl_bar.setValue(pct)
            self._dl_pct_lbl.setText(f"{pct}%")
            self._dl_total_lbl.setText(f"{total/1_048_576:.1f} MB")

    def _on_dl_finished(self, filepath: str):
        log.debug("_on_dl_finished: filepath=%s", filepath)
        self._zip_path = filepath
        self._dl_path_lbl.setText(f"Saved to:\n{filepath}")
        self._stack.setCurrentIndex(_PAGE_DOWNLOADED)
        self._refit()

    def _on_dl_failed(self, error: str):
        log.debug("Download failed: %s — showing error page", error)
        self._dl_error_lbl.setText(
            f"Error: {error}\n\nYou can download the update manually from GitHub."
        )
        self._stack.setCurrentIndex(_PAGE_DL_ERROR)
        self._refit()

    def _start_extract(self):
        if is_frozen_build():
            log.debug("_start_extract: frozen build, staging exe swap. new_exe=%s", self._zip_path)
            self._stack.setCurrentIndex(_PAGE_EXTRACTING)
            self._set_stage("prepare")
            self._refit()
            self._swap_worker = _ExeSwapWorker(self._zip_path)
            self._swap_worker.status.connect(self._ex_status_lbl.setText)
            self._swap_worker.finished.connect(self._on_swap_finished)
            self._swap_worker.failed.connect(self._on_ex_failed)
            self._swap_worker.start()
            return

        log.debug("_start_extract: zip_path=%s version=%s", self._zip_path, self._new_version)
        self._stack.setCurrentIndex(_PAGE_EXTRACTING)
        self._set_stage("prepare")
        self._refit()
        self._ex_worker = _ExtractWorker(self._zip_path, self._new_version)
        self._ex_worker.status.connect(self._ex_status_lbl.setText)
        self._ex_worker.finished.connect(self._on_ex_finished)
        self._ex_worker.failed.connect(self._on_ex_failed)
        self._ex_worker.start()

    def _on_swap_finished(self, script_path: str):
        log.debug("_on_swap_finished: script_path=%s", script_path)
        self._swap_script_path = script_path
        self._finish_stages(True)
        self._complete_lbl.setText(
            f"Downloaded version {self._new_version}.\n\n"
            "Your settings and custom vehicles have been preserved.\n\n"
            "Click Close & Install, then reopen BeamSkin Studio "
            "yourself once it closes."
        )
        self._restart_btn.setText(
            t("update.close_and_install", default="Close & Install")
        )
        self._stack.setCurrentIndex(_PAGE_COMPLETE)
        self._refit()

    def _on_ex_finished(self, files_updated: int):
        log.debug("_on_ex_finished: files_updated=%s", files_updated)
        self._finish_stages(True)
        self._complete_lbl.setText(
            f"Updated {files_updated} files to version {self._new_version}.\n\n"
            "Your settings and custom vehicles have been preserved.\n\n"
            "Please restart BeamSkin Studio to use the new version."
        )
        self._stack.setCurrentIndex(_PAGE_COMPLETE)
        self._refit()

    def _on_ex_failed(self, error: str):
        log.debug("_on_ex_failed: error=%s", error)
        self._finish_stages(False)
        self._dl_path_lbl.setText(
            f"Extract failed: {error}\nYou can extract manually from the downloads folder."
        )
        self._stack.setCurrentIndex(_PAGE_DOWNLOADED)
        self._refit()

    def _open_downloads(self):
        folder = os.path.dirname(self._zip_path) if self._zip_path else get_downloads_folder()
        log.debug("_open_downloads: folder=%s platform=%s", folder, sys.platform)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _restart_app(self):
        log.debug("_restart_app: called")
        self._fire_done()

        if is_frozen_build() and self._swap_script_path and os.path.exists(self._swap_script_path):
            log.debug("_restart_app: frozen build, launching swap script %s",
                      self._swap_script_path)
            self.accept()
            if sys.platform == "win32":
                subprocess.Popen(
                    ["cmd", "/c", self._swap_script_path],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                subprocess.Popen(["/bin/sh", self._swap_script_path])
            QApplication.instance().quit()
            return

        app_dir        = get_app_dir()
        batch_launcher = os.path.join(app_dir, "launchers-scripts", "quick_launcher.bat")
        py_launcher    = os.path.join(app_dir, "launchers-scripts", "quick_launcher.py")
        main_script    = os.path.join(app_dir, "main.py")
        self.accept()

        if is_frozen_build():
            log.debug("_restart_app: frozen build, no swap staged, relaunching %s",
                      sys.executable)
            clean_env = os.environ.copy()
            for var in ("PYTHONHOME", "PYTHONPATH", "_MEIPASS2"):
                clean_env.pop(var, None)
            subprocess.Popen([sys.executable], env=clean_env)
        elif sys.platform == "win32" and os.path.exists(batch_launcher):
            log.debug("_restart_app: using batch_launcher %s", batch_launcher)
            subprocess.Popen([batch_launcher], cwd=app_dir, shell=True)
        elif os.path.exists(py_launcher):
            log.debug("_restart_app: using py_launcher %s", py_launcher)
            subprocess.Popen(
                ["pythonw" if sys.platform == "win32" else sys.executable, py_launcher],
                cwd=app_dir,
            )
        else:
            log.debug("_restart_app: falling back to main_script %s", main_script)
            subprocess.Popen([sys.executable, main_script], cwd=app_dir)

        QApplication.instance().quit()


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
    _check_for_updates_impl(on_done=on_done, ignore_skip=False)


def check_for_updates_manual(on_done=None):
    _check_for_updates_impl(on_done=on_done, ignore_skip=True)


def _check_for_updates_impl(on_done=None, ignore_skip: bool = False):
    global _pending_signaller
    log.debug("check_for_updates called")
    log.debug("========== UPDATE CHECK STARTED ==========")
    log.debug("Platform: %s  Repo: %s", sys.platform, get_github_repo())
    log.debug("Current:  %s", CURRENT_VERSION)
    log.debug("ignore_skip=%s  skipped=%r", ignore_skip, get_skipped_version())

    signaller = _UpdateSignaller()
    _pending_signaller = signaller

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
    log.debug("_show_up_to_date_toast: called, version=%s", CURRENT_VERSION)
    try:
        for top in QApplication.topLevelWidgets():
            if hasattr(top, "show_notification"):
                log.debug("_show_up_to_date_toast: showing on widget %r", top)
                top.show_notification(
                    t("update.up_to_date",
                      version=CURRENT_VERSION,
                      default=f"You're up to date!  (v{CURRENT_VERSION})"),
                    type="success",
                    duration=3500,
                )
                return
        log.debug("_show_up_to_date_toast: no widget with show_notification found")
    except Exception as e:
        log.debug("_show_up_to_date_toast: %s", e)
