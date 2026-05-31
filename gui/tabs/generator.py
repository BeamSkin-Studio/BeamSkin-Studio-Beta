from __future__ import annotations
import os, json, threading
from typing import Dict, List, Optional, Any, Callable

from PySide6.QtCore    import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui     import QPixmap, QPainter, QBrush, QColor
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QCheckBox, QComboBox,
    QProgressBar, QScrollArea, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFileDialog, QSizePolicy, QSplitter,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import AnimButton, GhostButton, SectionHeader, HSeparator, ToggleSwitch
from gui.state   import state

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return key

try:
    from utils.file_ops import load_added_vehicles_json
except ImportError:
    def load_added_vehicles_json(): return {}

try:
    from core.file_ops import generate_multi_skin_mod
except ImportError:
    generate_multi_skin_mod = None

try:
    from utils.config_helper import load_config_types
    _CONFIG_TYPES = load_config_types()
except ImportError:
    _CONFIG_TYPES = ["Factory", "Custom", "Police"]

try:
    from core.settings import get_mods_folder_path as _get_mods_folder_path
except ImportError:
    def _get_mods_folder_path(): return ""

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

print("[DEBUG] Loading class: GeneratorTab")



def _load_pixmap_robust(path: str, max_w: int = 400, max_h: int = 200) -> Optional[QPixmap]:
    from PySide6.QtGui import QImageReader

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
            _PILImage.MAX_IMAGE_PIXELS = None  # allow large game textures (e.g. 16384×16384 BC7)
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
            return result
        return _pil_load()

    elif ext == ".dds":
        # Many game DDS files use DX10-extended headers with sRGB DXGI formats
        # (e.g. BC1_UNORM_SRGB = 72). Every library rejects these even though the
        # block layout is byte-for-byte identical to the linear variant (71).
        # Patch the 4-byte DXGI format field in-memory before decoding.
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
                _PilImg.MAX_IMAGE_PIXELS = None  # allow large game textures (e.g. 16384×16384 BC7)
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
                import io as _io
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
            return result
        result = _wand_load()
        if result:
            return result
        result = _pil_load()
        if result:
            return result
        result = _qt_load()
        if result:
            return result
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
        return result if result else _qt_load()


def _set_entry(entry, text: str, placeholder: bool = False):
    if hasattr(entry, "set_text"):
        entry.set_text(text)
    else:
        entry.setText(text)


def _get_entry_text(entry) -> str:
    return entry.text() if hasattr(entry, "text") else ""



def _make_project_key(carid: str, variant_suffix: str) -> str:
    """
    Generate the project dictionary key for a (carid, variant) combination.
      pickup + ""           → "pickup"
      pickup + "ambulance"  → "pickup__ambulance"
    """
    return f"{carid}__{variant_suffix}" if variant_suffix else carid


def _split_project_key(key: str):
    """Return (base_carid, variant_suffix) from a project key."""
    if "__" in key:
        base, suffix = key.split("__", 1)
        return base, suffix
    return key, ""


_ILLEGAL_NAME_CHARS = set('\\/:*?"<>|')

def _find_illegal_chars(name: str):
    """Return a sorted list of illegal filename characters found in *name*."""
    return sorted({c for c in name if c in _ILLEGAL_NAME_CHARS})


#  GENERATOR TAB



#  GENERATOR TAB

