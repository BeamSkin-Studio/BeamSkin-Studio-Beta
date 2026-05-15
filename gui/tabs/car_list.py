from __future__ import annotations
import json
import os
import re
import zipfile
from typing import List, Tuple

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import QPixmap, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QCheckBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QFileDialog, QDialog,
    QApplication, QSizePolicy,
)

from gui.theme import COLORS, font
from gui.state import state

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return kw.get("default", key)

try:
    from utils.file_ops import load_added_vehicles_json
except ImportError:
    def load_added_vehicles_json():
        return {}


# PATHS

_APP_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_IMAGES_DIR = os.path.join(_APP_DIR, "gui", "images", "vehicles")
_SETTINGS   = os.path.join(_APP_DIR, "data", "app_settings.json")

CARD_IMG_H  = 160
CARD_W      = 280
CARD_SPACING = 12
GLOW_PAD    = 7       # transparent outer ring — glow and grow effect live here        


# VARIANT IMAGE HELPER

_UV_KEYWORDS = ("uv", "uvmap", "uv_map", "uv_layout", "uv1_layout")
_UV_EXTS     = (".dds", ".png", ".jpg", ".jpeg", ".pdn")
# Same qualifier list as mod_scanner — catches double-extension typed textures
# like name.color.dds / name.data.dds that happen to contain "uv" in the stem.
_UV_TYPE_QUALIFIERS = (
    ".color", ".colour", ".data", ".normal", ".nrm",
    ".metallic", ".roughness", ".alpha", ".ao",
)
_UV_MAX_UNDERSCORES = 3

# vehicles/ folder root — mirrors VEHICLE_FOLDER in utils/file_ops.py
_VEHICLES_DIR = os.path.join(_APP_DIR, "vehicles")


def _is_uv_map_file(fn: str) -> bool:
    """Return True when *fn* looks like a UV layout template, not a livery texture."""
    lower = fn.lower()
    if not any(lower.endswith(ext) for ext in _UV_EXTS):
        return False
    stem = os.path.splitext(lower)[0]
    if not any(kw in stem for kw in _UV_KEYWORDS):
        return False
    if any(stem.endswith(q) or (q + ".") in stem for q in _UV_TYPE_QUALIFIERS):
        return False
    if stem.count("_") > _UV_MAX_UNDERSCORES:
        return False
    return True


def _get_local_uv_map_paths(carid: str) -> List[str]:
    """Return UV-layout image paths for a developer-added vehicle.

    Searches two locations so that UV maps are found regardless of whether
    they were pre-copied to the images cache:

    1. ``gui/images/vehicles/{carid}/``  -- the images cache folder.
    2. ``vehicles/{carid}/``             -- the actual mod folder tree
       (walked recursively, same rules as mod_scanner._find_uv_maps).
    """
    seen: set = set()
    results: List[str] = []

    def _scan_tree(root: str) -> None:
        for dirpath, _dirs, filenames in os.walk(root):
            for fn in sorted(filenames):
                if _is_uv_map_file(fn):
                    full = os.path.join(dirpath, fn)
                    if full not in seen:
                        seen.add(full)
                        results.append(full)

    images_dir = os.path.join(_IMAGES_DIR, carid)
    if os.path.isdir(images_dir):
        _scan_tree(images_dir)

    vehicles_dir = os.path.join(_VEHICLES_DIR, carid)
    if os.path.isdir(vehicles_dir):
        _scan_tree(vehicles_dir)

    return results


def _get_variant_images(carid: str) -> List[Tuple[str, str]]:
    """Return [(label, abs_path), …] for every image in a vehicle's folder.

    Files are sorted so that ``default.*`` always comes first, then
    alphabetically.  Only .jpg / .jpeg / .png files are returned.
    """
    vehicle_dir = os.path.join(_IMAGES_DIR, carid)
    if not os.path.isdir(vehicle_dir):
        return []
    entries: List[Tuple[str, str]] = []
    for fn in sorted(os.listdir(vehicle_dir)):
        if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        if _is_uv_map_file(fn):
            continue
        stem = os.path.splitext(fn)[0]
        label = "Default" if stem.lower() == "default" else stem.replace("_", " ").title()
        entries.append((label, os.path.join(vehicle_dir, fn)))
    # Ensure 'Default' is first
    entries.sort(key=lambda x: (x[0] != "Default", x[0].lower()))
    return entries


# BUILT-IN VEHICLE LIST

