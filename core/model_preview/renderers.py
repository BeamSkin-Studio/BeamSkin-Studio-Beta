from __future__ import annotations

import importlib.util
import os
import platform
from dataclasses import dataclass
from typing import Callable, Optional

AUTO = "auto"
GL = "opengl"
GL_SOFTWARE = "opengl_software"
WGPU_AUTO = "wgpu"
WGPU_D3D12 = "wgpu_d3d12"
WGPU_VULKAN = "wgpu_vulkan"
WGPU_METAL = "wgpu_metal"

SETTING_KEY = "preview_renderer"
ENV_OVERRIDE = "BEAMSKIN_PREVIEW_RENDERER"

WGPU_BACKEND_NAME = {WGPU_D3D12: "D3D12", WGPU_VULKAN: "Vulkan", WGPU_METAL: "Metal"}

Spec = tuple


@dataclass(frozen=True)
class RendererOption:
    id: str
    label: str
    description: str
    available: bool = True
    reason: str = ""


def wgpu_installed() -> bool:
    try:
        return importlib.util.find_spec("wgpu") is not None
    except Exception:
        return False


_NEEDS_WGPU = "Needs the optional 'wgpu' package  (pip install wgpu)"


def list_options() -> list[RendererOption]:
    system = platform.system()
    have_wgpu = wgpu_installed()
    wgpu_reason = "" if have_wgpu else _NEEDS_WGPU

    opts = [
        RendererOption(AUTO, "Automatic (recommended)",
                       "Uses OpenGL, and switches to another renderer by itself if OpenGL "
                       "fails or turns out to be software-only."),
        RendererOption(GL, "OpenGL (GPU)",
                       "Qt's OpenGL widget on the graphics card. Needs an app restart to apply."),
    ]
    if system in ("Windows", "Linux"):
        opts.append(RendererOption(GL_SOFTWARE, "OpenGL (software / CPU)",
                                   "Slow but works on any machine, e.g. remote desktop or broken "
                                   "GPU drivers. Needs an app restart to apply."))
    opts.append(RendererOption(WGPU_AUTO, "wgpu (best native API)",
                               "Direct3D 12 / Vulkan / Metal, whichever fits this system best.",
                               have_wgpu, wgpu_reason))
    if system == "Windows":
        opts.append(RendererOption(WGPU_D3D12, "Direct3D 12 (wgpu)",
                                   "Native Direct3D 12 renderer.", have_wgpu, wgpu_reason))
    if system in ("Windows", "Linux"):
        opts.append(RendererOption(WGPU_VULKAN, "Vulkan (wgpu)",
                                   "Native Vulkan renderer.", have_wgpu, wgpu_reason))
    if system == "Darwin":
        opts.append(RendererOption(WGPU_METAL, "Metal (wgpu)",
                                   "Native Metal renderer.", have_wgpu, wgpu_reason))
    return opts


def _valid_ids() -> set[str]:
    return {o.id for o in list_options()}


def label_for(renderer_id: str) -> str:
    for o in list_options():
        if o.id == renderer_id:
            return o.label
    return renderer_id


def get_preference() -> str:
    env = os.environ.get(ENV_OVERRIDE, "").strip().lower()
    value = env
    if not value:
        try:
            from core import settings as _s
            getter = getattr(_s, "get_preview_renderer", None)
            value = (getter() if getter else str(_s.app_settings.get(SETTING_KEY, AUTO) or AUTO)).lower()
        except Exception:
            value = AUTO
    return value if value in _valid_ids() else AUTO


def process_mode(pref: str) -> str:
    if pref == GL_SOFTWARE:
        return "software"
    if pref == GL:
        return "desktop"
    return "default"


_applied_mode: Optional[str] = None


def apply_startup_renderer() -> str:
    global _applied_mode
    pref = get_preference()
    mode = process_mode(pref)
    _applied_mode = mode
    if mode == "default":
        print(f"[DEBUG] renderers: startup preference={pref!r}, Qt OpenGL defaults untouched")
        return mode
    try:
        from PySide6.QtCore import QCoreApplication, Qt
        if mode == "software":
            os.environ["QT_OPENGL"] = "software"
            QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
        else:
            os.environ["QT_OPENGL"] = "desktop"
            QCoreApplication.setAttribute(Qt.AA_UseDesktopOpenGL, True)
        print(f"[DEBUG] renderers: startup preference={pref!r}, Qt OpenGL mode forced to {mode!r}")
    except Exception as e:
        print(f"[WARNING] renderers: could not apply OpenGL mode {mode!r}: {type(e).__name__}: {e}")
    return mode


def restart_required(new_pref: str) -> bool:
    return process_mode(new_pref) != (_applied_mode or "default")


_listeners: list[Callable[[], None]] = []


def add_listener(cb: Callable[[], None]) -> None:
    if cb not in _listeners:
        _listeners.append(cb)


def remove_listener(cb: Callable[[], None]) -> None:
    if cb in _listeners:
        _listeners.remove(cb)


def set_preference(pref: str) -> bool:
    if pref not in _valid_ids():
        pref = AUTO
    try:
        from core import settings as _s
        setter = getattr(_s, "set_preview_renderer", None)
        if setter:
            setter(pref)
        else:
            _s.app_settings[SETTING_KEY] = pref
            _s.save_settings()
    except Exception as e:
        print(f"[WARNING] renderers: could not save preference: {type(e).__name__}: {e}")
    for cb in list(_listeners):
        try:
            cb()
        except Exception as e:
            print(f"[WARNING] renderers: listener failed: {type(e).__name__}: {e}")
    return restart_required(pref)


def build_chain(pref: str) -> list[Spec]:
    if pref == AUTO:
        chain: list[Spec] = [("gl", None)]
        if wgpu_installed():
            chain.append(("wgpu", None))
        return chain
    if pref in (GL, GL_SOFTWARE):
        return [("gl", None)]
    if pref == WGPU_AUTO:
        return [("wgpu", None)]
    if pref in WGPU_BACKEND_NAME:
        return [("wgpu", WGPU_BACKEND_NAME[pref])]
    return [("gl", None)]


def spec_name(spec: Spec) -> str:
    kind, backend = spec
    if kind == "gl":
        return "OpenGL"
    return f"wgpu ({backend})" if backend else "wgpu"


_active = ""


def set_active(description: str) -> None:
    global _active
    _active = description or ""


def get_active() -> str:
    return _active
