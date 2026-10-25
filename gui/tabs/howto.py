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
    QDialog, QGraphicsView, QGraphicsScene, QSizePolicy,
)

import gui
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
        info.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;padding:4px 0 0 0;"
        )
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


_SIDEBAR_WIDTH = 252


def _scrollbar_qss() -> str:
    return f"""
        QScrollBar:vertical {{
            background:transparent; width:10px; margin:2px;
        }}
        QScrollBar::handle:vertical {{
            background:{COLORS['card_hover']}; border-radius:4px; min-height:30px;
        }}
        QScrollBar::handle:vertical:hover {{ background:{COLORS['accent']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
        QScrollBar:horizontal {{
            background:transparent; height:10px; margin:2px;
        }}
        QScrollBar::handle:horizontal {{
            background:{COLORS['card_hover']}; border-radius:4px; min-width:30px;
        }}
        QScrollBar::handle:horizontal:hover {{ background:{COLORS['accent']}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background:transparent; }}
    """


class HowToTab(QWidget):
    _SEARCH_DEBOUNCE_MS = 250

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet(f"background-color:{COLORS['app_bg']};")
        self._chapter_buttons: List[Tuple[QPushButton, str]] = []
        self._view_all_btn:    Optional[QPushButton]         = None
        self._content:         Optional[QTextEdit]           = None
        self._search:          Optional[QLineEdit]           = None
        self._active_key:      Optional[str]                 = None
        self._highlight:       str                           = ""

        self._images_dir = Path(gui.__file__).resolve().parent / "images" / "guide"
        if not self._images_dir.is_dir():
            print(f"[DEBUG] Guide images folder not found: {self._images_dir}")

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(self._SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._search_content)

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


    def _section_header(self, text: str):
        header = QFrame()
        header.setFixedHeight(30)
        header.setStyleSheet("background:transparent;border:none;")
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
        return header, label

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        root.addWidget(self._build_sidebar())
        root.addLayout(self._build_main(), 1)

    def _build_sidebar(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("howtoSidebar")
        panel.setFixedWidth(_SIDEBAR_WIDTH)
        panel.setStyleSheet(f"""
            QFrame#howtoSidebar {{
                background:{COLORS['card_bg']};
                border:1px solid {COLORS['border']};
                border-radius:10px;
            }}
        """)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        hdr, self._chapters_hdr_lbl = self._section_header(
            t("howto.chapters_title", default="Chapters")
        )
        lay.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}"
            + _scrollbar_qss()
        )

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 2, 0)
        col.setSpacing(6)

        self._view_all_btn = self._nav_btn(f"📖  {t('howto.view_all')}", active=True)
        self._view_all_btn.clicked.connect(self._on_view_all_clicked)
        col.addWidget(self._view_all_btn)

        self._chapter_buttons = []
        for key, data in self._get_chapters().items():
            btn = self._nav_btn(f"{data['icon']}  {data['title']}")
            btn.clicked.connect(lambda checked=False, k=key: self.load_chapter(k))
            col.addWidget(btn)
            self._chapter_buttons.append((btn, key))

        col.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return panel

    def _build_main(self) -> QVBoxLayout:
        main = QVBoxLayout()
        main.setSpacing(12)

        hdr = QFrame()
        hdr.setObjectName("howtoHeader")
        hdr.setFixedHeight(76)
        hdr.setStyleSheet(f"""
            QFrame#howtoHeader {{
                background:{COLORS['card_bg']};
                border:1px solid {COLORS['border']};
                border-radius:10px;
            }}
        """)
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(18, 0, 16, 0)
        hdr_row.setSpacing(16)

        marker = QFrame()
        marker.setFixedSize(4, 34)
        marker.setStyleSheet(
            f"background:{COLORS['accent']};border:none;border-radius:2px;"
        )
        hdr_row.addWidget(marker)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._page_title_lbl = QLabel(t("howto.page_title"))
        self._page_title_lbl.setFont(font(20, "bold"))
        self._page_title_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        text_col.addWidget(self._page_title_lbl)

        self._page_sub_lbl = QLabel(t("howto.page_subtitle"))
        self._page_sub_lbl.setFont(font(12))
        self._page_sub_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        text_col.addWidget(self._page_sub_lbl)
        hdr_row.addLayout(text_col, 1)

        self._search = QLineEdit()
        self._search.setPlaceholderText(f"🔍  {t('howto.search_placeholder')}")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(260)
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
            QLineEdit:focus {{ border-color:{COLORS.get('border_focus', COLORS['accent'])}; }}
        """)
        self._search.textChanged.connect(lambda _t: self._search_timer.start())
        self._search.returnPressed.connect(self._search_content)
        hdr_row.addWidget(self._search)
        main.addWidget(hdr)

        content_frame = QFrame()
        content_frame.setObjectName("howtoContent")
        content_frame.setStyleSheet(f"""
            QFrame#howtoContent {{
                background:{COLORS['card_bg']};
                border:1px solid {COLORS['border']};
                border-radius:10px;
            }}
        """)
        cf_layout = QVBoxLayout(content_frame)
        cf_layout.setContentsMargins(6, 6, 6, 6)

        self._content = _GuideTextEdit()
        self._content.setReadOnly(True)
        self._content.setFrameShape(QFrame.NoFrame)
        self._content.setFont(font(13))
        self._content.document().setDocumentMargin(18)
        self._content.setStyleSheet(f"""
            QTextEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:none;
                border-radius:8px;
                font-size:13px;
                selection-background-color:{COLORS['accent']};
                selection-color:{COLORS['accent_text']};
            }}
        """ + _scrollbar_qss())
        self._content.imageClicked.connect(self._show_full_image)
        cf_layout.addWidget(self._content)
        main.addWidget(content_frame, 1)
        return main


    def _nav_btn(self, text: str, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(font(13, "bold" if active else "normal"))
        btn.setMinimumHeight(38)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        self._style_nav_btn(btn, active)
        return btn

    def _style_nav_btn(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color:{COLORS['accent']};
                    color:{COLORS['accent_text']};
                    border-radius:8px; border:none;
                    padding:6px 14px; font-size:13px; font-weight:bold;
                    text-align:left;
                }}
                QPushButton:hover {{ background-color:{COLORS['accent_hover']}; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color:{COLORS['card_hover']};
                    color:{COLORS['text']};
                    border-radius:8px; border:none;
                    padding:6px 14px; font-size:13px;
                    text-align:left;
                }}
                QPushButton:hover {{
                    background-color:{COLORS['frame_bg']};
                    color:{COLORS['text']};
                }}
            """)
        btn.setFont(font(13, "bold" if active else "normal"))

    def _set_active_nav(self, key: Optional[str]):
        self._active_key = key
        self._style_nav_btn(self._view_all_btn, key is None)
        for btn, k in self._chapter_buttons:
            self._style_nav_btn(btn, k == key)


    def _resolve_image_path(self, filename: str) -> Optional[Path]:
        try:
            candidate = (self._images_dir / filename.strip()).resolve()
            candidate.relative_to(self._images_dir.resolve())
        except (ValueError, RuntimeError, OSError) as _exc:
            print(f"[WARNING] _resolve_image_path: {type(_exc).__name__}: {_exc}")
            return None
        return candidate if candidate.is_file() else None

    def _image_cell_html(self, filename: str, width: Optional[str], caption: str) -> str:
        path = self._resolve_image_path(filename)
        if path is None:
            print(f"[DEBUG] Guide image not found or invalid: {filename!r}")
            err = COLORS.get("error", "#e05555")
            return (
                f'<span style="color:{err};">'
                f'⚠ Missing image: {html.escape(filename)}</span>'
            )
        url = QUrl.fromLocalFile(str(path)).toString()
        href = _IMG_HREF_SCHEME + base64.urlsafe_b64encode(
            str(path).encode("utf-8")
        ).decode("ascii")
        width_px = width or str(_DEFAULT_IMG_WIDTH)
        muted = COLORS.get("text_muted", COLORS["text_secondary"])
        caption_html = (
            f'<br><span style="color:{COLORS["text_secondary"]};font-size:11px;">'
            f'{html.escape(caption)}</span>'
            if caption else ""
        )
        hint_html = (
            f'<br><span style="color:{muted};font-size:10px;">'
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
            f'<table align="left" cellspacing="0" cellpadding="0" '
            f'style="margin:8px 0;"><tr>{cells}</tr></table><br clear="all">'
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


    _BULLET_RE   = re.compile(r"^(\s*)[•\-\*–·]\s+(.*)$")
    _NUMBERED_RE = re.compile(r"^(\s*)(\d+[.)])\s+(.*)$")
    _RULE_RE     = re.compile(r"^\s*[═─━—_=\-]{3,}\s*$")

    def _hl(self, escaped: str) -> str:
        term = self._highlight
        if not term:
            return escaped
        pattern = re.compile(re.escape(html.escape(term)), re.IGNORECASE)
        return pattern.sub(
            lambda m: (
                f'<span style="background-color:{COLORS["accent"]};'
                f'color:{COLORS["accent_text"]};">{m.group(0)}</span>'
            ),
            escaped,
        )

    def _format_text_chunk(self, chunk: str) -> str:
        accent = COLORS["accent"]
        text   = COLORS["text"]
        out: List[str] = []
        blank_run = 0

        for raw in chunk.split("\n"):
            line = raw.rstrip()
            if not line.strip():
                blank_run += 1
                if blank_run == 1:
                    out.append('<p style="margin:0;font-size:6px;">&nbsp;</p>')
                continue
            blank_run = 0

            if self._RULE_RE.match(line):
                continue

            indent = len(line) - len(line.lstrip(" \t"))
            pad = min(indent, 8) * 4

            m = self._BULLET_RE.match(line)
            if m:
                body = self._hl(html.escape(m.group(2)))
                out.append(
                    f'<p style="margin:2px 0 2px {14 + pad}px;color:{text};">'
                    f'<span style="color:{accent};font-weight:bold;">•</span>&nbsp;&nbsp;{body}</p>'
                )
                continue

            m = self._NUMBERED_RE.match(line)
            if m:
                body = self._hl(html.escape(m.group(3)))
                out.append(
                    f'<p style="margin:3px 0 3px {14 + pad}px;color:{text};">'
                    f'<span style="color:{accent};font-weight:bold;">{html.escape(m.group(2))}</span>'
                    f'&nbsp;&nbsp;{body}</p>'
                )
                continue

            stripped = line.strip()
            if stripped.endswith(":") and len(stripped) <= 60:
                out.append(
                    f'<p style="margin:10px 0 3px 0;color:{text};font-size:14px;font-weight:bold;">'
                    f'{self._hl(html.escape(stripped))}</p>'
                )
                continue

            out.append(
                f'<p style="margin:2px 0 2px {pad}px;color:{text};">'
                f'{self._hl(html.escape(stripped))}</p>'
            )
        return "".join(out)

    def _heading_html(self, title: str, icon: str = "", level: int = 1) -> str:
        accent = COLORS["accent"]
        size   = 20 if level == 1 else 17
        label  = f"{icon}&nbsp;&nbsp;" if icon else ""
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin:6px 0 8px 0;">'
            f'<tr><td width="4" bgcolor="{accent}"></td>'
            f'<td bgcolor="{COLORS["card_bg"]}" style="padding:9px 14px;">'
            f'<span style="font-size:{size}px;font-weight:bold;color:{COLORS["text"]};">'
            f'{label}{self._hl(html.escape(title))}</span></td></tr></table>'
        )

    def _render_body_html(self, text: str) -> str:
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
                parts.append(self._format_text_chunk(between))
            pending_group.append((
                m.group("file"), m.group("width"), (m.group("caption") or "").strip()
            ))
            pos = m.end()

        flush_group()
        parts.append(self._format_text_chunk(text[pos:]))
        return "".join(parts)

    def _chapter_html(self, data: dict, level: int = 1) -> str:
        return (
            self._heading_html(data["title"], data["icon"], level)
            + self._render_body_html(data["content"])
        )

    def _wrap_document(self, body: str) -> str:
        return (
            f'<div style="color:{COLORS["text"]};font-size:13px;line-height:150%;">'
            f'{body}</div>'
        )

    def _set_document(self, body_html: str):
        self._content.setHtml(self._wrap_document(body_html))
        QApplication.processEvents()
        self._content.moveCursor(QTextCursor.Start)
        self._content.verticalScrollBar().setValue(0)


    def _on_view_all_clicked(self):
        if self._search is not None and self._search.text():
            self._search.blockSignals(True)
            self._search.clear()
            self._search.blockSignals(False)
        self.load_all_chapters()

    def load_chapter(self, chapter_key: str):
        print(f"[DEBUG] load_chapter: {chapter_key!r}")
        chapters = self._get_chapters()
        if chapter_key not in chapters:
            return
        data = chapters[chapter_key]
        self._highlight = ""
        self._set_document(self._chapter_html(data))
        self._set_active_nav(chapter_key)
        print(f"[DEBUG] Loaded chapter: {data['title']}")

    def load_all_chapters(self):
        print("[DEBUG] load_all_chapters: rendering full doc view")
        self._highlight = ""
        chapters = self._get_chapters()
        muted = COLORS.get("text_muted", COLORS["text_secondary"])

        welcome = t("howto.welcome_title")
        intro   = t("howto.welcome_intro")
        parts: List[str] = [
            f'<p style="margin:4px 0 4px 0;font-size:24px;font-weight:bold;color:{COLORS["text"]};">'
            f'{html.escape(welcome)}</p>',
            f'<p style="margin:0 0 10px 0;font-size:13px;color:{COLORS["text_secondary"]};">'
            f'{html.escape(intro).replace(chr(10), "<br>")}</p>',
        ]

        quick = []
        for key in ("howto.quick_nav_title", "howto.quick_nav_chapters",
                    "howto.quick_nav_search", "howto.quick_nav_walkthrough"):
            line = t(key)
            if line != key:
                quick.append(line)
        lets = t("howto.lets_start")
        if lets == "howto.lets_start":
            lets = ""

        if quick:
            rows = "".join(
                f'<tr><td style="padding:2px 0;color:{COLORS["text"]};">'
                f'{html.escape(q)}</td></tr>'
                for q in quick
            )
            parts.append(
                f'<table width="100%" cellspacing="0" cellpadding="0" style="margin:6px 0;">'
                f'<tr><td width="4" bgcolor="{COLORS["accent"]}"></td>'
                f'<td bgcolor="{COLORS["card_bg"]}" style="padding:10px 14px;">'
                f'<table cellspacing="0" cellpadding="0">{rows}</table></td></tr></table>'
            )
        if lets:
            parts.append(
                f'<p style="margin:8px 0 14px 0;color:{COLORS["accent"]};font-weight:bold;">'
                f'{html.escape(lets)}</p>'
            )

        for data in chapters.values():
            parts.append('<p style="margin:0;font-size:10px;">&nbsp;</p>')
            parts.append(self._chapter_html(data, level=2))
        self._set_document("".join(parts))
        self._set_active_nav(None)
        print("[DEBUG] Loaded all chapters")

    def _search_content(self):
        self._search_timer.stop()
        raw  = self._search.text() if self._search else ""
        term = raw.lower().strip()
        print(f"[DEBUG] _search_content: query={raw!r}")
        if not term:
            if self._active_key is not None or self._highlight:
                self.load_all_chapters()
            return

        chapters = self._get_chapters()
        results = [
            d for d in chapters.values()
            if term in d["content"].lower() or term in d["title"].lower()
        ]
        self._highlight = raw.strip()
        muted = COLORS.get("text_muted", COLORS["text_secondary"])

        if results:
            count = len(results)
            noun = "chapter" if count == 1 else "chapters"
            body = (
                f'<p style="margin:4px 0 2px 0;font-size:20px;font-weight:bold;color:{COLORS["text"]};">'
                f'Search results for “{html.escape(raw.strip())}”</p>'
                f'<p style="margin:0 0 10px 0;color:{COLORS["text_secondary"]};">'
                f'{count} {noun} found</p>'
            )
            for data in results:
                body += '<p style="margin:0;font-size:10px;">&nbsp;</p>'
                body += self._chapter_html(data, level=2)
        else:
            body = (
                f'<p style="margin:30px 0 4px 0;font-size:20px;font-weight:bold;color:{COLORS["text"]};">'
                f'No results found</p>'
                f'<p style="color:{COLORS["text_secondary"]};">'
                f'Nothing matched “{html.escape(raw.strip())}”. Try a different keyword.</p>'
            )
        self._set_document(body)
        self._set_active_nav("\0search")


    def refresh_ui(self):
        self._page_title_lbl.setText(t("howto.page_title"))
        self._page_sub_lbl.setText(t("howto.page_subtitle"))
        self._chapters_hdr_lbl.setText(
            t("howto.chapters_title", default="Chapters").upper()
        )
        if self._search:
            self._search.setPlaceholderText(f"🔍  {t('howto.search_placeholder')}")
        chapters = self._get_chapters()
        if self._view_all_btn:
            self._view_all_btn.setText(f"📖  {t('howto.view_all')}")
        for btn, key in self._chapter_buttons:
            if key in chapters:
                data = chapters[key]
                btn.setText(f"{data['icon']}  {data['title']}")

        if self._content is not None:
            if self._active_key in chapters:
                self.load_chapter(self._active_key)
            else:
                self.load_all_chapters()
