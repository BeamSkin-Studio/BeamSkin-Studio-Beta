from __future__ import annotations
import os
from typing import Callable, Optional

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QWidget, QLineEdit, QFileDialog, QApplication,
)

from gui.theme      import COLORS, font, drop_shadow, fade_in
from gui.widgets    import AnimButton, GhostButton, HSeparator
from gui.icon_helper import set_window_icon

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return kw.get('default', key)

from core.settings import get_data_dir, mark_setup_complete, set_legacy_mode
from core.legacy_migration import (
    LegacyDataInfo, migrate_all_legacy_data, skip_legacy_data,
)


class LegacyMigrationDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        info: LegacyDataInfo,
        on_done: Callable[[], None],
    ):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        set_window_icon(self)
        self.setModal(True)
        W, H = 560, 480
        self.setFixedSize(W, H)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        self._info      = info
        self._on_done    = on_done
        self._chosen_dir = get_data_dir()

        if parent:
            pg = parent.frameGeometry()
            self.move(pg.x() + (pg.width() - W) // 2, pg.y() + (pg.height() - H) // 2)
        else:
            sg = QApplication.primaryScreen().geometry()
            self.move((sg.width() - W) // 2, (sg.height() - H) // 2)

        self._build()
        fade_in(self._card, 220)


    def _build(self):
        self._card = QFrame(self)
        self._card.setObjectName("legacyMigrationCard")
        self._card.setGeometry(0, 0, 560, 480)
        self._card.setStyleSheet(f"""
            #legacyMigrationCard {{
                background-color: {COLORS['frame_bg']};
                border-radius: 16px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        drop_shadow(self._card, 32, (0, 8))

        root = QVBoxLayout(self._card)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        icon_lbl = QLabel("📦")
        icon_lbl.setFont(font(40))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent;border:none;")
        root.addWidget(icon_lbl)

        title = QLabel(t("legacy_migration.title", default="Data From an Older Version Found"))
        title.setFont(font(19, "bold"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        root.addWidget(title)

        desc = QLabel(t(
            "legacy_migration.desc",
            default="BeamSkin Studio now stores your data in a dedicated folder instead "
                    "of next to the app. We found projects and vehicles from a previous "
                    "install — choose where to keep them and we'll copy everything over. "
                    "Your old files are left untouched.",
        ))
        desc.setFont(font(13))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
        root.addWidget(desc)

        root.addWidget(HSeparator())

        summary = QFrame()
        summary.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: 10px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        s_inner = QVBoxLayout(summary)
        s_inner.setContentsMargins(18, 14, 18, 14)
        s_inner.setSpacing(6)

        found_lbl = QLabel(
            t("legacy_migration.found_at", default="Found at:") + f"\n{self._info.legacy_dir}"
        )
        found_lbl.setFont(font(12))
        found_lbl.setWordWrap(True)
        found_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        s_inner.addWidget(found_lbl)

        stats = QLabel(
            t("legacy_migration.stats",
              default="{vehicles} added vehicle(s) · {projects} saved project(s) · ~{size} KB",
              vehicles=self._info.vehicle_count,
              projects=self._info.project_count,
              size=self._info.approx_size_kb)
        )
        stats.setFont(font(12, "bold"))
        stats.setStyleSheet(f"color:{COLORS['accent_text']};background:transparent;border:none;")
        s_inner.addWidget(stats)
        root.addWidget(summary)

        dest_lbl = QLabel(t("legacy_migration.dest_label", default="Copy data to:"))
        dest_lbl.setFont(font(13, "bold"))
        dest_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        root.addWidget(dest_lbl)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(8)

        self._dest_entry = QLineEdit(self._chosen_dir)
        self._dest_entry.setReadOnly(True)
        self._dest_entry.setMinimumHeight(36)
        self._dest_entry.setFont(font(12))
        self._dest_entry.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:7px;
                padding:4px 10px;
                font-size:12px;
            }}
        """)
        dest_row.addWidget(self._dest_entry, 1)

        browse_btn = AnimButton(
            t("common.browse", default="Browse"),
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=12, bold=True, padding="6px 14px",
        )
        browse_btn.setFixedHeight(36)
        browse_btn.clicked.connect(self._browse_dest)
        dest_row.addWidget(browse_btn)
        root.addLayout(dest_row)

        root.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        skip_btn = GhostButton(
            t("legacy_migration.skip", default="Don't Migrate"), font_size=13
        )
        skip_btn.setMinimumHeight(42)
        skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(skip_btn, 1)

        migrate_btn = AnimButton(
            t("legacy_migration.migrate", default="Migrate My Data"),
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=14, bold=True, padding="8px 24px",
        )
        migrate_btn.setMinimumHeight(42)
        migrate_btn.clicked.connect(self._on_migrate)
        btn_row.addWidget(migrate_btn, 2)

        root.addLayout(btn_row)
        migrate_btn.setFocus()


    def _browse_dest(self):
        path = QFileDialog.getExistingDirectory(
            self,
            t("legacy_migration.browse_title", default="Choose Data Folder"),
            self._chosen_dir,
        )
        if not path:
            return
        if not os.access(path, os.W_OK):
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            return
        super().keyPressEvent(event)


def show_legacy_migration_dialog_if_needed(
    parent: Optional[QWidget],
    on_done: Callable[[], None],
) -> bool:
    from core.legacy_migration import detect_legacy_data

    info = detect_legacy_data()
    if not info.has_meaningful_data:
        return False

    dialog = LegacyMigrationDialog(parent, info, on_done)
    dialog.show()
    return True
