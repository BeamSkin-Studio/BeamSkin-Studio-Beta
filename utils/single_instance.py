import os
import sys
import tempfile


class SingleInstanceLock:
    def __init__(self, app_name: str = "BeamSkinStudio"):
        self.app_name       = app_name
        self.lock_file      = None
        self.lock_file_path = None
        self.file_handle    = None

        if sys.platform in ("win32", "darwin"):
            lock_dir = tempfile.gettempdir()
        else:
            lock_dir = os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())

        self.lock_file_path = os.path.join(lock_dir, f"{app_name}.lock")

    def acquire(self) -> bool:
        try:
            if sys.platform == "win32":
                self.file_handle = open(self.lock_file_path, "a+")
                try:
                    import msvcrt
                    self.file_handle.seek(0)
                    msvcrt.locking(self.file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                except ImportError:
                    print("[DEBUG] SingleInstanceLock.acquire: msvcrt not available, cannot enforce single instance")
                except OSError as _exc:
                    print(f"[WARNING] acquire: {type(_exc).__name__}: {_exc}")
                    self.file_handle.close()
                    self.file_handle = None
                    return False
            else:
                self.file_handle = open(self.lock_file_path, "a+")
                try:
                    import fcntl
                    fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except ImportError:
                    print("[DEBUG] SingleInstanceLock.acquire: fcntl not available, cannot enforce single instance")
                except OSError as _exc:
                    print(f"[WARNING] acquire: {type(_exc).__name__}: {_exc}")
                    self.file_handle.close()
                    self.file_handle = None
                    return False

            self.file_handle.seek(0)
            self.file_handle.truncate()
            self.file_handle.write(str(os.getpid()))
            self.file_handle.flush()

            self.lock_file = self.lock_file_path
            print(f"[DEBUG] SingleInstanceLock: lock acquired at {self.lock_file_path}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to acquire lock: {e}")
            return True

    def release(self):
        if self.file_handle:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self.file_handle.seek(0)
                    msvcrt.locking(self.file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_UN)
                self.file_handle.close()
            except Exception as _exc:
                print(f"[WARNING] release: {type(_exc).__name__}: {_exc}")

        if self.lock_file and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                print(f"[DEBUG] SingleInstanceLock: lock released at {self.lock_file}")
            except Exception as e:
                print(f"[ERROR] Failed to release lock: {e}")

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def check_single_instance(app_name: str = "BeamSkinStudio") -> bool:
    global _global_lock

    _global_lock = SingleInstanceLock(app_name)

    if not _global_lock.acquire():
        print("[DEBUG] check_single_instance: another instance detected, attempting to bring it to front")

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
                    print("[DEBUG] check_single_instance: pywin32 not available, cannot bring window to front")

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

        except Exception as e:
            print(f"[DEBUG] check_single_instance: could not bring existing window to front: {e}")

        return False

    return True


_global_lock: SingleInstanceLock | None = None


def acquire_global_lock(app_name: str = "BeamSkinStudio") -> bool:
    global _global_lock
    _global_lock = SingleInstanceLock(app_name)
    return _global_lock.acquire()


def release_global_lock():
    if _global_lock:
        _global_lock.release()
