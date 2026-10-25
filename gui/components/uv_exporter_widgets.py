
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.theme import COLORS

try:
    from core.localization import t
except ImportError:
    def t(key, default=None, **kw):
        text = default if default is not None else key
        try:
            return text.format(**kw)
        except Exception:
            return text


def _t(key: str, default: str, **kw) -> str:
    return t(key, default=default, **kw)


class ColorPickerButton(QPushButton):
    colorChanged = Signal(QColor)

    def __init__(self, initial: QColor, parent=None):
        super().__init__(parent)
        self._color = initial
        self.setFixedSize(44, 26)
        self._update_swatch()
        self.clicked.connect(self._pick)

    def _update_swatch(self):
        pix = QPixmap(self.size())
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setBrush(self._color)
        painter.setPen(QColor(COLORS["border"]))
        painter.drawRoundedRect(1, 1, pix.width() - 2, pix.height() - 2, 4, 4)
        painter.end()
        self.setIcon(pix)
        self.setIconSize(self.size())

    def color(self) -> QColor:
        return self._color

    def set_color(self, color: QColor):
        self._color = color
        self._update_swatch()

    def apply_theme(self):
        self._update_swatch()

    def _pick(self):
        chosen = QColorDialog.getColor(
            self._color, self, _t("uv_exporter.choose_color", "Choose color"), QColorDialog.ShowAlphaChannel
        )
        if chosen.isValid():
            self.set_color(chosen)
            self.colorChanged.emit(chosen)


