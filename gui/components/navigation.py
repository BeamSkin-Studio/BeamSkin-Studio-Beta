from __future__ import annotations
import os
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore   import Qt, Signal, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui    import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLineEdit, QSizePolicy, QButtonGroup,
    QRadioButton, QFileDialog, QApplication,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import (AnimButton, GhostButton, VehicleCard,
                          HSeparator, LabelledEntry, Badge, Spinner,
                          ToggleSwitch)
from gui.state   import state

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return key


# VARIANT  DETECTION  HELPER

def _get_vehicle_variants(carid: str) -> List[Tuple[str, str]]:
    """
    Scan vehicles/<carid>/ for SKINNAME* subdirectories.

    Returns a list of (variant_suffix, display_label) tuples.
      ("",          "Normal")     — the standard body (SKINNAME folder)
      ("ambulance", "Ambulance")  — SKINNAMEAMBULANCE folder
      ("box",       "Box")        — SKINNAMEBOX folder
      …

    Always returns at least [("", "Normal")].
    The list is sorted: normal first, then alphabetically by label.
    """
    vehicles_dir = os.path.join("vehicles", carid)
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
            suffix = dl[len("skinname"):]          # e.g. "ambulance", "box"
            variants.append((suffix, suffix.capitalize()))

    if not variants:
        return [("", "Normal")]

    variants.sort(key=lambda x: (x[0] != "", x[1].lower()))
    return variants


# VEHICLE  VARIANT  EXPANDER

class VehicleVariantExpander(QFrame):
    """
    Sidebar widget for vehicles with multiple body variants.

    Layout (collapsed):
      ▶  Pickup                    2 variants

    Layout (expanded):
      ▼  Pickup                    2 variants
      ┌────────────────────────┐
      │  [Normal]  [Ambulance] │
      └────────────────────────┘

    Each variant pill is clickable until that variant has been added to the
    project, at which point it grays out.  When all variants are added the
    whole widget hides itself.
    """

    variant_add_requested = Signal(str, str, str)   # carid, display_name, variant_suffix

    def __init__(
        self,
        carid:        str,
        display_name: str,
        variants:     List[Tuple[str, str]],   # [(suffix, label), …]
        parent:       QWidget | None = None,
        is_custom:    bool = False,
    ):
        super().__init__(parent)
        self.carid        = carid
        self.display_name = display_name
        self.variants     = variants
        self._expanded    = False
        self._added:      set = set()      # variant suffixes already in project
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
                    border: 1px solid {COLORS['border']};
                    border-radius: 3px;
                    padding: 0px 4px;
                }}
            """)
            hrow.addWidget(mod_badge)

        badge = QLabel(f"{len(variants)} variants")
        badge.setFont(font(8))
        badge.setStyleSheet(f"""
            color:{COLORS['text_secondary']};
            background:transparent;
            border:1px solid {COLORS['border']};
            border-radius:6px;
            padding:0px 5px;
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
                background:{COLORS['card_bg']};
                border-radius:8px;
                border:1px solid {COLORS['border']};
            }}
            QFrame:hover {{
                border-color:{COLORS['accent']};
                background:{COLORS['card_hover']};
            }}
        """)

    def _pill_style(self) -> str:
        print(f"[DEBUG] _pill_style() called")
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
        print(f"[DEBUG] _on_pill() called")
        # No guard here — clicking an already-added variant simply re-selects
        # it in the generator (which shows its skin form) rather than blocking.
        vname = (f"{self.display_name} ({label})"
                 if suffix else self.display_name)
        self.variant_add_requested.emit(self.carid, vname, suffix)

    def mark_variant_added(self, suffix: str):
        """
        Called by the sidebar after a variant has been added to the project.
        Hides the specific variant pill, matching the behaviour of single-body
        vehicle cards which are removed from the list on add.
        """
        print(f"[DEBUG] mark_variant_added() called")
        self._added.add(suffix)
        # Hide the specific variant pill that was just added
        if suffix in self._buttons:
            self._buttons[suffix].setVisible(False)
        # Hide the whole expander once every variant has been added
        if {s for s, _ in self.variants}.issubset(self._added):
            self.setVisible(False)


# NAV  PILL  BUTTON  (topbar tab)

class NavPill(QPushButton):
    """Animated topbar tab button with underline indicator."""

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
        self._apply(False)

    def _apply(self, active: bool):
        print(f"[DEBUG] _apply() called")
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
                    background-color: transparent;
                    color: {COLORS['text_secondary']};
                    border-radius: 8px;
                    border: none;
                    padding: 6px 16px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['card_hover']};
                    color: {COLORS['text']};
                }}
            """)

    def set_active(self, active: bool):
        print(f"[DEBUG] set_active() called")
        if self._active != active:
            self._apply(active)


