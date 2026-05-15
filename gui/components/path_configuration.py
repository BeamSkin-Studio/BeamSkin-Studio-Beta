from __future__ import annotations
import os, platform
from typing import Callable, Optional

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog,
)

from gui.theme   import COLORS, font, drop_shadow
from gui.widgets import AnimButton, GhostButton, HSeparator, SectionHeader
from gui.state   import state

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return key

try:
    from core.settings import (
        set_beamng_paths, get_beamng_install_path,
        get_mods_folder_path, save_settings,
    )
except ImportError:
    def set_beamng_paths(**kw): pass
    def get_beamng_install_path(): return ""
    def get_mods_folder_path(): return ""
    def save_settings(): pass

try:
    from utils.config_helper import (
        get_beamng_default_install_paths,
        get_beamng_mods_default_paths,
    )
except ImportError:
    def get_beamng_default_install_paths(): return []
    def get_beamng_mods_default_paths():    return []


class PathConfigurationSection(QFrame):
    """Embeddable widget for the settings tab."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        notification_callback: Optional[Callable] = None,
    ):
        super().__init__(parent)
        self.notification_callback = notification_callback
        self.system = platform.system()
        self._build()
        self._load_current_paths()

    def _build(self):
        print(f"[DEBUG] _build() called")
        # Use an object-name selector so the rule targets ONLY this frame and
        # does not cascade down to every nested QFrame child inside it.
        self.setObjectName("pathConfigSection")
        self.setStyleSheet(f"""
            #pathConfigSection {{
                background-color: {COLORS['card_bg']};
                border-radius: 12px;
                border: none;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # header
        hdr_row = QHBoxLayout()
        self._hdr_lbl = QLabel(t("settings.beamng_paths"))
        self._hdr_lbl.setFont(font(17, "bold"))
        self._hdr_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        hdr_row.addWidget(self._hdr_lbl, 1)

        platform_emoji = {"Windows": "🪟", "Linux": "🐧", "Darwin": "🍎"}.get(
            self.system, "💻"
        )
        plat_lbl = QLabel(f"{platform_emoji} {self.system}")
        plat_lbl.setFont(font(12))
        plat_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        hdr_row.addWidget(plat_lbl)
        root.addLayout(hdr_row)

        self._desc_lbl = QLabel(t("settings.beamng_paths_desc"))
        self._desc_lbl.setFont(font(13))
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        root.addWidget(self._desc_lbl)
        root.addWidget(HSeparator())

        # BeamNG install path
        root.addWidget(self._path_row(
            label=t("settings.beamng_install"),
            desc=t("settings.beamng_uvpath_desc"),
            attr_name="beamng",
            browse_cb=self._browse_beamng,
        ))

        # Mods folder path
        root.addWidget(self._path_row(
            label=t("settings.beamng_modpath"),
            desc=t("settings.beamng_modpath_desc"),
            attr_name="mods",
            browse_cb=self._browse_mods,
        ))

    def _path_row(
        self,
        label: str,
        desc:  str,
        attr_name: str,
        browse_cb: Callable,
    ) -> QFrame:
        """Build a single path input row."""
        row_frame = QFrame()
        row_frame.setObjectName("pathRow")
        # Scoped to #pathRow so the rule does not bleed into nested children.
        row_frame.setStyleSheet(f"""
            #pathRow {{
                background-color: {COLORS['frame_bg']};
                border-radius: 10px;
                border: none;
            }}
        """)
        inner = QVBoxLayout(row_frame)
        inner.setContentsMargins(16, 14, 16, 14)
        inner.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFont(font(13, "bold"))
        lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        inner.addWidget(lbl)

        d_lbl = QLabel(desc)
        d_lbl.setFont(font(12))
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
        inner.addWidget(d_lbl)

        entry_row = QHBoxLayout()
        entry_row.setSpacing(8)

        entry = QLineEdit()
        entry.setMinimumHeight(34)
        entry.setFont(font(12))
        entry.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:7px;
                padding:4px 10px;
                font-size:12px;
            }}
            QLineEdit:focus {{ border-color:{COLORS['border_focus']}; }}
        """)
        entry_row.addWidget(entry, 1)

        btn = AnimButton(
            t("common.browse"),
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=12, bold=True, padding="6px 14px",
        )
        btn.setFixedHeight(34)
        btn.clicked.connect(browse_cb)
        entry_row.addWidget(btn)
        inner.addLayout(entry_row)

        status = QLabel("")
        status.setFont(font(11))
        status.setStyleSheet("background:transparent;border:none;")
        inner.addWidget(status)

        # stash refs — label/desc/browse button stored for refresh_ui()
        setattr(self, f"_{attr_name}_entry",      entry)
        setattr(self, f"_{attr_name}_status",     status)
        setattr(self, f"_{attr_name}_row_label",  lbl)
        setattr(self, f"_{attr_name}_row_desc",   d_lbl)
        setattr(self, f"_{attr_name}_browse_btn", btn)
        return row_frame


    def refresh_ui(self):
        print(f"[DEBUG] PathConfigurationSection.refresh_ui: updating labels and reloading paths")
        """Update all translatable strings in-place (called on language change)."""
        self._hdr_lbl.setText(t("settings.beamng_paths"))
        self._desc_lbl.setText(t("settings.beamng_paths_desc"))

        self._beamng_row_label.setText(t("settings.beamng_install"))
        self._beamng_row_desc.setText(t("settings.beamng_uvpath_desc"))
        self._beamng_browse_btn.setText(t("common.browse"))

        self._mods_row_label.setText(t("settings.beamng_modpath"))
        self._mods_row_desc.setText(t("settings.beamng_modpath_desc"))
        self._mods_browse_btn.setText(t("common.browse"))

        # Reload saved path values — they may have been set by the setup
        # wizard after this widget was first initialised.
        self._load_current_paths()


    def _load_current_paths(self):
        bp = get_beamng_install_path()
        mp = get_mods_folder_path()
        if bp:
            self._beamng_entry.setText(bp)
            self._validate_beamng(bp, show_success=False)
        if mp:
            self._mods_entry.setText(mp)
            self._validate_mods(mp, show_success=False)

    def reload_paths(self):
        print(f"[DEBUG] PathConfigurationSection.reload_paths: refreshing path entries")
        self._load_current_paths()


    def _browse_beamng(self):
        print(f"[DEBUG] _browse_beamng: opening BeamNG install folder dialog")
        init = get_beamng_install_path() or ""
        if not init or not os.path.exists(init):
            defaults = get_beamng_default_install_paths()
            init = defaults[0] if defaults else os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self, t("settings.beamng_browse_title"), init
        )
        if path and self._validate_beamng(path):
            self._beamng_entry.setText(path)
            set_beamng_paths(beamng_install=path)
            if self.notification_callback:
                self.notification_callback(
                    t("settings.beamng_path_updated"), type="success"
                )

    def _browse_mods(self):
        print(f"[DEBUG] _browse_mods: opening mods folder dialog")
        init = get_mods_folder_path() or ""
        if not init or not os.path.exists(init):
            if self.system == "Windows":
                beamng_current = os.path.join(
                    os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")),
                    "BeamNG", "BeamNG.drive", "current",
                )
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                if os.path.exists(beamng_current):
                    init = beamng_current
                elif os.path.exists(desktop):
                    init = desktop
                else:
                    init = os.path.expanduser("~")
            else:
                defaults = get_beamng_mods_default_paths()
                init = defaults[0] if defaults else os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self, t("settings.mods_browse_title"), init
        )
        if path and self._validate_mods(path):
            self._mods_entry.setText(path)
            set_beamng_paths(mods_folder=path)
            if self.notification_callback:
                self.notification_callback(
                    t("settings.mods_path_updated"), type="success"
                )


    def _status(self, attr: str, text: str, ok: bool):
        color = COLORS["success"] if ok else COLORS["error"]
        lbl: QLabel = getattr(self, f"_{attr}_status")
        lbl.setText(text)
        lbl.setStyleSheet(f"color:{color};background:transparent;")

    def _validate_beamng(self, path: str, show_success: bool = True) -> bool:
        print(f"[DEBUG] _validate_beamng: validating path")
        if not os.path.exists(path):
            self._status("beamng", t("settings.path_not_exist"), False)
            return False
        sys = self.system
        if sys == "Windows":
            ok = (os.path.exists(os.path.join(path, "Bin64", "BeamNG.drive.x64.exe"))
                  or os.path.exists(os.path.join(path, "Bin64", "BeamNG.drive.exe")))
        elif sys == "Linux":
            ok = any(
                os.path.exists(os.path.join(path, p))
                for p in ["BeamNG.drive.x64", "Bin64/BeamNG.drive.x64", "BeamNG"]
            )
        elif sys == "Darwin":
            ok = path.endswith(".app") or os.path.exists(os.path.join(path, "BeamNG.drive"))
        else:
            ok = True
        content_ok = os.path.isdir(os.path.join(path, "content"))
        if not ok or not content_ok:
            self._status("beamng", t("settings.invalid_beamng_install"), False)
            return False
        if show_success:
            self._status("beamng", t("settings.valid_beamng_install"), True)
        else:
            self._beamng_status.setText("")
        return True

    def _validate_mods(self, path: str, show_success: bool = True) -> bool:
        print(f"[DEBUG] _validate_mods: validating mods folder")
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            self._status("mods", t("settings.path_not_exist_or_dir"), False)
            return False
        name = os.path.basename(path).lower()
        if name != "mods":
            self._status("mods", t("settings.mods_must_end_with_mods"), False)
            return False
        if show_success:
            self._status("mods", t("settings.valid_mods_folder"), True)
        else:
            self._mods_status.setText("")
        return True


    def pack(self, **_):
        self.show()

    def pack_forget(self):
        self.hide()
