from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QWidget

from core.model_preview import exporter_mod
from gui.theme import COLORS, font
from gui.components.dialog_kit import (
    DialogShell, body_label, input_qss, lbl_qss, make_panel,
    outline_button, primary_button, section_header,
)

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
    return str(t(key, default=default, **kw)).strip()


def _step_badge(number: int) -> QLabel:
    lbl = QLabel(str(number))
    lbl.setFixedSize(22, 22)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFont(font(10, "bold"))
    lbl.setStyleSheet(f"""
        QLabel {{
            color:{COLORS['accent']};
            background:{COLORS.get('accent_dim', COLORS['frame_bg'])};
            border:1px solid {COLORS['accent']};
            border-radius:11px;
        }}
    """)
    return lbl


class ExporterModDialog(DialogShell):
    INSTALL = "install"
    OPEN = "open"
    LOCATE = "locate"
    BROWSE = "browse"
    CLOSE = "close"

    def __init__(
        self,
        parent: Optional[QWidget],
        state: str,
        carid: str,
        app_name: str,
        export_folder: str,
        has_source: bool,
        first_use: bool,
    ):
        status_text = {
            exporter_mod.MISSING:   _t("model_preview.status_missing", "Not installed"),
            exporter_mod.OUTDATED:  _t("model_preview.status_outdated", "Update available"),
            exporter_mod.INSTALLED: _t("model_preview.status_installed", "Installed"),
        }.get(state, "")

        super().__init__(
            parent,
            _t("model_preview.exporter_title", "BeamNG exporter mod"),
            620, icon="🧩", subtitle=status_text,
        )
        self.choice = self.CLOSE
        self._state = state

        ok_color = COLORS.get("success", COLORS["accent"])
        warn_color = COLORS.get("warning", COLORS["accent"])

        self.body.addWidget(body_label(
            _t("model_preview.exporter_needs",
               "Loading BeamNG parts needs the BeamSkin Studio exporter mod, a small UI app "
               "that runs inside BeamNG and writes the parts of the spawned vehicle to a file."),
            secondary=False, size=12,
        ))

        if state == exporter_mod.MISSING and has_source:
            note, color, mark = _t(
                "model_preview.exporter_not_installed",
                "It is not installed in your BeamNG mods folder yet."), warn_color, "⚠"
        elif state == exporter_mod.MISSING:
            note, color, mark = _t(
                "model_preview.exporter_folder_not_found",
                "The mod folder was not found next to the app. Locate it manually, or copy "
                "beamskin_studio_exporter_mod into your BeamNG mods/unpacked folder."), warn_color, "⚠"
        elif state == exporter_mod.OUTDATED:
            note, color, mark = _t(
                "model_preview.exporter_outdated",
                "A newer version of the exporter mod is available."), warn_color, "⚠"
        elif first_use:
            note, color, mark = _t(
                "model_preview.exporter_no_export",
                "No export for this vehicle yet."), warn_color, "ℹ"
        else:
            note, color, mark = _t(
                "model_preview.exporter_installed",
                "The exporter mod is installed."), ok_color, "✓"
        self.body.addWidget(self._note_row(mark, note, color))

        header_text = (_t("model_preview.after_install_title", "After installing")
                       if state == exporter_mod.MISSING
                       else _t("model_preview.how_to_title", "How to export"))
        self.body.addWidget(section_header(header_text))

        panel, p_lay = make_panel("exporterSteps", margins=(14, 12, 14, 12), spacing=10)
        vehicle = carid or _t("model_preview.the_vehicle", "the vehicle")
        steps = (
            _t("model_preview.step_spawn",
               "Start BeamNG.drive (restart it if it was already open) and spawn {vehicle} "
               "with the parts you want to preview.", vehicle=vehicle),
            _t("model_preview.step_export",
               "Open the UI apps menu (Vehicle Info category), add \"{app}\" to your layout, "
               "pick a preset name and press \"Export current vehicle parts\".", app=app_name),
            _t("model_preview.step_load",
               "Come back here, click {button} and pick the preset's .json file.",
               button=_t("uv_exporter.load_parts", "Load BeamNG parts…").rstrip("….")),
        )
        for i, text in enumerate(steps, 1):
            row = QHBoxLayout()
            row.setSpacing(12)
            row.addWidget(_step_badge(i), 0, Qt.AlignTop)
            lbl = QLabel(text)
            lbl.setFont(font(11))
            lbl.setWordWrap(True)
            lbl.setStyleSheet(lbl_qss())
            row.addWidget(lbl, 1)
            p_lay.addLayout(row)
        self.body.addWidget(panel)

        if export_folder:
            self.body.addWidget(section_header(
                _t("model_preview.export_folder_title", "Export folder")))
            path_edit = QLineEdit(export_folder)
            path_edit.setReadOnly(True)
            path_edit.setMinimumHeight(34)
            path_edit.setStyleSheet(input_qss())
            path_edit.setCursorPosition(0)
            self.body.addWidget(path_edit)

        close_btn = outline_button(_t("model_preview.btn_close", "Close"), height=38, font_size=12)
        close_btn.clicked.connect(lambda: self._finish(self.CLOSE))
        self.footer.addWidget(close_btn)

        open_text = {
            exporter_mod.MISSING:   _t("model_preview.btn_show_mod_folder", "Show mod folder"),
            exporter_mod.OUTDATED:  _t("model_preview.btn_show_installed", "Show installed mod"),
            exporter_mod.INSTALLED: _t("model_preview.btn_show_export_folder", "Show export folder"),
        }.get(state, "")
        if open_text and not (state == exporter_mod.MISSING and not has_source):
            open_btn = outline_button(open_text, height=38, font_size=12)
            open_btn.clicked.connect(lambda: self._finish(self.OPEN))
            self.footer.addWidget(open_btn)

        self.footer.addStretch(1)

        primary_action = None
        if state == exporter_mod.MISSING:
            primary_action = (self.INSTALL, _t("model_preview.btn_install", "Install to BeamNG")) \
                if has_source else (self.LOCATE, _t("model_preview.btn_locate", "Locate mod folder…"))
        elif state == exporter_mod.OUTDATED:
            primary_action = (self.INSTALL, _t("model_preview.btn_update", "Update"))

        browse_text = _t("model_preview.btn_browse", "Browse for export…")
        if primary_action is None:
            browse_btn = primary_button(browse_text, height=38, font_size=12)
        else:
            browse_btn = outline_button(browse_text, height=38, font_size=12)
        browse_btn.clicked.connect(lambda: self._finish(self.BROWSE))
        self.footer.addWidget(browse_btn)

        default_btn = browse_btn
        if primary_action is not None:
            action, text = primary_action
            main_btn = primary_button(text, height=38, font_size=12)
            main_btn.clicked.connect(lambda _=False, a=action: self._finish(a))
            self.footer.addWidget(main_btn)
            default_btn = main_btn

        self.add_footer()
        default_btn.setDefault(True)
        default_btn.setFocus()

    def _note_row(self, mark: str, text: str, color: str):
        panel, lay = make_panel("exporterNote", margins=(12, 10, 12, 10), spacing=0, inset=True)
        row = QHBoxLayout()
        row.setSpacing(10)
        icon = QLabel(mark)
        icon.setFont(font(13, "bold"))
        icon.setStyleSheet(f"color:{color};background:transparent;border:none;")
        row.addWidget(icon, 0, Qt.AlignTop)
        lbl = QLabel(text)
        lbl.setFont(font(11))
        lbl.setWordWrap(True)
        lbl.setStyleSheet(lbl_qss())
        row.addWidget(lbl, 1)
        lay.addLayout(row)
        return panel

    def _finish(self, choice: str):
        self.choice = choice
        self.accept()


