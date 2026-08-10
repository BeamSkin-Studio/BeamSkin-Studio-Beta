from __future__ import annotations
import os, json, threading
from typing import Dict, List, Optional, Any, Callable

from PySide6.QtCore    import Qt, QTimer, Signal
from PySide6.QtGui     import QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QLineEdit, QComboBox, QProgressBar, QScrollArea, QVBoxLayout, QHBoxLayout, QFileDialog, QDialog, QCheckBox

from gui.theme   import COLORS, font
from gui.widgets import ToggleSwitch
from gui.state   import state

try:
    from core.localization import t
except ImportError:
    print("[DEBUG] generator: core.localization not available — using passthrough t()")
    def t(key, **kw): return key

try:
    from utils.file_ops import load_added_vehicles_json
except ImportError:
    print("[DEBUG] generator: utils.file_ops.load_added_vehicles_json not available — using empty stub")
    def load_added_vehicles_json(): return {}

try:
    from core.file_ops import generate_multi_skin_mod
except ImportError:
    print("[DEBUG] generator: core.file_ops.generate_multi_skin_mod not available — generation disabled")
    generate_multi_skin_mod = None

try:
    from utils.config_helper import load_config_types
    _CONFIG_TYPES = load_config_types()
    print(f"[DEBUG] generator: loaded {len(_CONFIG_TYPES)} config types")
except ImportError:
    print("[DEBUG] generator: utils.config_helper not available — using fallback config types")
    _CONFIG_TYPES = ["Factory", "Custom", "Police"]

try:
    from core.settings import get_mods_folder_path as _get_mods_folder_path
except ImportError:
    print("[DEBUG] generator: core.settings.get_mods_folder_path not available — using empty stub")
    def _get_mods_folder_path(): return ""

try:
    from core.settings import get_data_dir as _get_data_dir
except ImportError:
    print("[DEBUG] generator: core.settings.get_data_dir not available — using fallback ~/BeamSkinStudio")
    def _get_data_dir(): return os.path.join(os.path.expanduser("~"), "BeamSkinStudio")

try:
    from PIL import Image as _PILImage
    _PIL_OK = True
except Exception as e:
    print(f"[DEBUG] PIL not available: {e}")
    _PIL_OK = False

try:
    from core.project_registry import add_or_update_entry as _reg_add
    print("[DEBUG] generator: project_registry imported OK")
except ImportError as _reg_imp_exc:
    print(f"[DEBUG] generator: project_registry not available: {_reg_imp_exc} — registry disabled")
    def _reg_add(path, data): pass

try:
    from gui.components.project_browser import ProjectBrowserDialog
    print("[DEBUG] generator: ProjectBrowserDialog imported OK")
except ImportError as _pb_imp_exc:
    print(f"[DEBUG] generator: ProjectBrowserDialog not available: {_pb_imp_exc} — will fall back to file dialog")
    ProjectBrowserDialog = None


_PRESET_KIND_LAYER_FACTORS      = "layer_factors"
_PRESET_KIND_MATERIAL_PROPERTIES = "material_properties"


def _presets_dir(kind: str) -> str:
    path = os.path.join(_get_data_dir(), "presets", kind)
    return path


def _sanitize_preset_filename(name: str) -> str:
    keep = "-_ ()"
    cleaned = "".join(c for c in name if c.isalnum() or c in keep).strip()
    if not cleaned:
        print(f"[DEBUG] _sanitize_preset_filename: {name!r} sanitized to empty — falling back to 'preset'")
        return "preset"
    return cleaned


def _list_presets(kind: str) -> List[str]:
    d = _presets_dir(kind)
    if not os.path.isdir(d):
        print(f"[DEBUG] _list_presets: no presets dir for kind={kind!r} ({d!r})")
        return []
    entries = []
    skipped = 0
    for fn in os.listdir(d):
        if not fn.lower().endswith(".json"):
            continue
        fp = os.path.join(d, fn)
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            name = data.get("name") or os.path.splitext(fn)[0]
            mtime = os.path.getmtime(fp)
        except Exception as exc:
            print(f"[DEBUG] _list_presets: failed to read {fp!r}: {exc}")
            skipped += 1
            continue
        entries.append((name, mtime))
    entries.sort(key=lambda e: e[1], reverse=True)
    result = [name for name, _mtime in entries]
    print(f"[DEBUG] _list_presets: kind={kind!r} found={len(result)} skipped={skipped}")
    return result


def _preset_filepath(kind: str, name: str) -> str:
    return os.path.join(_presets_dir(kind), _sanitize_preset_filename(name) + ".json")


def _save_preset(kind: str, name: str, values: Dict[str, Any]) -> bool:
    name = name.strip()
    if not name:
        print("[DEBUG] _save_preset: aborted — empty name")
        return False
    d = _presets_dir(kind)
    try:
        os.makedirs(d, exist_ok=True)
        with open(_preset_filepath(kind, name), "w", encoding="utf-8") as fh:
            json.dump({"name": name, "values": values}, fh, indent=2, ensure_ascii=False)
        print(f"[DEBUG] _save_preset: saved {kind}/{name!r}")
        return True
    except Exception as exc:
        print(f"[DEBUG] _save_preset: failed to save {kind}/{name}: {exc}")
        return False


