from __future__ import annotations
import os
from typing import Callable, Optional

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QFileDialog, QWidget

from gui.theme import COLORS, font
from gui.components.dialog_kit import (
    DialogShell, make_panel, section_header, body_label, primary_button,
    outline_button, input_qss, lbl_qss, icon_badge,
)

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] legacy_migration_dialog.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return kw.get('default', key)

from core.settings import get_data_dir, mark_setup_complete, set_legacy_mode
from core.legacy_migration import (
    LegacyDataInfo, migrate_all_legacy_data, skip_legacy_data,
)


class LegacyMigrationDialog(DialogShell):
    def __init__(
        self,
        parent: Optional[QWidget],
        info: LegacyDataInfo,
        on_done: Callable[[], None],
    ):
        super().__init__(
            parent,
            t("legacy_migration.title", default="Data From an Older Version Found"),
            580, icon="📦",
            escape_closes=False,
        )
        self._info       = info
        self._on_done    = on_done
        self._chosen_dir = get_data_dir()
        self._build()

    def _build(self):
        self.body.addWidget(body_label(t(
            "legacy_migration.desc",
            default="BeamSkin Studio now stores your data in a dedicated folder instead "
                    "of next to the app. We found projects and vehicles from a previous "
                    "install — choose where to keep them and we'll copy everything over. "
                    "Your old files are left untouched.",
        ), size=12))

        found, f_lay = make_panel("foundPanel")
        f_lay.addWidget(section_header(t("legacy_migration.found_header", default="Found")))

        path_lbl = QLabel(self._info.legacy_dir)
        path_lbl.setFont(font(11))
        path_lbl.setWordWrap(True)
        path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_lbl.setStyleSheet(lbl_qss("text_secondary"))
        f_lay.addWidget(path_lbl)

        stats = QLabel(t(
            "legacy_migration.stats",
            default="{vehicles} added vehicle(s) · {projects} saved project(s) · ~{size} KB",
            vehicles=self._info.vehicle_count,
            projects=self._info.project_count,
            size=self._info.approx_size_kb,
        ))
        stats.setFont(font(12, "bold"))
        stats.setStyleSheet(lbl_qss("accent"))
        f_lay.addWidget(stats)
        self.body.addWidget(found)

        dest, d_lay = make_panel("destPanel")
        d_lay.addWidget(section_header(
            t("legacy_migration.dest_label", default="Copy data to")))

        row = QHBoxLayout()
        row.setSpacing(8)
        self._dest_entry = QLineEdit(self._chosen_dir)
        self._dest_entry.setReadOnly(True)
        self._dest_entry.setMinimumHeight(36)
        self._dest_entry.setFont(font(12))
        self._dest_entry.setStyleSheet(input_qss())
        row.addWidget(self._dest_entry, 1)

        browse = outline_button(t("common.browse", default="Browse"), height=36, font_size=12)
        browse.clicked.connect(self._browse_dest)
        row.addWidget(browse)
        d_lay.addLayout(row)
        self.body.addWidget(dest)

        skip_btn = outline_button(t("legacy_migration.skip", default="Don't Migrate"), height=42)
        skip_btn.clicked.connect(self._on_skip)
        self.footer.addWidget(skip_btn, 1)

        migrate_btn = primary_button(
            t("legacy_migration.migrate", default="Migrate My Data"), height=42, font_size=14)
        migrate_btn.clicked.connect(self._on_migrate)
        self.footer.addWidget(migrate_btn, 2)
        self.add_footer()
        migrate_btn.setFocus()

    def _browse_dest(self):
        path = QFileDialog.getExistingDirectory(
            self,
            t("legacy_migration.browse_title", default="Choose Data Folder"),
            self._chosen_dir,
        )
        if not path or not os.access(path, os.W_OK):
            return
        self._chosen_dir = path
        self._dest_entry.setText(path)

    def _on_migrate(self):
        print(f"[DEBUG] LegacyMigrationDialog._on_migrate: "
              f"{self._info.legacy_dir!r} -> {self._chosen_dir!r}")
        try:
            from core.settings import set_data_dir
            migrate_all_legacy_data(self._info.legacy_dir, self._chosen_dir)
            set_data_dir(self._chosen_dir, migrate=False)
        except Exception as e:
            print(f"[WARNING] LegacyMigrationDialog: migration failed: {e}")
        self._mark_setup_complete_for_upgrader()
        self._finish()

    def _on_skip(self):
        skip_legacy_data(self._info.legacy_dir)
        set_legacy_mode(True)
        self._mark_setup_complete_for_upgrader()
        self._finish()

    def _mark_setup_complete_for_upgrader(self):
        try:
            mark_setup_complete()
        except Exception as e:
            print(f"[WARNING] LegacyMigrationDialog: could not mark setup complete: {e}")

    def _finish(self):
        self.accept()
        if self._on_done:
            self._on_done()


def show_legacy_migration_dialog_if_needed(
    parent: Optional[QWidget],
    on_done: Callable[[], None],
) -> bool:
    from core.legacy_migration import detect_legacy_data

    info = detect_legacy_data()
    if not info.has_meaningful_data:
        return False

    dialog = LegacyMigrationDialog(parent, info, on_done)
    if parent is not None:
        parent._legacy_migration_dialog = dialog
    dialog.exec()
    return True
