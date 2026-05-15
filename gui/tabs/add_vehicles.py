from __future__ import annotations

import os
import shutil
from typing import Optional, List

from PySide6.QtCore    import Qt, Signal, QTimer, QThread
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QCheckBox,
    QVBoxLayout, QHBoxLayout, QScrollArea, QTabWidget,
    QFileDialog, QSizePolicy, QApplication,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import AnimButton, GhostButton, Card, HSeparator, Toast
from gui.state   import state

try:
    from core.localization import t
except ImportError:
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
except ImportError as _e:
    print(f"[WARNING] add_vehicles tab: backend import failed: {_e}")
    _BACKEND_OK = False

try:
    from core.mod_scanner import scan_mod, DiscoveredVehicle, DiscoveredVariant
    _SCANNER_OK = True
except ImportError:
    _SCANNER_OK = False

try:
    from core.settings import get_mods_folder_path as _get_mods_folder_path
except ImportError:
    def _get_mods_folder_path(): return ""


def _mods_start_dir() -> str:
    """Return the configured mods folder if it exists, else an empty string."""
    p = _get_mods_folder_path()
    return p if p and os.path.isdir(p) else ""


# ─────────────────────────────────────────────────────────────────────────────
# UV-map copy helper (used by smart import)
# ─────────────────────────────────────────────────────────────────────────────

def _copy_uv_maps_to_images(carid: str, uv_map_paths: list) -> None:
    """
    Copy UV-layout images found during mod scanning into the vehicle's local
    image folder (``gui/images/vehicles/{carid}/``) so that CarListTab can
    offer a "Get UV Map" button for custom-added vehicles without requiring
    BeamNG to be installed.

    Files are only written if they do not already exist at the destination,
    so repeated imports are safe.
    """
    if not uv_map_paths:
        return
    # add_vehicles.py lives at  gui/tabs/add_vehicles.py
    # → two levels up is the gui/ package root
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


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers / shared widgets
# ─────────────────────────────────────────────────────────────────────────────

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
    """Label + read-only entry + Browse button."""

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
    """Label + editable QLineEdit."""

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


# ─────────────────────────────────────────────────────────────────────────────
# Discovered vehicle row
# ─────────────────────────────────────────────────────────────────────────────

class _DiscoveredVehicleRow(QFrame):
    """
    One row inside the smart-import results list representing a discovered vehicle.
    Shows: [checkbox] [carid badge] [editable display name] [file status] [warnings]
    """

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

        # Checkbox
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

        # carid badge
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

        # Display name (editable)
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

        # File status chips
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

        # Warning icon if not ready
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
    """One row for a discovered body variant."""

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

        # "carid + suffix" badge
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

        # Display name (editable)
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

        # Folder preview
        folder_lbl = QLabel(f"SKINNAME_{variant.suffix}/")
        folder_lbl.setFont(font(10))
        folder_lbl.setStyleSheet(
            f"color:{COLORS['text_muted']};background:transparent;border:none;"
        )
        row.addWidget(folder_lbl)

        # File status
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


# ─────────────────────────────────────────────────────────────────────────────
# Smart Import Card  (shared base logic for vehicles + variants)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Background scan worker
# ─────────────────────────────────────────────────────────────────────────────

class _ScanWorker(QThread):
    """Runs scan_mod on a background thread so the UI stays responsive."""

    finished = Signal(list, list, object)   # vehicles, variants, temp_dir
    failed   = Signal(str)                  # error message

    def __init__(self, path: str, known_carids, parent=None):
        super().__init__(parent)
        self._path        = path
        self._known       = known_carids

    def run(self):
        try:
            vehicles, variants, tmp = scan_mod(self._path, known_carids=self._known)
            self.finished.emit(vehicles, variants, tmp)
        except Exception as e:
            self.failed.emit(str(e))


