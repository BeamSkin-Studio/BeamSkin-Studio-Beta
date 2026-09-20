from __future__ import annotations
import os
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore   import Qt, Signal, QRectF
from PySide6.QtGui    import QPixmap, QFontMetrics, QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLineEdit, QButtonGroup, QRadioButton,
    QFileDialog, QGraphicsOpacityEffect, QSizePolicy,
)

from gui.theme   import COLORS, font, fade_in
from gui.widgets import (AnimButton, VehicleCard, HSeparator,
                          LabelledEntry, ToggleSwitch)
from gui.state   import state

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return key

try:
    from core.settings import get_vehicles_dir, get_vehicle_previews_dir, get_bundle_path
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def get_vehicles_dir():
        return os.path.join(os.path.expanduser('~'), 'BeamSkinStudio', 'vehicles')
    def get_vehicle_previews_dir():
        return os.path.join('gui', 'images', 'vehicles')
    def get_bundle_path():
        return os.getcwd()


def _get_vehicle_variants(carid: str) -> List[Tuple[str, str]]:
    try:
        from core.config import is_rebadge_suffix
    except ImportError as _exc:
        print(f"[WARNING] _get_vehicle_variants: {type(_exc).__name__}: {_exc}")
        def is_rebadge_suffix(_c, _s):
            return False

    bundled_dir = os.path.join(get_bundle_path(), "vehicles", carid)
    local_dir   = os.path.join(get_vehicles_dir(), carid)
    vehicles_dir = bundled_dir if os.path.isdir(bundled_dir) else local_dir
    if not os.path.isdir(vehicles_dir):
        return [("", "Normal")]

    variants: List[Tuple[str, str]] = []
    for entry in os.listdir(vehicles_dir):
        full = os.path.join(vehicles_dir, entry)
        if not os.path.isdir(full):
            continue
        dl = entry.lower()
        if dl == "skinname":
            variants.append(("", "Normal"))
        elif dl.startswith("skinname"):
            suffix = dl[len("skinname"):]
            if is_rebadge_suffix(carid, suffix):
                continue
            variants.append((suffix, suffix.capitalize()))

    if not variants:
        return [("", "Normal")]

    variants.sort(key=lambda x: (x[0] != "", x[1].lower()))
    return variants


