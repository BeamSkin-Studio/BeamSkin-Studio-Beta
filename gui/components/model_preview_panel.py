from __future__ import annotations

import copy
import inspect
import json
import numpy as np
import os
from typing import Callable

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import QColorDialog
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from core.model_preview import store
from core.exterior_parts import has_exterior_part_name
from core.model_preview.dae_geometry import DaeParseError, PreviewModel
from core.model_preview.sources import PreviewSource, load_source
from core.model_preview.preview_jobs import PreviewJobs, sources_job, surface_job, texture_job
from core.model_preview import renderers
from core.model_preview import exporter_mod
from core.model_preview import material as material_mod
from gui.theme import COLORS, font
from gui.components.exporter_mod_dialog import exporter_gate, run_exporter_dialog

try:
    from core.localization import t
except ImportError:
    def t(key, default=None, **kw):
        text = default if default is not None else key
        try:
            return text.format(**kw)
        except Exception:
            return text


def _t(key: str, default: str, **kw) -> str:
    return t(key, default=default, **kw)

class _WrapLabel(QLabel):

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text: str):
        super().setText(
            text.replace("/", "/\u200b").replace("\\", "\\\u200b").replace("_", "_\u200b")
        )

    def setHtml(self, html: str):
        QLabel.setText(self, html)

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


_EXCLUDE_TOKENS = (
    "shadow", "collision", "colmesh", "hitbox", "_lod", "lod_", "lowpoly",
    "bounds", "helper", "debris", "dummy", "mechanicals", "piano", 
    "interior", "seat", "dash", "steering", "suspension", "exhaust",
)


_AUTO_RULES = 5

_DEFAULT_UV_SET = 1

_HAYSTACK_ROLE = Qt.UserRole + 1

_GLASS_TOKENS = ("glass", "window", "windshield", "windscreen", "backlight")


def _is_glass(name: str) -> bool:
    low = name.lower()
    return any(tok in low for tok in _GLASS_TOKENS)


_PLAIN_TOKENS = ("interior",)


def _is_interior(name: str) -> bool:
    low = name.lower()
    return any(tok in low for tok in _PLAIN_TOKENS)


def _is_plain(name: str) -> bool:
    return _is_interior(name) and not _is_glass(name)


