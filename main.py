import os
import sys
import threading
import platform

from gui.components.dialogs import run_startup_sequence

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print(f"[DEBUG] Working directory: {os.getcwd()}")
print(f"[DEBUG] Platform: {platform.system()}")

# ─── Error popup helper (works even if customtkinter isn't available) ──────────
def show_error_and_exit(title, message, detail=None):
    """Show a user-friendly error dialog then exit."""
    full_message = message
    if detail:
        full_message += f"\n\nDetails:\n{detail}"

    print(f"\n[FATAL] {title}")
    print(f"        {message}")
    if detail:
        print(f"        {detail}")

    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        messagebox.showerror(f"BeamSkin Studio — {title}", full_message)
        root.destroy()
    except Exception:
        # If even tkinter fails, the .bat will show the log
        pass

    sys.exit(1)


# ─── Dependency check ─────────────────────────────────────────────────────────
REQUIRED_PACKAGES = {
    "customtkinter": "customtkinter",
    "PIL":           "Pillow",
    "requests":      "requests",
    "flag":          "flagpy",
    "deep_translator": "deep-translator",
}

missing = []
for module, pip_name in REQUIRED_PACKAGES.items():
    try:
        __import__(module)
    except ImportError:
        missing.append(pip_name)

if missing:
    show_error_and_exit(
        "Missing Dependencies",
        "The following required packages are not installed:\n\n"
        + "\n".join(f"  • {p}" for p in missing)
        + "\n\nPlease run install.bat to fix this."
    )


# ─── Icon patch ───────────────────────────────────────────────────────────────
def _patch_ctk_icon():
    import customtkinter as ctk
    _ico = os.path.join(os.getcwd(), "gui", "Icons", "BeamSkin_Studio.ico")

    def _our_icon(self):
        try:
            if os.path.exists(_ico):
                self.after(0, lambda: self.iconbitmap(_ico))
        except Exception as e:
            print(f"[ICON] iconbitmap failed: {e}")

    ctk.CTkToplevel._windows_set_titlebar_icon = _our_icon
    ctk.CTk._windows_set_titlebar_icon = _our_icon
    print(f"[ICON] CTkToplevel icon patch applied — using: {_ico}")

_patch_ctk_icon()


# ─── AppUserModelID (taskbar icon) ────────────────────────────────────────────
if sys.platform == 'win32':
    try:
        import ctypes
        myappid = 'BeamSkinStudio.BeamSkinStudio.Application.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        print(f"[DEBUG] Set AppUserModelID for taskbar icon")
    except Exception as e:
        print(f"[DEBUG] Failed to set AppUserModelID: {e}")