class VehicleVariantExpander(QFrame):
    variant_add_requested = Signal(str, str, str)

    def __init__(
        self,
        carid:        str,
        display_name: str,
        variants:     List[Tuple[str, str]],
        parent:       QWidget | None = None,
        is_custom:    bool = False,
    ):
        super().__init__(parent)
        self.carid        = carid
        self.display_name = display_name
        self.variants     = variants
        self._expanded    = False
        self._added:      set = set()
        self._buttons:    Dict[str, QPushButton] = {}

        self.setStyleSheet("background:transparent;border:none;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        self._header = QFrame()
        self._header.setFixedHeight(38)
        self._header.setCursor(Qt.PointingHandCursor)
        self._apply_header_style(False)
        hrow = QHBoxLayout(self._header)
        hrow.setContentsMargins(10, 0, 10, 0)
        hrow.setSpacing(8)

        self._arrow = QLabel("▶")
        self._arrow.setFont(font(10))
        self._arrow.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        hrow.addWidget(self._arrow)

        name_lbl = QLabel(display_name)
        name_lbl.setFont(font(13, "bold"))
        name_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        hrow.addWidget(name_lbl, 1)

        if is_custom:
            mod_badge = QLabel("mod")
            mod_badge.setFont(font(8))
            mod_badge.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS['text_secondary']};
                    background: transparent;
                    border: none;
                    padding: 0px 2px;
                }}
            """)
            hrow.addWidget(mod_badge)

        badge = QLabel(f"{len(variants)} variants")
        badge.setFont(font(8))
        badge.setStyleSheet(f"""
            color:{COLORS['text_secondary']};
            background:transparent;
            border:none;
            padding:0px 2px;
        """)
        hrow.addWidget(badge)

        self._header.mousePressEvent = lambda _e: self._toggle()
        outer.addWidget(self._header)

        self._panel = QFrame()
        self._panel.setVisible(False)
        self._panel.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['frame_bg']};
                border-radius:8px;
                border:1px solid {COLORS['border']};
            }}
        """)
        panel_col = QVBoxLayout(self._panel)
        panel_col.setContentsMargins(8, 8, 8, 8)
        panel_col.setSpacing(4)

        hint = QLabel("Select body variant to add:")
        hint.setFont(font(10))
        hint.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        panel_col.addWidget(hint)

        for suffix, label in variants:
            btn = QPushButton(label)
            btn.setFont(font(12, "bold"))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._pill_style())
            btn.clicked.connect(
                lambda checked=False, s=suffix, lb=label: self._on_pill(s, lb)
            )
            panel_col.addWidget(btn)
            self._buttons[suffix] = btn

        outer.addWidget(self._panel)


    def _apply_header_style(self, hover: bool):
        self._header.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['frame_bg']};
                border-radius:8px;
                border:1px solid {COLORS['border']};
            }}
            QFrame:hover {{
                border-color:{COLORS['accent']};
                background:{COLORS['card_hover']};
            }}
        """)

    def _pill_style(self) -> str:
        return f"""
            QPushButton {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:6px;
                padding:4px 12px;
            }}
            QPushButton:hover {{
                background:{COLORS['accent']};
                color:{COLORS['accent_text']};
                border-color:{COLORS['accent']};
            }}
        """


    def _toggle(self):
        print(f"[DEBUG] VehicleVariantExpander._toggle: expanded={not self._expanded}")
        self._expanded = not self._expanded
        self._arrow.setText("▼" if self._expanded else "▶")
        self._panel.setVisible(self._expanded)

    def _on_pill(self, suffix: str, label: str):
        vname = (f"{self.display_name} ({label})"
                 if suffix else self.display_name)
        self.variant_add_requested.emit(self.carid, vname, suffix)

    def mark_variant_added(self, suffix: str):
        self._added.add(suffix)
        if suffix in self._buttons:
            self._buttons[suffix].setVisible(False)
        if {s for s, _ in self.variants}.issubset(self._added):
            self.setVisible(False)


class NavPill(QPushButton):
    def __init__(
        self,
        text: str,
        view_name: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self.view_name = view_name
        self._active   = False
        self.setFont(font(13))
        self.setMinimumHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._lock_width(text)
        self._apply(False)

    def _lock_width(self, text: str):
        metrics = QFontMetrics(font(13, "bold"))
        text_width = metrics.horizontalAdvance(text)
        self.setFixedWidth(max(text_width + 24, 80))

    def _apply(self, active: bool):
        self._active = active
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['accent']};
                    color: {COLORS['accent_text']};
                    border-radius: 8px;
                    border: none;
                    padding: 6px 16px;
                    font-size: 13px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['accent_hover']};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['card_hover']};
                    color: {COLORS['text']};
                    border-radius: 8px;
                    border: none;
                    padding: 6px 16px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['card_bg']};
                    color: {COLORS['text']};
                }}
            """)

    def set_active(self, active: bool):
        if self._active != active:
            self._apply(active)