class _SmartImportCard(QFrame):
    """
    Card with two browse buttons (Folder / ZIP), a scan status label, and a
    scrollable list of discovered items.  Sub-classed for Vehicles and Variants.
    """

    # Signal emitted after a successful add; used to refresh the parent list.
    items_added = Signal()

    def __init__(self, notify_fn, mode: str = "vehicles", parent=None):
        """
        mode : "vehicles"  → scans for new vehicles
               "variants"  → scans for variants of existing vehicles
        """
        super().__init__(parent)
        self._notify   = notify_fn
        self._mode     = mode          # "vehicles" or "variants"
        self._temp_dir: Optional[str] = None
        self._rows:     list = []      # _DiscoveredVehicleRow | _DiscoveredVariantRow
        self._worker:   Optional[_ScanWorker] = None

        # Animated dots timer for the "Scanning…" label
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

        # ── Header ──────────────────────────────────────────────────────────
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

        # ── Browse buttons ───────────────────────────────────────────────────
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

        # ── Path display ─────────────────────────────────────────────────────
        self._path_lbl = QLabel("")
        self._path_lbl.setFont(font(10))
        self._path_lbl.setWordWrap(True)
        self._path_lbl.setStyleSheet(
            f"color:{COLORS['text_muted']};background:transparent;"
        )
        self._path_lbl.setVisible(False)
        root.addWidget(self._path_lbl)

        # ── Scan status ──────────────────────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setFont(font(11))
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;")
        self._status_lbl.setVisible(False)
        root.addWidget(self._status_lbl)

        # ── Discovered list ──────────────────────────────────────────────────
        self._list_frame = QFrame()
        self._list_frame.setStyleSheet("background:transparent;")
        self._list_col   = QVBoxLayout(self._list_frame)
        self._list_col.setContentsMargins(0, 0, 0, 0)
        self._list_col.setSpacing(6)
        self._list_frame.setVisible(False)
        root.addWidget(self._list_frame)

        # ── Bottom actions ───────────────────────────────────────────────────
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

    # ── Browse ───────────────────────────────────────────────────────────────

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("add_vehicles.browse_folder_dialog", default="Select Mod Folder"),
            _mods_start_dir(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if path:
            self._run_scan(path)

    def _browse_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("add_vehicles.browse_zip_dialog", default="Select Mod ZIP"), _mods_start_dir(),
            "ZIP Archives (*.zip);;All Files (*)",
        )
        if path:
            self._run_scan(path)

    # ── Scan ─────────────────────────────────────────────────────────────────

    def _run_scan(self, path: str):
        if not _SCANNER_OK:
            self._notify(t("add_vehicles.scanner_unavailable", default="Mod scanner not available."), "error")
            return

        # Clean up any previous temp extraction / worker
        self._cleanup_temp()
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(500)

        # ── Known carids for variant detection ───────────────────────────────
        known: Optional[set] = None
        if self._mode == "variants":
            try:
                from core.config import VEHICLE_IDS
                known = set(VEHICLE_IDS.keys())
                if _BACKEND_OK:
                    known |= set(load_added_vehicles_json().keys())
            except Exception:
                known = set()

        # ── Show loading state ────────────────────────────────────────────────
        self._path_lbl.setText(f"📂 {path}")
        self._path_lbl.setVisible(True)
        self._set_scanning(True)

        # Clear old rows
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        self._list_frame.setVisible(False)
        self._add_btn.setVisible(False)
        self._select_all_btn.setVisible(False)

        # ── Launch background worker ──────────────────────────────────────────
        self._worker = _ScanWorker(path, known, parent=self)
        self._worker.finished.connect(
            lambda veh, var, tmp, p=path: self._on_scan_finished(veh, var, tmp, p)
        )
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.start()

    def _set_scanning(self, active: bool):
        """Show/hide the animated scanning label and disable/enable browse buttons."""
        self._btn_folder.setEnabled(not active)
        self._btn_zip.setEnabled(not active)
        if active:
            self._dot_count = 0
            self._status_lbl.setText(t("add_vehicles.scanning", default="🔍  Scanning"))
            self._status_lbl.setStyleSheet(
                f"color:{COLORS['accent']};background:transparent;"
            )
            self._status_lbl.setVisible(True)
            self._dot_timer.start()
        else:
            self._dot_timer.stop()
            self._status_lbl.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;"
            )

    def _tick_dots(self):
        """Animate trailing dots on the scanning label."""
        self._dot_count = (self._dot_count + 1) % 4
        self._status_lbl.setText(t("add_vehicles.scanning", default="🔍  Scanning") + "." * self._dot_count)

    def _on_scan_finished(self, vehicles, variants, tmp, path: str):
        self._set_scanning(False)
        self._temp_dir = tmp

        items     = vehicles if self._mode == "vehicles" else variants
        mod_label = os.path.basename(path)

        if not items:
            status = (
                t("add_vehicles.no_vehicles_found", mod=mod_label,
                  default=f"No vehicles found in \"{mod_label}\".")
                if self._mode == "vehicles"
                else t("add_vehicles.no_variants_found", mod=mod_label,
                       default=f"No variants found in \"{mod_label}\".")
            )
            self._status_lbl.setText(status)
            self._status_lbl.setVisible(True)
            return

        # ── Build rows ────────────────────────────────────────────────────────
        count = len(items)
        ready = sum(1 for i in items if i.ready)
        self._status_lbl.setText(
            t("add_vehicles.found_items", count=count, mod=mod_label, ready=ready,
              default=f"Found {count} item(s) in \"{mod_label}\" ({ready} ready to import).")
        )
        self._status_lbl.setVisible(True)
        self._list_frame.setVisible(True)
        self._add_btn.setVisible(True)
        self._select_all_btn.setVisible(count > 1)
        self._add_btn.setText(
            t("add_vehicles.add_checked_count_btn", count=ready, default=f"Add Checked ({ready})")
        )

        for item in items:
            if self._mode == "vehicles":
                row = _DiscoveredVehicleRow(item, self._list_frame)
            else:
                row = _DiscoveredVariantRow(item, self._list_frame)
            self._list_col.addWidget(row)
            self._rows.append(row)
            fade_in(row, 120)

    def _on_scan_failed(self, error: str):
        self._set_scanning(False)
        self._notify(t("add_vehicles.scan_failed", error=error, default=f"Scan failed: {error}"), "error")

    # ── Actions ──────────────────────────────────────────────────────────────

    def _select_all(self):
        for row in self._rows:
            if row.vehicle.ready if hasattr(row, 'vehicle') else row.variant.ready:
                row._chk.setChecked(True)

    def _on_add_checked(self):
        checked = [r for r in self._rows if r.is_checked]
        if not checked:
            self._notify(t("add_vehicles.no_items_selected", default="No items selected."), "warning")
            return

        added   = 0
        skipped = 0

        for row in checked:
            ok = self._add_one(row)
            if ok:
                added += 1
            else:
                skipped += 1

        if added:
            self._notify(
                t("add_vehicles.imported_success", count=added,
                  default=f"Imported {added} item(s) successfully."),
                "success",
            )
            self.items_added.emit()
            # Clear results after successful import
            self._clear_results()
        if skipped:
            self._notify(
                t("add_vehicles.import_failed_count", count=skipped,
                  default=f"{skipped} item(s) could not be imported."),
                "error",
            )

    def _add_one(self, row) -> bool:
        if not _BACKEND_OK:
            return False
        try:
            if self._mode == "vehicles":
                v  = row.vehicle
                ok = process_custom_vehicle(
                    carid      = v.carid,
                    carname    = row.display_name,
                    json_path  = v.json_path,
                    jbeam_path = v.jbeam_path,
                    image_path = v.image_path,
                )
                # Copy any UV-layout images found during scanning so that
                # CarListTab can show the "Get UV Map" button offline.
                if ok:
                    _copy_uv_maps_to_images(v.carid, getattr(v, "uv_map_paths", []))
                return ok
            else:
                v  = row.variant
                ok = process_custom_variant(
                    carid          = v.carid,
                    variant_suffix = v.suffix,
                    json_path      = v.json_path,
                    jbeam_path     = v.jbeam_path,
                    image_path     = v.image_path,
                )
                # Copy any UV-layout images so CarListTab can offer
                # "Get UV Map" for the parent vehicle without BeamNG installed.
                if ok:
                    _copy_uv_maps_to_images(v.carid, getattr(v, "uv_map_paths", []))
                return ok
        except Exception as e:
            import traceback
            print(f"[ERROR] _add_one failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            return False

    def _clear_results(self):
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        self._list_frame.setVisible(False)
        self._add_btn.setVisible(False)
        self._select_all_btn.setVisible(False)
        self._status_lbl.setVisible(False)
        self._path_lbl.setVisible(False)
        self._cleanup_temp()

    def _cleanup_temp(self):
        if self._temp_dir and os.path.isdir(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
        self._temp_dir = None

    def __del__(self):
        self._cleanup_temp()

    # ── Translations ─────────────────────────────────────────────────────────

    def retranslate_ui(self):
        """Update all translatable strings without rebuilding the widget tree."""
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
        # Only retranslate the "Add Checked" button if it doesn't show a
        # live count (i.e. no scan results are currently displayed).
        if not self._rows:
            self._add_btn.setText(t("add_vehicles.add_checked_btn", default="Add Checked"))


# ─────────────────────────────────────────────────────────────────────────────
# Existing-vehicle list cards
# ─────────────────────────────────────────────────────────────────────────────

class _VehicleListCard(QFrame):
    """A row showing a custom vehicle with a Delete button."""

    delete_requested = Signal(str)   # carid

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
    """A row showing a custom variant with a Delete button."""

    delete_requested = Signal(str, str)   # carid, suffix

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


# ─────────────────────────────────────────────────────────────────────────────
# Manual entry section (collapsible)
# ─────────────────────────────────────────────────────────────────────────────

class _ManualEntryCard(QFrame):
    """Collapsible card wrapping the original manual file-picker form."""

    submitted = Signal(str, str, str, str, str)   # carid, carname, json, jbeam, img

    def __init__(self, mode: str = "vehicle", parent=None):
        """mode : "vehicle" or "variant" """
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

        # ── Toggle header ────────────────────────────────────────────────────
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

        # ── Collapsible body ─────────────────────────────────────────────────
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

            # Live preview
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

        # UV map picker — vehicle mode only (variants share the parent vehicle's UV map)
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

    # ── Collapse / Expand ────────────────────────────────────────────────────

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

    # ── Helpers ──────────────────────────────────────────────────────────────

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
        # Re-translate the toggle header and expand/collapse button.
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


# ─────────────────────────────────────────────────────────────────────────────
# Vehicles sub-tab
# ─────────────────────────────────────────────────────────────────────────────

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

        # ── Smart import card ────────────────────────────────────────────────
        self._smart_card = _SmartImportCard(notify_fn, mode="vehicles", parent=inner)
        self._smart_card.items_added.connect(self._on_items_added)
        col.addWidget(self._smart_card)

        # ── Manual entry card (collapsible) ──────────────────────────────────
        self._manual_card = _ManualEntryCard(mode="vehicle", parent=inner)
        self._manual_card.submitted.connect(self._on_manual_submit)
        col.addWidget(self._manual_card)

        # ── Added vehicles list ──────────────────────────────────────────────
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

    # ── Handlers ─────────────────────────────────────────────────────────────

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

        existing = load_added_vehicles_json() if _BACKEND_OK else {}
        if carid in existing:
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
            # Copy any manually-selected UV map so CarListTab can show
            # the "Get UV Map" button for this vehicle without BeamNG installed.
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

    # ── Translations ──────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Variants sub-tab
# ─────────────────────────────────────────────────────────────────────────────

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

        # ── Info banner ───────────────────────────────────────────────────────
        self._info_lbl = QLabel(t("add_vehicles.variants_info_banner",
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

        # ── Smart import card ─────────────────────────────────────────────────
        self._smart_card = _SmartImportCard(notify_fn, mode="variants", parent=inner)
        self._smart_card.items_added.connect(self._on_items_added)
        col.addWidget(self._smart_card)

        # ── Manual entry card (collapsible) ───────────────────────────────────
        self._manual_card = _ManualEntryCard(mode="variant", parent=inner)
        self._manual_card.submitted.connect(self._on_manual_submit)
        col.addWidget(self._manual_card)

        # ── Added variants list ───────────────────────────────────────────────
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

    # ── Handlers ──────────────────────────────────────────────────────────────

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
                  carid=carid, suffix=suffix, default=f"Failed to delete variant."),
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

    # ── Translations ──────────────────────────────────────────────────────────

    def retranslate_ui(self):
        self._info_lbl.setText(t("add_vehicles.variants_info_banner",
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


# ─────────────────────────────────────────────────────────────────────────────
# Public tab
# ─────────────────────────────────────────────────────────────────────────────

def load_added_vehicles_at_startup():
    """Called from main.py to warm up the added vehicles list."""
    try:
        if _BACKEND_OK:
            load_added_vehicles_json()
    except Exception:
        pass


class AddVehiclesTab(QWidget):
    """
    Public tab shown in the main navigation.
    Contains two sub-tabs: Vehicles and Variants.
    """

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

        # ── Page header ───────────────────────────────────────────────────────
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

        # ── Tab widget ────────────────────────────────────────────────────────
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
