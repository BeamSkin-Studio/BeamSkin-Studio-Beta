import sys
import io
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame,
    QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout,
)

debug_mode_enabled = False
_debug_window: "QDialog | None" = None
_debug_textbox: "QTextEdit | None" = None


class DebugOutput(io.StringIO):
    def __init__(self):
        super().__init__()
        self._previous_stdout = sys.stdout

    def write(self, message: str) -> int:
        if self._previous_stdout is not None:
            try:
                self._previous_stdout.write(message)
            except Exception as _exc:
                print(f"[WARNING] write: {type(_exc).__name__}: {_exc}")

        if debug_mode_enabled and _debug_textbox is not None:
            _msg = message
            QTimer.singleShot(0, lambda m=_msg: _append_debug_text(m))

        return len(message)

    def flush(self):
        if self._previous_stdout and hasattr(self._previous_stdout, "flush"):
            try:
                self._previous_stdout.flush()
            except Exception as _exc:
                print(f"[WARNING] flush: {type(_exc).__name__}: {_exc}")


_COLOR_NORMAL = QColor("#FF8C00")
_COLOR_ERROR  = QColor("#FF3333")

_ERROR_MARKERS = ("[ERROR]", "[WARN]", "[WARNING]", "ERROR", "CRITICAL", "Traceback")


def _append_debug_text(message: str) -> None:
    if _debug_textbox is None:
        return
    try:
        is_error = any(marker in message for marker in _ERROR_MARKERS)
        color = _COLOR_ERROR if is_error else _COLOR_NORMAL

        fmt = QTextCharFormat()
        fmt.setForeground(color)

        timestamp = datetime.now().strftime("%H:%M:%S")
        cursor = _debug_textbox.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(f"[{timestamp}] {message}", fmt)
        _debug_textbox.setTextCursor(cursor)
        _debug_textbox.ensureCursorVisible()
    except Exception as _exc:
        print(f"[WARNING] _append_debug_text: {type(_exc).__name__}: {_exc}")


def create_debug_window(parent, colors: dict, on_close_callback=None) -> None:
    global _debug_window, _debug_textbox, debug_mode_enabled

    if _debug_window is not None and _debug_window.isVisible():
        _debug_window.raise_()
        _debug_window.activateWindow()
        return

    debug_mode_enabled = True

    win = QDialog(parent)
    win.setWindowTitle("Debug Console")
    win.resize(800, 600)
    win.setWindowFlags(
        win.windowFlags()
        | Qt.WindowMaximizeButtonHint
        | Qt.WindowMinimizeButtonHint
    )
    win.setStyleSheet(
        f"background:{colors.get('app_bg', '#0a0a0a')};"
        f"color:{colors.get('text', '#ffffff')};"
    )

    col = QVBoxLayout(win)
    col.setContentsMargins(10, 10, 10, 10)
    col.setSpacing(6)

    header = QFrame()
    header.setStyleSheet(
        f"QFrame {{"
        f"  background:{colors.get('frame_bg', '#1a1a1a')};"
        f"  border-radius:10px;"
        f"  border:none;"
        f"}}"
    )
    h_row = QHBoxLayout(header)
    h_row.setContentsMargins(16, 8, 8, 8)

    title_lbl = QLabel("Debug Console")
    title_lbl.setFont(QFont("", 14, QFont.Bold))
    title_lbl.setStyleSheet("background:transparent;border:none;")
    h_row.addWidget(title_lbl)
    h_row.addStretch()

    _btn_style = (
        f"QPushButton {{"
        f"  background:{colors.get('card_bg', '#1e1e1e')};"
        f"  color:{colors.get('text', '#ffffff')};"
        f"  border-radius:6px;border:none;padding:4px 14px;"
        f"}}"
        f"QPushButton:hover {{"
        f"  background:{colors.get('card_hover', '#2a2a2a')};"
        f"}}"
    )

    def _clear():
        _debug_textbox.clear()
        print("[DEBUG] Console cleared")

    def _copy():
        QApplication.clipboard().setText(_debug_textbox.toPlainText())
        print("[DEBUG] Content copied to clipboard")

    copy_btn = QPushButton("Copy All")
    copy_btn.setFixedSize(84, 30)
    copy_btn.setStyleSheet(_btn_style)
    copy_btn.clicked.connect(_copy)
    h_row.addWidget(copy_btn)

    clear_btn = QPushButton("Clear")
    clear_btn.setFixedSize(72, 30)
    clear_btn.setStyleSheet(_btn_style)
    clear_btn.clicked.connect(_clear)
    h_row.addWidget(clear_btn)

    col.addWidget(header)

    textbox = QTextEdit()
    textbox.setReadOnly(True)
    textbox.setFont(QFont("Consolas", 10))
    textbox.setStyleSheet(
        "QTextEdit {"
        "  background:#111111;"
        "  color:#FF8C00;"
        "  border-radius:8px;border:none;"
        "  padding:8px;"
        "}"
    )
    col.addWidget(textbox)
    _debug_textbox = textbox

    def _on_close():
        global debug_mode_enabled, _debug_window, _debug_textbox
        debug_mode_enabled = False
        _debug_window = None
        _debug_textbox = None
        if isinstance(sys.stdout, DebugOutput):
            sys.stdout = sys.stdout._previous_stdout
        if on_close_callback and callable(on_close_callback):
            on_close_callback()

    win.finished.connect(lambda _result: _on_close())

    _debug_window = win
    win.show()
    print("[DEBUG] Debug console opened")


def toggle_debug_mode(app, colors: dict, on_close=None) -> None:
    global debug_mode_enabled

    if debug_mode_enabled:
        if _debug_window is not None and _debug_window.isVisible():
            _debug_window.close()
        else:
            debug_mode_enabled = False
            if isinstance(sys.stdout, DebugOutput):
                sys.stdout = sys.stdout._previous_stdout
            if on_close and callable(on_close):
                on_close()
    else:
        create_debug_window(app, colors, on_close_callback=on_close)
        if not isinstance(sys.stdout, DebugOutput):
            sys.stdout = DebugOutput()
        print("[DEBUG] Debug console activated — output redirection enabled")


def setup_universal_scroll_handler(app) -> None:
    pass