class GeneratorTab(QWidget):

    _status_signal   = Signal(str)
    _progress_signal = Signal(int)
    _done_signal     = Signal(bool)

    def __init__(self, parent: QWidget,
                 notification_callback: Callable[[str, str, int], None] = None,
                 preview_manager=None,
                 **_kwargs):
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")
        print("[DEBUG] GeneratorTab.__init__ called")

        self.show_notification = notification_callback or self._fallback_notification

        self.mod_name_entry_sidebar: Optional[QLineEdit] = None
        self.author_entry_sidebar:   Optional[QLineEdit] = None

        self.project_data: Dict = {"mod_name": "", "author": "", "cars": {}}
        self.selected_car_for_skin: Optional[str] = None
        self.selected_skin_index:   Optional[int]  = None
        self.editing_mode:          bool            = False
        self.expanded_car_id:       Optional[str]   = None

        self.config_types = _CONFIG_TYPES

        # Normal / single-body paths
        self._dds_path       = ""
        self._data_map_path  = ""
        self._color_map_path = ""
        # Second body (variant) paths – only used when variant_suffix != ""
        self._dds_path_2       = ""
        self._data_map_path_2  = ""
        self._color_map_path_2 = ""
        self._rough_met_path   = ""
        self._rough_met_path_2 = ""

        self._pc_file_path   = ""
        self._jpg_file_path  = ""
        self._config_name    = ""
        self._data_map_photo_stash: Optional[QPixmap] = None
        self._current_project_path: Optional[str] = None   # set on load/save; None = unsaved new project

        self.material_properties_entries: Dict[str, Dict[str, QLineEdit]] = {}
        self.car_id_list: List = self._build_car_id_list()

        self._setup_ui()

        self._status_signal.connect(self._export_status.setText)
        self._progress_signal.connect(self._progress_bar.setValue)
        self._done_signal.connect(self._on_generate_done)
        self._pending_generate_button = None   # set in generate_mod(), cleared in _on_generate_done()


    def _selected_variant_suffix(self) -> str:
        """Return the variant suffix for the currently selected car, or ''."""
        if not self.selected_car_for_skin:
            return ""
        info = self.project_data["cars"].get(self.selected_car_for_skin, {})
        return info.get("variant_suffix", "")

    def _is_variant(self) -> bool:
        """True when the selected car is a non-normal body variant."""
        print(f"[DEBUG] _selected_variant_suffix() called")
        return self._selected_variant_suffix() != ""


    def _on_generate_done(self, success: bool):
        print(f"[DEBUG] _on_generate_done() called")

        # Re-enable the generate button on the main thread (the only safe place).
        # Prefer looking up the live topbar button so that a theme/language
        # refresh (which destroys and recreates topbar widgets) doesn't leave us
        # holding a stale reference.
        enabled = False
        try:
            mw = self.window()
            if mw and hasattr(mw, "topbar") and hasattr(mw.topbar, "generate_button"):
                mw.topbar.generate_button.setEnabled(True)
                enabled = True
        except RuntimeError:
            pass  # C++ object already deleted — topbar is mid-rebuild

        if not enabled:
            # Fallback: re-enable the exact button that was passed to generate_mod()
            btn = getattr(self, "_pending_generate_button", None)
            if btn is not None:
                try:
                    btn.setEnabled(True)
                except RuntimeError:
                    pass  # Widget was deleted during a concurrent refresh_ui()
        self._pending_generate_button = None

        hide_delay = 2000 if success else 8000
        QTimer.singleShot(hide_delay, lambda: self._progress_bar.setVisible(False))
        QTimer.singleShot(hide_delay, lambda: self._export_status.setVisible(False))

    def _fallback_notification(self, msg: str, kind: str = "info", duration: int = 3000):
        print(f"[DEBUG] _fallback_notification() called")
        print(f"[{kind.upper()}] {msg}")


    def _build_car_id_list(self) -> List:
        print(f"[DEBUG] _build_car_id_list() called")
        vehicles = load_added_vehicles_json()
        state.added_vehicles.clear()
        state.added_vehicles.update(vehicles)
        car_list = []
        for cid, cname in state.vehicle_ids.items():
            if cid not in state.added_vehicles:
                car_list.append((cid, cname))
        for cid, cname in state.added_vehicles.items():
            car_list.append((cid, cname))
        return sorted(car_list, key=lambda x: x[1].lower())

    def refresh_vehicle_list(self):
        print(f"[DEBUG] refresh_vehicle_list: rebuilding vehicle list from state")
        self.car_id_list = self._build_car_id_list()
        self.refresh_project_display()


    def set_sidebar_references(self, mod_name_entry, author_entry):
        print(f"[DEBUG] set_sidebar_references() called")
        self.mod_name_entry_sidebar = mod_name_entry
        self.author_entry_sidebar   = author_entry
        if self.project_data.get("mod_name"):
            _set_entry(mod_name_entry, self.project_data["mod_name"])
        if self.project_data.get("author"):
            _set_entry(author_entry, self.project_data["author"])


    def _setup_ui(self):
        print(f"[DEBUG] _setup_ui() called")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setFixedWidth(380)
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
        self._proj_layout.setContentsMargins(0, 0, 0, 0)
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

        # variant info banner (hidden for normal cars)
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

        self._export_status = QLabel("")
        self._export_status.setFont(font(12))
        self._export_status.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        self._export_status.setVisible(False)
        self._right_col.addWidget(self._export_status)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background:{COLORS['frame_bg']};
                border-radius:4px;
                border:none;
            }}
            QProgressBar::chunk {{
                background:{COLORS['accent']};
                border-radius:4px;
            }}
        """)
        self._progress_bar.setVisible(False)
        self._right_col.addWidget(self._progress_bar)

        self._right_col.addStretch()
        right_scroll.setWidget(right_inner)

        # Wrap scroll + sticky button footer so the button is always visible
        right_wrapper = QWidget()
        right_wrapper.setStyleSheet("background:transparent;")
        right_wrap_layout = QVBoxLayout(right_wrapper)
        right_wrap_layout.setContentsMargins(0, 0, 0, 0)
        right_wrap_layout.setSpacing(0)
        right_wrap_layout.addWidget(right_scroll, 1)

        # Sticky "Add Skin / Update Skin" footer — lives outside the scroll area
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


    def _build_skin_form(self, card: QFrame):
        print(f"[DEBUG] _build_skin_form() called")
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
        col.addWidget(self._config_files_widget)

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

        #  DDS SECTION  (non-colorable)
        self._dds_widget = QWidget()
        self._dds_widget.setStyleSheet("background:transparent;")
        dds_col = QVBoxLayout(self._dds_widget)
        dds_col.setContentsMargins(0, 0, 0, 0)
        dds_col.setSpacing(4)

        # Body 1 – always shown when non-colorable
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

        # Body 2 – only shown for variant cars (non-colorable).
        # Wrapped in a QWidget so the whole block (label + row) can be
        # shown/hidden with a single setVisible() call.
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

        col.addWidget(self._dds_widget)

        #  PNG / COLORABLE SECTION
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
        self._clr_body1_lbl.setVisible(False)   # only shown for variants
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

        #  REFLECTIVITY MAP SECTION  (optional, applies to any skin type)
        rfl_row = QHBoxLayout()
        self._rfl_lbl = QLabel(t("project.reflectivity_map"))
        self._rfl_lbl.setFont(font(11, "bold"))
        self._rfl_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        rfl_row.addWidget(self._rfl_lbl)
        self._rfl_toggle = ToggleSwitch()
        self._rfl_toggle.stateChanged.connect(self._toggle_reflectivity_map)
        rfl_row.addWidget(self._rfl_toggle)
        rfl_row.addStretch()
        col.addLayout(rfl_row)

        self._rfl_widget = QWidget()
        self._rfl_widget.setStyleSheet("background:transparent;")
        self._rfl_widget.setVisible(False)
        rfl_col = QVBoxLayout(self._rfl_widget)
        rfl_col.setContentsMargins(0, 0, 0, 4)
        rfl_col.setSpacing(4)

        # "Normal Body" sublabel — only shown for variant cars
        self._rfl_body1_lbl = QLabel(t("project.normal_body"))
        self._rfl_body1_lbl.setFont(font(11, "bold"))
        self._rfl_body1_lbl.setStyleSheet(
            f"color:{COLORS['accent']};background:transparent;border:none;"
        )
        self._rfl_body1_lbl.setVisible(False)
        rfl_col.addWidget(self._rfl_body1_lbl)

        rfl_input_row = QHBoxLayout()
        self.rfl_entry = QLineEdit()
        self.rfl_entry.setPlaceholderText(t("common.nofile_selected"))
        self.rfl_entry.setReadOnly(True)
        self.rfl_entry.setFixedHeight(36)
        self.rfl_entry.setFont(font(12))
        self.rfl_entry.setStyleSheet(self._entry_style())
        rfl_input_row.addWidget(self.rfl_entry)
        self._rfl_browse = self._mk_btn(
            t("common.browse"), self._browse_rough_met,
            "primary", width=100, height=36, font_size=11
        )
        rfl_input_row.addWidget(self._rfl_browse)
        rfl_col.addLayout(rfl_input_row)

        # Variant body reflectivity map — only shown for variant cars
        self._rfl_section_2 = QWidget()
        self._rfl_section_2.setStyleSheet("background:transparent;")
        self._rfl_section_2.setVisible(False)
        rfl_sec2_col = QVBoxLayout(self._rfl_section_2)
        rfl_sec2_col.setContentsMargins(0, 6, 0, 0)
        rfl_sec2_col.setSpacing(4)
        self._rfl_body2_lbl = QLabel(t("project.variant_body"))
        self._rfl_body2_lbl.setFont(font(11, "bold"))
        self._rfl_body2_lbl.setStyleSheet(
            f"color:{COLORS['accent']};background:transparent;border:none;"
        )
        rfl_sec2_col.addWidget(self._rfl_body2_lbl)
        rfl_input_row_2 = QHBoxLayout()
        self.rfl_entry_2 = QLineEdit()
        self.rfl_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self.rfl_entry_2.setReadOnly(True)
        self.rfl_entry_2.setFixedHeight(36)
        self.rfl_entry_2.setFont(font(12))
        self.rfl_entry_2.setStyleSheet(self._entry_style())
        rfl_input_row_2.addWidget(self.rfl_entry_2)
        self._rfl_browse_2 = self._mk_btn(
            t("common.browse"), self._browse_rough_met_2,
            "primary", width=100, height=36, font_size=11
        )
        rfl_input_row_2.addWidget(self._rfl_browse_2)
        rfl_sec2_col.addLayout(rfl_input_row_2)
        rfl_col.addWidget(self._rfl_section_2)

        col.addWidget(self._rfl_widget)

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
        print(f"[DEBUG] refresh_project_display() called")
        while self._proj_layout.count():
            item = self._proj_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide(); w.setParent(None); w.deleteLater()

        try:
            search_query = self._project_search.text().lower().strip()
        except Exception:
            search_query = ""

        if not self.project_data["cars"]:
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
        print(f"[DEBUG] _build_car_row() called")
        base    = car_info.get("base_carid", car_id)
        variant = car_info.get("variant_suffix", "")
        name    = self._car_display_name(base, car_id)
        is_selected = (car_id == self.selected_car_for_skin)
        is_expanded = (car_id == self.expanded_car_id)

        container = QFrame()
        container.setStyleSheet("background:transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        skin_count   = len(car_info["skins"])
        display_text = name
        skin_word    = t("project.skin") if skin_count == 1 else t("project.skins")
        display_text += f"  •  {skin_count} {skin_word}"

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        car_btn = QPushButton(display_text)
        car_btn.setFont(font(13, "bold"))
        car_btn.setFixedHeight(38)
        car_btn.setCursor(Qt.PointingHandCursor)
        acc   = COLORS["accent"]      if is_selected else COLORS["card_bg"]
        acc_h = COLORS["accent_hover"] if is_selected else COLORS["card_hover"]
        txt   = COLORS["accent_text"]  if is_selected else COLORS["text"]
        car_btn.setStyleSheet(f"""
            QPushButton {{
                background:{acc};color:{txt};
                border-radius:8px;border:1px solid {COLORS['border']};
                padding:4px 10px;text-align:left;
            }}
            QPushButton:hover {{ background:{acc_h}; }}
        """)
        car_btn.clicked.connect(lambda checked=False, c=car_id:
                                 self._toggle_car_expansion(c))
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
        print(f"[DEBUG] _build_skin_row() called")
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
        print(f"[DEBUG] _car_display_name() called")
        for cid, cname in self.car_id_list:
            if cid == base_carid:
                # If this car_id has a variant suffix, append it to name
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
        """
        Add a vehicle (optionally a specific body variant) to the project.

        Parameters
        ----------
        carid          : Base vehicle ID (e.g. "pickup")
        display_name   : Human-readable label shown in UI
        variant_suffix : Body variant suffix ("" = normal, "ambulance", "box", etc.)
        """
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

        # Add the vehicle back to the sidebar
        try:
            mw = self.window()
            if mw and hasattr(mw, "sidebar"):
                mw.sidebar.restore_vehicle(base, variant)
        except Exception as e:
            print(f"[WARNING] sidebar.restore_vehicle failed: {e}")

    def _toggle_car_expansion(self, car_id: str):
        print(f"[DEBUG] _toggle_car_expansion() called")
        self.expanded_car_id = None if self.expanded_car_id == car_id else car_id
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

        # Update variant banner
        info    = self.project_data["cars"][car_id]
        variant = info.get("variant_suffix", "")
        dname   = info.get("display_name", self._car_display_name(
                            info.get("base_carid", car_id), car_id))
        if variant:
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

        # Update variant-specific UI visibility
        self._update_variant_ui()
        self.refresh_project_display()

    def _update_variant_ui(self):
        """Show/hide variant-specific file pickers based on selected car."""
        is_var  = self._is_variant()
        is_clr  = self._colorable_toggle.isChecked()

        # DDS section
        v_suffix = self._selected_variant_suffix()
        self._dds_label_1.setText(
            t("project.dds_texture_normal_body") if is_var else t("project.dds_texture")
        )
        # Toggle the whole second-body block (label + entry + browse button)
        # via its container widget — bare QHBoxLayouts can't be hidden.
        self._dds_section_2.setVisible(is_var and not is_clr)

        # Colorable section
        self._clr_body1_lbl.setVisible(is_var and is_clr)
        self._clr_body2_section.setVisible(is_var and is_clr)

        # Update variant suffix label
        if is_var:
            self._clr_body2_lbl.setText(t("project.variant_body_named", variant=v_suffix.capitalize()))

        # Show/hide body-2 preview labels
        if not is_var:
            self._dds_preview_2.setVisible(False)
            self._dds_preview_2.clear()
            self._color_map_preview_2.setVisible(False)
            self._color_map_preview_2.clear()

        # Update banner text when colorable changes
        if is_var and self._variant_banner.isVisible():
            requirements = t("project.variant_4_pngs") if is_clr else t("project.variant_2_dds")
            info  = self.project_data["cars"].get(self.selected_car_for_skin, {})
            dname = info.get("display_name", "")
            self._variant_banner.setText(
                t("project.variant_banner", name=dname, requirements=requirements, variant=v_suffix)
            )

        # Reflectivity map: body-1 sublabel + body-2 section track is_var
        self._rfl_body1_lbl.setVisible(is_var)
        self._rfl_section_2.setVisible(is_var)
        if is_var:
            self._rfl_body2_lbl.setText(
                t("project.variant_body_named", variant=v_suffix.capitalize())
            )
        if not is_var:
            self._rough_met_path_2 = ""
            self.rfl_entry_2.clear()


    def add_skin_to_selected_car(self):
        if self.editing_mode and self.selected_skin_index is not None:
            self.update_skin()
            return

        if not self.selected_car_for_skin:
            self.show_notification(t("project.notification.select_car"), "warning")
            return

        skin_name = self.skin_name_entry.text().strip()
        if not skin_name:
            self.show_notification(
                t("project.notification.please_skin_name"), "warning"
            )
            return

        _bad = _find_illegal_chars(skin_name)
        if _bad:
            self.show_notification(
                f"Skin name contains invalid character(s): {' '.join(_bad)}\n"
                f'Avoid: \\ / : * ? " < > |',
                "error", 6000,
            )
            return

        is_colorable = self._colorable_toggle.isChecked()
        is_var       = self._is_variant()

        if is_colorable:
            if not self._data_map_path:
                self.show_notification(
                    t("project.notification.please_select_datamap"), "warning"
                )
                return
            if not self._color_map_path:
                self.show_notification(
                    t("project.notification.please_select_colormap"), "warning"
                )
                return
            if is_var:
                # 4 PNGs required for variant colorable
                if not self._data_map_path_2:
                    self.show_notification(
                        t("project.notification.please_select_datamap_variant"), "warning"
                    )
                    return
                if not self._color_map_path_2:
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
                self.show_notification(
                    t("project.notification.please_select_dds"), "warning"
                )
                return
            if is_var and not self._dds_path_2:
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

        # Config data
        if self._config_toggle.isChecked():
            config_name = self._config_name_entry.text().strip()
            if not config_name:
                self.show_notification(
                    t("project.notification.please_config_name"), "warning"
                )
                return
            if not self._pc_file_path:
                self.show_notification(
                    t("project.notification.please_select_pc"), "warning"
                )
                return
            if not self._jpg_file_path:
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

        # Material properties
        if self._material_toggle.isChecked():
            mat = self._collect_material_properties()
            if mat:
                skin_data["material_properties"] = mat

        # Reflectivity map
        if self._rfl_toggle.isChecked():
            if not self._rough_met_path:
                self.show_notification(
                    "Please select a Reflectivity Map (rough_met.png).",
                    "warning",
                )
                return
            if is_var and not self._rough_met_path_2:
                self.show_notification(
                    "Please select a Variant Body Reflectivity Map (rough_met.png).",
                    "warning",
                )
                return
            skin_data["rough_met_path"] = self._rough_met_path
            if is_var:
                skin_data["rough_met_path_2"] = self._rough_met_path_2

        self.project_data["cars"][self.selected_car_for_skin]["skins"].append(skin_data)

        # ── Testing mode: broadcast skin to every other vehicle in project ─ #
        if state.testing_mode and len(self.project_data["cars"]) > 1:
            broadcast_count = 0
            for car_key, car_info in self.project_data["cars"].items():
                if car_key == self.selected_car_for_skin:
                    continue
                target_is_variant = bool(car_info.get("variant_suffix", ""))
                broadcast_skin = dict(skin_data)
                if target_is_variant:
                    # Variant cars need a second body slot (_2 paths).
                    # If the skin was authored for a non-variant car those are
                    # absent — mirror the primary paths so every slot is filled.
                    if broadcast_skin.get("is_colorable"):
                        if not broadcast_skin.get("data_map_path_2"):
                            broadcast_skin["data_map_path_2"] = broadcast_skin.get("data_map_path", "")
                        if not broadcast_skin.get("color_map_path_2"):
                            broadcast_skin["color_map_path_2"] = broadcast_skin.get("color_map_path", "")
                    else:
                        if not broadcast_skin.get("dds_path_2"):
                            broadcast_skin["dds_path_2"] = broadcast_skin.get("dds_path", "")
                    if not broadcast_skin.get("rough_met_path_2"):
                        broadcast_skin["rough_met_path_2"] = broadcast_skin.get("rough_met_path", "")
                else:
                    # Non-variant cars only have one body — strip variant slots.
                    broadcast_skin.pop("dds_path_2",       None)
                    broadcast_skin.pop("data_map_path_2",  None)
                    broadcast_skin.pop("color_map_path_2", None)
                    broadcast_skin.pop("rough_met_path_2", None)
                # Skip if this car already has a skin with the same name
                existing_names = {s.get("name") for s in car_info["skins"]}
                if broadcast_skin["name"] not in existing_names:
                    car_info["skins"].append(broadcast_skin)
                    broadcast_count += 1
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
            self.selected_car_for_skin = car_id
            self.refresh_project_display()

    def remove_skin_from_car(self, car_id: str, skin_idx: int):
        if car_id in self.project_data["cars"]:
            skins = self.project_data["cars"][car_id]["skins"]
            if 0 <= skin_idx < len(skins):
                name = skins[skin_idx]["name"]
                del skins[skin_idx]
                self.show_notification(
                    f"{t('project.notification.removed_skin')} '{name}'", "info"
                )
                self.refresh_project_display()

    def select_skin_for_editing(self, car_id: str, skin_idx: int):
        if car_id not in self.project_data["cars"]:
            return
        skins = self.project_data["cars"][car_id]["skins"]
        if not (0 <= skin_idx < len(skins)):
            return

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
            # variant body 2
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
            # variant body 2
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
        else:
            self._config_toggle.setChecked(False)
            self._toggle_config_data()

        if "material_properties" in skin:
            self._material_toggle.setChecked(True)
            self._toggle_material_properties()
            self._load_material_properties_into_ui(skin["material_properties"])
        else:
            self._material_toggle.setChecked(False)
            self._toggle_material_properties()

        if "rough_met_path" in skin:
            self._rfl_toggle.setChecked(True)
            self._toggle_reflectivity_map()
            self._rough_met_path = skin["rough_met_path"]
            self.rfl_entry.setText(os.path.basename(self._rough_met_path))
            self._rough_met_path_2 = skin.get("rough_met_path_2", "")
            self.rfl_entry_2.setText(os.path.basename(self._rough_met_path_2))
        else:
            self._rfl_toggle.setChecked(False)
            self._toggle_reflectivity_map()

        self._add_skin_label.setVisible(True)
        self._skin_card.setVisible(True)
        self._update_variant_ui()
        self.refresh_project_display()
        self.show_notification(t("project.notification.editing_skin", name=skin["name"]), "info")

    def update_skin(self):
        if not self.editing_mode or self.selected_skin_index is None:
            return
        if self.selected_car_for_skin not in self.project_data["cars"]:
            self.cancel_skin_editing()
            return

        skin_name    = self.skin_name_entry.text().strip()
        is_colorable = self._colorable_toggle.isChecked()
        is_var       = self._is_variant()

        if not skin_name:
            self.show_notification(t("project.notification.skin_name_required"), "error")
            return

        _bad = _find_illegal_chars(skin_name)
        if _bad:
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
        else:
            skin.pop("config_data", None)

        if self._material_toggle.isChecked():
            mat = self._collect_material_properties()
            if mat:
                skin["material_properties"] = mat
        else:
            skin.pop("material_properties", None)

        if self._rfl_toggle.isChecked():
            if not self._rough_met_path:
                self.show_notification(
                    "Please select a Reflectivity Map (rough_met.png).",
                    "warning",
                )
                return
            if is_var and not self._rough_met_path_2:
                self.show_notification(
                    "Please select a Variant Body Reflectivity Map (rough_met.png).",
                    "warning",
                )
                return
            skin["rough_met_path"] = self._rough_met_path
            if is_var:
                skin["rough_met_path_2"] = self._rough_met_path_2
            else:
                skin.pop("rough_met_path_2", None)
        else:
            skin.pop("rough_met_path",   None)
            skin.pop("rough_met_path_2", None)

        self.show_notification(t("project.notification.updated_skin", name=skin_name), "success")
        self.cancel_skin_editing()

    def cancel_skin_editing(self):
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
            (self.rfl_entry,          None),
            (self.rfl_entry_2,        None),
        ]:
            try:
                widget.clear()
            except Exception:
                pass

        self._dds_path        = ""
        self._dds_path_2      = ""
        self._data_map_path   = ""
        self._color_map_path  = ""
        self._data_map_path_2 = ""
        self._color_map_path_2= ""
        self._pc_file_path    = ""
        self._jpg_file_path   = ""
        self._rough_met_path  = ""
        self._rough_met_path_2= ""

        try:
            self._dds_preview.setVisible(False)
            self._dds_preview.clear()
        except Exception:
            pass
        try:
            self._color_map_preview.setVisible(False)
            self._color_map_preview.clear()
        except Exception:
            pass
        try:
            self._dds_preview_2.setVisible(False)
            self._dds_preview_2.clear()
        except Exception:
            pass
        try:
            self._color_map_preview_2.setVisible(False)
            self._color_map_preview_2.clear()
        except Exception:
            pass

        for toggle in (self._colorable_toggle, self._config_toggle, self._material_toggle, self._rfl_toggle):
            try:
                toggle.blockSignals(True)
                toggle.setChecked(False)
                toggle.blockSignals(False)
            except Exception:
                pass

        self._toggle_colorable()
        self._toggle_config_data()
        self._toggle_material_properties()
        self._update_variant_ui()

        while self._mat_props_layout.count():
            item = self._mat_props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.material_properties_entries.clear()


    def browse_dds(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_dds"), "", "DDS files (*.dds);;All files (*.*)"
        )
        if path:
            self._dds_path = path
            self.dds_entry.setText(os.path.basename(path))
            self._load_preview(path, self._dds_preview)

    def browse_dds_2(self):
        """Browse for the second (variant body) DDS texture."""
        print(f"[DEBUG] _update_variant_ui() called")
        v_suffix = self._selected_variant_suffix()
        title = t("project.dialog_select_dds_variant", variant=v_suffix.capitalize())
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "DDS files (*.dds);;All files (*.*)"
        )
        if path:
            self._dds_path_2 = path
            self.dds_entry_2.setText(os.path.basename(path))
            self._load_preview(path, self._dds_preview_2)

    def _get_vehicle_browse_dir(self) -> str:
        """
        Return the best initial directory for config-related file dialogs.

        Logic:
          1. Fetch the saved mods folder (e.g. …/BeamNG.drive/current/mods).
          2. Derive the sibling ``vehicles`` folder by replacing the last
             ``mods`` path component with ``vehicles``.
          3. Append the base car-id of the currently selected vehicle.
          4. Return that path if it exists on disk, otherwise fall back to
             the bare ``vehicles`` folder, then the ``mods`` folder, then "".
        """
        mods_path = _get_mods_folder_path()
        print(f"[DEBUG] _get_vehicle_browse_dir: mods_path={mods_path!r}")
        if not mods_path or not os.path.isdir(mods_path):
            return ""

        # …/current/mods  →  …/current/vehicles
        parent       = os.path.dirname(mods_path)
        vehicles_dir = os.path.join(parent, "vehicles")
        print(f"[DEBUG] _get_vehicle_browse_dir: vehicles_dir={vehicles_dir!r}  exists={os.path.isdir(vehicles_dir)}")

        # Resolve the base car-id for the currently selected project key.
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
        print(f"[DEBUG] _browse_pc_file() called")
        init_dir = self._get_vehicle_browse_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_pc"), init_dir, "PC files (*.pc);;All files (*.*)"
        )
        if path:
            self._pc_file_path = path
            self.pc_file_entry.setText(os.path.basename(path))

    def _browse_jpg_file(self):
        print(f"[DEBUG] _browse_jpg_file() called")
        init_dir = self._get_vehicle_browse_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_jpg"), init_dir,
            "JPG files (*.jpg);;JPEG files (*.jpeg);;All files (*.*)"
        )
        if path:
            self._jpg_file_path = path
            self.jpg_file_entry.setText(os.path.basename(path))

    def _browse_data_map(self):
        print(f"[DEBUG] _browse_data_map() called")
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_base_color_map"), "", "PNG files (*.png);;All files (*.*)"
        )
        if path:
            self._data_map_path = path
            self.data_map_entry.setText(os.path.basename(path))
            self._load_preview(path, self._dds_preview)

    def _browse_color_map(self):
        print(f"[DEBUG] _browse_color_map() called")
        path, _ = QFileDialog.getOpenFileName(
            self, t("project.dialog_select_color_palette"), "", "PNG files (*.png);;All files (*.*)"
        )
        if path:
            self._color_map_path = path
            self.color_map_entry.setText(os.path.basename(path))
            self._load_preview(path, self._color_map_preview)

    def _browse_data_map_2(self):
        print(f"[DEBUG] _browse_data_map_2() called")
        v_suffix = self._selected_variant_suffix()
        title = t("project.dialog_select_base_color_map_v", variant=v_suffix.capitalize())
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "PNG files (*.png);;All files (*.*)"
        )
        if path:
            self._data_map_path_2 = path
            self.data_map_entry_2.setText(os.path.basename(path))
            self._load_preview(path, self._dds_preview_2)

    def _browse_color_map_2(self):
        print(f"[DEBUG] _browse_color_map_2() called")
        v_suffix = self._selected_variant_suffix()
        title = t("project.dialog_select_color_palette_v", variant=v_suffix.capitalize())
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "PNG files (*.png);;All files (*.*)"
        )
        if path:
            self._color_map_path_2 = path
            self.color_map_entry_2.setText(os.path.basename(path))
            self._load_preview(path, self._color_map_preview_2)

    def _browse_rough_met(self):
        print(f"[DEBUG] _browse_rough_met() called")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reflectivity Map (rough_met.png)",
            "",
            "PNG files (*.png);;All files (*.*)",
        )
        if path:
            self._rough_met_path = path
            self.rfl_entry.setText(os.path.basename(path))

    def _browse_rough_met_2(self):
        print(f"[DEBUG] _browse_rough_met_2() called")
        v_suffix = self._selected_variant_suffix()
        title = (
            "Select Variant Body Reflectivity Map"
            + (f" ({v_suffix.capitalize()} rough_met.png)" if v_suffix else "")
        )
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "PNG files (*.png);;All files (*.*)",
        )
        if path:
            self._rough_met_path_2 = path
            self.rfl_entry_2.setText(os.path.basename(path))

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
        # Respect the "Texture Previews" setting from Settings tab
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
        print(f"[DEBUG] _toggle_config_data() called")
        on = self._config_toggle.isChecked()
        self._config_name_lbl.setVisible(on)
        self._config_name_entry.setVisible(on)
        self._config_type_lbl.setVisible(on)
        self._config_type_combo.setVisible(on)
        self._config_files_widget.setVisible(on)

    def _toggle_colorable(self):
        print(f"[DEBUG] _toggle_colorable() called")
        on      = self._colorable_toggle.isChecked()
        is_var  = self._is_variant()
        self._dds_widget.setVisible(not on)
        self._colorable_widget.setVisible(on)
        if not on:
            self._color_map_preview.setVisible(False)
            self._color_map_preview.clear()
        self._update_variant_ui()

    def _toggle_reflectivity_map(self):
        print(f"[DEBUG] _toggle_reflectivity_map() called")
        on = self._rfl_toggle.isChecked()
        self._rfl_widget.setVisible(on)
        if not on:
            self._rough_met_path   = ""
            self._rough_met_path_2 = ""
            self.rfl_entry.clear()
            self.rfl_entry_2.clear()
        else:
            self._update_variant_ui()

    def _toggle_material_properties(self):
        print(f"[DEBUG] _toggle_material_properties() called")
        on = self._material_toggle.isChecked()
        if on:
            if not self.selected_car_for_skin:
                self.show_notification(t("project.notification.select_car_first"), "warning")
                self._material_toggle.setChecked(False)
                return
            car_info = self.project_data["cars"][self.selected_car_for_skin]
            base = car_info.get("base_carid", self.selected_car_for_skin)
            variant_suffix = car_info.get("variant_suffix", "")
            materials = self._load_material_structure(base, variant_suffix)
            if not materials:
                self.show_notification(
                    t("project.notification.no_material_properties"), "warning"
                )
                self._material_toggle.setChecked(False)
                return
            self._populate_material_properties_ui(materials)
        self._material_props_widget.setVisible(on)


    def _populate_material_properties_ui(self, materials: Dict):
        print(f"[DEBUG] _populate_material_properties_ui() called")
        while self._mat_props_layout.count():
            item = self._mat_props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.material_properties_entries.clear()

        hdr = QLabel(t("project.material_properties"))
        hdr.setFont(font(12, "bold"))
        hdr.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        self._mat_props_layout.addWidget(hdr)

        info = QLabel(t("project.material_values_hint"))
        info.setFont(font(10))
        info.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        self._mat_props_layout.addWidget(info)

        for mat_name, mat_info in materials.items():
            part  = mat_info["part_name"]
            props = mat_info["properties"]

            sect = QFrame()
            sect.setStyleSheet(
                f"QFrame{{background:{COLORS.get('sidebar_bg',COLORS['frame_bg'])};"
                "border-radius:6px;}}"
            )
            sc = QVBoxLayout(sect)
            sc.setContentsMargins(10, 8, 10, 8)
            sc.setSpacing(4)

            hl = QLabel(f"📦 {part}")
            hl.setFont(font(15, "bold"))
            hl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
            sc.addWidget(hl)

            tl = QLabel(f"({mat_name})")
            tl.setFont(font(11))
            tl.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;border:none;"
            )
            sc.addWidget(tl)

            self.material_properties_entries[mat_name] = {}

            for stage_key, stage_props in props.items():
                if len(props) > 1:
                    sl = QLabel(f"Stage {stage_key.split('_')[1]}")
                    sl.setFont(font(10, "bold"))
                    sl.setStyleSheet(
                        f"color:{COLORS['text_secondary']};background:transparent;border:none;"
                    )
                    sc.addWidget(sl)

                for prop_name, prop_value in stage_props.items():
                    pr = QHBoxLayout()
                    label_text = (prop_name.replace("Factor", "")
                                  .replace("clearCoat", "Clear Coat ")
                                  .replace("metallic", "Metallic")
                                  .replace("roughness", "Roughness"))
                    pl = QLabel(f"{label_text}:")
                    pl.setFont(font(12, "bold"))
                    pl.setFixedWidth(140)
                    pl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
                    pr.addWidget(pl)

                    pe = QLineEdit()
                    pe.setPlaceholderText(t("project.material_value_placeholder"))
                    pe.setFixedWidth(100)
                    pe.setFixedHeight(28)
                    pe.setFont(font(11))
                    pe.setStyleSheet(self._entry_style())
                    pe.setText("null" if prop_value is None else str(prop_value))
                    pr.addWidget(pe)
                    pr.addStretch()

                    w = QWidget()
                    w.setStyleSheet("background:transparent;")
                    w.setLayout(pr)
                    sc.addWidget(w)

                    entry_key = f"{stage_key}_{prop_name}"
                    self.material_properties_entries[mat_name][entry_key] = pe

            self._mat_props_layout.addWidget(sect)

    def _collect_material_properties(self) -> Dict:
        print(f"[DEBUG] _collect_material_properties() called")
        result = {}
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
                        stages.setdefault(stage_num, {})[prop_name] = nv
                    except ValueError:
                        self.show_notification(
                            t("project.notification.invalid_material_value",
                              prop_name=prop_name, value=val), "warning"
                        )
            if stages:
                result[mat_name] = stages
        return result

    def _load_material_properties_into_ui(self, mat_props: Dict):
        print(f"[DEBUG] _load_material_properties_into_ui() called")
        for mat_name, stages in mat_props.items():
            if mat_name not in self.material_properties_entries:
                continue
            entries = self.material_properties_entries[mat_name]
            for stage_num, properties in stages.items():
                for prop_name, val in properties.items():
                    key = f"stage_{stage_num}_{prop_name}"
                    if key in entries:
                        entries[key].setText("null" if val is None else str(val))


    def _load_material_structure(self, car_id: str, variant_suffix: str = "") -> Dict:
        print(f"[DEBUG] _load_material_structure() called")
        import re

        def _folder_matches_variant(folder_name: str, suffix: str) -> bool:
            """
            Template folders are named SKINNAME / skinname (default variant) or
            SKINNAMEAMBULANCE / skinnameambulance (named variant).
            Strip 'skinname' (case-insensitive) and compare the remainder to
            the desired suffix so each variant gets its own material file.
            """
            name_lower = folder_name.lower()
            if "skinname" not in name_lower:
                return False
            remainder = name_lower.replace("skinname", "", 1)
            return remainder == suffix.lower()

        search_paths = []
        for base in [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]:
            vp = os.path.join(base, "vehicles", car_id)
            if os.path.exists(vp):
                for item in os.listdir(vp):
                    ip = os.path.join(vp, item)
                    if os.path.isdir(ip) and _folder_matches_variant(item, variant_suffix):
                        search_paths.append(ip)
                break
        try:
            from core.settings import get_beamng_path
            bp = get_beamng_path()
            search_paths += [
                os.path.join(bp, "vehicles", car_id, "skins"),
                os.path.join(bp, "vehicles", car_id),
            ]
        except Exception:
            pass

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
                except Exception:
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
                    return material_data
        return material_data


    def save_project(self):
        print(f"[DEBUG] save_project: called")
        print(f"[DEBUG] save_project: cars in project={list(self.project_data.get('cars', {}).keys())}")

        if not self.project_data["cars"]:
            print(f"[DEBUG] save_project: no cars in project — aborting")
            self.show_notification(t("project.notification.no_cars_save"), "warning")
            return

        mod_name = (self.mod_name_entry_sidebar.text().strip()
                    if self.mod_name_entry_sidebar else "")
        author   = (self.author_entry_sidebar.text().strip()
                    if self.author_entry_sidebar else "")
        print(f"[DEBUG] save_project: mod_name={mod_name!r} author={author!r}")

        self.project_data["mod_name"] = mod_name
        self.project_data["author"]   = author or "Unknown"

        if self._current_project_path:
            # Project was loaded from (or previously saved to) a file — overwrite it directly.
            path = self._current_project_path
            print(f"[DEBUG] save_project: overwriting existing project file at {path!r}")
        else:
            # New unsaved project — open dialog with mod name pre-filled as filename.
            import re
            safe_name = re.sub(r'[\\/*?:"<>|]', "_", mod_name) if mod_name else ""
            default_filename = f"{safe_name}.json" if safe_name else ""
            print(f"[DEBUG] save_project: opening save file dialog (default={default_filename!r})")
            path, _ = QFileDialog.getSaveFileName(
                self, t("project.dialog_save_project"),
                default_filename,
                "JSON files (*.json);;All files (*.*)"
            )
            print(f"[DEBUG] save_project: user chose path={path!r}")

        if not path:
            print(f"[DEBUG] save_project: cancelled — no path chosen")
            return

        try:
            print(f"[DEBUG] save_project: writing JSON to {path!r}")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.project_data, f, indent=2)
            print(f"[DEBUG] save_project: write successful")
            self._current_project_path = path   # future saves overwrite this file directly

            ### register in the project registry
            try:
                print(f"[DEBUG] save_project: calling _reg_add with path={path!r}")
                _reg_add(path, self.project_data)
                print(f"[DEBUG] save_project: registry update OK")
            except Exception as _reg_exc:
                print(f"[WARN] save_project: registry update failed: {_reg_exc}")

            self.show_notification(
                t("project.notification.project_saved_to", filename=os.path.basename(path)), "success"
            )
            print(f"[DEBUG] save_project: done")

        except Exception as e:
            print(f"[DEBUG] save_project: ERROR writing file: {e}")
            self.show_notification(t("project.notification.save_error", error=e), "error")

    def load_project(self):
        print(f"[DEBUG] load_project: called")
        path: Optional[str] = None

        ### open browser dialog if available, else fall back to raw file dialog
        if ProjectBrowserDialog is not None:
            print(f"[DEBUG] load_project: opening ProjectBrowserDialog")
            dlg    = ProjectBrowserDialog(self.window())
            result = dlg.exec()
            print(f"[DEBUG] load_project: dialog result={result} selected_path={dlg.selected_path!r}")

            if not result:
                print(f"[DEBUG] load_project: dialog cancelled — returning early")
                return

            path = dlg.selected_path
        else:
            print(f"[DEBUG] load_project: ProjectBrowserDialog unavailable — using raw QFileDialog")
            path, _ = QFileDialog.getOpenFileName(
                self, t("project.dialog_load_project"), "", "JSON files (*.json);;All files (*.*)"
            )
            print(f"[DEBUG] load_project: raw dialog chose path={path!r}")

        if not path:
            print(f"[DEBUG] load_project: no path selected — returning early")
            return

        self._current_project_path = path   # enables direct overwrite on next save
        print(f"[DEBUG] load_project: reading project file from {path!r}")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            print(f"[DEBUG] load_project: JSON read OK — top-level keys={list(data.keys())}")

            if "cars" not in data:
                print(f"[DEBUG] load_project: 'cars' key missing — invalid project file")
                self.show_notification(t("project.notification.invalid_project"), "error")
                return

            print(f"[DEBUG] load_project: cars={list(data['cars'].keys())}")

            self.project_data          = data
            self.selected_car_for_skin = None
            self.editing_mode          = False
            self.selected_skin_index   = None
            print(f"[DEBUG] load_project: project_data assigned, selection state reset")

            try:
                self._update_button_ui()
                print(f"[DEBUG] load_project: _update_button_ui OK")
            except Exception as e:
                print(f"[DEBUG] load_project: _update_button_ui failed: {e}")
            try:
                self._reset_skin_form_fields()
                print(f"[DEBUG] load_project: _reset_skin_form_fields OK")
            except Exception as e:
                print(f"[DEBUG] load_project: _reset_skin_form_fields failed: {e}")
            try:
                self._skin_card.setVisible(False)
                self._add_skin_label.setVisible(False)
                self._variant_banner.setVisible(False)
                print(f"[DEBUG] load_project: UI visibility reset OK")
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
                    print(f"[DEBUG] load_project: mod_name sidebar entry set")
            except Exception as e:
                print(f"[DEBUG] load_project: failed to set mod_name sidebar entry: {e}")
            try:
                if self.author_entry_sidebar is not None:
                    _set_entry(self.author_entry_sidebar, author)
                    print(f"[DEBUG] load_project: author sidebar entry set")
            except Exception as e:
                print(f"[DEBUG] load_project: failed to set author sidebar entry: {e}")

            ### register the opened file in the project registry
            try:
                print(f"[DEBUG] load_project: calling _reg_add to register loaded path")
                _reg_add(path, self.project_data)
                print(f"[DEBUG] load_project: registry update OK")
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
                print(f"[DEBUG] load_project._deferred_refresh: calling refresh_project_display")
                try:
                    self.refresh_project_display()
                    print(f"[DEBUG] load_project._deferred_refresh: OK")
                except Exception as e:
                    print(f"[DEBUG] load_project._deferred_refresh: failed: {e}")

            QTimer.singleShot(100, _deferred_refresh)

            def _deferred_sidebar():
                print(f"[DEBUG] load_project._deferred_sidebar: repopulating sidebar")
                try:
                    mw = self.window()
                    print(f"[DEBUG] load_project._deferred_sidebar: mw={mw} has_sidebar={hasattr(mw, 'sidebar')}")
                    if mw is not None and hasattr(mw, "sidebar"):
                        mw.sidebar.populate_vehicles(mw._add_vehicle_from_sidebar)
                        print(f"[DEBUG] load_project._deferred_sidebar: sidebar repopulated OK")
                except Exception as e:
                    print(f"[DEBUG] load_project._deferred_sidebar: failed: {e}")

            QTimer.singleShot(150, _deferred_sidebar)
            print(f"[DEBUG] load_project: deferred callbacks scheduled — done")

        except Exception as e:
            print(f"[ERROR] load_project: unhandled exception: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification(t("project.notification.load_error", error=e), "error")

    def clear_project(self):
        print(f"[DEBUG] clear_project: requesting project clear confirmation")
        if not self.project_data["cars"]:
            self.show_notification(t("project.notification.already_empty"), "info")
            return
        try:
            from gui.confirmation_dialog import DangerConfirmationDialog
        except ImportError:
            from gui.components.confirmation_dialog import DangerConfirmationDialog

        dlg = DangerConfirmationDialog(
            self.window(),
            t("project.clear_project_window.clear_project_confirm_title"),
            t("project.clear_project_window.clear_project_confirm_message"),
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
        self._current_project_path = None   # cleared project is no longer tied to any file
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

        # Repopulate the sidebar with all vehicles now that the project is empty
        try:
            mw = self.window()
            if mw and hasattr(mw, "sidebar") and hasattr(mw, "_add_vehicle_from_sidebar"):
                mw.sidebar.populate_vehicles(mw._add_vehicle_from_sidebar)
        except Exception as e:
            print(f"[WARNING] sidebar repopulate after clear failed: {e}")


    def generate_mod(self, generate_button, output_mode_combo=None, custom_output_var=None, unpacked: bool = False):
        print(f"[DEBUG] generate_mod: output_mode={output_mode_combo!r} unpacked={unpacked}")
        if not self.mod_name_entry_sidebar or not self.author_entry_sidebar:
            self.show_notification(t("project.notification.sidebar_error"), "error")
            return

        mod_name = self.mod_name_entry_sidebar.text().strip()
        author   = self.author_entry_sidebar.text().strip()

        if not mod_name:
            self.show_notification(t("project.notification.no_zip_name"), "error")
            return
        if not author:
            self.show_notification(t("project.notification.no_author_name"), "error")
            return
        if not self.project_data["cars"]:
            self.show_notification(t("project.notification.please_add_vehicle"), "error")
            return

        missing = []
        total_skins = 0
        for carid, car_info in self.project_data["cars"].items():
            if not car_info["skins"]:
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

        if missing:
            self.show_notification(
                t("project.notification.missing_files", files="\n".join(missing[:5])),
                "error", 6000
            )
            return

        output_mode = output_mode_combo or "default"
        if output_mode == "custom":
            output_path = (custom_output_var or "").strip()
            if not output_path:
                self.show_notification(
                    t("project.notification.please_select_custom_output"), "error"
                )
                return
        elif output_mode == "steam":
            try:
                from core.settings import get_mods_folder_path
                mods_folder = get_mods_folder_path()
                if not mods_folder or not os.path.exists(mods_folder):
                    self.show_notification(
                        t("project.notification.mod_folder_not_exist") +
                        f" {mods_folder}", "error", 4000
                    )
                    return
                # When unpacked, output to the game's built-in unpacked subfolder
                if unpacked:
                    output_path = os.path.join(mods_folder, "unpacked")
                    os.makedirs(output_path, exist_ok=True)
                else:
                    output_path = mods_folder
            except Exception:
                self.show_notification(
                    t("project.notification.load_settings_failed"), "error"
                )
                return
        else:
            output_path = None

        # ── overwrite check ────────────────────────────────────────────────────
        # Mirrors the path logic in file_ops.generate_multi_skin_mod so we can
        # detect a collision *on the main thread* and ask the user before the
        # background worker even starts.  If the user confirms, we remove the
        # old file/folder here so file_ops won't raise FileExistsError.
        try:
            from core.file_ops import (
                get_beamng_mods_path   as _get_mods_path,
                sanitize_mod_name      as _sanitize_mod_name,
            )
        except ImportError:
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
                    return
                # Delete now so file_ops won't hit FileExistsError mid-thread.
                try:
                    if os.path.isdir(_conflict_path):
                        import shutil as _shutil
                        _shutil.rmtree(_conflict_path)
                    else:
                        os.remove(_conflict_path)
                    print(f"[DEBUG] generate_mod: removed existing output: {_conflict_path}")
                except Exception as _rm_err:
                    self.show_notification(
                        t("project.notification.overwrite_failed",
                          error=_rm_err,
                          default=f"Could not remove existing mod: {_rm_err}"),
                        "error", 5000,
                    )
                    return
        # ── end overwrite check ────────────────────────────────────────────────

        self.project_data["mod_name"] = mod_name
        self.project_data["author"]   = author

        self._export_status.setText(t("project.export_preparing"))
        self._export_status.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        generate_button.setEnabled(False)
        # Store so _on_generate_done (main thread) can re-enable it safely.
        self._pending_generate_button = generate_button

        def _update_status(msg: str):
            self._status_signal.emit(msg)

        def _update_progress(value: float):
            self._progress_signal.emit(int(value * 100))

        def _notify_safe(msg: str, kind: str = "info", dur: int = 3000):
            QTimer.singleShot(0, lambda: self.show_notification(msg, kind, dur))

        def _thread_fn():
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
                    _update_status(t("project.export_complete"))
                    _notify_safe(
                        t("project.notification.multi_skin_mod").format(
                            mod_name=mod_name, total_skins=total_skins
                        ),
                        "success", 5000
                    )
                else:
                    _update_status(t("project.export_error"))
                    _notify_safe(
                        t("project.notification.mod_generation_unavailable"),
                        "error", 7000
                    )
            except FileExistsError as exc:
                import traceback; traceback.print_exc()
                first_line = str(exc).split("\n")[0]
                _update_status(f"Error: {first_line}")
                _notify_safe(str(exc), "error", 9000)
            except FileNotFoundError as exc:
                import traceback; traceback.print_exc()
                _update_status(f"Error: {exc}")
                _notify_safe(
                    t("project.notification.file_not_found_hint", error=exc),
                    "error", 9000
                )
            except Exception as exc:
                import traceback; traceback.print_exc()
                _update_status(f"Export failed — {type(exc).__name__}: {exc}")
                _notify_safe(
                    t("project.notification.export_error_debug",
                      type=type(exc).__name__, error=exc),
                    "error", 7000
                )
            finally:
                # Do NOT call QTimer.singleShot from a background thread —
                # it is not thread-safe and will silently fail to fire.
                # Button re-enablement is handled in _on_generate_done(),
                # which runs on the main thread via the queued _done_signal.
                self._done_signal.emit(_success)

        threading.Thread(target=_thread_fn, daemon=True).start()


    def refresh_ui(self):
        print(f"[DEBUG] refresh_ui() called")
        self._proj_hdr_lbl.setText(t("project.project_overview"))
        self._save_btn.setText(t("project.save_project"))
        self._load_btn.setText(t("project.load_project"))
        self._clear_btn.setText(t("project.clear_project"))
        self._veh_lbl.setText(t("project.vehicles_in_project"))
        self._project_search.setPlaceholderText(t("common.search_vehicle"))
        self._add_skin_label.setText(
            t("project.add_skins_header", default="Add Skins to Selected Car")
        )

        # skin form — skin name label + placeholder
        self._skin_name_lbl.setText(t("project.skin_name"))
        self.skin_name_entry.setPlaceholderText(t("project.skin_name_placeholder"))

        # toggle labels
        self._cfg_lbl.setText(t("project.add_config_data"))
        self._mat_lbl.setText(t("project.edit_materials"))
        self._clr_lbl.setText(t("project.colorable"))

        # config fields
        self._config_name_lbl.setText(t("project.config_name"))
        self._config_name_entry.setPlaceholderText(t("project.config_name_placeholder"))
        self._config_type_lbl.setText(t("project.type"))

        # config file section labels + placeholders
        self._pc_file_lbl.setText(t("project.pc_file"))
        self.pc_file_entry.setPlaceholderText(t("common.nofile_selected"))
        self._pc_browse.setText(t("common.browse"))
        self._jpg_file_lbl.setText(t("project.jpg_file"))
        self.jpg_file_entry.setPlaceholderText(t("common.nofile_selected"))
        self._jpg_browse.setText(t("common.browse"))

        # DDS section labels + placeholders
        self._dds_label_1.setText(t("project.dds_texture"))
        self.dds_entry.setPlaceholderText(t("common.nofile_selected"))
        self._dds_browse.setText(t("common.browse"))
        self._dds_label_2.setText(t("project.dds_texture_variant_body"))
        self.dds_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self._dds_browse_2.setText(t("common.browse"))

        # colorable section labels + placeholders (body 1)
        self._clr_body1_lbl.setText(t("project.normal_body"))
        self._base_color_map_lbl_1.setText(t("project.base_Color_Map"))
        self.data_map_entry.setPlaceholderText(t("common.nofile_selected"))
        self._dm_browse.setText(t("common.browse"))
        self._color_palette_map_lbl_1.setText(t("project.color_Palette_Map"))
        self.color_map_entry.setPlaceholderText(t("common.nofile_selected"))
        self._cm_browse.setText(t("common.browse"))

        # colorable section labels + placeholders (body 2 / variant)
        self._clr_body2_lbl.setText(t("project.variant_body"))
        self._base_color_map_lbl_2.setText(t("project.base_Color_Map"))
        self.data_map_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self._dm2_browse.setText(t("common.browse"))
        self._color_palette_map_lbl_2.setText(t("project.color_Palette_Map"))
        self.color_map_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self._cm2_browse.setText(t("common.browse"))

        # action buttons
        self.add_skin_btn.setText(t("project.add_skin"))
        self.cancel_edit_btn.setText(t("project.cancel_edit"))

        # reflectivity map section
        self._rfl_lbl.setText(t("project.reflectivity_map"))
        self.rfl_entry.setPlaceholderText(t("common.nofile_selected"))
        self._rfl_browse.setText(t("common.browse"))
        self._rfl_body1_lbl.setText(t("project.normal_body"))
        self._rfl_body2_lbl.setText(t("project.variant_body"))
        self.rfl_entry_2.setPlaceholderText(t("common.nofile_selected"))
        self._rfl_browse_2.setText(t("common.browse"))

        # variant banner — always re-render in new language when a car is selected,
        # regardless of current visibility (banner may be shown later with stale text)
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