class GroupListWidget(QWidget):
    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("")
        layout.addWidget(self.title_label)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.select_all_btn = QPushButton("")
        self.select_none_btn = QPushButton("")
        self.select_only_shown_btn = QPushButton("")
        self.auto_select_btn = QPushButton("")
        for b in (
            self.select_all_btn,
            self.select_none_btn,
            self.select_only_shown_btn,
            self.auto_select_btn,
        ):
            b.setStyleSheet("padding:5px 6px;")
            header.addWidget(b, 1)
        layout.addLayout(header)

        self.search_box = QLineEdit()
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_box)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(180)
        layout.addWidget(self.list_widget, 1)

        self.match_label = QLabel("")
        self.match_label.hide()
        layout.addWidget(self.match_label)

        self.hidden_checked_label = QLabel("")
        self.hidden_checked_label.setWordWrap(True)
        self.hidden_checked_label.hide()
        layout.addWidget(self.hidden_checked_label)

        self.retranslate()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.activate()
        self._fixed_height = layout.sizeHint().height() + 56

        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        self.select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        self.select_only_shown_btn.clicked.connect(self._check_only_visible)
        self.list_widget.itemChanged.connect(self._on_item_changed)

        self.apply_theme()

    def retranslate(self):
        self.title_label.setText(_t("uv_exporter.group_title", "Mesh groups / materials"))
        self.select_all_btn.setText(_t("uv_exporter.sel_all", "All"))
        self.select_none_btn.setText(_t("uv_exporter.sel_none", "None"))
        self.select_only_shown_btn.setText(_t("uv_exporter.sel_only_shown", "Only shown"))
        self.select_only_shown_btn.setToolTip(_t(
            "uv_exporter.sel_only_shown_tip",
            "Check every group matching the current search and uncheck everything else",
        ))
        self.auto_select_btn.setText(_t("uv_exporter.sel_auto", "Auto"))
        self.auto_select_btn.setToolTip(_t(
            "uv_exporter.sel_auto_tip",
            "Automatically check exterior-part names with usable UVs, and "
            "uncheck mechanical parts, overlay materials, and "
            "degenerate/out-of-bounds UVs.",
        ))
        self.search_box.setPlaceholderText(_t("uv_exporter.search_parts", "Search parts…"))
        self._apply_filter(self.search_box.text())

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(hint.width(), self._fixed_height)

    def minimumSizeHint(self):
        return self.sizeHint()

    def apply_theme(self):
        self.title_label.setStyleSheet(
            f"font-weight:600;color:{COLORS['text']};background:transparent;"
        )
        self.match_label.setStyleSheet(
            f"color:{COLORS['text_secondary']};font-size:10px;background:transparent;"
        )
        self.hidden_checked_label.setStyleSheet(
            f"color:{COLORS['warning']};font-size:10px;background:transparent;"
        )

    def populate(self, group_infos):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for info in group_infos:
            if len(info) == 3:
                name, display_label, tri_count = info
            else:
                name, tri_count = info
                display_label = name
            item = QListWidgetItem(
                f"{display_label}  " + _t("uv_exporter.tris", "({count} tris)", count=tri_count)
            )
            item.setData(Qt.UserRole, name)
            item.setData(Qt.UserRole + 1, display_label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        self._apply_filter(self.search_box.text())
        self.selectionChanged.emit()

    def populate_preserving_checks(self, group_infos):
        previously_checked = self.checked_names()
        self.populate(group_infos)
        self.set_checked(previously_checked)

    def set_checked(self, names: set[str]):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in names else Qt.Unchecked)
        self.list_widget.blockSignals(False)
        self._update_hidden_checked_warning()
        self.selectionChanged.emit()

    def set_checked_with_reasons(
        self,
        included: set[str],
        reasons: dict[str, str],
        conflict_notes: dict[str, str] | None = None,
    ):
        conflict_notes = conflict_notes or {}
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            name = item.data(Qt.UserRole)
            is_included = name in included
            item.setCheckState(Qt.Checked if is_included else Qt.Unchecked)
            item.setToolTip(
                conflict_notes.get(name, "") if is_included else reasons.get(name, "")
            )
        self.list_widget.blockSignals(False)
        self._update_hidden_checked_warning()
        self.selectionChanged.emit()

    def checked_names(self) -> set[str]:
        return {
            self.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.Checked
        }

    def _on_item_changed(self, _item):
        self._update_hidden_checked_warning()
        self.selectionChanged.emit()

    def _apply_filter(self, query: str):
        query = query.strip().lower()
        visible_count = 0
        total_count = self.list_widget.count()
        for i in range(total_count):
            item = self.list_widget.item(i)
            name = item.data(Qt.UserRole) or ""
            display_label = item.data(Qt.UserRole + 1) or name
            matches = query in name.lower() or query in display_label.lower()
            item.setHidden(not matches)
            if matches:
                visible_count += 1
        self.match_label.setText(
            _t("uv_exporter.match_count", "{shown} of {total} match",
               shown=visible_count, total=total_count) if query else ""
        )
        self.match_label.setVisible(bool(query))
        self._update_hidden_checked_warning()

    def _update_hidden_checked_warning(self):
        hidden_checked = sum(
            1
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).isHidden()
            and self.list_widget.item(i).checkState() == Qt.Checked
        )
        if hidden_checked > 0:
            button = _t("uv_exporter.sel_only_shown", "Only shown")
            if hidden_checked == 1:
                text = _t(
                    "uv_exporter.hidden_checked_one",
                    "⚠ {count} more group checked outside this search and still "
                    "included in the render. Use \"{button}\" to isolate just what's visible.",
                    count=hidden_checked, button=button,
                )
            else:
                text = _t(
                    "uv_exporter.hidden_checked_many",
                    "⚠ {count} more groups checked outside this search and still "
                    "included in the render. Use \"{button}\" to isolate just what's visible.",
                    count=hidden_checked, button=button,
                )
            self.hidden_checked_label.setText(text)
        else:
            self.hidden_checked_label.setText("")
        self.hidden_checked_label.setVisible(hidden_checked > 0)

    def _set_all_checked(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)
        self.list_widget.blockSignals(False)
        self._update_hidden_checked_warning()
        self.selectionChanged.emit()

    def _check_only_visible(self):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.Unchecked if item.isHidden() else Qt.Checked)
        self.list_widget.blockSignals(False)
        self._update_hidden_checked_warning()
        self.selectionChanged.emit()


def make_labeled_row(label_text: str, widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    label = QLabel(label_text)
    label.setMinimumWidth(110)
    row.addWidget(label)
    row.addWidget(widget)
    row.addStretch()
    return row