_BUILTIN_VEHICLES: List[Tuple[str, str]] = [
    ("autobello", "Autobello Piccolina"), ("atv", "FPU Wydra"),
    ("barstow", "Gavril Barstow"), ("bastion", "Bruckell Bastion"),
    ("bluebuck", "Gavril Bluebuck"), ("bolide", "Civetta Bolide"),
    ("burnside", "Burnside Special"), ("covet", "Ibishu Covet"),
    ("citybus", "Wentward DT40L"), ("bx", "Ibishu BX-Series"),
    ("dryvan", "Dry Van Trailer"), ("dumptruck", "Hirochi HT-55"),
    ("etk800", "ETK 800 Series"), ("etkc", "ETK K Series"),
    ("etki", "ETK I Series"), ("fullsize", "Gavril Grand Marshal"),
    ("hopper", "Ibishu Hopper"), ("lansdale", "Soliad Lansdale"),
    ("legran", "Bruckell Legran"), ("midsize", "Newer Ibishu Pessima"),
    ("miramar", "Ibishu Miramar"), ("moonhawk", "Bruckell Moonhawk"),
    ("md_series", "Gavril MD-Series"), ("midtruck", "Autobello Stambecco"),
    ("nine", "Bruckell Nine"), ("pessima", "Older Ibishu Pessima"),
    ("pickup", "Gavril D Series"), ("pigeon", "Ibishu Pigeon"),
    ("racetruck", "SP Dunekicker"), ("roamer", "Gavril Roamer"),
    ("rockbouncer", "SP Rockbasher"), ("sbr", "Hirochi SBR4"),
    ("scintilla", "Civetta Scintilla"), ("sunburst2", "Hirochi Sunburst"),
    ("us_semi", "Gavril T Series"), ("utv", "Hirochi Aurata"),
    ("van", "Gavril H Series"), ("vivace", "Cherrier FCV"),
    ("wendover", "Soliad Wendover"), ("wigeon", "Ibishu Wigeon"),
    ("wl40", "Hirochi WL-40"),
]


# UV-MAP SELECTION DIALOG