# TOPBAR

class Topbar(QFrame):
    """Top navigation bar."""

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
        print(f"[DEBUG] _build() called")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(0)

        # logo / brand
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

        # menu pills
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
            layout.addSpacing(2)

        layout.addStretch()

        # generate button
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
        """Load the theme-appropriate topbar logo (White in dark, Black in light)."""
        icon_dir = os.path.join("gui", "Icons")
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
        """Rebuild the topbar in place (called after language/theme change)."""
        print(f"[DEBUG] _load_logo_pixmap() called")
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
            _tmp.setLayout(old)

        self.menu_buttons.clear()
        self._build()
        self.set_active(saved_view)


# SIDEBAR

class Sidebar(QFrame):
    """Left sidebar — project settings + vehicle picker."""

    # Signal now carries 3 args: carid, display_name, variant_suffix
    # variant_suffix is "" for normal vehicles and "ambulance" / "box" / etc
    # for variant bodies on vehicles like Pickup and Van.
    add_vehicle_requested = Signal(str, str, str)

    def __init__(self, parent: QWidget):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['sidebar_bg']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)

        self._populate_callback: Optional[Callable] = None
        self._vehicle_cards: List[VehicleCard] = []
        # Tracks VehicleVariantExpander widgets keyed by carid.
        self._variant_expanders: Dict[str, VehicleVariantExpander] = {}

        self._mod_name_text = ""
        self._author_text   = ""
        self.output_mode    = "steam"
        self.custom_output  = ""
        self.unpacked       = False

        self._build()


    def _build(self):
        print(f"[DEBUG] _build() called")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollArea > QWidget > QWidget {{ background:transparent; }}
        """)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(14, 14, 14, 14)
        inner_layout.setSpacing(8)

        sec = QLabel(t("project.title", default="PROJECT").upper())
        sec.setFont(font(11, "bold"))
        sec.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;letter-spacing:1px;"
        )
        inner_layout.addWidget(sec)

        self._mod_entry = LabelledEntry(
            t("project.mod_name", default="Mod Name"),
            t("project.mod_name_placeholder", default="MySkinPack"),
        )
        self._mod_entry.set_text(self._mod_name_text)
        inner_layout.addWidget(self._mod_entry)

        self._author_entry = LabelledEntry(
            t("project.author_name", default="Author"),
            t("project.author_name_placeholder", default="Your name"),
        )
        self._author_entry.set_text(self._author_text)
        inner_layout.addWidget(self._author_entry)

        out_lbl = QLabel(t("project.output_mode", default="Output Mode"))
        out_lbl.setFont(font(11, "bold"))
        out_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        inner_layout.addWidget(out_lbl)

        unpacked_frame = QFrame()
        unpacked_frame.setFixedHeight(44)
        unpacked_frame.setStyleSheet("background:transparent;border:none;")
        uf_row = QHBoxLayout(unpacked_frame)
        uf_row.setContentsMargins(10, 0, 10, 0)
        uf_row.setSpacing(8)

        self._unpacked_lbl = QLabel(t("project.unpacked_output"))
        self._unpacked_lbl.setFont(font(13, "bold"))
        self._unpacked_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;"
        )
        uf_row.addWidget(self._unpacked_lbl, 1)

        self._unpacked_toggle = ToggleSwitch()
        self._unpacked_toggle.setChecked(self.unpacked)
        self._unpacked_toggle.stateChanged.connect(self._on_unpacked_changed)
        uf_row.addWidget(self._unpacked_toggle)
        inner_layout.addWidget(unpacked_frame)

        steam_frame = QFrame()
        steam_frame.setFixedHeight(44)
        steam_frame.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['frame_bg']};
                border-radius:8px;
                border:1px solid {COLORS['border']};
            }}
        """)
        sf_row = QHBoxLayout(steam_frame)
        sf_row.setContentsMargins(10, 0, 10, 0)
        self._steam_radio = QRadioButton(
            t("project.steam_path", default="Save to Steam Mods")
        )
        self._steam_radio.setFont(font(13, "bold"))
        self._steam_radio.setStyleSheet(_radio_qss())
        self._steam_radio.setChecked(self.output_mode == "steam")
        sf_row.addWidget(self._steam_radio)
        inner_layout.addWidget(steam_frame)

        custom_frame = QFrame()
        custom_frame.setFixedHeight(44)
        custom_frame.setStyleSheet(steam_frame.styleSheet())
        cf_row = QHBoxLayout(custom_frame)
        cf_row.setContentsMargins(10, 0, 10, 0)
        self._custom_radio = QRadioButton(
            t("project.custom_location", default="Custom Location")
        )
        self._custom_radio.setFont(font(13, "bold"))
        self._custom_radio.setStyleSheet(_radio_qss())
        self._custom_radio.setChecked(self.output_mode == "custom")
        cf_row.addWidget(self._custom_radio)
        inner_layout.addWidget(custom_frame)

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

        browse_btn = QPushButton("📁")
        browse_btn.setFixedSize(32, 32)
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:6px;
                font-size:14px;
            }}
            QPushButton:hover {{
                border-color:{COLORS['accent']};
                background:{COLORS['card_hover']};
            }}
        """)
        browse_btn.clicked.connect(self._browse_custom_output)
        cp_row.addWidget(browse_btn)
        inner_layout.addWidget(self._custom_path_frame)

        self._output_group = QButtonGroup(self)
        self._output_group.addButton(self._steam_radio)
        self._output_group.addButton(self._custom_radio)

        self._steam_radio.toggled.connect(self._on_output_mode_changed)
        self._custom_radio.toggled.connect(self._on_output_mode_changed)
        self._update_custom_path_visibility()

        inner_layout.addWidget(HSeparator())

        veh_lbl = QLabel(t("project.add_vehicle", default="Add Vehicle"))
        veh_lbl.setFont(font(11, "bold"))
        veh_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        inner_layout.addWidget(veh_lbl)

        # ── Developer testing mode: Add All Vehicles button ────────────── #
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
        inner_layout.addWidget(self._add_all_btn)

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
        inner_layout.addWidget(self._search)

        self._vehicle_list = QVBoxLayout()
        self._vehicle_list.setSpacing(4)
        self._vehicle_list.setContentsMargins(0, 0, 0, 0)
        inner_layout.addLayout(self._vehicle_list)
        inner_layout.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll)


    def populate_vehicles(self, add_callback: Callable[[str, str, str], None]):
        """Called by the main window to populate the sidebar vehicle list."""
        self._populate_callback = add_callback
        state.sidebar_vehicle_buttons.clear()
        self._clear_vehicle_list()

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

    def _get_generator(self):
        """Walk up to main window and return the generator tab, or None."""
        print(f"[DEBUG] populate_vehicles: rebuilding sidebar vehicle list")
        mw = self.window()
        if mw and hasattr(mw, "tabs"):
            return mw.tabs.get("generator")
        return None

    def _is_fully_in_project(self, carid: str, project_keys: set) -> bool:
        """
        Return True only when every variant of carid is already in the project.
        For single-body vehicles that means one key; for multi-variant vehicles
        the user can still add remaining bodies even if one is present.
        """
        print(f"[DEBUG] _is_fully_in_project() called")
        variants = _get_vehicle_variants(carid)
        for suffix, _ in variants:
            from gui.tabs.generator import _make_project_key
            if _make_project_key(carid, suffix) not in project_keys:
                return False
        return True

    def restore_vehicle(self, carid: str, variant_suffix: str = ""):
        """
        Add a vehicle (or a single variant) back to the sidebar after it has
        been removed from the project.  Called by the generator tab.
        """
        print(f"[DEBUG] restore_vehicle() called")
        if self._populate_callback is None:
            return

        name = state.vehicle_ids.get(carid) or state.added_vehicles.get(carid, carid)
        variants = _get_vehicle_variants(carid)

        if len(variants) > 1:
            # Multi-variant: if an expander already exists for this carid,
            # just un-gray the pill.  Otherwise rebuild the whole expander.
            if carid in self._variant_expanders:
                exp = self._variant_expanders[carid]
                exp.setVisible(True)
                # Re-enable the specific pill that was removed
                if variant_suffix in exp._buttons:
                    btn = exp._buttons[variant_suffix]
                    btn.setEnabled(True)
                    btn.setVisible(True)
                    btn.setStyleSheet(exp._pill_style())
                    exp._added.discard(variant_suffix)
            else:
                self._add_variant_expander(carid, name, variants, self._populate_callback)
        else:
            # Single-body: only add the card back if it isn't already there
            if not any(c.carid == carid for c in self._vehicle_cards):
                self._add_vehicle_card(carid, name, self._populate_callback)

    def _insert_sorted(self, widget: QWidget, display_name: str):
        """Insert widget into _vehicle_list at the correct alphabetical position."""
        target = display_name.lower()
        count  = self._vehicle_list.count()
        insert_at = count  # default: append
        for i in range(count):
            item = self._vehicle_list.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w is None:
                continue
            # Get the display name from whatever widget type is at this slot
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
        """Add a VehicleVariantExpander for multi-body vehicles."""
        print(f"[DEBUG] _insert_sorted() called")
        is_custom = carid in state.added_vehicles
        expander = VehicleVariantExpander(carid, name, variants, parent=self,
                                          is_custom=is_custom)
        expander.variant_add_requested.connect(
            lambda c, d, v: self._on_add_vehicle(c, d, v, callback)
        )
        self._variant_expanders[carid] = expander
        self._insert_sorted(expander, name)
        fade_in(expander, 180)
        # Header hover → default image
        self._attach_hover_preview(expander._header, carid, "")
        # Each pill hover → variant-specific image
        for suffix, _label in variants:
            if suffix in expander._buttons:
                self._attach_hover_preview(expander._buttons[suffix], carid, suffix)

    def _add_vehicle_card(self, carid: str, name: str, callback: Callable):
        """Add a plain VehicleCard for single-body vehicles."""
        is_custom = carid in state.added_vehicles
        card = VehicleCard(carid, name, parent=self, is_custom=is_custom)
        card.add_requested.connect(
            lambda c, d: self._on_add_vehicle(c, d, "", callback)
        )
        self._vehicle_cards.append(card)
        state.sidebar_vehicle_buttons.append((card, carid, name, ""))
        self._insert_sorted(card, name)
        fade_in(card, 180)
        self._attach_hover_preview(card, carid, "")

    def _attach_hover_preview(
        self, widget: QWidget, carid: str, variant_suffix: str = ""
    ) -> None:
        mw = self.window()
        if mw is None or not hasattr(mw, "preview_manager"):
            return
        img_name = f"{variant_suffix}.jpg" if variant_suffix else "default.jpg"
        img_path = os.path.join("gui", "images", "vehicles", carid, img_name)
        # Fall back to default.jpg if the variant image doesn't exist
        if not os.path.exists(img_path):
            img_path = os.path.join("gui", "images", "vehicles", carid, "default.jpg")
        mw.preview_manager.setup_robust_hover(
            widget, carid, get_image_path=lambda p=img_path: p
        )

    def _on_add_vehicle(self, carid: str, name: str, variant: str, callback: Callable):
        """
        print(f"[DEBUG] _add_vehicle_card() called")
        Invoked when any vehicle (plain card or variant pill) is added.
        Forwards to the main-window callback, then updates the sidebar state.
        """
        callback(carid, name, variant)

        if carid in self._variant_expanders:
            # Multi-variant expander: mark the specific variant as added.
            # The expander hides itself when all variants are done.
            self._variant_expanders[carid].mark_variant_added(variant)
        else:
            # Plain single-variant card: remove it entirely.
            for card in list(self._vehicle_cards):
                if card.carid == carid:
                    self._vehicle_list.removeWidget(card)
                    card.deleteLater()
                    self._vehicle_cards.remove(card)
                    break

        state.sidebar_vehicle_buttons = [
            item for item in state.sidebar_vehicle_buttons
            if not (item[1] == carid and item[3] == variant)
        ]

    def _clear_vehicle_list(self):
        print(f"[DEBUG] _clear_vehicle_list() called")
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
        """
        Developer testing mode: add every known vehicle and every variant to
        the project in one shot.  Silently skips vehicles already in the project.
        """
        print(f"[DEBUG] _add_all_vehicles: testing mode bulk-add triggered")
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
        print(f"[DEBUG] _on_output_mode_changed() called")
        self.output_mode = "steam" if self._steam_radio.isChecked() else "custom"
        self._update_custom_path_visibility()

    def _on_unpacked_changed(self, state_val: int):
        print(f"[DEBUG] _on_unpacked_changed() called")
        self.unpacked = (state_val == 2)

    def _update_custom_path_visibility(self):
        print(f"[DEBUG] _update_custom_path_visibility() called")
        self._custom_path_frame.setVisible(self.output_mode == "custom")

    def _browse_custom_output(self):
        print(f"[DEBUG] _browse_custom_output: opening output folder dialog")
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


    def refresh_ui(self, populate_callback: Optional[Callable] = None):
        print(f"[DEBUG] refresh_ui() called")
        if populate_callback:
            self._populate_callback = populate_callback
        try:
            self._mod_name_text = self.get_mod_name()
            self._author_text   = self.get_author()
        except Exception:
            pass
        try:
            self.unpacked = self._unpacked_toggle.isChecked()
        except Exception:
            pass

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
            _tmp.setLayout(old)

        self._vehicle_cards       = []
        self._variant_expanders   = {}
        self._build()
        if self._populate_callback:
            self.populate_vehicles(self._populate_callback)


# HELPERS

def _radio_qss() -> str:
    return f"""
        QRadioButton {{
            color: {COLORS['text']};
            font-size: 13px;
            spacing: 8px;
            background: transparent;
        }}
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 8px;
            border: 2px solid {COLORS['border']};
            background: {COLORS['frame_bg']};
        }}
        QRadioButton::indicator:checked {{
            border-color: {COLORS['accent']};
            background: {COLORS['accent']};
        }}
    """


