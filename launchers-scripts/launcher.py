"""
launcher.py — BeamSkin Studio splash / dependency installer  (PySide6 edition)
===============================================================================
Replaces the old CustomTkinter LauncherWindow.

Responsibilities:
  1. Check that required Python packages are installed; install any that are
     missing (pip is invoked in a background thread so the UI stays responsive).
  2. Show an animated splash screen while the main app loads.
  3. Launch main.py and close the splash once the main window is visible.

If Python itself is missing the user is directed to python.org — we cannot
bootstrap a Python installer from inside a Python script that isn't running.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.request

# ── stdlib-only bootstrap: install PySide6 if it is somehow absent ───────────
# (Normally install.bat guarantees this; this is a last-resort safety net.)
def _ensure_pyside6() -> None:
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print("[LAUNCHER] PySide6 not found — attempting pip install …")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "PySide6", "--quiet"]
        )
        print("[LAUNCHER] PySide6 installed — restarting launcher …")
        os.execl(sys.executable, sys.executable, *sys.argv)


_ensure_pyside6()

# ── allow importing gui.theme from the project root ───────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# ── now safe to import Qt and theme colors ───────────────────────────────────
from PySide6.QtCore import (Qt, QThread, Signal, QObject,
                             QTimer, QPropertyAnimation, QEasingCurve)
from PySide6.QtGui  import QColor, QFont, QPixmap, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QProgressBar, QMessageBox,
)
from gui.theme import COLORS

_REQUIRED = [
    ("PySide6",   "PySide6"),
    ("Pillow",    "PIL"),
    ("requests",  "requests"),
]


# ─────────────────────────────────────────────────────────────────────────────
# WORKER  — package install in background thread
# ─────────────────────────────────────────────────────────────────────────────

class _InstallSignals(QObject):
    progress = Signal(str, float)   # (message, 0-1)
    finished = Signal(bool, str)    # (success, error_msg)


class _InstallWorker(QThread):
    def __init__(self):
        super().__init__()
        self.signals = _InstallSignals()

    def run(self):
        try:
            missing = []
            for pkg_name, import_name in _REQUIRED:
                try:
                    __import__(import_name)
                except ImportError:
                    missing.append(pkg_name)

            if not missing:
                self.signals.progress.emit("All dependencies ready!", 1.0)
                self.signals.finished.emit(True, "")
                return

            total = len(missing) + 1  # +1 for pip upgrade
            step  = 0

            # Upgrade pip first
            self.signals.progress.emit("Updating pip…", step / total)
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade",
                 "pip", "--quiet"],
                capture_output=True,
                creationflags=(subprocess.CREATE_NO_WINDOW
                               if sys.platform == "win32" else 0),
            )
            step += 1

            for pkg_name, _ in [(p, n) for p, n in _REQUIRED if p in missing]:
                self.signals.progress.emit(f"Installing {pkg_name}…",
                                           step / total)
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install",
                     "--upgrade", pkg_name, "--quiet"],
                    capture_output=True,
                    creationflags=(subprocess.CREATE_NO_WINDOW
                                   if sys.platform == "win32" else 0),
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"pip install {pkg_name} failed:\n"
                        + result.stderr.decode(errors="replace")
                    )
                step += 1

            self.signals.progress.emit("All dependencies installed!", 1.0)
            self.signals.finished.emit(True, "")

        except Exception as exc:
            self.signals.finished.emit(False, str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# SPLASH WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class SplashWindow(QWidget):
    """Frameless splash screen shown while packages are verified and the
    main application window is initialising."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(640, 420)
        self._center()
        self._build_ui()

    # ── layout ────────────────────────────────────────────────────────────── #

    def _build_ui(self):
        # outer card
        card = QFrame(self)
        card.setGeometry(0, 0, 640, 420)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['frame_bg']};
                border-radius: 16px;
                border: 1px solid {COLORS['border']};
            }}
        """)

        col = QVBoxLayout(card)
        col.setContentsMargins(48, 40, 48, 36)
        col.setSpacing(0)
        col.setAlignment(Qt.AlignCenter)

        # logo
        self._logo_lbl = QLabel()
        self._logo_lbl.setAlignment(Qt.AlignCenter)
        self._logo_lbl.setStyleSheet("background:transparent;border:none;")
        self._try_load_logo()
        col.addWidget(self._logo_lbl)
        col.addSpacing(20)

        # title
        title = QLabel("BeamSkin Studio")
        title.setFont(self._font(26, bold=True))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{COLORS['accent']};background:transparent;border:none;"
        )
        col.addWidget(title)
        col.addSpacing(6)

        # subtitle
        sub = QLabel("Professional Skin Modding Tool for BeamNG.drive")
        sub.setFont(self._font(12))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        col.addWidget(sub)
        col.addSpacing(32)

        # status label
        self._status = QLabel("Initialising…")
        self._status.setFont(self._font(13))
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        col.addWidget(self._status)
        col.addSpacing(14)

        # progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['card_bg']};
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['accent']};
                border-radius: 4px;
            }}
        """)
        col.addWidget(self._bar)
        col.addSpacing(28)

        # error/action button (hidden by default)
        self._action_btn = QPushButton("")
        self._action_btn.setFixedHeight(42)
        self._action_btn.setVisible(False)
        self._action_btn.setFont(self._font(13, bold=True))
        self._action_btn.setCursor(Qt.PointingHandCursor)
        col.addWidget(self._action_btn)

        # version / footer
        ver_lbl = QLabel("Loading…")
        ver_lbl.setFont(self._font(10))
        ver_lbl.setAlignment(Qt.AlignCenter)
        ver_lbl.setObjectName("ver_lbl")
        ver_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        col.addWidget(ver_lbl)
        self._ver_lbl = ver_lbl

    # ── helpers ───────────────────────────────────────────────────────────── #

    @staticmethod
    def _font(size: int, bold: bool = False) -> QFont:
        f = QFont("Segoe UI", size)
        if bold:
            f.setBold(True)
        return f

    def _try_load_logo(self):
        """Load the white logo PNG if available; fall back to text emoji."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # launcher.py lives inside launchers-scripts/ (one level down from root)
        parent_dir = os.path.dirname(script_dir)
        logo_path = os.path.join(
            parent_dir, "gui", "Icons", "BeamSkin_Studio_White.png"
        )
        if not os.path.exists(logo_path):
            # try root-level (if launcher.py is in project root)
            logo_path = os.path.join(
                script_dir, "gui", "Icons", "BeamSkin_Studio_White.png"
            )

        if os.path.exists(logo_path):
            px = QPixmap(logo_path).scaled(
                160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._logo_lbl.setPixmap(px)
        else:
            self._logo_lbl.setText("🎨")
            self._logo_lbl.setFont(self._font(56))
            self._logo_lbl.setStyleSheet(
                f"color:{COLORS['accent']};background:transparent;border:none;"
            )

    def _center(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

    # ── public API ────────────────────────────────────────────────────────── #

    def set_status(self, message: str, progress: float = None):
        """Update status label and optional progress bar (0.0–1.0)."""
        self._status.setText(message)
        if progress is not None:
            self._bar.setValue(int(progress * 1000))
        QApplication.processEvents()

    def set_version(self, text: str):
        self._ver_lbl.setText(text)

    def show_error(self, message: str, button_text: str = "Close",
                   on_click=None):
        self._status.setStyleSheet(
            f"color:{COLORS['error']};background:transparent;border:none;"
        )
        self._status.setText(message)
        self._bar.setValue(0)
        self._action_btn.setText(button_text)
        self._action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['error']};
                color: white;
                border-radius: 8px;
                border: none;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #DC2626; }}
        """)
        if on_click:
            try:
                self._action_btn.clicked.disconnect()
            except RuntimeError:
                pass
            self._action_btn.clicked.connect(on_click)
        self._action_btn.setVisible(True)
        QApplication.processEvents()

    def show_choice(self, message: str,
                    yes_text: str, no_text: str,
                    on_yes=None, on_no=None):
        """Show two buttons side by side (e.g. Download / Cancel)."""
        self._status.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._status.setText(message)
        self._bar.setValue(0)

        # reuse action_btn as YES; add a NO button dynamically
        self._action_btn.setText(yes_text)
        self._action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border-radius: 8px;
                border: none;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_hover']}; }}
        """)
        if on_yes:
            try:
                self._action_btn.clicked.disconnect()
            except RuntimeError:
                pass
            self._action_btn.clicked.connect(on_yes)
        self._action_btn.setVisible(True)

        if not hasattr(self, "_no_btn"):
            self._no_btn = QPushButton(no_text)
            self._no_btn.setFixedHeight(42)
            self._no_btn.setFont(self._font(13))
            self._no_btn.setCursor(Qt.PointingHandCursor)
            self._no_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['text_secondary']};
                    border-radius: 8px;
                    border: 1px solid {COLORS['border']};
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['card_bg']};
                    color: {COLORS['text']};
                }}
            """)
            # insert the no button right after action_btn
            layout = self._action_btn.parent().layout()
            idx = layout.indexOf(self._action_btn)
            layout.insertWidget(idx + 1, self._no_btn)
        else:
            self._no_btn.setText(no_text)
            try:
                self._no_btn.clicked.disconnect()
            except RuntimeError:
                pass
            self._no_btn.setVisible(True)

        if on_no:
            self._no_btn.clicked.connect(on_no)

        QApplication.processEvents()

    def hide_buttons(self):
        self._action_btn.setVisible(False)
        if hasattr(self, "_no_btn"):
            self._no_btn.setVisible(False)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SEQUENCE
