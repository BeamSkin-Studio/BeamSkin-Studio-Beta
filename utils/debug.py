"""Debug utilities — PySide6 edition"""
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


# ── stdout redirect ─────────────────────────────────────────────────────────

class DebugOutput(io.StringIO):
    """
    Custom stdout that echoes to the real terminal AND posts each write to the
    debug console via QTimer.singleShot so it is always delivered on the main
    thread, regardless of which thread calls print().
    """

    def __init__(self):
        super().__init__()
        # Keep a direct reference to the real terminal so we can always write
        # even after sys.stdout has been replaced.
        self._terminal = sys.__stdout__

    def write(self, message: str) -> int:
        # Always echo to the real terminal first.
        if self._terminal is not None:
            try:
                self._terminal.write(message)
            except Exception:
                pass

        # Forward to the GUI on the main thread.
        if debug_mode_enabled and _debug_textbox is not None:
            # Capture the value now; the lambda must not close over a mutable.
            _msg = message
            QTimer.singleShot(0, lambda m=_msg: _append_debug_text(m))

        return len(message)

    def flush(self):
        if self._terminal and hasattr(self._terminal, "flush"):
            self._terminal.flush()


_COLOR_NORMAL = QColor("#FF8C00")   # orange — all regular debug output
_COLOR_ERROR  = QColor("#FF3333")   # red   — lines that contain error/warning markers

_ERROR_MARKERS = ("[ERROR]", "[WARN]", "[WARNING]", "ERROR", "CRITICAL", "Traceback")


def _append_debug_text(message: str) -> None:
    """Appends coloured text to the debug textbox. MUST be called from the main thread."""
    global _debug_textbox
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
    except Exception:
        pass


# ── window ───────────────────────────────────────────────────────────────────

def create_debug_window(parent, colors: dict, on_close_callback=None) -> None:
    """Create (or raise) the debug console window using PySide6."""
    global _debug_window, _debug_textbox, debug_mode_enabled

    # If already open, just bring it to the front.
    if _debug_window is not None and _debug_window.isVisible():
        _debug_window.raise_()
        _debug_window.activateWindow()
        return

    debug_mode_enabled = True

    # ── window ──
    win = QDialog(parent)
    win.setWindowTitle("Debug Console")
    win.resize(800, 600)
    # Allow the dialog to be maximised / minimised like a normal window.
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

    # ── header bar ──
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

    # ── text area ──
    # Always use a dark terminal background regardless of the app theme —
    # orange-on-white in light mode is nearly unreadable.
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

    # ── close handler ──
    def _on_close():
        global debug_mode_enabled, _debug_window, _debug_textbox
        debug_mode_enabled = False
        _debug_window = None
        _debug_textbox = None
        # Restore the real stdout if we replaced it.
        if isinstance(sys.stdout, DebugOutput):
            sys.stdout = sys.__stdout__
        if on_close_callback and callable(on_close_callback):
            on_close_callback()

    win.finished.connect(lambda _result: _on_close())

    _debug_window = win
    win.show()
    print("[DEBUG] Debug console opened")


# ── public toggle ─────────────────────────────────────────────────────────────

def toggle_debug_mode(app, colors: dict, on_close=None) -> None:
    """Toggle the debug console on or off."""
    global debug_mode_enabled, _debug_window

    if debug_mode_enabled:
        # Close if it's open.
        if _debug_window is not None and _debug_window.isVisible():
            _debug_window.close()   # triggers finished → _on_close
        else:
            # Window was already gone; clean up state manually.
            debug_mode_enabled = False
            if isinstance(sys.stdout, DebugOutput):
                sys.stdout = sys.__stdout__
            if on_close and callable(on_close):
                on_close()
    else:
        create_debug_window(app, colors, on_close_callback=on_close)
        # Redirect stdout only if not already redirected.
        if not isinstance(sys.stdout, DebugOutput):
            sys.stdout = DebugOutput()
        print("[DEBUG] Debug console activated — output redirection enabled")


# ── scroll helper (kept for compatibility) ────────────────────────────────────

def setup_universal_scroll_handler(app) -> None:
    """
    No-op in the PySide6 build — QScrollArea handles wheel events natively.
    Kept so any call sites that import this function don't break.
    """
    pass