def show_notice(parent: Optional[QWidget], title: str, text: str,
                icon: str = "⚠️", warn: bool = True) -> None:
    dlg = DialogShell(
        parent, title, 460, icon=icon,
        accent=COLORS.get("warning", COLORS["accent"]) if warn else None,
    )
    dlg.body.addWidget(body_label(text, secondary=False, size=12))
    ok = primary_button(_t("model_preview.btn_ok", "OK"), height=38, font_size=12)
    ok.clicked.connect(dlg.accept)
    dlg.footer.addWidget(ok, 1)
    dlg.add_footer()
    ok.setFocus()
    dlg.exec()


def _mods_folder(parent: Optional[QWidget], ask: bool = False) -> str:
    try:
        from core.settings import get_mods_folder_path
        folder = get_mods_folder_path() or ""
    except Exception:
        folder = ""
    if folder and os.path.isdir(folder):
        return folder
    if not ask:
        return ""
    return QFileDialog.getExistingDirectory(
        parent, _t("model_preview.select_mods_folder", "Select your BeamNG mods folder"),
        os.path.expanduser("~"))


def _open_path(path: str) -> None:
    if path and os.path.exists(path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def run_exporter_dialog(parent: Optional[QWidget], carid: str, first_use: bool) -> bool:
    while True:
        mods = _mods_folder(parent)
        state = exporter_mod.status(mods) if mods else exporter_mod.MISSING
        source = exporter_mod.bundled_source()
        target = exporter_mod.installed_path(mods)
        folder = exporter_mod.export_folder(mods, carid)
        name = exporter_mod.app_name(target if os.path.isdir(target or "") else "")

        dlg = ExporterModDialog(parent, state, carid, name, folder,
                                has_source=bool(source), first_use=first_use)
        dlg.exec()
        action = dlg.choice

        if action == ExporterModDialog.BROWSE:
            return first_use
        if action == ExporterModDialog.OPEN:
            if state == exporter_mod.INSTALLED:
                if folder:
                    os.makedirs(folder, exist_ok=True)
                _open_path(folder)
            elif state == exporter_mod.OUTDATED:
                _open_path(target)
            else:
                _open_path(source)
            continue
        if action == ExporterModDialog.LOCATE:
            picked = QFileDialog.getExistingDirectory(
                parent,
                _t("model_preview.select_exporter_folder",
                   "Select the beamskin_studio_exporter_mod folder"),
                os.path.expanduser("~"))
            if picked and exporter_mod.valid_source(picked):
                exporter_mod.remember_source(picked)
            elif picked:
                show_notice(
                    parent,
                    _t("model_preview.not_exporter_title", "Not the exporter mod"),
                    _t("model_preview.not_exporter", "That folder has no ui or lua folder inside."))
            continue
        if action == ExporterModDialog.INSTALL:
            mods_folder = _mods_folder(parent, ask=True)
            if not mods_folder:
                continue
            try:
                exporter_mod.install(mods_folder, source)
            except (OSError, ValueError) as e:
                show_notice(
                    parent,
                    _t("model_preview.install_failed_title", "Could not install"),
                    _t("model_preview.install_failed",
                       "{error}\n\nClose BeamNG and try again, or copy the folder manually to:\n{folder}",
                       error=e, folder=exporter_mod.unpacked_dir(mods_folder)))
            continue
        return False


def exporter_gate(parent: Optional[QWidget], carid: str) -> bool:
    mods = _mods_folder(parent)
    if exporter_mod.has_export(exporter_mod.export_folder(mods, carid)):
        return True
    return run_exporter_dialog(parent, carid, first_use=True)
