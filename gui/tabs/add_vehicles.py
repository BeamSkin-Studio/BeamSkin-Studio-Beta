
from __future__ import annotations

import os
import shutil
from typing import Optional, List

from PySide6.QtCore    import Qt, Signal, QTimer, QThread
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QCheckBox,
    QVBoxLayout, QHBoxLayout, QScrollArea, QTabWidget,
    QFileDialog,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import GhostButton
from gui.state   import state

try:
    from core.localization import t
except Exception as _e:
    import traceback
    print(f"[WARNING] add_vehicles tab: localization unavailable ({type(_e).__name__}: {_e})")
    traceback.print_exc()
    def t(key, **kw): return key

try:
    from core.add_vehicles import (
        process_custom_vehicle,
        delete_custom_vehicle,
        process_custom_variant,
        delete_custom_variant,
    )
    from utils.file_ops import (
        load_added_vehicles_json,
        load_added_variants_json,
    )
    _BACKEND_OK = True
except Exception as _e:
    import traceback
    print(f"[ERROR] add_vehicles tab: backend import failed: {type(_e).__name__}: {_e}")
    traceback.print_exc()
    _BACKEND_OK = False

try:
    from core.mod_scanner import scan_mod, DiscoveredVehicle, DiscoveredVariant
    _SCANNER_OK = True
    _SCANNER_IMPORT_ERROR = None
except Exception as _e:
    import traceback
    _SCANNER_OK = False
    _SCANNER_IMPORT_ERROR = _e
    print(f"[ERROR] add_vehicles tab: mod_scanner import failed: "
          f"{type(_e).__name__}: {_e}")
    traceback.print_exc()

try:
    from core.settings import get_mods_folder_path as _get_mods_folder_path
except Exception as _e:
    import traceback
    print(f"[WARNING] add_vehicles tab: settings unavailable ({type(_e).__name__}: {_e})")
    traceback.print_exc()
    def _get_mods_folder_path(): return ""


def _mods_start_dir() -> str:
    p = _get_mods_folder_path()
    return p if p and os.path.isdir(p) else ""


def _carid_exists(carid: str) -> bool:
    builtin = state.vehicle_ids
    if carid in builtin:
        return True
    if _BACKEND_OK:
        added = load_added_vehicles_json()
        if carid in added:
            return True
    return False


def _copy_uv_maps_to_images(carid: str, uv_map_paths: list) -> None:
    if not uv_map_paths:
        return
    _gui_dir  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dest_dir  = os.path.join(_gui_dir, "images", "vehicles", carid)
    os.makedirs(dest_dir, exist_ok=True)
    for src in uv_map_paths:
        try:
            dest = os.path.join(dest_dir, os.path.basename(src))
            if not os.path.exists(dest):
                shutil.copy2(src, dest)
                print(f"[add_vehicles] Copied UV map: {os.path.basename(src)} → {dest_dir}")
        except Exception as e:
            print(f"[WARNING] _copy_uv_maps_to_images: could not copy {src}: {e}")


def _mk_action_btn(text: str, color_key: str = "accent") -> QPushButton:
    btn = QPushButton(text)
    btn.setFont(font(12, "bold"))
    btn.setFixedHeight(36)
    btn.setCursor(Qt.PointingHandCursor)
    bg   = COLORS[color_key]
    bg_h = COLORS.get(f"{color_key}_hover", bg)
    bg_d = COLORS.get(f"{color_key}_dim",   bg)
    tc   = COLORS.get("accent_text", "#ffffff")
    btn.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{tc};
            border:none; border-radius:8px; padding:4px 16px;
        }}
        QPushButton:hover   {{ background:{bg_h}; }}
        QPushButton:pressed {{ background:{bg_d}; }}
        QPushButton:disabled {{
            background:{COLORS['border']};
            color:{COLORS['text_muted']};
        }}
    """)
    return btn


class _FilePicker(QWidget):
    def __init__(self, label: str, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        self._lbl = QLabel(label)
        self._lbl.setFont(font(11, "bold"))
        self._lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        col.addWidget(self._lbl)

        row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText(placeholder)
        self.entry.setReadOnly(True)
        self.entry.setFixedHeight(34)
        self.entry.setFont(font(12))
        self.entry.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:none;
                border-radius:7px;
                padding:4px 8px;
            }}
            QLineEdit:read-only {{ color:{COLORS['text_secondary']}; }}
        """)
        row.addWidget(self.entry)

        self.btn = QPushButton(t("add_vehicles.browse_btn", default="Browse"))
        self.btn.setFont(font(11, "bold"))
        self.btn.setFixedSize(90, 34)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['accent']};
                color:{COLORS['accent_text']};
                border:none; border-radius:7px;
            }}
            QPushButton:hover {{ background:{COLORS['accent_hover']}; }}
            QPushButton:pressed {{ background:{COLORS['accent_dim']}; }}
        """)
        row.addWidget(self.btn)
        col.addLayout(row)

    def set_label(self, text: str):       self._lbl.setText(text)
    def set_placeholder(self, text: str): self.entry.setPlaceholderText(text)
    def retranslate_browse_btn(self):     self.btn.setText(t("add_vehicles.browse_btn", default="Browse"))
    def path(self) -> str:                return self.entry.text()
    def set_path(self, p: str):           self.entry.setText(p)
    def clear(self):                      self.entry.clear()


class _EntryField(QWidget):
    def __init__(self, label: str, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        self._lbl = QLabel(label)
        self._lbl.setFont(font(11, "bold"))
        self._lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        col.addWidget(self._lbl)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText(placeholder)
        self.entry.setFixedHeight(34)
        self.entry.setFont(font(13))
        self.entry.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:none;
                border-radius:7px;
                padding:4px 8px;
                selection-background-color:{COLORS['accent']};
            }}
        """)
        col.addWidget(self.entry)

    def set_label(self, text: str):       self._lbl.setText(text)
    def set_placeholder(self, text: str): self.entry.setPlaceholderText(text)
    def text(self) -> str:                return self.entry.text().strip()
    def clear(self):                      self.entry.clear()


class _DiscoveredVehicleRow(QFrame):
    def __init__(self, vehicle: DiscoveredVehicle, parent=None):
        super().__init__(parent)
        self.vehicle = vehicle
        self.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['card_bg']};
                border:none;
                border-radius:8px;
            }}
        """)
        self.setFixedHeight(52)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(10)

        self._chk = QCheckBox()
        self._chk.setChecked(vehicle.ready)
        self._chk.setEnabled(vehicle.ready)
        self._chk.setStyleSheet(f"""
            QCheckBox::indicator {{
                width:18px; height:18px;
                border-radius:4px;
                border:2px solid {COLORS['border']};
                background:{COLORS['frame_bg']};
            }}
            QCheckBox::indicator:checked {{
                background:{COLORS['accent']};
                border-color:{COLORS['accent']};
            }}
        """)
        row.addWidget(self._chk)

        carid_lbl = QLabel(vehicle.carid)
        carid_lbl.setFont(font(10, "bold"))
        carid_lbl.setStyleSheet(f"""
            color:{COLORS['accent']};
            background:{COLORS['frame_bg']};
            border:none;
            border-radius:5px;
            padding:2px 7px;
        """)
        carid_lbl.setFixedWidth(110)
        carid_lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(carid_lbl)

        self._name_edit = QLineEdit(vehicle.display_name)
        self._name_edit.setFont(font(12))
        self._name_edit.setFixedHeight(30)
        self._name_edit.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:none;
                border-radius:6px;
                padding:2px 8px;
            }}
        """)
        row.addWidget(self._name_edit, 1)

        status_row = QHBoxLayout()
        status_row.setSpacing(4)

        def _chip(text: str, ok: bool) -> QLabel:
            lbl = QLabel(text)
            lbl.setFont(font(10, "bold"))
            clr = COLORS.get("success", "#4ade80") if ok else COLORS.get("error", "#f87171")
            dim = COLORS.get("success_dim", "#166534") if ok else COLORS.get("error_dim", "#7f1d1d")
            lbl.setStyleSheet(f"""
                color:{clr};
                background:{dim};
                border:none;
                border-radius:4px;
                padding:1px 6px;
            """)
            return lbl

        status_row.addWidget(_chip("JSON",  bool(vehicle.json_path)))
        status_row.addWidget(_chip("JBEAM", bool(vehicle.jbeam_path)))
        status_row.addWidget(_chip("IMG",   bool(vehicle.image_path)))
        row.addLayout(status_row)

        if not vehicle.ready:
            warn_lbl = QLabel("⚠")
            warn_lbl.setFont(font(14))
            warn_lbl.setStyleSheet(f"color:{COLORS.get('warning', '#facc15')};background:transparent;")
            warn_lbl.setToolTip("\n".join(vehicle.warnings))
            row.addWidget(warn_lbl)

    @property
    def is_checked(self) -> bool:
        return self._chk.isChecked()

    @property
    def display_name(self) -> str:
        return self._name_edit.text().strip() or self.vehicle.display_name


