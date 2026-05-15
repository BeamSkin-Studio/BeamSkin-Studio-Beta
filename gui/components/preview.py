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
    """Manages a floating preview panel inside the main window."""

    def __init__(self, app_widget: QWidget, preview_overlay: QFrame):
        print(f"[DEBUG] __init__() called")
        self.app             = app_widget
        self.overlay         = preview_overlay
        self._timer: Optional[QTimer] = None
        self._current_carid: Optional[str] = None


    def show_hover_preview(self, carid: str, image_path: Optional[str] = None) -> None:
        print(f"[DEBUG] show_hover_preview: carid={carid!r} path={image_path!r}")
        # Use the supplied path if valid; otherwise fall back to default → MissingTexture
        if not image_path or not os.path.exists(image_path):
            image_path = os.path.join("gui", "images", "vehicles", carid, "default.jpg")
        if not os.path.exists(image_path):
            fallback = os.path.join("gui", "images", "common",
                                    "imagepreview", "MissingTexture.jpg")
            if os.path.exists(fallback):
                image_path = fallback
            else:
                return

        # ── Tear down the old layout completely before building a new one ── #
        # Creating a new QVBoxLayout(self.overlay) every call stacks layouts
        # on top of each other.  Instead we delete all children directly.
        self._clear_overlay()

        # header strip — parented to overlay directly (no layout yet)
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

        vehicle_name = state.get_vehicle_name(carid)
        hdr_lbl = QLabel(f"{vehicle_name}  |  {carid}")
        hdr_lbl.setFont(font(12, "bold"))
        hdr_lbl.setStyleSheet(
            f"color:{COLORS['accent_text']};background:transparent;"
        )
        hdr_row.addWidget(hdr_lbl)
        inner.addWidget(hdr)

        # image
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
        # overlay already has drop_shadow (set at creation), so fade_in
        # will skip the opacity animation — that's fine; it just appears.
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
        """Remove all child widgets and detach the current layout.

        Strategy
        --------
        1.  Walk the existing layout, hide + reparent each widget to None so
            Qt drops the reference immediately (deleteLater is deferred and
            can race with findChildren below).
        2.  Transfer the now-empty layout to a throwaway QWidget so the
            overlay's internal layout pointer is cleared.  The throwaway goes
            out of scope and takes the layout with it.
        3.  Sweep findChildren for anything that was not in the layout (e.g.
            widgets parented directly to the overlay).  At this point step 1
            has already hidden + reparented the layout-owned widgets, so
            findChildren only returns genuine stragglers.
        """
        print(f"[DEBUG] _clear_overlay() called")
        old_layout = self.overlay.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.hide()
                    w.setParent(None)   # immediate ref-drop; no deleteLater race
            _tmp = QWidget()
            _tmp.setLayout(old_layout)  # Qt reparents layout → overlay ptr cleared
            # _tmp leaves scope here → layout + empty items collected

        for child in list(self.overlay.findChildren(QWidget)):
            child.hide()
            child.setParent(None)

    def schedule_hover_preview(self, carid: str, widget: QWidget,
                               get_image_path=None) -> None:
        print(f"[DEBUG] schedule_hover_preview() called")
        if self._timer:
            self._timer.stop()
        self._current_carid = carid

        def _show():
            if self._current_carid == carid:
                img = get_image_path() if callable(get_image_path) else None
                self.show_hover_preview(carid, img)

        self._timer = QTimer(self.app)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(_show)
        self._timer.start(500)

    def setup_robust_hover(self, widget: QWidget, carid: str,
                           get_image_path=None) -> None:
        print(f"[DEBUG] setup_robust_hover() called")
        """Install enter/leave events recursively on widget and all children.

        ``get_image_path`` — optional zero-argument callable that returns the
        image path to show.  It is called at enter time so it always reflects
        whichever variant is currently displayed on the card.
        """
        def _enter(event, w=widget, c=carid):
            self.schedule_hover_preview(c, w, get_image_path=get_image_path)

        def _leave(event):
            self.hide_hover_preview()

        widget.enterEvent = _enter
        widget.leaveEvent = _leave
        for child in widget.findChildren(QWidget):
            child.enterEvent = _enter
            child.leaveEvent = _leave


def create_preview_overlay(parent: QWidget) -> QFrame:
    """Factory — call once from main window."""
    overlay = QFrame(parent)
    overlay.setStyleSheet(f"""
        QFrame {{
            background-color: {COLORS['card_bg']};
            border-radius: 10px;
            border: 2px solid {COLORS['accent']};
        }}
    """)
    # Apply shadow once at creation.  Later calls to fade_in() on this widget
    # will detect the existing effect and skip the opacity animation — that is
    # intentional and safe.
    drop_shadow(overlay, 20, (0, 6))
    overlay.hide()
    return overlay