def _load_preset(kind: str, name: str) -> Optional[Dict[str, Any]]:
    fp = _preset_filepath(kind, name)
    if not os.path.isfile(fp):
        print(f"[DEBUG] _load_preset: {kind}/{name!r} not found at {fp!r}")
        return None
    try:
        with open(fp, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("values")
    except Exception as exc:
        print(f"[DEBUG] _load_preset: failed to load {kind}/{name}: {exc}")
        return None


def _delete_preset(kind: str, name: str) -> bool:
    fp = _preset_filepath(kind, name)
    try:
        if os.path.isfile(fp):
            os.remove(fp)
            print(f"[DEBUG] _delete_preset: deleted {kind}/{name!r}")
            return True
        print(f"[DEBUG] _delete_preset: {kind}/{name!r} not found — nothing to delete")
    except Exception as exc:
        print(f"[DEBUG] _delete_preset: failed to delete {kind}/{name}: {exc}")
    return False


print("[DEBUG] Loading class: GeneratorTab")


def _load_pixmap_robust(path: str, max_w: int = 400, max_h: int = 200) -> Optional[QPixmap]:
    print(f"[DEBUG] _load_pixmap_robust: loading {path!r} (max={max_w}x{max_h})")

    ext = os.path.splitext(path)[1].lower()

    def _scale(px: QPixmap) -> QPixmap:
        if px.isNull():
            return px
        return px.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _qt_load() -> Optional[QPixmap]:
        px = QPixmap(path)
        return _scale(px) if not px.isNull() else None

    def _pil_load() -> Optional[QPixmap]:
        if not _PIL_OK:
            return None
        try:
            from PySide6.QtGui import QImage
            _PILImage.MAX_IMAGE_PIXELS = None
            img = _PILImage.open(path)
            img.thumbnail((max_w * 2, max_h * 2), _PILImage.Resampling.LANCZOS)
            img = img.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qi = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
            px = QPixmap.fromImage(qi)
            return _scale(px) if not px.isNull() else None
        except Exception as e:
            print(f"[DEBUG] PIL load failed for {os.path.basename(path)}: {e}")
            return None

    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga"):
        result = _qt_load()
        if result:
            print(f"[DEBUG] _load_pixmap_robust: loaded via Qt ({ext}): {os.path.basename(path)}")
            return result
        result = _pil_load()
        if result:
            print(f"[DEBUG] _load_pixmap_robust: loaded via PIL fallback ({ext}): {os.path.basename(path)}")
        else:
            print(f"[DEBUG] _load_pixmap_robust: ALL strategies failed for {ext} file: {os.path.basename(path)}")
        return result

    elif ext == ".dds":
        _SRGB_REMAP = {29: 28, 72: 71, 75: 74, 78: 77, 99: 98}

        def _patch_dxgi(data: bytes) -> bytes:
            import struct as _st
            if len(data) < 148 or data[:4] != b"DDS " or data[84:88] != b"DX10":
                return data
            fmt = _st.unpack_from("<I", data, 128)[0]
            remapped = _SRGB_REMAP.get(fmt)
            if remapped is None:
                return data
            print(f"[DEBUG] DDS sRGB remap {fmt}→{remapped}: {os.path.basename(path)}")
            p = bytearray(data)
            _st.pack_into("<I", p, 128, remapped)
            return bytes(p)

        def _imageio_load() -> Optional[QPixmap]:
            try:
                import io as _io
                import imageio.v2 as _iio
                import numpy as _np
                from PIL import Image as _PilImg
                from PySide6.QtGui import QImage
                _PilImg.MAX_IMAGE_PIXELS = None
                with open(path, "rb") as _fh:
                    raw = _fh.read()
                arr = _iio.imread(_io.BytesIO(_patch_dxgi(raw)))
                if arr is None or arr.size == 0:
                    return None
                if arr.ndim == 2:
                    arr = _np.stack([arr, arr, arr,
                                     _np.full(arr.shape, 255, dtype=_np.uint8)], axis=-1)
                elif arr.shape[2] == 3:
                    arr = _np.dstack([arr, _np.full(arr.shape[:2], 255, dtype=_np.uint8)])
                arr = arr[:, :, :4].astype(_np.uint8)
                h, w = arr.shape[:2]
                raw_bytes = bytes(arr.tobytes())
                qi = QImage(raw_bytes, w, h, w * 4, QImage.Format.Format_RGBA8888)
                qi = qi.copy()
                if qi.isNull():
                    return None
                px = QPixmap.fromImage(qi)
                return _scale(px) if not px.isNull() else None
            except Exception as e:
                print(f"[DEBUG] imageio load failed for {os.path.basename(path)}: {e}")
                return None

        def _wand_load() -> Optional[QPixmap]:
            try:
                from wand.image import Image as WandImage
                from PySide6.QtGui import QImage
                from PySide6.QtCore import QByteArray
                with open(path, "rb") as _fh:
                    raw = _fh.read()
                with WandImage(blob=_patch_dxgi(raw), format="dds") as img:
                    blob = img.make_blob("png")
                qi = QImage()
                qi.loadFromData(QByteArray(blob))
                if qi.isNull():
                    return None
                px = QPixmap.fromImage(qi)
                return _scale(px) if not px.isNull() else None
            except Exception as e:
                print(f"[DEBUG] Wand load failed for {os.path.basename(path)}: {e}")
                return None

        result = _imageio_load()
        if result:
            print(f"[DEBUG] _load_pixmap_robust: loaded DDS via imageio: {os.path.basename(path)}")
            return result
        result = _wand_load()
        if result:
            print(f"[DEBUG] _load_pixmap_robust: loaded DDS via Wand fallback: {os.path.basename(path)}")
            return result
        result = _pil_load()
        if result:
            print(f"[DEBUG] _load_pixmap_robust: loaded DDS via PIL fallback: {os.path.basename(path)}")
            return result
        result = _qt_load()
        if result:
            print(f"[DEBUG] _load_pixmap_robust: loaded DDS via Qt fallback: {os.path.basename(path)}")
            return result
        print(f"[DEBUG] _load_pixmap_robust: ALL DDS strategies failed, showing placeholder: {os.path.basename(path)}")
        from PySide6.QtGui import QImage, QPainter, QColor, QFont as _QFont
        placeholder = QImage(max_w, 80, QImage.Format.Format_RGBA8888)
        placeholder.fill(QColor("#2a2a3a"))
        painter = QPainter(placeholder)
        painter.setPen(QColor("#a0a0c0"))
        f = _QFont(); f.setPointSize(10); f.setBold(True)
        painter.setFont(f)
        painter.drawText(
            placeholder.rect(), Qt.AlignCenter,
            f"🖼  DDS — {os.path.basename(path)}\n(preview not available)"
        )
        painter.end()
        return QPixmap.fromImage(placeholder)

    else:
        result = _pil_load()
        if result:
            print(f"[DEBUG] _load_pixmap_robust: loaded via PIL ({ext}): {os.path.basename(path)}")
            return result
        result = _qt_load()
        if result:
            print(f"[DEBUG] _load_pixmap_robust: loaded via Qt fallback ({ext}): {os.path.basename(path)}")
        else:
            print(f"[DEBUG] _load_pixmap_robust: ALL strategies failed for {ext} file: {os.path.basename(path)}")
        return result


def _set_entry(entry, text: str, placeholder: bool = False):
    if hasattr(entry, "set_text"):
        entry.set_text(text)
    else:
        entry.setText(text)


def _get_entry_text(entry) -> str:
    return entry.text() if hasattr(entry, "text") else ""


def _make_project_key(carid: str, variant_suffix: str) -> str:
    return f"{carid}__{variant_suffix}" if variant_suffix else carid


def _split_project_key(key: str):
    if "__" in key:
        base, suffix = key.split("__", 1)
        return base, suffix
    return key, ""


_ILLEGAL_NAME_CHARS = set('\\/:*?"<>|')

def _find_illegal_chars(name: str):
    return sorted({c for c in name if c in _ILLEGAL_NAME_CHARS})


class GeneratorTab(QWidget):
    _status_signal   = Signal(str)
    _progress_signal = Signal(int)
    _done_signal     = Signal(bool)

    def __init__(self, parent: QWidget,
                 notification_callback: Callable[[str, str, int], None] = None,
                 preview_manager=None,
                 **_kwargs):
        super().__init__(parent)
        print("[DEBUG] GeneratorTab.__init__: constructing tab")
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self.show_notification = notification_callback or self._fallback_notification

        self.mod_name_entry_sidebar: Optional[QLineEdit] = None
        self.author_entry_sidebar:   Optional[QLineEdit] = None

        self.project_data: Dict = {"mod_name": "", "author": "", "cars": {}}
        self.selected_car_for_skin: Optional[str] = None
        self.selected_skin_index:   Optional[int]  = None
        self.editing_mode:          bool            = False
        self.expanded_car_id:       Optional[str]   = None

        self.config_types = _CONFIG_TYPES

        self._dds_path       = ""
        self._data_map_path  = ""
        self._color_map_path = ""
        self._dds_path_2       = ""
        self._data_map_path_2  = ""
        self._color_map_path_2 = ""
        self._emissive_dds_path = ""

        self._custom_layers: List[Dict[str, Any]] = []
        self._custom_layer_cards: List[Dict[str, Any]] = []

        self._pc_file_path   = ""
        self._jpg_file_path  = ""
        self._config_name    = ""
        self._data_map_photo_stash: Optional[QPixmap] = None
        self._current_project_path: Optional[str] = None
        self._project_dirty: bool = False
        self._project_emptied_since_load: bool = False

        self.material_properties_entries: Dict[str, Dict[str, QLineEdit]] = {}
        self.info_data_entries: Dict[str, QLineEdit] = {}
        self._info_field_originals: Dict[str, Any] = {}
        self.car_id_list: List = self._build_car_id_list()

        self._setup_ui()
        self._setup_project_shortcuts()

        self._status_signal.connect(self._export_status.setText)
        self._progress_signal.connect(self._progress_bar.setValue)
        self._done_signal.connect(self._on_generate_done)
        self._pending_generate_button = None
        print("[DEBUG] GeneratorTab.__init__: done, UI ready")


    def _selected_variant_suffix(self) -> str:
        if not self.selected_car_for_skin:
            return ""
        info = self.project_data["cars"].get(self.selected_car_for_skin, {})
        return info.get("variant_suffix", "")

    def _is_variant(self) -> bool:
        return self._selected_variant_suffix() != ""

    def _needs_double_layer(self) -> bool:
        if not self._is_variant():
            return False
        base = self.project_data["cars"].get(self.selected_car_for_skin, {}) \
                   .get("base_carid", "")
        suffix = self._selected_variant_suffix()
        try:
            from core.config import is_single_layer_variant
        except ImportError:
            print("[DEBUG] _needs_double_layer: core.config.is_single_layer_variant not available — assuming double layer")
            def is_single_layer_variant(_c, _s): return False
        single_layer = is_single_layer_variant(base, suffix)
        result = not single_layer
        print(f"[DEBUG] _needs_double_layer: base={base!r} suffix={suffix!r} single_layer={single_layer} -> needs_double={result}")
        return result


    def _set_project_locked(self, locked: bool) -> None:
        self.setEnabled(not locked)
        try:
            mw = self.window()
            if mw and hasattr(mw, "sidebar"):
                mw.sidebar.set_locked(locked)
        except RuntimeError as exc:
            print(f"[DEBUG] _set_project_locked: sidebar gone (mid-rebuild): {exc}")

    def _on_generate_done(self, success: bool):
        print(f"[DEBUG] _on_generate_done: success={success}")

        self._set_project_locked(False)

        enabled = False
        try:
            mw = self.window()
            if mw and hasattr(mw, "topbar") and hasattr(mw.topbar, "generate_button"):
                mw.topbar.generate_button.setEnabled(True)
                enabled = True
        except RuntimeError as exc:
            print(f"[DEBUG] _on_generate_done: topbar generate_button gone (mid-rebuild): {exc}")

        if not enabled:
            btn = getattr(self, "_pending_generate_button", None)
            if btn is not None:
                try:
                    btn.setEnabled(True)
                    print("[DEBUG] _on_generate_done: re-enabled fallback pending_generate_button")
                except RuntimeError as exc:
                    print(f"[DEBUG] _on_generate_done: pending_generate_button deleted during refresh_ui(): {exc}")
            else:
                print("[DEBUG] _on_generate_done: no topbar button and no pending_generate_button to re-enable")
        self._pending_generate_button = None

        hide_delay = 2000 if success else 8000
        QTimer.singleShot(hide_delay, lambda: self._export_overlay.setVisible(False))

    def _fallback_notification(self, msg: str, kind: str = "info", duration: int = 3000):
        print(f"[{kind.upper()}] {msg}")


    def _build_car_id_list(self) -> List:
        vehicles = load_added_vehicles_json()
        state.added_vehicles.clear()
        state.added_vehicles.update(vehicles)
        car_list = []
        for cid, cname in state.vehicle_ids.items():
            if cid not in state.added_vehicles:
                car_list.append((cid, cname))
        for cid, cname in state.added_vehicles.items():
            car_list.append((cid, cname))
        result = sorted(car_list, key=lambda x: x[1].lower())
        print(f"[DEBUG] _build_car_id_list: {len(result)} vehicles ({len(vehicles)} added, {len(state.vehicle_ids)} known)")
        return result

    def refresh_vehicle_list(self):
        print("[DEBUG] refresh_vehicle_list: rebuilding vehicle list from state")
        self.car_id_list = self._build_car_id_list()
        self.refresh_project_display()


    def set_sidebar_references(self, mod_name_entry, author_entry):
        print("[DEBUG] set_sidebar_references: binding sidebar mod_name/author entries")
        self.mod_name_entry_sidebar = mod_name_entry
        self.author_entry_sidebar   = author_entry
        if self.project_data.get("mod_name"):
            _set_entry(mod_name_entry, self.project_data["mod_name"])
        if self.project_data.get("author"):
            _set_entry(author_entry, self.project_data["author"])


    def _setup_project_shortcuts(self):
        print("[DEBUG] _setup_project_shortcuts: wiring Ctrl+S / Ctrl+Shift+S")

        save_sc = QShortcut(QKeySequence.Save, self)
        save_sc.activated.connect(self.save_project)
        self._save_shortcut = save_sc

        save_as_sc = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        save_as_sc.activated.connect(self.save_project_as)
        self._save_as_shortcut = save_as_sc

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setFixedWidth(320)
        sidebar.setStyleSheet(f"background:{COLORS.get('sidebar_bg', COLORS['frame_bg'])};")
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(15, 15, 15, 15)
        sb.setSpacing(8)

        self._proj_hdr_lbl = QLabel(t("project.project_overview"))
        self._proj_hdr_lbl.setFont(font(13, "bold"))
        self._proj_hdr_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        sb.addWidget(self._proj_hdr_lbl)

        btn_row1 = QHBoxLayout()
        self._save_btn  = self._mk_btn(t("project.save_project"),  self.save_project,  "primary", height=30)
        self._load_btn  = self._mk_btn(t("project.load_project"),  self.load_project,  "primary", height=30)
        btn_row1.addWidget(self._save_btn)
        btn_row1.addWidget(self._load_btn)
        sb.addLayout(btn_row1)

        self._save_as_btn = self._mk_btn(
            t("project.save_project_as", default="Save As..."),
            self.save_project_as, "secondary", height=26, font_size=11,
        )
        sb.addWidget(self._save_as_btn)

        self._clear_btn = self._mk_btn(t("project.clear_project"), self.clear_project, "danger",  height=30)
        sb.addWidget(self._clear_btn)

        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background:{COLORS['border']};")
        sb.addWidget(sep)

        self._veh_lbl = QLabel(t("project.vehicles_in_project"))
        self._veh_lbl.setFont(font(15, "bold"))
        self._veh_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        sb.addWidget(self._veh_lbl)

        self._project_search = QLineEdit()
        self._project_search.setPlaceholderText(t("common.search_vehicle"))
        self._project_search.setClearButtonEnabled(True)
        self._project_search.setFixedHeight(32)
        self._project_search.setFont(font(13))
        self._project_search.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 10px;
            }}
        """)
        self._project_search.textChanged.connect(self.refresh_project_display)
        sb.addWidget(self._project_search)

        proj_scroll = QScrollArea()
        proj_scroll.setWidgetResizable(True)
        proj_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        proj_scroll.setStyleSheet("""
            QScrollArea{background:transparent;border:none;}
            QScrollArea>QWidget>QWidget{background:transparent;}
        """)
        self._project_overview_frame = QWidget()
        self._project_overview_frame.setStyleSheet("background:transparent;")
        self._proj_layout = QVBoxLayout(self._project_overview_frame)
        self._proj_layout.setContentsMargins(0, 0, 4, 0)
        self._proj_layout.setSpacing(4)
        proj_scroll.setWidget(self._project_overview_frame)
        sb.addWidget(proj_scroll, 1)

        root.addWidget(sidebar)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("""
            QScrollArea{background:transparent;border:none;}
            QScrollArea>QWidget>QWidget{background:transparent;}
        """)
        right_inner = QWidget()
        right_inner.setStyleSheet(f"background:{COLORS['app_bg']};")
        self._right_col = QVBoxLayout(right_inner)
        self._right_col.setContentsMargins(20, 20, 20, 20)
        self._right_col.setSpacing(12)

        self._add_skin_label = QLabel(t("project.add_skins_header"))
        self._add_skin_label.setFont(font(18, "bold"))
        self._add_skin_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._add_skin_label.setVisible(False)
        self._right_col.addWidget(self._add_skin_label)

        self._variant_banner = QLabel("")
        self._variant_banner.setFont(font(12))
        self._variant_banner.setWordWrap(True)
        self._variant_banner.setStyleSheet(f"""
            QLabel {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['accent']};
                border-radius:8px;
                padding:8px 12px;
            }}
        """)
        self._variant_banner.setVisible(False)
        self._right_col.addWidget(self._variant_banner)

        self._skin_card = self._mk_card()
        self._skin_card.setVisible(False)
        self._right_col.addWidget(self._skin_card)
        self._build_skin_form(self._skin_card)

        self._right_col.addStretch()
        right_scroll.setWidget(right_inner)

        right_wrapper = QWidget()
        right_wrapper.setStyleSheet("background:transparent;")
        right_wrap_layout = QVBoxLayout(right_wrapper)
        right_wrap_layout.setContentsMargins(0, 0, 0, 0)
        right_wrap_layout.setSpacing(0)
        right_wrap_layout.addWidget(right_scroll, 1)

        self._btn_row_widget = QWidget()
        self._btn_row_widget.setStyleSheet(f"""
            background:{COLORS['app_bg']};
            border-top:1px solid {COLORS['border']};
        """)
        self._btn_row_widget.setVisible(False)
        btn_row = QHBoxLayout(self._btn_row_widget)
        btn_row.setContentsMargins(20, 10, 20, 10)
        btn_row.setSpacing(8)

        self.add_skin_btn = self._mk_btn(
            t("project.add_skin"), self.add_skin_to_selected_car,
            "primary", height=40, font_size=13
        )
        btn_row.addWidget(self.add_skin_btn, 1)

        self.cancel_edit_btn = self._mk_btn(
            t("project.cancel_edit"), self.cancel_skin_editing,
            "danger", width=100, height=40, font_size=13
        )
        self.cancel_edit_btn.setVisible(False)
        btn_row.addWidget(self.cancel_edit_btn)

        right_wrap_layout.addWidget(self._btn_row_widget)
        root.addWidget(right_wrapper, 1)

        self._build_export_overlay()

    def _build_export_overlay(self):
        self._export_overlay = QFrame(self)
        self._export_overlay.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['frame_bg']};
                border:1px solid {COLORS['accent']};
                border-radius:10px;
            }}
        """)
        self._export_overlay.setFixedWidth(320)
        self._export_overlay.setVisible(False)

        ov_col = QVBoxLayout(self._export_overlay)
        ov_col.setContentsMargins(14, 12, 14, 12)
        ov_col.setSpacing(8)

        self._export_status = QLabel("")
        self._export_status.setFont(font(12, "bold"))
        self._export_status.setWordWrap(True)
        self._export_status.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        ov_col.addWidget(self._export_status)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background:{COLORS['app_bg']};
                border-radius:4px;
                border:none;
            }}
            QProgressBar::chunk {{
                background:{COLORS['accent']};
                border-radius:4px;
            }}
        """)
        ov_col.addWidget(self._progress_bar)

        self._reposition_export_overlay()

    def _reposition_export_overlay(self):
        if not hasattr(self, "_export_overlay"):
            return
        margin = 20
        self._export_overlay.adjustSize()
        x = self.width()  - self._export_overlay.width()  - margin
        y = self.height() - self._export_overlay.height() - margin
        self._export_overlay.move(max(margin, x), max(margin, y))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_export_overlay()


    def _build_skin_form(self, card: QFrame):
        col = QVBoxLayout(card)
        col.setContentsMargins(15, 15, 15, 15)
        col.setSpacing(10)

        hdr_row = QHBoxLayout()
        self._skin_name_lbl = QLabel(t("project.skin_name"))
        self._skin_name_lbl.setFont(font(12, "bold"))
        self._skin_name_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        hdr_row.addWidget(self._skin_name_lbl)
        hdr_row.addStretch()

        self._cfg_lbl = QLabel(t("project.add_config_data"))
        self._cfg_lbl.setFont(font(11, "bold"))
        self._cfg_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        hdr_row.addWidget(self._cfg_lbl)
        self._config_toggle = ToggleSwitch()
        self._config_toggle.stateChanged.connect(self._toggle_config_data)
        hdr_row.addWidget(self._config_toggle)
        col.addLayout(hdr_row)

        entry_row = QHBoxLayout()
        self.skin_name_entry = QLineEdit()
        self.skin_name_entry.setPlaceholderText(t("project.skin_name_placeholder"))
        self.skin_name_entry.setFixedHeight(36)
        self.skin_name_entry.setFont(font(13))
        self.skin_name_entry.setStyleSheet(self._entry_style())
        entry_row.addWidget(self.skin_name_entry)

        self._config_name_lbl = QLabel(t("project.config_name"))
        self._config_name_lbl.setFont(font(12, "bold"))
        self._config_name_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._config_name_lbl.setVisible(False)
        entry_row.addWidget(self._config_name_lbl)

        self._config_name_entry = QLineEdit()
        self._config_name_entry.setPlaceholderText(t("project.config_name_placeholder"))
        self._config_name_entry.setFixedHeight(36)
        self._config_name_entry.setFont(font(13))
        self._config_name_entry.setStyleSheet(self._entry_style())
        self._config_name_entry.setVisible(False)
        entry_row.addWidget(self._config_name_entry)

        self._config_type_lbl = QLabel(t("project.type"))
        self._config_type_lbl.setFont(font(12, "bold"))
        self._config_type_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._config_type_lbl.setVisible(False)
        self._config_type_combo = QComboBox()
        self._config_type_combo.addItems(self.config_types)
        self._config_type_combo.setFixedHeight(36)
        self._config_type_combo.setFont(font(12))
        self._config_type_combo.setStyleSheet(f"""
            QComboBox {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 10px;
            }}
            QComboBox::drop-down {{ border:none; }}
        """)
        self._config_type_combo.setVisible(False)
        entry_row.addWidget(self._config_type_lbl)
        entry_row.addWidget(self._config_type_combo)
        col.addLayout(entry_row)

        self._dds_widget = QWidget()
        self._dds_widget.setStyleSheet("background:transparent;")
        dds_col = QVBoxLayout(self._dds_widget)
        dds_col.setContentsMargins(0, 0, 0, 0)
        dds_col.setSpacing(4)

        self._dds_label_1 = self._mk_label(t("project.dds_texture"), bold=True)
        dds_col.addWidget(self._dds_label_1)
        dds_input = QHBoxLayout()
        self.dds_entry = QLineEdit()
        self.dds_entry.setPlaceholderText(t("common.nofile_selected"))
        self.dds_entry.setReadOnly(True)
        self.dds_entry.setFixedHeight(36)
        self.dds_entry.setFont(font(12))
        self.dds_entry.setStyleSheet(self._entry_style())
        dds_input.addWidget(self.dds_entry)
        self._dds_browse = self._mk_btn(t("common.browse"), self.browse_dds,
                                   "primary", width=100, height=36, font_size=11)
        dds_input.addWidget(self._dds_browse)
        dds_col.addLayout(dds_input)

        self._dds_section_2 = QWidget()
        self._dds_section_2.setStyleSheet("background:transparent;")
        self._dds_section_2.setVisible(False)
        dds_sec2_col = QVBoxLayout(self._dds_section_2)
        dds_sec2_col.setContentsMargins(0, 0, 0, 0)
        dds_sec2_col.setSpacing(4)
        self._dds_label_2 = self._mk_label(t("project.dds_texture_variant_body"), bold=True)
        dds_sec2_col.addWidget(self._dds_label_2)
        dds_input_2 = QHBoxLayout()
        self.dds_entry_2 = QLineEdit()
        self.dds_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self.dds_entry_2.setReadOnly(True)
        self.dds_entry_2.setFixedHeight(36)
        self.dds_entry_2.setFont(font(12))
        self.dds_entry_2.setStyleSheet(self._entry_style())
        dds_input_2.addWidget(self.dds_entry_2)
        self._dds_browse_2 = self._mk_btn(t("common.browse"), self.browse_dds_2,
                                     "primary", width=100, height=36, font_size=11)
        dds_input_2.addWidget(self._dds_browse_2)
        dds_sec2_col.addLayout(dds_input_2)
        dds_col.addWidget(self._dds_section_2)

        self._config_files_widget = QWidget()
        self._config_files_widget.setStyleSheet("background:transparent;")
        self._config_files_widget.setVisible(False)
        cfg_files_col = QVBoxLayout(self._config_files_widget)
        cfg_files_col.setContentsMargins(0, 0, 0, 0)
        cfg_files_col.setSpacing(6)

        cfg_row = QHBoxLayout()

        pc_col = QVBoxLayout()
        self._pc_file_lbl = self._mk_label(t("project.pc_file"), bold=True)
        pc_col.addWidget(self._pc_file_lbl)
        pc_input_row = QHBoxLayout()
        self.pc_file_entry = QLineEdit()
        self.pc_file_entry.setPlaceholderText(t("common.nofile_selected"))
        self.pc_file_entry.setReadOnly(True)
        self.pc_file_entry.setFixedHeight(36)
        self.pc_file_entry.setFont(font(12))
        self.pc_file_entry.setStyleSheet(self._entry_style())
        pc_input_row.addWidget(self.pc_file_entry)
        self._pc_browse = self._mk_btn(t("common.browse"), self._browse_pc_file,
                                  "primary", width=100, height=36, font_size=11)
        pc_input_row.addWidget(self._pc_browse)
        pc_col.addLayout(pc_input_row)
        cfg_row.addLayout(pc_col)

        jpg_col = QVBoxLayout()
        self._jpg_file_lbl = self._mk_label(t("project.jpg_file"), bold=True)
        jpg_col.addWidget(self._jpg_file_lbl)
        jpg_input_row = QHBoxLayout()
        self.jpg_file_entry = QLineEdit()
        self.jpg_file_entry.setPlaceholderText(t("common.nofile_selected"))
        self.jpg_file_entry.setReadOnly(True)
        self.jpg_file_entry.setFixedHeight(36)
        self.jpg_file_entry.setFont(font(12))
        self.jpg_file_entry.setStyleSheet(self._entry_style())
        jpg_input_row.addWidget(self.jpg_file_entry)
        self._jpg_browse = self._mk_btn(t("common.browse"), self._browse_jpg_file,
                                   "primary", width=100, height=36, font_size=11)
        jpg_input_row.addWidget(self._jpg_browse)
        jpg_col.addLayout(jpg_input_row)
        cfg_row.addLayout(jpg_col)

        cfg_files_col.addLayout(cfg_row)

        info_row = QHBoxLayout()
        self._info_lbl = QLabel(t("project.edit_info_data", default="Edit Vehicle Info"))
        self._info_lbl.setFont(font(11, "bold"))
        self._info_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        info_row.addWidget(self._info_lbl)
        self._info_toggle = ToggleSwitch()
        self._info_toggle.stateChanged.connect(self._toggle_info_data)
        info_row.addWidget(self._info_toggle)
        info_row.addStretch()
        cfg_files_col.addLayout(info_row)

        self._info_data_widget = QWidget()
        self._info_data_widget.setStyleSheet(
            f"background:{COLORS.get('sidebar_bg', COLORS['frame_bg'])};border-radius:8px;"
        )
        self._info_data_widget.setVisible(False)
        self._info_data_layout = QVBoxLayout(self._info_data_widget)
        self._info_data_layout.setContentsMargins(10, 10, 10, 10)
        self._info_data_layout.setSpacing(6)
        cfg_files_col.addWidget(self._info_data_widget)

        col.addWidget(self._config_files_widget)

        clr_row = QHBoxLayout()
        self._clr_lbl = QLabel(t("project.colorable"))
        self._clr_lbl.setFont(font(11, "bold"))
        self._clr_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        clr_row.addWidget(self._clr_lbl)
        self._colorable_toggle = ToggleSwitch()
        self._colorable_toggle.stateChanged.connect(self._toggle_colorable)
        clr_row.addWidget(self._colorable_toggle)
        clr_row.addStretch()
        col.addLayout(clr_row)

        col.addWidget(self._dds_widget)

        glow_row = QHBoxLayout()
        self._glow_lbl = QLabel(t("project.glowing_skin"))
        self._glow_lbl.setFont(font(11, "bold"))
        self._glow_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        glow_row.addWidget(self._glow_lbl)
        self._glow_toggle = ToggleSwitch()
        self._glow_toggle.stateChanged.connect(self._toggle_glow)
        glow_row.addWidget(self._glow_toggle)
        glow_row.addStretch()
        self._glow_row_widget = QWidget()
        self._glow_row_widget.setStyleSheet("background:transparent;")
        self._glow_row_widget.setLayout(glow_row)
        self._glow_row_widget.setVisible(False)
        col.addWidget(self._glow_row_widget)

        self._glow_widget = QWidget()
        self._glow_widget.setStyleSheet("background:transparent;")
        self._glow_widget.setVisible(False)
        glow_col = QVBoxLayout(self._glow_widget)
        glow_col.setContentsMargins(0, 0, 0, 4)
        glow_col.setSpacing(4)

        self._emissive_lbl = self._mk_label(t("project.emissive_map"), bold=True)
        glow_col.addWidget(self._emissive_lbl)

        glow_input_row = QHBoxLayout()
        self.emissive_entry = QLineEdit()
        self.emissive_entry.setPlaceholderText(t("common.nofile_selected"))
        self.emissive_entry.setReadOnly(True)
        self.emissive_entry.setFixedHeight(36)
        self.emissive_entry.setFont(font(12))
        self.emissive_entry.setStyleSheet(self._entry_style())
        glow_input_row.addWidget(self.emissive_entry)
        self._emissive_browse = self._mk_btn(
            t("common.browse"), self._browse_emissive_dds,
            "primary", width=100, height=36, font_size=11
        )
        glow_input_row.addWidget(self._emissive_browse)
        glow_col.addLayout(glow_input_row)

        col.addWidget(self._glow_widget)

        self._colorable_widget = QWidget()
        self._colorable_widget.setStyleSheet("background:transparent;")
        self._colorable_widget.setVisible(False)
        clr_col = QVBoxLayout(self._colorable_widget)
        clr_col.setContentsMargins(0, 0, 0, 0)
        clr_col.setSpacing(4)

        self._clr_body1_lbl = QLabel(t("project.normal_body"))
        self._clr_body1_lbl.setFont(font(11, "bold"))
        self._clr_body1_lbl.setStyleSheet(
            f"color:{COLORS['accent']};background:transparent;border:none;"
        )
        self._clr_body1_lbl.setVisible(False)
        clr_col.addWidget(self._clr_body1_lbl)

        self._base_color_map_lbl_1 = self._mk_label(t("project.base_Color_Map"), bold=True)
        clr_col.addWidget(self._base_color_map_lbl_1)
        dm_row = QHBoxLayout()
        self.data_map_entry = QLineEdit()
        self.data_map_entry.setPlaceholderText(t("common.nofile_selected"))
        self.data_map_entry.setReadOnly(True)
        self.data_map_entry.setFixedHeight(36)
        self.data_map_entry.setFont(font(12))
        self.data_map_entry.setStyleSheet(self._entry_style())
        dm_row.addWidget(self.data_map_entry)
        self._dm_browse = self._mk_btn(t("common.browse"), self._browse_data_map,
                                  "primary", width=100, height=36, font_size=11)
        dm_row.addWidget(self._dm_browse)
        clr_col.addLayout(dm_row)

        self._color_palette_map_lbl_1 = self._mk_label(t("project.color_Palette_Map"), bold=True)
        clr_col.addWidget(self._color_palette_map_lbl_1)
        cm_row = QHBoxLayout()
        self.color_map_entry = QLineEdit()
        self.color_map_entry.setPlaceholderText(t("common.nofile_selected"))
        self.color_map_entry.setReadOnly(True)
        self.color_map_entry.setFixedHeight(36)
        self.color_map_entry.setFont(font(12))
        self.color_map_entry.setStyleSheet(self._entry_style())
        cm_row.addWidget(self.color_map_entry)
        self._cm_browse = self._mk_btn(t("common.browse"), self._browse_color_map,
                                  "primary", width=100, height=36, font_size=11)
        cm_row.addWidget(self._cm_browse)
        clr_col.addLayout(cm_row)

        self._clr_body2_section = QWidget()
        self._clr_body2_section.setStyleSheet("background:transparent;")
        self._clr_body2_section.setVisible(False)
        body2_col = QVBoxLayout(self._clr_body2_section)
        body2_col.setContentsMargins(0, 6, 0, 0)
        body2_col.setSpacing(4)

        self._clr_body2_lbl = QLabel(t("project.variant_body"))
        self._clr_body2_lbl.setFont(font(11, "bold"))
        self._clr_body2_lbl.setStyleSheet(
            f"color:{COLORS['accent']};background:transparent;border:none;"
        )
        body2_col.addWidget(self._clr_body2_lbl)

        self._base_color_map_lbl_2 = self._mk_label(t("project.base_Color_Map"), bold=True)
        body2_col.addWidget(self._base_color_map_lbl_2)
        dm2_row = QHBoxLayout()
        self.data_map_entry_2 = QLineEdit()
        self.data_map_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self.data_map_entry_2.setReadOnly(True)
        self.data_map_entry_2.setFixedHeight(36)
        self.data_map_entry_2.setFont(font(12))
        self.data_map_entry_2.setStyleSheet(self._entry_style())
        dm2_row.addWidget(self.data_map_entry_2)
        self._dm2_browse = self._mk_btn(t("common.browse"), self._browse_data_map_2,
                                   "primary", width=100, height=36, font_size=11)
        dm2_row.addWidget(self._dm2_browse)
        body2_col.addLayout(dm2_row)

        self._color_palette_map_lbl_2 = self._mk_label(t("project.color_Palette_Map"), bold=True)
        body2_col.addWidget(self._color_palette_map_lbl_2)
        cm2_row = QHBoxLayout()
        self.color_map_entry_2 = QLineEdit()
        self.color_map_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self.color_map_entry_2.setReadOnly(True)
        self.color_map_entry_2.setFixedHeight(36)
        self.color_map_entry_2.setFont(font(12))
        self.color_map_entry_2.setStyleSheet(self._entry_style())
        cm2_row.addWidget(self.color_map_entry_2)
        self._cm2_browse = self._mk_btn(t("common.browse"), self._browse_color_map_2,
                                   "primary", width=100, height=36, font_size=11)
        cm2_row.addWidget(self._cm2_browse)
        body2_col.addLayout(cm2_row)

        clr_col.addWidget(self._clr_body2_section)
        col.addWidget(self._colorable_widget)

        mat_row = QHBoxLayout()
        self._mat_lbl = QLabel(t("project.edit_materials"))
        self._mat_lbl.setFont(font(11, "bold"))
        self._mat_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        mat_row.addWidget(self._mat_lbl)
        self._material_toggle = ToggleSwitch()
        self._material_toggle.stateChanged.connect(self._toggle_material_properties)
        mat_row.addWidget(self._material_toggle)
        mat_row.addStretch()
        col.addLayout(mat_row)

        self._material_props_widget = QWidget()
        self._material_props_widget.setStyleSheet(
            f"background:{COLORS['card_bg']};border-radius:8px;"
        )
        self._material_props_widget.setVisible(False)
        self._mat_props_layout = QVBoxLayout(self._material_props_widget)
        self._mat_props_layout.setContentsMargins(10, 10, 10, 10)
        self._mat_props_layout.setSpacing(6)
        col.addWidget(self._material_props_widget)

        layers_hdr_row = QHBoxLayout()
        self._layers_lbl = QLabel(t("project.custom_layers"))
        self._layers_lbl.setFont(font(11, "bold"))
        self._layers_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        layers_hdr_row.addWidget(self._layers_lbl)
        layers_hdr_row.addStretch()
        self._add_layer_btn = self._mk_btn(
            t("project.add_new_layer"), self._add_custom_layer,
            "primary", width=140, height=32, font_size=11
        )
        layers_hdr_row.addWidget(self._add_layer_btn)
        col.addLayout(layers_hdr_row)

        self._layers_hint = QLabel(t("project.custom_layers_hint"))
        self._layers_hint.setFont(font(10))
        self._layers_hint.setWordWrap(True)
        self._layers_hint.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
        col.addWidget(self._layers_hint)

        self._layers_limit_lbl = QLabel("")
        self._layers_limit_lbl.setFont(font(10))
        self._layers_limit_lbl.setWordWrap(True)
        self._layers_limit_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
        col.addWidget(self._layers_limit_lbl)

        self._layers_container = QWidget()
        self._layers_container.setStyleSheet("background:transparent;")
        self._layers_layout = QVBoxLayout(self._layers_container)
        self._layers_layout.setContentsMargins(0, 4, 0, 4)
        self._layers_layout.setSpacing(8)
        col.addWidget(self._layers_container)

        _prev_style = "background:transparent;border:none;"
        self._dds_preview = QLabel()
        self._dds_preview.setAlignment(Qt.AlignCenter)
        self._dds_preview.setStyleSheet(_prev_style)
        self._dds_preview.setFixedHeight(210)
        self._dds_preview.setWordWrap(True)
        self._dds_preview.setVisible(False)
        col.addWidget(self._dds_preview)

        self._color_map_preview = QLabel()
        self._color_map_preview.setAlignment(Qt.AlignCenter)
        self._color_map_preview.setStyleSheet(_prev_style)
        self._color_map_preview.setFixedHeight(210)
        self._color_map_preview.setWordWrap(True)
        self._color_map_preview.setVisible(False)
        col.addWidget(self._color_map_preview)

        self._dds_preview_2 = QLabel()
        self._dds_preview_2.setAlignment(Qt.AlignCenter)
        self._dds_preview_2.setStyleSheet(_prev_style)
        self._dds_preview_2.setFixedHeight(210)
        self._dds_preview_2.setWordWrap(True)
        self._dds_preview_2.setVisible(False)
        col.addWidget(self._dds_preview_2)

        self._color_map_preview_2 = QLabel()
        self._color_map_preview_2.setAlignment(Qt.AlignCenter)
        self._color_map_preview_2.setStyleSheet(_prev_style)
        self._color_map_preview_2.setFixedHeight(210)
        self._color_map_preview_2.setWordWrap(True)
        self._color_map_preview_2.setVisible(False)
        col.addWidget(self._color_map_preview_2)


    def refresh_project_display(self):
        while self._proj_layout.count():
            item = self._proj_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide(); w.setParent(None); w.deleteLater()

        try:
            search_query = self._project_search.text().lower().strip()
        except Exception as exc:
            print(f"[DEBUG] refresh_project_display: failed to read search box, defaulting to empty: {exc}")
            search_query = ""

        if not self.project_data["cars"]:
            print("[DEBUG] refresh_project_display: no cars in project — showing empty-state label")
            lbl = QLabel(t("project.add_from_sidebar"))
            lbl.setFont(font(13))
            lbl.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;border:none;"
            )
            lbl.setAlignment(Qt.AlignCenter)
            self._proj_layout.addWidget(lbl)
            self._proj_layout.addStretch()
            self._project_overview_frame.adjustSize()
            return

        filtered = {}
        for car_id, car_info in self.project_data["cars"].items():
            base = car_info.get("base_carid", car_id)
            name = self._car_display_name(base, car_id)
            if not search_query or (search_query in name.lower() or
                                     search_query in base.lower()):
                filtered[car_id] = car_info

        print(f"[DEBUG] refresh_project_display: query={search_query!r} "
              f"matched={len(filtered)}/{len(self.project_data['cars'])} cars")

        if not filtered:
            lbl = QLabel(t("project.no_cars_match", query=search_query))
            lbl.setFont(font(13))
            lbl.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;border:none;"
            )
            lbl.setAlignment(Qt.AlignCenter)
            self._proj_layout.addWidget(lbl)
            self._proj_layout.addStretch()
            self._project_overview_frame.adjustSize()
            return

        for car_id, car_info in filtered.items():
            self._proj_layout.addWidget(self._build_car_row(car_id, car_info))

        self._proj_layout.addStretch()
        self._project_overview_frame.adjustSize()

    def _build_car_row(self, car_id: str, car_info: dict) -> QWidget:
        base    = car_info.get("base_carid", car_id)
        name    = self._car_display_name(base, car_id)
        is_selected = (car_id == self.selected_car_for_skin)
        is_expanded = (car_id == self.expanded_car_id)

        container = QFrame()
        container.setStyleSheet("background:transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        skin_count     = len(car_info["skins"])
        variant_suffix = car_info.get("variant_suffix", "")

        try:
            from core.config import is_rebadge_suffix
        except ImportError as _exc:
            print(f"[WARNING] _build_car_row: {type(_exc).__name__}: {_exc}")
            def is_rebadge_suffix(_c, _s):
                return False
        is_rebadge = bool(variant_suffix) and is_rebadge_suffix(base, variant_suffix)
        show_variant_row = bool(variant_suffix) and not is_rebadge

        if is_rebadge:
            base_name = car_info.get("display_name") or name
        else:
            base_name = name
            if variant_suffix:
                suffix_marker = f" ({variant_suffix.capitalize()})"
                if base_name.endswith(suffix_marker):
                    base_name = base_name[: -len(suffix_marker)]

        display_text  = base_name
        skin_word     = t("project.skin") if skin_count == 1 else t("project.skins")
        display_text += f"  •  {skin_count} {skin_word}"


        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        acc   = COLORS["accent"]      if is_selected else COLORS["card_bg"]
        acc_h = COLORS["accent_hover"] if is_selected else COLORS["card_hover"]
        txt   = COLORS["accent_text"]  if is_selected else COLORS["text"]

        car_btn = QPushButton()
        car_btn.setCursor(Qt.PointingHandCursor)
        car_btn.setStyleSheet(f"""
            QPushButton {{
                background:{acc};color:{txt};
                border-radius:8px;border:1px solid {COLORS['border']};
                text-align:left;
            }}
            QPushButton:hover {{ background:{acc_h}; }}
            QPushButton:disabled {{
                background:{COLORS['border']};color:{COLORS['text_muted']};
                border-color:{COLORS['border']};
            }}
        """)
        car_btn.clicked.connect(lambda checked=False, c=car_id:
                                 self._toggle_car_expansion(c))

        btn_lbl_col = QVBoxLayout(car_btn)
        btn_lbl_col.setContentsMargins(10, 4, 10, 4)
        btn_lbl_col.setSpacing(0)

        main_lbl = QLabel(display_text)
        main_lbl.setFont(font(13, "bold"))
        main_lbl.setStyleSheet(f"""
            QLabel {{ color:{txt};background:transparent;border:none; }}
            QLabel:disabled {{ color:{COLORS['text_muted']}; }}
        """)
        main_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        btn_lbl_col.addWidget(main_lbl)

        if show_variant_row:
            suffix_display = variant_suffix.capitalize()
            sub_lbl = QLabel(t("project.variant_type",
                               default=f"Type: {suffix_display}",
                               suffix=suffix_display))
            sub_lbl.setFont(font(10, "bold"))
            sub_txt = COLORS["accent_text"] if is_selected else COLORS["text_secondary"]
            sub_lbl.setStyleSheet(f"""
                QLabel {{ color:{sub_txt};background:transparent;border:none; }}
                QLabel:disabled {{ color:{COLORS['text_muted']}; }}
            """)
            sub_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            btn_lbl_col.addWidget(sub_lbl)
            car_btn.setFixedHeight(50)
        else:
            car_btn.setFixedHeight(38)

        btn_row.addWidget(car_btn, 1)

        rem_btn = QPushButton("✕")
        rem_btn.setFixedSize(30, 30)
        rem_btn.setCursor(Qt.PointingHandCursor)
        rem_btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['error']};color:white;
                border-radius:6px;border:none;font-weight:bold;
            }}
            QPushButton:hover {{ background:{COLORS.get('error_hover','#c0392b')}; }}
            QPushButton:disabled {{
                background:{COLORS['border']};color:{COLORS['text_muted']};
            }}
        """)
        rem_btn.clicked.connect(lambda checked=False, c=car_id:
                                 self.remove_car_from_project(c))
        btn_row.addWidget(rem_btn)
        col.addLayout(btn_row)

        if is_expanded and car_info["skins"]:
            skins_frame = QFrame()
            skins_frame.setStyleSheet(f"""
                QFrame {{
                    background:{COLORS['app_bg']};
                    border-radius:6px;
                    border:1px solid {COLORS['border']};
                }}
            """)
            sf_col = QVBoxLayout(skins_frame)
            sf_col.setContentsMargins(6, 4, 6, 6)
            sf_col.setSpacing(4)

            hdr = QLabel(t("project.skins_header"))
            hdr.setFont(font(10, "bold"))
            hdr.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;border:none;"
            )
            sf_col.addWidget(hdr)

            for i, skin in enumerate(car_info["skins"]):
                sf_col.addWidget(self._build_skin_row(car_id, i, skin))

            col.addWidget(skins_frame)

        return container

    def _build_skin_row(self, car_id: str, idx: int, skin: dict) -> QFrame:
        is_editing = (self.editing_mode and
                      self.selected_skin_index == idx and
                      self.selected_car_for_skin == car_id)
        has_config = "config_data" in skin
        row_bg = COLORS["accent"] if is_editing else COLORS["card_bg"]
        row_h  = 75 if has_config else 38

        f = QFrame()
        f.setFixedHeight(row_h)
        f.setCursor(Qt.PointingHandCursor)
        f.setStyleSheet(f"QFrame {{ background:{row_bg};border-radius:6px; }}")
        f.mousePressEvent = lambda e, c=car_id, i=idx: \
            QTimer.singleShot(0, lambda: self.select_skin_for_editing(c, i))

        row = QHBoxLayout(f)
        row.setContentsMargins(8, 4, 6, 4)
        row.setSpacing(6)

        icon = QLabel("✏️" if is_editing else "🎨")
        icon.setFont(font(14))
        icon.setStyleSheet("background:transparent;")
        row.addWidget(icon)

        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        txt_c = COLORS["accent_text"] if is_editing else COLORS["text"]
        n_lbl = QLabel(f"{idx + 1}. {skin['name']}")
        n_lbl.setFont(font(12, "bold"))
        n_lbl.setStyleSheet(f"color:{txt_c};background:transparent;border:none;")
        info_col.addWidget(n_lbl)

        if has_config:
            cd = skin["config_data"]
            for text in [f"{t('project.config_type_label')}: {cd.get('config_type','')}",
                         f"{t('project.config_name_label')}: {cd.get('config_name','')}"]:
                l = QLabel(text)
                l.setFont(font(10))
                sub_c = COLORS["accent_text"] if is_editing else COLORS["text_secondary"]
                l.setStyleSheet(f"color:{sub_c};background:transparent;border:none;")
                info_col.addWidget(l)

        row.addLayout(info_col, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(28, 28)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['error']};color:white;
                border-radius:6px;border:none;font-weight:bold;
            }}
        """)
        del_btn.clicked.connect(lambda checked=False, c=car_id, i=idx:
                                  self.remove_skin_from_car(c, i))
        row.addWidget(del_btn)
        return f

    def _car_display_name(self, base_carid: str, car_id: str = "") -> str:
        for cid, cname in self.car_id_list:
            if cid == base_carid:
                _, v = _split_project_key(car_id)
                if v:
                    return f"{cname} ({v.capitalize()})"
                return cname
        name = state.vehicle_ids.get(base_carid, base_carid)
        _, v = _split_project_key(car_id)
        if v:
            return f"{name} ({v.capitalize()})"
        return name


    def add_car_to_project(self, carid: str, display_name: str, variant_suffix: str = ""):
        print(f"[DEBUG] add_car_to_project: {carid!r} variant={variant_suffix!r}")
        project_key = _make_project_key(carid, variant_suffix)

        if project_key in self.project_data["cars"]:
            self.show_notification(
                f"{display_name} {t('project.notification.already_in_project')}",
                "warning"
            )
            self.select_car_for_skin(project_key)
            return

        self.project_data["cars"][project_key] = {
            "base_carid":     carid,
            "variant_suffix": variant_suffix,
            "display_name":   display_name,
            "skins":          [],
        }
        self._mark_dirty()
        self.show_notification(
            t("project.notification.added_car").format(display_name=display_name)
        )
        self.select_car_for_skin(project_key)
        self.refresh_project_display()

    def remove_car_from_project(self, car_id: str):
        print(f"[DEBUG] remove_car_from_project: {car_id!r}")
        if car_id not in self.project_data["cars"]:
            return
        base    = self.project_data["cars"][car_id].get("base_carid", car_id)
        variant = self.project_data["cars"][car_id].get("variant_suffix", "")
        dname   = self.project_data["cars"][car_id].get("display_name") \
                  or self._car_display_name(base, car_id)
        del self.project_data["cars"][car_id]
        self._mark_dirty()

        if not self.project_data["cars"] and self._current_project_path:
            print("[DEBUG] remove_car_from_project: all vehicles removed from a loaded project — flagging for save confirmation")
            self._project_emptied_since_load = True

        if self.selected_car_for_skin == car_id:
            self.selected_car_for_skin = None
            self._skin_card.setVisible(False)
            self._add_skin_label.setVisible(False)
            self._variant_banner.setVisible(False)
            self._btn_row_widget.setVisible(False)
        self.show_notification(
            t("project.notification.removed_car").format(display_name=dname), "info"
        )
        self.refresh_project_display()

        try:
            mw = self.window()
            if mw and hasattr(mw, "sidebar"):
                mw.sidebar.restore_vehicle(base, variant)
        except Exception as e:
            print(f"[WARNING] sidebar.restore_vehicle failed: {e}")

    def _toggle_car_expansion(self, car_id: str):
        was_expanded = self.expanded_car_id == car_id
        self.expanded_car_id = None if was_expanded else car_id
        print(f"[DEBUG] _toggle_car_expansion: {car_id!r} {'collapsed' if was_expanded else 'expanded'}")
        if self.expanded_car_id:
            self.select_car_for_skin(car_id)
        self.refresh_project_display()

    def select_car_for_skin(self, car_id: str):
        print(f"[DEBUG] select_car_for_skin: {car_id!r}")
        if car_id not in self.project_data["cars"]:
            return
        if self.editing_mode and self.selected_car_for_skin != car_id:
            self.editing_mode        = False
            self.selected_skin_index = None
            self._update_button_ui()

        self.selected_car_for_skin = car_id
        self._add_skin_label.setVisible(True)
        self._skin_card.setVisible(True)
        self._btn_row_widget.setVisible(True)

        info    = self.project_data["cars"][car_id]
        variant = info.get("variant_suffix", "")
        base    = info.get("base_carid", car_id)
        dname   = info.get("display_name", self._car_display_name(base, car_id))
        try:
            from core.config import is_single_layer_variant
        except ImportError:
            print("[DEBUG] select_car_for_skin: core.config.is_single_layer_variant not available — assuming double layer")
            def is_single_layer_variant(_c, _s): return False
        needs_double = bool(variant) and not is_single_layer_variant(base, variant)
        if needs_double:
            is_colorable = self._colorable_toggle.isChecked()
            requirements = t("project.variant_4_pngs") if is_colorable else t("project.variant_2_dds")
            self._variant_banner.setText(
                t("project.variant_banner", name=dname, requirements=requirements, variant=variant)
            )
            self._variant_banner.setVisible(True)
        else:
            self._variant_banner.setVisible(False)

        if not self.editing_mode:
            self._reset_skin_form_fields()

        self._update_variant_ui()
        self.refresh_project_display()

    def _update_variant_ui(self):
        is_var  = self._needs_double_layer()
        is_clr  = self._colorable_toggle.isChecked()
        print(f"[DEBUG] _update_variant_ui: is_var={is_var} is_colorable={is_clr}")

        v_suffix = self._selected_variant_suffix()
        self._dds_label_1.setText(
            t("project.dds_texture_normal_body") if is_var else t("project.dds_texture")
        )
        self._dds_section_2.setVisible(is_var and not is_clr)

        self._clr_body1_lbl.setVisible(is_var and is_clr)
        self._clr_body2_section.setVisible(is_var and is_clr)

        if is_var:
            self._clr_body2_lbl.setText(t("project.variant_body_named", variant=v_suffix.capitalize()))

        if not is_var:
            self._dds_preview_2.setVisible(False)
            self._dds_preview_2.clear()
            self._color_map_preview_2.setVisible(False)
            self._color_map_preview_2.clear()

        if is_var and self._variant_banner.isVisible():
            requirements = t("project.variant_4_pngs") if is_clr else t("project.variant_2_dds")
            info  = self.project_data["cars"].get(self.selected_car_for_skin, {})
            dname = info.get("display_name", "")
            self._variant_banner.setText(
                t("project.variant_banner", name=dname, requirements=requirements, variant=v_suffix)
            )

        if self._custom_layer_cards and any(c["is_var"] != is_var for c in self._custom_layer_cards):
            print(f"[DEBUG] _update_variant_ui: is_var changed under existing layer cards — rebuilding "
                  f"{len(self._custom_layer_cards)} custom layer card(s)")
            existing = self._collect_custom_layers()
            self._clear_custom_layers_ui()
            for layer in existing:
                self._add_custom_layer(layer)
        self._refresh_layers_limit_label()


    def add_skin_to_selected_car(self):
        print(f"[DEBUG] add_skin_to_selected_car: editing_mode={self.editing_mode} "
              f"selected_car={self.selected_car_for_skin!r}")
        if self.editing_mode and self.selected_skin_index is not None:
            print("[DEBUG] add_skin_to_selected_car: delegating to update_skin() (editing existing skin)")
            self.update_skin()
            return

        if not self.selected_car_for_skin:
            print("[DEBUG] add_skin_to_selected_car: aborted — no car selected")
            self.show_notification(t("project.notification.select_car"), "warning")
            return

        skin_name = self.skin_name_entry.text().strip()
        if not skin_name:
            print("[DEBUG] add_skin_to_selected_car: aborted — skin name is empty")
            self.show_notification(
                t("project.notification.please_skin_name"), "warning"
            )
            return

        _bad = _find_illegal_chars(skin_name)
        if _bad:
            print(f"[DEBUG] add_skin_to_selected_car: aborted — illegal chars in skin name {skin_name!r}: {_bad}")
            self.show_notification(
                f"Skin name contains invalid character(s): {' '.join(_bad)}\n"
                f'Avoid: \\ / : * ? " < > |',
                "error", 6000,
            )
            return

        is_colorable = self._colorable_toggle.isChecked()
        is_var       = self._needs_double_layer()
        print(f"[DEBUG] add_skin_to_selected_car: skin_name={skin_name!r} is_colorable={is_colorable} is_var={is_var}")

        if is_colorable:
            if not self._data_map_path:
                print("[DEBUG] add_skin_to_selected_car: aborted — missing data map (colorable)")
                self.show_notification(
                    t("project.notification.please_select_datamap"), "warning"
                )
                return
            if not self._color_map_path:
                print("[DEBUG] add_skin_to_selected_car: aborted — missing color map (colorable)")
                self.show_notification(
                    t("project.notification.please_select_colormap"), "warning"
                )
                return
            if is_var:
                if not self._data_map_path_2:
                    print("[DEBUG] add_skin_to_selected_car: aborted — missing variant data map")
                    self.show_notification(
                        t("project.notification.please_select_datamap_variant"), "warning"
                    )
                    return
                if not self._color_map_path_2:
                    print("[DEBUG] add_skin_to_selected_car: aborted — missing variant color map")
                    self.show_notification(
                        t("project.notification.please_select_colormap_variant"), "warning"
                    )
                    return
            skin_data = {
                "name":            skin_name,
                "is_colorable":    True,
                "data_map_path":   self._data_map_path,
                "color_map_path":  self._color_map_path,
            }
            if is_var:
                skin_data["data_map_path_2"]  = self._data_map_path_2
                skin_data["color_map_path_2"] = self._color_map_path_2
        else:
            if not self._dds_path:
                print("[DEBUG] add_skin_to_selected_car: aborted — missing DDS texture")
                self.show_notification(
                    t("project.notification.please_select_dds"), "warning"
                )
                return
            if is_var and not self._dds_path_2:
                print("[DEBUG] add_skin_to_selected_car: aborted — missing variant DDS texture")
                self.show_notification(
                    t("project.notification.please_select_dds_variant"), "warning"
                )
                return
            skin_data = {
                "name":         skin_name,
                "is_colorable": False,
                "dds_path":     self._dds_path,
            }
            if is_var:
                skin_data["dds_path_2"] = self._dds_path_2

        if self._config_toggle.isChecked():
            config_name = self._config_name_entry.text().strip()
            if not config_name:
                print("[DEBUG] add_skin_to_selected_car: aborted — config enabled but name is empty")
                self.show_notification(
                    t("project.notification.please_config_name"), "warning"
                )
                return
            if not self._pc_file_path:
                print("[DEBUG] add_skin_to_selected_car: aborted — config enabled but missing .pc file")
                self.show_notification(
                    t("project.notification.please_select_pc"), "warning"
                )
                return
            if not self._jpg_file_path:
                print("[DEBUG] add_skin_to_selected_car: aborted — config enabled but missing .jpg file")
                self.show_notification(
                    t("project.notification.please_select_jpg"), "warning"
                )
                return
            skin_data["config_data"] = {
                "config_type":   self._config_type_combo.currentText(),
                "config_name":   config_name,
                "pc_file_path":  self._pc_file_path,
                "jpg_file_path": self._jpg_file_path,
            }
            if self._info_toggle.isChecked():
                info_data = self._collect_info_data()
                if info_data:
                    skin_data["config_data"]["info_data"] = info_data

        if self._material_toggle.isChecked():
            mat = self._collect_material_properties()
            if mat:
                skin_data["material_properties"] = mat

        if self._custom_layer_cards:
            if not self._validate_custom_layers():
                print("[DEBUG] add_skin_to_selected_car: aborted — custom layer validation failed")
                return
            skin_data["custom_layers"] = self._collect_custom_layers()
            print(f"[DEBUG] add_skin_to_selected_car: attached {len(skin_data['custom_layers'])} custom layer(s)")

        if self._glow_toggle.isChecked():
            if not self._emissive_dds_path:
                print("[DEBUG] add_skin_to_selected_car: aborted — glow enabled but missing emissive map")
                self.show_notification(
                    "Please select an Emissive Map (.dds) for the glow effect.",
                    "warning",
                )
                return
            skin_data["emissive_dds_path"] = self._emissive_dds_path

        self.project_data["cars"][self.selected_car_for_skin]["skins"].append(skin_data)
        self._mark_dirty()
        print(f"[DEBUG] add_skin_to_selected_car: skin {skin_name!r} added to {self.selected_car_for_skin!r}")
        if state.testing_mode and len(self.project_data["cars"]) > 1:
            print(f"[DEBUG] add_skin_to_selected_car: testing_mode broadcast starting "
                  f"({len(self.project_data['cars']) - 1} other car(s) in project)")
            broadcast_count = 0
            for car_key, car_info in self.project_data["cars"].items():
                if car_key == self.selected_car_for_skin:
                    continue
                target_suffix = car_info.get("variant_suffix", "")
                target_base   = car_info.get("base_carid", car_key)
                try:
                    from core.config import is_single_layer_variant
                except ImportError:
                    print("[DEBUG] add_skin_to_selected_car: core.config.is_single_layer_variant not available — assuming double layer")
                    def is_single_layer_variant(_c, _s): return False
                target_is_variant = bool(target_suffix) and not is_single_layer_variant(target_base, target_suffix)
                broadcast_skin = dict(skin_data)
                if target_is_variant:
                    if broadcast_skin.get("is_colorable"):
                        if not broadcast_skin.get("data_map_path_2"):
                            broadcast_skin["data_map_path_2"] = broadcast_skin.get("data_map_path", "")
                        if not broadcast_skin.get("color_map_path_2"):
                            broadcast_skin["color_map_path_2"] = broadcast_skin.get("color_map_path", "")
                    else:
                        if not broadcast_skin.get("dds_path_2"):
                            broadcast_skin["dds_path_2"] = broadcast_skin.get("dds_path", "")
                    if broadcast_skin.get("custom_layers"):
                        mirrored_layers = []
                        for layer in broadcast_skin["custom_layers"]:
                            layer = dict(layer)
                            if layer.get("is_colorable"):
                                if not layer.get("data_map_path_2"):
                                    layer["data_map_path_2"] = layer.get("data_map_path", "")
                                if not layer.get("color_map_path_2"):
                                    layer["color_map_path_2"] = layer.get("color_map_path", "")
                            else:
                                if not layer.get("dds_path_2"):
                                    layer["dds_path_2"] = layer.get("dds_path", "")
                            if layer.get("opacity_map_path") and not layer.get("opacity_map_path_2"):
                                layer["opacity_map_path_2"] = layer["opacity_map_path"]
                            if layer.get("normal_map_path") and not layer.get("normal_map_path_2"):
                                layer["normal_map_path_2"] = layer["normal_map_path"]
                            if layer.get("glowing") and layer.get("emissive_dds_path") and not layer.get("emissive_dds_path_2"):
                                layer["emissive_dds_path_2"] = layer["emissive_dds_path"]
                            mirrored_layers.append(layer)
                        broadcast_skin["custom_layers"] = mirrored_layers
                else:
                    broadcast_skin.pop("dds_path_2",       None)
                    broadcast_skin.pop("data_map_path_2",  None)
                    broadcast_skin.pop("color_map_path_2", None)
                    if broadcast_skin.get("custom_layers"):
                        stripped_layers = []
                        for layer in broadcast_skin["custom_layers"]:
                            layer = dict(layer)
                            for k in ("data_map_path_2", "color_map_path_2", "dds_path_2",
                                      "opacity_map_path_2", "normal_map_path_2", "emissive_dds_path_2"):
                                layer.pop(k, None)
                            stripped_layers.append(layer)
                        broadcast_skin["custom_layers"] = stripped_layers
                existing_names = {s.get("name") for s in car_info["skins"]}
                if broadcast_skin["name"] not in existing_names:
                    car_info["skins"].append(broadcast_skin)
                    broadcast_count += 1
                else:
                    print(f"[DEBUG] add_skin_to_selected_car: skipped broadcast to {car_key!r} — "
                          f"skin name {skin_name!r} already exists there")
            print(f"[DEBUG] add_skin_to_selected_car: testing_mode broadcast finished — "
                  f"applied to {broadcast_count} other vehicle(s)")
            if broadcast_count:
                self.show_notification(
                    f"[Testing] Skin '{skin_name}' also applied to "
                    f"{broadcast_count} other vehicle(s) in project.",
                    "info", 3500,
                )

        self.show_notification(
            f"{t('project.notification.added_skin')}'{skin_name}'", "success"
        )
        self._reset_skin_form_fields()
        current = self.selected_car_for_skin
        self.selected_car_for_skin = None
        self.refresh_project_display()
        QTimer.singleShot(50, lambda: self._reselect_car(current))

    def _reselect_car(self, car_id: Optional[str]):
        if car_id:
            print(f"[DEBUG] _reselect_car: re-selecting {car_id!r} after add/edit")
            self.selected_car_for_skin = car_id
            self.refresh_project_display()

    def remove_skin_from_car(self, car_id: str, skin_idx: int):
        if car_id in self.project_data["cars"]:
            skins = self.project_data["cars"][car_id]["skins"]
            if 0 <= skin_idx < len(skins):
                name = skins[skin_idx]["name"]
                print(f"[DEBUG] remove_skin_from_car: removing skin {name!r} (idx {skin_idx}) from {car_id!r}")
                del skins[skin_idx]
                self._mark_dirty()
                self.show_notification(
                    f"{t('project.notification.removed_skin')} '{name}'", "info"
                )
                self.refresh_project_display()
            else:
                print(f"[DEBUG] remove_skin_from_car: skin_idx {skin_idx} out of range for {car_id!r} "
                      f"({len(skins)} skins)")
        else:
            print(f"[DEBUG] remove_skin_from_car: {car_id!r} not found in project")

    def select_skin_for_editing(self, car_id: str, skin_idx: int):
        if car_id not in self.project_data["cars"]:
            print(f"[DEBUG] select_skin_for_editing: {car_id!r} not found in project")
            return
        skins = self.project_data["cars"][car_id]["skins"]
        if not (0 <= skin_idx < len(skins)):
            print(f"[DEBUG] select_skin_for_editing: skin_idx {skin_idx} out of range for {car_id!r} "
                  f"({len(skins)} skins)")
            return

        print(f"[DEBUG] select_skin_for_editing: editing skin idx {skin_idx} of {car_id!r}")
        self.selected_car_for_skin = car_id
        self.selected_skin_index   = skin_idx
        self.editing_mode          = True
        self._update_button_ui()

        skin = skins[skin_idx]
        self.skin_name_entry.setText(skin["name"])

        is_colorable = skin.get("is_colorable", False)
        self._colorable_toggle.setChecked(is_colorable)
        self._toggle_colorable()

        if is_colorable:
            self._data_map_path  = skin.get("data_map_path",  "")
            self._color_map_path = skin.get("color_map_path", "")
            self.data_map_entry.setText(os.path.basename(self._data_map_path))
            self.color_map_entry.setText(os.path.basename(self._color_map_path))
            self._load_preview(self._data_map_path,  self._dds_preview)
            self._load_preview(self._color_map_path, self._color_map_preview)
            self._data_map_path_2  = skin.get("data_map_path_2",  "")
            self._color_map_path_2 = skin.get("color_map_path_2", "")
            self.data_map_entry_2.setText(os.path.basename(self._data_map_path_2))
            self.color_map_entry_2.setText(os.path.basename(self._color_map_path_2))
            if self._data_map_path_2:
                self._load_preview(self._data_map_path_2, self._dds_preview_2)
            if self._color_map_path_2:
                self._load_preview(self._color_map_path_2, self._color_map_preview_2)
        else:
            self._dds_path = skin.get("dds_path", "")
            self.dds_entry.setText(os.path.basename(self._dds_path))
            self._load_preview(self._dds_path, self._dds_preview)
            self._dds_path_2 = skin.get("dds_path_2", "")
            self.dds_entry_2.setText(os.path.basename(self._dds_path_2))
            if self._dds_path_2:
                self._load_preview(self._dds_path_2, self._dds_preview_2)

        if "config_data" in skin:
            cd = skin["config_data"]
            self._config_toggle.setChecked(True)
            self._toggle_config_data()
            idx = self._config_type_combo.findText(cd.get("config_type", ""))
            if idx >= 0:
                self._config_type_combo.setCurrentIndex(idx)
            self._config_name_entry.setText(cd.get("config_name", ""))
            self._pc_file_path  = cd.get("pc_file_path",  "")
            self._jpg_file_path = cd.get("jpg_file_path", "")
            self.pc_file_entry.setText(os.path.basename(self._pc_file_path))
            self.jpg_file_entry.setText(os.path.basename(self._jpg_file_path))
            if "info_data" in cd:
                self._info_toggle.setChecked(True)
                self._toggle_info_data()
                self._load_info_data_into_ui(cd["info_data"])
            else:
                self._info_toggle.setChecked(False)
                self._toggle_info_data()
        else:
            self._config_toggle.setChecked(False)
            self._toggle_config_data()
            self._info_toggle.setChecked(False)
            self._toggle_info_data()

        if "material_properties" in skin:
            self._material_toggle.setChecked(True)
            self._toggle_material_properties()
            self._load_material_properties_into_ui(skin["material_properties"])
        else:
            self._material_toggle.setChecked(False)
            self._toggle_material_properties()

        self._clear_custom_layers_ui()
        layers = list(skin.get("custom_layers", []))

        if "retro_rough_met_path" in skin or "retro_mask_path" in skin:
            print("[DEBUG] Converting legacy retro_rough_met/mask fields into a custom layer")
            legacy_layer = self._new_custom_layer_defaults()
            legacy_layer["is_colorable"]    = False
            legacy_layer["dds_path"]        = skin.get("retro_rough_met_path", "")
            legacy_layer["dds_path_2"]      = skin.get("retro_rough_met_path_2", "")
            legacy_layer["opacity_map_path"]   = skin.get("retro_mask_path", "")
            legacy_layer["opacity_map_path_2"] = skin.get("retro_mask_path_2", "")
            legacy_layer["retroreflectivity"] = 1.0
            legacy_layer["metallic_factor"] = 0.899999976
            legacy_layer["roughness_factor"] = 0.5
            layers.append(legacy_layer)
        elif "rough_met_path" in skin:
            print("[DEBUG] Converting legacy rough_met field into a custom layer")
            legacy_layer = self._new_custom_layer_defaults()
            legacy_layer["is_colorable"] = False
            legacy_layer["dds_path"]     = skin.get("rough_met_path", "")
            legacy_layer["dds_path_2"]   = skin.get("rough_met_path_2", "")
            legacy_layer["metallic_factor"]  = 0.95
            legacy_layer["roughness_factor"] = 0.7
            legacy_layer["clear_coat_roughness_factor"] = 0.03
            layers.append(legacy_layer)

        for layer in layers:
            self._add_custom_layer(layer)

        if "emissive_dds_path" in skin:
            self._glow_toggle.setChecked(True)
            self._toggle_glow()
            self._emissive_dds_path = skin["emissive_dds_path"]
            self.emissive_entry.setText(os.path.basename(self._emissive_dds_path))
        else:
            self._glow_toggle.setChecked(False)
            self._toggle_glow()

        self._add_skin_label.setVisible(True)
        self._skin_card.setVisible(True)
        self._update_variant_ui()
        self.refresh_project_display()
        self.show_notification(t("project.notification.editing_skin", name=skin["name"]), "info")

    def update_skin(self):
        if not self.editing_mode or self.selected_skin_index is None:
            print("[DEBUG] update_skin: aborted — not in editing mode or no skin index selected")
            return
        if self.selected_car_for_skin not in self.project_data["cars"]:
            print(f"[DEBUG] update_skin: aborted — {self.selected_car_for_skin!r} no longer in project, cancelling edit")
            self.cancel_skin_editing()
            return

        skin_name    = self.skin_name_entry.text().strip()
        is_colorable = self._colorable_toggle.isChecked()
        is_var       = self._needs_double_layer()
        print(f"[DEBUG] update_skin: car={self.selected_car_for_skin!r} idx={self.selected_skin_index} "
              f"skin_name={skin_name!r} is_colorable={is_colorable} is_var={is_var}")

        if not skin_name:
            print("[DEBUG] update_skin: aborted — skin name is empty")
            self.show_notification(t("project.notification.skin_name_required"), "error")
            return

        _bad = _find_illegal_chars(skin_name)
        if _bad:
            print(f"[DEBUG] update_skin: aborted — illegal chars in skin name {skin_name!r}: {_bad}")
            self.show_notification(
                f"Skin name contains invalid character(s): {' '.join(_bad)}\n"
                f'Avoid: \\ / : * ? " < > |',
                "error", 6000,
            )
            return

        skins = self.project_data["cars"][self.selected_car_for_skin]["skins"]
        skin  = skins[self.selected_skin_index]
        skin["name"]         = skin_name
        skin["is_colorable"] = is_colorable

        if is_colorable:
            skin["data_map_path"]  = self._data_map_path
            skin["color_map_path"] = self._color_map_path
            skin.pop("dds_path",   None)
            skin.pop("dds_path_2", None)
            if is_var:
                skin["data_map_path_2"]  = self._data_map_path_2
                skin["color_map_path_2"] = self._color_map_path_2
            else:
                skin.pop("data_map_path_2",  None)
                skin.pop("color_map_path_2", None)
        else:
            skin["dds_path"] = self._dds_path
            skin.pop("data_map_path",   None)
            skin.pop("color_map_path",  None)
            skin.pop("data_map_path_2", None)
            skin.pop("color_map_path_2",None)
            if is_var:
                skin["dds_path_2"] = self._dds_path_2
            else:
                skin.pop("dds_path_2", None)

        if self._config_toggle.isChecked():
            skin["config_data"] = {
                "config_type":   self._config_type_combo.currentText(),
                "config_name":   self._config_name_entry.text().strip(),
                "pc_file_path":  self._pc_file_path,
                "jpg_file_path": self._jpg_file_path,
            }
            if self._info_toggle.isChecked():
                info_data = self._collect_info_data()
                if info_data:
                    skin["config_data"]["info_data"] = info_data
        else:
            skin.pop("config_data", None)

        if self._material_toggle.isChecked():
            mat = self._collect_material_properties()
            if mat:
                skin["material_properties"] = mat
        else:
            skin.pop("material_properties", None)

        if self._custom_layer_cards:
            if not self._validate_custom_layers():
                print("[DEBUG] update_skin: aborted — custom layer validation failed")
                return
            skin["custom_layers"] = self._collect_custom_layers()
            print(f"[DEBUG] update_skin: attached {len(skin['custom_layers'])} custom layer(s)")
        else:
            skin.pop("custom_layers", None)
        skin.pop("rough_met_path", None)
        skin.pop("rough_met_path_2", None)
        skin.pop("retro_rough_met_path", None)
        skin.pop("retro_rough_met_path_2", None)
        skin.pop("retro_mask_path", None)
        skin.pop("retro_mask_path_2", None)

        if self._glow_toggle.isChecked():
            if not self._emissive_dds_path:
                print("[DEBUG] update_skin: aborted — glow enabled but missing emissive map")
                self.show_notification(
                    "Please select an Emissive Map (.dds) for the glow effect.",
                    "warning",
                )
                return
            skin["emissive_dds_path"] = self._emissive_dds_path
        else:
            skin.pop("emissive_dds_path", None)

        self._mark_dirty()
        print(f"[DEBUG] update_skin: saved changes to skin {skin_name!r}")
        self.show_notification(t("project.notification.updated_skin", name=skin_name), "success")
        self.cancel_skin_editing()

    def cancel_skin_editing(self):
        print("[DEBUG] cancel_skin_editing: exiting edit mode")
        self.editing_mode        = False
        self.selected_skin_index = None
        self._update_button_ui()
        self._reset_skin_form_fields()
        self.refresh_project_display()

    def _update_button_ui(self):
        if self.editing_mode:
            self.add_skin_btn.setText(t("project.update_skin"))
            self.cancel_edit_btn.setVisible(True)
        else:
            self.add_skin_btn.setText(t("project.add_skin"))
            self.cancel_edit_btn.setVisible(False)

    def _reset_skin_form_fields(self):
        print("[DEBUG] _reset_skin_form_fields: clearing skin form")
        for widget, attr in [
            (self.skin_name_entry,    None),
            (self.dds_entry,          None),
            (self.dds_entry_2,        None),
            (self.pc_file_entry,      None),
            (self.jpg_file_entry,     None),
            (self.data_map_entry,     None),
            (self.color_map_entry,    None),
            (self.data_map_entry_2,   None),
            (self.color_map_entry_2,  None),
            (self._config_name_entry, None),
            (self.emissive_entry,     None),
        ]:
            try:
                widget.clear()
            except Exception as exc:
                print(f"[DEBUG] _reset_skin_form_fields: failed to clear widget {widget!r}: {exc}")

        self._dds_path        = ""
        self._dds_path_2      = ""
        self._data_map_path   = ""
        self._color_map_path  = ""
        self._data_map_path_2 = ""
        self._color_map_path_2= ""
        self._pc_file_path    = ""
        self._jpg_file_path   = ""
        self._emissive_dds_path = ""

        try:
            self._dds_preview.setVisible(False)
            self._dds_preview.clear()
        except Exception as exc:
            print(f"[DEBUG] _reset_skin_form_fields: failed to clear dds_preview: {exc}")
        try:
            self._color_map_preview.setVisible(False)
            self._color_map_preview.clear()
        except Exception as exc:
            print(f"[DEBUG] _reset_skin_form_fields: failed to clear color_map_preview: {exc}")
        try:
            self._dds_preview_2.setVisible(False)
            self._dds_preview_2.clear()
        except Exception as exc:
            print(f"[DEBUG] _reset_skin_form_fields: failed to clear dds_preview_2: {exc}")
        try:
            self._color_map_preview_2.setVisible(False)
            self._color_map_preview_2.clear()
        except Exception as exc:
            print(f"[DEBUG] _reset_skin_form_fields: failed to clear color_map_preview_2: {exc}")

        for toggle in (self._colorable_toggle, self._config_toggle, self._material_toggle, self._glow_toggle, self._info_toggle):
            try:
                toggle.blockSignals(True)
                toggle.setChecked(False)
                toggle.blockSignals(False)
            except Exception as exc:
                print(f"[DEBUG] _reset_skin_form_fields: failed to reset toggle {toggle!r}: {exc}")

        self._toggle_colorable()
        self._toggle_config_data()
        self._toggle_material_properties()
        self._clear_custom_layers_ui()
        self._toggle_glow()
        self._toggle_info_data()
        self._update_variant_ui()

        self._clear_layout(self._mat_props_layout)
        self.material_properties_entries.clear()

        self._clear_layout(self._info_data_layout)
        self.info_data_entries.clear()
        self._info_field_originals.clear()


    def browse_dds(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_dds"), "", "DDS files (*.dds);;All files (*.*)"
        )
        if path:
            print(f"[DEBUG] browse_dds: selected {path!r}")
            self._dds_path = path
            self.dds_entry.setText(os.path.basename(path))
            self._load_preview(path, self._dds_preview)
        else:
            print("[DEBUG] browse_dds: dialog cancelled")

    def browse_dds_2(self):
        v_suffix = self._selected_variant_suffix()
        title = t("project.dialog_select_dds_variant", variant=v_suffix.capitalize())
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "DDS files (*.dds);;All files (*.*)"
        )
        if path:
            print(f"[DEBUG] browse_dds_2: selected {path!r}")
            self._dds_path_2 = path
            self.dds_entry_2.setText(os.path.basename(path))
            self._load_preview(path, self._dds_preview_2)
        else:
            print("[DEBUG] browse_dds_2: dialog cancelled")

    def _get_vehicle_browse_dir(self) -> str:
        mods_path = _get_mods_folder_path()
        print(f"[DEBUG] _get_vehicle_browse_dir: mods_path={mods_path!r}")
        if not mods_path or not os.path.isdir(mods_path):
            return ""

        parent       = os.path.dirname(mods_path)
        vehicles_dir = os.path.join(parent, "vehicles")
        print(f"[DEBUG] _get_vehicle_browse_dir: vehicles_dir={vehicles_dir!r}  exists={os.path.isdir(vehicles_dir)}")

        base_carid = ""
        if self.selected_car_for_skin:
            car_info   = self.project_data["cars"].get(self.selected_car_for_skin, {})
            base_carid = car_info.get("base_carid", "") or _split_project_key(self.selected_car_for_skin)[0]
        print(f"[DEBUG] _get_vehicle_browse_dir: selected={self.selected_car_for_skin!r}  base_carid={base_carid!r}")

        if base_carid:
            vehicle_dir = os.path.join(vehicles_dir, base_carid)
            print(f"[DEBUG] _get_vehicle_browse_dir: vehicle_dir={vehicle_dir!r}  exists={os.path.isdir(vehicle_dir)}")
            if os.path.isdir(vehicle_dir):
                return vehicle_dir

        if os.path.isdir(vehicles_dir):
            return vehicles_dir

        return mods_path

    def _browse_pc_file(self):
        init_dir = self._get_vehicle_browse_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_pc"), init_dir, "PC files (*.pc);;All files (*.*)"
        )
        if path:
            print(f"[DEBUG] _browse_pc_file: selected {path!r}")
            self._pc_file_path = path
            self.pc_file_entry.setText(os.path.basename(path))
        else:
            print("[DEBUG] _browse_pc_file: dialog cancelled")

    def _browse_jpg_file(self):
        init_dir = self._get_vehicle_browse_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_jpg"), init_dir,
            "JPG files (*.jpg);;JPEG files (*.jpeg);;All files (*.*)"
        )
        if path:
            print(f"[DEBUG] _browse_jpg_file: selected {path!r}")
            self._jpg_file_path = path
            self.jpg_file_entry.setText(os.path.basename(path))
        else:
            print("[DEBUG] _browse_jpg_file: dialog cancelled")

    def _browse_data_map(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_base_color_map"), "", "PNG files (*.png);;All files (*.*)"
        )
        if path:
            print(f"[DEBUG] _browse_data_map: selected {path!r}")
            self._data_map_path = path
            self.data_map_entry.setText(os.path.basename(path))
            self._load_preview(path, self._dds_preview)
        else:
            print("[DEBUG] _browse_data_map: dialog cancelled")

    def _browse_color_map(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_color_palette"), "", "PNG files (*.png);;All files (*.*)"
        )
        if path:
            print(f"[DEBUG] _browse_color_map: selected {path!r}")
            self._color_map_path = path
            self.color_map_entry.setText(os.path.basename(path))
            self._load_preview(path, self._color_map_preview)
        else:
            print("[DEBUG] _browse_color_map: dialog cancelled")

    def _browse_data_map_2(self):
        v_suffix = self._selected_variant_suffix()
        title = t("project.dialog_select_base_color_map_v", variant=v_suffix.capitalize())
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "PNG files (*.png);;All files (*.*)"
        )
        if path:
            print(f"[DEBUG] _browse_data_map_2: selected {path!r}")
            self._data_map_path_2 = path
            self.data_map_entry_2.setText(os.path.basename(path))
            self._load_preview(path, self._dds_preview_2)
        else:
            print("[DEBUG] _browse_data_map_2: dialog cancelled")

    def _browse_color_map_2(self):
        v_suffix = self._selected_variant_suffix()
        title = t("project.dialog_select_color_palette_v", variant=v_suffix.capitalize())
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "PNG files (*.png);;All files (*.*)"
        )
        if path:
            print(f"[DEBUG] _browse_color_map_2: selected {path!r}")
            self._color_map_path_2 = path
            self.color_map_entry_2.setText(os.path.basename(path))
            self._load_preview(path, self._color_map_preview_2)
        else:
            print("[DEBUG] _browse_color_map_2: dialog cancelled")

    def _load_preview(self, path: str, label: QLabel):
        print(f"[DEBUG] _load_preview: loading {path!r}")
        label.setVisible(False)
        label.clear()
        if not path:
            return
        if not os.path.exists(path):
            label.setText(f"⚠  File not found:\n{os.path.basename(path)}")
            label.setStyleSheet(
                f"color:{COLORS.get('error','#e74c3c')};"
                "background:transparent;border:none;"
            )
            label.setAlignment(Qt.AlignCenter)
            label.setVisible(True)
            return
        if not getattr(state, 'texture_previews_enabled', True):
            label.setText(f"📄  {os.path.basename(path)}")
            label.setStyleSheet(
                f"color:{COLORS['text_secondary']};"
                "background:transparent;border:none;"
            )
            label.setAlignment(Qt.AlignCenter)
            label.setVisible(True)
            return
        px = _load_pixmap_robust(path)
        if px and not px.isNull():
            label.setPixmap(px)
            label.setStyleSheet("background:transparent;border:none;")
            label.setToolTip(path)
        else:
            label.setText(f"📄  {os.path.basename(path)}")
            label.setStyleSheet(
                f"color:{COLORS['text_secondary']};"
                "background:transparent;border:none;"
            )
            label.setAlignment(Qt.AlignCenter)
        label.setVisible(True)


    def _toggle_config_data(self):
        on = self._config_toggle.isChecked()
        print(f"[DEBUG] _toggle_config_data: {on}")
        self._config_name_lbl.setVisible(on)
        self._config_name_entry.setVisible(on)
        self._config_type_lbl.setVisible(on)
        self._config_type_combo.setVisible(on)
        self._config_files_widget.setVisible(on)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
                continue
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)

    def _toggle_info_data(self):
        on = self._info_toggle.isChecked()
        print(f"[DEBUG] _toggle_info_data: {on}")
        if on:
            if not self.selected_car_for_skin:
                print("[DEBUG] _toggle_info_data: aborted — no car selected")
                self.show_notification(t("project.notification.select_car_first"), "warning")
                self._info_toggle.setChecked(False)
                return
            car_info = self.project_data["cars"][self.selected_car_for_skin]
            base = car_info.get("base_carid", self.selected_car_for_skin)
            variant_suffix = car_info.get("variant_suffix", "")
            fields = self._load_info_template_fields(base, variant_suffix)
            fields = {k: v for k, v in fields.items()
                      if k not in ("Config Type", "Configuration")}
            if not fields:
                print(f"[DEBUG] _toggle_info_data: aborted — no editable info fields for base={base!r} variant={variant_suffix!r}")
                self.show_notification(
                    t("project.notification.no_info_fields",
                      default="No editable info fields found for this vehicle."),
                    "warning"
                )
                self._info_toggle.setChecked(False)
                return
            print(f"[DEBUG] _toggle_info_data: populating {len(fields)} field(s) for base={base!r}")
            self._populate_info_data_ui(fields)
        self._info_data_widget.setVisible(on)

    def _populate_info_data_ui(self, fields: Dict[str, Any]):
        self._clear_layout(self._info_data_layout)
        self.info_data_entries.clear()
        self._info_field_originals = dict(fields)

        hdr = self._mk_label(t("project.info_data", default="Vehicle Info"), bold=True)
        self._info_data_layout.addWidget(hdr)

        hint = QLabel(t("project.info_data_hint",
                         default="Leave a field blank to keep the template's default value."))
        hint.setFont(font(10))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
        self._info_data_layout.addWidget(hint)

        fields_grid = QHBoxLayout()
        fields_grid.setSpacing(8)
        col_count = 0
        desc_fields: Dict[str, Any] = {}
        for key, value in fields.items():
            if key.strip().lower() == "description":
                desc_fields[key] = value
                continue

            fcol = QVBoxLayout()
            lbl = QLabel(key)
            lbl.setFont(font(9))
            lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
            fcol.addWidget(lbl)

            entry = QLineEdit()
            entry.setPlaceholderText("" if value is None else str(value))
            entry.setFixedHeight(30)
            entry.setFont(font(11))
            entry.setStyleSheet(self._entry_style())
            fcol.addWidget(entry)

            fields_grid.addLayout(fcol)
            col_count += 1
            self.info_data_entries[key] = entry

            if col_count == 4:
                self._info_data_layout.addLayout(fields_grid)
                fields_grid = QHBoxLayout()
                fields_grid.setSpacing(8)
                col_count = 0

        if col_count:
            fields_grid.addStretch()
            self._info_data_layout.addLayout(fields_grid)

        for key, value in desc_fields.items():
            dcol = QVBoxLayout()
            dcol.setContentsMargins(0, 6, 0, 0)
            dlbl = QLabel(key)
            dlbl.setFont(font(9))
            dlbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
            dcol.addWidget(dlbl)

            dentry = QLineEdit()
            dentry.setPlaceholderText("" if value is None else str(value))
            dentry.setFixedHeight(36)
            dentry.setFont(font(11))
            dentry.setStyleSheet(self._entry_style())
            dcol.addWidget(dentry)

            self._info_data_layout.addLayout(dcol)
            self.info_data_entries[key] = dentry

    def _collect_info_data(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, widget in self.info_data_entries.items():
            val = widget.text().strip()
            if not val:
                continue
            orig = self._info_field_originals.get(key)
            if isinstance(orig, (int, float)) and not isinstance(orig, bool):
                try:
                    num = float(val)
                    if isinstance(orig, int) and "." not in val:
                        result[key] = int(num)
                    else:
                        result[key] = num
                except ValueError:
                    print(f"[DEBUG] _collect_info_data: invalid numeric value for {key!r}: {val!r} — ignoring")
                    self.show_notification(
                        t("project.notification.invalid_info_value",
                          default=f"'{key}' must be a number — ignoring '{val}'.",
                          field=key, value=val),
                        "warning"
                    )
                    continue
            else:
                result[key] = val
        print(f"[DEBUG] _collect_info_data: collected {len(result)} field(s)")
        return result

    def _load_info_data_into_ui(self, info_data: Dict[str, Any]):
        applied = 0
        for key, val in info_data.items():
            if key in self.info_data_entries:
                self.info_data_entries[key].setText(str(val))
                applied += 1
        print(f"[DEBUG] _load_info_data_into_ui: applied {applied}/{len(info_data)} field(s)")

    def _toggle_colorable(self):
        on      = self._colorable_toggle.isChecked()
        print(f"[DEBUG] _toggle_colorable: {on}")
        self._dds_widget.setVisible(not on)
        self._colorable_widget.setVisible(on)
        if not on:
            self._color_map_preview.setVisible(False)
            self._color_map_preview.clear()
        self._update_variant_ui()

    def _toggle_glow(self):
        on = self._glow_toggle.isChecked()
        print(f"[DEBUG] _toggle_glow: {on}")
        self._glow_widget.setVisible(on)
        if not on:
            self._emissive_dds_path = ""
            self.emissive_entry.clear()

    def _browse_emissive_dds(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("project.dialog_select_emissive"),
            "",
            "DDS files (*.dds);;All files (*.*)",
        )
        if path:
            print(f"[DEBUG] _browse_emissive_dds: selected {path!r}")
            self._emissive_dds_path = path
            self.emissive_entry.setText(os.path.basename(path))
        else:
            print("[DEBUG] _browse_emissive_dds: dialog cancelled")


    def _max_new_layers(self) -> int:
        try:
            from core.file_ops import get_max_custom_layers
        except ImportError:
            print("[DEBUG] _max_new_layers: core.file_ops.get_max_custom_layers not available")
            get_max_custom_layers = None

        if not self.selected_car_for_skin or not get_max_custom_layers:
            fallback = max(0, 4 - 2 - len(self._custom_layer_cards))
            print(f"[DEBUG] _max_new_layers: using permissive fallback={fallback} "
                  f"(selected_car={self.selected_car_for_skin!r}, get_max_custom_layers={'available' if get_max_custom_layers else 'missing'})")
            return fallback

        car_info = self.project_data["cars"].get(self.selected_car_for_skin, {})
        base = car_info.get("base_carid", self.selected_car_for_skin)
        variant_suffix = car_info.get("variant_suffix", "")
        try:
            from core.settings import get_vehicles_dir, get_bundle_path
            roots = [get_vehicles_dir(), os.path.join(get_bundle_path(), "vehicles")]
        except ImportError:
            print("[DEBUG] _max_new_layers: core.settings vehicle dirs not available — using cwd/vehicles")
            roots = [os.path.join(os.getcwd(), "vehicles")]

        template_dir = None
        target = f"skinname{variant_suffix.lower()}" if variant_suffix else "skinname"
        for root in roots:
            vp = os.path.join(root, base)
            if os.path.isdir(vp):
                for entry in os.listdir(vp):
                    if entry.lower() == target and os.path.isdir(os.path.join(vp, entry)):
                        template_dir = os.path.join(vp, entry)
                        break
            if template_dir:
                break

        if not template_dir:
            fallback = max(0, 4 - 2 - len(self._custom_layer_cards))
            print(f"[DEBUG] _max_new_layers: template dir not found for base={base!r} "
                  f"variant={variant_suffix!r} — using permissive fallback={fallback}")
            return fallback

        existing_cap = get_max_custom_layers(template_dir)
        result = max(0, existing_cap - len(self._custom_layer_cards))
        print(f"[DEBUG] _max_new_layers: template={template_dir!r} cap={existing_cap} "
              f"used={len(self._custom_layer_cards)} -> remaining={result}")
        return result

    def _refresh_layers_limit_label(self):
        remaining = self._max_new_layers()
        used      = len(self._custom_layer_cards)
        self._layers_limit_lbl.setText(
            t("project.custom_layers_remaining", used=used, remaining=remaining)
        )
        self._add_layer_btn.setEnabled(remaining > 0)

    def _add_custom_layer(self, layer_data: Optional[Dict[str, Any]] = None):
        if layer_data is None and self._max_new_layers() <= 0:
            print("[DEBUG] _add_custom_layer: aborted — layer limit reached")
            self.show_notification(t("project.notification.layer_limit_reached"), "warning")
            return

        layer_data = layer_data or self._new_custom_layer_defaults()
        card = self._build_layer_card(layer_data)
        self._custom_layer_cards.append(card)
        self._layers_layout.addWidget(card["frame"])
        self._renumber_layer_cards()
        self._refresh_layers_limit_label()
        print(f"[DEBUG] _add_custom_layer: added layer card #{len(self._custom_layer_cards)}")

    def _new_custom_layer_defaults(self) -> Dict[str, Any]:
        return {
            "is_colorable": False,
            "data_map_path": "", "color_map_path": "",
            "data_map_path_2": "", "color_map_path_2": "",
            "dds_path": "", "dds_path_2": "",
            "roughness_map_path": "", "roughness_map_path_2": "",
            "metallic_map_path": "", "metallic_map_path_2": "",
            "opacity_map_path": "", "opacity_map_path_2": "",
            "normal_map_path": "", "normal_map_path_2": "",
            "retroreflectivity": 0.0,
            "glowing": False,
            "emissive_dds_path": "", "emissive_dds_path_2": "",
            "metallic_factor": 0.0,
            "roughness_factor": 0.45,
            "clear_coat_factor": 0.4,
            "clear_coat_roughness_factor": 0.1,
        }

    def _remove_custom_layer(self, card: Dict[str, Any]):
        if card in self._custom_layer_cards:
            self._custom_layer_cards.remove(card)
        card["frame"].deleteLater()
        self._renumber_layer_cards()
        self._refresh_layers_limit_label()
        print(f"[DEBUG] _remove_custom_layer: removed layer card, {len(self._custom_layer_cards)} remaining")

    def _renumber_layer_cards(self):
        for idx, card in enumerate(self._custom_layer_cards):
            card["title_lbl"].setText(t("project.layer_n", n=idx + 1))

    def _clear_custom_layers_ui(self):
        print(f"[DEBUG] _clear_custom_layers_ui: clearing {len(self._custom_layer_cards)} layer card(s)")
        while self._layers_layout.count():
            item = self._layers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._custom_layer_cards.clear()
        self._refresh_layers_limit_label()

    def _build_layer_card(self, layer_data: Dict[str, Any]) -> Dict[str, Any]:
        is_var = self._needs_double_layer()
        v_suffix = self._selected_variant_suffix()

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{COLORS.get('sidebar_bg', COLORS['frame_bg'])};"
            "border-radius:8px;}}"
        )
        fc = QVBoxLayout(frame)
        fc.setContentsMargins(10, 10, 10, 10)
        fc.setSpacing(6)

        card: Dict[str, Any] = {"frame": frame, "is_var": is_var}

        hdr_row = QHBoxLayout()
        title_lbl = QLabel(t("project.layer_n", n=len(self._custom_layer_cards) + 1))
        title_lbl.setFont(font(12, "bold"))
        title_lbl.setStyleSheet(f"color:{COLORS['accent']};background:transparent;border:none;")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()
        remove_btn = self._mk_btn(t("common.remove"), lambda: self._remove_custom_layer(card),
                                   "danger", width=80, height=28, font_size=10)
        hdr_row.addWidget(remove_btn)
        fc.addLayout(hdr_row)
        card["title_lbl"] = title_lbl

        clr_row = QHBoxLayout()
        clr_lbl = QLabel(t("project.colorable"))
        clr_lbl.setFont(font(10, "bold"))
        clr_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        clr_row.addWidget(clr_lbl)
        clr_toggle = ToggleSwitch()
        clr_toggle.setChecked(bool(layer_data.get("is_colorable", False)))
        clr_row.addWidget(clr_toggle)
        clr_row.addStretch()
        fc.addLayout(clr_row)
        card["colorable_toggle"] = clr_toggle

        opt_row = QHBoxLayout()

        glow_widget = QWidget()
        glow_widget.setVisible(False)
        glow_widget.setStyleSheet("background:transparent;")
        glow_col = QVBoxLayout(glow_widget)
        glow_col.setContentsMargins(0, 0, 0, 0)
        glow_lbl = QLabel(t("project.glowing_skin"))
        glow_lbl.setFont(font(9))
        glow_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
        glow_col.addWidget(glow_lbl)
        glow_toggle = ToggleSwitch()
        glow_toggle.setChecked(bool(layer_data.get("glowing", False)))
        glow_col.addWidget(glow_toggle)
        opt_row.addWidget(glow_widget)

        opt_row.addStretch()
        fc.addLayout(opt_row)
        card.update(glow_toggle=glow_toggle)

        dds_widget = QWidget(); dds_widget.setStyleSheet("background:transparent;")
        dds_col = QVBoxLayout(dds_widget); dds_col.setContentsMargins(0, 0, 0, 0); dds_col.setSpacing(4)
        dds_lbl = self._mk_label(t("project.base_color_map_dds"), bold=True)
        dds_col.addWidget(dds_lbl)
        dds_entry = QLineEdit(); dds_entry.setPlaceholderText(t("common.nofile_selected"))
        dds_entry.setReadOnly(True); dds_entry.setFixedHeight(32); dds_entry.setFont(font(11))
        dds_entry.setStyleSheet(self._entry_style())
        dds_row = QHBoxLayout(); dds_row.addWidget(dds_entry)
        dds_browse = self._mk_btn(t("common.browse"),
                                   lambda: self._browse_layer_file(card, "dds_path", dds_entry, "dds"),
                                   "primary", width=90, height=32, font_size=10)
        dds_row.addWidget(dds_browse)
        dds_col.addLayout(dds_row)

        dds_widget_2 = QWidget(); dds_widget_2.setStyleSheet("background:transparent;")
        dds_widget_2.setVisible(is_var)
        dds2_col = QVBoxLayout(dds_widget_2); dds2_col.setContentsMargins(0, 4, 0, 0); dds2_col.setSpacing(4)
        dds2_lbl = QLabel(t("project.variant_body_named", variant=v_suffix.capitalize()) if is_var else "")
        dds2_lbl.setFont(font(10, "bold"))
        dds2_lbl.setStyleSheet(f"color:{COLORS['accent']};background:transparent;border:none;")
        dds2_col.addWidget(dds2_lbl)
        dds_entry_2 = QLineEdit(); dds_entry_2.setPlaceholderText(t("common.nofile_selected"))
        dds_entry_2.setReadOnly(True); dds_entry_2.setFixedHeight(32); dds_entry_2.setFont(font(11))
        dds_entry_2.setStyleSheet(self._entry_style())
        dds_row_2 = QHBoxLayout(); dds_row_2.addWidget(dds_entry_2)
        dds_browse_2 = self._mk_btn(t("common.browse"),
                                     lambda: self._browse_layer_file(card, "dds_path_2", dds_entry_2, "dds"),
                                     "primary", width=90, height=32, font_size=10)
        dds_row_2.addWidget(dds_browse_2)
        dds2_col.addLayout(dds_row_2)
        dds_col.addWidget(dds_widget_2)

        rm_lbl = self._mk_label(t("project.roughness_map"), bold=True)
        dds_col.addWidget(rm_lbl)
        rm_entry = QLineEdit(); rm_entry.setPlaceholderText(t("common.nofile_selected"))
        rm_entry.setReadOnly(True); rm_entry.setFixedHeight(32); rm_entry.setFont(font(11))
        rm_entry.setStyleSheet(self._entry_style())
        rm_row = QHBoxLayout(); rm_row.addWidget(rm_entry)
        rm_browse = self._mk_btn(t("common.browse"),
                                  lambda: self._browse_layer_file(card, "roughness_map_path", rm_entry, "png"),
                                  "primary", width=90, height=32, font_size=10)
        rm_row.addWidget(rm_browse)
        dds_col.addLayout(rm_row)

        rm_widget_2 = QWidget(); rm_widget_2.setStyleSheet("background:transparent;")
        rm_widget_2.setVisible(is_var)
        rm2_col = QVBoxLayout(rm_widget_2); rm2_col.setContentsMargins(0, 4, 0, 0); rm2_col.setSpacing(4)
        rm2_entry = QLineEdit(); rm2_entry.setPlaceholderText(
            t("project.variant_body_named", variant=v_suffix.capitalize()) if is_var else t("common.nofile_selected")
        )
        rm2_entry.setReadOnly(True); rm2_entry.setFixedHeight(32); rm2_entry.setFont(font(11))
        rm2_entry.setStyleSheet(self._entry_style())
        rm2_row = QHBoxLayout(); rm2_row.addWidget(rm2_entry)
        rm2_browse = self._mk_btn(t("common.browse"),
                                   lambda: self._browse_layer_file(card, "roughness_map_path_2", rm2_entry, "png"),
                                   "primary", width=90, height=32, font_size=10)
        rm2_row.addWidget(rm2_browse)
        rm2_col.addLayout(rm2_row)
        dds_col.addWidget(rm_widget_2)

        mm_lbl = self._mk_label(t("project.metallic_map"), bold=True)
        dds_col.addWidget(mm_lbl)
        mm_entry = QLineEdit(); mm_entry.setPlaceholderText(t("common.nofile_selected"))
        mm_entry.setReadOnly(True); mm_entry.setFixedHeight(32); mm_entry.setFont(font(11))
        mm_entry.setStyleSheet(self._entry_style())
        mm_row = QHBoxLayout(); mm_row.addWidget(mm_entry)
        mm_browse = self._mk_btn(t("common.browse"),
                                  lambda: self._browse_layer_file(card, "metallic_map_path", mm_entry, "png"),
                                  "primary", width=90, height=32, font_size=10)
        mm_row.addWidget(mm_browse)
        dds_col.addLayout(mm_row)

        mm_widget_2 = QWidget(); mm_widget_2.setStyleSheet("background:transparent;")
        mm_widget_2.setVisible(is_var)
        mm2_col = QVBoxLayout(mm_widget_2); mm2_col.setContentsMargins(0, 4, 0, 0); mm2_col.setSpacing(4)
        mm2_entry = QLineEdit(); mm2_entry.setPlaceholderText(
            t("project.variant_body_named", variant=v_suffix.capitalize()) if is_var else t("common.nofile_selected")
        )
        mm2_entry.setReadOnly(True); mm2_entry.setFixedHeight(32); mm2_entry.setFont(font(11))
        mm2_entry.setStyleSheet(self._entry_style())
        mm2_row = QHBoxLayout(); mm2_row.addWidget(mm2_entry)
        mm2_browse = self._mk_btn(t("common.browse"),
                                   lambda: self._browse_layer_file(card, "metallic_map_path_2", mm2_entry, "png"),
                                   "primary", width=90, height=32, font_size=10)
        mm2_row.addWidget(mm2_browse)
        mm2_col.addLayout(mm2_row)
        dds_col.addWidget(mm_widget_2)

        fc.addWidget(dds_widget)
        card.update(dds_entry=dds_entry, dds_entry_2=dds_entry_2, dds_widget=dds_widget, dds_widget_2=dds_widget_2)
        card["dds_lbl"] = dds_lbl
        card.update(
            rm_entry=rm_entry, rm_entry_2=rm2_entry, rm_widget_2=rm_widget_2,
            mm_entry=mm_entry, mm_entry_2=mm2_entry, mm_widget_2=mm_widget_2,
        )

        clr_widget = QWidget(); clr_widget.setStyleSheet("background:transparent;")
        clrw_col = QVBoxLayout(clr_widget); clrw_col.setContentsMargins(0, 0, 0, 0); clrw_col.setSpacing(4)

        dm_lbl = self._mk_label(t("project.base_Color_Map"), bold=True)
        clrw_col.addWidget(dm_lbl)
        dm_entry = QLineEdit(); dm_entry.setPlaceholderText(t("common.nofile_selected"))
        dm_entry.setReadOnly(True); dm_entry.setFixedHeight(32); dm_entry.setFont(font(11))
        dm_entry.setStyleSheet(self._entry_style())
        dm_row = QHBoxLayout(); dm_row.addWidget(dm_entry)
        dm_browse = self._mk_btn(t("common.browse"),
                                  lambda: self._browse_layer_file(card, "data_map_path", dm_entry, "png"),
                                  "primary", width=90, height=32, font_size=10)
        dm_row.addWidget(dm_browse)
        clrw_col.addLayout(dm_row)

        pm_lbl = self._mk_label(t("project.color_Palette_Map"), bold=True)
        clrw_col.addWidget(pm_lbl)
        pm_entry = QLineEdit(); pm_entry.setPlaceholderText(t("common.nofile_selected"))
        pm_entry.setReadOnly(True); pm_entry.setFixedHeight(32); pm_entry.setFont(font(11))
        pm_entry.setStyleSheet(self._entry_style())
        pm_row = QHBoxLayout(); pm_row.addWidget(pm_entry)
        pm_browse = self._mk_btn(t("common.browse"),
                                  lambda: self._browse_layer_file(card, "color_map_path", pm_entry, "png"),
                                  "primary", width=90, height=32, font_size=10)
        pm_row.addWidget(pm_browse)
        clrw_col.addLayout(pm_row)

        rm_clr_lbl = self._mk_label(t("project.roughness_map"), bold=True)
        clrw_col.addWidget(rm_clr_lbl)
        rm_clr_entry = QLineEdit(); rm_clr_entry.setPlaceholderText(t("common.nofile_selected"))
        rm_clr_entry.setReadOnly(True); rm_clr_entry.setFixedHeight(32); rm_clr_entry.setFont(font(11))
        rm_clr_entry.setStyleSheet(self._entry_style())
        rm_clr_row = QHBoxLayout(); rm_clr_row.addWidget(rm_clr_entry)
        rm_clr_browse = self._mk_btn(t("common.browse"),
                                      lambda: self._browse_layer_file(card, "roughness_map_path_clr", rm_clr_entry, "png"),
                                      "primary", width=90, height=32, font_size=10)
        rm_clr_row.addWidget(rm_clr_browse)
        clrw_col.addLayout(rm_clr_row)

        mm_clr_lbl = self._mk_label(t("project.metallic_map"), bold=True)
        clrw_col.addWidget(mm_clr_lbl)
        mm_clr_entry = QLineEdit(); mm_clr_entry.setPlaceholderText(t("common.nofile_selected"))
        mm_clr_entry.setReadOnly(True); mm_clr_entry.setFixedHeight(32); mm_clr_entry.setFont(font(11))
        mm_clr_entry.setStyleSheet(self._entry_style())
        mm_clr_row = QHBoxLayout(); mm_clr_row.addWidget(mm_clr_entry)
        mm_clr_browse = self._mk_btn(t("common.browse"),
                                      lambda: self._browse_layer_file(card, "metallic_map_path_clr", mm_clr_entry, "png"),
                                      "primary", width=90, height=32, font_size=10)
        mm_clr_row.addWidget(mm_clr_browse)
        clrw_col.addLayout(mm_clr_row)

        clr_widget_2 = QWidget(); clr_widget_2.setStyleSheet("background:transparent;")
        clr_widget_2.setVisible(is_var)
        clr2_col = QVBoxLayout(clr_widget_2); clr2_col.setContentsMargins(0, 6, 0, 0); clr2_col.setSpacing(4)
        clr2_lbl = QLabel(t("project.variant_body_named", variant=v_suffix.capitalize()) if is_var else "")
        clr2_lbl.setFont(font(10, "bold"))
        clr2_lbl.setStyleSheet(f"color:{COLORS['accent']};background:transparent;border:none;")
        clr2_col.addWidget(clr2_lbl)

        dm2_entry = QLineEdit(); dm2_entry.setPlaceholderText(t("common.nofile_selected"))
        dm2_entry.setReadOnly(True); dm2_entry.setFixedHeight(32); dm2_entry.setFont(font(11))
        dm2_entry.setStyleSheet(self._entry_style())
        dm2_row = QHBoxLayout(); dm2_row.addWidget(dm2_entry)
        dm2_browse = self._mk_btn(t("common.browse"),
                                   lambda: self._browse_layer_file(card, "data_map_path_2", dm2_entry, "png"),
                                   "primary", width=90, height=32, font_size=10)
        dm2_row.addWidget(dm2_browse)
        clr2_col.addLayout(dm2_row)

        pm2_entry = QLineEdit(); pm2_entry.setPlaceholderText(t("common.nofile_selected"))
        pm2_entry.setReadOnly(True); pm2_entry.setFixedHeight(32); pm2_entry.setFont(font(11))
        pm2_entry.setStyleSheet(self._entry_style())
        pm2_row = QHBoxLayout(); pm2_row.addWidget(pm2_entry)
        pm2_browse = self._mk_btn(t("common.browse"),
                                   lambda: self._browse_layer_file(card, "color_map_path_2", pm2_entry, "png"),
                                   "primary", width=90, height=32, font_size=10)
        pm2_row.addWidget(pm2_browse)
        clr2_col.addLayout(pm2_row)

        rm2_clr_entry = QLineEdit(); rm2_clr_entry.setPlaceholderText(t("common.nofile_selected"))
        rm2_clr_entry.setReadOnly(True); rm2_clr_entry.setFixedHeight(32); rm2_clr_entry.setFont(font(11))
        rm2_clr_entry.setStyleSheet(self._entry_style())
        rm2_clr_row = QHBoxLayout(); rm2_clr_row.addWidget(rm2_clr_entry)
        rm2_clr_browse = self._mk_btn(t("common.browse"),
                                       lambda: self._browse_layer_file(card, "roughness_map_path_clr_2", rm2_clr_entry, "png"),
                                       "primary", width=90, height=32, font_size=10)
        rm2_clr_row.addWidget(rm2_clr_browse)
        clr2_col.addLayout(rm2_clr_row)

        mm2_clr_entry = QLineEdit(); mm2_clr_entry.setPlaceholderText(t("common.nofile_selected"))
        mm2_clr_entry.setReadOnly(True); mm2_clr_entry.setFixedHeight(32); mm2_clr_entry.setFont(font(11))
        mm2_clr_entry.setStyleSheet(self._entry_style())
        mm2_clr_row = QHBoxLayout(); mm2_clr_row.addWidget(mm2_clr_entry)
        mm2_clr_browse = self._mk_btn(t("common.browse"),
                                       lambda: self._browse_layer_file(card, "metallic_map_path_clr_2", mm2_clr_entry, "png"),
                                       "primary", width=90, height=32, font_size=10)
        mm2_clr_row.addWidget(mm2_clr_browse)
        clr2_col.addLayout(mm2_clr_row)

        clrw_col.addWidget(clr_widget_2)
        fc.addWidget(clr_widget)
        card.update(
            dm_entry=dm_entry, pm_entry=pm_entry, dm_entry_2=dm2_entry, pm_entry_2=pm2_entry,
            rm_clr_entry=rm_clr_entry, mm_clr_entry=mm_clr_entry,
            rm_clr_entry_2=rm2_clr_entry, mm_clr_entry_2=mm2_clr_entry,
            clr_widget=clr_widget, clr_widget_2=clr_widget_2,
        )

        clr_toggle.stateChanged.connect(lambda: self._toggle_layer_colorable(card))

        op_lbl = self._mk_label(t("project.opacity_map"), bold=True)
        fc.addWidget(op_lbl)
        op_entry = QLineEdit(); op_entry.setPlaceholderText(t("common.nofile_selected"))
        op_entry.setReadOnly(True); op_entry.setFixedHeight(32); op_entry.setFont(font(11))
        op_entry.setStyleSheet(self._entry_style())
        op_row = QHBoxLayout(); op_row.addWidget(op_entry)
        op_browse = self._mk_btn(t("common.browse"),
                                  lambda: self._browse_layer_file(card, "opacity_map_path", op_entry, "png"),
                                  "primary", width=90, height=32, font_size=10)
        op_row.addWidget(op_browse)
        fc.addLayout(op_row)
        card["op_entry"] = op_entry

        op_widget_2 = QWidget(); op_widget_2.setStyleSheet("background:transparent;")
        op_widget_2.setVisible(is_var)
        op2_col = QVBoxLayout(op_widget_2); op2_col.setContentsMargins(0, 4, 0, 0); op2_col.setSpacing(4)
        op2_entry = QLineEdit(); op2_entry.setPlaceholderText(
            t("project.variant_body_named", variant=v_suffix.capitalize()) if is_var else t("common.nofile_selected")
        )
        op2_entry.setReadOnly(True); op2_entry.setFixedHeight(32); op2_entry.setFont(font(11))
        op2_entry.setStyleSheet(self._entry_style())
        op2_row = QHBoxLayout(); op2_row.addWidget(op2_entry)
        op2_browse = self._mk_btn(t("common.browse"),
                                   lambda: self._browse_layer_file(card, "opacity_map_path_2", op2_entry, "png"),
                                   "primary", width=90, height=32, font_size=10)
        op2_row.addWidget(op2_browse)
        op2_col.addLayout(op2_row)
        fc.addWidget(op_widget_2)
        card.update(op_entry_2=op2_entry, op_widget_2=op_widget_2)

        nm_lbl = self._mk_label(t("project.normal_map"), bold=True)
        fc.addWidget(nm_lbl)
        nm_entry = QLineEdit(); nm_entry.setPlaceholderText(t("common.nofile_selected"))
        nm_entry.setReadOnly(True); nm_entry.setFixedHeight(32); nm_entry.setFont(font(11))
        nm_entry.setStyleSheet(self._entry_style())
        nm_row = QHBoxLayout(); nm_row.addWidget(nm_entry)
        nm_browse = self._mk_btn(t("common.browse"),
                                  lambda: self._browse_layer_file(card, "normal_map_path", nm_entry, "png"),
                                  "primary", width=90, height=32, font_size=10)
        nm_row.addWidget(nm_browse)
        fc.addLayout(nm_row)
        card["nm_entry"] = nm_entry

        nm_widget_2 = QWidget(); nm_widget_2.setStyleSheet("background:transparent;")
        nm_widget_2.setVisible(is_var)
        nm2_col = QVBoxLayout(nm_widget_2); nm2_col.setContentsMargins(0, 4, 0, 0); nm2_col.setSpacing(4)
        nm2_entry = QLineEdit(); nm2_entry.setPlaceholderText(
            t("project.variant_body_named", variant=v_suffix.capitalize()) if is_var else t("common.nofile_selected")
        )
        nm2_entry.setReadOnly(True); nm2_entry.setFixedHeight(32); nm2_entry.setFont(font(11))
        nm2_entry.setStyleSheet(self._entry_style())
        nm2_row = QHBoxLayout(); nm2_row.addWidget(nm2_entry)
        nm2_browse = self._mk_btn(t("common.browse"),
                                   lambda: self._browse_layer_file(card, "normal_map_path_2", nm2_entry, "png"),
                                   "primary", width=90, height=32, font_size=10)
        nm2_row.addWidget(nm2_browse)
        nm2_col.addLayout(nm2_row)
        fc.addWidget(nm_widget_2)
        card.update(nm_entry_2=nm2_entry, nm_widget_2=nm_widget_2)

        fc.addSpacing(10)
        factors_lbl = self._mk_label(t("project.layer_factors"), bold=True)

        factors_grid = QHBoxLayout()
        factor_entries: Dict[str, QLineEdit] = {}
        for key, label_key, default in [
            ("metallic_factor",             "project.metallic_factor",              0.0),
            ("roughness_factor",            "project.roughness_factor",             0.45),
            ("clear_coat_factor",           "project.clear_coat_factor",            0.4),
            ("clear_coat_roughness_factor", "project.clear_coat_roughness_factor",  0.1),
            ("retroreflectivity",           "project.retroreflectivity",            0.0),
        ]:
            fcol = QVBoxLayout()
            flbl = QLabel(t(label_key))
            flbl.setFont(font(9))
            flbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
            fcol.addWidget(flbl)
            fentry = QLineEdit(str(layer_data.get(key, default)))
            fentry.setFixedHeight(30)
            fentry.setFont(font(11))
            fentry.setStyleSheet(self._entry_style())
            fcol.addWidget(fentry)
            factors_grid.addLayout(fcol)
            factor_entries[key] = fentry
        card["factor_entries"] = factor_entries

        def _get_factor_values(entries=factor_entries) -> Dict[str, Any]:
            out = {}
            for k, e in entries.items():
                txt = e.text().strip()
                try:
                    out[k] = float(txt) if "." in txt else int(txt)
                except ValueError as _exc:
                    print(f"[WARNING] _get_factor_values: {type(_exc).__name__}: {_exc}")
                    out[k] = txt
            return out

        def _apply_factor_values(values: Dict[str, Any], entries=factor_entries):
            for k, v in values.items():
                if k in entries:
                    entries[k].setText(str(v))

        factors_preset_row = self._build_preset_row(
            _PRESET_KIND_LAYER_FACTORS, _get_factor_values, _apply_factor_values
        )
        fc.addWidget(factors_lbl)
        fc.addWidget(factors_preset_row)
        fc.addLayout(factors_grid)

        em_widget = QWidget(); em_widget.setStyleSheet("background:transparent;")
        em_widget.setVisible(bool(layer_data.get("glowing", False)))
        em_col = QVBoxLayout(em_widget); em_col.setContentsMargins(0, 4, 0, 0); em_col.setSpacing(4)
        em_lbl = self._mk_label(t("project.emissive_map"), bold=True)
        em_col.addWidget(em_lbl)
        em_entry = QLineEdit(); em_entry.setPlaceholderText(t("common.nofile_selected"))
        em_entry.setReadOnly(True); em_entry.setFixedHeight(32); em_entry.setFont(font(11))
        em_entry.setStyleSheet(self._entry_style())
        em_row = QHBoxLayout(); em_row.addWidget(em_entry)
        em_browse = self._mk_btn(t("common.browse"),
                                  lambda: self._browse_layer_file(card, "emissive_dds_path", em_entry, "dds"),
                                  "primary", width=90, height=32, font_size=10)
        em_row.addWidget(em_browse)
        em_col.addLayout(em_row)

        em_widget_2 = QWidget(); em_widget_2.setStyleSheet("background:transparent;")
        em_widget_2.setVisible(is_var)
        em2_col = QVBoxLayout(em_widget_2); em2_col.setContentsMargins(0, 4, 0, 0); em2_col.setSpacing(4)
        em2_entry = QLineEdit(); em2_entry.setPlaceholderText(
            t("project.variant_body_named", variant=v_suffix.capitalize()) if is_var else t("common.nofile_selected")
        )
        em2_entry.setReadOnly(True); em2_entry.setFixedHeight(32); em2_entry.setFont(font(11))
        em2_entry.setStyleSheet(self._entry_style())
        em2_row = QHBoxLayout(); em2_row.addWidget(em2_entry)
        em2_browse = self._mk_btn(t("common.browse"),
                                   lambda: self._browse_layer_file(card, "emissive_dds_path_2", em2_entry, "dds"),
                                   "primary", width=90, height=32, font_size=10)
        em2_row.addWidget(em2_browse)
        em2_col.addLayout(em2_row)
        em_col.addWidget(em_widget_2)
        fc.addWidget(em_widget)
        card.update(em_entry=em_entry, em_entry_2=em2_entry, em_widget=em_widget, em_widget_2=em_widget_2)

        glow_toggle.stateChanged.connect(lambda: em_widget.setVisible(glow_toggle.isChecked()))

        self._load_layer_card_values(card, layer_data)
        self._toggle_layer_colorable(card)

        return card

    def _toggle_layer_colorable(self, card: Dict[str, Any]):
        on = card["colorable_toggle"].isChecked()
        print(f"[DEBUG] _toggle_layer_colorable: layer card colorable={on}")
        card["dds_widget"].setVisible(not on)
        card["clr_widget"].setVisible(on)

    def _browse_layer_file(self, card: Dict[str, Any], data_key: str,
                            entry: QLineEdit, kind: str):
        if kind == "dds":
            filt = "DDS files (*.dds);;All files (*.*)"
        else:
            filt = "PNG files (*.png);;All files (*.*)"
        path, _ = QFileDialog.getOpenFileName(self, t("project.dialog_select_layer_file"), "", filt)
        if path:
            print(f"[DEBUG] _browse_layer_file: {data_key}={path!r}")
            card[data_key] = path
            entry.setText(os.path.basename(path))
        else:
            print(f"[DEBUG] _browse_layer_file: dialog cancelled for {data_key}")

    def _load_layer_card_values(self, card: Dict[str, Any], layer_data: Dict[str, Any]):
        applied = 0
        for key, entry_attr in [
            ("dds_path",             "dds_entry"),
            ("dds_path_2",           "dds_entry_2"),
            ("roughness_map_path",   "rm_entry"),
            ("roughness_map_path_2", "rm_entry_2"),
            ("metallic_map_path",    "mm_entry"),
            ("metallic_map_path_2",  "mm_entry_2"),
            ("data_map_path",        "dm_entry"),
            ("color_map_path",       "pm_entry"),
            ("data_map_path_2",      "dm_entry_2"),
            ("color_map_path_2",     "pm_entry_2"),
            ("roughness_map_path_clr",   "rm_clr_entry"),
            ("roughness_map_path_clr_2", "rm_clr_entry_2"),
            ("metallic_map_path_clr",    "mm_clr_entry"),
            ("metallic_map_path_clr_2",  "mm_clr_entry_2"),
            ("opacity_map_path",     "op_entry"),
            ("opacity_map_path_2",   "op_entry_2"),
            ("normal_map_path",      "nm_entry"),
            ("normal_map_path_2",    "nm_entry_2"),
            ("emissive_dds_path",    "em_entry"),
            ("emissive_dds_path_2",  "em_entry_2"),
        ]:
            path = layer_data.get(key, "")
            card[key] = path
            if path:
                card[entry_attr].setText(os.path.basename(path))
                applied += 1

        for key, fentry in card["factor_entries"].items():
            if key in layer_data:
                fentry.setText(str(layer_data[key]))
        print(f"[DEBUG] _load_layer_card_values: applied {applied} file path(s) from stored layer data")

    def _collect_custom_layers(self) -> List[Dict[str, Any]]:
        layers = []
        for card in self._custom_layer_cards:
            is_colorable = card["colorable_toggle"].isChecked()
            layer: Dict[str, Any] = {
                "is_colorable": is_colorable,
                "glowing": card["glow_toggle"].isChecked(),
            }
            if is_colorable:
                layer["data_map_path"]  = card.get("data_map_path", "")
                layer["color_map_path"] = card.get("color_map_path", "")
                if card["is_var"]:
                    layer["data_map_path_2"]  = card.get("data_map_path_2", "")
                    layer["color_map_path_2"] = card.get("color_map_path_2", "")
                if card.get("roughness_map_path_clr"):
                    layer["roughness_map_path"] = card["roughness_map_path_clr"]
                if card["is_var"] and card.get("roughness_map_path_clr_2"):
                    layer["roughness_map_path_2"] = card["roughness_map_path_clr_2"]
                if card.get("metallic_map_path_clr"):
                    layer["metallic_map_path"] = card["metallic_map_path_clr"]
                if card["is_var"] and card.get("metallic_map_path_clr_2"):
                    layer["metallic_map_path_2"] = card["metallic_map_path_clr_2"]
            else:
                layer["dds_path"] = card.get("dds_path", "")
                if card["is_var"]:
                    layer["dds_path_2"] = card.get("dds_path_2", "")
                if card.get("roughness_map_path"):
                    layer["roughness_map_path"] = card["roughness_map_path"]
                if card["is_var"] and card.get("roughness_map_path_2"):
                    layer["roughness_map_path_2"] = card["roughness_map_path_2"]
                if card.get("metallic_map_path"):
                    layer["metallic_map_path"] = card["metallic_map_path"]
                if card["is_var"] and card.get("metallic_map_path_2"):
                    layer["metallic_map_path_2"] = card["metallic_map_path_2"]

            if card.get("opacity_map_path"):
                layer["opacity_map_path"] = card["opacity_map_path"]
            if card["is_var"] and card.get("opacity_map_path_2"):
                layer["opacity_map_path_2"] = card["opacity_map_path_2"]

            if card.get("normal_map_path"):
                layer["normal_map_path"] = card["normal_map_path"]
            if card["is_var"] and card.get("normal_map_path_2"):
                layer["normal_map_path_2"] = card["normal_map_path_2"]

            if layer["glowing"]:
                layer["emissive_dds_path"] = card.get("emissive_dds_path", "")
                if card["is_var"]:
                    layer["emissive_dds_path_2"] = card.get("emissive_dds_path_2", "")

            for key, fentry in card["factor_entries"].items():
                val = fentry.text().strip()
                try:
                    parsed = float(val) if val else 0.0
                except ValueError:
                    print(f"[DEBUG] _collect_custom_layers: invalid value for {key!r}: {val!r} — defaulting to 0.0")
                    self.show_notification(
                        t("project.notification.invalid_layer_value", field=key, value=val),
                        "warning"
                    )
                    parsed = 0.0
                layer[key] = int(parsed) if parsed == int(parsed) else parsed

            layers.append(layer)
        print(f"[DEBUG] _collect_custom_layers: collected {len(layers)} layer(s)")
        return layers

    def _validate_custom_layers(self) -> bool:
        for i, card in enumerate(self._custom_layer_cards, start=1):
            is_colorable = card["colorable_toggle"].isChecked()
            if is_colorable:
                if not card.get("data_map_path") or not card.get("color_map_path"):
                    print(f"[DEBUG] _validate_custom_layers: layer {i} missing colorable data/color map")
                    self.show_notification(
                        t("project.notification.layer_missing_colorable", n=i), "warning"
                    )
                    return False
                if card["is_var"] and (not card.get("data_map_path_2") or not card.get("color_map_path_2")):
                    print(f"[DEBUG] _validate_custom_layers: layer {i} missing variant colorable data/color map")
                    self.show_notification(
                        t("project.notification.layer_missing_colorable_variant", n=i), "warning"
                    )
                    return False
            else:
                if not card.get("dds_path"):
                    print(f"[DEBUG] _validate_custom_layers: layer {i} missing DDS path")
                    self.show_notification(
                        t("project.notification.layer_missing_dds", n=i), "warning"
                    )
                    return False
                if card["is_var"] and not card.get("dds_path_2"):
                    print(f"[DEBUG] _validate_custom_layers: layer {i} missing variant DDS path")
                    self.show_notification(
                        t("project.notification.layer_missing_dds_variant", n=i), "warning"
                    )
                    return False
            if card["glow_toggle"].isChecked() and not card.get("emissive_dds_path"):
                print(f"[DEBUG] _validate_custom_layers: layer {i} glow enabled but missing emissive map")
                self.show_notification(
                    t("project.notification.layer_missing_emissive", n=i), "warning"
                )
                return False
        print(f"[DEBUG] _validate_custom_layers: all {len(self._custom_layer_cards)} layer(s) valid")
        return True

    def _toggle_material_properties(self):
        on = self._material_toggle.isChecked()
        print(f"[DEBUG] _toggle_material_properties: {on}")
        if on:
            if not self.selected_car_for_skin:
                print("[DEBUG] _toggle_material_properties: aborted — no car selected")
                self.show_notification(t("project.notification.select_car_first"), "warning")
                self._material_toggle.setChecked(False)
                return
            car_info = self.project_data["cars"][self.selected_car_for_skin]
            base = car_info.get("base_carid", self.selected_car_for_skin)
            variant_suffix = car_info.get("variant_suffix", "")
            materials = self._load_material_structure(base, variant_suffix)
            if not materials:
                print(f"[DEBUG] _toggle_material_properties: aborted — no material structure for "
                      f"base={base!r} variant={variant_suffix!r}")
                self.show_notification(
                    t("project.notification.no_material_properties"), "warning"
                )
                self._material_toggle.setChecked(False)
                return
            print(f"[DEBUG] _toggle_material_properties: populating {len(materials)} material(s)")
            self._populate_material_properties_ui(materials)
        self._material_props_widget.setVisible(on)


    def _populate_material_properties_ui(self, materials: Dict):
        while self._mat_props_layout.count():
            item = self._mat_props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.material_properties_entries.clear()

        hdr = self._mk_label(t("project.material_properties"), bold=True)
        self._mat_props_layout.addWidget(hdr)

        info = QLabel(t("project.material_values_hint"))
        info.setFont(font(10))
        info.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        self._mat_props_layout.addWidget(info)

        mat_preset_row = self._build_preset_row(
            _PRESET_KIND_MATERIAL_PROPERTIES,
            self._collect_material_properties,
            self._load_material_properties_into_ui,
        )
        self._mat_props_layout.addWidget(mat_preset_row)

        for mat_name, mat_info in materials.items():
            part  = mat_info["part_name"]
            props = mat_info["properties"]

            sect = QFrame()
            sect.setStyleSheet(
                f"QFrame{{background:{COLORS.get('sidebar_bg', COLORS['frame_bg'])};"
                "border-radius:8px;}}"
            )
            sc = QVBoxLayout(sect)
            sc.setContentsMargins(10, 10, 10, 10)
            sc.setSpacing(6)

            hdr_row = QHBoxLayout()
            hl = QLabel(part)
            hl.setFont(font(12, "bold"))
            hl.setStyleSheet(f"color:{COLORS['accent']};background:transparent;border:none;")
            hdr_row.addWidget(hl)
            hdr_row.addStretch()
            tl = QLabel(f"({mat_name})")
            tl.setFont(font(10))
            tl.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;border:none;"
            )
            hdr_row.addWidget(tl)
            sc.addLayout(hdr_row)

            self.material_properties_entries[mat_name] = {}

            for stage_key, stage_props in props.items():
                if len(props) > 1:
                    sl = QLabel(t("project.material_stage_n", n=stage_key.split('_')[1]))
                    sl.setFont(font(10, "bold"))
                    sl.setStyleSheet(
                        f"color:{COLORS['text_secondary']};background:transparent;border:none;"
                    )
                    sc.addWidget(sl)

                props_grid = QHBoxLayout()
                props_grid.setSpacing(8)
                col_count = 0
                for prop_name, prop_value in stage_props.items():
                    label_text = (prop_name.replace("Factor", "")
                                  .replace("clearCoat", "Clear Coat ")
                                  .replace("metallic", "Metallic")
                                  .replace("roughness", "Roughness"))

                    pcol = QVBoxLayout()
                    pl = QLabel(label_text)
                    pl.setFont(font(9))
                    pl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
                    pcol.addWidget(pl)

                    pe = QLineEdit()
                    pe.setPlaceholderText(t("project.material_value_placeholder"))
                    pe.setFixedHeight(30)
                    pe.setFont(font(11))
                    pe.setStyleSheet(self._entry_style())
                    pe.setText("null" if prop_value is None else str(prop_value))
                    pcol.addWidget(pe)

                    props_grid.addLayout(pcol)
                    col_count += 1

                    entry_key = f"{stage_key}_{prop_name}"
                    self.material_properties_entries[mat_name][entry_key] = pe

                    if col_count == 4:
                        sc.addLayout(props_grid)
                        props_grid = QHBoxLayout()
                        props_grid.setSpacing(8)
                        col_count = 0

                if col_count:
                    props_grid.addStretch()
                    sc.addLayout(props_grid)

            self._mat_props_layout.addWidget(sect)

    def _collect_material_properties(self) -> Dict:
        result = {}
        invalid_count = 0
        for mat_name, entries in self.material_properties_entries.items():
            stages: Dict[str, Dict] = {}
            for entry_key, widget in entries.items():
                parts = entry_key.split("_", 2)
                if len(parts) < 3:
                    continue
                stage_num, prop_name = parts[1], parts[2]
                val = widget.text().strip()
                if not val or val.lower() == "null":
                    stages.setdefault(stage_num, {})[prop_name] = None
                else:
                    try:
                        nv = float(val) if "." in val else int(val)
                        nv = max(0.0, min(1.0, nv))
                        nv = int(nv) if nv == int(nv) else nv
                        stages.setdefault(stage_num, {})[prop_name] = nv
                    except ValueError:
                        invalid_count += 1
                        print(f"[DEBUG] _collect_material_properties: invalid value for "
                              f"{mat_name}/stage_{stage_num}/{prop_name}: {val!r} — skipping")
                        self.show_notification(
                            t("project.notification.invalid_material_value",
                              prop_name=prop_name, value=val), "warning"
                        )
            if stages:
                result[mat_name] = stages
        print(f"[DEBUG] _collect_material_properties: collected {len(result)} material(s), "
              f"{invalid_count} invalid value(s) skipped")
        return result

    def _load_material_properties_into_ui(self, mat_props: Dict):
        applied = 0
        skipped_materials = 0
        for mat_name, stages in mat_props.items():
            if mat_name not in self.material_properties_entries:
                skipped_materials += 1
                continue
            entries = self.material_properties_entries[mat_name]
            for stage_num, properties in stages.items():
                for prop_name, val in properties.items():
                    key = f"stage_{stage_num}_{prop_name}"
                    if key in entries:
                        entries[key].setText("null" if val is None else str(val))
                        applied += 1
        print(f"[DEBUG] _load_material_properties_into_ui: applied {applied} value(s), "
              f"{skipped_materials} material(s) not found in current UI (skipped)")


    def _load_material_structure(self, car_id: str, variant_suffix: str = "") -> Dict:
        import re
        print(f"[DEBUG] _load_material_structure: car_id={car_id!r} variant_suffix={variant_suffix!r}")

        def _folder_matches_variant(folder_name: str, suffix: str) -> bool:
            name_lower = folder_name.lower()
            if "skinname" not in name_lower:
                return False
            remainder = name_lower.replace("skinname", "", 1)
            return remainder == suffix.lower()

        search_paths = []
        try:
            from core.settings import get_vehicles_dir, get_bundle_path
            vehicle_roots = [get_vehicles_dir(), os.path.join(get_bundle_path(), "vehicles")]
        except ImportError:
            print("[DEBUG] _load_material_structure: core.settings vehicle dirs not available — using cwd/module-relative fallback")
            vehicle_roots = [os.path.join(os.getcwd(), "vehicles"),
                              os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicles")]

        for base in vehicle_roots:
            vp = os.path.join(base, car_id)
            if os.path.exists(vp):
                for item in os.listdir(vp):
                    ip = os.path.join(vp, item)
                    if os.path.isdir(ip) and _folder_matches_variant(item, variant_suffix):
                        search_paths.append(ip)
                break
        try:
            from core.settings import get_beamng_install_path
            bp = get_beamng_install_path()
            if bp:
                search_paths += [
                    os.path.join(bp, "vehicles", car_id, "skins"),
                    os.path.join(bp, "vehicles", car_id),
                ]
        except Exception as exc:
            print(f"[DEBUG] _load_material_structure: get_beamng_install_path lookup failed: {exc}")

        print(f"[DEBUG] _load_material_structure: {len(search_paths)} search path(s): {search_paths}")

        material_data = {}
        for sp in search_paths:
            if not os.path.isdir(sp):
                continue
            for fn in os.listdir(sp):
                if fn not in ("skin.materials.json", "materials.json"):
                    continue
                fp = os.path.join(sp, fn)
                try:
                    with open(fp, encoding="utf-8") as f:
                        content = re.sub(r",(\s*[}\]])", r"\1", f.read())
                    data = json.loads(content)
                except Exception as exc:
                    print(f"[DEBUG] _load_material_structure: failed to parse {fp!r}: {exc}")
                    continue

                for mat_name, mat_info in data.items():
                    stages = mat_info.get("Stages", [])
                    if not stages:
                        continue
                    props = {}
                    for si, stage in enumerate(stages):
                        stage_props_dict = {
                            p: stage[p]
                            for p in ["clearCoatFactor", "clearCoatRoughnessFactor",
                                      "metallicFactor", "roughnessFactor"]
                            if p in stage
                        }
                        if stage_props_dict:
                            props[f"stage_{si}"] = stage_props_dict
                    if props:
                        part = mat_name.split(".")[0] if "." in mat_name else mat_name
                        material_data[mat_name] = {"part_name": part, "properties": props}
                if material_data:
                    print(f"[DEBUG] _load_material_structure: loaded {len(material_data)} material(s) from {fp!r}")
                    return material_data
        print(f"[DEBUG] _load_material_structure: no materials found ({len(material_data)} result)")
        return material_data


    def _load_info_template_fields(self, car_id: str, variant_suffix: str = "") -> Dict[str, Any]:
        import re
        print(f"[DEBUG] _load_info_template_fields: car_id={car_id!r} variant_suffix={variant_suffix!r}")

        def _folder_matches_variant(folder_name: str, suffix: str) -> bool:
            name_lower = folder_name.lower()
            if "skinname" not in name_lower:
                return False
            remainder = name_lower.replace("skinname", "", 1)
            return remainder == suffix.lower()

        search_paths = []
        try:
            from core.settings import get_vehicles_dir, get_bundle_path
            vehicle_roots = [get_vehicles_dir(), os.path.join(get_bundle_path(), "vehicles")]
        except ImportError:
            print("[DEBUG] _load_info_template_fields: core.settings vehicle dirs not available — using cwd/module-relative fallback")
            vehicle_roots = [os.path.join(os.getcwd(), "vehicles"),
                              os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicles")]

        for base in vehicle_roots:
            vp = os.path.join(base, car_id)
            if os.path.exists(vp):
                for item in os.listdir(vp):
                    ip = os.path.join(vp, item)
                    if os.path.isdir(ip) and _folder_matches_variant(item, variant_suffix):
                        search_paths.append(ip)
                search_paths.append(vp)
                break

        for sp in search_paths:
            if not os.path.isdir(sp):
                continue

            source_info = None
            for fn in ["info.json", "info_template.json"]:
                p = os.path.join(sp, fn)
                if os.path.exists(p):
                    source_info = p
                    break
            if not source_info:
                for fn in os.listdir(sp):
                    if fn.startswith("info") and fn.endswith(".json"):
                        source_info = os.path.join(sp, fn)
                        break
            if not source_info:
                continue

            try:
                with open(source_info, encoding="utf-8") as f:
                    content = re.sub(r",(\s*[}\]])", r"\1", f.read())
                data = json.loads(content)
                if isinstance(data, dict):
                    print(f"[DEBUG] _load_info_template_fields: loaded {len(data)} field(s) from {source_info!r}")
                    return data
            except Exception as e:
                print(f"[DEBUG] failed to parse info template {source_info}: {e}")
                continue

        print("[DEBUG] _load_info_template_fields: no info template found")
        return {}


    def _mark_dirty(self):
        if not self._project_dirty:
            print("[DEBUG] _mark_dirty: project_data changed, now dirty")
        self._project_dirty = True

    def _confirm_discard_if_dirty(self, message_key: str, title_key: str) -> bool:
        if not self._project_dirty:
            return True
        try:
            from gui.confirmation_dialog import DangerConfirmationDialog
        except ImportError:
            print("[DEBUG] _confirm_discard_if_dirty: gui.confirmation_dialog not found — using gui.components.confirmation_dialog")
            from gui.components.confirmation_dialog import DangerConfirmationDialog

        dlg = DangerConfirmationDialog(
            self.window(),
            t(title_key, default="Unsaved Changes"),
            t(message_key, default=(
                "You have unsaved changes to the current project.\n"
                "Continuing will discard them. Are you sure?"
            )),
            state.colors,
            confirm_text=t("project.unsaved.discard", default="Discard Changes"),
            cancel_text=t("project.unsaved.cancel", default="Cancel"),
            icon="⚠️",
        )
        result = bool(dlg.show_and_get())
        print(f"[DEBUG] _confirm_discard_if_dirty: user {'confirmed discard' if result else 'cancelled'}")
        return result

    def _write_project_to_path(self, path: str, mod_name: str, author: str) -> bool:
        self.project_data["mod_name"] = mod_name
        self.project_data["author"]   = author or "Unknown"
        try:
            print(f"[DEBUG] _write_project_to_path: writing JSON to {path!r}")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.project_data, f, indent=2)
            print("[DEBUG] _write_project_to_path: write successful")
            self._current_project_path = path
            self._project_dirty = False

            try:
                print(f"[DEBUG] _write_project_to_path: calling _reg_add with path={path!r}")
                _reg_add(path, self.project_data)
                print("[DEBUG] _write_project_to_path: registry update OK")
            except Exception as _reg_exc:
                print(f"[WARN] _write_project_to_path: registry update failed: {_reg_exc}")

            self.show_notification(
                t("project.notification.project_saved_to", filename=os.path.basename(path)), "success"
            )
            print("[DEBUG] _write_project_to_path: done")
            return True

        except Exception as e:
            print(f"[DEBUG] _write_project_to_path: ERROR writing file: {e}")
            self.show_notification(t("project.notification.save_error", error=e), "error")
            return False

    def _prompt_save_path(self, mod_name: str) -> Optional[str]:
        import re
        from core.settings import get_projects_dir
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", mod_name) if mod_name else ""
        default_filename = f"{safe_name}.json" if safe_name else ""
        default_dir = get_projects_dir()
        default_path = os.path.join(default_dir, default_filename) if default_filename else default_dir
        print(f"[DEBUG] _prompt_save_path: opening save file dialog (default={default_path!r})")
        path, _ = QFileDialog.getSaveFileName(
            self, t("project.dialog_save_project"),
            default_path,
            "JSON files (*.json);;All files (*.*)"
        )
        print(f"[DEBUG] _prompt_save_path: user chose path={path!r}")
        return path or None

    def save_project(self):
        print(f"[DEBUG] save_project: cars in project={list(self.project_data.get('cars', {}).keys())}")

        if not self.project_data["cars"]:
            print("[DEBUG] save_project: no cars in project — aborting")
            self.show_notification(t("project.notification.no_cars_save"), "warning")
            return

        mod_name = (self.mod_name_entry_sidebar.text().strip()
                    if self.mod_name_entry_sidebar else "")
        author   = (self.author_entry_sidebar.text().strip()
                    if self.author_entry_sidebar else "")
        print(f"[DEBUG] save_project: mod_name={mod_name!r} author={author!r}")

        if self._current_project_path:
            path = self._current_project_path

            if state.confirm_on_save:
                print(f"[DEBUG] save_project: confirm_on_save enabled — confirming overwrite of {path!r}")
                if not self._confirm_save(path, emptied=self._project_emptied_since_load):
                    print("[DEBUG] save_project: user cancelled save")
                    return
            else:
                print(f"[DEBUG] save_project: confirm_on_save disabled — overwriting {path!r} directly")
        else:
            path = self._prompt_save_path(mod_name)
            if not path:
                print("[DEBUG] save_project: cancelled — no path chosen")
                return

        if self._write_project_to_path(path, mod_name, author):
            self._project_emptied_since_load = False

    def save_project_as(self):
        if not self.project_data["cars"]:
            self.show_notification(t("project.notification.no_cars_save"), "warning")
            return

        mod_name = (self.mod_name_entry_sidebar.text().strip()
                    if self.mod_name_entry_sidebar else "")
        author   = (self.author_entry_sidebar.text().strip()
                    if self.author_entry_sidebar else "")

        path = self._prompt_save_path(mod_name)
        if not path:
            print("[DEBUG] save_project_as: cancelled — no path chosen")
            return

        if self._write_project_to_path(path, mod_name, author):
            self._project_emptied_since_load = False

    def _confirm_save(self, path: str, emptied: bool = False) -> bool:
        print(f"[DEBUG] _confirm_save: showing for path={path!r} emptied={emptied}")

        if emptied:
            title_text = t("project.overwrite.title_emptied", default="Overwrite Project File?")
            body_text = t("project.overwrite.message_emptied", default=(
                f"This will overwrite:\n{os.path.basename(path)}\n\n"
                "All the original vehicles were removed from this loaded project — "
                "if this has turned into something different, use \"Save As\" instead "
                "to keep the original file intact."
            ))
            icon_char = "⚠️"
        else:
            title_text = t("project.save_confirm.title", default="Save Project?")
            body_text = t("project.save_confirm.message", default=(
                f"This will save changes to:\n{os.path.basename(path)}"
            ))
            icon_char = "💾"

        dlg = QDialog(self.window())
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setModal(True)
        dlg.setFixedWidth(420)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['frame_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
            }}
        """)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        icon_lbl = QLabel(icon_char)
        icon_lbl.setFont(font(32))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        root.addWidget(icon_lbl)

        title_lbl = QLabel(title_text)
        title_lbl.setFont(font(15, "bold"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent; border: none;")
        root.addWidget(title_lbl)

        body_lbl = QLabel(body_text)
        body_lbl.setFont(font(12))
        body_lbl.setWordWrap(True)
        body_lbl.setAlignment(Qt.AlignCenter)
        body_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent; border: none;")
        root.addWidget(body_lbl)

        chk = QCheckBox(t("project.save_confirm.dont_ask", default="Don't ask me again"))
        chk.setFont(font(11))
        chk.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text_secondary']};
                background: transparent;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 15px; height: 15px;
                border: 1px solid {COLORS['border']};
                border-radius: 3px;
                background: {COLORS['frame_bg']};
            }}
            QCheckBox::indicator:checked {{
                background: {COLORS['accent']};
                border-color: {COLORS['accent']};
            }}
        """)
        root.addWidget(chk, alignment=Qt.AlignCenter)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        result = {"proceed": False}

        def _on_cancel():
            print("[DEBUG] _confirm_save: user cancelled")
            result["proceed"] = False
            dlg.reject()

        def _on_confirm():
            print(f"[DEBUG] _confirm_save: user confirmed, dont_ask_again={chk.isChecked()}")
            result["proceed"] = True
            if chk.isChecked():
                state.set_confirm_on_save(False)
                print("[DEBUG] _confirm_save: confirm_on_save preference disabled and persisted")
            dlg.accept()

        cancel_btn = self._mk_btn(
            t("dialog.cancel", default="Cancel"), _on_cancel,
            "secondary", height=34,
        )
        confirm_btn = self._mk_btn(
            t("project.save_confirm.confirm", default="Save"), _on_confirm,
            "primary", height=34,
        )

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(confirm_btn, 1)
        root.addLayout(btn_row)

        dlg.adjustSize()
        pg = self.window().geometry()
        dlg.move(
            pg.x() + (pg.width()  - dlg.width())  // 2,
            pg.y() + (pg.height() - dlg.height()) // 2,
        )

        dlg.exec()
        print(f"[DEBUG] _confirm_save: dialog closed, proceed={result['proceed']}")
        return result["proceed"]

    def load_project(self):
        if not self._confirm_discard_if_dirty(
            "project.unsaved.load_message",
            "project.unsaved.load_title",
        ):
            print("[DEBUG] load_project: cancelled by user due to unsaved changes")
            return

        path: Optional[str] = None

        if ProjectBrowserDialog is not None:
            print("[DEBUG] load_project: opening ProjectBrowserDialog")
            dlg    = ProjectBrowserDialog(self.window())
            result = dlg.exec()
            print(f"[DEBUG] load_project: dialog result={result} selected_path={dlg.selected_path!r}")

            if not result:
                print("[DEBUG] load_project: dialog cancelled — returning early")
                return

            path = dlg.selected_path
        else:
            print("[DEBUG] load_project: ProjectBrowserDialog unavailable — using raw QFileDialog")
            from core.settings import get_projects_dir
            path, _ = QFileDialog.getOpenFileName(
                self, t("project.dialog_load_project"), get_projects_dir(), "JSON files (*.json);;All files (*.*)"
            )
            print(f"[DEBUG] load_project: raw dialog chose path={path!r}")

        if not path:
            print("[DEBUG] load_project: no path selected — returning early")
            return

        self._current_project_path = path
        print(f"[DEBUG] load_project: reading project file from {path!r}")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            print(f"[DEBUG] load_project: JSON read OK — top-level keys={list(data.keys())}")

            if "cars" not in data:
                print("[DEBUG] load_project: 'cars' key missing — invalid project file")
                self.show_notification(t("project.notification.invalid_project"), "error")
                return

            print(f"[DEBUG] load_project: cars={list(data['cars'].keys())}")

            self.project_data          = data
            self.selected_car_for_skin = None
            self.editing_mode          = False
            self.selected_skin_index   = None
            self._project_dirty        = False
            self._project_emptied_since_load = False
            print("[DEBUG] load_project: project_data assigned, selection state reset")

            try:
                self._update_button_ui()
                print("[DEBUG] load_project: _update_button_ui OK")
            except Exception as e:
                print(f"[DEBUG] load_project: _update_button_ui failed: {e}")
            try:
                self._reset_skin_form_fields()
                print("[DEBUG] load_project: _reset_skin_form_fields OK")
            except Exception as e:
                print(f"[DEBUG] load_project: _reset_skin_form_fields failed: {e}")
            try:
                self._skin_card.setVisible(False)
                self._add_skin_label.setVisible(False)
                self._variant_banner.setVisible(False)
                print("[DEBUG] load_project: UI visibility reset OK")
            except Exception as e:
                print(f"[DEBUG] load_project: visibility reset failed: {e}")

            mod_name = data.get("mod_name", "")
            author   = data.get("author",   "")
            self.project_data["mod_name"] = mod_name
            self.project_data["author"]   = author
            print(f"[DEBUG] load_project: mod_name={mod_name!r} author={author!r}")

            try:
                if self.mod_name_entry_sidebar is not None:
                    _set_entry(self.mod_name_entry_sidebar, mod_name)
                    print("[DEBUG] load_project: mod_name sidebar entry set")
            except Exception as e:
                print(f"[DEBUG] load_project: failed to set mod_name sidebar entry: {e}")
            try:
                if self.author_entry_sidebar is not None:
                    _set_entry(self.author_entry_sidebar, author)
                    print("[DEBUG] load_project: author sidebar entry set")
            except Exception as e:
                print(f"[DEBUG] load_project: failed to set author sidebar entry: {e}")

            try:
                print("[DEBUG] load_project: calling _reg_add to register loaded path")
                _reg_add(path, self.project_data)
                print("[DEBUG] load_project: registry update OK")
            except Exception as _reg_exc:
                print(f"[WARN] load_project: registry update failed: {_reg_exc}")

            self.show_notification(
                t("project.notification.project_loaded_count", count=len(data["cars"])), "success"
            )

            try:
                self.car_id_list = self._build_car_id_list()
                print(f"[DEBUG] load_project: car_id_list rebuilt ({len(self.car_id_list)} entries)")
            except Exception as e:
                print(f"[DEBUG] load_project: failed to rebuild car_id_list: {e}")

            def _deferred_refresh():
                print("[DEBUG] load_project._deferred_refresh: calling refresh_project_display")
                try:
                    self.refresh_project_display()
                    print("[DEBUG] load_project._deferred_refresh: OK")
                except Exception as e:
                    print(f"[DEBUG] load_project._deferred_refresh: failed: {e}")

            QTimer.singleShot(100, _deferred_refresh)

            def _deferred_sidebar():
                print("[DEBUG] load_project._deferred_sidebar: repopulating sidebar")
                try:
                    mw = self.window()
                    print(f"[DEBUG] load_project._deferred_sidebar: mw={mw} has_sidebar={hasattr(mw, 'sidebar')}")
                    if mw is not None and hasattr(mw, "sidebar"):
                        mw.sidebar.populate_vehicles(mw._add_vehicle_from_sidebar)
                        print("[DEBUG] load_project._deferred_sidebar: sidebar repopulated OK")
                except Exception as e:
                    print(f"[DEBUG] load_project._deferred_sidebar: failed: {e}")

            QTimer.singleShot(150, _deferred_sidebar)
            print("[DEBUG] load_project: deferred callbacks scheduled — done")

        except Exception as e:
            print(f"[ERROR] load_project: unhandled exception: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification(t("project.notification.load_error", error=e), "error")

    def clear_project(self):
        print("[DEBUG] clear_project: requesting project clear confirmation")
        if not self.project_data["cars"]:
            self.show_notification(t("project.notification.already_empty"), "info")
            return
        try:
            from gui.confirmation_dialog import DangerConfirmationDialog
        except ImportError as _exc:
            print(f"[WARNING] clear_project: {type(_exc).__name__}: {_exc}")
            from gui.components.confirmation_dialog import DangerConfirmationDialog

        if self._project_dirty:
            clear_message = t(
                "project.clear_project_window.clear_project_confirm_message_dirty",
                default=(
                    "This project has unsaved changes. Clearing it now will "
                    "permanently discard everything since the last save. "
                    "Are you sure you want to continue?"
                ),
            )
        else:
            clear_message = t("project.clear_project_window.clear_project_confirm_message")

        dlg = DangerConfirmationDialog(
            self.window(),
            t("project.clear_project_window.clear_project_confirm_title"),
            clear_message,
            state.colors,
            confirm_text=t("project.clear_project_window.clear_project_confirm_yes"),
            cancel_text=t("project.clear_project_window.clear_project_confirm_no"),
            icon="🗑️",
        )
        if not dlg.show_and_get():
            return

        self.project_data["cars"]  = {}
        self.selected_car_for_skin = None
        self.editing_mode          = False
        self.selected_skin_index   = None
        self._current_project_path = None
        self._project_dirty        = False
        self._project_emptied_since_load = False
        self._update_button_ui()
        self._reset_skin_form_fields()
        self._skin_card.setVisible(False)
        self._add_skin_label.setVisible(False)
        self._variant_banner.setVisible(False)

        if self.mod_name_entry_sidebar:
            _set_entry(self.mod_name_entry_sidebar, "")
        if self.author_entry_sidebar:
            _set_entry(self.author_entry_sidebar, "")

        self.show_notification(t("project.notification.project_cleared"), "info")
        self.refresh_project_display()

        try:
            mw = self.window()
            if mw and hasattr(mw, "sidebar") and hasattr(mw, "_add_vehicle_from_sidebar"):
                mw.sidebar.populate_vehicles(mw._add_vehicle_from_sidebar)
        except Exception as e:
            print(f"[WARNING] sidebar repopulate after clear failed: {e}")


    def generate_mod(self, generate_button, output_mode_combo=None, custom_output_var=None, unpacked: bool = False):
        print(f"[DEBUG] generate_mod: output_mode={output_mode_combo!r} unpacked={unpacked}")
        if not self.mod_name_entry_sidebar or not self.author_entry_sidebar:
            print("[DEBUG] generate_mod: aborted — sidebar entries not wired up")
            self.show_notification(t("project.notification.sidebar_error"), "error")
            return

        mod_name = self.mod_name_entry_sidebar.text().strip()
        author   = self.author_entry_sidebar.text().strip()

        if not mod_name:
            print("[DEBUG] generate_mod: aborted — mod name is empty")
            self.show_notification(t("project.notification.no_zip_name"), "error")
            return
        if not author:
            print("[DEBUG] generate_mod: aborted — author name is empty")
            self.show_notification(t("project.notification.no_author_name"), "error")
            return
        if not self.project_data["cars"]:
            print("[DEBUG] generate_mod: aborted — no vehicles in project")
            self.show_notification(t("project.notification.please_add_vehicle"), "error")
            return

        missing = []
        total_skins = 0
        for carid, car_info in self.project_data["cars"].items():
            if not car_info["skins"]:
                print(f"[DEBUG] generate_mod: aborted — {carid!r} has no skins")
                self.show_notification(
                    f"{t('project.notification.please_add_skin')} {carid}", "error", 4000
                )
                return
            total_skins += len(car_info["skins"])
            for skin in car_info["skins"]:
                sn = skin.get("name", "?")
                if skin.get("is_colorable"):
                    for fk in ("data_map_path", "color_map_path",
                               "data_map_path_2", "color_map_path_2"):
                        p = skin.get(fk)
                        if p and not os.path.exists(p):
                            missing.append(f"'{sn}' – {fk}: {os.path.basename(p)}")
                else:
                    for fk in ("dds_path", "dds_path_2"):
                        p = skin.get(fk)
                        if p and not os.path.exists(p):
                            missing.append(f"'{sn}' – {fk}: {os.path.basename(p)}")
                if "config_data" in skin:
                    cd = skin["config_data"]
                    for fk in ("pc_file_path", "jpg_file_path"):
                        p = cd.get(fk)
                        if p and not os.path.exists(p):
                            missing.append(f"'{sn}' – {fk}: {os.path.basename(p)}")

        print(f"[DEBUG] generate_mod: {len(self.project_data['cars'])} vehicle(s), "
              f"{total_skins} skin(s) total, {len(missing)} missing file(s)")

        if missing:
            print(f"[DEBUG] generate_mod: aborted — missing files: {missing[:5]}")
            self.show_notification(
                t("project.notification.missing_files", files="\n".join(missing[:5])),
                "error", 6000
            )
            return

        output_mode = output_mode_combo or "default"
        if output_mode == "custom":
            output_path = (custom_output_var or "").strip()
            if not output_path:
                print("[DEBUG] generate_mod: aborted — custom output mode but no path given")
                self.show_notification(
                    t("project.notification.please_select_custom_output"), "error"
                )
                return
        elif output_mode == "steam":
            try:
                from core.settings import get_mods_folder_path
                mods_folder = get_mods_folder_path()
                if not mods_folder or not os.path.exists(mods_folder):
                    print(f"[DEBUG] generate_mod: aborted — steam mods folder missing/invalid: {mods_folder!r}")
                    self.show_notification(
                        t("project.notification.mod_folder_not_exist") +
                        f" {mods_folder}", "error", 4000
                    )
                    return
                if unpacked:
                    output_path = os.path.join(mods_folder, "unpacked")
                    os.makedirs(output_path, exist_ok=True)
                else:
                    output_path = mods_folder
            except Exception as exc:
                print(f"[DEBUG] generate_mod: aborted — failed to resolve steam mods folder: {exc}")
                self.show_notification(
                    t("project.notification.load_settings_failed"), "error"
                )
                return
        else:
            output_path = None

        print(f"[DEBUG] generate_mod: output_path={output_path!r}")

        try:
            from core.file_ops import (
                get_beamng_mods_path   as _get_mods_path,
                sanitize_mod_name      as _sanitize_mod_name,
            )
        except ImportError:
            print("[DEBUG] generate_mod: core.file_ops mods-path/sanitize helpers not available — using fallback")
            def _sanitize_mod_name(n): return n.strip().replace(" ", "_")
            def _get_mods_path(): return None

        _san_mod_name  = _sanitize_mod_name(mod_name)
        _resolved_mods = output_path or _get_mods_path()

        if _resolved_mods:
            if unpacked:
                _conflict_path  = os.path.join(_resolved_mods, _san_mod_name)
                _conflict_label = f"folder named '{_san_mod_name}'"
            else:
                _conflict_path  = os.path.join(_resolved_mods, f"{_san_mod_name}.zip")
                _conflict_label = f"'{_san_mod_name}.zip'"

            if os.path.exists(_conflict_path):
                print(f"[DEBUG] generate_mod: output conflict detected at {_conflict_path!r}")
                _title   = t("project.overwrite_dialog.title", default="Overwrite existing mod?")
                _message = t("project.overwrite_dialog.message",
                             label=_conflict_label,
                             default=(
                                 f"A mod {_conflict_label} already exists in the output folder.\n\n"
                                 f"Do you want to overwrite it?"
                             ))
                try:
                    from gui.confirmation_dialog import askokcancel
                    _confirmed = askokcancel(
                        self.window(), _title, _message, COLORS, icon="📁", danger=True,
                    )
                except Exception as _dlg_err:
                    print(f"[WARNING] generate_mod: styled overwrite dialog failed ({_dlg_err}), using fallback")
                    from PySide6.QtWidgets import QMessageBox
                    _confirmed = QMessageBox.question(
                        self.window(), _title, _message,
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                    ) == QMessageBox.Yes
                if not _confirmed:
                    print("[DEBUG] generate_mod: user declined overwrite — aborting")
                    return
                try:
                    if os.path.isdir(_conflict_path):
                        import shutil as _shutil
                        _shutil.rmtree(_conflict_path)
                    else:
                        os.remove(_conflict_path)
                    print(f"[DEBUG] generate_mod: removed existing output: {_conflict_path}")
                except Exception as _rm_err:
                    print(f"[DEBUG] generate_mod: failed to remove existing output {_conflict_path!r}: {_rm_err}")
                    self.show_notification(
                        t("project.notification.overwrite_failed",
                          error=_rm_err,
                          default=f"Could not remove existing mod: {_rm_err}"),
                        "error", 5000,
                    )
                    return

        self.project_data["mod_name"] = mod_name
        self.project_data["author"]   = author

        self._export_status.setText(t("project.export_preparing"))
        self._progress_bar.setValue(0)
        self._reposition_export_overlay()
        self._export_overlay.setVisible(True)
        self._export_overlay.raise_()
        generate_button.setEnabled(False)
        self._pending_generate_button = generate_button

        self._set_project_locked(True)

        def _update_status(msg: str):
            self._status_signal.emit(msg)

        def _update_progress(value: float):
            self._progress_signal.emit(int(value * 100))

        def _notify_safe(msg: str, kind: str = "info", dur: int = 3000):
            QTimer.singleShot(0, lambda: self.show_notification(msg, kind, dur))

        def _thread_fn():
            print(f"[DEBUG] generate_mod._thread_fn: starting generation ({total_skins} skin(s))")
            _success = False
            try:
                def prog(v):
                    _update_progress(v)
                    if   v < 0.3: _update_status(t("project.export_copying"))
                    elif v < 0.7: _update_status(t("project.export_processing", count=total_skins))
                    else:
                        if unpacked:
                            _update_status(t("project.export_unpacking"))
                        else:
                            _update_status(t("project.export_zipping"))

                if generate_multi_skin_mod:
                    generate_multi_skin_mod(
                        self.project_data,
                        output_path=output_path,
                        progress_callback=prog,
                        unpacked=unpacked,
                    )
                    _success = True
                    print("[DEBUG] generate_mod._thread_fn: generate_multi_skin_mod completed successfully")
                    _update_status(t("project.export_complete"))
                    _notify_safe(
                        t("project.notification.multi_skin_mod").format(
                            mod_name=mod_name, total_skins=total_skins
                        ),
                        "success", 5000
                    )
                else:
                    print("[DEBUG] generate_mod._thread_fn: generate_multi_skin_mod is None — mod generation unavailable")
                    _update_status(t("project.export_error"))
                    _notify_safe(
                        t("project.notification.mod_generation_unavailable"),
                        "error", 7000
                    )
            except FileExistsError as exc:
                print(f"[DEBUG] generate_mod._thread_fn: FileExistsError: {exc}")
                import traceback; traceback.print_exc()
                first_line = str(exc).split("\n")[0]
                _update_status(f"Error: {first_line}")
                _notify_safe(str(exc), "error", 9000)
            except FileNotFoundError as exc:
                print(f"[DEBUG] generate_mod._thread_fn: FileNotFoundError: {exc}")
                import traceback; traceback.print_exc()
                _update_status(f"Error: {exc}")
                _notify_safe(
                    t("project.notification.file_not_found_hint", error=exc),
                    "error", 9000
                )
            except Exception as exc:
                print(f"[DEBUG] generate_mod._thread_fn: unexpected {type(exc).__name__}: {exc}")
                import traceback; traceback.print_exc()
                _update_status(f"Export failed — {type(exc).__name__}: {exc}")
                _notify_safe(
                    t("project.notification.export_error_debug",
                      type=type(exc).__name__, error=exc),
                    "error", 7000
                )
            finally:
                print(f"[DEBUG] generate_mod._thread_fn: finished, success={_success}")
                self._done_signal.emit(_success)

        threading.Thread(target=_thread_fn, daemon=True).start()


    def refresh_ui(self):
        print("[DEBUG] refresh_ui: re-applying locale strings after language/theme change")
        self._proj_hdr_lbl.setText(t("project.project_overview"))
        self._save_btn.setText(t("project.save_project"))
        self._load_btn.setText(t("project.load_project"))
        self._clear_btn.setText(t("project.clear_project"))
        self._veh_lbl.setText(t("project.vehicles_in_project"))
        self._project_search.setPlaceholderText(t("common.search_vehicle"))
        self._add_skin_label.setText(
            t("project.add_skins_header", default="Add Skins to Selected Car")
        )

        self._skin_name_lbl.setText(t("project.skin_name"))
        self.skin_name_entry.setPlaceholderText(t("project.skin_name_placeholder"))

        self._cfg_lbl.setText(t("project.add_config_data"))
        self._mat_lbl.setText(t("project.edit_materials"))
        self._clr_lbl.setText(t("project.colorable"))
        self._info_lbl.setText(t("project.edit_info_data", default="Edit Vehicle Info"))

        self._config_name_lbl.setText(t("project.config_name"))
        self._config_name_entry.setPlaceholderText(t("project.config_name_placeholder"))
        self._config_type_lbl.setText(t("project.type"))

        self._pc_file_lbl.setText(t("project.pc_file"))
        self.pc_file_entry.setPlaceholderText(t("common.nofile_selected"))
        self._pc_browse.setText(t("common.browse"))
        self._jpg_file_lbl.setText(t("project.jpg_file"))
        self.jpg_file_entry.setPlaceholderText(t("common.nofile_selected"))
        self._jpg_browse.setText(t("common.browse"))

        self._dds_label_1.setText(t("project.dds_texture"))
        self.dds_entry.setPlaceholderText(t("common.nofile_selected"))
        self._dds_browse.setText(t("common.browse"))
        self._dds_label_2.setText(t("project.dds_texture_variant_body"))
        self.dds_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self._dds_browse_2.setText(t("common.browse"))

        self._clr_body1_lbl.setText(t("project.normal_body"))
        self._base_color_map_lbl_1.setText(t("project.base_Color_Map"))
        self.data_map_entry.setPlaceholderText(t("common.nofile_selected"))
        self._dm_browse.setText(t("common.browse"))
        self._color_palette_map_lbl_1.setText(t("project.color_Palette_Map"))
        self.color_map_entry.setPlaceholderText(t("common.nofile_selected"))
        self._cm_browse.setText(t("common.browse"))

        self._clr_body2_lbl.setText(t("project.variant_body"))
        self._base_color_map_lbl_2.setText(t("project.base_Color_Map"))
        self.data_map_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self._dm2_browse.setText(t("common.browse"))
        self._color_palette_map_lbl_2.setText(t("project.color_Palette_Map"))
        self.color_map_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self._cm2_browse.setText(t("common.browse"))

        self.add_skin_btn.setText(t("project.add_skin"))
        self.cancel_edit_btn.setText(t("project.cancel_edit"))

        self._layers_lbl.setText(t("project.custom_layers"))
        self._add_layer_btn.setText(t("project.add_new_layer"))
        self._layers_hint.setText(t("project.custom_layers_hint"))
        self._refresh_layers_limit_label()

        self._glow_lbl.setText(t("project.glowing_skin"))
        self._emissive_lbl.setText(t("project.emissive_map"))
        self.emissive_entry.setPlaceholderText(t("common.nofile_selected"))
        self._emissive_browse.setText(t("common.browse"))

        if self.selected_car_for_skin:
            info     = self.project_data["cars"].get(self.selected_car_for_skin, {})
            dname    = info.get("display_name", "")
            v_suffix = info.get("variant_suffix", "")
            if v_suffix:
                is_clr       = self._colorable_toggle.isChecked()
                requirements = (
                    t("project.variant_4_pngs") if is_clr
                    else t("project.variant_2_dds")
                )
                self._variant_banner.setText(
                    t("project.variant_banner",
                      name=dname, requirements=requirements, variant=v_suffix)
                )

        self.car_id_list = self._build_car_id_list()
        self.refresh_project_display()


    def _mk_card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['card_bg']};
                border-radius:12px;
                border:1px solid {COLORS['border']};
            }}
            QFrame:hover {{
                border:1px solid {COLORS['accent']};
            }}
        """)
        return f

    def _mk_btn(self, text: str, cmd, style: str = "primary",
                width: int = 120, height: int = 36,
                font_size: int = 12) -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(font(font_size, "bold"))
        btn.setFixedHeight(height)
        btn.setCursor(Qt.PointingHandCursor)
        if style == "primary":
            fg, fgh = COLORS["accent"], COLORS["accent_hover"]
            tc = COLORS["accent_text"]
        elif style == "danger":
            fg  = COLORS.get("error",  "#e74c3c")
            fgh = COLORS.get("error_hover", "#c0392b")
            tc  = "white"
        else:
            fg, fgh = COLORS["card_bg"], COLORS["card_hover"]
            tc = COLORS["text"]
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{fg};color:{tc};
                border-radius:8px;border:none;
                padding:4px 12px;
            }}
            QPushButton:hover {{ background:{fgh}; }}
            QPushButton:disabled {{ background:{COLORS['border']};color:{COLORS['text_secondary']}; }}
        """)
        btn.clicked.connect(cmd)
        return btn

    def _mk_label(self, text: str, bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(font(12, "bold" if bold else "normal"))
        lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        return lbl

    def _entry_style(self) -> str:
        return f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 10px;
            }}
            QLineEdit:focus {{ border-color:{COLORS.get('border_focus', COLORS['accent'])}; }}
            QLineEdit:read-only {{ background:{COLORS['card_bg']}; }}
        """


    def _build_preset_row(self, kind: str, get_values: Callable[[], Dict[str, Any]],
                           apply_values: Callable[[Dict[str, Any]], None]) -> QWidget:
        row_widget = QWidget()
        row_widget.setStyleSheet("background:transparent;")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        lbl = QLabel(t("project.preset"))
        lbl.setFont(font(9))
        lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
        row.addWidget(lbl)

        name_entry = QLineEdit()
        name_entry.setFixedHeight(30)
        name_entry.setFont(font(10))
        name_entry.setStyleSheet(self._entry_style())
        name_entry.setPlaceholderText(t("project.preset_name_placeholder"))
        row.addWidget(name_entry, 1)

        def _apply_loaded(name: str):
            print(f"[DEBUG] _build_preset_row[{kind}]: loading preset {name!r}")
            values = _load_preset(kind, name)
            if values is None:
                print(f"[DEBUG] _build_preset_row[{kind}]: load failed for {name!r}")
                self.show_notification(t("project.notification.preset_load_failed", name=name), "error")
                return
            apply_values(values)
            name_entry.setText(name)
            print(f"[DEBUG] _build_preset_row[{kind}]: loaded preset {name!r} with {len(values)} value(s)")
            self.show_notification(t("project.notification.preset_loaded", name=name), "success")

        def _do_save():
            name = name_entry.text().strip()
            if not name:
                print(f"[DEBUG] _build_preset_row[{kind}]: save aborted — no preset name entered")
                self.show_notification(t("project.notification.preset_name_required"), "warning")
                return
            values = get_values()
            if _save_preset(kind, name, values):
                print(f"[DEBUG] _build_preset_row[{kind}]: saved preset {name!r} with {len(values)} value(s)")
                self.show_notification(t("project.notification.preset_saved", name=name), "success")
            else:
                print(f"[DEBUG] _build_preset_row[{kind}]: save FAILED for {name!r}")
                self.show_notification(t("project.notification.preset_save_failed", name=name), "error")

        def _do_open_picker():
            self._open_preset_picker(kind, on_load=_apply_loaded)

        load_btn = self._mk_btn(t("common.load"), _do_open_picker, "primary",
                                 width=64, height=30, font_size=10)
        load_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;color:{COLORS['text']};
                border-radius:8px;border:1px solid {COLORS['border']};
                padding:4px 12px;
            }}
            QPushButton:hover {{ background:{COLORS['card_hover']};border-color:{COLORS['accent']}; }}
        """)
        save_btn = self._mk_btn(t("common.save"), _do_save, "primary",
                                 width=64, height=30, font_size=10)

        row.addWidget(save_btn)
        row.addWidget(load_btn)

        return row_widget

    def _open_preset_picker(self, kind: str, on_load: Callable[[str], None]):
        names = _list_presets(kind)
        print(f"[DEBUG] _open_preset_picker: kind={kind!r} showing {len(names)} preset(s)")

        dlg = QDialog(self.window())
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setModal(True)
        dlg.setFixedWidth(420)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['frame_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
            }}
        """)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title_lbl = QLabel(t("project.preset_picker_title"))
        title_lbl.setFont(font(14, "bold"))
        title_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        root.addWidget(title_lbl)

        search_entry = QLineEdit()
        search_entry.setPlaceholderText(t("common.search_preset"))
        search_entry.setClearButtonEnabled(True)
        search_entry.setFixedHeight(30)
        search_entry.setFont(font(11))
        search_entry.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 10px;
            }}
            QLineEdit:focus {{ border-color:{COLORS['accent']}; }}
        """)
        root.addWidget(search_entry)

        list_area = QScrollArea()
        list_area.setWidgetResizable(True)
        list_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        list_area.setFixedHeight(min(280, max(80, 52 * max(1, len(names)))))
        list_area.setStyleSheet(f"""
            QScrollArea{{background:transparent;border:none;}}
            QScrollArea>QWidget>QWidget{{background:transparent;}}
        """)
        list_inner = QWidget()
        list_inner.setStyleSheet("background:transparent;")
        list_layout = QVBoxLayout(list_inner)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)

        empty_lbl = QLabel(t("project.no_presets_saved"))
        empty_lbl.setFont(font(11))
        empty_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
        empty_lbl.setVisible(not names)
        list_layout.addWidget(empty_lbl)

        def _rebuild_rows():
            while list_layout.count():
                item = list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            current_names = _list_presets(kind)
            query = search_entry.text().strip().lower()
            if query:
                current_names = [n for n in current_names if query in n.lower()]

            if not current_names:
                empty = QLabel(t("project.no_presets_saved"))
                empty.setFont(font(11))
                empty.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
                list_layout.addWidget(empty)
                return

            for preset_name in current_names:
                entry_row = QFrame()
                entry_row.setStyleSheet(
                    f"QFrame{{background:{COLORS.get('sidebar_bg', COLORS['card_bg'])};border-radius:8px;}}"
                )
                er = QHBoxLayout(entry_row)
                er.setContentsMargins(10, 6, 10, 6)
                er.setSpacing(8)

                name_lbl = QLabel(preset_name)
                name_lbl.setFont(font(11))
                name_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
                er.addWidget(name_lbl, 1)

                def _make_load(n=preset_name):
                    def _run():
                        on_load(n)
                        dlg.accept()
                    return _run

                def _make_delete(n=preset_name):
                    def _run():
                        print(f"[DEBUG] _open_preset_picker[{kind}]: deleting {n!r}")
                        if _delete_preset(kind, n):
                            self.show_notification(
                                t("project.notification.preset_deleted", name=n), "success"
                            )
                            _rebuild_rows()
                        else:
                            self.show_notification(
                                t("project.notification.preset_delete_failed", name=n), "error"
                            )
                    return _run

                row_load_btn = self._mk_btn(t("common.load"), _make_load(), "primary",
                                             width=64, height=28, font_size=10)
                row_load_btn.setStyleSheet(f"""
                    QPushButton {{
                        background:transparent;color:{COLORS['text']};
                        border-radius:8px;border:1px solid {COLORS['border']};
                        padding:4px 12px;
                    }}
                    QPushButton:hover {{ background:{COLORS['card_hover']};border-color:{COLORS['accent']}; }}
                """)
                row_del_btn  = self._mk_btn(t("common.delete"), _make_delete(), "danger",
                                             width=70, height=28, font_size=10)
                er.addWidget(row_load_btn)
                er.addWidget(row_del_btn)

                list_layout.addWidget(entry_row)

        search_entry.textChanged.connect(lambda _txt: _rebuild_rows())

        _rebuild_rows()

        list_area.setWidget(list_inner)
        root.addWidget(list_area)

        close_btn = self._mk_btn(t("common.close"), lambda: dlg.reject(), "secondary", height=34)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;color:{COLORS['text']};
                border-radius:8px;border:1px solid {COLORS['border']};
                padding:4px 12px;
            }}
            QPushButton:hover {{ background:{COLORS['card_hover']};border-color:{COLORS['accent']}; }}
        """)
        root.addWidget(close_btn)

        dlg.adjustSize()
        pg = self.window().geometry()
        dlg.move(
            pg.x() + (pg.width()  - dlg.width())  // 2,
            pg.y() + (pg.height() - dlg.height()) // 2,
        )
        dlg.exec()
