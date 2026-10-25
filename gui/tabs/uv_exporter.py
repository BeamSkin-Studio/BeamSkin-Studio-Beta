
from __future__ import annotations

import json
import os
import zipfile
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.theme import COLORS, font
from gui.state import state
from gui.components.exporter_mod_dialog import exporter_gate, run_exporter_dialog
from gui.components.uv_exporter_widgets import (
    ColorPickerButton,
    GroupListWidget,
    make_labeled_row,
)
from core.uv_exporter.auto_select import auto_select_groups
from core.uv_exporter.car_models import (
    CarModelSource,
    find_car_dae_sources,
    materialize,
    resolve_path,
)
from core.uv_exporter import mod_locations
from core.uv_exporter.mod_locations import ModDaeSource
from core.uv_exporter.dae_parser import parse_dae
from core.uv_exporter.mesh_data import MeshParseError, UVMesh
from core.uv_exporter.rasterizer import RenderOptions, render_uv_template, save_render
from core.uv_exporter.selection_store import (
    clear_selection,
    load_selection,
    save_selection,
)

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] uv_exporter: localization import failed ({_exc}), using fallback")

    def t(key, default=None, **kw):
        text = default if default is not None else key
        try:
            return text.format(**kw)
        except Exception:
            return text

RESOLUTION_PRESETS = [512, 1024, 2048, 4096, 8192, 16384]


def _t(key: str, default: str, **kw) -> str:
    return t(key, default=default, **kw)


class _WrapLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text: str):
        super().setText(text.replace("/", "/\u200b").replace("\\", "\\\u200b").replace("_", "_\u200b"))

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


@dataclass
class VariantDaeSource:
    label: str
    carid: str
    vpath: str
    vfs: object

    def materialize(self) -> str:
        return self.vfs.extract(self.vpath)


def _variant_sources(carid: str, variant: str) -> list[VariantDaeSource]:
    if not carid or not variant:
        return []
    try:
        from core.model_preview.dae_search import find_variant_daes
        from core.model_preview.sources import _material_vfs

        vfs = _material_vfs(carid, ())
        title = variant.replace("_", " ").title()
        return [
            VariantDaeSource(f"{os.path.basename(vpath)}  ({title} variant body)", carid, vpath, vfs)
            for vpath in find_variant_daes(vfs, carid, variant)
        ]
    except Exception as e:
        print(f"[WARNING] uv_exporter: variant body lookup failed: {type(e).__name__}: {e}")
        return []


class LoadWorker(QThread):
    finished_ok = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, token: int, source: CarModelSource | str, uv_channel: str | None):
        super().__init__()
        self.token = token
        self.source = source
        self.uv_channel = uv_channel

    def run(self):
        try:
            if isinstance(self.source, CarModelSource):
                path = materialize(self.source)
            else:
                path = self.source
            mesh = parse_dae(path, uv_set=self.uv_channel)
            self.finished_ok.emit(self.token, mesh)
        except MeshParseError as e:
            self.failed.emit(self.token, str(e))
        except (OSError, zipfile.BadZipFile, KeyError) as e:
            self.failed.emit(self.token, _t("uv_exporter.read_error", "Could not read the model file: {error}", error=e))
        except Exception as e:
            self.failed.emit(self.token, _t("uv_exporter.unexpected_error", "Unexpected error: {error}", error=e))


class RenderWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, mesh: UVMesh, opts: RenderOptions, out_path: str):
        super().__init__()
        self.mesh = mesh
        self.opts = opts
        self.out_path = out_path

    def run(self):
        try:
            img = render_uv_template(self.mesh, self.opts)
            if not save_render(img, self.out_path):
                self.failed.emit(_t("uv_exporter.save_png_failed", "Failed to save PNG to {path}", path=self.out_path))
                return
            self.finished_ok.emit(self.out_path)
        except Exception as e:
            self.failed.emit(_t("uv_exporter.render_failed", "Render failed: {error}", error=e))


class DropZone(QFrame):
    fileDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("uvx_drop")
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        self._hover = False
        lay = QVBoxLayout(self)
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        lay.addWidget(self.label)
        self.apply_theme()

    def apply_theme(self):
        border = COLORS["accent"] if self._hover else COLORS["border"]
        self.setStyleSheet(
            f"#uvx_drop {{ border:2px dashed {border}; border-radius:10px; "
            f"background:{COLORS['frame_bg']}; }}"
        )
        self.label.setStyleSheet(
            f"color:{COLORS['text_secondary']};font-size:12px;background:transparent;border:none;"
        )
        self.label.setText(
            _t("uv_exporter.drop_hint", "Drop a .dae file here\nor click to browse")
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            path = event.mimeData().urls()[0].toLocalFile()
            if path.lower().endswith(".dae"):
                self._hover = True
                self.apply_theme()
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, _event):
        self._hover = False
        self.apply_theme()

    def dropEvent(self, event: QDropEvent):
        self._hover = False
        self.apply_theme()
        self.fileDropped.emit(event.mimeData().urls()[0].toLocalFile())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            path, _ = QFileDialog.getOpenFileName(
                self, _t("uv_exporter.open_collada", "Open COLLADA model"), "", "COLLADA (*.dae);;All files (*)"
            )
            if path:
                self.fileDropped.emit(path)


