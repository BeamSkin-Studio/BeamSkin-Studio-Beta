
import os
import sys
import threading
import platform


script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print(f"[DEBUG] Working directory: {os.getcwd()}")
print(f"[DEBUG] Platform: {platform.system()}")


def show_error_and_exit(title: str, message: str, detail: str = None):
    full_message = message
    if detail:
        full_message += f"\n\nDetails:\n{detail}"

    print(f"\n[FATAL] {title}")
    print(f"        {message}")
    if detail:
        print(f"        {detail}")

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        _app = QApplication.instance() or QApplication(sys.argv)
        box = QMessageBox()
        box.setWindowTitle(f"BeamSkin Studio — {title}")
        box.setText(message)
        if detail:
            box.setDetailedText(detail)
        box.setIcon(QMessageBox.Critical)
        box.exec()
    except Exception:
        pass

    sys.exit(1)


REQUIRED_PACKAGES = {
    "PySide6":        "PySide6",
    "PIL":            "Pillow",
    "requests":       "requests",
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
        + "\n\nPlease run install.bat to fix this.",
    )


if sys.platform == "win32":
    try:
        import ctypes
        myappid = "BeamSkinStudio.BeamSkinStudio.Application.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        print("[DEBUG] Set AppUserModelID for taskbar icon")
    except Exception as e:
        print(f"[DEBUG] Failed to set AppUserModelID: {e}")


if __name__ == "__main__":


    try:
        from utils.single_instance import check_single_instance, release_global_lock
        import atexit

        if not check_single_instance("BeamSkinStudio"):
            show_error_and_exit(
                "Already Running",
                "BeamSkin Studio is already open.\n\n"
                "Please close the existing window before launching a new one.",
            )

        atexit.register(release_global_lock)
        print("[DEBUG] Single instance lock acquired")

    except ImportError as e:
        print(f"[WARNING] Could not import single_instance module: {e}")
        print("[WARNING] Multiple instances may run simultaneously")


    try:
        from core.updater import check_for_updates, CURRENT_VERSION, set_app_instance
        from gui.theme import COLORS as colors
    except ImportError as e:
        show_error_and_exit("Missing Core Files",
                            "A required core module could not be loaded.", str(e))


    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QTimer

    app = QApplication(sys.argv)
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


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
            "  gui/components/navigation.py\n"
            "  gui/components/dialogs.py",
            traceback.format_exc(),
        )


    try:
        window = BeamSkinStudioApp()
    except Exception as e:
        import traceback
        show_error_and_exit(
            "Startup Error",
            "BeamSkin Studio encountered an error while starting up.",
            traceback.format_exc(),
        )

    print(f"\n[DEBUG] ========================================")
    print(f"[DEBUG] BeamSkin Studio Starting...")
    print(f"[DEBUG] Version: {CURRENT_VERSION}")
    print(f"[DEBUG] Platform: {platform.system()} {platform.release()}")
    print(f"[DEBUG] ========================================\n")

    set_app_instance(window, colors)


    screen = app.primaryScreen().geometry()
    w, h = 1600, 1000
    window.resize(w, h)
    window.move((screen.width() - w) // 2, (screen.height() - h) // 2)
    window.show()
    window.raise_()
    window.activateWindow()


    try:
        import tempfile
        _signal_path = os.path.join(tempfile.gettempdir(), "BeamSkinStudio_ready.signal")
        with open(_signal_path, "w") as _f:
            _f.write("ready")
        print(f"[DEBUG] Wrote ready signal to: {_signal_path}")
    except Exception as _e:
        print(f"[DEBUG] Could not write ready signal: {_e}")


    def _do_connection_check():
        from utils.connection import check_connection
        from gui.components.connection_dialog import show_connection_dialog

        def on_success():
            print("[DEBUG] Server connection: OK")
            report_tab = window.tabs.get("report")
            if report_tab and hasattr(report_tab, "_refresh_status_badge"):
                QTimer.singleShot(0, report_tab._refresh_status_badge)
                QTimer.singleShot(0, report_tab._update_cooldown_ui)

        def on_failure():
            print("[DEBUG] Server connection: FAILED — showing dialog")
            QTimer.singleShot(0, lambda: show_connection_dialog(
                window,
                on_retry=_do_connection_check,
                on_offline=_go_offline,
            ))

        check_connection(on_success=on_success, on_failure=on_failure)

    def _do_connection_check_bg():
        from utils.connection import check_connection

        def on_success():
            print("[DEBUG] Server connection (bg): OK")
            report_tab = window.tabs.get("report")
            if report_tab and hasattr(report_tab, "_refresh_status_badge"):
                QTimer.singleShot(0, report_tab._refresh_status_badge)
                QTimer.singleShot(0, report_tab._update_cooldown_ui)

        def on_failure():
            print("[DEBUG] Server connection (bg): FAILED")

        check_connection(on_success=on_success, on_failure=on_failure)

    def _go_offline():
        print("[DEBUG] User chose offline mode")
        report_tab = window.tabs.get("report")
        if report_tab and hasattr(report_tab, "_refresh_status_badge"):
            report_tab._refresh_status_badge()
            report_tab._update_cooldown_ui()

    def show_startup_sequence():
        print("[DEBUG] show_startup_sequence called")
        try:
            from core.settings import is_setup_complete
            from gui.components.dialogs import run_startup_sequence
        except Exception as e:
            import traceback
            print(f"[FATAL] show_startup_sequence import failed:\n{traceback.format_exc()}")
            return

        try:
            threading.Thread(target=_do_connection_check_bg, daemon=True).start()

            if not is_setup_complete():
                print("[DEBUG] First-time setup not complete, showing setup wizard...")
                QTimer.singleShot(200, window.show_setup_wizard)
                return

            def _show_offline_dialog():
                from gui.components.connection_dialog import show_connection_dialog
                show_connection_dialog(
                    window,
                    on_retry=_do_connection_check,
                    on_offline=_go_offline,
                )

            run_startup_sequence(window, show_offline_dialog_fn=_show_offline_dialog)

        except Exception:
            import traceback
            print(f"[FATAL] show_startup_sequence crashed:\n{traceback.format_exc()}")

    QTimer.singleShot(500, show_startup_sequence)

    print("[DEBUG] Starting main event loop...")
    print("[DEBUG] ========================================\n")

    try:
        exit_code = app.exec()
    except Exception as e:
        import traceback
        show_error_and_exit(
            "Runtime Error",
            "BeamSkin Studio crashed during runtime.",
            traceback.format_exc(),
        )
    finally:
        print("[DEBUG] Application closed")
        try:
            release_global_lock()
        except Exception:
            pass

    sys.exit(exit_code)