class _UVSelectDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        carid: str,
        found_files: List[Tuple[str, str]],
    ):
        super().__init__(parent)
        self.setWindowTitle(t("car_list.select_uv_title"))
        self.setMinimumSize(600, 400)
        self.setModal(True)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self.selected_files: List[Tuple[str, str]] = []
        self._checkboxes: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(
            f"Multiple UV maps found for <b>{carid}</b><br>"
            + t("car_list.select_uv_prompt")
        )
        title.setFont(font(13, "bold"))
        title.setWordWrap(True)
        title.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}"
        )
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        inner_col = QVBoxLayout(inner)
        inner_col.setContentsMargins(8, 8, 8, 8)
        inner_col.setSpacing(6)

        main_zip = found_files[0][1] if found_files else ""
        for file_path, source_zip in found_files:
            filename = os.path.basename(file_path)
            source_name = os.path.basename(source_zip)
            display = (
                f"{filename} (from {source_name})"
                if source_zip != main_zip else filename
            )
            cb = QCheckBox(display)
            cb.setFont(font(12))
            cb.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
            inner_col.addWidget(cb)
            self._checkboxes[(file_path, source_zip)] = cb

        inner_col.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self._mk_btn(t("car_list.select_all"),   self._select_all))
        btn_row.addWidget(self._mk_btn(t("car_list.deselect_all"), self._deselect_all))
        btn_row.addStretch()
        btn_row.addWidget(self._mk_btn(t("dialog.cancel"), self.reject, "danger"))
        btn_row.addWidget(self._mk_btn(t("dialog.ok"),     self._on_ok, "primary"))
        layout.addLayout(btn_row)

    def _mk_btn(self, text: str, cmd, style: str = "secondary") -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(font(12, "bold"))
        btn.setFixedHeight(36)
        btn.setCursor(Qt.PointingHandCursor)
        if style == "primary":
            bg, bgh, tc = COLORS["accent"], COLORS["accent_hover"], COLORS["accent_text"]
        elif style == "danger":
            bg  = COLORS.get("error", "#e74c3c")
            bgh = COLORS.get("error_hover", "#c0392b")
            tc  = "white"
        else:
            bg, bgh, tc = COLORS["card_bg"], COLORS["card_hover"], COLORS["text"]
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{bg};color:{tc};
                border-radius:8px;border:1px solid {COLORS['border']};
                padding:4px 16px;
            }}
            QPushButton:hover {{ background:{bgh}; }}
        """)
        btn.clicked.connect(cmd)
        return btn

    def _select_all(self):
        print(f"[DEBUG] _select_all() called")
        for cb in self._checkboxes.values():
            cb.setChecked(True)

    def _deselect_all(self):
        print(f"[DEBUG] _deselect_all() called")
        for cb in self._checkboxes.values():
            cb.setChecked(False)

    def _on_ok(self):
        print(f"[DEBUG] _on_ok() called")
        self.selected_files = [
            file_info
            for file_info, cb in self._checkboxes.items()
            if cb.isChecked()
        ]
        if self.selected_files:
            self.accept()


# ANIMATED MODERN CARD

def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _lerp_color(c1: str, c2: str, t: float) -> QColor:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return QColor(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


class AnimatedCard(QFrame):
    """
    Modern vehicle card with hover animation drawn entirely in paintEvent.
    No QGraphicsEffect — avoids QPainter reentrancy crashes inside QScrollArea.

    At rest  : card background + 1px border at full GLOW_PAD inset
    On hover : card expands into the GLOW_PAD ring (grow) + layered glow rings
    """

    def __init__(self, parent: QWidget | None = None):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent)
        # Let our paintEvent own the background entirely
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setStyleSheet("AnimatedCard { background: transparent; border: none; }")
        self._t = 0.0
        self._hovered = False
        self._tick = QTimer(self)
        self._tick.setInterval(16)
        self._tick.timeout.connect(self._step)

    def _step(self):
        print(f"[DEBUG] _step() called")
        target = 1.0 if self._hovered else 0.0
        self._t += (target - self._t) * 0.20
        self.update()
        if abs(self._t - target) < 0.008:
            self._t = target
            self._tick.stop()
            self.update()

    def enterEvent(self, event):
        print(f"[DEBUG] enterEvent() called")
        super().enterEvent(event)
        self._hovered = True
        if not self._tick.isActive():
            self._tick.start()

    def leaveEvent(self, event):
        print(f"[DEBUG] leaveEvent() called")
        super().leaveEvent(event)
        self._hovered = False
        if not self._tick.isActive():
            self._tick.start()

    def paintEvent(self, _event):
        print(f"[DEBUG] paintEvent() called")
        t  = self._t
        w, h = self.width(), self.height()

        # Card rect shrinks into GLOW_PAD at rest; grows outward as t→1
        grow  = int(t * 3)                    # expand up to 3px into the ring
        inset = max(0, GLOW_PAD - grow)
        radius = 12

        accent_rgb = _hex_to_rgb(COLORS["accent"])
        ar, ag, ab = accent_rgb

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # ── glow layers (drawn outward → inward so inner overwrites outer) ──
        if t > 0.01:
            num_layers = 7
            for i in range(num_layers, 0, -1):
                layer_inset = max(0, inset - i)
                alpha = int(t * 28 * (i / num_layers))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(ar, ag, ab, alpha))
                r = radius + (GLOW_PAD - layer_inset)
                p.drawRoundedRect(layer_inset, layer_inset,
                                  w - 2 * layer_inset, h - 2 * layer_inset,
                                  r, r)

        # ── card background ──
        bg     = _lerp_color(COLORS["card_bg"], COLORS.get("card_hover", COLORS["card_bg"]), t)
        border = _lerp_color(COLORS["border"],  COLORS["accent"], t)
        bw = 1.0 + t * 0.6

        p.setBrush(bg)
        p.setPen(QPen(border, bw))
        p.drawRoundedRect(inset, inset, w - 2 * inset, h - 2 * inset, radius, radius)

        p.end()


# CAR LIST TAB

class CarListTab(QWidget):
    def __init__(self, parent: QWidget, **_):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self._items: List[Tuple[QWidget, str, str]] = []
        self._modern_row = 0
        self._modern_col = 0
        self._modern_cols_current = 0   
        self._view_mode: str = self._load_view_mode()

        self._setup_ui()
        self._populate()

    def _load_view_mode(self) -> str:
        print(f"[DEBUG] _load_view_mode() called")
        try:
            if os.path.exists(_SETTINGS):
                with open(_SETTINGS, "r", encoding="utf-8") as f:
                    return json.load(f).get("carlist_view_mode", "classic")
        except Exception:
            pass
        return "classic"

    def _save_view_mode(self):
        print(f"[DEBUG] _save_view_mode() called")
        try:
            data: dict = {}
            if os.path.exists(_SETTINGS):
                with open(_SETTINGS, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["carlist_view_mode"] = self._view_mode
            os.makedirs(os.path.dirname(_SETTINGS), exist_ok=True)
            with open(_SETTINGS, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[DEBUG] CarListTab: failed to save view mode: {e}")

    def _setup_ui(self):
        print(f"[DEBUG] _setup_ui() called")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText(t("car_list.search_placeholder"))
        self._search.setFixedHeight(36)
        self._search.setFont(font(13))
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 12px;
            }}
            QLineEdit:focus {{
                border-color:{COLORS.get('border_focus', COLORS['accent'])};
            }}
        """)
        self._search.textChanged.connect(self._filter)
        top_bar.addWidget(self._search, 1)

        self._btn_classic = QPushButton(t("car_list.view_classic"))
        self._btn_modern  = QPushButton(t("car_list.view_modern"))
        for btn, mode in ((self._btn_classic, "classic"), (self._btn_modern, "modern")):
            btn.setFixedSize(108, 36)
            btn.setFont(font(12, "bold"))
            btn.setCursor(Qt.PointingHandCursor)
        self._btn_classic.clicked.connect(lambda: self._set_view("classic"))
        self._btn_modern.clicked.connect(lambda: self._set_view("modern"))
        self._update_toggle_style()

        top_bar.addWidget(self._btn_classic)
        top_bar.addWidget(self._btn_modern)

        root.addLayout(top_bar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}"
        )
        self._rebuild_inner()
        root.addWidget(self._scroll, 1)

    def _rebuild_inner(self):
        print(f"[DEBUG] _rebuild_inner() called")
        outer = QWidget()
        outer.setStyleSheet("background:transparent;")
        outer_vbox = QVBoxLayout(outer)
        outer_vbox.setContentsMargins(0, 0, 0, 0)
        outer_vbox.setSpacing(0)

        content = QWidget()
        content.setStyleSheet("background:transparent;")

        if self._view_mode == "modern":
            layout = QGridLayout(content)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(CARD_SPACING)
            layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        else:
            layout = QVBoxLayout(content)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            layout.addStretch()

        outer_vbox.addWidget(content)
        outer_vbox.addStretch()

        self._scroll.setWidget(outer)
        self._list_widget  = content
        self._list_layout  = layout
        self._modern_row   = 0
        self._modern_col   = 0
        self._modern_cols_current = 0

    def _update_toggle_style(self):
        print(f"[DEBUG] _update_toggle_style() called")
        def _style(active: bool) -> str:
            bg  = COLORS["accent"]       if active else COLORS["card_bg"]
            bgh = COLORS["accent_hover"] if active else COLORS.get("card_hover", COLORS["card_bg"])
            tc  = COLORS["accent_text"]  if active else COLORS["text"]
            return f"""
                QPushButton {{
                    background:{bg};color:{tc};
                    border:1px solid {COLORS['border']};
                    border-radius:8px;padding:4px 10px;
                }}
                QPushButton:hover {{ background:{bgh}; }}
            """
        self._btn_classic.setStyleSheet(_style(self._view_mode == "classic"))
        self._btn_modern.setStyleSheet(_style(self._view_mode == "modern"))

    def _set_view(self, mode: str):
        if mode == self._view_mode:
            return
        self._view_mode = mode
        self._save_view_mode()
        self._update_toggle_style()
        self.refresh_ui()

    def _populate(self):
        print(f"[DEBUG] _populate() called")
        added = load_added_vehicles_json()
        state.added_vehicles.clear()
        state.added_vehicles.update(added)

        all_vehicles: List[Tuple[str, str, bool]] = []
        for carid, name in _BUILTIN_VEHICLES:
            all_vehicles.append((carid, name, False))
        for carid, name in state.added_vehicles.items():
            all_vehicles.append((carid, name, True))
        all_vehicles.sort(key=lambda x: x[1].lower())

        for carid, name, dev_added in all_vehicles:
            self._add_card(carid, name, developer_added=dev_added)

    def _add_card(self, carid: str, name: str, developer_added: bool):
        print(f"[DEBUG] _add_card() called")
        if self._view_mode == "modern":
            card = self._build_modern_card(carid, name, developer_added)
            self._items.append((card, carid, name))
            self._list_layout.addWidget(card)
        else:
            insert_pos = len(self._items)
            for i, (_, _, existing_name) in enumerate(self._items):
                if existing_name.lower() > name.lower():
                    insert_pos = i
                    break

            card = self._build_card(carid, name, developer_added)
            self._items.insert(insert_pos, (card, carid, name))

            while self._list_layout.count() > 1:
                self._list_layout.takeAt(0)
            for i, (w, _, _) in enumerate(self._items):
                self._list_layout.insertWidget(i, w)

            # Classic mode: attach the floating hover-preview popup
            self._attach_hover_preview(card, carid)

    def _attach_hover_preview(self, widget: QWidget, carid: str,
                              get_image_path=None) -> None:
        """Wire enter/leave preview hooks for both Classic and Modern modes."""
        mw = self.window()
        if mw is not None and hasattr(mw, "preview_manager"):
            mw.preview_manager.setup_robust_hover(
                widget, carid, get_image_path=get_image_path
            )

    @staticmethod
    def _rounded_top_pixmap(src: QPixmap, w: int, h: int, radius: int = 12) -> QPixmap:
        from PySide6.QtGui import QPainter, QPainterPath, QColor
        scaled = src.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        ox = max(0, (scaled.width()  - w) // 2)
        oy = max(0, (scaled.height() - h) // 2)
        cropped = scaled.copy(ox, oy, w, h)

        result = QPixmap(w, h)
        result.fill(QColor(0, 0, 0, 0))
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.moveTo(radius, 0)
        path.lineTo(w - radius, 0)
        path.arcTo(w - radius * 2, 0, radius * 2, radius * 2, 90, -90)   
        path.lineTo(w, h)
        path.lineTo(0, h)
        path.lineTo(0, radius)
        path.arcTo(0, 0, radius * 2, radius * 2, 180, -90)                
        path.closeSubpath()
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return result

    def _cols_for_width(self, viewport_width: int) -> int:
        print(f"[DEBUG] _cols_for_width() called")
        available = max(viewport_width - 8, CARD_W)   
        return max(1, available // (CARD_W + CARD_SPACING))

    def _card_width_for(self, viewport_width: int, cols: int) -> int:
        print(f"[DEBUG] _card_width_for() called")
        margins = 8   
        spacing = CARD_SPACING * (cols - 1)
        return max(CARD_W, (viewport_width - margins - spacing) // cols) - 2

    def _reflow_modern_grid(self):
        print(f"[DEBUG] _reflow_modern_grid() called")
        if self._view_mode != "modern" or not self._items:
            return
        vw = self._scroll.viewport().width()
        cols = self._cols_for_width(vw)
        card_w = self._card_width_for(vw, cols)

        if cols == self._modern_cols_current and card_w == getattr(self, "_modern_card_w", 0):
            return
        self._modern_cols_current = cols
        self._modern_card_w = card_w

        for card, _, _ in self._items:
            self._list_layout.removeWidget(card)

        for idx, (card, _, _) in enumerate(self._items):
            r, c = divmod(idx, cols)
            self._list_layout.addWidget(card, r, c)
            card.setFixedWidth(card_w)

            img_lbl = card.findChild(QLabel, "vehicle_img")
            if img_lbl is not None:
                inner_w = card_w - 2 * GLOW_PAD
                img_lbl.setGeometry(0, 0, inner_w, CARD_IMG_H)
                img_path = card.property("img_path")
                if img_path:
                    img_lbl.setPixmap(self._rounded_top_pixmap(QPixmap(img_path), inner_w, CARD_IMG_H, radius=11))
                else:
                    img_lbl.resize(inner_w, CARD_IMG_H)

    def showEvent(self, event):
        print(f"[DEBUG] showEvent() called")
        super().showEvent(event)
        self._modern_cols_current = 0
        self._modern_card_w = 0
        self._reflow_modern_grid()

    def resizeEvent(self, event):
        print(f"[DEBUG] resizeEvent() called")
        super().resizeEvent(event)
        self._reflow_modern_grid()

    def _build_card(self, carid: str, name: str, developer_added: bool) -> QFrame:
        print(f"[DEBUG] _build_card() called")
        card = QFrame()
        card.setObjectName("vehicle_card")
        card.setStyleSheet(f"""
            #vehicle_card {{
                background:{COLORS['card_bg']};
                border-radius:12px;
                border:1px solid {COLORS['border']};
            }}
            #vehicle_card:hover {{
                border:1px solid {COLORS['accent']};
                background:{COLORS.get('card_hover', COLORS['card_bg'])};
            }}
        """)

        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        icon = QLabel("🚗")
        icon.setFont(font(20))
        icon.setStyleSheet("background:transparent;border:none;")
        icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        row.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        text_col.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(name)
        name_lbl.setFont(font(14, "bold"))
        name_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        text_col.addWidget(name_lbl)

        id_lbl = QLabel(carid)
        id_lbl.setFont(font(12))
        id_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        text_col.addWidget(id_lbl)

        row.addLayout(text_col, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        if not developer_added:
            uv_btn = self._mk_btn(
                t("car_list.get_uv_map"),
                lambda _, c=carid: self._get_uv_map(c),
                "primary",
            )
            btn_row.addWidget(uv_btn)
        else:
            # For custom-added vehicles show UV button only when a local UV
            # map was copied in during import.
            local_uvs = _get_local_uv_map_paths(carid)
            if local_uvs:
                uv_btn = self._mk_btn(
                    t("car_list.get_uv_map"),
                    lambda _, c=carid: self._get_local_uv_map(c),
                    "primary",
                )
                btn_row.addWidget(uv_btn)

        copy_btn = self._mk_btn(
            t("car_list.copy_id"),
            lambda _, c=carid: self._copy_carid(c),
            "secondary",
        )
        btn_row.addWidget(copy_btn)

        row.addLayout(btn_row)
        return card

    def _build_modern_card(self, carid: str, name: str, developer_added: bool) -> AnimatedCard:
        print(f"[DEBUG] _build_modern_card() called")
        card = AnimatedCard()
        card.setObjectName("vehicle_card")
        card.setFixedWidth(CARD_W)

        variants = _get_variant_images(carid)
        card._variants    = variants
        card._variant_idx = 0

        # GLOW_PAD on all sides — glow + grow effect lives in this outer ring
        inner_w = CARD_W - 2 * GLOW_PAD
        col = QVBoxLayout(card)
        col.setContentsMargins(GLOW_PAD, GLOW_PAD, GLOW_PAD, GLOW_PAD + 5)
        col.setSpacing(8)

        img_container = QFrame()
        img_container.setObjectName("vehicle_img_container")
        img_container.setFixedHeight(CARD_IMG_H)
        img_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        img_container.setStyleSheet(
            f"QFrame {{ background:{COLORS.get('frame_bg', COLORS['card_bg'])};"
            f"border:none;"
            f"border-top-left-radius:11px; border-top-right-radius:11px; }}"
        )

        img_lbl = QLabel(img_container)
        img_lbl.setObjectName("vehicle_img")
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setStyleSheet("background:transparent;border:none;")
        img_lbl.setGeometry(0, 0, inner_w, CARD_IMG_H)

        if variants:
            first_label, first_path = variants[0]
            card.setProperty("img_path", first_path)
            img_lbl.setPixmap(
                self._rounded_top_pixmap(QPixmap(first_path), inner_w, CARD_IMG_H, radius=11)
            )
        else:
            card.setProperty("img_path", "")
            img_lbl.setText("🚗")
            img_lbl.setFont(font(38))

        if len(variants) > 1:
            _NAV_BTN = """
                QPushButton {{
                    background: rgba(0,0,0,110);
                    color: white;
                    border-radius: {r}px;
                    border: none;
                    font-size: 18px;
                    font-weight: bold;
                    padding: 0px;
                }}
                QPushButton:hover {{ background: rgba(0,0,0,210); }}
            """

            # Left arrow
            prev_btn = QPushButton("‹", img_container)
            prev_btn.setFixedSize(26, 38)
            prev_btn.setStyleSheet(_NAV_BTN.format(r=6))
            prev_btn.setCursor(Qt.PointingHandCursor)
            prev_btn.raise_()

            # Right arrow
            next_btn = QPushButton("›", img_container)
            next_btn.setFixedSize(26, 38)
            next_btn.setStyleSheet(_NAV_BTN.format(r=6))
            next_btn.setCursor(Qt.PointingHandCursor)
            next_btn.raise_()

            # Variant label badge — bottom-left of image
            var_lbl = QLabel(variants[0][0], img_container)
            var_lbl.setObjectName("variant_label")
            var_lbl.setFont(font(9, "bold"))
            var_lbl.setStyleSheet("""
                QLabel {
                    color: white;
                    background: rgba(0,0,0,145);
                    border-radius: 4px;
                    padding: 2px 6px;
                    border: none;
                }
            """)
            var_lbl.adjustSize()
            var_lbl.raise_()

            # Dot indicators
            dot_size   = 6
            dot_gap    = 4
            dot_widgets: List[QLabel] = []
            for di in range(len(variants)):
                d = QLabel(img_container)
                d.setFixedSize(dot_size, dot_size)
                d.setStyleSheet(
                    "background:white;border-radius:3px;border:none;"
                    if di == 0 else
                    "background:rgba(255,255,255,90);border-radius:3px;border:none;"
                )
                d.raise_()
                dot_widgets.append(d)

            def _reposition(w, h,
                            pb=prev_btn, nb=next_btn,
                            vl=var_lbl, dws=dot_widgets,
                            il=img_lbl, ds=dot_size, dg=dot_gap):
                """Reposition all overlay widgets to match the container size."""
                il.setGeometry(0, 0, w, h)
                pb.move(4, (h - pb.height()) // 2)
                nb.move(w - nb.width() - 4, (h - nb.height()) // 2)
                vl.move(6, h - vl.height() - 6)
                dots_w = len(dws) * ds + (len(dws) - 1) * dg
                dx = (w - dots_w) // 2
                dy = h - ds - 4
                for di, dw in enumerate(dws):
                    dw.move(dx + di * (ds + dg), dy)

            # Initial placement
            _reposition(img_container.width() or inner_w, CARD_IMG_H)

            # Keep positions correct whenever the container is resized
            img_container.resizeEvent = lambda ev, rp=_reposition: rp(
                ev.size().width(), ev.size().height()
            )

            def _switch(delta, c=card, lbl=img_lbl, vl=var_lbl, dws=dot_widgets):
                c._variant_idx = (c._variant_idx + delta) % len(c._variants)
                v_label, v_path = c._variants[c._variant_idx]
                c.setProperty("img_path", v_path)
                vl.setText(v_label)
                vl.adjustSize()
                vl.move(6, img_container.height() - vl.height() - 6)
                iw = img_container.width() or inner_w
                ih = img_container.height() or CARD_IMG_H
                lbl.setPixmap(
                    CarListTab._rounded_top_pixmap(QPixmap(v_path), iw, ih, radius=11)
                )
                for di, dw in enumerate(dws):
                    dw.setStyleSheet(
                        "background:white;border-radius:3px;border:none;"
                        if di == c._variant_idx else
                        "background:rgba(255,255,255,90);border-radius:3px;border:none;"
                    )

            prev_btn.clicked.connect(lambda _=False: _switch(-1))
            next_btn.clicked.connect(lambda _=False: _switch(1))

        col.addWidget(img_container)

        info = QWidget()
        info.setStyleSheet("background:transparent;border:none;")
        info_col = QVBoxLayout(info)
        info_col.setContentsMargins(10, 0, 10, 0)
        info_col.setSpacing(3)

        name_lbl = QLabel(name)
        name_lbl.setFont(font(13, "bold"))
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        info_col.addWidget(name_lbl)

        id_lbl = QLabel(carid)
        id_lbl.setFont(font(11))
        id_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        info_col.addWidget(id_lbl)

        col.addWidget(info)

        btn_container = QWidget()
        btn_container.setStyleSheet("background:transparent;border:none;")
        btn_row = QHBoxLayout(btn_container)
        btn_row.setContentsMargins(8, 0, 8, 0)
        btn_row.setSpacing(6)

        if not developer_added:
            uv_btn = self._mk_btn(
                t("car_list.get_uv_map"),
                lambda _, c=carid: self._get_uv_map(c),
                "primary",
                compact=True,
            )
            btn_row.addWidget(uv_btn)
        else:
            local_uvs = _get_local_uv_map_paths(carid)
            if local_uvs:
                uv_btn = self._mk_btn(
                    t("car_list.get_uv_map"),
                    lambda _, c=carid: self._get_local_uv_map(c),
                    "primary",
                    compact=True,
                )
                btn_row.addWidget(uv_btn)

        copy_btn = self._mk_btn(
            t("car_list.copy_id"),
            lambda _, c=carid: self._copy_carid(c),
            "secondary",
            compact=True,
        )
        btn_row.addWidget(copy_btn)

        col.addWidget(btn_container)

        return card

    def _mk_btn(self, text: str, cmd, style: str = "primary", compact: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(font(12, "bold"))
        btn.setFixedHeight(32 if compact else 36)
        if not compact:
            btn.setMinimumWidth(100)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setCursor(Qt.PointingHandCursor)
        if style == "primary":
            bg  = COLORS["accent"]
            bgh = COLORS["accent_hover"]
            tc  = COLORS["accent_text"]
            border = "none"
        else:
            bg  = COLORS["frame_bg"]
            bgh = COLORS["card_hover"]
            tc  = COLORS["text"]
            border = f"1px solid {COLORS['border']}"
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{bg};color:{tc};
                border-radius:10px;border:{border};
                padding:4px {"4px" if compact else "14px"};
            }}
            QPushButton:hover {{ background:{bgh}; }}
        """)
        btn.clicked.connect(cmd)
        return btn

    def _notify(self, msg: str, kind: str = "info", duration: int = 3000):
        print(f"[DEBUG] _notify() called")
        try:
            mw = self.window()
            if hasattr(mw, "show_notification"):
                mw.show_notification(msg, type=kind, duration=duration)
                return
        except Exception:
            pass
        print(f"[{kind.upper()}] {msg}")

    def _filter(self, text: str):
        print(f"[DEBUG] _filter: query={text!r}")
        q = text.lower()
        if not q:
            for card, _, _ in self._items:
                card.setVisible(True)
            self._relayout_all()
        else:
            matches    = [(card, cid, nm) for card, cid, nm in self._items
                          if q in cid.lower() or q in nm.lower()]
            non_matches = [(card, cid, nm) for card, cid, nm in self._items
                           if not (q in cid.lower() or q in nm.lower())]
            for card, _, _ in non_matches:
                card.setVisible(False)
            for card, _, _ in matches:
                card.setVisible(True)
            self._relayout_order(matches)
        self._scroll.verticalScrollBar().setValue(0)

    def _relayout_all(self):
        print(f"[DEBUG] _relayout_all() called")
        if self._view_mode == "modern":
            for card, _, _ in self._items:
                self._list_layout.removeWidget(card)
            for idx, (card, _, _) in enumerate(self._items):
                r, c = divmod(idx, self._modern_cols_current or 1)
                self._list_layout.addWidget(card, r, c)
        else:
            while self._list_layout.count() > 1:
                self._list_layout.takeAt(0)
            for i, (w, _, _) in enumerate(self._items):
                self._list_layout.insertWidget(i, w)

    def _relayout_order(self, ordered: list):
        print(f"[DEBUG] _relayout_order() called")
        if self._view_mode == "modern":
            for card, _, _ in self._items:
                self._list_layout.removeWidget(card)
            for idx, (card, _, _) in enumerate(ordered):
                r, c = divmod(idx, self._modern_cols_current or 1)
                self._list_layout.addWidget(card, r, c)
        else:
            while self._list_layout.count() > 1:
                self._list_layout.takeAt(0)
            for i, (w, _, _) in enumerate(ordered):
                self._list_layout.insertWidget(i, w)

    def refresh_ui(self):
        print(f"[DEBUG] refresh_ui() called")
        self._search.setPlaceholderText(t("car_list.search_placeholder"))
        self._btn_classic.setText(t("car_list.view_classic"))
        self._btn_modern.setText(t("car_list.view_modern"))
        self._items.clear()
        if hasattr(state, "carlist_items"):
            state.carlist_items.clear()
        self._rebuild_inner()
        self._populate()
        self._reflow_modern_grid()

    def refresh_vehicle_list(self):
        print(f"[DEBUG] refresh_vehicle_list: refreshing car list UI")
        self.refresh_ui()
        print(f"[DEBUG] CarListTab: Vehicle list refreshed with {len(self._items)} vehicles")

    def _copy_carid(self, carid: str):
        print(f"[DEBUG] _copy_carid: copying {carid!r} to clipboard")
        QApplication.clipboard().setText(carid)
        self._notify(t("car_list.copied_to_clipboard", carid=carid), "success", 2000)
        print(f"[DEBUG] Car ID '{carid}' copied to clipboard")

    def _get_local_uv_map(self, carid: str):
        """Serve a UV map that was copied locally during auto-import."""
        uv_paths = _get_local_uv_map_paths(carid)
        if not uv_paths:
            self._notify(
                t("car_list.no_uv_files_found", carid=carid), "error", 4000
            )
            return

        if len(uv_paths) == 1:
            selected = [(uv_paths[0], "")]
        else:
            # Reuse the existing multi-file selection dialog.
            found_files = [(p, p) for p in uv_paths]
            dlg = _UVSelectDialog(self, carid, found_files)
            if dlg.exec() != QDialog.Accepted or not dlg.selected_files:
                return
            selected = dlg.selected_files

        self._save_uv_files_local(selected)

    def _save_uv_files_local(self, selected: List[Tuple[str, str]]):
        """Save locally-stored UV maps to a user-chosen location."""
        if len(selected) == 1:
            src_path, _ = selected[0]
            ext  = os.path.splitext(src_path)[1]
            dest, _ = QFileDialog.getSaveFileName(
                self,
                t("car_list.save_uv_dialog"),
                os.path.basename(src_path),
                f"Image Files (*{ext});;All Files (*.*)",
            )
            if not dest:
                return
            try:
                import shutil as _shutil
                _shutil.copy2(src_path, dest)
                self._notify(t("car_list.uv_extracted"), "success", 3000)
            except Exception as e:
                self._notify(t("car_list.failed_save_uv", error=e), "error", 4000)
        else:
            dest_folder = QFileDialog.getExistingDirectory(
                self, t("car_list.save_uv_folder")
            )
            if not dest_folder:
                return
            import shutil as _shutil
            ok = 0
            for src_path, _ in selected:
                try:
                    _shutil.copy2(src_path, os.path.join(dest_folder, os.path.basename(src_path)))
                    ok += 1
                except Exception as e:
                    print(f"[DEBUG] Failed to copy {os.path.basename(src_path)}: {e}")
            self._notify(
                t("car_list.uv_extracted_count", ok=ok, total=len(selected)),
                "success", 3000,
            )

    def _get_uv_map(self, carid: str):
        try:
            from core.settings import get_beamng_install_path
        except ImportError:
            self._notify(t("car_list.import_error"), "error")
            return

        beamng_install = get_beamng_install_path()
        if not beamng_install:
            self._notify(
                t("car_list.beamng_not_configured") + " " + t("car_list.no_beamng_path"),
                "warning", 5000,
            )
            return

        beamng_path = os.path.join(beamng_install, "content", "vehicles")
        if not os.path.exists(beamng_path):
            self._notify(
                t("car_list.vehicles_folder_not_found", path=beamng_path), "error", 5000
            )
            return

        zip_file_path = os.path.join(beamng_path, f"{carid}.zip")
        if not os.path.exists(zip_file_path):
            self._notify(t("car_list.vehicle_zip_not_found", carid=carid), "error", 4000)
            return

        try:
            found_files = self._find_uv_files(carid, zip_file_path, beamng_path)
        except zipfile.BadZipFile:
            self._notify(t("car_list.invalid_zip", carid=carid), "error", 4000)
            return
        except Exception as e:
            self._notify(t("car_list.failed_search_zip", error=e), "error", 4000)
            import traceback; traceback.print_exc()
            return

        if not found_files:
            self._notify(t("car_list.no_uv_files_found", carid=carid), "error", 4000)
            print(f"[DEBUG] UV Map search failed: no UV files found in {zip_file_path}")
            return

        if len(found_files) == 1:
            selected = found_files
        else:
            dlg = _UVSelectDialog(self, carid, found_files)
            if dlg.exec() != QDialog.Accepted or not dlg.selected_files:
                print("[DEBUG] User cancelled UV map selection")
                return
            selected = dlg.selected_files

        self._save_uv_files(selected)

    def _find_uv_files(
        self,
        carid: str,
        zip_file_path: str,
        beamng_path: str,
    ) -> List[Tuple[str, str]]:
        found: List[Tuple[str, str]] = []
        search_common = False
        common_search_dirs: List[str] = []

        with zipfile.ZipFile(zip_file_path, "r") as z:
            for fp in z.namelist():
                if "ambulance" in os.path.basename(fp).lower():
                    search_common = True
                    common_search_dirs.append("vehicles/common/pickup/")
                    break

        with zipfile.ZipFile(zip_file_path, "r") as z:
            target_dir = f"vehicles/{carid}/"
            for fp in z.namelist():
                if fp.startswith(target_dir) and self._is_uv_file(fp):
                    found.append((fp, zip_file_path))

        if search_common:
            common_zip = os.path.join(beamng_path, "common.zip")
            if os.path.exists(common_zip):
                print("[DEBUG] Also searching in common.zip for ambulance UV maps…")
                with zipfile.ZipFile(common_zip, "r") as z:
                    for search_dir in common_search_dirs:
                        for fp in z.namelist():
                            if fp.startswith(search_dir) and self._is_uv_file(fp):
                                found.append((fp, common_zip))

        return found

    @staticmethod
    def _is_uv_file(file_path: str) -> bool:
        fn = os.path.basename(file_path).lower()
        if not fn.endswith((".dds", ".png", ".jpg", ".jpeg")):
            return False
        has_uv = (
            "uv" in fn
            or "uvmap" in fn
            or "uv1_layout" in fn
            or "uv_layout" in fn
        )
        if not has_uv:
            return False
        if "color" in fn:
            return False
        if re.search(r"_skin_\w+_uv\d+\.", fn):
            return False
        return True

    def _save_uv_files(self, selected: List[Tuple[str, str]]):
        print(f"[DEBUG] _save_uv_files: saving {len(selected)} UV file(s)")
        if len(selected) == 1:
            file_path, source_zip = selected[0]
            ext = os.path.splitext(file_path)[1]
            dest, _ = QFileDialog.getSaveFileName(
                self,
                t("car_list.save_uv_dialog"),
                os.path.basename(file_path),
                f"Image Files (*{ext});;All Files (*.*)",
            )
            if not dest:
                return
            try:
                with zipfile.ZipFile(source_zip, "r") as z:
                    with z.open(file_path) as src, open(dest, "wb") as dst:
                        dst.write(src.read())
                self._notify(t("car_list.uv_extracted"), "success", 3000)
                print(f"[DEBUG] UV Map extracted: {file_path} → {dest}")
            except Exception as e:
                self._notify(t("car_list.failed_save_uv", error=e), "error", 4000)
        else:
            dest_folder = QFileDialog.getExistingDirectory(
                self, t("car_list.save_uv_folder")
            )
            if not dest_folder:
                return
            ok = 0
            for file_path, source_zip in selected:
                filename = os.path.basename(file_path)
                dest = os.path.join(dest_folder, filename)
                try:
                    with zipfile.ZipFile(source_zip, "r") as z:
                        with z.open(file_path) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                    ok += 1
                    print(f"[DEBUG] UV Map extracted: {filename} → {dest}")
                except Exception as e:
                    print(f"[DEBUG] Failed to extract {filename}: {e}")
            self._notify(
                t("car_list.uv_extracted_count", ok=ok, total=len(selected)),
                "success", 3000,
            )