class _DiscoveredVariantRow(QFrame):
    def __init__(self, variant: DiscoveredVariant, parent=None):
        super().__init__(parent)
        self.variant = variant
        self.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['card_bg']};
                border:none;
                border-radius:8px;
            }}
        """)
        self.setFixedHeight(52)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(10)

        self._chk = QCheckBox()
        self._chk.setChecked(variant.ready)
        self._chk.setEnabled(variant.ready)
        self._chk.setStyleSheet(f"""
            QCheckBox::indicator {{
                width:18px; height:18px;
                border-radius:4px;
                border:2px solid {COLORS['border']};
                background:{COLORS['frame_bg']};
            }}
            QCheckBox::indicator:checked {{
                background:{COLORS['accent']};
                border-color:{COLORS['accent']};
            }}
        """)
        row.addWidget(self._chk)

        badge_lbl = QLabel(f"{variant.carid}  +  {variant.suffix}")
        badge_lbl.setFont(font(10, "bold"))
        badge_lbl.setStyleSheet(f"""
            color:{COLORS['accent']};
            background:{COLORS['frame_bg']};
            border:none;
            border-radius:5px;
            padding:2px 7px;
        """)
        badge_lbl.setFixedWidth(160)
        badge_lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(badge_lbl)

        self._name_edit = QLineEdit(variant.display_name)
        self._name_edit.setFont(font(12))
        self._name_edit.setFixedHeight(30)
        self._name_edit.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:none;
                border-radius:6px;
                padding:2px 8px;
            }}
        """)
        row.addWidget(self._name_edit, 1)

        folder_lbl = QLabel(f"SKINNAME_{variant.suffix}/")
        folder_lbl.setFont(font(10))
        folder_lbl.setStyleSheet(
            f"color:{COLORS['text_muted']};background:transparent;border:none;"
        )
        row.addWidget(folder_lbl)

        def _chip(text: str, ok: bool) -> QLabel:
            lbl = QLabel(text)
            lbl.setFont(font(10, "bold"))
            clr = COLORS.get("success", "#4ade80") if ok else COLORS.get("error", "#f87171")
            dim = COLORS.get("success_dim", "#166534") if ok else COLORS.get("error_dim", "#7f1d1d")
            lbl.setStyleSheet(f"color:{clr};background:{dim};border:none;border-radius:4px;padding:1px 6px;")
            return lbl

        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        status_row.addWidget(_chip("JSON",  bool(variant.json_path)))
        status_row.addWidget(_chip("JBEAM", bool(variant.jbeam_path)))
        row.addLayout(status_row)

        if not variant.ready:
            warn_lbl = QLabel("⚠")
            warn_lbl.setFont(font(14))
            warn_lbl.setStyleSheet(
                f"color:{COLORS.get('warning','#facc15')};background:transparent;"
            )
            warn_lbl.setToolTip("\n".join(variant.warnings))
            row.addWidget(warn_lbl)

    @property
    def is_checked(self) -> bool:
        return self._chk.isChecked()

    @property
    def display_name(self) -> str:
        return self._name_edit.text().strip() or self.variant.display_name


class _ScanWorker(QThread):
    finished = Signal(list, list, object, object)
    failed   = Signal(str, str)

    def __init__(self, path: str, known_carids, parent=None):
        super().__init__(parent)
        self._path        = path
        self._known       = known_carids

    def run(self):
        try:
            vehicles, variants, tmp, reason = scan_mod(self._path, known_carids=self._known)
            self.finished.emit(vehicles, variants, tmp, reason)
        except Exception as e:
            print(f"[WARNING] run: {type(e).__name__}: {e}")
            self.failed.emit(str(e), self._path)


class _ImportWorker(QThread):
    item_done    = Signal(int, bool)
    all_finished = Signal(int, int)

    def __init__(self, tasks: list, mode: str, parent=None):
        super().__init__(parent)
        self._tasks = tasks
        self._mode  = mode

    def run(self):
        added = skipped = 0
        for idx, item, display_name in self._tasks:
            ok = self._process(item, display_name)
            self.item_done.emit(idx, ok)
            if ok:
                added += 1
            else:
                skipped += 1
        self.all_finished.emit(added, skipped)

    def _process(self, item, display_name: str) -> bool:
        try:
            if self._mode == "vehicles":
                if _carid_exists(item.carid):
                    return False
                ok = process_custom_vehicle(
                    carid      = item.carid,
                    carname    = display_name,
                    json_path  = item.json_path,
                    jbeam_path = item.jbeam_path,
                    image_path = item.image_path,
                    info_json_path = item.info_json_path,
                )
                if ok:
                    _copy_uv_maps_to_images(item.carid, getattr(item, "uv_map_paths", []))
                return ok
            else:
                existing = load_added_variants_json() if _BACKEND_OK else {}
                if f"{item.carid}__{item.suffix.lower()}" in existing:
                    return False
                ok = process_custom_variant(
                    carid          = item.carid,
                    variant_suffix = item.suffix,
                    json_path      = item.json_path,
                    jbeam_path     = item.jbeam_path,
                    image_path     = item.image_path,
                    info_json_path = item.info_json_path,
                )
                if ok:
                    _copy_uv_maps_to_images(item.carid, getattr(item, "uv_map_paths", []))
                return ok
        except Exception as e:
            import traceback
            print(f"[ERROR] _ImportWorker._process failed: {e}")
            traceback.print_exc()
            return False


