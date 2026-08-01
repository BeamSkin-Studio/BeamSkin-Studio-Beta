from __future__ import annotations
import os
from typing import Optional

from PySide6.QtCore    import Qt, QTimer, QPoint, QSize
from PySide6.QtGui     import QPixmap, QCursor
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QApplication,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.state   import state

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return key


class HoverPreviewManager:

    def __init__(self, app_widget: QWidget, preview_overlay: QFrame):
        print(f"[DEBUG] __init__() called")
        self.app             = app_widget
        self.overlay         = preview_overlay
        self._timer: Optional[QTimer] = None
        self._current_carid: Optional[str] = None


    def show_hover_preview(self, carid: str, image_path: Optional[str] = None,
                            display_name: Optional[str] = None) -> None:
        print(f"[DEBUG] show_hover_preview: carid={carid!r} path={image_path!r} display_name={display_name!r}")

        if not image_path or not os.path.exists(image_path):
            image_path = os.path.join("gui", "images", "vehicles", carid, "default.jpg")
        if not os.path.exists(image_path):
            fallback = os.path.join("gui", "images", "common",
                                    "imagepreview", "MissingTexture.jpg")
            if os.path.exists(fallback):
                image_path = fallback
            else:
                return


        self._clear_overlay()


        ow, oh = 300, 240
        self.overlay.setFixedSize(ow, oh)

        inner = QVBoxLayout(self.overlay)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(6)

        hdr = QFrame()
        hdr.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['accent']};
                border-radius: 6px;
            }}
        """)
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(8, 4, 8, 4)

        vehicle_name = display_name or state.get_vehicle_name(carid)
        hdr_lbl = QLabel(f"{vehicle_name}  |  {carid}")
        hdr_lbl.setFont(font(12, "bold"))
        hdr_lbl.setStyleSheet(
            f"color:{COLORS['accent_text']};background:transparent;"
        )
        hdr_row.addWidget(hdr_lbl)
        inner.addWidget(hdr)


        px = QPixmap(image_path).scaled(
            280, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        img_lbl = QLabel()
        img_lbl.setPixmap(px)
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setStyleSheet("background:transparent;border:none;")
        inner.addWidget(img_lbl)

        try:
            cursor = self.app.mapFromGlobal(QCursor.pos())
        except Exception:
            cursor = QPoint(0, 0)

        x = cursor.x() + 20
        y = cursor.y() + 10
        if x + ow > self.app.width():
            x = cursor.x() - ow - 20
        if y + oh > self.app.height():
            y = cursor.y() - oh - 10
        x = max(10, x)
        y = max(10, y)

        self.overlay.move(x, y)
        self.overlay.raise_()
        self.overlay.show()


        fade_in(self.overlay, 150)

    def hide_hover_preview(self, force: bool = False) -> None:
        print(f"[DEBUG] hide_hover_preview: hiding preview overlay")
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._current_carid = None
        self.overlay.hide()
        self._clear_overlay()

    def _clear_overlay(self) -> None:
        print(f"[DEBUG] _clear_overlay() called")
        old_layout = self.overlay.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.hide()
                    w.setParent(None)
            _tmp = QWidget()
            _tmp.setLayout(old_layout)


        for child in list(self.overlay.findChildren(QWidget)):
            child.hide()
            child.setParent(None)

    def schedule_hover_preview(self, carid: str, widget: QWidget,
                               get_image_path=None, get_display_name=None) -> None:
        print(f"[DEBUG] schedule_hover_preview() called")
        if self._timer:
            self._timer.stop()
        self._current_carid = carid

        def _show():
            if self._current_carid == carid:
                img  = get_image_path() if callable(get_image_path) else None
                name = get_display_name() if callable(get_display_name) else None
                self.show_hover_preview(carid, img, display_name=name)

        self._timer = QTimer(self.app)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(_show)
        self._timer.start(500)

    def setup_robust_hover(self, widget: QWidget, carid: str,
                           get_image_path=None, get_display_name=None) -> None:
        print(f"[DEBUG] setup_robust_hover() called")
        def _enter(event, w=widget, c=carid):
            self.schedule_hover_preview(
                c, w, get_image_path=get_image_path, get_display_name=get_display_name
            )

        def _leave(event):
            self.hide_hover_preview()

        widget.enterEvent = _enter
        widget.leaveEvent = _leave
        for child in widget.findChildren(QWidget):
            child.enterEvent = _enter
            child.leaveEvent = _leave


def create_preview_overlay(parent: QWidget) -> QFrame:
    overlay = QFrame(parent)
    overlay.setStyleSheet(f"""
        QFrame {{
            background-color: {COLORS['card_bg']};
            border-radius: 10px;
            border: 2px solid {COLORS['accent']};
        }}
    """)


    drop_shadow(overlay, 20, (0, 6))
    overlay.hide()
    return overlay