class Topbar(QFrame):
    view_changed     = Signal(str)
    generate_clicked = Signal()

    def __init__(
        self,
        parent: QWidget,
        logo_pixmap: Optional[QPixmap] = None,
    ):
        super().__init__(parent)
        self.logo_pixmap  = logo_pixmap
        self.menu_buttons: Dict[str, NavPill] = {}
        self._active_view = "generator"

        self.setFixedHeight(60)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['topbar_bg']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)

        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(0)

        logo_px = self.logo_pixmap or self._load_logo_pixmap()
        if logo_px:
            logo = QLabel()
            logo.setFixedSize(80, 40)
            scaled = logo_px.scaled(80, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(scaled)
            logo.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            logo.setStyleSheet("background:transparent;border:none;")
            layout.addWidget(logo)
            layout.addSpacing(12)
        else:
            brand = QLabel("BeamSkin Studio")
            brand.setFont(font(18, "bold"))
            brand.setStyleSheet(
                f"color:{COLORS['accent']};background:transparent;border:none;"
            )
            layout.addWidget(brand)
            layout.addSpacing(8)

        items = [
            (t("menu.generator"),    "generator"),
            (t("menu.HowToTab"),     "howto"),
            (t("menu.carlist"),      "carlist"),
            (t("menu.add_vehicles"), "add_vehicles"),
            (t("menu.settings"),     "settings"),
            (t("menu.about"),        "about"),
            (t("menu.online"),       "online_tab"),
        ]
        for label, name in items:
            btn = NavPill(label, name, self)
            btn.clicked.connect(lambda checked=False, n=name: self.view_changed.emit(n))
            self.menu_buttons[name] = btn
            layout.addWidget(btn)
            if name != items[-1][1]:
                layout.addSpacing(8)

        layout.addStretch()

        self.generate_button = AnimButton(
            t("project.generate_mod", default="Generate Mod"),
            icon_text="✨",
            fg=COLORS["accent"],
            fg_hover=COLORS["accent_hover"],
            font_size=13,
            bold=True,
            padding="8px 20px",
        )
        self.generate_button.setFixedHeight(40)
        self.generate_button.clicked.connect(self.generate_clicked)
        layout.addWidget(self.generate_button)

        self.set_active("generator")

    def _load_logo_pixmap(self) -> Optional[QPixmap]:
        icon_dir = os.path.join(get_bundle_path(), "gui", "Icons")
        suffix   = "White" if state.theme_mode == "dark" else "Black"
        path     = os.path.join(icon_dir, f"BeamSkin_Studio_{suffix}.png")
        if os.path.exists(path):
            return QPixmap(path).scaled(80, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return None

    def set_active(self, view_name: str):
        self._active_view = view_name
        for name, btn in self.menu_buttons.items():
            btn.set_active(name == view_name)
        self.generate_button.setVisible(view_name == "generator")

    def refresh_ui(self, logo_pixmap: Optional[QPixmap] = None):
        if logo_pixmap:
            self.logo_pixmap = logo_pixmap
        else:
            reloaded = self._load_logo_pixmap()
            if reloaded:
                self.logo_pixmap = reloaded

        saved_view = self._active_view

        old = self.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
            _tmp = QWidget()
            _tmp.setAttribute(Qt.WA_DontShowOnScreen, True)
            _tmp.setLayout(old)
            _tmp.deleteLater()

        self.menu_buttons.clear()
        self._build()
        self.set_active(saved_view)


class Sidebar(QFrame):
    add_vehicle_requested = Signal(str, str, str)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setMaximumWidth(460)
        self.setObjectName("SidebarFrame")
        self.setStyleSheet(f"""
            #SidebarFrame {{
                background-color: {COLORS['sidebar_bg']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)

        self._populate_callback: Optional[Callable] = None
        self._vehicle_cards: List[VehicleCard] = []
        self._variant_expanders: Dict[str, VehicleVariantExpander] = {}

        self._mod_name_text = ""
        self._author_text   = ""
        self.output_mode    = "steam"
        self.custom_output  = ""
        self.unpacked       = False

        self._locked = False

        self._build()
        self._apply_content_width()

    def _apply_content_width(self) -> None:
        labels = [
            t("project.mod_name", default="Mod Name"),
            t("project.author_name", default="Author"),
            t("project.steam_path", default="Save to Steam Mods"),
            t("project.custom_location", default="Custom Location"),
            t("project.output_location", default="Output Location"),
            t("project.add_vehicle", default="ADD VEHICLES"),
            t("common.browse", default="Browse"),
        ]
        metrics = QFontMetrics(font(13, "bold"))
        longest = max(
            (metrics.horizontalAdvance(label) for label in labels),
            default=0,
        )

        vehicle_names = list(state.vehicle_ids.values()) + list(state.added_vehicles.values())
        if vehicle_names:
            vehicle_widths = sorted(
                metrics.horizontalAdvance(name) for name in vehicle_names
            )
            idx = min(len(vehicle_widths) - 1, int(len(vehicle_widths) * 0.9))
            longest = max(longest, vehicle_widths[idx])

        desired = max(300, min(360, longest + 80))
        self.setFixedWidth(desired)


    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(14, 14, 14, 14)
        inner_layout.setSpacing(8)

        details_panel = QFrame()
        details_panel.setObjectName("projectDetailsPanel")
        details_panel.setStyleSheet(f"""
            QFrame#projectDetailsPanel {{
                background: {COLORS['card_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(8, 8, 8, 8)
        details_layout.setSpacing(6)
        details_layout.addWidget(self._section_header(
            t("project.details", default="PROJECT DETAILS"), contained=True
        ))

        self._mod_entry = LabelledEntry(
            t("project.mod_name", default="Mod Name"),
            t("project.mod_name_placeholder", default="MySkinPack"),
        )
        self._mod_entry.set_text(self._mod_name_text)
        details_layout.addWidget(self._mod_entry)

        self._author_entry = LabelledEntry(
            t("project.author_name", default="Author"),
            t("project.author_name_placeholder", default="Your name"),
        )
        self._author_entry.set_text(self._author_text)
        details_layout.addWidget(self._author_entry)

        inner_layout.addWidget(details_panel)

        inner_layout.addWidget(self._section_divider())
        output_panel = QFrame()
        output_panel.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['card_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(8, 8, 8, 8)
        output_layout.setSpacing(6)
        output_layout.addWidget(self._section_header(
            t("project.output_mode", default="OUTPUT"), contained=True
        ))

        unpacked_frame = QFrame()
        unpacked_frame.setFixedHeight(44)
        unpacked_frame.setStyleSheet("background:transparent;border:none;")
        uf_row = QHBoxLayout(unpacked_frame)
        uf_row.setContentsMargins(10, 0, 10, 0)
        uf_row.setSpacing(8)

        format_track = QFrame()
        format_track.setObjectName("formatTrack")
        format_track.setStyleSheet(f"""
            QFrame#formatTrack {{
                background: {COLORS['frame_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        format_row = QHBoxLayout(format_track)
        format_row.setContentsMargins(0, 0, 0, 0)
        format_row.setSpacing(0)

        segment_style = f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: 1px solid transparent;
                border-radius: 7px;
                padding: 5px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background: {COLORS['card_hover']};
            }}
            QPushButton:checked {{
                background: {COLORS['accent']};
                color: {COLORS['accent_text']};
                border-color: {COLORS['accent_hover']};
            }}
        """
        zip_button = QPushButton(t("project.zip_output", default="ZIP"))
        zip_button.setCheckable(True)
        zip_button.setMinimumHeight(30)
        zip_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        zip_button.setStyleSheet(segment_style)

        unpacked_button = QPushButton(
            t("project.unpacked_output", default="Unpacked")
        )
        unpacked_button.setCheckable(True)
        unpacked_button.setMinimumHeight(30)
        unpacked_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        unpacked_button.setStyleSheet(segment_style)

        self._output_format_group = QButtonGroup(self)
        self._output_format_group.setExclusive(True)
        self._output_format_group.addButton(zip_button, 0)
        self._output_format_group.addButton(unpacked_button, 1)
        zip_button.setChecked(not self.unpacked)
        unpacked_button.setChecked(self.unpacked)
        zip_button.toggled.connect(
            lambda checked: self._on_generate_format_toggled(checked, False)
        )
        unpacked_button.toggled.connect(
            lambda checked: self._on_generate_format_toggled(checked, True)
        )
        self._unpacked_toggle = unpacked_button
        format_row.addWidget(zip_button, 1)
        format_row.addWidget(unpacked_button, 1)
        uf_row.addWidget(format_track, 1)
        output_layout.addWidget(unpacked_frame)

        output_layout.addSpacing(16)
        output_location_header = QFrame()
        output_location_header.setFixedHeight(22)
        output_location_header.setStyleSheet(
            "background:transparent;border:none;"
        )
        location_header_row = QHBoxLayout(output_location_header)
        location_header_row.setContentsMargins(2, 0, 0, 0)
        location_header_row.setSpacing(6)

        location_marker = QFrame()
        location_marker.setFixedSize(3, 14)
        location_marker.setStyleSheet(
            f"background:{COLORS['accent']};border:none;border-radius:1px;"
        )
        location_header_row.addWidget(location_marker)

        self._output_location_lbl = QLabel(
            t("project.output_location", default="Output Location").upper()
        )
        self._output_location_lbl.setFont(font(10, "bold"))
        self._output_location_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        location_header_row.addWidget(self._output_location_lbl)
        location_header_row.addStretch()
        output_layout.addWidget(output_location_header)

        steam_frame = QFrame()
        steam_frame.setFixedHeight(44)
        steam_frame.setStyleSheet("background:transparent;border:none;")
        sf_row = QHBoxLayout(steam_frame)
        sf_row.setContentsMargins(10, 0, 10, 0)
        self._steam_radio = RingRadioButton(
            t("project.steam_path", default="Save to Steam Mods")
        )
        self._steam_radio.setFont(font(13, "bold"))
        self._steam_radio.setStyleSheet(_radio_qss())
        self._steam_radio.setChecked(self.output_mode == "steam")
        sf_row.addWidget(self._steam_radio)
        output_layout.addWidget(steam_frame)

        custom_frame = QFrame()
        custom_frame.setFixedHeight(44)
        custom_frame.setStyleSheet("background:transparent;border:none;")
        cf_row = QHBoxLayout(custom_frame)
        cf_row.setContentsMargins(10, 0, 10, 0)
        self._custom_radio = RingRadioButton(
            t("project.custom_location", default="Custom Location")
        )
        self._custom_radio.setFont(font(13, "bold"))
        self._custom_radio.setStyleSheet(_radio_qss())
        self._custom_radio.setChecked(self.output_mode == "custom")
        cf_row.addWidget(self._custom_radio)

        browse_btn = QPushButton(t('common.browse', default='Browse'))
        browse_btn.setFont(font(11, "bold"))
        browse_btn.setFixedHeight(32)
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background: {COLORS['card_hover']};
                border-color: {COLORS['accent']};
            }}
        """)
        browse_btn.clicked.connect(self._browse_custom_output)
        cf_row.addStretch()
        cf_row.addWidget(browse_btn)
        output_layout.addWidget(custom_frame)

        self._custom_path_frame = QFrame()
        self._custom_path_frame.setStyleSheet("background:transparent;border:none;")
        cp_row = QHBoxLayout(self._custom_path_frame)
        cp_row.setContentsMargins(0, 0, 0, 0)
        cp_row.setSpacing(6)

        self._custom_entry = QLineEdit()
        self._custom_entry.setReadOnly(True)
        self._custom_entry.setPlaceholderText(
            t("project.select_output", default="Select output folder…")
        )
        self._custom_entry.setText(self.custom_output)
        self._custom_entry.setMinimumHeight(32)
        self._custom_entry.setFont(font(11))
        self._custom_entry.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:6px;
                padding:4px 8px;
                font-size:11px;
            }}
        """)
        cp_row.addWidget(self._custom_entry, 1)

        output_layout.addWidget(self._custom_path_frame)

        self._output_group = QButtonGroup(self)
        self._output_group.addButton(self._steam_radio)
        self._output_group.addButton(self._custom_radio)

        self._steam_radio.toggled.connect(self._on_output_mode_changed)
        self._custom_radio.toggled.connect(self._on_output_mode_changed)
        self._update_custom_path_visibility()

        inner_layout.addWidget(output_panel)
        inner_layout.addWidget(self._section_divider())

        vehicles_panel = QFrame()
        vehicles_panel.setObjectName("vehiclesPanel")
        vehicles_panel.setStyleSheet(f"""
            QFrame#vehiclesPanel {{
                background: {COLORS['card_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        vehicles_layout = QVBoxLayout(vehicles_panel)
        vehicles_layout.setContentsMargins(8, 8, 8, 8)
        vehicles_layout.setSpacing(6)
        vehicles_layout.addWidget(self._section_header(
            t("project.add_vehicle", default="ADD VEHICLES"), contained=True
        ))

        self._add_all_btn = QPushButton("⚡  Add All Vehicles & Variants")
        self._add_all_btn.setFont(font(12, "bold"))
        self._add_all_btn.setFixedHeight(36)
        self._add_all_btn.setCursor(Qt.PointingHandCursor)
        self._add_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS.get('warning', '#e67e22')};
                color: white;
                border-radius: 8px;
                border: none;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: {COLORS.get('warning_hover', '#d35400')};
            }}
        """)
        self._add_all_btn.clicked.connect(self._add_all_vehicles)
        self._add_all_btn.setVisible(state.testing_mode)
        vehicles_layout.addWidget(self._add_all_btn)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            t("common.search_vehicle", default="Search vehicles…")
        )
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumHeight(34)
        self._search.setFont(font(12))
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:5px 10px;
                font-size:12px;
            }}
            QLineEdit:focus {{ border-color:{COLORS['border_focus']}; }}
        """)
        self._search.textChanged.connect(self._filter_vehicles)
        vehicles_layout.addWidget(self._search)

        vehicle_scroll = QScrollArea()
        vehicle_scroll.setWidgetResizable(True)
        vehicle_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        vehicle_scroll.setStyleSheet("""
            QScrollArea{background:transparent;border:none;}
            QScrollArea>QWidget>QWidget{background:transparent;}
        """)

        vehicle_container = QWidget()
        vehicle_container.setStyleSheet("background:transparent;")
        self._vehicle_list = QVBoxLayout(vehicle_container)
        self._vehicle_list.setSpacing(4)
        self._vehicle_list.setContentsMargins(0, 0, 4, 0)
        self._vehicle_list.setAlignment(Qt.AlignTop)
        vehicle_scroll.setWidget(vehicle_container)
        vehicle_scroll.setMinimumHeight(120)
        vehicles_layout.addWidget(vehicle_scroll, 1)

        inner_layout.addWidget(vehicles_panel, 1)

        root.addWidget(inner)

        self._inner = inner
        self.set_locked(self._locked)

    def _section_header(self, text: str, contained: bool = False) -> QFrame:
        header = QFrame()
        header.setFixedHeight(30)
        if contained:
            header.setStyleSheet("background:transparent;border:none;")
        else:
            header.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['card_bg']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 7px;
                }}
            """)
        row = QHBoxLayout(header)
        row.setContentsMargins(6, 0, 10, 0)
        row.setSpacing(6)

        marker = QFrame()
        marker.setFixedSize(3, 14)
        marker.setStyleSheet(
            f"background:{COLORS['accent']};border:none;border-radius:1px;"
        )
        row.addWidget(marker)

        label = QLabel(text.upper())
        label.setFont(font(10, "bold"))
        label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        row.addWidget(label)
        row.addStretch()
        return header

    def _section_divider(self) -> QFrame:
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"background:{COLORS['border']};border:none;"
        )
        return divider


    def populate_vehicles(self, add_callback: Callable[[str, str, str], None]):
        self._populate_callback = add_callback
        state.sidebar_vehicle_buttons.clear()
        self._clear_vehicle_list()

        try:
            from core.config import get_rebadges_for
        except ImportError as _exc:
            print(f"[WARNING] populate_vehicles: {type(_exc).__name__}: {_exc}")
            def get_rebadges_for(_c):
                return {}

        gen = self._get_generator()
        project_keys = set(gen.project_data["cars"].keys()) if gen else set()

        all_vehicles = {**state.vehicle_ids, **state.added_vehicles}
        for cid, name in sorted(all_vehicles.items(), key=lambda x: x[1].lower()):
            if self._is_fully_in_project(cid, project_keys):
                continue
            variants = _get_vehicle_variants(cid)
            if len(variants) > 1:
                self._add_variant_expander(cid, name, variants, add_callback)
            else:
                self._add_vehicle_card(cid, name, add_callback)

            for suffix, rebadge_name in get_rebadges_for(cid).items():
                from gui.tabs.generator import _make_project_key
                if _make_project_key(cid, suffix) in project_keys:
                    continue
                self._add_vehicle_card(cid, rebadge_name, add_callback,
                                       variant_suffix=suffix)

    def _get_generator(self):
        print("[DEBUG] populate_vehicles: rebuilding sidebar vehicle list")
        mw = self.window()
        if mw and hasattr(mw, "tabs"):
            return mw.tabs.get("generator")
        return None

    def _is_fully_in_project(self, carid: str, project_keys: set) -> bool:
        variants = _get_vehicle_variants(carid)
        for suffix, _ in variants:
            from gui.tabs.generator import _make_project_key
            if _make_project_key(carid, suffix) not in project_keys:
                return False
        return True

    def restore_vehicle(self, carid: str, variant_suffix: str = ""):
        if self._populate_callback is None:
            return

        try:
            from core.config import is_rebadge_suffix, get_rebadges_for
        except ImportError as _exc:
            print(f"[WARNING] restore_vehicle: {type(_exc).__name__}: {_exc}")
            def is_rebadge_suffix(_c, _s):
                return False
            def get_rebadges_for(_c):
                return {}

        if variant_suffix and is_rebadge_suffix(carid, variant_suffix):
            rebadge_name = get_rebadges_for(carid).get(variant_suffix, carid)
            already_present = any(
                cid == carid and vs == variant_suffix
                for _card, cid, _name, vs in state.sidebar_vehicle_buttons
            )
            if not already_present:
                self._add_vehicle_card(carid, rebadge_name, self._populate_callback,
                                       variant_suffix=variant_suffix)
            return

        name = state.vehicle_ids.get(carid) or state.added_vehicles.get(carid, carid)
        variants = _get_vehicle_variants(carid)

        if len(variants) > 1:
            if carid in self._variant_expanders:
                exp = self._variant_expanders[carid]
                exp.setVisible(True)
                if variant_suffix in exp._buttons:
                    btn = exp._buttons[variant_suffix]
                    btn.setEnabled(True)
                    btn.setVisible(True)
                    btn.setStyleSheet(exp._pill_style())
                    exp._added.discard(variant_suffix)
            else:
                self._add_variant_expander(carid, name, variants, self._populate_callback)
        else:
            already_present = any(
                cid == carid and vs == variant_suffix
                for _card, cid, _name, vs in state.sidebar_vehicle_buttons
            )
            if not already_present:
                self._add_vehicle_card(carid, name, self._populate_callback)

    def _insert_sorted(self, widget: QWidget, display_name: str):
        target = display_name.lower()
        count  = self._vehicle_list.count()
        insert_at = count
        for i in range(count):
            item = self._vehicle_list.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w is None:
                continue
            if hasattr(w, "display_name"):
                existing = w.display_name.lower()
            elif isinstance(w, VehicleVariantExpander):
                existing = w.display_name.lower()
            else:
                continue
            if target < existing:
                insert_at = i
                break
        self._vehicle_list.insertWidget(insert_at, widget)

    def _add_variant_expander(
        self,
        carid:    str,
        name:     str,
        variants: List[Tuple[str, str]],
        callback: Callable,
    ):
        is_custom = carid in state.added_vehicles
        expander = VehicleVariantExpander(carid, name, variants, parent=self,
                                          is_custom=is_custom)
        expander.variant_add_requested.connect(
            lambda c, d, v: self._on_add_vehicle(c, d, v, callback)
        )
        self._variant_expanders[carid] = expander
        self._insert_sorted(expander, name)
        fade_in(expander, 180)
        self._attach_hover_preview(expander._header, carid, "")
        for suffix, label in variants:
            if suffix in expander._buttons:
                self._attach_hover_preview(
                    expander._buttons[suffix], carid, suffix,
                    display_name=f"{name} {label}" if suffix else name,
                )

    def _add_vehicle_card(self, carid: str, name: str, callback: Callable,
                          variant_suffix: str = ""):
        is_custom = carid in state.added_vehicles
        card = VehicleCard(carid, name, parent=self, is_custom=is_custom)
        card.add_requested.connect(
            lambda c, d: self._on_add_vehicle(c, d, variant_suffix, callback)
        )
        self._vehicle_cards.append(card)
        state.sidebar_vehicle_buttons.append((card, carid, name, variant_suffix))
        self._insert_sorted(card, name)
        fade_in(card, 180)
        self._attach_hover_preview(card, carid, variant_suffix, display_name=name)

    def _attach_hover_preview(
        self, widget: QWidget, carid: str, variant_suffix: str = "",
        display_name: Optional[str] = None,
    ) -> None:
        mw = self.window()
        if mw is None or not hasattr(mw, "preview_manager"):
            return
        img_name = f"{variant_suffix}.jpg" if variant_suffix else "default.jpg"

        candidates = [
            os.path.join(get_vehicle_previews_dir(), carid, img_name),
            os.path.join(get_bundle_path(), "gui", "images", "vehicles", carid, img_name),
        ]
        if variant_suffix:
            candidates += [
                os.path.join(get_vehicle_previews_dir(), carid, "default.jpg"),
                os.path.join(get_bundle_path(), "gui", "images", "vehicles", carid, "default.jpg"),
            ]

        img_path = next((p for p in candidates if os.path.exists(p)), candidates[0])

        mw.preview_manager.setup_robust_hover(
            widget, carid,
            get_image_path=lambda p=img_path: p,
            get_display_name=(lambda n=display_name: n) if display_name else None,
            variant_suffix=variant_suffix,
        )

    def _on_add_vehicle(self, carid: str, name: str, variant: str, callback: Callable):
        callback(carid, name, variant)

        if carid in self._variant_expanders:
            self._variant_expanders[carid].mark_variant_added(variant)
        else:
            target_cards = [
                card for card, cid, _name, vs in state.sidebar_vehicle_buttons
                if cid == carid and vs == variant
            ]
            for card in target_cards:
                if card in self._vehicle_cards:
                    self._vehicle_list.removeWidget(card)
                    card.deleteLater()
                    self._vehicle_cards.remove(card)

        state.sidebar_vehicle_buttons = [
            item for item in state.sidebar_vehicle_buttons
            if not (item[1] == carid and item[3] == variant)
        ]

    def _clear_vehicle_list(self):
        for card in list(self._vehicle_cards):
            card.deleteLater()
        self._vehicle_cards.clear()
        for exp in list(self._variant_expanders.values()):
            exp.deleteLater()
        self._variant_expanders.clear()
        while self._vehicle_list.count():
            item = self._vehicle_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _filter_vehicles(self, text: str):
        print(f"[DEBUG] _filter_vehicles: query={text!r}")
        term = text.lower()
        for card in self._vehicle_cards:
            card.setVisible(
                term in card.display_name.lower() or term in card.carid.lower()
            )
        for carid, exp in self._variant_expanders.items():
            exp.setVisible(
                term in exp.display_name.lower() or term in carid.lower()
            )


    def _add_all_vehicles(self):
        print("[DEBUG] _add_all_vehicles: testing mode bulk-add triggered")
        if self._populate_callback is None:
            return

        all_vehicles = {**state.vehicle_ids, **state.added_vehicles}
        added_count = 0
        for cid, name in sorted(all_vehicles.items(), key=lambda x: x[1].lower()):
            variants = _get_vehicle_variants(cid)
            for suffix, label in variants:
                vname = f"{name} ({label})" if suffix else name
                self._on_add_vehicle(cid, vname, suffix, self._populate_callback)
                added_count += 1

        mw = self.window()
        if mw and hasattr(mw, "show_notification"):
            mw.show_notification(
                f"[Testing] Added {added_count} vehicle/variant entries to project.",
                type="success",
            )

    def _on_output_mode_changed(self):
        self.output_mode = "steam" if self._steam_radio.isChecked() else "custom"
        self._update_custom_path_visibility()

    def _on_generate_format_toggled(self, checked: bool, unpacked: bool):
        if checked:
            self._on_unpacked_changed(unpacked)

    def _on_unpacked_changed(self, state_val: int):
        self.unpacked = bool(state_val) if isinstance(state_val, bool) else state_val == 2

    def _update_custom_path_visibility(self):
        self._custom_path_frame.setVisible(self.output_mode == "custom")

    def _browse_custom_output(self):
        print("[DEBUG] _browse_custom_output: opening output folder dialog")
        self._custom_radio.setChecked(True)
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.custom_output = path
            self._custom_entry.setText(path)


    def get_mod_name(self) -> str:
        return self._mod_entry.text()

    def get_author(self) -> str:
        return self._author_entry.text()

    def get_output_mode(self) -> str:
        return self.output_mode

    def get_custom_output(self) -> str:
        return self._custom_entry.text()

    def get_unpacked(self) -> bool:
        return self.unpacked

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        if not hasattr(self, "_inner"):
            return

        self._inner.setEnabled(not locked)
        if locked:
            effect = QGraphicsOpacityEffect(self._inner)
            effect.setOpacity(0.5)
            self._inner.setGraphicsEffect(effect)
        else:
            self._inner.setGraphicsEffect(None)


    def refresh_ui(self, populate_callback: Optional[Callable] = None):
        if populate_callback:
            self._populate_callback = populate_callback
        try:
            self._mod_name_text = self.get_mod_name()
            self._author_text   = self.get_author()
        except Exception as _exc:
            print(f"[WARNING] refresh_ui: {type(_exc).__name__}: {_exc}")
        try:
            self.unpacked = self._unpacked_toggle.isChecked()
        except Exception as _exc:
            print(f"[WARNING] refresh_ui: {type(_exc).__name__}: {_exc}")

        old = self.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
            _tmp = QWidget()
            _tmp.setAttribute(Qt.WA_DontShowOnScreen, True)
            _tmp.setLayout(old)
            _tmp.deleteLater()

        self._vehicle_cards       = []
        self._variant_expanders   = {}
        self._build()
        self._apply_content_width()
        if self._populate_callback:
            self.populate_vehicles(self._populate_callback)


def _radio_qss() -> str:
    return f"""
        QRadioButton {{
            color: {COLORS['text']};
            font-size: 13px;
            font-weight: bold;
            spacing: 10px;
            background: transparent;
        }}
        QRadioButton::indicator {{
            width: 20px;
            height: 20px;
            background: transparent;
            border: none;
            image: none;
        }}
    """


class RingRadioButton(QRadioButton):

    _SIZE      = 20
    _RING_W    = 1.5
    _DOT_INSET = 5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hovered = False
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        cy = self.height() / 2.0
        d  = float(self._SIZE)
        rw = self._RING_W
        ring_rect = QRectF(rw / 2.0, cy - d / 2.0 + rw / 2.0, d - rw, d - rw)

        checked = self.isChecked()
        if checked or self._hovered:
            ring_col = QColor(COLORS["accent"])
        else:
            ring_col = QColor(COLORS["border"])

        p.setPen(QPen(ring_col, rw))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(ring_rect)

        if checked:
            i = float(self._DOT_INSET)
            dot_rect = QRectF(i, cy - d / 2.0 + i, d - 2 * i, d - 2 * i)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(COLORS["accent"])))
            p.drawEllipse(dot_rect)

        p.end()
