from __future__ import annotations
from typing import List, Tuple, Optional

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import QTextCursor
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QTextEdit, QSizePolicy,
    QApplication,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import AnimButton, GhostButton, SectionHeader, HSeparator
from gui.state   import state

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return key


class HowToTab(QWidget):
    """Documentation tab with chapter nav, search, and animated transitions."""

    def __init__(self, parent: QWidget):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent)
        self.setStyleSheet(f"background-color:{COLORS['app_bg']};")
        self._chapter_buttons: List[Tuple[QPushButton, str]] = []
        self._view_all_btn:    Optional[QPushButton]         = None
        self._content:         Optional[QTextEdit]           = None
        self._search:          Optional[QLineEdit]           = None
        self._setup_ui()
        # 50 ms gives Qt time to finish laying out the widget before we set
        # the scroll position — 0 ms fires before the first paint and the
        # viewport reset gets ignored.
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
        print(f"[DEBUG] _setup_ui() called")
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

        # search
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

        self._content = QTextEdit()
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
        cf_layout.addWidget(self._content)
        root.addWidget(content_frame, 1)


    def _nav_btn(self, text: str, active: bool = False) -> QPushButton:
        print(f"[DEBUG] _nav_btn() called")
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


    def _set_text_scroll_top(self, text: str):
        """
        Set content and guarantee the viewport starts at the top.

        processEvents() flushes Qt's pending layout pass synchronously so our
        setValue(0) is always the last thing to touch the scrollbar.

        fade_in() is intentionally NOT called on self._content or its direct
        parent — applying QGraphicsOpacityEffect to either causes Qt to
        re-render the QTextEdit through an offscreen pixmap, resetting the
        viewport scroll after we set it to 0.
        """
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
        print(f"[DEBUG] load_all_chapters: rendering full doc view")
        chapters = self._get_chapters()

        # Build the same intro block as the original ctk version
        intro = (
            t("howto.welcome_title")         + "\n\n"
            + t("howto.welcome_intro")       + "\n\n"
        )
        # Optional quick-nav lines (graceful fallback if keys don't exist)
        for key in ("howto.quick_nav_title", "howto.quick_nav_chapters",
                    "howto.quick_nav_search", "howto.quick_nav_walkthrough"):
            line = t(key)
            if line != key:          # key was actually translated
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
        """
        Refresh translations without rebuilding the widget tree.
        Only the text content is reloaded, preserving the layout.
        """
        print(f"[DEBUG] refresh_ui() called")
        self._page_title_lbl.setText(t("howto.page_title"))
        self._page_sub_lbl.setText(t("howto.page_subtitle"))
        if self._search:
            self._search.setPlaceholderText(t("howto.search_placeholder"))
        chapters = self._get_chapters()
        # Re-label the view-all button
        if self._view_all_btn:
            self._view_all_btn.setText(f"📖  {t('howto.view_all')}")
        # Re-label each chapter button
        for btn, key in self._chapter_buttons:
            if key in chapters:
                data = chapters[key]
                btn.setText(f"{data['icon']} {data['title']}")

        # Reload content with new locale strings (guard against not-yet-shown)
        if self._content is not None:
            self.load_all_chapters()


