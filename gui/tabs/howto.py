from __future__ import annotations
import base64
import html
import re
from pathlib import Path
from typing import List, Tuple, Optional

from PySide6.QtCore    import Qt, QTimer, QUrl, Signal
from PySide6.QtGui     import QTextCursor, QPixmap, QPainter
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QTextEdit, QApplication,
    QDialog, QGraphicsView, QGraphicsScene,
)

import gui  # noqa: F401  (imported for gui.__file__, used to locate images/guide)
from gui.theme   import COLORS, font

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return key


_IMG_PATTERN = re.compile(
    r"\{\{img:(?P<file>[^{}|]+)(?:\|(?P<width>\d+))?(?:\|(?P<caption>[^{}]*))?\}\}"
)
_DEFAULT_IMG_WIDTH = 480
_IMG_HREF_SCHEME = "guideimg:"


class _GuideTextEdit(QTextEdit):
    imageClicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        anchor = self.anchorAt(event.pos())
        self.viewport().setCursor(Qt.PointingHandCursor if anchor else Qt.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        anchor = self.anchorAt(event.pos())
        if anchor.startswith(_IMG_HREF_SCHEME):
            self.imageClicked.emit(anchor[len(_IMG_HREF_SCHEME):])
            return
        super().mouseReleaseEvent(event)


class _ZoomPanView(QGraphicsView):
    _MIN_ZOOM_VS_FIT = 1.0
    _MAX_ZOOM_VS_FIT = 8.0
    _WHEEL_STEP = 1.15

    def __init__(self, pixmap: QPixmap, parent: Optional[QWidget] = None):
        super().__init__(parent)
        scene = QGraphicsScene(self)
        self._item = scene.addPixmap(pixmap)
        self.setScene(scene)
        scene.setSceneRect(self._item.boundingRect())

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setStyleSheet(f"background:{COLORS['app_bg']}; border:none;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCursor(Qt.OpenHandCursor)

        self._fit_scale = 1.0
        self._press_pos = None
        self._dragged = False

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_to_window()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_zoom_ratio() <= self._MIN_ZOOM_VS_FIT + 1e-6:
            self._fit_to_window()

    def _fit_to_window(self):
        self.fitInView(self._item, Qt.KeepAspectRatio)
        self._fit_scale = self.transform().m11()

    def _current_zoom_ratio(self) -> float:
        if self._fit_scale <= 0:
            return 1.0
        return self.transform().m11() / self._fit_scale

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = self._WHEEL_STEP if delta > 0 else 1.0 / self._WHEEL_STEP
        new_ratio = self._current_zoom_ratio() * factor
        new_ratio = max(self._MIN_ZOOM_VS_FIT, min(self._MAX_ZOOM_VS_FIT, new_ratio))
        factor = new_ratio / self._current_zoom_ratio()
        if abs(factor - 1.0) > 1e-6:
            self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
            self._dragged = False
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is not None and not self._dragged:
            if (event.pos() - self._press_pos).manhattanLength() > 4:
                self._dragged = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.OpenHandCursor)
            if not self._dragged:
                window = self.window()
                if window is not None:
                    window.close()
            self._press_pos = None
            self._dragged = False


class _ImageViewerDialog(QDialog):
    def __init__(self, image_path: Path, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(image_path.name)
        self.setStyleSheet(f"background-color:{COLORS['app_bg']};")

        pixmap = QPixmap(str(image_path))

        view = _ZoomPanView(pixmap, self)

        info = QLabel(f"{image_path.name}  •  {pixmap.width()}×{pixmap.height()}px  "
                       f"•  drag to pan  •  scroll to zoom  •  click or press Esc to close")
        info.setFont(font(11))
        info.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;")
        info.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(view, 1)
        layout.addWidget(info)

        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        max_w = int(avail.width() * 0.9) if avail else 1200
        max_h = int(avail.height() * 0.9) if avail else 800
        target_w = min(max(pixmap.width() + 48, 640), max_w)
        target_h = min(max(pixmap.height() + 90, 480), max_h)
        self.resize(target_w, target_h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


class HowToTab(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet(f"background-color:{COLORS['app_bg']};")
        self._chapter_buttons: List[Tuple[QPushButton, str]] = []
        self._view_all_btn:    Optional[QPushButton]         = None
        self._content:         Optional[QTextEdit]           = None
        self._search:          Optional[QLineEdit]           = None

        self._images_dir = Path(gui.__file__).resolve().parent / "images" / "guide"
        if not self._images_dir.is_dir():
            print(f"[DEBUG] Guide images folder not found: {self._images_dir}")

        self._setup_ui()
        QTimer.singleShot(50, self.load_all_chapters)


    def _get_chapters(self) -> dict:
        return {
            "getting_started": {
                "icon": "🚀",
                "title":   t("howto.chapter_getting_started"),
                "content": t("howto_content.getting_started_content"),
            },
            "skin_creation": {
                "icon": "🎨",
                "title":   t("howto.chapter_skin_creation"),
                "content": t("howto_content.skin_creation_content"),
            },
            "skin_color": {
                "icon": "🦚",
                "title":   t("howto.chapter_skin_color"),
                "content": t("howto_content.skin_color_content"),
            },
            "skin_reflective": {
                "icon": "🪞",
                "title":   t("howto.chapter_skin_reflective"),
                "content": t("howto_content.skin_reflective_content"),
            },
            "project": {
                "icon": "⚙️",
                "title":   t("howto.chapter_project"),
                "content": t("howto_content.project_content"),
            },
            "car_list": {
                "icon": "🚗",
                "title":   t("howto.chapter_car_list"),
                "content": t("howto_content.car_list_content"),
            },
            "add_vehicle": {
                "icon": "➕",
                "title":   t("howto.chapter_add_vehicle"),
                "content": t("howto_content.add_vehicle_content"),
            },
            "troubleshooting": {
                "icon": "🔍",
                "title":   t("howto.chapter_troubleshooting"),
                "content": t("howto_content.troubleshooting_content"),
            },
            "advanced": {
                "icon": "⚡",
                "title":   t("howto.chapter_advanced"),
                "content": t("howto_content.advanced_content"),
            },
            "faq": {
                "icon": "❓",
                "title":   t("howto.chapter_faq"),
                "content": t("howto_content.faq_content"),
            },
        }


    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr = QFrame()
        hdr.setFixedHeight(80)
        hdr.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['frame_bg']};
                border-radius:12px;
                border:1px solid {COLORS['border']};
            }}
        """)
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(20, 0, 20, 0)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        self._page_title_lbl = QLabel(t("howto.page_title"))
        self._page_title_lbl.setFont(font(22, "bold"))
        self._page_title_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        text_col.addWidget(self._page_title_lbl)

        self._page_sub_lbl = QLabel(t("howto.page_subtitle"))
        self._page_sub_lbl.setFont(font(12))
        self._page_sub_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        text_col.addWidget(self._page_sub_lbl)
        hdr_row.addLayout(text_col, 1)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        si = QLabel("🔍")
        si.setFont(font(16))
        si.setStyleSheet("background:transparent;border:none;")
        search_row.addWidget(si)

        self._search = QLineEdit()
        self._search.setPlaceholderText(t("howto.search_placeholder"))
        self._search.setFixedWidth(240)
        self._search.setFixedHeight(34)
        self._search.setFont(font(12))
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:5px 10px;
            }}
            QLineEdit:focus {{ border-color:{COLORS.get('border_focus', COLORS['accent'])}; }}
        """)
        self._search.returnPressed.connect(self._search_content)
        search_row.addWidget(self._search)
        hdr_row.addLayout(search_row)
        root.addWidget(hdr)

        nav_scroll = QScrollArea()
        nav_scroll.setFixedHeight(60)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setStyleSheet(f"""
            QScrollArea {{ background:{COLORS['frame_bg']};
                           border-radius:12px;
                           border:1px solid {COLORS['border']}; }}
            QScrollArea > QWidget > QWidget {{ background:{COLORS['frame_bg']}; }}
        """)

        nav_inner = QWidget()
        nav_inner.setStyleSheet(f"background:{COLORS['frame_bg']};")
        nav_row = QHBoxLayout(nav_inner)
        nav_row.setContentsMargins(12, 0, 12, 0)
        nav_row.setSpacing(4)

        self._view_all_btn = self._nav_btn(
            f"📖  {t('howto.view_all')}", active=True
        )
        self._view_all_btn.clicked.connect(self.load_all_chapters)
        nav_row.addWidget(self._view_all_btn)

        self._chapter_buttons = []
        for key, data in self._get_chapters().items():
            btn = self._nav_btn(f"{data['icon']} {data['title']}")
            btn.clicked.connect(
                lambda checked=False, k=key: self.load_chapter(k)
            )
            nav_row.addWidget(btn)
            self._chapter_buttons.append((btn, key))

        nav_row.addStretch()
        nav_scroll.setWidget(nav_inner)
        root.addWidget(nav_scroll)

        content_frame = QFrame()
        content_frame.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['frame_bg']};
                border-radius:12px;
                border:1px solid {COLORS['border']};
            }}
        """)
        cf_layout = QVBoxLayout(content_frame)
        cf_layout.setContentsMargins(16, 12, 16, 12)

        self._content = _GuideTextEdit()
        self._content.setReadOnly(True)
        self._content.setFont(font(13))
        self._content.setStyleSheet(f"""
            QTextEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:none;
                font-size:13px;
                line-height:1.6;
            }}
        """)
        self._content.imageClicked.connect(self._show_full_image)
        cf_layout.addWidget(self._content)
        root.addWidget(content_frame, 1)


    def _nav_btn(self, text: str, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(font(12, "bold" if active else "normal"))
        btn.setFixedHeight(38)
        btn.setCursor(Qt.PointingHandCursor)
        self._style_nav_btn(btn, active)
        return btn

    def _style_nav_btn(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{COLORS['accent']};
                    color:{COLORS['accent_text']};
                    border-radius:8px;border:none;
                    padding:6px 14px;font-size:12px;font-weight:bold;
                }}
                QPushButton:hover {{ background:{COLORS['accent_hover']}; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{COLORS['card_bg']};color:{COLORS['text']};
                    border-radius:8px;border:1px solid {COLORS['border']};
                    padding:6px 14px;font-size:12px;
                }}
                QPushButton:hover {{
                    background:{COLORS['card_hover']};
                    border-color:{COLORS['accent']};
                }}
            """)


    def _resolve_image_path(self, filename: str) -> Optional[Path]:
        try:
            candidate = (self._images_dir / filename.strip()).resolve()
            candidate.relative_to(self._images_dir.resolve())
        except (ValueError, RuntimeError, OSError) as _exc:
            print(f"[WARNING] _resolve_image_path: {type(_exc).__name__}: {_exc}")
            return None
        return candidate if candidate.is_file() else None

    @staticmethod
    def _escape_html_chunk(chunk: str) -> str:
        return html.escape(chunk).replace("\n", "<br>")

    def _image_cell_html(self, filename: str, width: Optional[str], caption: str) -> str:
        path = self._resolve_image_path(filename)
        if path is None:
            print(f"[DEBUG] Guide image not found or invalid: {filename!r}")
            return (
                f'<span style="color:#e05555;">'
                f'⚠ Missing image: {html.escape(filename)}</span>'
            )
        url = QUrl.fromLocalFile(str(path)).toString()
        href = _IMG_HREF_SCHEME + base64.urlsafe_b64encode(
            str(path).encode("utf-8")
        ).decode("ascii")
        width_px = width or str(_DEFAULT_IMG_WIDTH)
        caption_html = (
            f'<br><span style="color:{COLORS["text_secondary"]};font-size:11px;">'
            f'{html.escape(caption)}</span>'
            if caption else ""
        )
        hint_html = (
            f'<br><span style="color:{COLORS["text_secondary"]};font-size:10px;">'
            f'🔍 Click to view full resolution</span>'
        )
        return (
            f'<a href="{href}" style="text-decoration:none;">'
            f'<img src="{url}" width="{width_px}"></a>'
            f'{caption_html}{hint_html}'
        )

    def _image_group_html(self, images: List[Tuple[str, Optional[str], str]]) -> str:
        cells = "".join(
            f'<td style="padding:0 16px 0 0;">{self._image_cell_html(f, w, c)}</td>'
            for f, w, c in images
        )
        return (
            f'<br><table align="left" cellspacing="0" cellpadding="0" '
            f'style="margin:8px 0;"><tr>{cells}</tr></table><br>'
        )

    def _show_full_image(self, encoded_path: str):
        try:
            raw = base64.urlsafe_b64decode(encoded_path.encode("ascii"))
            path = Path(raw.decode("utf-8"))
        except Exception:
            print(f"[DEBUG] Failed to decode guide image link: {encoded_path!r}")
            return
        if not path.is_file():
            print(f"[DEBUG] Guide image no longer exists on disk: {path}")
            return
        print(f"[DEBUG] Opening full-resolution viewer for: {path}")
        _ImageViewerDialog(path, self).exec()

    def _render_guide_html(self, text: str) -> str:
        parts: List[str] = []
        pos = 0
        pending_group: List[Tuple[str, Optional[str], str]] = []

        def flush_group():
            if pending_group:
                parts.append(self._image_group_html(list(pending_group)))
                pending_group.clear()

        for m in _IMG_PATTERN.finditer(text):
            between = text[pos:m.start()]
            if pending_group and between.strip() == "":
                pass
            else:
                flush_group()
                parts.append(self._escape_html_chunk(between))
            pending_group.append((
                m.group("file"), m.group("width"), (m.group("caption") or "").strip()
            ))
            pos = m.end()

        flush_group()
        parts.append(self._escape_html_chunk(text[pos:]))
        return (
            f'<div style="color:{COLORS["text"]};font-size:13px;">'
            + "".join(parts)
            + "</div>"
        )

    def _set_text_scroll_top(self, text: str):
        if _IMG_PATTERN.search(text):
            self._content.setHtml(self._render_guide_html(text))
        else:
            self._content.setPlainText(text)
        QApplication.processEvents()
        self._content.moveCursor(QTextCursor.Start)
        self._content.verticalScrollBar().setValue(0)


    def load_chapter(self, chapter_key: str):
        print(f"[DEBUG] load_chapter: {chapter_key!r}")
        chapters = self._get_chapters()
        if chapter_key not in chapters:
            return
        data = chapters[chapter_key]
        self._set_text_scroll_top(
            f"{data['icon']} {data['title']}\n"
            + "═" * 60 + "\n\n"
            + data["content"]
        )

        self._style_nav_btn(self._view_all_btn, False)
        for btn, key in self._chapter_buttons:
            self._style_nav_btn(btn, key == chapter_key)

        print(f"[DEBUG] Loaded chapter: {data['title']}")

    def load_all_chapters(self):
        print("[DEBUG] load_all_chapters: rendering full doc view")
        chapters = self._get_chapters()

        intro = (
            t("howto.welcome_title")         + "\n\n"
            + t("howto.welcome_intro")       + "\n\n"
        )
        for key in ("howto.quick_nav_title", "howto.quick_nav_chapters",
                    "howto.quick_nav_search", "howto.quick_nav_walkthrough"):
            line = t(key)
            if line != key:
                intro += line + "\n"
        lets = t("howto.lets_start")
        if lets != "howto.lets_start":
            intro += "\n" + lets + "\n"
        intro += "\n" + "═" * 60 + "\n\n"

        parts = [intro]
        for data in chapters.values():
            parts.append(
                f"{data['icon']} {data['title']}\n"
                + "─" * 60 + "\n"
                + data["content"]
                + "\n\n"
            )
        self._set_text_scroll_top("".join(parts))

        self._style_nav_btn(self._view_all_btn, True)
        for btn, _ in self._chapter_buttons:
            self._style_nav_btn(btn, False)

        print("[DEBUG] Loaded all chapters")

    def _search_content(self):
        print(f"[DEBUG] _search_content: query={self._search.text()!r}")
        term = self._search.text().lower().strip()
        if not term:
            self.load_all_chapters()
            return
        chapters = self._get_chapters()
        results = [
            (k, d) for k, d in chapters.items()
            if term in d["content"].lower() or term in d["title"].lower()
        ]
        if results:
            text = f"Search results for: '{term}'\n" + "═" * 60 + "\n\n"
            for _, data in results:
                text += (f"{data['icon']} {data['title']}\n"
                         f"─────\n{data['content']}\n\n")
        else:
            text = (f"No results found for '{term}'.\n\n"
                    f"Try a different keyword.")
        self._set_text_scroll_top(text)


    def refresh_ui(self):
        self._page_title_lbl.setText(t("howto.page_title"))
        self._page_sub_lbl.setText(t("howto.page_subtitle"))
        if self._search:
            self._search.setPlaceholderText(t("howto.search_placeholder"))
        chapters = self._get_chapters()
        if self._view_all_btn:
            self._view_all_btn.setText(f"📖  {t('howto.view_all')}")
        for btn, key in self._chapter_buttons:
            if key in chapters:
                data = chapters[key]
                btn.setText(f"{data['icon']} {data['title']}")

        if self._content is not None:
            self.load_all_chapters()
