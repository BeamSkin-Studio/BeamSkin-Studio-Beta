"""
BeamSkin Studio - Quick Launcher  (PySide6 edition)
Cross-platform splash screen and app launcher.
Replaces the customtkinter version — no extra dependencies beyond PySide6.
"""

import os
import platform
import subprocess
import sys
import tempfile

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

# ── Constants ─────────────────────────────────────────────────────────────────

READY_SIGNAL     = os.path.join(tempfile.gettempdir(), "BeamSkinStudio_ready.signal")
POLL_INTERVAL_MS = 100    # how often to check for the signal (ms)
POLL_TIMEOUT_MS  = 15_000 # close anyway after this long if signal never arrives (ms)
PROGRESS_STEP_MS = 21     # timer interval per progress tick (matches original)

COLORS = {
    "bg":             "#0a0a0a",
    "frame_bg":       "#141414",
    "card":           "#1e1e1e",
    "accent":         "#e67e22",
    "text":           "#f5f5f5",
    "text_secondary": "#999999",
}

print(f"[DEBUG] Loading class: QuickLauncher")
print(f"[DEBUG] Platform: {platform.system()}")


# ── Splash window ─────────────────────────────────────────────────────────────

class SplashWindow(QWidget):
    """Frameless 600×450 splash with logo, subtitle labels, and progress bar."""

    BORDER_WIDTH = 2

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(600, 450)
        self.setStyleSheet(f"background-color: {COLORS['bg']};")

        self._build_ui()
        self._center()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            self.BORDER_WIDTH, self.BORDER_WIDTH,
            self.BORDER_WIDTH, self.BORDER_WIDTH,
        )
        outer.setSpacing(0)

        # Inner content area
        inner = QWidget()
        inner.setStyleSheet(f"background-color: {COLORS['bg']};")
        outer.addWidget(inner)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        # Logo
        logo_lbl = self._make_logo_label()
        layout.addWidget(logo_lbl, alignment=Qt.AlignHCenter)
        layout.addSpacing(20)

        # Tagline
        tagline = QLabel("Professional Skin Modding Tool")
        tagline.setFont(self._font(13))
        tagline.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        tagline.setAlignment(Qt.AlignCenter)
        layout.addWidget(tagline)
        layout.addSpacing(25)

        # Loading label
        loading = QLabel("Loading BeamSkin Studio...")
        loading.setFont(self._font(15, bold=True))
        loading.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        loading.setAlignment(Qt.AlignCenter)
        layout.addWidget(loading)
        layout.addSpacing(25)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedSize(420, 8)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['card']};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['accent']};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignHCenter)
        layout.addSpacing(15)

        # "Please wait" label
        wait_lbl = QLabel("Please wait...")
        wait_lbl.setFont(self._font(11))
        wait_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        wait_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(wait_lbl)

    def _make_logo_label(self) -> QLabel:
        lbl = QLabel()
        lbl.setFixedSize(200, 200)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: transparent;")

        logo_path = self._find_logo()
        if logo_path:
            px = QPixmap(logo_path).scaled(
                200, 200,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            lbl.setPixmap(px)
            print(f"[DEBUG] Loaded logo from: {logo_path}")
        else:
            lbl.setText("🎨")
            lbl.setFont(self._font(72))
            lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
            print("[DEBUG] Logo not found — using fallback emoji")

        return lbl

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _find_logo() -> str | None:
        """Return logo path relative to this script's parent directory, or None."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        candidate = os.path.join(parent_dir, "gui", "Icons", "BeamSkin_Studio_White.png")
        return candidate if os.path.exists(candidate) else None

    @staticmethod
    def _font(size: int, bold: bool = False) -> QFont:
        f = QFont()
        f.setPointSize(size)
        if bold:
            f.setBold(True)
        return f

    def _center(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

    # ── Accent border (painted, not via stylesheet, to avoid layout issues) ──

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(QColor(COLORS["accent"]))
        pen.setWidth(self.BORDER_WIDTH)
        painter.setPen(pen)
        # inset by half the pen width so it's fully inside the widget
        offset = self.BORDER_WIDTH // 2
        painter.drawRect(
            offset, offset,
            self.width()  - self.BORDER_WIDTH,
            self.height() - self.BORDER_WIDTH,
        )


# ── Launcher controller ───────────────────────────────────────────────────────

class QuickLauncher:
    def __init__(self):
        print("[DEBUG] __init__ called")

        self.app = QApplication.instance() or QApplication(sys.argv)

        self.launch_main_app()

        self.window = SplashWindow()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

        self._progress_step   = 0
        self._poll_elapsed_ms = 0

        self._progress_timer = QTimer()
        self._progress_timer.setInterval(PROGRESS_STEP_MS)
        self._progress_timer.timeout.connect(self._on_progress_tick)

        self._poll_timer = QTimer()
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_for_ready)

    # ── Subprocess ────────────────────────────────────────────────────────────

    def launch_main_app(self):
        print("[DEBUG] launch_main_app called - launching main.py NOW")

        script_dir  = os.path.dirname(os.path.abspath(__file__))
        parent_dir  = os.path.dirname(script_dir)
        main_py     = os.path.join(parent_dir, "main.py")
        system      = platform.system()

        if system == "Windows":
            self.process = subprocess.Popen(
                ["pythonw", main_py],
                cwd=parent_dir,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            self.process = subprocess.Popen(
                ["python3", main_py],
                cwd=parent_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        print(f"[DEBUG] main.py launched, PID: {self.process.pid}")

    # ── Progress animation ────────────────────────────────────────────────────

    def _on_progress_tick(self):
        self._progress_step += 1
        self.window.progress_bar.setValue(self._progress_step)

        if self._progress_step >= 100:
            self._progress_timer.stop()
            print("[DEBUG] Progress complete, waiting for ready signal...")
            self._poll_timer.start()

    # ── Ready-signal polling ──────────────────────────────────────────────────

    def _poll_for_ready(self):
        self._poll_elapsed_ms += POLL_INTERVAL_MS

        if os.path.exists(READY_SIGNAL):
            print(f"[DEBUG] Ready signal received after ~{self._poll_elapsed_ms}ms — closing splash")
            try:
                os.remove(READY_SIGNAL)
            except Exception:
                pass
            self._close()
            return

        if self._poll_elapsed_ms >= POLL_TIMEOUT_MS:
            print(f"[DEBUG] Ready signal timeout ({POLL_TIMEOUT_MS}ms) — closing splash anyway")
            self._close()

    def _close(self):
        self._poll_timer.stop()
        self.window.close()
        self.app.quit()

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self):
        print("[DEBUG] run called")
        self._progress_timer.start()
        sys.exit(self.app.exec())


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    launcher = QuickLauncher()
    launcher.run()