def _skin_paint(image):
    if image is None or image.isNull():
        return None
    small = image.scaled(64, 64, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(
        QImage.Format_RGBA8888)
    ptr = small.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8, count=small.sizeInBytes()).reshape(
        small.height(), small.bytesPerLine() // 4, 4)[:, :small.width(), :3].reshape(-1, 3)
    luma = arr.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    arr = arr[luma > 28]
    if arr.shape[0] == 0:
        return None
    q = (arr >> 4).astype(np.int32)
    keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    top = np.bincount(keys).argmax()
    mean = arr[keys == top].mean(axis=0) / 255.0
    return tuple(round(float(v), 3) for v in mean)


def _lacks_skin_uv(group) -> bool:
    return (not group.has_uv) or bool(group.uv_fallback)


_FAMILY_SKIP = ("transparent", "black_hole", "glass", "screen", "light")


def _takes_skin(model, group) -> bool:
    if model is None or model.skin_materials is None or _lacks_skin_uv(group):
        return False
    key = group.material.casefold()
    if key in model.skin_materials:
        return True
    if _is_glass(group.name) or _is_plain(group.name) or any(t in key for t in _FAMILY_SKIP):
        return False
    return any(key.startswith(t + "_") for t in model.skin_materials)


def _auto_names(model) -> set[str]:
    def ok(g) -> bool:
        low = f"{g.name} {g.node}".lower()
        return (
            g.has_uv
            and has_exterior_part_name(g.node or g.name)
            and not any(tok in low for tok in _EXCLUDE_TOKENS)
        )

    candidates = [g for g in model.groups if ok(g)]
    return {g.name for g in candidates}


class _NullViewport:

    def __getattr__(self, name):
        return lambda *a, **k: None


class _LoadingOverlay(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mpv_loading")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)
        self.title = QLabel("Loading 3D preview…")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(font(14, "bold"))
        self.detail = QLabel("")
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setProperty("muted", True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedSize(260, 8)
        lay.addWidget(self.title)
        lay.addWidget(self.bar, 0, Qt.AlignCenter)
        lay.addWidget(self.detail)
        self.restyle()

    def restyle(self):
        c = COLORS
        self.setStyleSheet(f"""
            QWidget#mpv_loading {{ background:{c.get('app_bg', '#18181c')}; }}
            QLabel {{ color:{c.get('text', '#ffffff')}; background:transparent; }}
            QLabel[muted="true"] {{ color:{c.get('text_secondary', '#a0a0a8')}; font-size:11px; }}
            QProgressBar {{
                background:{c.get('card_bg', '#26262c')}; border:none; border-radius:4px;
            }}
            QProgressBar::chunk {{ background:{c.get('accent', '#4a9eff')}; border-radius:4px; }}
        """)

    def set_detail(self, text: str):
        self.detail.setText(text)


class _LoadWorker(QThread):
    done = Signal(int, object, str)

    def __init__(self, token: int, source: PreviewSource, uv_set: int = 0,
                 chosen_parts: dict | None = None, mesh_names=None, variant: str = "",
                 parent=None):
        super().__init__(parent)
        self._token = token
        self._source = source
        self._uv_set = uv_set
        self._chosen_parts = dict(chosen_parts or {})
        self._mesh_names = frozenset(mesh_names or ())
        self._variant = variant

    def run(self):
        try:
            model = load_source(
                self._source, self._uv_set, self._chosen_parts, self._mesh_names, self._variant)
            self.done.emit(self._token, model, "")
        except (DaeParseError, ValueError, OSError) as e:
            self.done.emit(self._token, None, str(e))
        except Exception as e:
            self.done.emit(self._token, None, f"{type(e).__name__}: {e}")


class _ThemedDialog(QDialog):

    def __init__(self, parent, title: str, heading: str, accept_text: str, danger: bool = False):
        super().__init__(parent)
        self.setObjectName("mpv_dialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(22, 20, 22, 18)
        self.root.setSpacing(10)

        self.heading = QLabel(heading)
        self.heading.setObjectName("mpv_dlg_heading")
        self.heading.setWordWrap(True)
        self.root.addWidget(self.heading)

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        self.root.addLayout(self.body)

        self.hint = QLabel("")
        self.hint.setObjectName("mpv_dlg_hint")
        self.hint.setWordWrap(True)
        self.hint.hide()
        self.root.addWidget(self.hint)

        self.root.addSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("mpv_dlg_cancel")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton(accept_text)
        self.ok_btn.setObjectName("mpv_dlg_danger" if danger else "mpv_dlg_ok")
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        for b in (self.cancel_btn, self.ok_btn):
            b.setMinimumSize(96, 34)
            row.addWidget(b)
        self.root.addLayout(row)
        self._restyle()

    def set_hint(self, text: str, warn: bool = False):
        self.hint.setProperty("warn", "true" if warn else "false")
        self.hint.style().unpolish(self.hint)
        self.hint.style().polish(self.hint)
        self.hint.setText(text)
        self.hint.setVisible(bool(text))

    def _restyle(self):
        c = COLORS
        accent = c.get("accent", "#ff6a00")
        border = c.get("border", "#3a3a42")
        self.setStyleSheet(f"""
            QDialog#mpv_dialog {{ background:{c.get('card_bg', '#26262c')}; }}
            QLabel {{ color:{c.get('text', '#ffffff')}; background:transparent; }}
            QLabel#mpv_dlg_heading {{ font-size:14px; font-weight:bold; }}
            QLabel#mpv_dlg_hint {{ color:{c.get('text_secondary', '#a0a0a8')}; font-size:11px; }}
            QLabel#mpv_dlg_hint[warn="true"] {{ color:{accent}; }}
            QLabel[muted="true"] {{ color:{c.get('text_secondary', '#a0a0a8')}; font-size:11px; }}
            QLineEdit {{
                background:{c.get('app_bg', '#18181c')}; color:{c.get('text', '#ffffff')};
                border:1px solid {c.get('text_muted', '#6a6a74')}; border-radius:6px; padding:8px 10px;
                selection-background-color:{accent}; selection-color:{c.get('accent_text', '#000000')};
            }}
            QLineEdit:hover {{ border-color:{c.get('text_secondary', '#a0a0a8')}; }}
            QLineEdit:focus {{ border:2px solid {accent}; padding:7px 9px; }}
            QPushButton {{ border-radius:6px; padding:6px 16px; font-weight:bold; }}
            QPushButton#mpv_dlg_cancel {{
                background:transparent; color:{c.get('text', '#ffffff')};
                border:1px solid {c.get('text_muted', '#6a6a74')};
            }}
            QPushButton#mpv_dlg_cancel:hover {{
                background:{c.get('card_hover', '#32323a')}; border-color:{c.get('text', '#ffffff')};
            }}
            QPushButton#mpv_dlg_ok {{
                background:{accent}; color:{c.get('accent_text', '#000000')}; border:1px solid {accent};
            }}
            QPushButton#mpv_dlg_ok:hover {{
                background:{c.get('accent_hover', accent)}; border-color:{c.get('accent_hover', accent)};
            }}
            QPushButton#mpv_dlg_ok:disabled {{
                background:{c.get('app_bg', '#18181c')}; color:{c.get('text_muted', '#6a6a74')};
                border:1px solid {border};
            }}
            QPushButton#mpv_dlg_danger {{
                background:{c.get('error', '#e74c3c')}; color:#ffffff; border:1px solid {c.get('error', '#e74c3c')};
            }}
            QPushButton#mpv_dlg_danger:hover {{ background:#ff5a47; border-color:#ff5a47; }}
        """)


class _PresetNameDialog(_ThemedDialog):

    def __init__(self, parent, existing: list[str], initial: str = ""):
        super().__init__(parent, "Save preset", "Save preset", "Save")
        self._existing = {n.lower(): n for n in existing}
        label = QLabel("Name")
        label.setProperty("muted", "true")
        self.body.addWidget(label)
        self.edit = QLineEdit(initial)
        self.edit.setPlaceholderText("e.g. Kombi, Roof lights, Without spoiler")
        self.edit.setMaxLength(80)
        self.edit.setClearButtonEnabled(True)
        self.edit.setMinimumHeight(38)
        self.edit.textChanged.connect(self._changed)
        self.edit.returnPressed.connect(self._try_accept)
        self.body.addWidget(self.edit)
        self._changed(initial)
        self.edit.setFocus()
        self.edit.selectAll()

    def _changed(self, text: str):
        name = text.strip()
        self.ok_btn.setEnabled(bool(name))
        if name and name.lower() in self._existing:
            self.set_hint(f"A preset named \"{self._existing[name.lower()]}\" already exists. "
                          f"Saving will ask before replacing it.", warn=True)
        else:
            self.set_hint("Saves which parts are shown for this model.")

    def _try_accept(self):
        if self.ok_btn.isEnabled():
            self.accept()

    def name(self) -> str:
        return self.edit.text().strip()


def _confirm(parent, title: str, heading: str, detail: str, accept_text: str, danger: bool = False) -> bool:
    dlg = _ThemedDialog(parent, title, heading, accept_text, danger=danger)
    if detail:
        dlg.set_hint(detail)
    return dlg.exec() == QDialog.Accepted


class ModelPreviewPanel(QWidget):
    ready = Signal()

    SIDEBAR_WIDTH = 150
    SIDEBAR_MAX_WIDTH = 420

    def __init__(self, texture_loader: Callable[[str], QImage | None], parent=None):
        super().__init__(parent)
        self._texture_loader = texture_loader
        self._carid: str | None = None
        self._variant = ""
        self._extra_roots: tuple[str, ...] = ()
        self._store_id = ""
        self._sources: list[PreviewSource] = []
        self._active_source: PreviewSource | None = None
        self._beamng_mesh_names: frozenset[str] | None = None
        self._beamng_export_path = ""
        self._beamng_export_model = ""
        self._beamng_part_count = 0
        self._model: PreviewModel | None = None
        self._model_key: str | None = None
        self._token = 0
        self._worker: _LoadWorker | None = None
        self._gl_error: str = ""
        self._chain: list = []
        self._chain_pos = -1
        self._failed_specs: set = set()
        self._demoted_software = False
        self._renderer_note = ""
        self._cur_image: QImage | None = None
        self._cur_full = False
        self._cur_material = None
        self._cur_variant_material = None
        self._surface_materials: dict = {}
        self._stage: dict | None = None
        self._stage_resolve = None
        self._stage_uv_flag = None
        self._material_cache: tuple | None = None
        self.viewport3d = _NullViewport()
        self._forced = False
        self._texture_cache: dict[tuple, QImage | None] = {}
        self._texture_entries: list[tuple[str, str]] = []
        try:
            self._loader_takes_full = len(inspect.signature(texture_loader).parameters) >= 2
        except (TypeError, ValueError):
            self._loader_takes_full = False

        self._jobs = PreviewJobs(self)
        self._jobs.finished.connect(self._on_job_done)
        self._tex_debounce = QTimer(self)
        self._tex_debounce.setSingleShot(True)
        self._tex_debounce.timeout.connect(self._submit_texture_job)
        self._submitted_stamp: tuple | None = None
        self._plain_key: tuple | None = None
        self._surface_busy = False
        self._tex_busy = False
        self._tex_reason = "load"
        self._badge_dots = 0
        self._badge_anim = QTimer(self)
        self._badge_anim.setInterval(350)
        self._badge_anim.timeout.connect(self._tick_badge)
        self._badge_hide_timer = QTimer(self)
        self._badge_hide_timer.setSingleShot(True)
        self._badge_hide_timer.timeout.connect(lambda: self._badge.hide())

        self._dirty = False
        self._applied_stamp: tuple | None = None
        self._pending_stamp: tuple | None = None
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(1000)
        self._watch_timer.timeout.connect(self._poll_files)
        self._watch_timer.start()

        self.setObjectName("mpv_root")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(10)
        root.addWidget(self._splitter)

        self._viewport_host = QWidget()
        self._viewport_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._viewport_stack = QStackedLayout(self._viewport_host)
        self._viewport_stack.setStackingMode(QStackedLayout.StackAll)
        self._viewport_stack.setContentsMargins(0, 0, 0, 0)
        self._loading = _LoadingOverlay()
        self._viewport_stack.addWidget(self._loading)
        self._loading_hide_timer = QTimer(self)
        self._loading_hide_timer.setSingleShot(True)
        self._loading_hide_timer.timeout.connect(self._finish_loading)
        self._badge = QFrame(self)
        self._badge.setObjectName("mpv_texture_status")
        self._badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        badge_layout = QVBoxLayout(self._badge)
        badge_layout.setContentsMargins(28, 22, 28, 22)
        badge_layout.setSpacing(12)
        self._badge_label = QLabel("")
        self._badge_label.setAlignment(Qt.AlignCenter)
        self._badge_label.setFont(font(13, "bold"))
        self._badge_label.setWordWrap(True)
        badge_layout.addWidget(self._badge_label)
        self._badge_bar = QProgressBar()
        self._badge_bar.setRange(0, 0)
        self._badge_bar.setTextVisible(False)
        self._badge_bar.setFixedHeight(8)
        badge_layout.addWidget(self._badge_bar)
        self._badge.setFixedSize(300, 100)
        c = COLORS
        self._badge.setStyleSheet(f"""
            QFrame#mpv_texture_status {{
                background:{c.get('card_bg', '#26262c')};
                border:1px solid {c.get('border', '#3a3a42')}; border-radius:10px;
            }}
            QLabel {{ color:{c.get('text', '#ffffff')}; background:transparent; }}
            QProgressBar {{
                background:{c.get('app_bg', '#18181c')}; border:none; border-radius:4px;
            }}
            QProgressBar::chunk {{
                background:{c.get('accent', '#4a9eff')}; border-radius:4px;
            }}
        """)
        self._badge.hide()
        self._viewport_host.installEventFilter(self)

        self._interaction_overlay = QFrame(self)
        self._interaction_overlay.setObjectName("mpv_busy_overlay")
        self._interaction_overlay.setAttribute(Qt.WA_StyledBackground, True)
        self._interaction_overlay.setStyleSheet(
            "QFrame#mpv_busy_overlay { background:rgba(16, 16, 18, 155); }"
        )
        self._interaction_overlay.hide()
        self._splitter.addWidget(self._viewport_host)

        side_scroll = QScrollArea()
        side_scroll.setWidgetResizable(True)
        side_scroll.setFrameShape(QFrame.NoFrame)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side_scroll.setMinimumWidth(320)
        side_scroll.setMaximumWidth(self.SIDEBAR_MAX_WIDTH)
        side_host = QWidget()
        side_host.setObjectName("mpv_side")
        side = QVBoxLayout(side_host)
        side.setContentsMargins(0, 0, 6, 0)
        side.setSpacing(8)
        side_scroll.setWidget(side_host)
        self._splitter.addWidget(side_scroll)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([10000, self.SIDEBAR_WIDTH])

        self.h_model = self._heading("Model")
        side.addWidget(self.h_model)

        self.model_combo = QComboBox()
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.model_combo.setMinimumContentsLength(8)
        self.model_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.model_combo.setMinimumWidth(0)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        side.addWidget(self.model_combo)

        self.model_label = _WrapLabel("")
        self.model_label.setProperty("muted", True)
        side.addWidget(self.model_label)

        self.uv_combo = QComboBox()
        self.uv_combo.addItems(["UV set 1", "UV set 2"])
        self.uv_combo.setVisible(False)
        self.uv_combo.currentIndexChanged.connect(self._on_uv_changed)
        side.addWidget(self.uv_combo)

        self.h_texture = self._heading("Texture")
        side.addWidget(self.h_texture)

        self.texture_combo = QComboBox()
        self.texture_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.texture_combo.setMinimumContentsLength(8)
        self.texture_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.texture_combo.setMinimumWidth(0)
        self.texture_combo.currentIndexChanged.connect(self._apply_texture)
        side.addWidget(self.texture_combo)

        self.texture_empty = _WrapLabel("No skin texture selected yet.")
        self.texture_empty.setProperty("muted", True)
        side.addWidget(self.texture_empty)

        self.full_res_check = QCheckBox("Full resolution textures")
        self.full_res_check.setToolTip(
            "Use the texture at its native size (up to 8192 px) instead of 2048 px.\n"
            "Sharper, but slower to load and uses more video memory."
        )
        self.full_res_check.setChecked(bool(store.get_option("full_res_textures", False)))
        self.full_res_check.toggled.connect(self._on_full_res_toggled)
        side.addWidget(self.full_res_check)

        self.refresh_btn = QPushButton("Refresh textures")
        self.refresh_btn.setToolTip("Reload the skin textures from disk and redraw the model")
        self.refresh_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.refresh_btn.setMinimumWidth(0)
        self.refresh_btn.clicked.connect(lambda: self._reload_textures())
        side.addWidget(self.refresh_btn)

        self.auto_refresh_check = QCheckBox("Auto-refresh when texture files change")
        self.auto_refresh_check.setToolTip(
            "Checks the texture files about once a second and redraws the model\n"
            "as soon as one of them has been saved or replaced.")
        self.auto_refresh_check.setChecked(bool(store.get_option("auto_refresh_textures", True)))
        self.auto_refresh_check.toggled.connect(
            lambda on: store.set_option("auto_refresh_textures", bool(on)))
        side.addWidget(self.auto_refresh_check)

        self._paint_colors = [QColor.fromRgbF(*c) for c in material_mod.DEFAULT_PAINTS]
        self.paint_row = QWidget()
        paint_lay = QHBoxLayout(self.paint_row)
        paint_lay.setContentsMargins(0, 0, 0, 0)
        paint_lay.setSpacing(6)
        self.paint_btns = []
        for i in range(3):
            b = QPushButton(f"Paint {i + 1}")
            b.setToolTip("Pick the colour BeamNG would use for this paint slot on the colorable skin")
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setMinimumWidth(0)
            b.clicked.connect(lambda _=False, i=i: self._pick_paint(i))
            paint_lay.addWidget(b)
            self.paint_btns.append(b)
        self.paint_row.setVisible(False)
        side.addWidget(self.paint_row)
        self._style_paint_buttons()

        self.parts_label = self._heading("Visible parts")
        side.addWidget(self.parts_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self.all_btn = QPushButton("All")
        self.all_btn.setToolTip("Show every part (only the ones matching the search, if one is active)")
        self.none_btn = QPushButton("None")
        self.none_btn.setToolTip("Hide every part (only the ones matching the search, if one is active)")
        self.auto_btn = QPushButton("Auto")
        self.auto_btn.setToolTip(
            "Select named exterior parts with UVs and drop any loaded BeamNG parts "
            "(press Save selection to keep it)"
        )
        self.view_btn = QPushButton("Reset view")
        for i, b in enumerate((self.all_btn, self.none_btn, self.auto_btn, self.view_btn)):
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setMinimumWidth(0)
            grid.addWidget(b, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.load_beamng_parts_btn = QPushButton(_t("uv_exporter.load_parts", "Load BeamNG parts…"))
        self.load_beamng_parts_btn.setToolTip(
            "Use the live mesh names exported by the BeamSkin Studio BeamNG UI app"
        )
        self.load_beamng_parts_btn.clicked.connect(self._load_beamng_parts)
        self.load_beamng_parts_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.load_beamng_parts_btn.setMinimumWidth(0)
        grid.addWidget(self.load_beamng_parts_btn, 2, 0, 1, 2)
        self.exporter_setup_btn = QPushButton(_t("model_preview.btn_exporter_setup", "Exporter mod setup…"))
        self.exporter_setup_btn.setToolTip(_t(
            "model_preview.btn_exporter_setup_tip",
            "Install or update the BeamNG exporter mod and see how to use it",
        ))
        self.exporter_setup_btn.clicked.connect(self._exporter_setup)
        self.exporter_setup_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.exporter_setup_btn.setMinimumWidth(0)
        grid.addWidget(self.exporter_setup_btn, 3, 0, 1, 2)
        side.addLayout(grid)
        self.beamng_parts_status = _WrapLabel("")
        self.beamng_parts_status.setProperty("muted", True)
        self.beamng_parts_status.setVisible(False)
        side.addWidget(self.beamng_parts_status)
        self.all_btn.clicked.connect(lambda: self._set_all(True))
        self.none_btn.clicked.connect(lambda: self._set_all(False))
        self.auto_btn.clicked.connect(self._reset_to_auto)
        self.view_btn.clicked.connect(lambda: self.viewport3d and self.viewport3d.reset_view())

        self.h_presets = self._heading("Presets")
        side.addWidget(self.h_presets)

        self.preset_combo = QComboBox()
        self.preset_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.setMinimumContentsLength(8)
        self.preset_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.preset_combo.setMinimumWidth(0)
        self.preset_combo.setToolTip("Saved part selections for this model")
        self.preset_combo.currentIndexChanged.connect(self._update_preset_buttons)
        self.preset_combo.activated.connect(lambda _i: self._load_preset())
        side.addWidget(self.preset_combo)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        self.preset_load_btn = QPushButton("Load")
        self.preset_load_btn.setToolTip("Apply the selected preset to the part list")
        self.preset_save_btn = QPushButton("Save as…")
        self.preset_save_btn.setToolTip("Save the parts that are checked now as a named preset.\n"
                                        "Use an existing name to overwrite that preset.")
        self.preset_del_btn = QPushButton("Delete")
        self.preset_del_btn.setToolTip("Delete the selected preset")
        for b in (self.preset_load_btn, self.preset_save_btn, self.preset_del_btn):
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setMinimumWidth(0)
            preset_row.addWidget(b, 1)
        side.addLayout(preset_row)
        self.preset_load_btn.clicked.connect(self._load_preset)
        self.preset_save_btn.clicked.connect(self._save_preset)
        self.preset_del_btn.clicked.connect(self._delete_preset)
        self._refresh_presets()

        self.save_btn = QPushButton("Save selection")
        self.save_btn.setObjectName("mpv_save")
        self.save_btn.setToolTip(
            "Remember which parts are shown for this model.\n"
            "Nothing is saved until you press this button.")
        self.save_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.save_btn.setMinimumWidth(0)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_selection)
        side.addWidget(self.save_btn)

        self._keywords: list[str] = []
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a keyword, press Enter to add it")
        self.search.setToolTip(
            "Type a word and press Enter to add it as a keyword.\n"
            "Only parts whose name contains ALL keywords are listed.\n"
            "Click a keyword below to remove it. Backspace on an empty box removes the last one.")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._apply_filter())
        self.search.returnPressed.connect(self._commit_keyword)
        self.search.installEventFilter(self)
        side.addWidget(self.search)

        self.keyword_label = _WrapLabel("")
        self.keyword_label.setTextFormat(Qt.RichText)
        self.keyword_label.setOpenExternalLinks(False)
        self.keyword_label.linkActivated.connect(self._on_keyword_link)
        self.keyword_label.setVisible(False)
        side.addWidget(self.keyword_label)

        self.match_label = _WrapLabel("")
        self.match_label.setProperty("muted", True)
        side.addWidget(self.match_label)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(180)
        self.list_widget.setTextElideMode(Qt.ElideMiddle)
        self.list_widget.setWordWrap(False)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.itemChanged.connect(self._on_item_changed)
        side.addWidget(self.list_widget, 1)

        self.renderer_label = _WrapLabel("")
        self.renderer_label.setProperty("muted", True)
        side.addWidget(self.renderer_label)

        self.status = _WrapLabel("")
        self.status.setProperty("muted", True)
        side.addWidget(self.status)

        self._update_texture_visibility()
        self.apply_theme()

        self._pref_cb = self._on_renderer_pref_changed
        renderers.add_listener(self._pref_cb)
        self.destroyed.connect(lambda *_: renderers.remove_listener(self._pref_cb))
        self._rebuild_viewport()

    def _heading(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("heading", True)
        lbl.setFont(font(13, "bold"))
        return lbl

    def apply_theme(self):
        c = COLORS
        if hasattr(self, "_loading"):
            self._loading.restyle()
        if self.viewport3d is not None:
            self.viewport3d.set_background(QColor(c.get("app_bg", "#18181c")))
        self.setStyleSheet(f"""
            QWidget#mpv_root {{ background:{c['app_bg']}; }}
            QWidget#mpv_side {{ background:{c['app_bg']}; }}
            QScrollArea {{ background:transparent; border:none; }}
            QSplitter::handle {{ background:transparent; }}
            QLabel {{ color:{c['text']}; background:transparent; }}
            QLabel[heading="true"] {{ color:{c['text']}; }}
            QLabel[muted="true"] {{ color:{c['text_secondary']}; font-size:11px; }}
            QPushButton {{
                background:{c['card_bg']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:6px; padding:6px 10px;
            }}
            QPushButton:hover {{ background:{c['card_hover']}; }}
            QPushButton:disabled {{ color:{c['text_muted']}; }}
            QPushButton#mpv_save {{
                background:{c['accent']}; color:{c['accent_text']};
                border:none; font-weight:bold;
            }}
            QPushButton#mpv_save:hover {{ background:{c['accent_hover']}; }}
            QPushButton#mpv_save:disabled {{
                background:{c['card_bg']}; color:{c['text_muted']};
                border:1px solid {c['border']};
            }}
            QComboBox, QLineEdit {{
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
            QListWidget::item {{ padding:2px 2px; }}
            QListWidget::item:hover {{ background:{c['card_hover']}; }}
            QCheckBox {{ color:{c['text']}; background:transparent; spacing:6px; }}
            QCheckBox::indicator, QListWidget::indicator {{
                width:15px; height:15px; border:1px solid {c['border']};
                border-radius:3px; background:{c['card_bg']};
            }}
            QCheckBox::indicator:checked, QListWidget::indicator:checked {{
                background:{c['accent']}; border-color:{c['accent']};
            }}
        """)

    def _on_renderer_pref_changed(self):
        self._rebuild_viewport()

    def _rebuild_viewport(self):
        pref = renderers.get_preference()
        self._chain = renderers.build_chain(pref)
        self._forced = pref != renderers.AUTO
        self._failed_specs = set()
        self._demoted_software = False
        self._gl_error = ""
        self._renderer_note = ""
        print(f"[DEBUG] model preview: renderer preference={pref!r} chain={self._chain}")
        self._activate(0)

    def _create_viewport(self, spec):
        kind, backend = spec
        if kind == "gl":
            from gui.components.model_viewport import ModelViewport
            return ModelViewport()
        from gui.components.wgpu_viewport import WgpuViewport
        return WgpuViewport(backend=backend)

    def _activate(self, pos: int, note: str = ""):
        last_error = ""
        for i in range(pos, len(self._chain)):
            spec = self._chain[i]
            if spec in self._failed_specs:
                continue
            try:
                vp = self._create_viewport(spec)
            except Exception as e:
                last_error = f"{renderers.spec_name(spec)}: {type(e).__name__}: {e}"
                print(f"[WARNING] model preview: could not create {renderers.spec_name(spec)} viewport: {last_error}")
                self._failed_specs.add(spec)
                continue
            self._chain_pos = i
            self._install_viewport(vp, spec)
            self._renderer_note = note
            self.renderer_label.setText(
                f"Renderer: {renderers.spec_name(spec)}" + (f"  ·  {note}" if note else ""))
            renderers.set_active(renderers.spec_name(spec))
            return
        self._chain_pos = -1
        self.viewport3d = _NullViewport()
        msg = last_error or "no usable renderer"
        self._on_gl_error(msg, None)

    def _install_viewport(self, vp, spec):
        vp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vp.glError.connect(lambda message, vp=vp: self._on_gl_error(message, vp))
        vp.rendererInfo.connect(lambda desc, software, vp=vp: self._on_renderer_info(desc, software, vp))
        old = self.viewport3d
        if isinstance(old, QWidget) and old is not vp:
            self._viewport_stack.removeWidget(old)
            old.hide()
            old.deleteLater()
        self._viewport_stack.insertWidget(0, vp)
        self._loading.raise_()
        self.viewport3d = vp
        vp.set_background(QColor(COLORS.get("app_bg", "#18181c")))
        if self._model is not None:
            vp.set_model(self._model)
            vp.set_unskinned_groups({g.name for g in self._model.groups if _is_glass(g.name)})
            vp.set_plain_groups({g.name for g in self._model.groups if _is_plain(g.name)})
            vp.set_skin_groups(self._viewport_skin_group_names(self._model))
            vp.set_variant_material(
                self._cur_variant_material, self._variant_skin_group_names(self._model),
                full_res=self._cur_full)
            vp.set_surface_materials(self._surface_materials)
            vp.set_surface_assignments(self._surface_assignments(self._model))
            vp.set_visible_groups(self._checked(), refit=True)
        if self._cur_material is not None:
            vp.set_material(self._cur_material, full_res=self._cur_full)
            vp.set_palette_colors([(c.redF(), c.greenF(), c.blueF()) for c in self._paint_colors])
        elif self._cur_image is not None:
            vp.set_texture_image(self._cur_image, full_res=self._cur_full)
        self._gl_error = ""

    def _on_renderer_info(self, description: str, software: bool, vp):
        if vp is not self.viewport3d:
            return
        self.renderer_label.setText(
            f"Renderer: {description}" + (f"  ·  {self._renderer_note}" if self._renderer_note else ""))
        renderers.set_active(description)
        print(f"[DEBUG] model preview: active renderer = {description!r} software={software}")
        spec = self._chain[self._chain_pos] if 0 <= self._chain_pos < len(self._chain) else None
        if (software and not self._forced and not self._demoted_software
                and spec is not None and spec[0] == "gl"):
            later = [i for i in range(self._chain_pos + 1, len(self._chain))
                     if self._chain[i] not in self._failed_specs]
            if later:
                self._demoted_software = True
                note = "OpenGL was software-only, switched automatically"
                QTimer.singleShot(0, lambda i=later[0], n=note: self._activate(i, n))

    def _on_gl_error(self, message: str, vp=None):
        if vp is not None and vp is not self.viewport3d:
            return
        self._gl_error = message
        spec = self._chain[self._chain_pos] if 0 <= self._chain_pos < len(self._chain) else None
        if spec is not None:
            self._failed_specs.add(spec)
        if not self._forced:
            later = [i for i in range(len(self._chain))
                     if self._chain[i] not in self._failed_specs]
            if later and spec is not None:
                note = f"{renderers.spec_name(spec)} failed, switched automatically"
                print(f"[WARNING] model preview: {renderers.spec_name(spec)} failed ({message}); trying next renderer")
                QTimer.singleShot(0, lambda i=later[0], n=note: self._activate(i, n))
                return
        hint = ("  Pick another renderer in Settings > Advanced > 3D preview renderer."
                if self._forced else
                "  Install 'wgpu' (pip install wgpu) or pick a renderer in Settings > Advanced.")
        if spec is not None:
            self.renderer_label.setText(f"Renderer: {renderers.spec_name(spec)} (not available)")
        renderers.set_active("")
        self.status.setText(f"3D preview error: {message.rstrip('.')}.{hint}")

    def _style_paint_buttons(self):
        for col, btn in zip(self._paint_colors, self.paint_btns):
            lum = 0.299 * col.redF() + 0.587 * col.greenF() + 0.114 * col.blueF()
            fg = "#000000" if lum > 0.55 else "#ffffff"
            btn.setStyleSheet(f"QPushButton {{ background:{col.name()}; color:{fg}; }}")

    def _pick_paint(self, i: int):
        col = QColorDialog.getColor(self._paint_colors[i], self, f"Paint {i + 1}")
        if col.isValid():
            self._paint_colors[i] = col
            self._style_paint_buttons()
            self._send_paints()

    def _send_paints(self):
        if self.viewport3d is not None:
            self.viewport3d.set_palette_colors(
                [(c.redF(), c.greenF(), c.blueF()) for c in self._paint_colors])

    def _push_texture(self, image, full: bool):
        self.paint_row.setVisible(False)
        self._cur_image, self._cur_full = image, full
        self._cur_material = None
        self._cur_variant_material = None
        self._update_surface_paint(None)
        if self.viewport3d is not None:
            self.viewport3d.set_material(None)
            self.viewport3d.set_variant_material(None, set())
            self.viewport3d.set_texture_image(image, full_res=full)
            self._push_surface_assignments()

    def _push_material(self, material, full: bool):
        if isinstance(material, material_mod.PreviewMaterialSet):
            base, variant = material.base, material.variant
        else:
            base, variant = material, None
        self._cur_material, self._cur_variant_material, self._cur_full = base, variant, full
        self._cur_image = base.albedo
        self._update_surface_paint(_skin_paint(base.albedo))
        self.paint_row.setVisible(base.palette is not None)
        if self.viewport3d is not None:
            self.viewport3d.set_material(base, full_res=full)
            self.viewport3d.set_variant_material(
                variant, self._variant_skin_group_names(self._model), full_res=full)
            self._push_surface_assignments()
            self._send_paints()

    def _update_surface_paint(self, paint):
        if paint == getattr(self, "_surface_paint", None):
            return
        self._surface_paint = paint
        if self._model is not None and getattr(self, "_surface_materials", None):
            self._submit_surface_job(self._model)

    def _push_surface_assignments(self):
        self.viewport3d.set_surface_assignments(self._surface_assignments(self._model))

    def _surface_assignments(self, model: PreviewModel | None) -> dict[str, str]:
        if model is None or not self._surface_materials:
            return {}
        variant = self._variant_skin_group_names(model)
        has_variant_skin = self._cur_variant_material is not None
        out: dict[str, str] = {}
        for g in model.groups:
            key = g.material.casefold()
            if key not in self._surface_materials or _is_glass(g.name):
                continue
            if not _is_plain(g.name):
                if g.name in variant:
                    if has_variant_skin:
                        continue
                elif model.skin_materials is None:
                    continue
                elif _takes_skin(model, g):
                    continue
            out[g.name] = key
        stamp = (id(model), bool(self._stage), len(out), len(model.groups))
        if stamp != getattr(self, "_surface_log_stamp", None):
            self._surface_log_stamp = stamp
            print(f"[DEBUG] model preview surfaces: {len(out)} of {len(model.groups)} groups drawn with stock "
                  f"material, stage={'yes' if self._stage else 'no'}, "
                  f"skin_materials={sorted(model.skin_materials) if model.skin_materials is not None else None}, "
                  f"dae materials={sorted({g.material.casefold() for g in model.groups})}")
        return out

    def _stop_surface_busy(self):
        self._surface_busy = False
        if not self._tex_busy:
            self._hide_badge()

    def _submit_surface_job(self, model: PreviewModel):
        self._jobs.cancel("surfaces")
        self._surface_materials = {}
        defs, vfs = getattr(model, "material_defs", None), getattr(model, "material_vfs", None)
        used = {g.material.casefold() for g in model.groups if g.active}
        defs = {key: value for key, value in (defs or {}).items() if key in used}
        if not defs or vfs is None:
            self._stop_surface_busy()
            return
        loader = self._load_image
        self._surface_busy = True
        self._show_badge("load")
        self.status.setText("Loading textures…")
        self._jobs.submit("surfaces", lambda: surface_job(model, defs, vfs, loader, getattr(self, "_surface_paint", None)))

    def _clear_car_texture_state(self):
        self._tex_debounce.stop()
        self._jobs.cancel("texture")
        self._jobs.cancel("surfaces")
        self._surface_busy = False
        self._surface_materials = {}
        self._tex_busy = False
        self._plain_key = None
        self._submitted_stamp = None
        self._applied_stamp = None
        self._pending_stamp = None
        self._material_cache = None
        self._texture_cache.clear()
        self._stage = None
        self._stage_resolve = None
        self._stage_uv_flag = None
        self._texture_entries = []
        self.texture_combo.blockSignals(True)
        self.texture_combo.clear()
        self.texture_combo.blockSignals(False)
        self._update_texture_visibility()
        self._hide_badge()
        self._push_texture(None, self._cur_full)

    def set_car(
        self,
        carid: str | None,
        force: bool = False,
        variant: str = "",
        extra_roots: tuple[str, ...] = (),
    ):
        variant = variant or ""
        extra_roots = tuple(extra_roots)
        car_changed = carid != self._carid
        variant_changed = variant != self._variant
        if car_changed:
            self._clear_beamng_part_selection()
            self._extra_roots = ()
            self._active_source = None
        elif variant_changed:
            self._extra_roots = ()
        if car_changed:
            self._clear_car_texture_state()
        if not carid:
            self._clear_beamng_part_selection()
            self._carid = None
            self._variant = self._store_id = ""
            self._extra_roots = ()
            self._sources = []
            self._active_source = None
            self._invalidate_load()
            self._jobs.cancel("sources")
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.blockSignals(False)
            self._update_model_label()
            self._show_model(None)
            self._end_loading()
            self.status.setText("Select a car to preview.")
            return
        if (
            carid == self._carid
            and variant == self._variant
            and extra_roots == self._extra_roots
            and not force
        ):
            return
        self._carid = carid
        self._variant = variant
        self._extra_roots = extra_roots
        self._store_id = carid + (f"__{variant}" if variant else "")

        self._invalidate_load()
        self._sources = []
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.blockSignals(False)
        self._update_model_label()
        self._show_model(None)
        self._begin_loading("Looking for models…")
        self.status.setText("Looking for models…")
        self._jobs.submit(
            "sources",
            lambda: sources_job(carid, extra_roots),
        )

    def _mods_folder(self, ask: bool = False) -> str:
        try:
            from core.settings import get_mods_folder_path
            folder = get_mods_folder_path() or ""
        except Exception:
            folder = ""
        if folder and os.path.isdir(folder):
            return folder
        if not ask:
            return ""
        return QFileDialog.getExistingDirectory(
            self, "Select your BeamNG mods folder", os.path.expanduser("~")
        )

    def _exporter_gate(self) -> bool:
        return exporter_gate(self, self._carid)

    def _exporter_setup(self):
        run_exporter_dialog(self, self._carid, first_use=False)

    def _load_beamng_parts(self):
        if not self._carid:
            QMessageBox.information(
                self,
                _t("model_preview.no_vehicle_title", "No vehicle selected"),
                _t("model_preview.no_vehicle", "Load a vehicle model first."),
            )
            return
        try:
            from core.model_preview.beamng_parts import read_part_export
            from core.settings import get_mods_folder_path

            mods_folder = get_mods_folder_path()
            current_folder = (
                os.path.dirname(os.path.normpath(mods_folder)) if mods_folder else ""
            )
            export_folder = os.path.join(
                current_folder, "settings", "beamskin_studio", self._carid
            ) if current_folder else ""
            if not self._exporter_gate():
                return
            if export_folder:
                os.makedirs(export_folder, exist_ok=True)
            start_path = export_folder or current_folder
            selected_path, _ = QFileDialog.getOpenFileName(
                self,
                "Load BeamNG live-parts export",
                start_path,
                "BeamSkin Studio live-parts export (*.json)",
            )
            if not selected_path:
                return
            model_id, mesh_names, part_count, _chosen = read_part_export(selected_path)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "Could not load BeamNG parts", str(e))
            return

        if model_id and model_id.casefold() != self._carid.casefold():
            answer = QMessageBox.question(
                self,
                "Vehicle model does not match",
                f"The export is for '{model_id}', but the preview is '{self._carid}'. "
                "Try matching the mesh names anyway?",
            )
            if answer != QMessageBox.Yes:
                return

        self._beamng_mesh_names = mesh_names
        self._beamng_export_path = selected_path
        self._beamng_export_model = model_id
        self._beamng_part_count = part_count
        if self._model is not None:
            self._apply_beamng_part_selection(self._model)
        else:
            self.beamng_parts_status.setText(
                f"Loaded {len(mesh_names)} mesh names; they will be matched when the model loads."
            )
            self.beamng_parts_status.setVisible(True)

    def _beamng_visible_groups(self, model: PreviewModel) -> set[str]:
        if self._beamng_mesh_names is None:
            return set()
        mesh_names = {name.casefold() for name in self._beamng_mesh_names}
        return {
            group.name for group in model.groups
            if group.node.casefold() in mesh_names
        }

    def _apply_beamng_part_selection(self, model: PreviewModel) -> bool:
        visible = self._beamng_visible_groups(model)
        if not visible:
            self.beamng_parts_status.setText(
                f"No DAE mesh names from {os.path.basename(self._beamng_export_path)} "
                "match this model. Check the selected model."
            )
            self.beamng_parts_status.setVisible(True)
            return False
        matched_nodes = {
            group.node.casefold() for group in model.groups if group.name in visible
        }
        self._fill_list(model, visible)
        self.viewport3d.set_visible_groups(visible, refit=True)
        label = (
            f"BeamNG parts: {self._beamng_part_count} selected; "
            f"{len(matched_nodes)} mesh names matched"
        )
        if self._beamng_export_model:
            label += f" ({self._beamng_export_model})"
        self.beamng_parts_status.setText(label)
        self.beamng_parts_status.setVisible(True)
        return True

    def _clear_beamng_part_selection(self):
        self._beamng_mesh_names = None
        self._beamng_export_path = ""
        self._beamng_export_model = ""
        self._beamng_part_count = 0
        if hasattr(self, "beamng_parts_status"):
            self.beamng_parts_status.clear()
            self.beamng_parts_status.hide()

    def _clear_beamng_parts(self):
        self._clear_beamng_part_selection()
        if self._model is not None:
            visible = self._default_visible_groups(self._model)
            self._fill_list(self._model, visible)
            self.viewport3d.set_visible_groups(visible, refit=True)

    def _on_sources(self, token: int, sources, error: str):
        if not self._jobs.is_current("sources", token):
            return
        if error or sources is None:
            self._end_loading()
            self.status.setText(f"Model search failed: {error}")
            return
        self._sources = list(sources)
        selected_model_key = (
            self.model_combo.currentData().key
            if isinstance(self.model_combo.currentData(), PreviewSource)
            else store.get_model(self._store_id)
        )

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for s in self._sources:
            self.model_combo.addItem(s.label, s)
            self.model_combo.setItemData(self.model_combo.count() - 1, s.label, Qt.ToolTipRole)
        index = 0
        if selected_model_key:
            for i, s in enumerate(self._sources):
                if s.key == selected_model_key:
                    index = i
                    break
        if self._sources:
            self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)
        self.model_combo.setVisible(len(self._sources) > 1)
        self._update_model_label()

        if not self._sources:
            self._show_model(None)
            self._end_loading()
            self.status.setText(
                "No .dae model found for this vehicle. Use Locate mod in the UV Exporter tab "
                "to point to the mod."
            )
            return
        self._start_load(self._sources[index])

    def _update_model_label(self):
        i = self.model_combo.currentIndex()
        if 0 <= i < len(self._sources):
            self.model_label.setText(self._sources[i].label)
            self.model_label.setToolTip(self._sources[i].label)
        else:
            self.model_label.setText("")
        self.model_label.setVisible(bool(self.model_label.text()))

    def _update_texture_visibility(self):
        n = len(self._texture_entries)
        self.texture_combo.setVisible(n > 1)
        self.texture_empty.setVisible(n == 0)

    def set_textures(self, entries: list[tuple[str, str]]):
        previous = self.texture_combo.currentData()
        self._texture_entries = [(label, path) for label, path in entries if path and os.path.isfile(path)]
        self.texture_combo.blockSignals(True)
        self.texture_combo.clear()
        for label, path in self._texture_entries:
            self.texture_combo.addItem(label, path)
        if previous:
            i = self.texture_combo.findData(previous)
            if i >= 0:
                self.texture_combo.setCurrentIndex(i)
        self.texture_combo.blockSignals(False)
        self._update_texture_visibility()
        self._apply_texture()

    def _on_full_res_toggled(self, checked: bool):
        store.set_option("full_res_textures", bool(checked))
        self._apply_texture()

    def set_material_stage(self, stage: dict | None, resolve: Callable[[str], str | None] | None = None):
        self._stage = stage or None
        self._stage_resolve = resolve
        if self.viewport3d is not None:
            self.viewport3d.set_skin_groups(self._viewport_skin_group_names(self._model))
            self._push_surface_assignments()
        self._follow_stage_uv()
        self._apply_texture()

    def _skin_group_names(self, model: PreviewModel | None) -> set[str] | None:
        if not self._stage or model is None or model.skin_materials is None:
            return None
        return {group.name for group in model.groups if _takes_skin(model, group)}

    def _viewport_skin_group_names(self, model: PreviewModel | None) -> set[str] | None:
        groups = self._skin_group_names(model)
        if groups is None:
            return None
        return groups - self._variant_skin_group_names(model)

    def _variant_skin_group_names(self, model: PreviewModel | None) -> set[str]:
        if model is None or not model.variant_skin_materials:
            return set()
        return {
            group.name for group in model.groups
            if group.material.casefold() in model.variant_skin_materials and not _lacks_skin_uv(group)
        }

    def _wanted_uv(self):
        if not self._stage or "diffuseMapUseUV" not in self._stage:
            return None
        try:
            return 1 if int(self._stage["diffuseMapUseUV"]) else 0
        except (TypeError, ValueError):
            return None

    def _follow_stage_uv(self):
        want = self._wanted_uv()
        if want == self._stage_uv_flag:
            return
        self._stage_uv_flag = want
        if want is None or self._model is None or self._model.uv_set_count < 2:
            return
        if self.uv_combo.currentIndex() != want:
            self.uv_combo.setCurrentIndex(want)

    def _load_image(self, path: str, full: bool):
        if self._loader_takes_full:
            return self._texture_loader(path, full)
        return self._texture_loader(path)

    def _apply_texture(self, *_):
        self._tex_debounce.start(150)

    @staticmethod
    def _plain_cache_key(path: str, full: bool):
        try:
            return (path, os.path.getmtime(path), os.path.getsize(path), full)
        except OSError:
            return None

    _BADGE_STYLES = {
        "load": "Loading textures",
        "update": "Texture files changed, updating",
        "reload": "Reloading textures",
        "done": "",
    }

    def _show_badge(self, kind: str, text: str = ""):
        self._badge_kind = kind
        self._badge_base = text or self._BADGE_STYLES[kind]
        self._badge_hide_timer.stop()
        self._badge_dots = 0
        self._tick_badge(advance=False)
        self._badge_bar.setVisible(kind != "done")
        self._badge.layout().activate()
        if kind == "done":
            self._set_texture_busy(False)
        else:
            self._set_texture_busy(True)
        self._badge.show()
        self._position_badge()
        self._badge.raise_()
        if kind == "done":
            self._badge_anim.stop()
            self._badge_hide_timer.start(1600)
        else:
            self._badge_anim.start()

    def _tick_badge(self, advance: bool = True):
        if advance:
            self._badge_dots = (self._badge_dots + 1) % 4
        if getattr(self, "_badge_kind", "") == "done":
            self._badge_label.setText(self._badge_base)
        else:
            self._badge_label.setText(self._badge_base + "…" if self._badge_base else "")
        self._position_badge()

    def _position_badge(self):
        if not hasattr(self, "_badge") or not self._badge.isVisible():
            return
        host = self._viewport_host
        center = host.mapTo(self, host.rect().center())
        self._badge.move(
            max(0, center.x() - self._badge.width() // 2),
            max(0, center.y() - self._badge.height() // 2),
        )

    def _set_texture_busy(self, busy: bool):
        self._splitter.setEnabled(not busy)
        if busy:
            self._interaction_overlay.setGeometry(self.rect())
            self._interaction_overlay.show()
            self._interaction_overlay.raise_()
            self._badge.raise_()
        else:
            self._interaction_overlay.hide()

    def _hide_badge(self):
        self._badge_anim.stop()
        self._badge_hide_timer.stop()
        self._badge.hide()
        self._set_texture_busy(False)

    def _submit_texture_job(self, reason: str = "load"):
        if self._cur_material is None and self._cur_image is None and reason == "update":
            reason = "load"
        self._tex_reason = reason
        full = self.full_res_check.isChecked()
        path = self.texture_combo.currentData()
        stage = copy.deepcopy(self._stage) if self._stage else None
        self._submitted_stamp = self._files_stamp()
        self._plain_key = None

        if not stage:
            if not path:
                self._jobs.cancel("texture")
                self._tex_busy = False
                self._hide_badge()
                self._push_texture(None, full)
                self._applied_stamp, self._pending_stamp = self._submitted_stamp, None
                return
            key = self._plain_cache_key(path, full)
            if key is not None and key in self._texture_cache:
                self._jobs.cancel("texture")
                self._tex_busy = False
                self._hide_badge()
                self._push_texture(self._texture_cache[key], full)
                self._applied_stamp, self._pending_stamp = self._submitted_stamp, None
                return
            self._plain_key = key

        resolve = self._stage_resolve or (lambda value: value)
        loader = self._load_image
        cached = self._material_cache
        self._tex_busy = True
        self._show_badge(reason if reason in ("load", "update", "reload") else "load")
        self.status.setText({"load": "Loading textures…", "update": "Texture files changed, updating…",
                             "reload": "Reloading textures…"}.get(reason, "Loading textures…"))
        self._jobs.submit(
            "texture", lambda: texture_job(stage, resolve, path, full, loader, cached))

    def _on_job_done(self, kind: str, token: int, result, error: str):
        if kind == "sources":
            self._on_sources(token, result, error)
            return
        if kind == "surfaces":
            if not self._jobs.is_current(kind, token):
                return
            if error or result is None:
                print(f"[WARNING] model preview: stock materials failed: {error or 'no result'}")
                self._stop_surface_busy()
                return
            model, materials = result
            if model is not self._model:
                self._stop_surface_busy()
                return
            self._surface_materials = materials
            self.viewport3d.set_surface_materials(materials)
            self._push_surface_assignments()
            self._surface_busy = False
            if not self._tex_busy:
                self._show_badge("done", "Textures loaded  \u2713")
            return
        if kind != "texture" or not self._jobs.is_current(kind, token):
            return
        self._tex_busy = False
        if error or result is None:
            if self._surface_busy:
                self._show_badge("load")
            else:
                self._hide_badge()
            self.status.setText(f"Texture update failed: {error or 'no texture could be read'}")
            return
        what, payload, stamp, full = result
        if what == "material":
            self._material_cache = (stamp, full, payload)
            self._push_material(payload, full)
        else:
            key = self._plain_key
            if key is not None:
                self._texture_cache = {k: v for k, v in self._texture_cache.items() if k[0] != key[0]}
                self._texture_cache[key] = payload
            self._push_texture(payload, full)
        self._applied_stamp, self._pending_stamp = self._submitted_stamp, None
        verb = "updated" if self._tex_reason in ("update", "reload") else "loaded"
        if self._surface_busy:
            self._show_badge("load")
        else:
            self._show_badge("done", f"Textures {verb}  \u2713")
        if self._model is not None:
            self._update_status()
            self.status.setText(self.status.text() + f"  ·  textures {verb}")
        else:
            self.status.setText(f"Textures {verb}")

    def _watched_files(self) -> list[str]:
        paths = [p for _, p in self._texture_entries]
        if self._stage:
            try:
                resolve = self._stage_resolve or (lambda value: value)
                paths += list(material_mod.stage_files(self._stage, resolve).values())
            except Exception:
                pass
        return paths

    def _files_stamp(self) -> tuple:
        out = []
        for path in sorted(set(self._watched_files())):
            try:
                st = os.stat(path)
                out.append((path, st.st_mtime_ns, st.st_size))
            except OSError:
                out.append((path, 0, 0))
        return tuple(out)

    def _poll_files(self):
        if not self.isVisible() or not self.auto_refresh_check.isChecked():
            return
        if self._tex_busy:
            return
        stamp = self._files_stamp()
        if stamp == self._applied_stamp:
            self._pending_stamp = None
            return
        if stamp != self._pending_stamp:
            self._pending_stamp = stamp
            return
        self._reload_textures(auto=True)

    def _reload_textures(self, auto: bool = False):
        self._texture_cache.clear()
        self._material_cache = None
        self._tex_debounce.stop()
        self._submit_texture_job("update" if auto else "reload")

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._catch_up)

    def _catch_up(self):
        if (self.isVisible() and self.auto_refresh_check.isChecked() and not self._tex_busy
                and self._files_stamp() != self._applied_stamp):
            self._reload_textures(auto=True)

    def _invalidate_load(self):
        self._token += 1

    def _begin_loading(self, detail: str = ""):
        self._loading_hide_timer.stop()
        self._loading.set_detail(detail)
        self._loading.show()
        self._loading.raise_()

    def _finish_loading(self):
        self._loading.hide()
        self.ready.emit()

    def _end_loading(self):
        self._loading_hide_timer.start(150)

    def _on_model_changed(self, index: int):
        if index < 0 or index >= len(self._sources) or not self._carid:
            return
        store.set_model(self._store_id, self._sources[index].key)
        self._update_model_label()
        self._start_load(self._sources[index])

    def _on_uv_changed(self, _index: int):
        if self._carid and self._active_source is not None:
            self._start_load(self._active_source, keep_uv=True)

    def _start_load(self, source: PreviewSource, keep_uv: bool = False):
        self._invalidate_load()
        self._active_source = source
        if not keep_uv:
            self.uv_combo.blockSignals(True)
            want = self._wanted_uv()
            self.uv_combo.setCurrentIndex(_DEFAULT_UV_SET if want is None else want)
            self.uv_combo.blockSignals(False)
        self._model_key = source.key
        self._show_model(None)
        self._begin_loading(source.label)
        self.status.setText("Loading model…")
        worker = _LoadWorker(
            self._token, source, self.uv_combo.currentIndex(), None, None, self._variant, self)
        worker.done.connect(self._on_loaded)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_loaded(self, token: int, model, error: str):
        if token != self._token:
            return
        try:
            self._handle_loaded(model, error)
        except Exception as e:
            self._end_loading()
            self.status.setText(f"Preview error: {type(e).__name__}: {e}")
            print(f"[ERROR] model preview: {type(e).__name__}: {e}")

    def _handle_loaded(self, model, error: str):
        if model is None:
            self._show_model(None)
            self._end_loading()
            self.status.setText(error or "Could not load the model.")
            return
        if model.uv_set_count < 2 and self.uv_combo.currentIndex() != 0:
            self.uv_combo.blockSignals(True)
            self.uv_combo.setCurrentIndex(0)
            self.uv_combo.blockSignals(False)
            if self._active_source is not None:
                self._start_load(self._active_source, keep_uv=True)
                return
        self._show_model(model)
        self.uv_combo.setVisible(model.uv_set_count > 1)
        visible = self._default_visible_groups(model)
        if self._beamng_mesh_names is not None:
            if not self._apply_beamng_part_selection(model):
                self._fill_list(model, visible)
                self.viewport3d.set_visible_groups(visible, refit=True)
        else:
            self._fill_list(model, visible)
            self.viewport3d.set_visible_groups(visible, refit=True)
        self._refresh_presets()
        self._log_glass(model)
        self._update_status()
        warn = f"  ·  {len(model.warnings)} warning(s)" if model.warnings else ""
        self.status.setText(self.status.text() + warn)
        self._end_loading()

    def _default_visible_groups(self, model: PreviewModel) -> set[str]:
        selection = (
            store.get_selection(self._store_id, self._model_key, _AUTO_RULES)
            if self._store_id else None
        )
        auto = _auto_names(model)
        if selection is None:
            return auto
        saved_visible, saved_hidden = selection
        return {
            group.name for group in model.groups
            if group.name in saved_visible
            or (group.name not in saved_hidden and group.name in auto)
        }

    def _glass_summary(self, model: PreviewModel) -> str:
        glass = [g for g in model.groups if _is_glass(g.name)]
        if not glass:
            return ""
        no_uv = sum(1 for g in glass if not g.has_uv)
        fallback = sum(1 for g in glass if g.has_uv and g.uv_fallback)
        text = f"glass: {len(glass)} parts (drawn without skin)"
        if no_uv:
            text += f", {no_uv} without UVs"
        if fallback:
            text += f", {fallback} lack the selected UV set"
        return text

    def _log_glass(self, model: PreviewModel):
        shown = 0
        for g in model.groups:
            if _is_glass(g.name):
                shown += 1
                if shown > 25:
                    print("[DEBUG] model preview glass: ... (more glass parts not listed)")
                    break
                print(
                    f"[DEBUG] model preview glass: {g.name} tris={g.count // 3} "
                    f"has_uv={g.has_uv} uv_sets={g.uv_sets} fallback={g.uv_fallback} "
                    f"uv_range={tuple(round(v, 3) for v in g.uv_range)}"
                )

    def _show_model(self, model: PreviewModel | None):
        self._model = model
        self.viewport3d.set_model(model)
        self.viewport3d.set_unskinned_groups(
            {g.name for g in model.groups if _is_glass(g.name)} if model is not None else set()
        )
        self.viewport3d.set_plain_groups(
            {g.name for g in model.groups if _is_plain(g.name)} if model is not None else set()
        )
        self.viewport3d.set_skin_groups(self._viewport_skin_group_names(model))
        self.viewport3d.set_variant_material(
            self._cur_variant_material, self._variant_skin_group_names(model),
            full_res=self._cur_full)
        self._surface_materials = {}
        self._jobs.cancel("surfaces")
        if self._surface_busy:
            self._stop_surface_busy()
        self.viewport3d.set_surface_materials({})
        self.viewport3d.set_surface_assignments({})
        if model is not None:
            self._submit_surface_job(model)
        self._set_dirty(False)
        self.save_btn.setEnabled(model is not None)
        self._refresh_presets()
        if model is None:
            self.list_widget.blockSignals(True)
            self.list_widget.clear()
            self.list_widget.blockSignals(False)

    def _fill_list(self, model: PreviewModel, visible: set[str]):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        skin_groups = self._skin_group_names(model)
        for g in model.groups:
            tris = g.count // 3
            note = ""
            if not g.has_uv:
                note = "  [no UVs]"
            elif g.uv_fallback:
                note = f"  [only {g.uv_sets} UV set(s)]"
            item = QListWidgetItem(f"{g.name}  ({tris} tris){note}")
            item.setData(Qt.UserRole, g.name)
            item.setData(_HAYSTACK_ROLE, g.name.lower())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if g.name in visible else Qt.Unchecked)
            tip = f"{g.name}\n{tris} tris"
            if g.source:
                tip += f"\nModel file: {g.source}"
            if _is_glass(g.name):
                tip += "\nGlass: drawn as plain translucent glass, the skin is not applied"
            if _is_plain(g.name):
                tip += "\nInterior: drawn plain, the skin is not applied"
            if (
                self._stage
                and model.skin_materials is not None
                and skin_groups is not None
                and g.name not in skin_groups
                and not _is_glass(g.name)
                and not _is_plain(g.name)
            ):
                tip += "\nThe selected vehicle material does not accept the active skin layer"
            if not g.has_uv:
                tip += "\nNo UV data: the skin cannot be shown on this part"
            elif g.uv_fallback:
                tip += (
                    f"\nThis part only has {g.uv_sets} UV set(s), so the selected UV set "
                    "does not exist on it. The skin is not drawn on it (the game shows the "
                    "base material there, e.g. an interior floor); it uses its stock material."
                )
            elif g.uv_range:
                u0, v0, u1, v1 = g.uv_range
                tip += f"\nUV range: U {u0:.2f}..{u1:.2f}, V {v0:.2f}..{v1:.2f}"
            item.setToolTip(tip)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        self._apply_filter()

    def _checked(self) -> set[str]:
        return {
            self.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.Checked
        }

    def _on_item_changed(self, _item):
        self._push_visibility()

    def _push_visibility(self):
        self.viewport3d.set_visible_groups(self._checked())
        self._update_status()
        self._set_dirty(True)

    def _set_all(self, checked: bool):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.list_widget.blockSignals(False)
        self._push_visibility()

    def _reset_to_auto(self):
        if self._model is None or not self._carid or not self._model_key:
            return
        self._clear_beamng_part_selection()
        visible = _auto_names(self._model)
        self._fill_list(self._model, visible)
        self.viewport3d.set_visible_groups(visible, refit=True)
        self._update_status()
        self._set_dirty(True)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "_viewport_host", None) and event.type() == QEvent.Resize:
            self._position_badge()
        if (obj is getattr(self, "search", None) and event.type() == QEvent.KeyPress
                and event.key() == Qt.Key_Backspace
                and not self.search.text() and self._keywords):
            self._keywords.pop()
            self._refresh_keywords()
            self._apply_filter()
            return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_interaction_overlay"):
            self._interaction_overlay.setGeometry(self.rect())
        self._position_badge()

    def _commit_keyword(self):
        added = False
        for word in self.search.text().lower().split():
            if word not in self._keywords:
                self._keywords.append(word)
                added = True
        self.search.clear()
        if added:
            self._refresh_keywords()
            self._apply_filter()

    def _on_keyword_link(self, link: str):
        if link == "clear":
            self._keywords.clear()
        elif link.startswith("rm:"):
            word = link[3:]
            if word in self._keywords:
                self._keywords.remove(word)
        self._refresh_keywords()
        self._apply_filter()

    def _refresh_keywords(self):
        if not self._keywords:
            self.keyword_label.setVisible(False)
            self.keyword_label.setHtml("")
            return
        from html import escape
        accent = COLORS.get("accent", "#4a9eff")
        chips = "  ".join(
            f'<a href="rm:{escape(w, quote=True)}" style="color:{accent}; text-decoration:none;">'
            f'[{escape(w)} ✕]</a>' for w in self._keywords)
        clear = (f'  <a href="clear" style="color:{COLORS.get("text_secondary", "#a0a0a8")};">clear all</a>'
                 if len(self._keywords) > 1 else "")
        self.keyword_label.setHtml(chips + clear)
        self.keyword_label.setVisible(True)

    def _apply_filter(self, *_):
        terms = list(self._keywords) + self.search.text().lower().split()
        total = self.list_widget.count()
        shown = 0
        for i in range(total):
            item = self.list_widget.item(i)
            hay = item.data(_HAYSTACK_ROLE) or (item.data(Qt.UserRole) or "").lower()
            hide = bool(terms) and not all(t in hay for t in terms)
            item.setHidden(hide)
            shown += 0 if hide else 1
        if terms:
            self.match_label.setText(
                f"{shown} of {total} parts match. All / None only affect these."
                if shown else "No parts match."
            )
        else:
            self.match_label.setText("")
        self.match_label.setVisible(bool(terms))

    def _update_status(self):
        if self._model is None:
            return
        checked = self._checked()
        tris = sum(g.count for g in self._model.groups if g.name in checked) // 3
        text = f"{len(checked)} of {len(self._model.groups)} parts shown, {tris} tris"
        glass = self._glass_summary(self._model)
        if glass:
            text += f"  ·  {glass}"
        n_plain = sum(1 for g in self._model.groups if g.name in checked and _is_plain(g.name))
        if n_plain:
            text += f"  ·  interior: {n_plain} parts (drawn without skin)"
        if self._gl_error:
            text = f"[3D error: {self._gl_error}]  " + text
        self.status.setText(text)

    def _set_dirty(self, dirty: bool):
        self._dirty = bool(dirty)
        self.save_btn.setText("Save selection  ●" if self._dirty else "Save selection")

    def _save_selection(self):
        if self._model is None or not self._carid or not self._model_key:
            return
        visible = self._checked()
        hidden = [g.name for g in self._model.groups if g.name not in visible]
        store.set_selection(self._store_id, self._model_key, sorted(visible), hidden, _AUTO_RULES)
        self._set_dirty(False)
        self._update_status()
        self.status.setText(self.status.text() + "  ·  selection saved")


    def _preset_ready(self) -> bool:
        return self._model is not None and bool(self._store_id) and bool(self._model_key)

    def _refresh_presets(self, select: str | None = None):
        keep = select if select is not None else self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        if self._preset_ready():
            for name in store.list_presets(self._store_id, self._model_key):
                self.preset_combo.addItem(name)
            i = self.preset_combo.findText(keep) if keep else -1
            if i >= 0:
                self.preset_combo.setCurrentIndex(i)
        self.preset_combo.blockSignals(False)
        self._update_preset_buttons()

    def _update_preset_buttons(self, *_):
        ready = self._preset_ready()
        has = self.preset_combo.count() > 0
        self.preset_combo.setEnabled(ready and has)
        self.preset_load_btn.setEnabled(ready and has)
        self.preset_del_btn.setEnabled(ready and has)
        self.preset_save_btn.setEnabled(ready)
        self.preset_combo.setPlaceholderText("No presets yet" if ready else "")

    def _save_preset(self):
        if not self._preset_ready():
            return
        existing = store.list_presets(self._store_id, self._model_key)
        dlg = _PresetNameDialog(self.window(), existing, self.preset_combo.currentText())
        if dlg.exec() != QDialog.Accepted:
            return
        name = dlg.name()
        if not name:
            return
        match = next((n for n in existing if n.lower() == name.lower()), None)
        if match is not None:
            if not _confirm(self.window(), "Replace preset", f"Replace \"{match}\"?",
                            "A preset with this name already exists for this model. "
                            "Its saved part selection will be overwritten.", "Replace"):
                return
            name = match
        visible = self._checked()
        hidden = [g.name for g in self._model.groups if g.name not in visible]
        if store.set_preset(self._store_id, self._model_key, name, sorted(visible), hidden):
            self._refresh_presets(select=name)
            self.status.setText(self.status.text() + f"  ·  preset \"{name}\" saved")
        else:
            self.status.setText("Could not save the preset (see the console for details).")

    def _load_preset(self):
        if not self._preset_ready():
            return
        name = self.preset_combo.currentText()
        preset = store.get_preset(self._store_id, self._model_key, name) if name else None
        if preset is None:
            return
        saved_visible, saved_hidden = preset
        auto = _auto_names(self._model)
        visible = set()
        for g in self._model.groups:
            if g.name in saved_visible:
                visible.add(g.name)
            elif g.name not in saved_hidden and g.name in auto:
                visible.add(g.name)
        self._fill_list(self._model, visible)
        self.viewport3d.set_visible_groups(visible, refit=True)
        self._update_status()
        self._set_dirty(True)
        self.status.setText(self.status.text() + f"  ·  preset \"{name}\" loaded")

    def _delete_preset(self):
        if not self._preset_ready():
            return
        name = self.preset_combo.currentText()
        if not name:
            return
        if not _confirm(self.window(), "Delete preset", f"Delete \"{name}\"?",
                        "This removes the saved part selection. It cannot be undone.",
                        "Delete", danger=True):
            return
        store.delete_preset(self._store_id, self._model_key, name)
        self._refresh_presets()


def _find_host() -> QWidget | None:
    wins = [w for w in QApplication.topLevelWidgets() if isinstance(w, QMainWindow) and w.isVisible()]
    if not wins:
        return None
    active = QApplication.activeWindow()
    return active if active in wins else wins[0]


class _OpeningPopup(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("mpv_opening")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(12)
        self.title = QLabel("Loading 3D preview…")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(font(13, "bold"))
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        lay.addWidget(self.title)
        lay.addWidget(self.bar)
        self.setFixedSize(300, 100)
        c = COLORS
        self.setStyleSheet(f"""
            QWidget#mpv_opening {{
                background:{c.get('card_bg', '#26262c')};
                border:1px solid {c.get('border', '#3a3a42')}; border-radius:10px;
            }}
            QLabel {{ color:{c.get('text', '#ffffff')}; background:transparent; }}
            QProgressBar {{ background:{c.get('app_bg', '#18181c')}; border:none; border-radius:4px; }}
            QProgressBar::chunk {{ background:{c.get('accent', '#4a9eff')}; border-radius:4px; }}
        """)

    def popup_over(self, host: QWidget | None):
        if host is not None:
            center = host.frameGeometry().center()
        else:
            screen = QApplication.primaryScreen()
            center = screen.availableGeometry().center() if screen is not None else self.rect().center()
        self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)
        self.show()


class ModelPreviewWindow(QWidget):
    closed = Signal()

    DEFAULT_SIZE = (1460, 1000)
    _GEOMETRY_OPTION = "window_geometry"

    def __init__(self, texture_loader: Callable[[str], QImage | None], parent: QWidget | None = None):
        host = parent or _find_host()
        host = host.window() if host is not None else None
        super().__init__(host, Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        self._host = host
        self._geometry_restored = False
        self.setObjectName("modelPreviewWindow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.resize(*self.DEFAULT_SIZE)
        if host is not None:
            host.installEventFilter(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("3D Preview")
        self._title.setFont(font(14, "bold"))
        header.addWidget(self._title)
        header.addStretch(1)
        self.close_btn = QPushButton("✕  Close")
        self.close_btn.setObjectName("mpv_close")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFixedHeight(32)
        self.close_btn.setMinimumWidth(100)
        self.close_btn.setToolTip("Close the 3D preview  (Esc)")
        self.close_btn.clicked.connect(self.close_preview)
        header.addWidget(self.close_btn)
        lay.addLayout(header)

        self.panel = ModelPreviewPanel(texture_loader)
        lay.addWidget(self.panel, 1)

        self._awaiting = False
        self._popup: _OpeningPopup | None = None
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.timeout.connect(self._reveal)
        self.panel.ready.connect(self._reveal)

        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.setContext(Qt.WidgetWithChildrenShortcut)
        esc.activated.connect(self.close_preview)

        c = COLORS
        self.setStyleSheet(f"""
            QWidget#modelPreviewWindow {{ background:{c.get('app_bg', '#18181c')}; }}
            QLabel {{ color:{c.get('text', '#ffffff')}; background:transparent; }}
            QPushButton#mpv_close {{
                background:{c.get('card_bg', '#26262c')}; color:{c.get('text', '#ffffff')};
                border:1px solid {c.get('border', '#3a3a42')}; border-radius:8px; padding:0 14px;
                font-weight:bold;
            }}
            QPushButton#mpv_close:hover {{
                background:{c.get('error', '#e74c3c')}; color:#ffffff; border-color:{c.get('error', '#e74c3c')};
            }}
        """)
        self.setWindowTitle("3D Preview")

    def show(self):
        if not self.isVisible():
            self._begin_open()
        super().show()

    def _begin_open(self):
        self._awaiting = True
        self.setWindowOpacity(0.0)
        self._set_click_through(True)
        if self._popup is None:
            self._popup = _OpeningPopup(self._host)
        self._popup.popup_over(self._host)
        self._reveal_timer.start(20000)

    def _set_click_through(self, on: bool):
        try:
            self.winId()
            handle = self.windowHandle()
            if handle is not None:
                handle.setFlag(Qt.WindowTransparentForInput, on)
        except Exception as e:
            print(f"[WARNING] model preview: click-through flag failed: {type(e).__name__}: {e}")

    def _reveal(self):
        if not self._awaiting:
            return
        self._awaiting = False
        self._reveal_timer.stop()
        if self._popup is not None:
            self._popup.hide()
        self._set_click_through(False)
        self.setWindowOpacity(1.0)
        self.raise_()
        self.activateWindow()

    def _cancel_open(self):
        if self._awaiting:
            self._awaiting = False
            self._reveal_timer.stop()
            self._set_click_through(False)
            self.setWindowOpacity(1.0)
        if self._popup is not None:
            self._popup.hide()

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        self._title.setText(title)

    def _restore_geometry(self):
        self._geometry_restored = True
        restored = False
        try:
            from PySide6.QtCore import QByteArray
            hexdata = store.get_option(self._GEOMETRY_OPTION, "")
            if isinstance(hexdata, str) and hexdata:
                restored = bool(self.restoreGeometry(QByteArray.fromHex(hexdata.encode("ascii"))))
        except Exception as e:
            print(f"[WARNING] model preview: could not restore window geometry: {type(e).__name__}: {e}")
        if not restored and self._host is not None:
            size = self._host.size()
            screen = self._host.screen() or QApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                size = size.boundedTo(avail.size() - QSize(40, 80))
            self.resize(size)
            top_left = self._host.frameGeometry().topLeft()
            x, y = top_left.x() + 60, top_left.y() + 60
            if screen is not None:
                avail = screen.availableGeometry()
                x = max(avail.left(), min(x, avail.right() - size.width() - 20))
                y = max(avail.top(), min(y, avail.bottom() - size.height() - 40))
            self.move(x, y)

    def _store_geometry(self):
        try:
            store.set_option(self._GEOMETRY_OPTION, bytes(self.saveGeometry().toHex()).decode("ascii"))
        except Exception as e:
            print(f"[WARNING] model preview: could not save window geometry: {type(e).__name__}: {e}")

    def close_preview(self):
        self._cancel_open()
        self._store_geometry()
        self.hide()
        self.closed.emit()

    def closeEvent(self, event):
        event.ignore()
        self.close_preview()

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() == QEvent.Close and self.isVisible():
            self.close_preview()
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        if not self._geometry_restored:
            self._restore_geometry()
        self.raise_()
        self.setFocus()
        super().showEvent(event)
