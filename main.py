import os
import sys
import threading
import platform

# Change working directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print(f"[DEBUG] Working directory: {os.getcwd()}")
print(f"[DEBUG] Platform: {platform.system()}")

# Windows-specific taskbar icon setup
if sys.platform == 'win32':
    try:
        import ctypes
        myappid = 'BeamSkinStudio.BeamSkinStudio.Application.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        print(f"[DEBUG] Set AppUserModelID for taskbar icon")
    except Exception as e:
        print(f"[DEBUG] Failed to set AppUserModelID: {e}")

def center_window(window):
    print(f"[DEBUG] center_window called")
    """Centers the window on the screen"""
    window.geometry("1600x1200")
    window.update_idletasks()
    
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    x = (screen_width // 2) - (1600 // 2)
    y = (screen_height // 2) - (1200 // 2)
    
    window.geometry(f'1600x1200+{x}+{y}')

if __name__ == "__main__":
    # Check for single instance BEFORE importing heavy modules
    try:
        from utils.single_instance import check_single_instance, release_global_lock
        import atexit
        
        # Check if another instance is already running
        if not check_single_instance("BeamSkinStudio"):
            print("[DEBUG] Another instance is already running. Exiting...")
            sys.exit(0)
        
        # Register cleanup on exit
        atexit.register(release_global_lock)
        print("[DEBUG] Single instance lock acquired")
        
    except ImportError as e:
        print(f"[WARNING] Could not import single_instance module: {e}")
        print(f"[WARNING] Multiple instances may run simultaneously")
    
    # Import after setting working directory and checking single instance
    from core.updater import check_for_updates, CURRENT_VERSION, set_app_instance
    from core.settings import colors
    from utils.debug import setup_universal_scroll_handler
    
    print(f"[DEBUG] Using NEW refactored GUI structure...")
    
    try:
        from gui.main_window import BeamSkinStudioApp
        
        # Create the app using the new class
        app = BeamSkinStudioApp()
        
        print(f"\n[DEBUG] ========================================")
        print(f"[DEBUG] BeamSkin Studio Starting...")
        print(f"[DEBUG] Version: {CURRENT_VERSION}")
        print(f"[DEBUG] Platform: {platform.system()} {platform.release()}")
        print(f"[DEBUG] ========================================\n")
        
    except ImportError as e:
        print(f"[ERROR] Failed to import GUI structure: {e}")
        print(f"[ERROR] Make sure all files in gui/ folder exist:")
        print(f"  - gui/main_window.py")
        print(f"  - gui/state.py")
        print(f"  - gui/tabs/car_list.py")
        print(f"  - gui/tabs/generator.py")
        print(f"  - gui/tabs/settings.py")
        print(f"  - gui/tabs/howto.py")
        print(f"  - gui/components/preview.py")
        print(f"  - gui/components/navigation.py")
        print(f"  - gui/components/dialogs.py")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Give updater access to app and colors for custom UI
    set_app_instance(app, colors)
    
    # Center the window on screen FIRST
    print(f"[DEBUG] Centering window...")
    center_window(app)
    
    # Make window appear on top when launched
    print(f"[DEBUG] Bringing window to front...")
    app.lift()
    app.focus_force()
    
    # Platform-specific window management
    if sys.platform == 'win32':
        app.attributes('-topmost', True)  # Set on top (Windows)
    elif sys.platform == 'darwin':
        # macOS
        try:
            app.attributes('-topmost', True)
        except:
            pass
    # Linux/X11 - handled differently, focus_force() is usually sufficient
    
    # CRITICAL: Initialize universal scroll handler BEFORE showing dialogs
    print(f"[DEBUG] Initializing scroll handler...")
    app.after(100, lambda: setup_universal_scroll_handler(app))
    
    # Show WIP warning AFTER a proper delay to ensure window is visible and focused
    def show_startup_sequence():
        print(f"[DEBUG] show_startup_sequence called")
        """Show startup dialogs in sequence after window is ready"""
        # First remove topmost attribute (after 500ms to ensure window is visible)
        try:
            app.attributes('-topmost', False)
        except:
            pass
        
        # Check if setup is complete
        from core.settings import is_setup_complete
        if not is_setup_complete():
            print("[DEBUG] First-time setup not complete, showing setup wizard...")
            app.after(200, app.show_setup_wizard)
        else:
            print("[DEBUG] Setup complete, showing WIP warning...")
            app.after(200, app.show_startup_warning)
        
        # Start update check thread after dialogs
        app.after(500, lambda: threading.Thread(target=check_for_updates, daemon=True).start())
    
    print(f"[DEBUG] Scheduling startup sequence...")
    app.after(500, show_startup_sequence)
    
    print(f"[DEBUG] Starting main event loop...")
    print(f"[DEBUG] ========================================\n")
    
    try:
        app.mainloop()
    finally:
        # Cleanup on exit
        print("[DEBUG] Application closed")
        release_global_lock()
