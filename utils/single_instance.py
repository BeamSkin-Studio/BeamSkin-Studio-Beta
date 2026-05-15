"""
Single Instance Lock – Prevents multiple instances of BeamSkin Studio from running.
Cross-platform implementation for Windows, Linux, and macOS.
Uses PySide6 QMessageBox instead of tkinter (Qt Quick migration).
"""
import os
import sys
import tempfile
import platform

print(f"[DEBUG] Loading class: SingleInstanceLock")


class SingleInstanceLock:
    """Ensures only one instance of the application can run at a time."""

    def __init__(self, app_name: str = "BeamSkinStudio"):
        print(f"[DEBUG] SingleInstanceLock.__init__ called")
        self.app_name       = app_name
        self.lock_file      = None
        self.lock_file_path = None
        self.file_handle    = None

        if sys.platform in ("win32", "darwin"):
            lock_dir = tempfile.gettempdir()
        else:
            lock_dir = os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())

        self.lock_file_path = os.path.join(lock_dir, f"{app_name}.lock")
        print(f"[DEBUG] Lock file path: {self.lock_file_path}")

    # ------------------------------------------------------------------ #
    def acquire(self) -> bool:
        print(f"[DEBUG] acquire called")
        try:
            if os.path.exists(self.lock_file_path):
                try:
                    with open(self.lock_file_path, "r") as f:
                        pid = int(f.read().strip())

                    if self._is_process_running(pid):
                        print(f"[DEBUG] Another instance is running (PID: {pid})")
                        return False
                    else:
                        print(f"[DEBUG] Removing stale lock file (PID: {pid} not running)")
                        os.remove(self.lock_file_path)
                except (ValueError, IOError):
                    print(f"[DEBUG] Removing invalid lock file")
                    try:
                        os.remove(self.lock_file_path)
                    except Exception:
                        pass

            with open(self.lock_file_path, "w") as f:
                f.write(str(os.getpid()))

            if sys.platform != "win32":
                try:
                    import fcntl
                    self.file_handle = open(self.lock_file_path, "r")
                    fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    print(f"[DEBUG] File lock acquired using fcntl")
                except ImportError:
                    print(f"[DEBUG] fcntl not available, using PID-based locking only")
                except IOError:
                    print(f"[DEBUG] Could not acquire file lock, another instance may be running")
                    if self.file_handle:
                        self.file_handle.close()
                    return False

            self.lock_file = self.lock_file_path
            print(f"[DEBUG] Lock acquired: {self.lock_file_path}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to acquire lock: {e}")
            return True  # fail-open so the app can still start

    # ------------------------------------------------------------------ #
    def release(self):
        print(f"[DEBUG] release called")
        if self.file_handle:
            try:
                import fcntl
                fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_UN)
                self.file_handle.close()
                print(f"[DEBUG] File lock released")
            except Exception:
                pass

        if self.lock_file and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                print(f"[DEBUG] Lock released: {self.lock_file}")
            except Exception as e:
                print(f"[ERROR] Failed to release lock: {e}")

    # ------------------------------------------------------------------ #
    def _is_process_running(self, pid: int) -> bool:
        try:
            if sys.platform == "win32":
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                return str(pid) in result.stdout
            else:
                os.kill(pid, 0)
                return True
        except (OSError, Exception):
            return False

    # ------------------------------------------------------------------ #
    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ---------------------------------------------------------------------------
# High-level helper used by main.py
# ---------------------------------------------------------------------------
def check_single_instance(app_name: str = "BeamSkinStudio") -> bool:
    """
    Check if another instance is running.
    Shows a QMessageBox if so, and tries to bring the existing window forward.
    Returns True if this is the only instance, False otherwise.
    """
    global _global_lock
    print(f"[DEBUG] check_single_instance called")

    _global_lock = SingleInstanceLock(app_name)

    if not _global_lock.acquire():
        print(f"[DEBUG] Another instance detected, attempting to bring it to front...")

        # ── Try to focus the existing window ─────────────────────────── #
        try:
            if sys.platform == "win32":
                try:
                    import win32gui, win32con

                    def _cb(hwnd, _):
                        if app_name.lower() in win32gui.GetWindowText(hwnd).lower():
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                            return False
                        return True

                    win32gui.EnumWindows(_cb, None)
                except ImportError:
                    print("[DEBUG] pywin32 not available, cannot bring window to front")

            elif sys.platform in ("linux", "linux2"):
                import subprocess
                result = subprocess.run(
                    ["wmctrl", "-l"], capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if "BeamSkin Studio" in line or app_name in line:
                            window_id = line.split()[0]
                            subprocess.run(["wmctrl", "-i", "-a", window_id])
                            print(f"[DEBUG] Activated existing window using wmctrl")
                            break

            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(
                    [
                        "osascript", "-e",
                        f'tell application "System Events" to set frontmost of every process '
                        f'whose name contains "{app_name}" to true',
                    ],
                    timeout=2,
                )
                print(f"[DEBUG] Activated existing window using osascript")

        except Exception as e:
            print(f"[DEBUG] Could not bring existing window to front: {e}")

        # ── Show QMessageBox error dialog ─────────────────────────────── #
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            # Reuse an existing QApplication if one is already running
            q_app = QApplication.instance() or QApplication(sys.argv)

            msg = QMessageBox()
            msg.setWindowTitle("Already Running")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText(
                f"{app_name} is already running!\n\n"
                "Please close the existing instance before starting a new one."
            )
            msg.setWindowFlags(msg.windowFlags() | 0x00040000)  # WindowStaysOnTopHint
            msg.exec()

        except Exception as e:
            # Last resort: plain console output
            print(f"[ERROR] Failed to show dialog: {e}")
            print(f"[ERROR] {app_name} is already running!")

        return False

    return True


# ---------------------------------------------------------------------------
# Global lock management
# ---------------------------------------------------------------------------
_global_lock: SingleInstanceLock | None = None


def acquire_global_lock(app_name: str = "BeamSkinStudio") -> bool:
    print(f"[DEBUG] acquire_global_lock called")
    global _global_lock
    _global_lock = SingleInstanceLock(app_name)
    return _global_lock.acquire()


def release_global_lock():
    print(f"[DEBUG] release_global_lock called")
    global _global_lock
    if _global_lock:
        _global_lock.release()
