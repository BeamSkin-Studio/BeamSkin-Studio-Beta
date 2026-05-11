"""
updater.py — GitHub update checker with in-app download/extract/restart
(customtkinter edition)
"""
from __future__ import annotations

import os
import re
import sys
import shutil
import zipfile
import logging
import threading
import subprocess
import webbrowser

import requests
import customtkinter as ctk
from tkinter import messagebox
from gui.icon_helper import set_window_icon
from core.localization import t

try:
    import core.settings as _settings
except ImportError:
    _settings = None

log = logging.getLogger(__name__)


# ── path helpers ──────────────────────────────────────────────────────────── #

def get_github_repo() -> str:
    if sys.platform == "win32":
        return "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Beta"
    return "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Linux-Beta"

def get_releases_api_url() -> str:
    repo = "BeamSkin-Studio-Beta" if sys.platform == "win32" else "BeamSkin-Studio-Linux-Beta"
    return f"https://api.github.com/repos/BeamSkin-Studio/{repo}/releases/latest"

# Populated by fetch_latest_release(); used by get_zip_url().
_latest_release_zip_url: str = ""

def get_zip_url() -> str:
    """Return the zip download URL from the latest GitHub release.

    Falls back to the source-archive URL if fetch_latest_release() has not
    been called yet (e.g. in headless / fallback flows).
    """
    if _latest_release_zip_url:
        return _latest_release_zip_url
    repo = "BeamSkin-Studio-Beta" if sys.platform == "win32" else "BeamSkin-Studio-Linux-Beta"
    return f"https://github.com/BeamSkin-Studio/{repo}/releases/latest/download/BeamSkin-Studio.zip"

def fetch_latest_release() -> "tuple[str, str]":
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

def get_base_path() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(os.path.abspath(__file__))

