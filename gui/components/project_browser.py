from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional, Dict

from PySide6.QtCore    import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy,
    QFileDialog, QComboBox,
)

from gui.theme import COLORS, font

try:
    from gui.confirmation_dialog import askyesno
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def askyesno(parent, title, message, colors, icon='❓', danger=False):
        return True

try:
    from core.settings import get_projects_dir
except ImportError as _imp_exc:
    print(f"[DEBUG] project_browser: could not import get_projects_dir: {_imp_exc} — using empty default dir")
    def get_projects_dir(): return ""

try:
    from core.project_registry import (
        load_registry, remove_entry, register_existing, validate_entries,
        touch_last_opened,
    )
    _REGISTRY_OK = True
except ImportError as _imp_exc:
    _REGISTRY_OK = False
    print(f"[DEBUG] project_browser: could not import project_registry: {_imp_exc} — using stubs")
    def load_registry():         return []
    def remove_entry(p):         return False
    def register_existing(p):    return None
    def validate_entries():      return [], []
    def touch_last_opened(p):    pass

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return kw.get('default', key)


def _fmt_date(iso: str) -> str:
    try:
        dt     = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.strftime("%d %b %Y  %H:%M")
    except Exception as exc:
        print(f"[DEBUG] _fmt_date: parse error for {iso!r}: {exc} — returning raw")
        return iso or "—"


def _fmt_size(kb: float) -> str:
    if kb < 1024:
        return f"{kb:.1f} KB"
    return f"{kb / 1024:.2f} MB"


def _trunc(text: str, maxlen: int = 52) -> str:
    if len(text) <= maxlen:
        return text
    return "…" + text[-(maxlen - 1):]


