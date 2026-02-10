"""
Single Instance Lock - Prevents multiple instances of BeamSkin Studio from running
Cross-platform implementation for Windows, Linux, and macOS
"""
import os
import sys
import tempfile
import platform

print(f"[DEBUG] Loading class: SingleInstanceLock")


class SingleInstanceLock:
    """Ensures only one instance of the application can run at a time"""
    
    def __init__(self, app_name="BeamSkinStudio"):
        print(f"[DEBUG] __init__ called")
        self.app_name = app_name
        self.lock_file = None
        self.lock_file_path = None
        self.file_handle = None  # For file locking on Unix systems
        
        # Platform-specific lock file location
        if sys.platform == "win32":
            # Windows: Use temp directory
            lock_dir = tempfile.gettempdir()
        elif sys.platform == "darwin":
            # macOS: Use temp directory
            lock_dir = tempfile.gettempdir()
        else:
            # Linux: Use /tmp or XDG_RUNTIME_DIR
            lock_dir = os.environ.get('XDG_RUNTIME_DIR', tempfile.gettempdir())
        
        self.lock_file_path = os.path.join(lock_dir, f"{app_name}.lock")
        print(f"[DEBUG] Lock file path: {self.lock_file_path}")
    
    def acquire(self):
        print(f"[DEBUG] acquire called")
        """Try to acquire the lock. Returns True if successful, False if another instance is running"""
        try:
            # Check if lock file exists
            if os.path.exists(self.lock_file_path):
                try:
                    with open(self.lock_file_path, 'r') as f:
                        pid = int(f.read().strip())
                    
                    if self._is_process_running(pid):
                        print(f"[DEBUG] Another instance is running (PID: {pid})")
                        return False
                    else:
                        # Stale lock file, remove it
                        print(f"[DEBUG] Removing stale lock file (PID: {pid} not running)")
                        os.remove(self.lock_file_path)
                except (ValueError, IOError):
                    # Invalid lock file, remove it
                    print(f"[DEBUG] Removing invalid lock file")
                    try:
                        os.remove(self.lock_file_path)
                    except:
                        pass
            
            # Create lock file with current PID
            with open(self.lock_file_path, 'w') as f:
                f.write(str(os.getpid()))
            
            # On Unix systems, try to use file locking for additional safety
            if sys.platform != 'win32':
                try:
                    import fcntl
                    self.file_handle = open(self.lock_file_path, 'r')
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
            return True  # Allow app to run if lock mechanism fails
    
    def release(self):
        print(f"[DEBUG] release called")
        """Release the lock by removing the lock file"""
        # Release file lock on Unix systems
        if self.file_handle:
            try:
                import fcntl
                fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_UN)
                self.file_handle.close()
                print(f"[DEBUG] File lock released")
            except:
                pass
        
        # Remove lock file
        if self.lock_file and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                print(f"[DEBUG] Lock released: {self.lock_file}")
            except Exception as e:
                print(f"[ERROR] Failed to release lock: {e}")
    
    def _is_process_running(self, pid):
        """Check if a process with the given PID is running"""
        try:
            if sys.platform == "win32":
                # Windows: Use tasklist
                import subprocess
                result = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {pid}'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                return str(pid) in result.stdout
            else:
                # Linux/Mac: Use kill signal 0
                os.kill(pid, 0)
                return True
        except (OSError, subprocess.SubprocessError):
            return False
    
    def __enter__(self):
        """Context manager entry"""
        return self.acquire()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()


def check_single_instance(app_name="BeamSkinStudio"):
    print(f"[DEBUG] check_single_instance called")
    """
    Check if another instance is running and show error dialog if so.
    Returns True if this is the only instance, False otherwise.
    """
    lock = SingleInstanceLock(app_name)
    
    if not lock.acquire():
        print(f"[DEBUG] Another instance detected, attempting to bring it to front...")
        
        # Try to bring existing window to front (platform-specific)
        try:
            if sys.platform == "win32":
                # Windows
                try:
                    import win32gui
                    import win32con
                    
                    def callback(hwnd, extra):
                        print(f"[DEBUG] callback called")
                        if app_name.lower() in win32gui.GetWindowText(hwnd).lower():
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                            return False
                        return True
                    
                    win32gui.EnumWindows(callback, None)
                except ImportError:
                    print("[DEBUG] pywin32 not available, cannot bring window to front")
            
            elif sys.platform == "linux" or sys.platform == "linux2":
                # Linux with X11
                try:
                    import subprocess
                    # Try to find the window using wmctrl
                    result = subprocess.run(
                        ['wmctrl', '-l'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'BeamSkin Studio' in line or app_name in line:
                                window_id = line.split()[0]
                                subprocess.run(['wmctrl', '-i', '-a', window_id])
                                print(f"[DEBUG] Activated existing window using wmctrl")
                                break
                except (subprocess.SubprocessError, FileNotFoundError):
                    print("[DEBUG] wmctrl not available, cannot bring window to front")
            
            elif sys.platform == "darwin":
                # macOS
                try:
                    import subprocess
                    # Use osascript to activate the application
                    subprocess.run([
                        'osascript', '-e',
                        f'tell application "System Events" to set frontmost of every process whose name contains "{app_name}" to true'
                    ], timeout=2)
                    print(f"[DEBUG] Activated existing window using osascript")
                except (subprocess.SubprocessError, FileNotFoundError):
                    print("[DEBUG] osascript not available, cannot bring window to front")
        
        except Exception as e:
            print(f"[DEBUG] Could not bring existing window to front: {e}")
        
        # Show error dialog
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            
            # Platform-specific window attributes
            try:
                root.attributes('-topmost', True)  # Make dialog appear on top
            except:
                pass
            
            messagebox.showerror(
                "Already Running",
                f"{app_name} is already running!\n\n"
                "Please close the existing instance before starting a new one.",
                parent=root
            )
            root.destroy()
        except Exception as e:
            print(f"[ERROR] Failed to show dialog: {e}")
            print(f"[ERROR] {app_name} is already running!")
        
        return False
    
    return True


# Global lock instance to be used in main.py
_global_lock = None


def acquire_global_lock(app_name="BeamSkinStudio"):
    print(f"[DEBUG] acquire_global_lock called")
    """Acquire a global lock. Call this at program start."""
    global _global_lock
    _global_lock = SingleInstanceLock(app_name)
    return _global_lock.acquire()


def release_global_lock():
    print(f"[DEBUG] release_global_lock called")
    """Release the global lock. Call this at program exit."""
    global _global_lock
    if _global_lock:
        _global_lock.release()
