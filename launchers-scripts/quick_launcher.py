"""
BeamSkin Studio - Quick Launcher
Cross-platform splash screen and app launcher
"""
import customtkinter as ctk
from PIL import Image
import subprocess
import sys
import time
import threading
import os
import platform

COLORS = {
    "bg": "#0a0a0a",           # app_bg
    "frame_bg": "#141414",     # frame_bg
    "card": "#1e1e1e",         # card_bg
    "accent": "#39E09B",       # accent (green)
    "text": "#f5f5f5",         # text
    "text_secondary": "#999999" # text_secondary
}

print(f"[DEBUG] Loading class: QuickLauncher")
print(f"[DEBUG] Platform: {platform.system()}")

class QuickLauncher:
    def __init__(self):
        print(f"[DEBUG] __init__ called")
        
        # LAUNCH MAIN APP FIRST before creating GUI
        self.launch_main_app()
        
        # Now create the loading GUI
        self.app = ctk.CTk()
        self.app.title("BeamSkin Studio")
        self.app.geometry("600x450")
        self.app.resizable(False, False)
        self.app.configure(fg_color=COLORS["bg"])
        
        # Platform-specific window setup
        if platform.system() != "Darwin":  # Not macOS
            self.app.attributes('-topmost', True)
        
        # Remove window decorations for cleaner look
        try:
            self.app.overrideredirect(True)
        except:
            # Some window managers don't support this
            pass
        
        # Load logo
        self.logo_image = self._load_logo()
        
        # Center window
        self.center_window()
        
        self.create_ui()
        
        # Lift window to front
        self.app.lift()
        self.app.focus_force()
    
    def _load_logo(self):
        """Load the BeamSkin Studio logo"""
        # Get parent directory (go up from launchers-scripts to root)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        
        # Try to load white logo (for dark background)
        logo_path = os.path.join(parent_dir, "gui", "Icons", "BeamSkin_Studio_White.png")
        
        try:
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)
                # Logo size - adjust as needed
                logo_image = ctk.CTkImage(
                    light_image=pil_image,
                    dark_image=pil_image,
                    size=(200, 200)
                )
                print(f"[DEBUG] Loaded logo from: {logo_path}")
                return logo_image
            else:
                print(f"[DEBUG] Logo not found at: {logo_path}")
                return None
        except Exception as e:
            print(f"[DEBUG] Failed to load logo: {e}")
            return None
    
    def launch_main_app(self):
        print(f"[DEBUG] launch_main_app called - launching main.py NOW")
        """Launch main.py immediately"""
        
        # Get the parent directory (go up from launchers-scripts to root)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        main_py_path = os.path.join(parent_dir, "main.py")
        
        system = platform.system()
        
        # Launch main app without console window (platform-specific)
        if system == 'Windows':
            # Windows: Use pythonw to avoid console
            self.process = subprocess.Popen(
                ["pythonw", main_py_path],
                cwd=parent_dir,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        elif system == 'Darwin':
            # macOS: Use python3
            self.process = subprocess.Popen(
                ["python3", main_py_path],
                cwd=parent_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Linux: Use python3
            self.process = subprocess.Popen(
                ["python3", main_py_path],
                cwd=parent_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        print(f"[DEBUG] main.py launched, PID: {self.process.pid}")
    
    def wait_and_close(self):
        print(f"[DEBUG] wait_and_close called")
        """Animate progress bar, then wait for main app to load, then close"""
        
        # Animate progress bar
        for i in range(101):
            self.progress_bar.set(i / 100)
            self.app.update()
            time.sleep(0.011)  # Smooth animation
        
        # Wait additional time for main app window to appear
        time.sleep(1.2)
        
        # Close launcher
        self.app.destroy()
    
    def run(self):
        print(f"[DEBUG] run called")
        """Start the launcher"""
        
        # Start wait sequence in background
        threading.Thread(target=self.wait_and_close, daemon=True).start()
        
        # Run GUI (this will show while main app loads)
        self.app.mainloop()

    def center_window(self):
        print(f"[DEBUG] center_window called")
        """Center the window on screen"""
        self.app.update_idletasks()
        x = (self.app.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.app.winfo_screenheight() // 2) - (450 // 2)
        self.app.geometry(f"600x450+{x}+{y}")
    
    def create_ui(self):
        print(f"[DEBUG] create_ui called")
        """Create the launcher UI"""
        # Main container with border (matching main app accent color)
        main_frame = ctk.CTkFrame(
            self.app, 
            fg_color=COLORS["frame_bg"],
            border_width=2,
            border_color=COLORS["accent"]
        )
        main_frame.pack(fill="both", expand=True)
        
        content_frame = ctk.CTkFrame(main_frame, fg_color=COLORS["bg"])
        content_frame.pack(fill="both", expand=True, padx=30, pady=30)
        
        # Header
        header_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        header_frame.pack(expand=True)
        
        # Logo/Icon
        if self.logo_image:
            # Use logo image
            ctk.CTkLabel(
                header_frame,
                text="",
                image=self.logo_image
            ).pack(pady=(0, 20))
        else:
            # Fallback to emoji if logo not found
            ctk.CTkLabel(
                header_frame,
                text="🎨",
                font=ctk.CTkFont(size=72)
            ).pack(pady=(0, 15))
        
        # Subtitle
        ctk.CTkLabel(
            header_frame,
            text="Professional Skin Modding Tool",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(0, 25))
        
        # Loading text
        ctk.CTkLabel(
            header_frame,
            text="Loading BeamSkin Studio...",
            font=ctk.CTkFont(size=15),
            text_color=COLORS["text"]
        ).pack(pady=(0, 25))
        
        # Animated progress bar
        self.progress_bar = ctk.CTkProgressBar(
            header_frame,
            width=420,
            height=8,
            corner_radius=4,
            fg_color=COLORS["card"],
            progress_color=COLORS["accent"]
        )
        self.progress_bar.pack(pady=(0, 15))
        self.progress_bar.set(0)
        
        # Status text
        ctk.CTkLabel(
            header_frame,
            text="Please wait...",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        ).pack()

if __name__ == "__main__":
    launcher = QuickLauncher()
    launcher.run()
