from __future__ import annotations
from typing import Callable, Optional

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from gui.theme import COLORS, font
from gui.components.dialog_kit import (
    DialogShell, LanguageRow, make_scroll, primary_button, input_qss,
    platform_supports_transparency as _platform_supports_transparency,
)

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

_LangRow = LanguageRow


class LanguageSelectionDialog(DialogShell):
    def __init__(
        self,
        parent: QWidget,
        colors: dict,
        on_complete: Optional[Callable] = None,
    ):
        super().__init__(
            parent,
            t("language_selection.title", default="Select Your Language"),
            560, 560, icon="🌍",
            subtitle="BeamSkin Studio",
        )
        self._colors     = colors
        self.on_complete = on_complete

        loc = get_localization()
        self.selected_language = loc.current_language if loc else "en"

        self.body.addWidget(self._sub_label())

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "🔍  " + t("language_selection.search", default="Search languages…")
        )
        self._search.setMinimumHeight(36)
        self._search.setFont(font(12))
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(input_qss())
        self._search.textChanged.connect(lambda _t: self._populate_list())
        self.body.addWidget(self._search)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(6)
        self.body.addWidget(make_scroll(self._list_widget), 1)

        self._populate_list()

        self._continue_btn = primary_button(
            t("language_selection.continue", default="Continue →"), height=42,
        )
        self._continue_btn.clicked.connect(self._on_continue)
        self.footer.addWidget(self._continue_btn, 1)
        self.add_footer()

    def _sub_label(self):
        from gui.components.dialog_kit import body_label
        return body_label(
            t("language_selection.subtitle",
              default="Choose your preferred language for BeamSkin Studio"),
            size=12,
        )

    def _populate_list(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        q = self._search.text().strip().lower() if hasattr(self, "_search") else ""
        langs = get_available_languages()
        for code, info in sorted(langs.items(), key=lambda x: x[1].get("name", x[0])):
            if q and not any(q in str(s).lower()
                             for s in (info.get("native", ""), info.get("name", ""), code)):
                continue
            row = LanguageRow(code, info, code == self.selected_language)
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