def get_app_dir() -> str:
    """Return the application root directory (works frozen and dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # updater.py lives in core/ — parent of parent is app root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_downloads_folder() -> str:
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


def read_version() -> str:
    log.debug("read_version called")
    for p in [
        os.path.join(get_base_path(), "version.txt"),
        os.path.join(os.getcwd(), "version.txt"),
        "version.txt",
    ]:
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

_app_instance = None
_colors       = None

def set_app_instance(app, colors):
    global _app_instance, _colors
    _app_instance = app
    _colors       = colors
    log.debug("set_app_instance called")


# ── skip-version helpers ──────────────────────────────────────────────────── #

def get_skipped_version() -> str:
    """Return the version string the user chose to skip, or '' if none."""
    try:
        if _settings:
            return _settings.app_settings.get("skipped_update_version", "")
    except Exception:
        pass
    return ""


def set_skipped_version(version: str) -> None:
    """Persist the version the user wants to skip (pass '' to clear)."""
    log.debug("set_skipped_version: %r", version)
    try:
        if _settings:
            _settings.app_settings["skipped_update_version"] = version
            _settings.save_settings()
    except Exception as e:
        log.warning("set_skipped_version: could not persist: %s", e)


# ── file-protection rules (mirrors _ExtractWorker in PySide6 edition) ─────── #

# Tier 1 — individual files backed up before overwrite and restored afterwards.
_PRESERVE: set = {
    os.path.join("data",     "app_settings.json"),
    os.path.join("vehicles", "added_vehicles.json"),
}

# Tier 2 — directory prefixes NEVER written to during the copy step.
#   The files already on disk are left completely intact.
#   • data/ — every file here is user state; the zip must not touch any of it.
_NEVER_OVERWRITE_PREFIXES: frozenset = frozenset({
    "data",
})

# Tier 3 — directory prefixes where existing files are NEVER deleted during
#   cleanup, even if the new zip no longer ships them.
#   New files from the update ARE still copied in — only deletions are blocked.
#   • data/               — all user settings / state (also Tier 2)
#   • vehicles/           — vehicle template trees (may have user-created ones)
#   • gui/images/vehicles — bundled vehicle preview images
_NEVER_DELETE_PREFIXES: frozenset = frozenset({
    "data",
    "vehicles",
    os.path.join("gui", "images", "vehicles"),
})


def _is_overwrite_protected(rel_norm: str) -> bool:
    """Return True if this path must never be overwritten by the zip."""
    parts = rel_norm.split(os.sep)
    for prefix in _NEVER_OVERWRITE_PREFIXES:
        prefix_parts = prefix.split(os.sep)
        if parts[: len(prefix_parts)] == prefix_parts:
            return True
    return False


def _is_deletion_protected(rel_norm: str) -> bool:
    """Return True if this on-disk relative path must never be deleted."""
    parts = rel_norm.split(os.sep)
    # Always keep __pycache__ and compiled bytecode — not shipped in zip.
    if "__pycache__" in parts or rel_norm.endswith(".pyc"):
        return True
    for prefix in _NEVER_DELETE_PREFIXES:
        prefix_parts = prefix.split(os.sep)
        if parts[: len(prefix_parts)] == prefix_parts:
            return True
    return False


# ── extract + install logic ───────────────────────────────────────────────── #

def _extract_and_install(
    zip_path:    str,
    new_version: str,
    on_status:   "callable[[str], None] | None" = None,
) -> int:
    """
    Extract *zip_path* and install it over the live app directory.

    Applies the three-tier protection rules:
      Tier 1 — PRESERVE files are backed up and restored unchanged.
      Tier 2 — NEVER_OVERWRITE_PREFIXES directories are never written to.
      Tier 3 — NEVER_DELETE_PREFIXES directories are never cleaned up.

    Returns the number of files updated.
    Raises on fatal error.
    """
    def _status(msg: str):
        log.debug("extract: %s", msg)
        if on_status:
            on_status(msg)

    app_dir   = get_app_dir()
    dl_folder = os.path.dirname(zip_path)
    temp_dir  = os.path.join(dl_folder, f"BeamSkin-Studio-temp-{new_version}")

    # ── 1. Extract zip to a temp location ────────────────────────────────── #
    _status("Extracting archive…")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(temp_dir)

    contents = os.listdir(temp_dir)
    source   = (os.path.join(temp_dir, contents[0])
                if len(contents) == 1 and
                   os.path.isdir(os.path.join(temp_dir, contents[0]))
                else temp_dir)

    # ── 2. Collect every relative path the new version ships ─────────────── #
    incoming: set = set()
    for root, _, files in os.walk(source):
        for fname in files:
            rel = os.path.relpath(os.path.join(root, fname), source)
            incoming.add(rel.replace("/", os.sep).replace("\\", os.sep))

    # ── 3. Back up Tier-1 preserved files ────────────────────────────────── #
    backups: dict = {}
    preserve_norm = {p.replace("/", os.sep).replace("\\", os.sep)
                     for p in _PRESERVE}
    for rel in preserve_norm:
        full = os.path.join(app_dir, rel)
        if os.path.exists(full):
            try:
                with open(full, "r", encoding="utf-8") as f:
                    backups[rel] = f.read()
                log.debug("Backed up: %s", rel)
            except Exception as e:
                log.debug("Could not backup %s: %s", rel, e)

    # ── 4. Copy new / changed files into app_dir ──────────────────────────── #
    _status("Copying files…")
    updated = 0
    for root, _, files in os.walk(source):
        rel_dir    = os.path.relpath(root, source)
        target_dir = app_dir if rel_dir == "." else os.path.join(app_dir, rel_dir)
        os.makedirs(target_dir, exist_ok=True)
        for fname in files:
            rel_file = fname if rel_dir == "." else os.path.join(rel_dir, fname)
            rel_norm = rel_file.replace("/", os.sep).replace("\\", os.sep)
            if rel_norm in preserve_norm:
                continue   # restored from backup in step 6
            if _is_overwrite_protected(rel_norm):
                continue   # Tier 2 — entire directory is off-limits for writes
            try:
                shutil.copy2(os.path.join(root, fname),
                             os.path.join(target_dir, fname))
                updated += 1
            except Exception as e:
                log.debug("Could not copy %s: %s", rel_norm, e)

    # ── 5. Remove files the new version no longer ships ───────────────────── #
    #       Skips anything covered by _is_deletion_protected().
    _status("Removing obsolete files…")
    for root, dirs, files in os.walk(app_dir, topdown=False):
        for fname in files:
            full     = os.path.join(root, fname)
            rel_norm = os.path.relpath(full, app_dir)
            if rel_norm in incoming:
                continue   # still present in new version — keep
            if rel_norm in preserve_norm:
                continue   # handled separately
            if _is_deletion_protected(rel_norm):
                continue   # Tier 3 — protected tree
            try:
                os.remove(full)
                log.debug("Removed obsolete file: %s", rel_norm)
            except Exception as e:
                log.warning("Could not remove %s: %s", rel_norm, e)

        # Remove empty directories that are not inside a protected tree.
        for dname in dirs:
            dpath    = os.path.join(root, dname)
            rel_norm = os.path.relpath(dpath, app_dir)
            if _is_deletion_protected(os.path.join(rel_norm, ".keep")):
                continue
            try:
                if not os.listdir(dpath):
                    os.rmdir(dpath)
            except Exception:
                pass

    # ── 6. Restore Tier-1 preserved files ────────────────────────────────── #
    for rel, content in backups.items():
        full = os.path.join(app_dir, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        try:
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            log.debug("Restored: %s", rel)
        except Exception as e:
            log.debug("Could not restore %s: %s", rel, e)

    # ── 7. Clean up temp extraction folder and downloaded zip ────────────── #
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass
    try:
        os.remove(zip_path)
    except Exception:
        pass

    return updated


# ── prompt_update (main update dialog) ───────────────────────────────────── #

def prompt_update(new_version: str, on_done=None):
    log.debug("prompt_update — showing dialog for %s", new_version)

    if _app_instance is None or _colors is None:
        response = messagebox.askyesno(
            "Update Available",
            f"A new version is available!\n\n"
            f"Current: {CURRENT_VERSION}\n"
            f"Latest:  {new_version}\n\n"
            f"Would you like to download it now?",
        )
        if response:
            webbrowser.open(get_github_repo())
        if on_done:
            on_done()
        return

    # ── window setup ──────────────────────────────────────────────────────── #
    update_window = ctk.CTkToplevel(_app_instance)
    update_window.title(t("update.title", default="Update Available"))
    update_window.geometry("500x360")
    update_window.resizable(False, False)
    update_window.transient(_app_instance)
    update_window.grab_set()
    set_window_icon(update_window)

    _WIN_W, _WIN_H = 500, 360
    update_window.update_idletasks()
    x = (update_window.winfo_screenwidth()  // 2) - (_WIN_W // 2)
    y = (update_window.winfo_screenheight() // 2) - (_WIN_H // 2)
    update_window.geometry(f"{_WIN_W}x{_WIN_H}+{x}+{y}")

    # Fire on_done exactly once, regardless of how the window is closed
    _done_fired = [False]
    def _fire_on_done(event=None):
        if not _done_fired[0]:
            _done_fired[0] = True
            if on_done:
                _app_instance.after(0, on_done)
    update_window.bind("<Destroy>", _fire_on_done)

    # ── main frame ────────────────────────────────────────────────────────── #
    main_frame = ctk.CTkFrame(update_window, fg_color=_colors["frame_bg"])
    main_frame.pack(fill="both", expand=True, padx=15, pady=15)

    title_label = ctk.CTkLabel(
        main_frame,
        text=t("update.title", default="Update Available"),
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=_colors["accent"],
    )
    title_label.pack(pady=(5, 15))

    info_frame = ctk.CTkFrame(main_frame, fg_color=_colors["card_bg"], corner_radius=10)
    info_frame.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(
        info_frame,
        text=t("update.current_version", default="Current Version: {CURRENT_VERSION}").format(
            CURRENT_VERSION=CURRENT_VERSION
        ),
        font=ctk.CTkFont(size=15),
        text_color=_colors["text"],
    ).pack(pady=(10, 5))

    ctk.CTkLabel(
        info_frame,
        text="↓",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=_colors["accent"],
    ).pack(pady=2)

    ctk.CTkLabel(
        info_frame,
        text=t("update.new_version", default="New Version: {new_version}").format(
            new_version=new_version
        ),
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=_colors["accent"],
    ).pack(pady=(5, 10))

    ctk.CTkLabel(
        main_frame,
        text=t("update.update_message",
               default="⚙  Your settings and custom data will be preserved."),
        font=ctk.CTkFont(size=13),
        text_color=_colors["text"],
        justify="center",
    ).pack(pady=(0, 10))

    # ── button area ───────────────────────────────────────────────────────── #
    button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(pady=5, fill="x", padx=20)

    # ── skip-version link ─────────────────────────────────────────────────── #
    def _skip_this_version():
        log.debug("Skipping version %r", new_version)
        set_skipped_version(new_version)
        update_window.destroy()

    skip_version_btn = ctk.CTkButton(
        main_frame,
        text=t("update.skip_version", default="Skip this version"),
        command=_skip_this_version,
        fg_color="transparent",
        hover_color=_colors.get("card_hover", _colors["card_bg"]),
        text_color=_colors["text_secondary"],
        height=24,
        font=ctk.CTkFont(size=11),
    )
    # Packed after buttons are created below

    # ── download action ───────────────────────────────────────────────────── #
    def download_update():
        filename       = f"BeamSkin-Studio-{new_version}.zip"
        downloads_folder = get_downloads_folder()
        filepath       = os.path.join(downloads_folder, filename)

        log.debug("Starting download: %s → %s", get_zip_url(), filepath)

        # Resize window for progress area
        update_window.geometry(f"500x420+{x}+{y}")
        download_btn.configure(text="Downloading Update…", state="disabled")
        maybe_later_btn.configure(state="disabled")
        skip_version_btn.configure(state="disabled")
        update_window.update()

        status_label = ctk.CTkLabel(
            main_frame,
            text="Starting download…",
            font=ctk.CTkFont(size=11),
            text_color=_colors["text"],
            wraplength=450,
        )
        status_label.pack(pady=(0, 5))

        progress_bar = ctk.CTkProgressBar(main_frame, width=420)
        progress_bar.set(0)
        progress_bar.pack(pady=(0, 5))
        update_window.update()

        def _dl_thread():
            try:
                resp = requests.get(get_zip_url(), stream=True, timeout=30)
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                done  = 0
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                        done += len(chunk)
                        if total > 0:
                            pct = done / total
                            progress_mb  = done  / 1_048_576
                            total_mb     = total / 1_048_576
                            msg = f"Downloading {filename}… {progress_mb:.1f} MB / {total_mb:.1f} MB"
                        else:
                            pct = 0
                            msg = f"Downloading {filename}… {done/1_048_576:.1f} MB"
                        _app_instance.after(
                            0,
                            lambda m=msg, p=pct: (
                                status_label.configure(text=m),
                                progress_bar.set(p),
                            ),
                        )
                _app_instance.after(0, lambda: _on_dl_success(filepath, downloads_folder))
            except Exception as e:
                log.debug("Download failed: %s", e)
                _app_instance.after(0, lambda err=str(e): _on_dl_failed(err))

        def _on_dl_success(fp: str, dl_folder: str):
            log.debug("Download complete: %s", fp)
            update_window.withdraw()
            _show_downloaded_window(fp, dl_folder, new_version, update_window, _fire_on_done)

        def _on_dl_failed(err: str):
            log.debug("Download failed — showing error")
            download_btn.configure(text=t("update.download_update", default="Download Update"), state="normal")
            maybe_later_btn.configure(state="normal")
            skip_version_btn.configure(state="normal")
            progress_bar.pack_forget()
            status_label.configure(
                text=f"Download failed: {err}\n\nOpening GitHub page instead…",
                text_color="red",
            )
            update_window.after(2000, lambda: [
                webbrowser.open(get_github_repo()),
                update_window.destroy(),
            ])

        threading.Thread(target=_dl_thread, daemon=True).start()

    def maybe_later():
        log.debug("User chose Maybe Later")
        update_window.destroy()

    download_btn = ctk.CTkButton(
        button_frame,
        text=t("update.download_update", default="Download Update"),
        command=download_update,
        fg_color=_colors["accent"],
        hover_color=_colors["accent_hover"],
        text_color=_colors["accent_text"],
        height=40,
        corner_radius=8,
        font=ctk.CTkFont(size=13, weight="bold"),
    )
    download_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

    maybe_later_btn = ctk.CTkButton(
        button_frame,
        text=t("update.maybe_later", default="Maybe Later"),
        command=maybe_later,
        fg_color=_colors["card_bg"],
        hover_color=_colors.get("card_hover", _colors["card_bg"]),
        text_color=_colors["text"],
        height=40,
        corner_radius=8,
        font=ctk.CTkFont(size=13),
    )
    maybe_later_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

    skip_version_btn.pack(pady=(8, 0))


def _show_downloaded_window(filepath, downloads_folder, new_version, update_window, fire_on_done):
    """Show the 'Download Complete' window with Extract / Open Folder / Close."""

    success_window = ctk.CTkToplevel(_app_instance)
    set_window_icon(success_window)
    success_window.title("Download Complete")
    success_window.geometry("450x310")
    success_window.resizable(False, False)
    success_window.transient(_app_instance)
    success_window.grab_set()

    def _close_all():
        try:
            success_window.destroy()
        except Exception:
            pass
        try:
            update_window.destroy()
        except Exception:
            pass

    success_window.protocol("WM_DELETE_WINDOW", _close_all)

    success_window.update_idletasks()
    w = success_window.winfo_width()
    h = success_window.winfo_height()
    sx = (success_window.winfo_screenwidth()  // 2) - (w // 2)
    sy = (success_window.winfo_screenheight() // 2) - (h // 2)
    success_window.geometry(f"{w}x{h}+{sx}+{sy}")

    frame = ctk.CTkFrame(success_window, fg_color=_colors["frame_bg"])
    frame.pack(fill="both", expand=True, padx=15, pady=15)

    ctk.CTkLabel(
        frame, text="✓",
        font=ctk.CTkFont(size=40, weight="bold"),
        text_color=_colors["accent"],
    ).pack(pady=(10, 5))

    ctk.CTkLabel(
        frame, text="Download Complete!",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=_colors["text"],
    ).pack(pady=(0, 10))

    ctk.CTkLabel(
        frame,
        text=f"Update file saved to:\n{filepath}",
        font=ctk.CTkFont(size=11),
        text_color=_colors["text_secondary"],
        justify="center",
    ).pack(pady=10)

    status_lbl = ctk.CTkLabel(
        frame, text="",
        font=ctk.CTkFont(size=11),
        text_color=_colors["text"],
        wraplength=400,
        justify="center",
    )
    status_lbl.pack(pady=(0, 5))

    btn_container = ctk.CTkFrame(frame, fg_color="transparent")
    btn_container.pack(pady=(5, 10), fill="x", padx=10)

    def extract_and_update():
        extract_btn.configure(text="Installing…", state="disabled")
        open_folder_btn.configure(state="disabled")
        close_btn.configure(state="disabled")
        status_lbl.configure(text="Please wait…", text_color=_colors["text"])
        success_window.update()

        def _on_status(msg: str):
            _app_instance.after(0, lambda m=msg: status_lbl.configure(text=m))

        def _ex_thread():
            try:
                files_updated = _extract_and_install(
                    filepath, new_version, on_status=_on_status
                )
                _app_instance.after(0, lambda: _on_extract_success(files_updated))
            except Exception as e:
                log.debug("Extraction failed: %s", e)
                import traceback; traceback.print_exc()
                _app_instance.after(0, lambda err=str(e): _on_extract_failed(err))

        def _on_extract_success(files_updated: int):
            success_window.destroy()
            _show_complete_window(files_updated, new_version, update_window, fire_on_done)

        def _on_extract_failed(err: str):
            extract_btn.configure(text=t("update.update_button", default="Extract & Install"), state="normal")
            open_folder_btn.configure(state="normal")
            close_btn.configure(state="normal")
            status_lbl.configure(
                text=f"Install failed: {err}\nYou can extract manually from the downloads folder.",
                text_color="red",
            )

        threading.Thread(target=_ex_thread, daemon=True).start()

    def open_folder():
        if sys.platform == "win32":
            os.startfile(downloads_folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", downloads_folder])
        else:
            subprocess.Popen(["xdg-open", downloads_folder])
        _close_all()

    extract_btn = ctk.CTkButton(
        btn_container,
        text=t("update.update_button", default="Extract & Install"),
        command=extract_and_update,
        fg_color=_colors["accent"],
        hover_color=_colors["accent_hover"],
        text_color=_colors["accent_text"],
        height=35,
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    extract_btn.pack(fill="x", pady=(0, 5))

    open_folder_btn = ctk.CTkButton(
        btn_container,
        text=t("update.open_download_folder", default="Open Downloads Folder"),
        command=open_folder,
        fg_color=_colors["card_bg"],
        hover_color=_colors.get("card_hover", _colors["card_bg"]),
        text_color=_colors["text"],
        height=35,
    )
    open_folder_btn.pack(fill="x", pady=(0, 5))

    close_btn = ctk.CTkButton(
        btn_container,
        text=t("update.close", default="Close"),
        command=_close_all,
        fg_color=_colors["card_bg"],
        hover_color=_colors.get("card_hover", _colors["card_bg"]),
        text_color=_colors["text"],
        height=35,
    )
    close_btn.pack(fill="x")


def _show_complete_window(files_updated: int, new_version: str, update_window, fire_on_done):
    """Show the post-install 'Update Complete' window with Restart Now / Later."""

    completion_window = ctk.CTkToplevel(_app_instance)
    set_window_icon(completion_window)
    completion_window.title("Update Complete")
    completion_window.geometry("450x280")
    completion_window.resizable(False, False)
    completion_window.transient(_app_instance)
    completion_window.grab_set()

    completion_window.update_idletasks()
    w = completion_window.winfo_width()
    h = completion_window.winfo_height()
    cx = (completion_window.winfo_screenwidth()  // 2) - (w // 2)
    cy = (completion_window.winfo_screenheight() // 2) - (h // 2)
    completion_window.geometry(f"{w}x{h}+{cx}+{cy}")

    comp_frame = ctk.CTkFrame(completion_window, fg_color=_colors["frame_bg"])
    comp_frame.pack(fill="both", expand=True, padx=15, pady=15)

    ctk.CTkLabel(
        comp_frame,
        text="✓ Update Complete!",
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=_colors["accent"],
    ).pack(pady=(10, 5))

    ctk.CTkLabel(
        comp_frame,
        text=(
            f"Updated {files_updated} files to version {new_version}\n\n"
            "Your settings and custom vehicles have been preserved.\n\n"
            "Please restart BeamSkin Studio to use the new version."
        ),
        font=ctk.CTkFont(size=11),
        text_color=_colors["text"],
        justify="center",
    ).pack(pady=10)

    def restart_app():
        log.debug("Restarting application…")
        fire_on_done()
        app_dir        = get_app_dir()
        batch_launcher = os.path.join(app_dir, "launchers-scripts", "quick_launcher.bat")
        py_launcher    = os.path.join(app_dir, "launchers-scripts", "quick_launcher.py")
        main_script    = os.path.join(app_dir, "main.py")

        completion_window.destroy()
        try:
            update_window.destroy()
        except Exception:
            pass
        _app_instance.destroy()

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

        sys.exit(0)

    ctk.CTkButton(
        comp_frame,
        text=t("update.restart_now", default="Restart Now"),
        command=restart_app,
        fg_color=_colors["accent"],
        hover_color=_colors["accent_hover"],
        text_color=_colors["accent_text"],
        height=35,
    ).pack(pady=(5, 5))

    ctk.CTkButton(
        comp_frame,
        text=t("update.restart_later", default="Restart Later"),
        command=completion_window.destroy,
        fg_color=_colors["card_bg"],
        hover_color=_colors.get("card_hover", _colors["card_bg"]),
        text_color=_colors["text"],
        height=35,
    ).pack(pady=(0, 10))


# ── public API ────────────────────────────────────────────────────────────── #

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
    previously skipped versions.  Use this for the 'Check for Updates' button.
    Shows a toast if already up to date.
    """
    _check_for_updates_impl(on_done=on_done, ignore_skip=True)