class _ProjectRow(QFrame):
    open_requested   = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, entry: Dict, missing: bool = False, parent=None):
        super().__init__(parent)
        self._path    = entry.get("path", "")
        self._missing = missing
        self._entry   = entry

        self.setCursor(Qt.PointingHandCursor)
        self._apply_style(hover=False)
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(12)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        mod_name = entry.get("mod_name") or os.path.splitext(
            os.path.basename(self._path)
        )[0] or t("project_browser.untitled_project")

        self._name_lbl = QLabel(mod_name)
        self._name_lbl.setFont(font(14, "bold"))
        self._name_lbl.setStyleSheet(
            f"color:{'#ff6b6b' if missing else COLORS['text']};"
            "background:transparent;border:none;"
        )
        name_row.addWidget(self._name_lbl)

        if missing:
            badge = QLabel(t("project_browser.file_not_found_badge"))
            badge.setFont(font(10, "bold"))
            badge.setStyleSheet(
                f"color:{COLORS['error']};background:{COLORS['frame_bg']};"
                f"border:1px solid {COLORS['error']};border-radius:4px;"
                "padding:1px 6px;"
            )
            name_row.addWidget(badge)

        name_row.addStretch()
        info_col.addLayout(name_row)

        author = entry.get("author",     "")
        cars   = entry.get("car_count",  0)
        skins  = entry.get("skin_count", 0)

        meta_parts = []
        if author:
            meta_parts.append(f"👤 {author}")
        meta_parts.append(f"🚗 {cars} {t('project_browser.car') if cars == 1 else t('project_browser.cars')}")
        meta_parts.append(f"🎨 {skins} {t('project_browser.skin') if skins == 1 else t('project_browser.skins')}")

        meta_lbl = QLabel("   ·   ".join(meta_parts))
        meta_lbl.setFont(font(12))
        meta_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        info_col.addWidget(meta_lbl)

        last_saved = _fmt_date(entry.get("last_saved", ""))
        size_str   = _fmt_size(entry.get("file_size_kb", 0))
        path_short = _trunc(self._path)

        detail_lbl = QLabel(
            f"💾 {last_saved}   ·   {size_str}   ·   {path_short}"
        )
        detail_lbl.setFont(font(11))
        detail_lbl.setToolTip(self._path)
        detail_lbl.setStyleSheet(
            f"color:{COLORS['text_muted']};background:transparent;border:none;"
        )
        info_col.addWidget(detail_lbl)

        outer.addLayout(info_col, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        btn_col.setAlignment(Qt.AlignVCenter)

        if not missing:
            self._open_btn = QPushButton(t("project_browser.open"))
            self._open_btn.setFont(font(12, "bold"))
            self._open_btn.setFixedSize(80, 30)
            self._open_btn.setCursor(Qt.PointingHandCursor)
            self._open_btn.setStyleSheet(self._open_btn_style())
            self._open_btn.clicked.connect(
                lambda: self.open_requested.emit(self._path)
            )
            btn_col.addWidget(self._open_btn)

        self._remove_btn = QPushButton(t("project_browser.remove"))
        self._remove_btn.setFont(font(11))
        self._remove_btn.setFixedSize(80, 26)
        self._remove_btn.setCursor(Qt.PointingHandCursor)
        self._remove_btn.setStyleSheet(self._remove_btn_style())
        self._remove_btn.clicked.connect(
            lambda: self.remove_requested.emit(self._path)
        )
        btn_col.addWidget(self._remove_btn)

        outer.addLayout(btn_col)

    def _open_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background:{COLORS['accent']};
                color:{COLORS['accent_text']};
                border-radius:7px;border:none;font-weight:bold;
            }}
            QPushButton:hover {{ background:{COLORS['accent_hover']}; }}
        """

    def _remove_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background:transparent;
                color:{COLORS['text_muted']};
                border:1px solid {COLORS['border']};
                border-radius:6px;
            }}
            QPushButton:hover {{
                color:{COLORS['error']};
                border-color:{COLORS['error']};
            }}
        """

    def _apply_style(self, hover: bool):
        bg = COLORS["card_hover"] if hover and not self._missing else COLORS["card_bg"]
        border_color = (
            COLORS["error"] if self._missing
            else (COLORS["accent"] if hover else COLORS["border"])
        )
        self.setStyleSheet(f"""
            QFrame {{
                background:{bg};
                border-radius:10px;
                border:1px solid {border_color};
            }}
        """)

    def enterEvent(self, event):
        if not self._missing:
            self._apply_style(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(hover=False)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if not self._missing and event.button() == Qt.LeftButton:
            self.open_requested.emit(self._path)
        super().mouseDoubleClickEvent(event)


class ProjectBrowserDialog(QDialog):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.selected_path: Optional[str] = None

        self.setModal(True)
        self.resize(820, 580)
        self.setMinimumSize(600, 400)
        self.setStyleSheet(f"""
            QDialog {{
                background:{COLORS['app_bg']};
                color:{COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
            }}
        """)

        self._entries:     List[Dict] = []
        self._rows:        List[_ProjectRow] = []
        self._filter_text: str = ""
        self._sort_key: str = "last_opened"

        self._setup_ui()
        self._load_and_populate()


    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title_row = QHBoxLayout()
        title_lbl = QLabel(t("project_browser.title"))
        title_lbl.setFont(font(20, "bold"))
        title_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        self._count_lbl = QLabel("")
        self._count_lbl.setFont(font(12))
        self._count_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        title_row.addWidget(self._count_lbl)
        root.addLayout(title_row)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        self._search = QLineEdit()
        self._search.setPlaceholderText(t("project_browser.search_placeholder"))
        self._search.setClearButtonEnabled(True)
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
            QLineEdit:focus {{ border-color:{COLORS['border_focus']}; }}
        """)
        self._search.textChanged.connect(self._on_search)
        search_row.addWidget(self._search, 1)

        self._sort_combo = QComboBox()
        self._sort_combo.addItem(t("project_browser.sort_last_opened", default="Recently opened"), "last_opened")
        self._sort_combo.addItem(t("project_browser.sort_last_saved",  default="Recently modified"), "last_saved")
        self._sort_combo.setFixedHeight(36)
        self._sort_combo.setFont(font(13))
        self._sort_combo.setCursor(Qt.PointingHandCursor)
        self._sort_combo.setStyleSheet(f"""
            QComboBox {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 12px;
            }}
            QComboBox:hover {{ border-color:{COLORS['accent']}; }}
            QComboBox::drop-down {{ border:none; width:24px; }}
            QComboBox QAbstractItemView {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                selection-background-color:{COLORS['accent']};
                selection-color:{COLORS['accent_text']};
                outline:none;
            }}
        """)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        search_row.addWidget(self._sort_combo)

        root.addLayout(search_row)

        self._missing_banner = QLabel("")
        self._missing_banner.setFont(font(12))
        self._missing_banner.setWordWrap(True)
        self._missing_banner.setStyleSheet(f"""
            QLabel {{
                background:{COLORS['frame_bg']};
                color:{COLORS['warning']};
                border:1px solid {COLORS['warning']};
                border-radius:8px;
                padding:8px 14px;
            }}
        """)
        self._missing_banner.setVisible(False)
        root.addWidget(self._missing_banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background:transparent; border:none; }
            QScrollArea > QWidget > QWidget { background:transparent; }
        """)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, 1)

        self._empty_lbl = QLabel(t("project_browser.empty_state"))
        self._empty_lbl.setFont(font(14))
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{COLORS['text_muted']};background:transparent;border:none;"
        )
        self._empty_lbl.setVisible(False)
        root.addWidget(self._empty_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._add_btn = QPushButton(t("project_browser.add_existing"))
        self._add_btn.setFont(font(13))
        self._add_btn.setFixedHeight(36)
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setStyleSheet(self._secondary_btn_style())
        self._add_btn.clicked.connect(self._add_existing)
        btn_row.addWidget(self._add_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton(t("common.cancel"))
        cancel_btn.setFont(font(13))
        cancel_btn.setFixedHeight(36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(self._secondary_btn_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        root.addLayout(btn_row)

    def _secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 16px;
            }}
            QPushButton:hover {{
                background:{COLORS['card_hover']};
                border-color:{COLORS['accent']};
                color:{COLORS['accent']};
            }}
        """


    def _load_and_populate(self):
        valid, missing = validate_entries()
        print(f"[DEBUG] ProjectBrowserDialog._load_and_populate: valid={len(valid)} missing={len(missing)}")

        self._entries = valid

        if missing:
            names = ", ".join(
                os.path.basename(e.get("path", "?")) for e in missing[:3]
            )
            extra = f" (+{len(missing) - 3} more)" if len(missing) > 3 else ""
            banner_text = t(
                "project_browser.missing_banner",
                count=len(missing), names=names, extra=extra,
            )
            self._missing_banner.setText(banner_text)
            self._missing_banner.setVisible(True)

        self._rebuild_list()

    def _rebuild_list(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

        ft = self._filter_text.lower()
        visible = [
            e for e in self._entries
            if not ft
            or ft in (e.get("mod_name") or "").lower()
            or ft in (e.get("author")   or "").lower()
            or ft in (e.get("path")     or "").lower()
        ]

        if self._sort_key == "last_opened":
            sort_fn = lambda e: e.get("last_opened") or e.get("added_at", "")
        else:
            sort_fn = lambda e: e.get("last_saved", "")
        visible.sort(key=sort_fn, reverse=True)

        for entry in visible:
            row = _ProjectRow(entry, missing=False, parent=self._list_widget)
            row.open_requested.connect(self._accept_path)
            row.remove_requested.connect(self._remove_row)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

        count = len(visible)
        total = len(self._entries)

        if ft and total > count:
            count_text = t("project_browser.count_filtered", count=count, total=total)
        elif total:
            count_text = t("project_browser.count_one", total=total) if total == 1 else t("project_browser.count_many", total=total)
        else:
            count_text = ""

        self._count_lbl.setText(count_text)
        self._empty_lbl.setVisible(count == 0)


    def _on_search(self, text: str):
        self._filter_text = text
        self._rebuild_list()

    def _on_sort_changed(self, index: int):
        self._sort_key = self._sort_combo.itemData(index)
        print(f"[DEBUG] ProjectBrowserDialog._on_sort_changed: sort_key={self._sort_key!r}")
        self._rebuild_list()

    def _accept_path(self, path: str):
        if not os.path.isfile(path):
            print(f"[DEBUG] ProjectBrowserDialog._accept_path: {path!r} no longer exists — removing from registry")
            banner_text = t("project_browser.file_gone_banner", path=path)
            self._missing_banner.setText(banner_text)
            self._missing_banner.setVisible(True)
            remove_entry(path)
            self._entries = [e for e in self._entries if e.get("path") != path]
            self._rebuild_list()
            return

        self.selected_path = path
        touch_last_opened(path)
        self.accept()

    def _remove_row(self, path: str):
        mod_name = next(
            (e.get("mod_name") for e in self._entries if e.get("path") == path),
            None,
        ) or os.path.basename(path)

        confirmed = askyesno(
            self,
            t("project_browser.delete_confirm_title", default="Delete Project?"),
            t(
                "project_browser.delete_confirm_message",
                default=f"This will permanently delete '{mod_name}' from disk:\n\n{path}\n\n"
                        "This cannot be undone.",
                name=mod_name, path=path,
            ),
            COLORS,
            icon="🗑️",
            danger=True,
        )
        if not confirmed:
            return

        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError as e:
                print(f"[ERROR] ProjectBrowserDialog._remove_row: could not delete {path!r}: {e}")
                banner_text = t(
                    "project_browser.delete_failed_banner",
                    default=f"Could not delete '{mod_name}': {e}",
                    name=mod_name, err=str(e),
                )
                self._missing_banner.setText(banner_text)
                self._missing_banner.setVisible(True)
                return

        remove_entry(path)
        self._entries = [e for e in self._entries if e.get("path") != path]
        self._rebuild_list()

    def _add_existing(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            t("project_browser.add_existing_dialog_title"),
            get_projects_dir(),
            t("project_browser.file_filter"),
        )
        if not paths:
            return

        failed:  List[str] = []
        added:   int       = 0
        skipped: int       = 0

        for path in paths:
            entry = register_existing(path)

            if entry is None:
                failed.append(os.path.basename(path))
                continue

            norm    = os.path.normcase(os.path.abspath(path))
            already = any(
                os.path.normcase(os.path.abspath(e.get("path", ""))) == norm
                for e in self._entries
            )

            if already:
                skipped += 1
            else:
                self._entries.insert(0, entry)
                added += 1

        print(f"[DEBUG] ProjectBrowserDialog._add_existing: added={added} skipped={skipped} failed={len(failed)}")

        if failed:
            fail_names  = ", ".join(failed[:3])
            fail_extra  = f" (+{len(failed) - 3} more)" if len(failed) > 3 else ""
            banner_text = t("project_browser.add_failed_banner", count=len(failed), names=fail_names, extra=fail_extra)
            self._missing_banner.setText(banner_text)
            self._missing_banner.setVisible(True)

        self._rebuild_list()