class UVExporterTab(QWidget):
    def __init__(self, parent: QWidget | None = None, **_):
        super().__init__(parent)
        self.setObjectName("uvx_root")
        self._row_labels: list[tuple] = []

        self.current_mesh: UVMesh | None = None
        self.current_path: str | None = None
        self._current_source: CarModelSource | ModDaeSource | str | None = None
        self._carid: str | None = None
        self._variant = ""
        self._sources: list[CarModelSource | ModDaeSource] = []
        self._load_token = 0
        self._reloading_for_channel_switch = False
        self._workers: set[QThread] = set()
        self._render_worker: RenderWorker | None = None

        self._build_ui()
        self._apply_theme()
        self._update_resolution_hint()

    def _heading(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("heading", True)
        lbl.setFont(font(13, "bold"))
        return lbl

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(430)
        left_panel = QWidget()
        left_panel.setObjectName("uvx_left")
        left = QVBoxLayout(left_panel)
        left.setSpacing(12)

        self.h_model = self._heading("")
        left.addWidget(self.h_model)

        self.car_label = _WrapLabel("")
        self.car_label.setProperty("carlabel", True)
        self.car_label.hide()
        left.addWidget(self.car_label)

        self.model_combo = QComboBox()
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.model_combo.setMinimumContentsLength(8)
        self.model_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.model_combo.setMinimumWidth(0)
        self.model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        self.model_combo.hide()
        left.addWidget(self.model_combo)

        self.drop_zone = DropZone()
        self.drop_zone.fileDropped.connect(self._on_file_chosen)
        left.addWidget(self.drop_zone)

        self.locate_mod_btn = QPushButton("")
        self.locate_mod_btn.clicked.connect(self._on_locate_mod_clicked)
        self.locate_mod_btn.hide()
        left.addWidget(self.locate_mod_btn)

        self.file_label = _WrapLabel("")
        self.file_label.setProperty("muted", True)
        left.addWidget(self.file_label)

        self.load_progress = QProgressBar()
        self.load_progress.setRange(0, 0)
        self.load_progress.setTextVisible(False)
        self.load_progress.setFixedHeight(6)
        self.load_progress.hide()
        left.addWidget(self.load_progress)

        self.uv_channel_row = QWidget()
        ucr = QHBoxLayout(self.uv_channel_row)
        ucr.setContentsMargins(0, 0, 0, 0)
        self.uv_channel_combo = QComboBox()
        ucr.addLayout(self._labeled("uv_exporter.uv_channel", "UV channel", self.uv_channel_combo))
        self.uv_channel_row.setVisible(False)
        left.addWidget(self.uv_channel_row)

        self.h_groups = self._heading("")
        left.addWidget(self.h_groups)
        self.group_list = GroupListWidget()
        self.group_list.setMinimumHeight(180)
        self.group_list.selectionChanged.connect(self._update_export_enabled)
        self.group_list.auto_select_btn.clicked.connect(self._on_auto_select_clicked)
        left.addWidget(self.group_list)

        self.load_beamng_parts_btn = QPushButton("")
        self.load_beamng_parts_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.load_beamng_parts_btn.setMinimumWidth(0)
        self.load_beamng_parts_btn.setEnabled(False)
        self.load_beamng_parts_btn.clicked.connect(self._on_load_beamng_parts_clicked)
        left.addWidget(self.load_beamng_parts_btn)

        self.exporter_setup_btn = QPushButton("")
        self.exporter_setup_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.exporter_setup_btn.setMinimumWidth(0)
        self.exporter_setup_btn.clicked.connect(self._on_exporter_setup_clicked)
        left.addWidget(self.exporter_setup_btn)

        sel_row = QHBoxLayout()
        self.save_selection_btn = QPushButton("")
        self.save_selection_btn.setEnabled(False)
        self.save_selection_btn.clicked.connect(self._on_save_selection_clicked)
        sel_row.addWidget(self.save_selection_btn)
        self.clear_selection_btn = QPushButton("")
        self.clear_selection_btn.setFixedWidth(64)
        self.clear_selection_btn.setEnabled(False)
        self.clear_selection_btn.clicked.connect(self._on_clear_selection_clicked)
        sel_row.addWidget(self.clear_selection_btn)
        left.addLayout(sel_row)

        self.selection_status_label = QLabel("")
        self.selection_status_label.setWordWrap(True)
        self.selection_status_label.setProperty("ok", True)
        self.selection_status_label.hide()
        left.addWidget(self.selection_status_label)

        self.h_options = self._heading("")
        left.addWidget(self.h_options)
        opts_group = QGroupBox()
        ol = QVBoxLayout(opts_group)

        self.width_combo = QComboBox()
        self.height_combo = QComboBox()
        for combo in (self.width_combo, self.height_combo):
            for r in RESOLUTION_PRESETS:
                combo.addItem(str(r), r)
            combo.setCurrentIndex(RESOLUTION_PRESETS.index(4096))
            combo.currentIndexChanged.connect(self._update_resolution_hint)
        ol.addLayout(self._labeled("uv_exporter.width", "Width (px)", self.width_combo))
        ol.addLayout(self._labeled("uv_exporter.height", "Height (px)", self.height_combo))

        self.resolution_hint = QLabel("")
        self.resolution_hint.setProperty("muted", True)
        ol.addWidget(self.resolution_hint)

        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0.1, 64.0)
        self.line_width_spin.setSingleStep(0.5)
        self.line_width_spin.setValue(1.0)
        ol.addLayout(self._labeled("uv_exporter.line_width", "Line width (px)", self.line_width_spin))

        self.color_button = ColorPickerButton(QColor(0, 0, 0, 255))
        ol.addLayout(self._labeled("uv_exporter.line_color", "Line color", self.color_button))

        self.color_by_group_check = QCheckBox("")
        ol.addWidget(self.color_by_group_check)

        self.checker_bg_check = QCheckBox("")
        ol.addWidget(self.checker_bg_check)

        self.island_silhouette_check = QCheckBox("")
        ol.addWidget(self.island_silhouette_check)

        self.hide_quad_diagonals_check = QCheckBox("")
        ol.addWidget(self.hide_quad_diagonals_check)

        self.island_fill_check = QCheckBox("")
        ol.addWidget(self.island_fill_check)

        self.island_fill_options = QWidget()
        fo = QVBoxLayout(self.island_fill_options)
        fo.setContentsMargins(20, 0, 0, 0)
        self.fill_color_button = ColorPickerButton(QColor(255, 255, 255, 255))
        fo.addLayout(self._labeled("uv_exporter.fill_color", "Fill color", self.fill_color_button))
        op_row = QHBoxLayout()
        op_label = self.fill_opacity_label = QLabel("")
        op_label.setMinimumWidth(110)
        op_row.addWidget(op_label)
        self.fill_opacity_slider = QSlider(Qt.Horizontal)
        self.fill_opacity_slider.setRange(0, 100)
        self.fill_opacity_slider.setValue(20)
        op_row.addWidget(self.fill_opacity_slider)
        self.fill_opacity_value_label = QLabel("20%")
        self.fill_opacity_value_label.setFixedWidth(36)
        op_row.addWidget(self.fill_opacity_value_label)
        fo.addLayout(op_row)
        self.island_fill_options.setVisible(False)
        ol.addWidget(self.island_fill_options)

        self.auto_apply_selection_check = QCheckBox("")
        self.auto_apply_selection_check.setChecked(True)
        ol.addWidget(self.auto_apply_selection_check)

        left.addWidget(opts_group)
        left.addStretch()
        left_scroll.setWidget(left_panel)
        splitter.addWidget(left_scroll)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)

        self.h_preview = self._heading("")
        rl.addWidget(self.h_preview)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_label = QLabel("")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.preview_label.setMinimumSize(1, 1)
        self.preview_scroll.setWidget(self.preview_label)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(120)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self.preview_scroll.viewport().installEventFilter(self)
        rl.addWidget(self.preview_scroll, stretch=1)

        self.applying_overlay = QLabel(
            "",
            self.preview_scroll.viewport(),
        )
        self.applying_overlay.setAlignment(Qt.AlignCenter)
        self.applying_overlay.setWordWrap(True)
        self.applying_overlay.setFixedWidth(240)
        self.applying_overlay.hide()

        self.warnings_box = QTextEdit()
        self.warnings_box.setReadOnly(True)
        self.warnings_box.setMaximumHeight(90)
        self.warnings_box.hide()
        rl.addWidget(self.warnings_box)

        self.status_label = QLabel("")
        self.status_label.setProperty("muted", True)
        rl.addWidget(self.status_label)

        self.export_button = QPushButton("")
        self.export_button.setProperty("primary", True)
        self.export_button.setEnabled(False)
        self.export_button.setMinimumHeight(38)
        self.export_button.clicked.connect(self._on_export_clicked)
        rl.addWidget(self.export_button)

        self.render_progress = QProgressBar()
        self.render_progress.setRange(0, 0)
        self.render_progress.setTextVisible(False)
        self.render_progress.setFixedHeight(6)
        self.render_progress.hide()
        rl.addWidget(self.render_progress)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([460, 820])

        self.width_combo.currentIndexChanged.connect(self._refresh_preview)
        self.height_combo.currentIndexChanged.connect(self._refresh_preview)
        self.line_width_spin.valueChanged.connect(self._refresh_preview)
        self.color_by_group_check.stateChanged.connect(self._refresh_preview)
        self.checker_bg_check.stateChanged.connect(self._refresh_preview)
        self.island_silhouette_check.stateChanged.connect(self._refresh_preview)
        self.hide_quad_diagonals_check.stateChanged.connect(self._refresh_preview)
        self.island_fill_check.stateChanged.connect(self._on_island_fill_toggled)
        self.fill_color_button.colorChanged.connect(self._refresh_preview_with_overlay)
        self.fill_opacity_slider.valueChanged.connect(self._on_fill_opacity_changed)
        self.fill_opacity_slider.sliderReleased.connect(self._refresh_preview_with_overlay)
        self.color_button.colorChanged.connect(self._refresh_preview)
        self.group_list.selectionChanged.connect(self._refresh_preview)
        self.uv_channel_combo.currentIndexChanged.connect(self._on_uv_channel_changed)

        self._retranslate()

    def eventFilter(self, obj, event):
        if obj is self.preview_scroll.viewport() and event.type() == QEvent.Resize:
            if self.current_mesh is not None:
                self._preview_timer.start()
        return super().eventFilter(obj, event)

    def _retranslate(self):
        self.h_model.setText(_t("uv_exporter.model", "1. Model"))
        self.h_groups.setText(_t("uv_exporter.groups", "2. Groups to include"))
        self.h_options.setText(_t("uv_exporter.options", "3. Template options"))
        self.h_preview.setText(
            _t("uv_exporter.preview", "Preview (low-res proxy; export renders at full resolution)")
        )
        self.save_selection_btn.setText(
            _t("uv_exporter.save_selection", "Save selection for this file")
        )
        self.save_selection_btn.setToolTip(_t(
            "uv_exporter.save_selection_tip",
            "Remembers the checked groups, UV channel, and template options "
            "for this exact file so they're applied automatically next time.",
        ))
        self.clear_selection_btn.setText(_t("uv_exporter.clear", "Clear"))
        self.export_button.setText(_t("uv_exporter.export", "Export UV Template PNG…"))
        if self.current_mesh is None and not self.file_label.text():
            self.file_label.setText(_t("uv_exporter.no_file", "No model loaded"))
        if self.current_mesh is None:
            self.preview_label.setText(
                _t("uv_exporter.preview_empty", "Load a model to preview its UV layout")
            )
        self.drop_zone.apply_theme()

        for row, key, default in self._row_labels:
            row.itemAt(0).widget().setText(_t(key, default))
        self.fill_opacity_label.setText(_t("uv_exporter.fill_opacity", "Fill opacity"))
        self.model_combo.setToolTip(_t(
            "uv_exporter.model_combo_tip",
            "Every .dae found for this vehicle. The one named after the car ID "
            "is loaded first; pick another if it's the wrong model.",
        ))
        self.locate_mod_btn.setText(_t("uv_exporter.locate_mod", "Locate mod (folder / ZIP / .dae)…"))
        self.locate_mod_btn.setToolTip(_t(
            "uv_exporter.locate_mod_tip",
            "Point to where this vehicle's mod lives. The location is remembered.",
        ))
        self.load_beamng_parts_btn.setText(_t("uv_exporter.load_parts", "Load BeamNG parts…"))
        self.load_beamng_parts_btn.setToolTip(_t(
            "uv_exporter.load_parts_tip",
            "Check only the exterior body parts (bumpers, fenders, doors, hoods, mirrors, ...) "
            "whose mesh names are in a live-parts export from the BeamSkin Studio BeamNG UI app",
        ))
        self.exporter_setup_btn.setText(_t("uv_exporter.exporter_setup", "Exporter mod setup…"))
        self.exporter_setup_btn.setToolTip(_t(
            "uv_exporter.exporter_setup_tip",
            "Loading BeamNG parts needs the BeamSkin Studio exporter mod inside BeamNG. "
            "Install or update it and see how to use it",
        ))
        self.color_by_group_check.setText(_t("uv_exporter.color_by_group", "Color-code by material/group"))
        self.checker_bg_check.setText(_t("uv_exporter.checker_bg", "Checker background (scale reference)"))
        self.island_silhouette_check.setText(
            _t("uv_exporter.island_outlines", "Island outlines only (no triangulation)")
        )
        self.island_silhouette_check.setToolTip(_t(
            "uv_exporter.island_outlines_tip",
            "Draws only each UV island's outer edge instead of the full wireframe.",
        ))
        self.hide_quad_diagonals_check.setText(_t("uv_exporter.hide_quad_diagonals", "Hide quad diagonals"))
        self.hide_quad_diagonals_check.setToolTip(_t(
            "uv_exporter.hide_quad_diagonals_tip",
            "Hides the diagonal splitting two triangles that form a quad, "
            "so the result reads as a clean quad grid.",
        ))
        self.island_fill_check.setText(_t("uv_exporter.island_fill", "Fill islands with color"))
        self.island_fill_check.setToolTip(_t(
            "uv_exporter.island_fill_tip",
            "Fills each UV island with a translucent color, like the game's "
            "own shipped UV maps.",
        ))
        self.auto_apply_selection_check.setText(
            _t("uv_exporter.auto_apply_selection", "Auto-apply saved selection on load")
        )
        self.applying_overlay.setText(_t(
            "uv_exporter.applying",
            "Applying…\nThis may freeze the app for a minute or two.",
        ))
        self.group_list.retranslate()
        self._update_resolution_hint()

    def _labeled(self, key: str, default: str, widget: QWidget):
        row = make_labeled_row("", widget)
        self._row_labels.append((row, key, default))
        return row

    def _apply_theme(self):
        c = COLORS
        self.setStyleSheet(f"""
            QWidget#uvx_root {{ background:{c['app_bg']}; }}
            QWidget#uvx_left {{ background:{c['app_bg']}; }}
            QLabel {{ color:{c['text']}; background:transparent; }}
            QLabel[heading="true"] {{ color:{c['text']}; }}
            QLabel[muted="true"] {{ color:{c['text_secondary']}; font-size:11px; }}
            QLabel[ok="true"] {{ color:{c['success']}; font-size:10px; }}
            QLabel[carlabel="true"] {{
                color:{c['accent']}; font-weight:bold; font-size:13px;
            }}
            QScrollArea {{ background:transparent; border:none; }}
            QGroupBox {{
                background:{c['frame_bg']}; border:1px solid {c['border']};
                border-radius:8px; margin-top:6px; padding:8px;
            }}
            QPushButton {{
                background:{c['card_bg']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:6px; padding:6px 10px;
            }}
            QPushButton:hover {{ background:{c['card_hover']}; }}
            QPushButton:disabled {{ color:{c['text_muted']}; }}
            QPushButton[primary="true"] {{
                background:{c['accent']}; color:{c['accent_text']};
                border:none; font-weight:bold;
            }}
            QPushButton[primary="true"]:hover {{ background:{c['accent_hover']}; }}
            QPushButton[primary="true"]:disabled {{
                background:{c['accent_dim']}; color:{c['text_muted']};
            }}
            QComboBox, QDoubleSpinBox, QLineEdit {{
                background:{c['card_bg']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:4px; padding:3px 6px;
            }}
            QComboBox QAbstractItemView {{
                background:{c['card_bg']}; color:{c['text']};
                selection-background-color:{c['accent']};
                selection-color:{c['accent_text']};
            }}
            QListWidget {{
                background:{c['frame_bg']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:6px;
            }}
            QListWidget::item:hover {{ background:{c['card_hover']}; }}
            QCheckBox {{ color:{c['text']}; background:transparent; spacing:6px; }}
            QCheckBox::indicator, QListWidget::indicator {{
                width:15px; height:15px; border:1px solid {c['border']};
                border-radius:3px; background:{c['card_bg']};
            }}
            QCheckBox::indicator:checked, QListWidget::indicator:checked {{
                background:{c['accent']}; border-color:{c['accent']};
            }}
            QTextEdit {{
                background:{c['frame_bg']}; color:{c['warning']};
                border:1px solid {c['border']}; border-radius:6px;
            }}
            QProgressBar {{ background:{c['card_bg']}; border:none; border-radius:3px; }}
            QProgressBar::chunk {{ background:{c['accent']}; border-radius:3px; }}
            QSlider::groove:horizontal {{
                height:4px; background:{c['border']}; border-radius:2px;
            }}
            QSlider::sub-page:horizontal {{ background:{c['accent']}; border-radius:2px; }}
            QSlider::handle:horizontal {{
                width:14px; margin:-5px 0; border-radius:7px; background:{c['accent']};
            }}
        """)
        self.preview_scroll.setStyleSheet(
            f"QScrollArea {{ background:{c['frame_bg']}; border:1px solid {c['border']};"
            f" border-radius:8px; }}"
        )
        self.preview_label.setStyleSheet(
            f"color:{c['text_muted']};background:transparent;"
        )
        self.applying_overlay.setStyleSheet(
            f"background:{c['card_bg']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:6px;"
            f"padding:8px 16px;font-weight:600;"
        )
        self.group_list.apply_theme()
        self.color_button.apply_theme()
        self.fill_color_button.apply_theme()
        self.drop_zone.apply_theme()

    def refresh_ui(self):
        self._apply_theme()
        self._retranslate()
        self._refresh_preview()

    def load_for_car(self, carid: str, display_name: str | None = None, variant: str = ""):
        self._variant = variant or ""
        name = display_name or state.get_vehicle_name(carid)
        self._carid = carid
        self.car_label.setText(f"{name}  ({carid})")
        self.car_label.show()

        try:
            sources = list(find_car_dae_sources(carid))
        except Exception as e:
            print(f"[WARNING] uv_exporter: find_car_dae_sources failed: {type(e).__name__}: {e}")
            sources = []
        sources += mod_locations.find_dae_sources(carid)
        variant_sources = _variant_sources(carid, self._variant)
        sources += variant_sources
        self._sources = sources
        self.locate_mod_btn.show()

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for s in sources:
            self.model_combo.addItem(s.label, s)
            self.model_combo.setItemData(self.model_combo.count() - 1, s.label, Qt.ToolTipRole)
        self.model_combo.blockSignals(False)
        self.model_combo.setVisible(len(sources) > 1)

        if not sources:
            self._clear_loaded_state()
            msg = _t(
                "uv_exporter.no_dae_for_car",
                "No .dae model was found for this vehicle. Check the BeamNG "
                "install path in Settings, locate the mod, or drop a .dae file below.",
            )
            missing = mod_locations.missing_locations(carid)
            if missing:
                msg += "\n\n" + _t("uv_exporter.saved_location_missing", "Saved mod location not found:") + "\n" + "\n".join(missing)
            self.file_label.setText(msg)
            self._notify(
                _t("uv_exporter.no_dae_notify", "No .dae found for {carid}", carid=carid),
                "error",
                4000,
            )
            return

        self.model_combo.setCurrentIndex(0)
        self._start_load(sources[0])

    def _notify(self, msg: str, kind: str = "info", duration: int = 3000):
        try:
            mw = self.window()
            if hasattr(mw, "show_notification"):
                mw.show_notification(msg, type=kind, duration=duration)
                return
        except Exception as _exc:
            print(f"[WARNING] uv_exporter _notify: {type(_exc).__name__}: {_exc}")
        print(f"[{kind.upper()}] {msg}")

    def _clear_loaded_state(self):
        self._load_token += 1
        self.current_mesh = None
        self.current_path = None
        self._current_source = None
        self.load_progress.hide()
        self.group_list.populate([])
        self.uv_channel_row.setVisible(False)
        self.warnings_box.hide()
        self.preview_label.clear()
        self.preview_label.setText(
            _t("uv_exporter.preview_empty", "Load a model to preview its UV layout")
        )
        self.save_selection_btn.setEnabled(False)
        self.clear_selection_btn.setEnabled(False)
        self.load_beamng_parts_btn.setEnabled(False)
        self.selection_status_label.hide()
        self._update_export_enabled()

    def _on_model_combo_changed(self, index: int):
        source = self.model_combo.itemData(index)
        if isinstance(source, (CarModelSource, ModDaeSource, VariantDaeSource)):
            self._start_load(source)

    def _on_file_chosen(self, path: str):
        if not path.lower().endswith(".dae"):
            QMessageBox.warning(
                self,
                _t("uv_exporter.unsupported", "Unsupported file"),
                _t("uv_exporter.only_dae", "Only .dae (COLLADA) files are supported."),
            )
            return
        self._carid = None
        self._variant = ""
        self._sources = []
        self.car_label.hide()
        self.model_combo.hide()
        self.locate_mod_btn.hide()
        self._start_load(path)

    def _on_locate_mod_clicked(self):
        if not self._carid:
            return
        box = QMessageBox(self)
        box.setWindowTitle(_t("uv_exporter.locate_title", "Locate mod"))
        box.setText(_t("uv_exporter.locate_question", "What is the mod?"))
        b_folder = box.addButton(_t("uv_exporter.locate_folder", "Folder"), QMessageBox.AcceptRole)
        b_zip = box.addButton(_t("uv_exporter.locate_zip", "ZIP"), QMessageBox.AcceptRole)
        b_dae = box.addButton(_t("uv_exporter.locate_dae", ".dae file"), QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is b_folder:
            path = QFileDialog.getExistingDirectory(self, _t("uv_exporter.select_mod_folder", "Select mod folder"))
        elif clicked is b_zip:
            path, _ = QFileDialog.getOpenFileName(self, _t("uv_exporter.select_mod_zip", "Select mod ZIP"), "", "ZIP (*.zip);;All files (*)")
        elif clicked is b_dae:
            path, _ = QFileDialog.getOpenFileName(self, _t("uv_exporter.select_dae", "Select .dae"), "", "COLLADA (*.dae)")
        else:
            return
        if not path:
            return
        if not mod_locations.probe(self._carid, path):
            QMessageBox.warning(
                self,
                _t("uv_exporter.locate_title", "Locate mod"),
                _t("uv_exporter.no_dae_at_location", "No .dae file found at that location."),
            )
            return
        mod_locations.register(self._carid, path)
        self.load_for_car(self._carid, variant=self._variant)

    def _start_load(self, source: CarModelSource | str, uv_channel: str | None = None,
                    channel_switch: bool = False):
        try:
            if isinstance(source, CarModelSource):
                path = resolve_path(source)
            elif isinstance(source, ModDaeSource):
                path = mod_locations.materialize(source)
            elif isinstance(source, VariantDaeSource):
                path = source.materialize()
            else:
                path = source
        except (ValueError, OSError, zipfile.BadZipFile, KeyError) as e:
            QMessageBox.critical(self, _t("uv_exporter.load_failed_title", "Couldn't load model"), str(e))
            return

        self._current_source = source
        self.current_path = path
        self._reloading_for_channel_switch = channel_switch
        self.file_label.setText(
            f"{source.carid}: {source.member or source.path}"
            if isinstance(source, CarModelSource)
            else f"{source.carid}: {source.label}" if isinstance(source, (ModDaeSource, VariantDaeSource))
            else path
        )
        self.load_progress.show()
        self.export_button.setEnabled(False)
        self.warnings_box.hide()
        if not channel_switch:
            self.uv_channel_row.setVisible(False)
            self.save_selection_btn.setEnabled(False)
            self.clear_selection_btn.setEnabled(False)
            self.selection_status_label.hide()
            saved = load_selection(path) if self.auto_apply_selection_check.isChecked() else None
            uv_channel = saved.get("uv_channel") if saved else None
        self.status_label.setText(
            _t("uv_exporter.loading", "Loading {name}…", name=os.path.basename(path))
        )

        self._load_token += 1
        worker = LoadWorker(
            self._load_token, path if isinstance(source, (ModDaeSource, VariantDaeSource)) else source, uv_channel
        )
        worker.finished_ok.connect(self._on_load_success)
        worker.failed.connect(self._on_load_failed)
        self._track(worker)
        worker.start()

    def _track(self, worker: QThread):
        self._workers.add(worker)
        worker.finished.connect(lambda w=worker: self._workers.discard(w))

    def _on_load_success(self, token: int, mesh: UVMesh):
        if token != self._load_token:
            return
        self.load_progress.hide()
        self.current_mesh = mesh
        self.load_beamng_parts_btn.setEnabled(True)
        self.status_label.setText(
            _t("uv_exporter.loaded", "Loaded {groups} group(s), {triangles} triangles.",
               groups=len(mesh.groups), triangles=mesh.total_triangles)
        )

        group_infos = [(g.name, g.display_name, g.triangle_count) for g in mesh.groups]
        was_switch = self._reloading_for_channel_switch
        if was_switch:
            self.group_list.populate_preserving_checks(group_infos)
        else:
            self.group_list.populate(group_infos)
        self._reloading_for_channel_switch = False

        self._update_uv_channel_combo(mesh)

        applied_saved = False
        if not was_switch and self.auto_apply_selection_check.isChecked() and self.current_path:
            saved = load_selection(self.current_path)
            if saved:
                self._apply_saved_selection(saved, group_infos)
                applied_saved = True

        if self.current_path is not None:
            has_saved = load_selection(self.current_path) is not None
            self.save_selection_btn.setEnabled(True)
            self.clear_selection_btn.setEnabled(has_saved)
            if applied_saved:
                self.selection_status_label.setText("✓ Applied saved selection for this file.")
                self.selection_status_label.show()
            else:
                self.selection_status_label.hide()

        if mesh.warnings:
            self.warnings_box.setPlainText("\n".join(f"⚠ {w}" for w in mesh.warnings))
            self.warnings_box.show()
        else:
            self.warnings_box.hide()

        self._update_export_enabled()
        self._refresh_preview()

    def _on_load_failed(self, token: int, message: str):
        if token != self._load_token:
            return
        self.load_progress.hide()
        was_switch = self._reloading_for_channel_switch
        self._reloading_for_channel_switch = False

        if not was_switch:
            self.current_mesh = None
        elif self.current_mesh is not None:
            idx = self.uv_channel_combo.findData(self.current_mesh.active_uv_set)
            if idx >= 0:
                self.uv_channel_combo.blockSignals(True)
                self.uv_channel_combo.setCurrentIndex(idx)
                self.uv_channel_combo.blockSignals(False)

        self._update_export_enabled()
        self.status_label.setText(
            _t("uv_exporter.switch_failed_status", "Failed to switch UV channel.") if was_switch
            else _t("uv_exporter.load_failed_status", "Failed to load model.")
        )
        QMessageBox.critical(
            self,
            _t("uv_exporter.switch_failed_title", "Couldn't switch UV channel") if was_switch
            else _t("uv_exporter.load_failed_title", "Couldn't load model"),
            message,
        )

    def _update_uv_channel_combo(self, mesh: UVMesh):
        self.uv_channel_combo.blockSignals(True)
        self.uv_channel_combo.clear()
        for channel_id in mesh.available_uv_sets:
            self.uv_channel_combo.addItem(_t("uv_exporter.uv_set", "UV set {id}", id=channel_id), channel_id)
        idx = self.uv_channel_combo.findData(mesh.active_uv_set)
        self.uv_channel_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.uv_channel_combo.blockSignals(False)
        self.uv_channel_row.setVisible(len(mesh.available_uv_sets) > 1)

    def _on_uv_channel_changed(self, _index: int):
        if self._current_source is None or self.current_mesh is None:
            return
        selected = self.uv_channel_combo.currentData()
        if selected == self.current_mesh.active_uv_set:
            return
        self._start_load(self._current_source, uv_channel=selected, channel_switch=True)

    def _apply_saved_selection(self, saved: dict, group_infos: list[tuple]):
        available = {info[0] for info in group_infos}
        checked = set(saved.get("checked_groups", [])) & available
        if checked:
            self.group_list.set_checked(checked)

        o = saved.get("render_options", {})
        if "width" in o:
            i = self.width_combo.findData(o["width"])
            if i >= 0:
                self.width_combo.setCurrentIndex(i)
        if "height" in o:
            i = self.height_combo.findData(o["height"])
            if i >= 0:
                self.height_combo.setCurrentIndex(i)
        if "line_width" in o:
            self.line_width_spin.setValue(o["line_width"])
        if "line_color_rgba" in o:
            self.color_button.set_color(QColor(*o["line_color_rgba"]))
        if "color_by_group" in o:
            self.color_by_group_check.setChecked(o["color_by_group"])
        if "checker_background" in o:
            self.checker_bg_check.setChecked(o["checker_background"])
        if "island_silhouette_only" in o:
            self.island_silhouette_check.setChecked(o["island_silhouette_only"])
        if "hide_quad_diagonals" in o:
            self.hide_quad_diagonals_check.setChecked(o["hide_quad_diagonals"])
        if "fill_color_rgba" in o:
            self.fill_color_button.set_color(QColor(*o["fill_color_rgba"]))
        if "fill_opacity_pct" in o:
            self.fill_opacity_slider.setValue(o["fill_opacity_pct"])

    def _capture_current_selection(self) -> dict:
        color = self.color_button.color()
        fill = self.fill_color_button.color()
        return {
            "uv_channel": (
                self.uv_channel_combo.currentData() if self.uv_channel_row.isVisible() else None
            ),
            "checked_groups": sorted(self.group_list.checked_names()),
            "render_options": {
                "width": self.width_combo.currentData(),
                "height": self.height_combo.currentData(),
                "line_width": self.line_width_spin.value(),
                "line_color_rgba": [color.red(), color.green(), color.blue(), color.alpha()],
                "color_by_group": self.color_by_group_check.isChecked(),
                "checker_background": self.checker_bg_check.isChecked(),
                "island_silhouette_only": self.island_silhouette_check.isChecked(),
                "hide_quad_diagonals": self.hide_quad_diagonals_check.isChecked(),
                "fill_color_rgba": [fill.red(), fill.green(), fill.blue(), fill.alpha()],
                "fill_opacity_pct": self.fill_opacity_slider.value(),
            },
        }

    def _on_save_selection_clicked(self):
        if self.current_path is None:
            return
        save_selection(self.current_path, self._capture_current_selection())
        self.clear_selection_btn.setEnabled(True)
        self.selection_status_label.setText(
            f"✓ Saved selection for {os.path.basename(self.current_path)}."
        )
        self.selection_status_label.show()

    def _on_clear_selection_clicked(self):
        if self.current_path is None:
            return
        clear_selection(self.current_path)
        self.clear_selection_btn.setEnabled(False)
        self.selection_status_label.setText(_t("uv_exporter.selection_cleared", "Saved selection cleared."))
        self.selection_status_label.show()

    @staticmethod
    def _mesh_name_variants(name: str) -> set[str]:
        out = set()
        if name:
            out.add(name.casefold())
            if ":" in name:
                out.add(name.rsplit(":", 1)[0].casefold())
        return out

    def _on_exporter_setup_clicked(self):
        run_exporter_dialog(self, getattr(self, "_carid", "") or "", first_use=False)

    def _on_load_beamng_parts_clicked(self):
        if self.current_mesh is None:
            return
        if not exporter_gate(self, self._carid or ""):
            return
        try:
            from core.model_preview.beamng_parts import read_part_export
            from core.settings import get_mods_folder_path

            mods_folder = get_mods_folder_path()
            current_folder = os.path.dirname(os.path.normpath(mods_folder)) if mods_folder else ""
            export_folder = (
                os.path.join(current_folder, "settings", "beamskin_studio", self._carid)
                if current_folder and self._carid else ""
            )
            if export_folder:
                os.makedirs(export_folder, exist_ok=True)
            selected_path, _ = QFileDialog.getOpenFileName(
                self, _t("uv_exporter.parts_dialog_title", "Load BeamNG live-parts export"), export_folder or current_folder,
                "BeamSkin Studio live-parts export (*.json)",
            )
            if not selected_path:
                return
            model_id, mesh_names, part_count = read_part_export(selected_path)[:3]
        except (OSError, ValueError, json.JSONDecodeError) as e:
            QMessageBox.warning(
                self, _t("uv_exporter.parts_load_failed", "Could not load BeamNG parts"), str(e)
            )
            return

        if self._carid and model_id and model_id.casefold() != self._carid.casefold():
            answer = QMessageBox.question(
                self, _t("uv_exporter.model_mismatch_title", "Vehicle model does not match"),
                _t("uv_exporter.model_mismatch",
                   "The export is for '{model}', but this is '{carid}'. "
                   "Try matching the mesh names anyway?",
                   model=model_id, carid=self._carid),
            )
            if answer != QMessageBox.Yes:
                return

        wanted = {n.casefold() for n in mesh_names}
        matched: set[str] = set()
        matched_nodes: set[str] = set()
        for g in self.current_mesh.groups:
            hits = (self._mesh_name_variants(g.node_name) | self._mesh_name_variants(g.name)) & wanted
            if hits:
                matched.add(g.name)
                matched_nodes |= hits
        if not matched:
            QMessageBox.information(
                self, _t("uv_exporter.no_match_title", "No matching groups"),
                _t("uv_exporter.no_match",
                   "No mesh name from {file} matches a group of this model. "
                   "Check the selected model.",
                   file=os.path.basename(selected_path)),
            )
            return
        verdicts, _conflicts = auto_select_groups(self.current_mesh, skip_area_outlier=True)
        exterior = {v.name for v in verdicts if v.include}
        reasons = {v.name: v.reason for v in verdicts if not v.include and v.name in matched}
        chosen = matched & exterior
        if not chosen:
            QMessageBox.information(
                self, _t("uv_exporter.no_exterior_title", "No exterior parts"),
                _t("uv_exporter.no_exterior",
                   "{count} group(s) matched {file}, but none of them "
                   "is an exterior body part with usable UVs.",
                   count=len(matched), file=os.path.basename(selected_path)),
            )
            return
        self.group_list.set_checked_with_reasons(chosen, reasons)
        label = _t(
            "uv_exporter.parts_status",
            "BeamNG parts: {parts} selected; {nodes} mesh names matched, "
            "{chosen} exterior group(s) checked, {skipped} non-exterior skipped",
            parts=part_count, nodes=len(matched_nodes),
            chosen=len(chosen), skipped=len(matched) - len(chosen),
        )
        if model_id:
            label += f" ({model_id})"
        self.status_label.setText(label + ".")

    def _on_auto_select_clicked(self):
        if self.current_mesh is None:
            return
        verdicts, conflicts = auto_select_groups(self.current_mesh)
        included = {v.name for v in verdicts if v.include}
        reasons = {v.name: v.reason for v in verdicts if not v.include}

        node_to_identity = {
            g.node_name: g.name for g in self.current_mesh.groups if g.node_name
        }
        conflict_notes: dict[str, str] = {}
        for conflict in conflicts:
            identities = [node_to_identity[n] for n in conflict.group_names if n in node_to_identity]
            if len(identities) < 2:
                continue
            for identity in identities:
                others = [n for n in conflict.group_names if node_to_identity.get(n) != identity]
                conflict_notes[identity] = _t(
                    "uv_exporter.conflict_note",
                    "Couldn't automatically tell this apart from a likely variant "
                    "of the same part ({others}). Both are checked -- "
                    "uncheck whichever doesn't match your build.",
                    others=", ".join(others),
                )

        self.group_list.set_checked_with_reasons(included, reasons, conflict_notes)

        parts = [_t("uv_exporter.auto_checked", "Auto-select: checked {count} group(s)", count=len(included))]
        if reasons:
            parts.append(_t("uv_exporter.auto_excluded", "excluded {count} (hover excluded items for why)", count=len(reasons)))
        n_conf = sum(1 for c in conflicts if len(c.group_names) > 1)
        if n_conf:
            parts.append(_t("uv_exporter.auto_variants", "{count} part(s) have variants that need a manual pick", count=n_conf))
        self.status_label.setText(", ".join(parts) + ".")

    def _on_island_fill_toggled(self, _state):
        self.island_fill_options.setVisible(self.island_fill_check.isChecked())
        self._refresh_preview_with_overlay()

    def _on_fill_opacity_changed(self, value: int):
        self.fill_opacity_value_label.setText(f"{value}%")
        if not self.fill_opacity_slider.isSliderDown():
            self._refresh_preview_with_overlay()

    def _update_resolution_hint(self, *_):
        largest = max(self.width_combo.currentData(), self.height_combo.currentData())
        if largest >= 16384:
            self.resolution_hint.setText(
                _t("uv_exporter.hint_16k", "16K exports are large (~1GB working buffer) and can take 10-30s+.")
            )
        elif largest >= 8192:
            self.resolution_hint.setText(_t("uv_exporter.hint_8k", "8K exports may take several seconds."))
        else:
            self.resolution_hint.setText("")

    def _update_export_enabled(self):
        busy = self._render_worker is not None and self._render_worker.isRunning()
        self.export_button.setEnabled(
            self.current_mesh is not None
            and len(self.group_list.checked_names()) > 0
            and not busy
        )

    def _current_options(self, width: int | None = None, height: int | None = None) -> RenderOptions:
        color = self.color_button.color()
        fill = self.fill_color_button.color()
        rgba = (color.red(), color.green(), color.blue(), color.alpha())
        return RenderOptions(
            width=width or self.width_combo.currentData(),
            height=height or self.height_combo.currentData(),
            line_width=self.line_width_spin.value(),
            line_color=rgba,
            color_by_group=self.color_by_group_check.isChecked(),
            included_group_names=self.group_list.checked_names(),
            draw_checker_background=self.checker_bg_check.isChecked(),
            island_silhouette_only=self.island_silhouette_check.isChecked(),
            hide_quad_diagonals=self.hide_quad_diagonals_check.isChecked(),
            island_fill=self.island_fill_check.isChecked(),
            fill_color=(fill.red(), fill.green(), fill.blue(), fill.alpha()),
            fill_opacity=self.fill_opacity_slider.value() / 100.0,
            boundary_line_width=self.line_width_spin.value(),
            boundary_line_color=rgba,
        )

    def _position_applying_overlay(self):
        self.applying_overlay.adjustSize()
        vp = self.applying_overlay.parentWidget()
        self.applying_overlay.move(
            max(0, (vp.width() - self.applying_overlay.width()) // 2),
            max(0, (vp.height() - self.applying_overlay.height()) // 2),
        )

    def _refresh_preview_with_overlay(self, *_):
        if self.island_fill_check.isChecked() and self.current_mesh is not None:
            self._position_applying_overlay()
            self.applying_overlay.show()
            self.applying_overlay.raise_()
            QApplication.processEvents()
        try:
            self._refresh_preview()
        finally:
            self.applying_overlay.hide()

    def _refresh_preview(self, *_):
        if self.current_mesh is None:
            return
        fw = self.width_combo.currentData()
        fh = self.height_combo.currentData()
        vp = self.preview_scroll.viewport().size()
        avail_w = max(64, vp.width() - 4)
        avail_h = max(64, vp.height() - 4)
        scale = min(avail_w / fw, avail_h / fh, 2048 / max(fw, fh))
        pw, ph = max(1, round(fw * scale)), max(1, round(fh * scale))

        img = render_uv_template(self.current_mesh, self._current_options(pw, ph))

        lc = self.color_button.color()
        luminance = (0.299 * lc.red() + 0.587 * lc.green() + 0.114 * lc.blue()) / 255
        backdrop = QColor("#262626") if luminance > 0.5 and not self.color_by_group_check.isChecked() \
            else QColor("#e6e6e6")
        pix = QPixmap(img.size())
        pix.fill(backdrop)
        p = QPainter(pix)
        p.drawImage(0, 0, img)
        p.end()

        self.preview_label.setPixmap(pix)
        self._update_export_enabled()

    def _on_export_clicked(self):
        if self.current_mesh is None:
            return
        w = self.width_combo.currentData()
        h = self.height_combo.currentData()
        stem = self._carid or os.path.splitext(os.path.basename(self.current_path or "template"))[0]
        default_name = f"{stem}_uv_{w}x{h}.png"
        out_path, _ = QFileDialog.getSaveFileName(
            self, _t("uv_exporter.export_dialog_title", "Export UV Template"), default_name, "PNG image (*.png)"
        )
        if not out_path:
            return

        self.export_button.setEnabled(False)
        self.render_progress.show()
        self.status_label.setText(_t("uv_exporter.rendering", "Rendering {w}x{h} template…", w=w, h=h))

        worker = RenderWorker(self.current_mesh, self._current_options(), out_path)
        worker.finished_ok.connect(self._on_render_success)
        worker.failed.connect(self._on_render_failed)
        self._render_worker = worker
        self._track(worker)
        worker.start()

    def _on_render_success(self, out_path: str):
        self.render_progress.hide()
        self._render_worker = None
        self._update_export_enabled()
        self.status_label.setText(_t("uv_exporter.saved_to", "Saved to {path}", path=out_path))
        if self.current_path is not None:
            save_selection(self.current_path, self._capture_current_selection())
            self.clear_selection_btn.setEnabled(True)
        self._notify(_t("uv_exporter.exported", "UV template saved"), "success", 3000)

    def _on_render_failed(self, message: str):
        self.render_progress.hide()
        self._render_worker = None
        self._update_export_enabled()
        self.status_label.setText(_t("uv_exporter.export_failed_status", "Export failed."))
        QMessageBox.critical(self, _t("uv_exporter.export_failed_title", "Export failed"), message)