class _SmartImportCard(QFrame):
    items_added = Signal()

    def __init__(self, notify_fn, mode: str = "vehicles", parent=None):
        super().__init__(parent)
        self._notify    = notify_fn
        self._mode      = mode
        self._temp_dirs: List[str] = []
        self._rows:      list = []
        self._worker:    Optional[_ScanWorker] = None
        self._pending_paths: List[str] = []
        self._import_worker: Optional[_ImportWorker] = None

        self._dot_timer = QTimer(self)
        self._dot_timer.setInterval(400)
        self._dot_timer.timeout.connect(self._tick_dots)
        self._dot_count = 0

        self.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['card_bg']};
                border:none;
                border-radius:12px;
            }}
        """)
        drop_shadow(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title_text = (
            t("add_vehicles.smart_import_title_vehicles", default="🔍  Auto-Import Vehicles from Mod")
            if mode == "vehicles"
            else t("add_vehicles.smart_import_title_variants", default="🔍  Auto-Import Variants from Mod")
        )
        self._title_lbl = QLabel(title_text)
        self._title_lbl.setFont(font(15, "bold"))
        self._title_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        root.addWidget(self._title_lbl)

        sub_text = (
            t("add_vehicles.smart_import_subtitle_vehicles",
              default="Select a mod folder or ZIP — BeamSkin Studio will find the vehicles automatically.")
            if mode == "vehicles"
            else t("add_vehicles.smart_import_subtitle_variants",
                   default="Select a mod folder or ZIP — BeamSkin Studio will detect body variants automatically.")
        )
        self._sub_lbl = QLabel(sub_text)
        self._sub_lbl.setFont(font(11))
        self._sub_lbl.setWordWrap(True)
        self._sub_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;")
        root.addWidget(self._sub_lbl)

        browse_row = QHBoxLayout()
        browse_row.setSpacing(8)

        self._btn_folder = _mk_action_btn(t("add_vehicles.browse_folder_btn", default="📁  Browse Folder"))
        self._btn_folder.setFixedHeight(38)
        self._btn_folder.clicked.connect(self._browse_folder)
        browse_row.addWidget(self._btn_folder)

        self._btn_zip = _mk_action_btn(t("add_vehicles.browse_zip_btn", default="📦  Browse ZIP"))
        self._btn_zip.setFixedHeight(38)
        self._btn_zip.clicked.connect(self._browse_zip)
        browse_row.addWidget(self._btn_zip)

        browse_row.addStretch()
        root.addLayout(browse_row)

        self._active_scan_frame = QFrame()
        self._active_scan_frame.setStyleSheet(
            f"background:{COLORS['frame_bg']};border:none;border-radius:8px;"
        )
        self._active_scan_frame.setVisible(False)
        active_row = QHBoxLayout(self._active_scan_frame)
        active_row.setContentsMargins(10, 7, 10, 7)
        active_row.setSpacing(8)
        self._active_scan_icon = QLabel("🔍")
        self._active_scan_icon.setFont(font(13))
        self._active_scan_icon.setStyleSheet("background:transparent;")
        active_row.addWidget(self._active_scan_icon)
        self._active_scan_name = QLabel("")
        self._active_scan_name.setFont(font(12, "bold"))
        self._active_scan_name.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        active_row.addWidget(self._active_scan_name, 1)
        self._active_scan_dots = QLabel("")
        self._active_scan_dots.setFont(font(11))
        self._active_scan_dots.setStyleSheet(f"color:{COLORS['accent']};background:transparent;")
        self._active_scan_dots.setFixedWidth(30)
        active_row.addWidget(self._active_scan_dots)
        root.addWidget(self._active_scan_frame)

        self._queue_frame = QFrame()
        self._queue_frame.setStyleSheet("background:transparent;border:none;")
        _queue_outer = QVBoxLayout(self._queue_frame)
        _queue_outer.setContentsMargins(0, 0, 0, 0)
        _queue_outer.setSpacing(4)

        _queue_inner = QWidget()
        _queue_inner.setStyleSheet("background:transparent;")
        self._queue_col = QVBoxLayout(_queue_inner)
        self._queue_col.setContentsMargins(0, 2, 0, 2)
        self._queue_col.setSpacing(4)
        self._queue_col.addStretch()
        _queue_outer.addWidget(_queue_inner)

        self._queue_frame.setVisible(False)
        root.addWidget(self._queue_frame)
        self._queue_rows: dict = {}
        self._queue_hdr: Optional[QLabel] = None

        self._status_lbl = QLabel("")
        self._status_lbl.setFont(font(11))
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;")
        self._status_lbl.setVisible(False)
        root.addWidget(self._status_lbl)

        self._list_frame = QFrame()
        self._list_frame.setStyleSheet("background:transparent;")
        self._list_col   = QVBoxLayout(self._list_frame)
        self._list_col.setContentsMargins(0, 0, 0, 0)
        self._list_col.setSpacing(6)
        self._list_frame.setVisible(False)
        root.addWidget(self._list_frame)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._select_all_btn = GhostButton(t("add_vehicles.select_all_btn", default="Select All"))
        self._select_all_btn.setFixedHeight(34)
        self._select_all_btn.clicked.connect(self._select_all)
        self._select_all_btn.setVisible(False)
        btn_row.addWidget(self._select_all_btn)

        btn_row.addStretch()

        self._add_btn = _mk_action_btn(t("add_vehicles.add_checked_btn", default="Add Checked"))
        self._add_btn.setFixedHeight(38)
        self._add_btn.clicked.connect(self._on_add_checked)
        self._add_btn.setVisible(False)
        btn_row.addWidget(self._add_btn)

        root.addLayout(btn_row)


    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(
            self,
            t("add_vehicles.browse_folder_dialog", default="Select Mod Folder"),
            _mods_start_dir(),
        )
        if path and os.path.isdir(path):
            self._queue_scans([path])

    def _browse_zip(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            t("add_vehicles.browse_zip_dialog", default="Select Mod ZIP(s)"),
            _mods_start_dir(),
            "ZIP Archives (*.zip);;All Files (*)",
        )
        if paths:
            self._queue_scans(paths)


    def _make_queue_row(self, path: str, status: str = "queued") -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"background:{COLORS['frame_bg']};border:none;border-radius:7px;"
        )
        frame.setFixedHeight(34)
        hl = QHBoxLayout(frame)
        hl.setContentsMargins(10, 0, 10, 0)
        hl.setSpacing(8)

        name_lbl = QLabel(os.path.basename(path))
        name_lbl.setFont(font(11))
        name_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;")
        name_lbl.setToolTip(path)
        hl.addWidget(name_lbl, 1)

        chip = QLabel()
        chip.setFont(font(10, "bold"))
        chip.setFixedHeight(20)
        chip.setContentsMargins(6, 1, 6, 1)
        chip.setAlignment(Qt.AlignCenter)
        frame._chip = chip
        hl.addWidget(chip)

        self._set_queue_chip(frame, status)
        return frame

    def _set_queue_chip(self, frame: QFrame, status: str):
        chip = frame._chip
        if status == "queued":
            chip.setText(t("add_vehicles.chip_queued"))
            chip.setStyleSheet(
                f"color:{COLORS['text_muted']};background:{COLORS['border']};"
                f"border:none;border-radius:4px;"
            )
        elif status == "scanning":
            chip.setText(t("add_vehicles.chip_scanning"))
            chip.setStyleSheet(
                f"color:{COLORS['accent']};background:{COLORS.get('accent_dim', COLORS['frame_bg'])};"
                f"border:none;border-radius:4px;"
            )
        elif status == "done":
            chip.setText(t("add_vehicles.chip_done"))
            chip.setStyleSheet(
                f"color:{COLORS.get('success', '#4ade80')};"
                f"background:{COLORS.get('success_dim', '#166534')};"
                f"border:none;border-radius:4px;"
            )
        elif status == "failed":
            chip.setText(t("add_vehicles.chip_failed"))
            chip.setStyleSheet(
                f"color:{COLORS.get('error', '#f87171')};"
                f"background:{COLORS.get('error_dim', '#7f1d1d')};"
                f"border:none;border-radius:4px;"
            )
        elif status == "empty":
            chip.setText(t("add_vehicles.chip_empty"))
            chip.setStyleSheet(
                f"color:{COLORS.get('warning', '#facc15')};"
                f"background:{COLORS.get('warning_dim', COLORS['border'])};"
                f"border:none;border-radius:4px;"
            )

    def _build_queue_panel(self, paths: List[str]):
        for w in list(self._queue_rows.values()):
            w.setParent(None)
            w.deleteLater()
        self._queue_rows.clear()

        if not paths:
            self._queue_frame.setVisible(False)
            return

        if self._queue_hdr is not None:
            self._queue_hdr.setParent(None)
            self._queue_hdr.deleteLater()
            self._queue_hdr = None
        self._queue_hdr = QLabel(t("add_vehicles.queue_header"))
        self._queue_hdr.setFont(font(10, "bold"))
        self._queue_hdr.setStyleSheet(f"color:{COLORS['text_muted']};background:transparent;")
        self._queue_frame.layout().insertWidget(0, self._queue_hdr)

        for p in paths:
            row = self._make_queue_row(p, "queued")
            self._queue_col.insertWidget(self._queue_col.count() - 1, row)
            self._queue_rows[p] = row

        self._queue_frame.setVisible(True)


    def _queue_scans(self, paths: List[str]):
        self._clear_results()
        self._pending_paths = list(paths)
        self._build_queue_panel(paths)
        self._run_next_scan()

    def _run_next_scan(self):
        if not self._pending_paths:
            return
        path = self._pending_paths.pop(0)
        self._run_scan(path)

    def _run_scan(self, path: str):
        if not _SCANNER_OK:
            detail = f" ({type(_SCANNER_IMPORT_ERROR).__name__}: {_SCANNER_IMPORT_ERROR})" if _SCANNER_IMPORT_ERROR else ""
            print(f"[ERROR] add_vehicles tab: scan requested for {path!r} but scanner is unavailable{detail}")
            self._notify(
                t("add_vehicles.scanner_unavailable",
                  default=f"Mod scanner not available{detail}. Check the debug console / log for details."),
                "error",
            )
            return

        if self._worker is not None:
            if self._worker.isRunning():
                self._worker.wait()
            self._worker = None

        known: Optional[set] = None
        if self._mode == "variants":
            try:
                from core.config import VEHICLE_IDS
                known = set(VEHICLE_IDS.keys())
                if _BACKEND_OK:
                    known |= set(load_added_vehicles_json().keys())
            except Exception as _exc:
                print(f"[WARNING] _run_scan: {type(_exc).__name__}: {_exc}")
                known = set()

        name = os.path.basename(path)
        self._active_scan_name.setText(t("add_vehicles.scanning_file", name=name))
        self._active_scan_dots.setText("")
        self._active_scan_frame.setVisible(True)
        self._set_scanning(True)

        if path in self._queue_rows:
            self._set_queue_chip(self._queue_rows[path], "scanning")

        self._worker = _ScanWorker(path, known, parent=self)
        self._worker.finished.connect(
            lambda veh, var, tmp, reason, p=path: self._on_scan_finished(veh, var, tmp, p, reason)
        )
        self._worker.failed.connect(lambda err, pth, p=path: self._on_scan_failed(err, p))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._worker.finished.connect(self._clear_worker_ref)
        self._worker.failed.connect(self._clear_worker_ref)
        self._worker.start()

    def _clear_worker_ref(self, *_args):
        self._worker = None

    def _set_scanning(self, active: bool):
        self._btn_folder.setEnabled(not active)
        self._btn_zip.setEnabled(not active)
        if active:
            self._dot_count = 0
            self._active_scan_dots.setText(".")
            self._dot_timer.start()
        else:
            self._dot_timer.stop()
            self._active_scan_dots.setText("")

    def _tick_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        self._active_scan_dots.setText("." * max(1, self._dot_count))

    def _on_scan_finished(self, vehicles, variants, tmp, path: str, failure_reason=None):
        self._set_scanning(False)
        if tmp:
            self._temp_dirs.append(tmp)

        items     = vehicles if self._mode == "vehicles" else variants
        mod_label = os.path.basename(path)
        found     = len(items)

        if path in self._queue_rows:
            if not found:
                self._set_queue_chip(self._queue_rows[path], "empty")
            else:
                self._set_queue_chip(self._queue_rows[path], "done")

        if found:
            self._active_scan_name.setText(
                t("add_vehicles.scan_found", mod=mod_label, found=found)
            )
        else:
            reason_suffix = f": {failure_reason}" if failure_reason else ""
            self._active_scan_name.setText(
                t("add_vehicles.scan_empty", mod=mod_label) + reason_suffix
            )

        if not items:
            reason_text = f" ({failure_reason})" if failure_reason else ""
            if not self._rows:
                self._status_lbl.setText(
                    (
                        t("add_vehicles.no_vehicles_found", mod=mod_label,
                          default=f"No vehicles found in \"{mod_label}\".")
                        if self._mode == "vehicles"
                        else t("add_vehicles.no_variants_found", mod=mod_label,
                               default=f"No variants found in \"{mod_label}\".")
                    ) + reason_text
                )
                self._status_lbl.setVisible(True)
            self._run_next_scan()
            return

        new_items: list = []
        skipped_existing: int = 0
        for item in items:
            if self._mode == "vehicles" and _carid_exists(item.carid):
                skipped_existing += 1
                print(f"[add_vehicles] Skipping already-existing vehicle: {item.carid}")
            else:
                new_items.append(item)

        if skipped_existing and not new_items:
            print(f"[add_vehicles] All vehicles in \"{mod_label}\" already exist, skipping.")
            if not self._pending_paths:
                self._active_scan_frame.setVisible(False)
                _non_done = {
                    s for p, row in self._queue_rows.items()
                    for s in [row._chip.text()]
                    if s in ("empty", "failed")
                }
                if not _non_done:
                    self._queue_frame.setVisible(False)
            self._run_next_scan()
            return

        for item in new_items:
            if self._mode == "vehicles":
                row = _DiscoveredVehicleRow(item, self._list_frame)
            else:
                row = _DiscoveredVariantRow(item, self._list_frame)
            self._list_col.addWidget(row)
            self._rows.append(row)
            fade_in(row, 120)

        total = len(self._rows)
        ready = sum(1 for r in self._rows if self._row_item(r).ready)

        if not self._pending_paths:
            self._active_scan_frame.setVisible(False)
            _non_done = {
                s for p, row in self._queue_rows.items()
                for s in [row._chip.text()]
                if s in ("empty", "failed")
            }
            if not _non_done:
                self._queue_frame.setVisible(False)

        if skipped_existing:
            print(f"[add_vehicles] {skipped_existing} already-existing vehicle(s) hidden from results.")
        self._status_lbl.setText(
            t("add_vehicles.found_items", count=total, ready=ready, mod=mod_label,
              default=f"Found {total} item(s) in \"{mod_label}\" ({ready} ready to import).")
        )
        self._status_lbl.setVisible(True)
        self._list_frame.setVisible(True)
        self._add_btn.setVisible(True)
        self._add_btn.setEnabled(True)
        self._select_all_btn.setVisible(total > 1)
        self._add_btn.setText(
            t("add_vehicles.add_checked_count_btn", count=ready,
              default=f"Add Checked ({ready})")
        )

        self._run_next_scan()

    def _on_scan_failed(self, error: str, path: str = ""):
        self._set_scanning(False)
        if path in self._queue_rows:
            self._set_queue_chip(self._queue_rows[path], "failed")
        name = os.path.basename(path) if path else t("add_vehicles.unknown")
        self._active_scan_name.setText(t("add_vehicles.scan_failed_label", name=name))
        self._notify(t("add_vehicles.scan_failed", error=error, default=f"Scan failed: {error}"), "error")
        if not self._pending_paths:
            self._active_scan_frame.setVisible(False)
        self._run_next_scan()


    @staticmethod
    def _row_item(row):
        return row.vehicle if hasattr(row, "vehicle") else row.variant


    def _select_all(self):
        ready_rows = [r for r in self._rows if self._row_item(r).ready]
        all_checked = all(r.is_checked for r in ready_rows)
        for row in ready_rows:
            row._chk.setChecked(not all_checked)
        self._select_all_btn.setText(
            t("add_vehicles.deselect_all_btn", default="Deselect All")
            if not all_checked
            else t("add_vehicles.select_all_btn", default="Select All")
        )

    def _on_add_checked(self):
        if not _BACKEND_OK:
            print("[ERROR] add_vehicles tab: Add Checked clicked but _BACKEND_OK is False "
                  "(core.add_vehicles / utils.file_ops import failed at module load — "
                  "see the '[WARNING] add_vehicles tab: backend import failed' line above)")
            self._notify(
                t("add_vehicles.backend_unavailable",
                  default="Vehicle import backend not available. Check the debug console / log for details."),
                "error",
            )
            return
        checked = [r for r in self._rows if r.is_checked]
        if not checked:
            self._notify(t("add_vehicles.no_items_selected", default="No items selected."), "warning")
            return

        tasks = [
            (self._rows.index(r), self._row_item(r), r.display_name)
            for r in checked
        ]

        self._add_btn.setEnabled(False)
        self._add_btn.setText(
            t("add_vehicles.importing_btn", count=len(tasks),
              default=f"Importing {len(tasks)}…")
        )
        self._select_all_btn.setEnabled(False)
        self._btn_folder.setEnabled(False)
        self._btn_zip.setEnabled(False)

        self._import_worker = _ImportWorker(tasks, self._mode, parent=self)
        self._import_worker.item_done.connect(self._on_item_imported)
        self._import_worker.all_finished.connect(self._on_import_finished)
        self._import_worker.finished.connect(self._import_worker.deleteLater)
        self._import_worker.start()

    def _on_item_imported(self, row_index: int, ok: bool):
        if ok and row_index < len(self._rows):
            row = self._rows[row_index]
            row.setEnabled(False)
            row.setStyleSheet(row.styleSheet() + " opacity: 0.4;")

    def _on_import_finished(self, added: int, skipped: int):
        self._btn_folder.setEnabled(True)
        self._btn_zip.setEnabled(True)
        self._add_btn.setEnabled(True)
        self._select_all_btn.setEnabled(True)

        if added:
            self._notify(
                t("add_vehicles.imported_success", count=added,
                  default=f"Imported {added} item(s) successfully."),
                "success",
            )
            self.items_added.emit()

        if skipped:
            self._notify(
                t("add_vehicles.import_failed_count", count=skipped,
                  default=f"{skipped} item(s) could not be imported."),
                "error",
            )

        self._clear_results()

    def _clear_results(self):
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        self._list_frame.setVisible(False)
        self._add_btn.setVisible(False)
        self._select_all_btn.setVisible(False)
        self._status_lbl.setVisible(False)
        self._active_scan_frame.setVisible(False)
        for w in list(self._queue_rows.values()):
            w.setParent(None)
            w.deleteLater()
        self._queue_rows.clear()
        if self._queue_hdr is not None:
            self._queue_hdr.setParent(None)
            self._queue_hdr.deleteLater()
            self._queue_hdr = None
        while self._queue_col.count() > 1:
            item = self._queue_col.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._queue_frame.setVisible(False)
        self._pending_paths.clear()
        self._cleanup_temp()

    def _cleanup_temp(self):
        for td in self._temp_dirs:
            if td and os.path.isdir(td):
                try:
                    shutil.rmtree(td, ignore_errors=True)
                except Exception as _exc:
                    print(f"[WARNING] _cleanup_temp: {type(_exc).__name__}: {_exc}")
        self._temp_dirs.clear()

    def __del__(self):
        self._cleanup_temp()


    def retranslate_ui(self):
        if self._mode == "vehicles":
            self._title_lbl.setText(
                t("add_vehicles.smart_import_title_vehicles",
                  default="🔍  Auto-Import Vehicles from Mod")
            )
            self._sub_lbl.setText(
                t("add_vehicles.smart_import_subtitle_vehicles",
                  default="Select a mod folder or ZIP — BeamSkin Studio will find the vehicles automatically.")
            )
        else:
            self._title_lbl.setText(
                t("add_vehicles.smart_import_title_variants",
                  default="🔍  Auto-Import Variants from Mod")
            )
            self._sub_lbl.setText(
                t("add_vehicles.smart_import_subtitle_variants",
                  default="Select a mod folder or ZIP — BeamSkin Studio will detect body variants automatically.")
            )
        self._btn_folder.setText(t("add_vehicles.browse_folder_btn", default="📁  Browse Folder"))
        self._btn_zip.setText(t("add_vehicles.browse_zip_btn", default="📦  Browse ZIP"))
        self._select_all_btn.setText(t("add_vehicles.select_all_btn", default="Select All"))
        if not self._rows:
            self._add_btn.setText(t("add_vehicles.add_checked_btn", default="Add Checked"))


class _VehicleListCard(QFrame):
    delete_requested = Signal(str)

    def __init__(self, carid: str, carname: str, parent=None):
        super().__init__(parent)
        self.carid   = carid
        self.carname = carname
        self.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['card_bg']};
                border:none;
                border-radius:8px;
            }}
        """)
        self.setFixedHeight(46)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 8, 0)
        row.setSpacing(8)

        name_lbl = QLabel(
            f"<b>{carname}</b>  "
            f"<span style='color:{COLORS['text_secondary']}'>{carid}</span>"
        )
        name_lbl.setFont(font(12))
        name_lbl.setStyleSheet(
            "background:transparent;border:none;color:" + COLORS['text'] + ";"
        )
        row.addWidget(name_lbl, 1)

        self._del_btn = _mk_action_btn(t("add_vehicles.delete_btn", default="Delete"), "error")
        self._del_btn.setFixedWidth(75)
        self._del_btn.clicked.connect(lambda: self.delete_requested.emit(self.carid))
        row.addWidget(self._del_btn)

    def retranslate_ui(self):
        self._del_btn.setText(t("add_vehicles.delete_btn", default="Delete"))


