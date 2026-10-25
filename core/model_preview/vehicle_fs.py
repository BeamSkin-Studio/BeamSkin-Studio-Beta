from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
import zipfile
from typing import Iterable, Optional


class VehicleFS:
    def __init__(self, roots: Iterable[str], prefixes: Iterable[str] = ("vehicles/",)):
        self._roots = [r for r in roots if r and os.path.exists(r)]
        self._prefixes = tuple(p.lower() for p in prefixes)
        self._entries: Optional[dict[str, tuple]] = None
        self._zips: dict[int, zipfile.ZipFile] = {}
        self._lock = threading.RLock()

    def _wanted(self, vpath: str) -> bool:
        return vpath.lower().startswith(self._prefixes)

    def _build(self) -> dict:
        entries: dict[str, tuple] = {}
        for ri, root in enumerate(self._roots):
            try:
                if os.path.isdir(root):
                    for base, dirs, names in os.walk(root):
                        if os.path.normcase(base) == os.path.normcase(root):
                            dirs[:] = [name for name in dirs if name.casefold() == "vehicles"]
                        for name in names:
                            full = os.path.join(base, name)
                            vpath = os.path.relpath(full, root).replace("\\", "/")
                            if self._wanted(vpath):
                                entries[vpath.lower()] = (ri, full, vpath)
                elif zipfile.is_zipfile(root):
                    with zipfile.ZipFile(root) as z:
                        for name in z.namelist():
                            if name.endswith("/"):
                                continue
                            vpath = name.replace("\\", "/").lstrip("/")
                            if self._wanted(vpath):
                                entries[vpath.lower()] = (ri, name, vpath)
            except (OSError, zipfile.BadZipFile) as e:
                print(f"[WARNING] model_preview.vehicle_fs: cannot read {root}: {type(e).__name__}: {e}")
        return entries

    def _all(self) -> dict:
        if self._entries is None:
            with self._lock:
                if self._entries is None:
                    self._entries = self._build()
        return self._entries

    def add_root(self, root: str) -> bool:
        if not root or not os.path.exists(root) or root in self._roots:
            return False
        with self._lock:
            self._roots.append(root)
            self._entries = None
        return True

    @property
    def roots(self) -> list[str]:
        return list(self._roots)

    def files(self, prefix: str, ext: str = "", recursive: bool = True) -> list[str]:
        pl, el = prefix.lower(), ext.lower()
        out = []
        for low, (_ri, _real, vpath) in self._all().items():
            if not low.startswith(pl) or (el and not low.endswith(el)):
                continue
            if not recursive and "/" in low[len(pl):]:
                continue
            out.append(vpath)
        return sorted(out, key=str.lower)

    def exists(self, vpath: str) -> bool:
        return vpath.lower() in self._all()

    def stamp(self, vpath: str) -> tuple:
        ri, real, vp = self._all()[vpath.lower()]
        root = self._roots[ri]
        try:
            mtime = os.stat(real if os.path.isdir(root) else root).st_mtime_ns
        except OSError:
            mtime = 0
        return (root, mtime, vp.lower())

    def _zip(self, ri: int) -> zipfile.ZipFile:
        with self._lock:
            z = self._zips.get(ri)
            if z is None:
                z = zipfile.ZipFile(self._roots[ri])
                self._zips[ri] = z
            return z

    def read(self, vpath: str) -> bytes:
        ri, real, _vp = self._all()[vpath.lower()]
        if os.path.isdir(self._roots[ri]):
            with open(real, "rb") as f:
                return f.read()
        with self._lock:
            return self._zip(ri).read(real)

    def extract(self, vpath: str, cache_dir: str = "") -> str:
        ri, real, vp = self._all()[vpath.lower()]
        root = self._roots[ri]
        if os.path.isdir(root):
            return real
        cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "BeamSkinStudio_preview")
        tag = hashlib.sha1(f"{root}|{vp}".encode("utf-8", "replace")).hexdigest()[:16]
        folder = os.path.join(cache_dir, tag)
        dest = os.path.join(folder, os.path.basename(vp))
        try:
            fresh = os.path.getmtime(dest) >= os.path.getmtime(root)
        except OSError:
            fresh = False
        if not fresh:
            os.makedirs(folder, exist_ok=True)
            data = self.read(vpath)
            tmp = dest + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
        return dest

    def close(self):
        with self._lock:
            for z in self._zips.values():
                try:
                    z.close()
                except Exception:
                    pass
            self._zips.clear()


def find_beamng_content() -> str:
    env = os.environ.get("BEAMNG_CONTENT", "").strip()
    if env and os.path.isdir(env):
        return env
    steam_roots = [
        r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam",
        os.path.expanduser("~/.steam/steam"), os.path.expanduser("~/.local/share/Steam"),
    ]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam_roots.insert(0, winreg.QueryValueEx(k, "SteamPath")[0])
    except Exception:
        pass
    libraries = []
    for steam in steam_roots:
        vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, "r", encoding="utf-8", errors="replace") as f:
                libraries += [m.replace("\\\\", "\\") for m in re.findall(r'"path"\s+"([^"]+)"', f.read())]
        except OSError:
            pass
        libraries.append(steam)
    for lib in libraries:
        content = os.path.join(lib, "steamapps", "common", "BeamNG.drive", "content")
        if os.path.isdir(content):
            return content
    return ""