# ─── Window helper ────────────────────────────────────────────────────────────
def center_window(window):
    print(f"[DEBUG] center_window called")
    window.geometry("1600x1200")
    window.update_idletasks()

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    x = (screen_width // 2) - (1600 // 2)
    y = (screen_height // 2) - (1200 // 2)

    window.geometry(f'1600x1200+{x}+{y}')


# ─── Main entry point ─────────────────────────────────────────────────────────
if __name__ == "__main__":

    # Single instance check
    try:
        from utils.single_instance import check_single_instance, release_global_lock
        import atexit

        if not check_single_instance("BeamSkinStudio"):
            show_error_and_exit(
                "Already Running",
                "BeamSkin Studio is already open.\n\nPlease close the existing window before launching a new one."
            )

        atexit.register(release_global_lock)
        print("[DEBUG] Single instance lock acquired")

    except ImportError as e:
        print(f"[WARNING] Could not import single_instance module: {e}")
        print(f"[WARNING] Multiple instances may run simultaneously")

    # Core imports
    try:
        from core.updater import check_for_updates, CURRENT_VERSION, set_app_instance
        from core.settings import colors
        from utils.debug import setup_universal_scroll_handler
    except ImportError as e:
        show_error_and_exit(
            "Missing Core Files",
            "A required core module could not be loaded.",
            str(e)
        )

    print(f"[DEBUG] Using NEW refactored GUI structure...")

    # GUI import
    try:
        from gui.main_window import BeamSkinStudioApp
    except ImportError as e:
        import traceback
        show_error_and_exit(
            "Missing GUI Files",
            "Could not load the main window. One or more GUI files are missing.\n\n"
            "Expected files:\n"
            "  gui/main_window.py\n"
            "  gui/state.py\n"
            "  gui/tabs/car_list.py\n"
            "  gui/tabs/generator.py\n"
            "  gui/tabs/settings.py\n"
            "  gui/tabs/howto.py\n"
            "  gui/components/preview.py\n"
            "  gui/components/navigation.py\n"
            "  gui/components/dialogs.py",
            traceback.format_exc()
        )

    # Create app window
    try:
        app = BeamSkinStudioApp()
    except Exception as e:
        import traceback
        show_error_and_exit(
            "Startup Error",
            "BeamSkin Studio encountered an error while starting up.",
            traceback.format_exc()
        )

    print(f"\n[DEBUG] ========================================")
    print(f"[DEBUG] BeamSkin Studio Starting...")
    print(f"[DEBUG] Version: {CURRENT_VERSION}")
    print(f"[DEBUG] Platform: {platform.system()} {platform.release()}")
    print(f"[DEBUG] ========================================\n")

    set_app_instance(app, colors)

    print(f"[DEBUG] Centering window...")
    center_window(app)

    print(f"[DEBUG] Bringing window to front...")
    # Window is withdrawn; it will be revealed in show_startup_sequence.
    # No topmost juggling needed here.

    print(f"[DEBUG] Initializing scroll handler...")
    app.after(100, lambda: setup_universal_scroll_handler(app))

    def _do_connection_check():
        from utils.connection import check_connection
        from gui.components.connection_dialog import show_connection_dialog

        def on_success():
            print("[DEBUG] Server connection: OK")
            report_tab = app.tabs.get("report")
            if report_tab and hasattr(report_tab, "_refresh_status_badge"):
                app.after(0, report_tab._refresh_status_badge)
                app.after(0, report_tab._update_cooldown_ui)

        def on_failure():
            print("[DEBUG] Server connection: FAILED — showing dialog")
            app.after(0, lambda: show_connection_dialog(
                app,
                on_retry   = _do_connection_check,
                on_offline = _go_offline
            ))

        check_connection(on_success=on_success, on_failure=on_failure)

    def _do_connection_check_bg():
        from utils.connection import check_connection

        def on_success():
            print("[DEBUG] Server connection (bg): OK")
            report_tab = app.tabs.get("report")
            if report_tab and hasattr(report_tab, "_refresh_status_badge"):
                app.after(0, report_tab._refresh_status_badge)
                app.after(0, report_tab._update_cooldown_ui)

        def on_failure():
            print("[DEBUG] Server connection (bg): FAILED — dialog deferred to startup sequence")

        check_connection(on_success=on_success, on_failure=on_failure)

    def _go_offline():
        print("[DEBUG] User chose offline mode")
        report_tab = app.tabs.get("report")
        if report_tab and hasattr(report_tab, "_refresh_status_badge"):
            report_tab._refresh_status_badge()
            report_tab._update_cooldown_ui()

    def show_startup_sequence():
        print(f"[DEBUG] show_startup_sequence called")
        """Show startup dialogs in sequence after window is ready"""

        try:
            app.attributes('-topmost', False)
        except:
            pass

        from core.settings import is_setup_complete

        print("[DEBUG] Checking server connection in background...")
        threading.Thread(target=_do_connection_check_bg, daemon=True).start()

        # Reveal the window now — all widgets are built and the language refresh
        # (scheduled at 150 ms) has already run.  Users see a fully-loaded UI.
        print("[DEBUG] Revealing main window...")
        app.deiconify()
        app.lift()
        app.focus_force()

        if not is_setup_complete():
            print("[DEBUG] First-time setup not complete, showing setup wizard...")
            app.after(200, app.show_setup_wizard)
            return

        def _show_offline_dialog():
            from gui.components.connection_dialog import show_connection_dialog
            show_connection_dialog(
                app,
                on_retry   = _do_connection_check,
                on_offline = _go_offline,
            )

        run_startup_sequence(
            app,
            show_offline_dialog_fn=_show_offline_dialog,
        )

    print(f"[DEBUG] Scheduling startup sequence...")
    app.after(500, show_startup_sequence)

    print(f"[DEBUG] Starting main event loop...")
    print(f"[DEBUG] ========================================\n")

    try:
        app.mainloop()
    except Exception as e:
        import traceback
        show_error_and_exit(
            "Runtime Error",
            "BeamSkin Studio crashed during runtime.",
            traceback.format_exc()
        )
    finally:
        print("[DEBUG] Application closed")
        try:
            release_global_lock()
        except Exception:
            pass