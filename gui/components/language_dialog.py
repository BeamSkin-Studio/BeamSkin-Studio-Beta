from __future__ import annotations
import sys as _sys
from typing import Callable, Optional

from PySide6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QWidget, QApplication,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtGui     import QShowEvent

from gui.theme   import COLORS, font, drop_shadow
from gui.widgets import AnimButton
from gui.icon_helper import set_window_icon

try:
    from core.localization import (
        get_available_languages, set_language, get_localization, t,
    )
except ImportError as e:
    print(f"[DEBUG] language_dialog.py: localization import failed ({e}), using fallbacks")
    def get_available_languages():
        return {"en": {"name": "English", "native": "English", "flag": "🇬🇧"}}
    def set_language(lang): return True
    def get_localization(): return None
    def t(key, **kw): return kw.get("default", key)


def _platform_supports_transparency() -> bool:
    if _sys.platform in ("win32", "darwin"):
        return True
    try:
        app = QApplication.instance()
        platform_name = app.platformName().lower() if app else ""
        if app and "wayland" in platform_name:
            return True
        import subprocess, os
        display = os.environ.get("DISPLAY", ":0")
        screen_num = display.split(".")[-1] if "." in display else "0"
        result = subprocess.run(
            ["xprop", "-root", f"_NET_WM_CM_S{screen_num}"],
            capture_output=True, text=True, timeout=1,
        )
        has_compositor = "window id" in result.stdout.lower()
        print(f"[DEBUG] _platform_supports_transparency: display={display!r} compositor_present={has_compositor}")
        return has_compositor
    except Exception as e:
        print(f"[DEBUG] _platform_supports_transparency: probe failed ({e}), returning False")
        return False


class _LangRow(QFrame):
    selected = Signal(str)

    def __init__(self, lang_code: str, info: dict, is_selected: bool, parent=None):
        super().__init__(parent)
        self.lang_code = lang_code
        self._selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(62)
        self._apply(is_selected)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(14)

        flag_lbl = QLabel(info.get("flag", "🌐"))
        flag_lbl.setFont(font(28))
        flag_lbl.setStyleSheet("background:transparent;border:none;")
        row.addWidget(flag_lbl)

        names = QVBoxLayout()
        names.setSpacing(2)
        native_name = info.get("native", info.get("name", lang_code))
        native_lbl = QLabel(native_name)
        native_lbl.setFont(font(15, "bold"))
        native_lbl.setStyleSheet(
            f"color:{COLORS['accent_text'] if is_selected else COLORS['text']};"
            "background:transparent;border:none;"
        )
        names.addWidget(native_lbl)

        if info.get("native") != info.get("name"):
            eng_name = info.get("name", "")
            eng_lbl = QLabel(eng_name)
            eng_lbl.setFont(font(11))
            eng_lbl.setStyleSheet(
                f"color:{COLORS['accent_text'] if is_selected else COLORS['text_secondary']};"
                "background:transparent;border:none;"
            )
            names.addWidget(eng_lbl)

        row.addLayout(names, 1)

        if is_selected:
            check = QLabel("✓")
            check.setFont(font(20, "bold"))
            check.setStyleSheet(
                f"color:{COLORS['accent_text']};background:transparent;border:none;"
            )
            row.addWidget(check)

    def _apply(self, active: bool):
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['accent']};
                    border-radius: 10px;
                    border: none;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['card_bg']};
                    border-radius: 10px;
                    border: 1px solid {COLORS['border']};
                }}
                QFrame:hover {{
                    background-color: {COLORS['card_hover']};
                    border-color: {COLORS['accent']};
                }}
            """)

    def mousePressEvent(self, _event):
        self.selected.emit(self.lang_code)


class LanguageSelectionDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        colors: dict,
        on_complete: Optional[Callable] = None,
    ):
        use_transparency = _platform_supports_transparency()

        flags = Qt.Dialog | Qt.FramelessWindowHint

        super().__init__(parent, flags)
        set_window_icon(self)
        self.setModal(True)
        self.setFixedSize(680, 580)

        if use_transparency:
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setStyleSheet("background:transparent;")
        else:
            self.setStyleSheet(f"background:{COLORS['frame_bg']};border-radius:20px;")

        self._colors      = colors
        self.on_complete  = on_complete
        self._fade_done   = False

        loc = get_localization()
        self.selected_language = loc.current_language if loc else "en"

        if parent:
            pg = parent.geometry()
            x = pg.x() + (pg.width()  - 680) // 2
            y = pg.y() + (pg.height() - 580) // 2
            self.move(x, y)

        self._build()


    def _build(self):
        self._card = QFrame(self)
        self._card.setGeometry(0, 0, 680, 580)
        self._card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['frame_bg']};
                border-radius: 20px;
                border: 1px solid {COLORS['border']};
            }}
        """)

        root = QVBoxLayout(self._card)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        hdr = QVBoxLayout()
        hdr.setSpacing(6)
        globe = QLabel("🌍")
        globe.setFont(font(52))
        globe.setAlignment(Qt.AlignCenter)
        globe.setStyleSheet("background:transparent;border:none;")
        hdr.addWidget(globe)

        title_text = t("language_selection.title", default="Select Your Language")
        title = QLabel(title_text)
        title.setFont(font(24, "bold"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        hdr.addWidget(title)

        sub_text = t("language_selection.subtitle",
                     default="Choose your preferred language for BeamSkin Studio")
        sub = QLabel(sub_text)
        sub.setFont(font(13))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        hdr.addWidget(sub)
        root.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollArea > QWidget > QWidget {{ background:transparent; }}
        """)
        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        self._list_layout.setSpacing(6)
        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, 1)

        self._populate_list()

        continue_text = t("language_selection.continue", default="Continue →")
        self._continue_btn = AnimButton(
            continue_text,
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=14, bold=True, padding="12px 32px",
        )
        self._continue_btn.setMinimumHeight(46)
        self._continue_btn.clicked.connect(self._on_continue)
        root.addWidget(self._continue_btn)


    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)

        if self._fade_done:
            return
        self._fade_done = True

        fx = QGraphicsOpacityEffect(self._card)
        fx.setOpacity(0.0)
        self._card.setGraphicsEffect(fx)

        anim = QPropertyAnimation(fx, b"opacity", self._card)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def _on_done():
            self._card.setGraphicsEffect(None)
            drop_shadow(self._card, 36, (0, 10))

        anim.finished.connect(_on_done)
        anim.start(QPropertyAnimation.DeleteWhenStopped)


    def _populate_list(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        langs = get_available_languages()
        sorted_langs = sorted(langs.items(), key=lambda x: x[1].get("name", x[0]))
        for code, info in sorted_langs:
            is_sel = code == self.selected_language
            row = _LangRow(code, info, is_sel)
            row.selected.connect(self._on_select)
            self._list_layout.addWidget(row)
        self._list_layout.addStretch()

    def _on_select(self, code: str):
        print(f"[DEBUG] LanguageSelectionDialog._on_select: code={code!r}")
        self.selected_language = code
        set_language(code)
        self._populate_list()

    def _on_continue(self):
        if self.selected_language:
            set_language(self.selected_language)
        if self.on_complete:
            self.on_complete(self.selected_language)
        self.accept()

    def open(self) -> str:
        self.exec()
        return self.selected_language


def show_language_selection(
    parent: QWidget,
    colors: dict,
    on_complete: Optional[Callable] = None,
) -> str:
    d = LanguageSelectionDialog(parent, colors, on_complete)
    return d.open()