def _check_for_updates_impl(on_done=None, ignore_skip: bool = False):
    """Internal implementation shared by check_for_updates() and check_for_updates_manual()."""
    log.debug("========== UPDATE CHECK STARTED ==========")
    log.debug("Platform: %s  Repo: %s", sys.platform, get_github_repo())
    log.debug("Current:  %s", CURRENT_VERSION)
    log.debug("ignore_skip=%s  skipped=%r", ignore_skip, get_skipped_version())

    def _worker():
        log.debug("Fetching latest release from: %s", get_releases_api_url())
        try:
            latest, _zip_url = fetch_latest_release()
            log.debug("Remote: %s  zip: %s", latest, _zip_url)
            if is_newer_version(latest, CURRENT_VERSION):
                log.debug("UPDATE AVAILABLE: %s → %s", CURRENT_VERSION, latest)
                log.debug("========== UPDATE CHECK COMPLETE ==========")

                skipped = get_skipped_version()
                if not ignore_skip and skipped and skipped == latest:
                    log.debug("Version %r is skipped, suppressing dialog", latest)
                    if on_done and _app_instance:
                        _app_instance.after(0, on_done)
                    elif on_done:
                        on_done()
                    return

                if _app_instance:
                    _app_instance.after(0, lambda: prompt_update(latest, on_done=on_done))
                else:
                    response = messagebox.askyesno(
                        "Update Available",
                        f"Version {latest} is available!\nDownload now?",
                    )
                    if response:
                        webbrowser.open(get_github_repo())
                    if on_done:
                        on_done()
                return
        except Exception as e:
            log.debug("Update check failed: %s", e)

        log.debug("========== UPDATE CHECK COMPLETE ==========")

        # No update (or check failed) — no dialog was shown
        if ignore_skip:
            _show_up_to_date_toast()
        if on_done and _app_instance:
            _app_instance.after(0, on_done)
        elif on_done:
            on_done()

    threading.Thread(target=_worker, daemon=True).start()


def _show_up_to_date_toast() -> None:
    """Inform the user they are already on the latest version (manual check)."""
    if _app_instance is None:
        return
    try:
        # Use the app's notification system if available
        if hasattr(_app_instance, "show_notification"):
            _app_instance.after(
                0,
                lambda: _app_instance.show_notification(
                    t("update.up_to_date",
                      version=CURRENT_VERSION,
                      default=f"You're up to date!  (v{CURRENT_VERSION})"),
                    type="success",
                    duration=3500,
                ),
            )
            return
    except Exception as e:
        log.debug("_show_up_to_date_toast: %s", e)

    # Fallback: simple messagebox
    _app_instance.after(
        0,
        lambda: messagebox.showinfo(
            "No Updates",
            f"You're already on the latest version!\n\n(v{CURRENT_VERSION})",
        ),
    )
