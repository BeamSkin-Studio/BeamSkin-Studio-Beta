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
    "bg": "#0a0a0a",
    "frame_bg": "#141414",
    "card": "#1e1e1e",
    "accent": "#39E09B",
    "text": "#f5f5f5",
    "text_secondary": "#999999"
}

print(f"[DEBUG] Loading class: QuickLauncher")
print(f"[DEBUG] Platform: {platform.system()}")

class QuickLauncher:
    def __init__(self):
        print(f"[DEBUG] __init__ called")

        self.launch_main_app()

        self.app = ctk.CTk()
        self.app.title("BeamSkin Studio")
        self.app.geometry("600x450")
        self.app.resizable(False, False)
        self.app.configure(fg_color=COLORS["bg"])

        if platform.system() != "Darwin":
            self.app.attributes('-topmost', True)

        try:
            self.app.overrideredirect(True)
        except:

            pass

        self.logo_image = self._load_logo()

        self.center_window()

        self.create_ui()

        self.app.lift()
        self.app.focus_force()

    def _load_logo(self):
        """Load the BeamSkin Studio logo"""

        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)

        logo_path = os.path.join(parent_dir, "gui", "Icons", "BeamSkin_Studio_White.png")

        try:
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)

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

        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        main_py_path = os.path.join(parent_dir, "main.py")

        system = platform.system()

        if system == 'Windows':

            self.process = subprocess.Popen(
                ["pythonw", main_py_path],
                cwd=parent_dir,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        elif system == 'Darwin':

            self.process = subprocess.Popen(
                ["python3", main_py_path],
                cwd=parent_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:

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

        for i in range(101):
            self.progress_bar.set(i / 100)
            self.app.update()
            time.sleep(0.011)

        time.sleep(1.2)

        self.app.destroy()

    def run(self):
        print(f"[DEBUG] run called")
        """Start the launcher"""

        threading.Thread(target=self.wait_and_close, daemon=True).start()

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

        main_frame = ctk.CTkFrame(
            self.app,
            fg_color=COLORS["frame_bg"],
            border_width=2,
            border_color=COLORS["accent"]
        )
        main_frame.pack(fill="both", expand=True)

        content_frame = ctk.CTkFrame(main_frame, fg_color=COLORS["bg"])
        content_frame.pack(fill="both", expand=True, padx=30, pady=30)

        header_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        header_frame.pack(expand=True)

        if self.logo_image:

            ctk.CTkLabel(
                header_frame,
                text="",
                image=self.logo_image
            ).pack(pady=(0, 20))
        else:

            ctk.CTkLabel(
                header_frame,
                text="🎨",
                font=ctk.CTkFont(size=72)
            ).pack(pady=(0, 15))

        ctk.CTkLabel(
            header_frame,
            text="Professional Skin Modding Tool",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(0, 25))

        ctk.CTkLabel(
            header_frame,
            text="Loading BeamSkin Studio...",
            font=ctk.CTkFont(size=15),
            text_color=COLORS["text"]
        ).pack(pady=(0, 25))

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

        ctk.CTkLabel(
            header_frame,
            text="Please wait...",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        ).pack()

if __name__ == "__main__":
    launcher = QuickLauncher()
    launcher.run()