class _VariantListCard(QFrame):
    delete_requested = Signal(str, str)

    def __init__(self, carid: str, suffix: str, parent=None):
        super().__init__(parent)
        self.carid  = carid
        self.suffix = suffix
        self.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['card_bg']};
                border:none;
                border-radius:8px;
            }}
        """)
        self.setFixedHeight(46)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 8, 0)
        row.setSpacing(8)

        label = QLabel(
            f"<b>{carid}</b>  "
            f"<span style='color:{COLORS['accent']}'>+ {suffix}</span>"
        )
        label.setFont(font(12))
        label.setStyleSheet(
            "background:transparent;border:none;color:" + COLORS['text'] + ";"
        )
        row.addWidget(label, 1)

        folder_lbl = QLabel(f"SKINNAME{suffix.upper()}")
        folder_lbl.setFont(font(10))
        folder_lbl.setStyleSheet(
            f"color:{COLORS['text_muted']};background:transparent;border:none;"
        )
        row.addWidget(folder_lbl)

        self._del_btn = _mk_action_btn(t("add_vehicles.delete_btn", default="Delete"), "error")
        self._del_btn.setFixedWidth(75)
        self._del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self.carid, self.suffix)
        )
        row.addWidget(self._del_btn)

    def retranslate_ui(self):
        self._del_btn.setText(t("add_vehicles.delete_btn", default="Delete"))


class _ManualEntryCard(QFrame):
    submitted = Signal(str, str, str, str, str)

    def __init__(self, mode: str = "vehicle", parent=None):
        super().__init__(parent)
        self._mode     = mode
        self._expanded = False

        self.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['card_bg']};
                border:none;
                border-radius:12px;
            }}
        """)
        drop_shadow(self)

        self._root_col = QVBoxLayout(self)
        self._root_col.setContentsMargins(20, 14, 20, 14)
        self._root_col.setSpacing(10)

        toggle_row = QHBoxLayout()
        _plain_label = (
            t("add_vehicles.manual_entry_text", default="Manual Entry")
            if mode == "vehicle"
            else t("add_vehicles.manual_variant_text", default="Manual Variant Entry")
        )
        self._toggle_lbl = QLabel(f"＋  {_plain_label}")
        self._toggle_lbl.setFont(font(13, "bold"))
        self._toggle_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;"
        )
        toggle_row.addWidget(self._toggle_lbl)
        toggle_row.addStretch()

        self._toggle_btn = QPushButton(t("add_vehicles.expand", default="Expand"))
        self._toggle_btn.setFont(font(11))
        self._toggle_btn.setFixedHeight(28)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                color:{COLORS['accent']};
                border:none;
            }}
            QPushButton:hover {{ color:{COLORS['accent_hover']}; }}
        """)
        self._toggle_btn.clicked.connect(self._toggle)
        toggle_row.addWidget(self._toggle_btn)
        self._root_col.addLayout(toggle_row)

        self._body = QWidget()
        self._body.setStyleSheet("background:transparent;")
        body_col = QVBoxLayout(self._body)
        body_col.setContentsMargins(0, 4, 0, 0)
        body_col.setSpacing(10)
        self._body.setVisible(False)

        if mode == "vehicle":
            id_row = QHBoxLayout()
            self._carid_field   = _EntryField(
                t("add_vehicles.vehicle_id_label", default="Vehicle ID"),
                t("add_vehicles.vehicle_id_placeholder", default="e.g. pickup"),
            )
            self._carname_field = _EntryField(
                t("add_vehicles.display_name_label", default="Display Name"),
                t("add_vehicles.display_name_placeholder", default="e.g. Pickup Truck"),
            )
            id_row.addWidget(self._carid_field)
            id_row.addWidget(self._carname_field)
            body_col.addLayout(id_row)
        else:
            id_row = QHBoxLayout()
            self._carid_field  = _EntryField(
                t("add_vehicles.vehicle_id_label", default="Vehicle ID"),
                t("add_vehicles.vehicle_id_placeholder", default="e.g. pickup"),
            )
            self._suffix_field = _EntryField(
                t("add_vehicles.variants_suffix_label", default="Variant Suffix"),
                t("add_vehicles.variants_suffix_placeholder", default="e.g. ambulance"),
            )
            id_row.addWidget(self._carid_field)
            id_row.addWidget(self._suffix_field)
            body_col.addLayout(id_row)

            self._preview_lbl = QLabel("")
            self._preview_lbl.setFont(font(11))
            self._preview_lbl.setStyleSheet(
                f"color:{COLORS['text_muted']};background:transparent;"
            )
            body_col.addWidget(self._preview_lbl)
            self._carid_field.entry.textChanged.connect(self._update_preview)
            self._suffix_field.entry.textChanged.connect(self._update_preview)

        self._json_picker  = _FilePicker(
            t("add_vehicles.vehicles_json_label",  default="Skin Materials JSON"),
            t("common.nofile_selected", default="No file selected"),
        )
        self._jbeam_picker = _FilePicker(
            t("add_vehicles.vehicles_jbeam_label", default="Skin JBEAM"),
            t("common.nofile_selected", default="No file selected"),
        )
        self._img_picker   = _FilePicker(
            t("add_vehicles.image_label", default="Preview Image (optional)"),
            t("common.nofile_selected", default="No file selected"),
        )
        self._json_picker.btn.clicked.connect(
            lambda: self._browse_file(self._json_picker, "JSON Files (*.json);;All Files (*)")
        )
        self._jbeam_picker.btn.clicked.connect(
            lambda: self._browse_file(self._jbeam_picker, "JBEAM Files (*.jbeam);;All Files (*)")
        )
        self._img_picker.btn.clicked.connect(
            lambda: self._browse_file(self._img_picker, "Images (*.jpg *.jpeg);;All Files (*)")
        )
        body_col.addWidget(self._json_picker)
        body_col.addWidget(self._jbeam_picker)
        body_col.addWidget(self._img_picker)

        if mode == "vehicle":
            self._uv_picker = _FilePicker(
                t("add_vehicles.uv_map_label", default="UV Map (optional)"),
                t("common.nofile_selected", default="No file selected"),
            )
            self._uv_picker.btn.clicked.connect(
                lambda: self._browse_file(
                    self._uv_picker,
                    "UV Map Images (*.png *.dds *.jpg *.jpeg);;All Files (*)",
                )
            )
            body_col.addWidget(self._uv_picker)
        else:
            self._uv_picker = None

        label = (
            t("add_vehicles.vehicles_add_btn", default="Add Vehicle")
            if mode == "vehicle"
            else t("add_vehicles.variants_add_btn", default="Add Variant")
        )
        self._add_btn = _mk_action_btn(label)
        self._add_btn.setFixedHeight(40)
        self._add_btn.clicked.connect(self._on_submit)
        body_col.addWidget(self._add_btn)

        self._root_col.addWidget(self._body)


    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._toggle_btn.setText(
            t("add_vehicles.collapse", default="Collapse") if self._expanded
            else t("add_vehicles.expand", default="Expand")
        )
        sym = "－" if self._expanded else "＋"
        plain = (
            t("add_vehicles.manual_entry_text", default="Manual Entry")
            if self._mode == "vehicle"
            else t("add_vehicles.manual_variant_text", default="Manual Variant Entry")
        )
        self._toggle_lbl.setText(f"{sym}  {plain}")


    def _browse_file(self, picker: _FilePicker, file_filter: str):
        path, _ = QFileDialog.getOpenFileName(
            self, t("add_vehicles.dialog_select_file", default="Select File"),
            _mods_start_dir(), file_filter,
        )
        if path:
            picker.set_path(path)

    def _update_preview(self):
        if self._mode != "variant":
            return
        carid  = self._carid_field.text()
        suffix = self._suffix_field.text().upper()
        if carid or suffix:
            folder = f"vehicles/{carid}/SKINNAME_{suffix}/"
            self._preview_lbl.setText(f"→ {folder}")
        else:
            self._preview_lbl.setText("")

    def _on_submit(self):
        carid  = self._carid_field.text()
        json_  = self._json_picker.path()
        jbeam_ = self._jbeam_picker.path()
        img_   = self._img_picker.path()

        if self._mode == "vehicle":
            carname = self._carname_field.text()
            self.submitted.emit(carid, carname, json_, jbeam_, img_)
        else:
            suffix = self._suffix_field.text().lower()
            self.submitted.emit(carid, suffix, json_, jbeam_, img_, )

    def clear_fields(self):
        self._carid_field.clear()
        if self._mode == "vehicle":
            self._carname_field.clear()
        else:
            self._suffix_field.clear()
        self._json_picker.clear()
        self._jbeam_picker.clear()
        self._img_picker.clear()
        if self._uv_picker is not None:
            self._uv_picker.clear()

    def retranslate_ui(self):
        sym = "－" if self._expanded else "＋"
        plain = (
            t("add_vehicles.manual_entry_text", default="Manual Entry")
            if self._mode == "vehicle"
            else t("add_vehicles.manual_variant_text", default="Manual Variant Entry")
        )
        self._toggle_lbl.setText(f"{sym}  {plain}")
        self._toggle_btn.setText(
            t("add_vehicles.collapse", default="Collapse") if self._expanded
            else t("add_vehicles.expand", default="Expand")
        )

        self._carid_field.set_label(t("add_vehicles.vehicle_id_label", default="Vehicle ID"))
        self._carid_field.set_placeholder(t("add_vehicles.vehicle_id_placeholder", default="e.g. pickup"))
        self._json_picker.set_label(t("add_vehicles.vehicles_json_label",  default="Skin Materials JSON"))
        self._json_picker.set_placeholder(t("common.nofile_selected", default="No file selected"))
        self._json_picker.retranslate_browse_btn()
        self._jbeam_picker.set_label(t("add_vehicles.vehicles_jbeam_label", default="Skin JBEAM"))
        self._jbeam_picker.set_placeholder(t("common.nofile_selected", default="No file selected"))
        self._jbeam_picker.retranslate_browse_btn()
        self._img_picker.set_label(t("add_vehicles.image_label", default="Preview Image (optional)"))
        self._img_picker.set_placeholder(t("common.nofile_selected", default="No file selected"))
        self._img_picker.retranslate_browse_btn()
        if self._uv_picker is not None:
            self._uv_picker.set_label(t("add_vehicles.uv_map_label", default="UV Map (optional)"))
            self._uv_picker.set_placeholder(t("common.nofile_selected", default="No file selected"))
            self._uv_picker.retranslate_browse_btn()
        if self._mode == "vehicle":
            self._carname_field.set_label(t("add_vehicles.display_name_label", default="Display Name"))
            self._carname_field.set_placeholder(t("add_vehicles.display_name_placeholder", default="e.g. Pickup Truck"))
            self._add_btn.setText(t("add_vehicles.vehicles_add_btn", default="Add Vehicle"))
        else:
            self._suffix_field.set_label(t("add_vehicles.variants_suffix_label", default="Variant Suffix"))
            self._suffix_field.set_placeholder(t("add_vehicles.variants_suffix_placeholder", default="e.g. ambulance"))
            self._add_btn.setText(t("add_vehicles.variants_add_btn", default="Add Variant"))


class _VehiclesTab(QWidget):
    vehicle_added   = Signal()
    vehicle_deleted = Signal()

    def __init__(self, notify_fn, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")
        self._notify = notify_fn
        self._cards: List[_VehicleListCard] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet(f"background:{COLORS['app_bg']};")
        col = QVBoxLayout(inner)
        col.setContentsMargins(20, 20, 20, 20)
        col.setSpacing(16)

        self._smart_card = _SmartImportCard(notify_fn, mode="vehicles", parent=inner)
        self._smart_card.items_added.connect(self._on_items_added)
        col.addWidget(self._smart_card)

        self._manual_card = _ManualEntryCard(mode="vehicle", parent=inner)
        self._manual_card.submitted.connect(self._on_manual_submit)
        col.addWidget(self._manual_card)

        self._list_hdr = QLabel(t("add_vehicles.vehicles_added_header", default="Added Vehicles"))
        self._list_hdr.setFont(font(14, "bold"))
        self._list_hdr.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        col.addWidget(self._list_hdr)

        self._list_frame = QFrame()
        self._list_frame.setStyleSheet("background:transparent;")
        self._list_col = QVBoxLayout(self._list_frame)
        self._list_col.setContentsMargins(0, 0, 0, 0)
        self._list_col.setSpacing(6)
        col.addWidget(self._list_frame)

        self._empty_lbl = QLabel(t("add_vehicles.no_vehicles", default="No custom vehicles added yet."))
        self._empty_lbl.setFont(font(12))
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color:{COLORS['text_muted']};background:transparent;")
        self._list_col.addWidget(self._empty_lbl)

        col.addStretch()
        scroll.setWidget(inner)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self._reload_list()


    def _on_items_added(self):
        self._reload_list()
        self.vehicle_added.emit()

    def _on_manual_submit(
        self, carid: str, carname: str, json_path: str, jbeam_path: str, img_path: str
    ):
        if not carid:
            self._notify(t("add_vehicles.notification.enter_vehicle_id", default="Enter a vehicle ID."), "warning")
            return
        if not carname:
            self._notify(t("add_vehicles.notification.enter_display_name", default="Enter a display name."), "warning")
            return
        if not json_path:
            self._notify(t("add_vehicles.notification.select_json", default="Select a JSON file."), "warning")
            return
        if not jbeam_path:
            self._notify(t("add_vehicles.notification.select_jbeam", default="Select a JBEAM file."), "warning")
            return

        if _carid_exists(carid):
            self._notify(
                t("add_vehicles.notification.vehicle_already_exists",
                  carid=carid, default=f"Vehicle '{carid}' already exists."),
                "warning",
            )
            return

        self._manual_card._add_btn.setEnabled(False)
        ok = False
        if _BACKEND_OK:
            ok = process_custom_vehicle(
                carid      = carid,
                carname    = carname,
                json_path  = json_path,
                jbeam_path = jbeam_path,
                image_path = img_path or None,
            )
        self._manual_card._add_btn.setEnabled(True)

        if ok:
            self._notify(
                t("add_vehicles.notification.vehicle_added",
                  carname=carname, default=f"Added '{carname}' successfully."),
                "success",
            )
            uv_path = self._manual_card._uv_picker.path() if self._manual_card._uv_picker else ""
            if uv_path:
                _copy_uv_maps_to_images(carid, [uv_path])
            self._manual_card.clear_fields()
            self._reload_list()
            self.vehicle_added.emit()
        else:
            self._notify(t("add_vehicles.notification.vehicle_add_failed",
                           default="Failed to add vehicle."), "error")

    def _on_delete(self, carid: str):
        ok = delete_custom_vehicle(carid) if _BACKEND_OK else False
        if ok:
            self._notify(
                t("add_vehicles.notification.vehicle_deleted_id",
                  carid=carid, default=f"Deleted '{carid}'."),
                "info",
            )
            self._reload_list()
            self.vehicle_deleted.emit()
        else:
            self._notify(
                t("add_vehicles.notification.vehicle_delete_failed",
                  carid=carid, default=f"Failed to delete '{carid}'."),
                "error",
            )

    def _reload_list(self):
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        vehicles = load_added_vehicles_json() if _BACKEND_OK else {}

        if not vehicles:
            self._empty_lbl.setVisible(True)
            return

        self._empty_lbl.setVisible(False)
        for carid, carname in sorted(vehicles.items(), key=lambda x: x[1].lower()):
            card = _VehicleListCard(carid, carname, self._list_frame)
            card.delete_requested.connect(self._on_delete)
            self._list_col.insertWidget(self._list_col.count() - 1, card)
            self._cards.append(card)
            fade_in(card, 150)


    def retranslate_ui(self):
        self._list_hdr.setText(t("add_vehicles.vehicles_added_header", default="Added Vehicles"))
        self._empty_lbl.setText(t("add_vehicles.no_vehicles", default="No custom vehicles added yet."))
        self._smart_card.retranslate_ui()
        self._manual_card.retranslate_ui()
        for card in self._cards:
            card.retranslate_ui()

    def refresh_ui(self):
        self.retranslate_ui()
        self._reload_list()


class _VariantsTab(QWidget):
    variant_added   = Signal()
    variant_deleted = Signal()

    def __init__(self, notify_fn, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")
        self._notify = notify_fn
        self._cards: List[_VariantListCard] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet(f"background:{COLORS['app_bg']};")
        col = QVBoxLayout(inner)
        col.setContentsMargins(20, 20, 20, 20)
        col.setSpacing(16)

        self._info_lbl = QLabel(t("add_vehicles.variants_info_banner", SUFFIX="_box",
                                   default="Variants add extra body types to an existing vehicle."))
        self._info_lbl.setWordWrap(True)
        self._info_lbl.setFont(font(11))
        self._info_lbl.setStyleSheet(f"""
            color:{COLORS['text']};
            background:{COLORS['frame_bg']};
            border:none;
            border-radius:8px;
            padding:10px 14px;
        """)
        col.addWidget(self._info_lbl)

        self._smart_card = _SmartImportCard(notify_fn, mode="variants", parent=inner)
        self._smart_card.items_added.connect(self._on_items_added)
        col.addWidget(self._smart_card)

        self._manual_card = _ManualEntryCard(mode="variant", parent=inner)
        self._manual_card.submitted.connect(self._on_manual_submit)
        col.addWidget(self._manual_card)

        self._list_hdr = QLabel(t("add_vehicles.variants_added_header", default="Added Variants"))
        self._list_hdr.setFont(font(14, "bold"))
        self._list_hdr.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        col.addWidget(self._list_hdr)

        self._list_frame = QFrame()
        self._list_frame.setStyleSheet("background:transparent;")
        self._list_col = QVBoxLayout(self._list_frame)
        self._list_col.setContentsMargins(0, 0, 0, 0)
        self._list_col.setSpacing(6)
        col.addWidget(self._list_frame)

        self._empty_lbl = QLabel(t("add_vehicles.variants_no_variants", default="No custom variants added yet."))
        self._empty_lbl.setFont(font(12))
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color:{COLORS['text_muted']};background:transparent;")
        self._list_col.addWidget(self._empty_lbl)

        col.addStretch()
        scroll.setWidget(inner)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self._reload_list()


    def _on_items_added(self):
        self._reload_list()
        self.variant_added.emit()

    def _on_manual_submit(
        self, carid: str, suffix: str, json_path: str, jbeam_path: str, img_path: str
    ):
        if not carid:
            self._notify(t("add_vehicles.notification.enter_vehicle_id", default="Enter a vehicle ID."), "warning")
            return
        if not suffix:
            self._notify(t("add_vehicles.notification.enter_suffix", default="Enter a variant suffix."), "warning")
            return
        if not json_path:
            self._notify(t("add_vehicles.notification.select_json", default="Select a JSON file."), "warning")
            return
        if not jbeam_path:
            self._notify(t("add_vehicles.notification.select_jbeam", default="Select a JBEAM file."), "warning")
            return

        existing = load_added_variants_json() if _BACKEND_OK else {}
        if f"{carid}__{suffix}" in existing:
            self._notify(
                t("add_vehicles.notification.variant_already_exists",
                  carid=carid, suffix=suffix,
                  default=f"Variant '{carid} + {suffix}' already exists."),
                "warning",
            )
            return

        self._manual_card._add_btn.setEnabled(False)
        ok = False
        if _BACKEND_OK:
            ok = process_custom_variant(
                carid          = carid,
                variant_suffix = suffix,
                json_path      = json_path,
                jbeam_path     = jbeam_path,
                image_path     = img_path or None,
            )
        self._manual_card._add_btn.setEnabled(True)

        if ok:
            self._notify(
                t("add_vehicles.notification.variant_added",
                  carid=carid, suffix=suffix.upper(),
                  default=f"Added variant '{carid} + {suffix}' successfully."),
                "success",
            )
            self._manual_card.clear_fields()
            self._reload_list()
            self.variant_added.emit()
        else:
            self._notify(t("add_vehicles.notification.variant_add_failed",
                           default="Failed to add variant."), "error")

    def _on_delete(self, carid: str, suffix: str):
        ok = delete_custom_variant(carid, suffix) if _BACKEND_OK else False
        if ok:
            self._notify(
                t("add_vehicles.notification.variant_deleted",
                  carid=carid, suffix=suffix, default=f"Deleted variant '{carid} + {suffix}'."),
                "info",
            )
            self._reload_list()
            self.variant_deleted.emit()
        else:
            self._notify(
                t("add_vehicles.notification.variant_delete_failed",
                  carid=carid, suffix=suffix, default="Failed to delete variant."),
                "error",
            )

    def _reload_list(self):
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        variants = load_added_variants_json() if _BACKEND_OK else {}

        if not variants:
            self._empty_lbl.setVisible(True)
            return

        self._empty_lbl.setVisible(False)
        for key, info in sorted(variants.items()):
            carid  = info.get("carid",  key)
            suffix = info.get("suffix", "")
            card   = _VariantListCard(carid, suffix, self._list_frame)
            card.delete_requested.connect(self._on_delete)
            self._list_col.insertWidget(self._list_col.count() - 1, card)
            self._cards.append(card)
            fade_in(card, 150)


    def retranslate_ui(self):
        self._info_lbl.setText(t("add_vehicles.variants_info_banner", SUFFIX="_box",
                                  default="Variants add extra body types to an existing vehicle."))
        self._list_hdr.setText(t("add_vehicles.variants_added_header", default="Added Variants"))
        self._empty_lbl.setText(t("add_vehicles.variants_no_variants", default="No custom variants added yet."))
        self._smart_card.retranslate_ui()
        self._manual_card.retranslate_ui()
        for card in self._cards:
            card.retranslate_ui()

    def refresh_ui(self):
        self.retranslate_ui()
        self._reload_list()


def load_added_vehicles_at_startup():
    try:
        if _BACKEND_OK:
            load_added_vehicles_json()
    except Exception as _exc:
        print(f"[WARNING] load_added_vehicles_at_startup: {type(_exc).__name__}: {_exc}")


class AddVehiclesTab(QWidget):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        notification_callback=None,
        refresh_vehicle_list_callback=None,
        **_kwargs,
    ):
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self._notify     = notification_callback or self._fallback_notify
        self._refresh_cb = refresh_vehicle_list_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr_frame = QFrame()
        hdr_frame.setStyleSheet(f"background:{COLORS['frame_bg']};border:none;")
        hdr_frame.setFixedHeight(60)
        hdr_row = QHBoxLayout(hdr_frame)
        hdr_row.setContentsMargins(24, 0, 24, 0)

        self._title = QLabel(t("add_vehicles.page_title", default="Add Vehicles & Variants"))
        self._title.setFont(font(18, "bold"))
        self._title.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        hdr_row.addWidget(self._title)
        hdr_row.addStretch()
        root.addWidget(hdr_frame)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {COLORS['app_bg']};
            }}
            QTabBar::tab {{
                background: {COLORS['frame_bg']};
                color: {COLORS['text_secondary']};
                border: none;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {COLORS['app_bg']};
                color: {COLORS['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                background: {COLORS['card_hover']};
                color: {COLORS['text']};
            }}
        """)

        self._vehicles_tab = _VehiclesTab(self._notify, self)
        self._variants_tab = _VariantsTab(self._notify, self)

        self._tabs.addTab(self._vehicles_tab, t("add_vehicles.tab_vehicles", default="Vehicles"))
        self._tabs.addTab(self._variants_tab, t("add_vehicles.tab_variants", default="Variants"))

        self._vehicles_tab.vehicle_added.connect(self._on_list_changed)
        self._vehicles_tab.vehicle_deleted.connect(self._on_list_changed)
        self._variants_tab.variant_added.connect(self._on_list_changed)
        self._variants_tab.variant_deleted.connect(self._on_list_changed)

        root.addWidget(self._tabs)

    def retranslate_ui(self):
        self._title.setText(t("add_vehicles.page_title", default="Add Vehicles & Variants"))
        self._tabs.setTabText(0, t("add_vehicles.tab_vehicles", default="Vehicles"))
        self._tabs.setTabText(1, t("add_vehicles.tab_variants", default="Variants"))
        self._vehicles_tab.retranslate_ui()
        self._variants_tab.retranslate_ui()

    def _fallback_notify(self, msg: str, kind: str = "info", duration: int = 3000):
        print(f"[{kind.upper()}] {msg}")

    def _on_list_changed(self):
        if self._refresh_cb:
            try:
                self._refresh_cb()
            except Exception as e:
                print(f"[WARNING] refresh_vehicle_list_callback failed: {e}")

    def refresh_ui(self):
        self._title.setText(t("add_vehicles.page_title", default="Add Vehicles & Variants"))
        self._tabs.setTabText(0, t("add_vehicles.tab_vehicles", default="Vehicles"))
        self._tabs.setTabText(1, t("add_vehicles.tab_variants", default="Variants"))
        self._vehicles_tab.refresh_ui()
        self._variants_tab.refresh_ui()