# ─────────────────────────────────────────────────────────────────────────────

def _launch_main_app(splash: SplashWindow):
    """Launch main.py in the same process (or as subprocess if preferred)."""
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    parent_dir  = os.path.dirname(script_dir)
    main_py     = os.path.join(parent_dir, "main.py")

    if not os.path.exists(main_py):
        # if launcher.py lives at the root level alongside main.py
        main_py = os.path.join(script_dir, "main.py")

    if not os.path.exists(main_py):
        splash.show_error(
            "main.py not found — check your installation.",
            "Close",
            QApplication.quit,
        )
        return

    if sys.platform == "win32":
        subprocess.Popen(
            ["pythonw", main_py],
            cwd=os.path.dirname(main_py),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        subprocess.Popen(
            [sys.executable, main_py],
            cwd=os.path.dirname(main_py),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main():
    app = QApplication(sys.argv)
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    splash = SplashWindow()
    splash.show()
    QApplication.processEvents()

    # Try to read version for footer
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(script_dir, "version.txt"),
        os.path.join(os.path.dirname(script_dir), "version.txt"),
    ]:
        if os.path.exists(candidate):
            try:
                ver = open(candidate).read().strip()
                splash.set_version(f"v{ver}")
            except Exception:
                pass
            break

    worker = _InstallWorker()

    def on_progress(msg: str, pct: float):
        splash.set_status(msg, pct)

    def on_finished(success: bool, error_msg: str):
        if not success:
            splash.show_error(
                f"Setup failed: {error_msg}",
                "Close",
                QApplication.quit,
            )
            return

        splash.set_status("Launching BeamSkin Studio…", 1.0)
        QTimer.singleShot(400, lambda: _launch_and_close(splash))

    worker.signals.progress.connect(on_progress)
    worker.signals.finished.connect(on_finished)
    worker.start()

    sys.exit(app.exec())


def _launch_and_close(splash: SplashWindow):
    _launch_main_app(splash)
    # Give main.py a moment to appear, then close splash
    QTimer.singleShot(200, QApplication.quit)


if __name__ == "__main__":
    main()
