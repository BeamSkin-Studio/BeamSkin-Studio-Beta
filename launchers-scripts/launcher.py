"""
BeamSkin Studio - installer
"""
# Import only standard library modules first (these are always available)
import subprocess
import sys
import os
import threading
import time
import urllib.request
import tempfile

# Check and install required packages BEFORE importing them
def ensure_packages():
    """Check if required packages are installed, install if not"""
    print("[LAUNCHER] Checking required packages...")
    
    required_packages = [
        ("customtkinter", "customtkinter"),
        ("Pillow", "PIL"),
        ("requests", "requests")
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"[LAUNCHER]   ✓ {package_name} is installed")
        except ImportError:
            print(f"[LAUNCHER]   ✗ {package_name} is NOT installed")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"[LAUNCHER] Installing missing packages: {', '.join(missing_packages)}")
        print("[LAUNCHER] This may take 1-2 minutes...")
        
        for package in missing_packages:
            print(f"[LAUNCHER]   Installing {package}...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", package, "--quiet"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print(f"[LAUNCHER]   ✓ {package} installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"[LAUNCHER]   ✗ Failed to install {package}")
                print(f"[LAUNCHER]   Please run manually: pip install {package}")
                input("\nPress Enter to exit...")
                sys.exit(1)
        
        print("[LAUNCHER] All packages installed successfully!")
    else:
        print("[LAUNCHER] All required packages are already installed")
    
    print("[LAUNCHER] Starting GUI launcher...")

# Run package check BEFORE importing GUI libraries
ensure_packages()

# NOW it's safe to import GUI libraries
import customtkinter as ctk
from PIL import Image

COLORS = {
    "bg": "#0a0a0a",
    "frame_bg": "#141414",
    "card": "#1e1e1e",
    "card_hover": "#282828",
    "accent": "#39E09B",
    "accent_hover": "#2fc97f",
    "text": "#f5f5f5",
    "text_secondary": "#999999",
    "success": "#39E09B",
    "error": "#ff4444",
    "warning": "#ffa726"
}

print(f"[DEBUG] Loading class: LauncherWindow")

class LauncherWindow:
    def __init__(self):
        print(f"[DEBUG] __init__ called")
        self.app = ctk.CTk()
        self.app.title("BeamSkin Studio - Launcher")
        self.app.geometry("700x600")  # Slightly taller for logo
        self.app.resizable(False, False)
        self.app.configure(fg_color=COLORS["bg"])
        
        self.app.attributes('-topmost', True)
        
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
                    size=(200, 200)  # Adjust size here
                )
                print(f"[DEBUG] Loaded logo from: {logo_path}")
                return logo_image
            else:
                print(f"[DEBUG] Logo not found at: {logo_path}")
                return None
        except Exception as e:
            print(f"[DEBUG] Failed to load logo: {e}")
            return None
        
    def center_window(self):
        
        print(f"[DEBUG] center_window called")
        """Center the window on screen"""
        self.app.update_idletasks()
        x = (self.app.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.app.winfo_screenheight() // 2) - (600 // 2)
        self.app.geometry(f"700x600+{x}+{y}")
    
    def create_ui(self):
    
        print(f"[DEBUG] create_ui called")
        """Create the launcher UI"""
        # Main container
        main_frame = ctk.CTkFrame(self.app, fg_color=COLORS["bg"])
        main_frame.pack(fill="both", expand=True, padx=25, pady=25)
        
        # Header
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(pady=(0, 20))
        
        # Logo/Icon
        if self.logo_image:
            # Use logo image
            ctk.CTkLabel(
                header_frame,
                text="",
                image=self.logo_image
            ).pack(pady=(0, 15))
        else:
            # Fallback to emoji if logo not found
            ctk.CTkLabel(
                header_frame,
                text="🎨",
                font=ctk.CTkFont(size=56)
            ).pack()
        
        ctk.CTkLabel(
            header_frame,
            text="Professional Skin Modding Tool",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"]
        ).pack()
        
        # Status card
        self.status_card = ctk.CTkFrame(
            main_frame,
            fg_color=COLORS["card"],
            corner_radius=16,
            border_width=2,
            border_color=COLORS["accent"]
        )
        self.status_card.pack(fill="both", expand=True, pady=(0, 20))
        
        # Status content
        status_content = ctk.CTkFrame(self.status_card, fg_color="transparent")
        status_content.pack(fill="both", expand=True, padx=30, pady=30)
        
        # Status icon
        self.status_icon = ctk.CTkLabel(
            status_content,
            text="🔍",
            font=ctk.CTkFont(size=64)
        )
        self.status_icon.pack(pady=(20, 15))
        
        # Status text
        self.status_label = ctk.CTkLabel(
            status_content,
            text="Initializing...",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.status_label.pack(pady=(0, 10))
        
        # Detail text
        self.detail_label = ctk.CTkLabel(
            status_content,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"]
        )
        self.detail_label.pack(pady=(0, 15))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            status_content,
            width=500,
            height=8,
            corner_radius=4,
            fg_color=COLORS["frame_bg"],
            progress_color=COLORS["accent"]
        )
        self.progress_bar.pack(pady=(0, 20))
        self.progress_bar.set(0)
        
        # Action button (hidden initially)
        self.action_button = ctk.CTkButton(
            status_content,
            text="",
            command=None,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg"],
            width=200,
            height=45,
            corner_radius=10,
            font=ctk.CTkFont(size=15, weight="bold")
        )
        
        # Footer
        footer_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        footer_frame.pack()
        
        ctk.CTkLabel(
            footer_frame,
            text="Please wait while we prepare BeamSkin Studio...",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        ).pack()
        
    def update_status(self, icon, message, detail="", progress=None):
        
        print(f"[DEBUG] update_status called")
        """Update the status display"""
        self.status_icon.configure(text=icon)
        self.status_label.configure(text=message, text_color=COLORS["text"])
        self.detail_label.configure(text=detail)
        if progress is not None:
            self.progress_bar.set(progress)
        self.app.update()
        
    def show_error(self, message, detail="", button_text="Close", button_command=None):
        
        print(f"[DEBUG] show_error called")
        """Show error state"""
        self.status_icon.configure(text="❌")
        self.status_label.configure(text=message, text_color=COLORS["error"])
        self.detail_label.configure(text=detail)
        self.progress_bar.set(0)
        
        # Show action button
        if button_command is None:
            button_command = self.app.quit
            
        self.action_button.configure(
            text=button_text,
            command=button_command,
            fg_color=COLORS["error"],
            hover_color="#cc3636"
        )
        self.action_button.pack(pady=10)
        
    def show_success(self, message, detail=""):
        
        print(f"[DEBUG] show_success called")
        """Show success state"""
        self.status_icon.configure(text="✅")
        self.status_label.configure(text=message, text_color=COLORS["success"])
        self.detail_label.configure(text=detail)
        self.progress_bar.set(1.0)
        
    def show_choice(self, icon, message, detail, yes_text, no_text, yes_command, no_command):
        
        print(f"[DEBUG] show_choice called")
        """Show a choice dialog"""
        self.status_icon.configure(text=icon)
        self.status_label.configure(text=message)
        self.detail_label.configure(text=detail)
        self.progress_bar.set(0)
        
        # Create button frame
        button_frame = ctk.CTkFrame(self.status_card, fg_color="transparent")
        button_frame.pack(pady=10)
        
        ctk.CTkButton(
            button_frame,
            text=yes_text,
            command=lambda: [button_frame.destroy(), yes_command()],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg"],
            width=150,
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text=no_text,
            command=lambda: [button_frame.destroy(), no_command()],
            fg_color=COLORS["card"],
            hover_color=COLORS["card_hover"],
            text_color=COLORS["text"],
            width=150,
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=5)
        
    def run(self):
        
        print(f"[DEBUG] run called")
        """Start the launcher"""
        self.app.mainloop()


print(f"[DEBUG] Loading class: SetupManager")


class SetupManager:
    """Handles Python installation and dependency management"""
    
    def __init__(self, launcher):
    
        print(f"[DEBUG] __init__ called")
        self.launcher = launcher
        
    def check_python(self):
        
        print(f"[DEBUG] check_python called")
        """Check if Python is installed"""
        try:
            result = subprocess.run(
                ["python", "--version"],
                capture_output=True,
                text=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, version
            return False, None
        except FileNotFoundError:
            return False, None
    
    def download_python_installer(self):
    
        print(f"[DEBUG] download_python_installer called")
        """Download Python installer for Windows"""
        import webbrowser
        
        # Python 3.11.9 (stable, widely compatible)
        python_url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        
        self.launcher.update_status(
            "📥",
            "Downloading Python installer...",
            "This may take a few minutes",
            0.2
        )
        
        try:
            # Download to Downloads folder
            import os
            downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            installer_path = os.path.join(downloads_folder, "python-3.11.9-amd64.exe")
            
            # Download with progress tracking
            def download_progress(block_num, block_size, total_size):
                print(f"[DEBUG] download_progress called")
                downloaded = block_num * block_size
                if total_size > 0:
                    progress = min(downloaded / total_size, 1.0)
                    self.launcher.progress_bar.set(0.2 + (progress * 0.6))  # 20-80%
                    self.launcher.app.update()
            
            urllib.request.urlretrieve(python_url, installer_path, download_progress)
            
            self.launcher.update_status(
                "✅",
                "Python installer downloaded!",
                "Starting installation...",
                0.9
            )
            
            time.sleep(0.5)
            
            # Run the installer automatically with silent flags
            self.launcher.update_status(
                "🔧",
                "Installing Python...",
                "This will take a few minutes\nPlease wait...",
                0.95
            )
            
            try:
                # Run Python installer with automatic flags
                # /passive = shows progress but no user interaction
                # PrependPath=1 = adds Python to PATH automatically
                # Include_pip=1 = installs pip
                result = subprocess.run(
                    [installer_path, "/passive", "PrependPath=1", "Include_pip=1"],
                    check=False
                )
                
                if result.returncode == 0:
                    self.launcher.show_success(
                        "Python Installed Successfully!",
                        "Please restart this launcher to continue"
                    )
                    
                    # Show restart button
                    self.launcher.action_button.configure(
                        text="Restart Launcher",
                        command=lambda: [self.launcher.app.quit(), os.execl(sys.executable, sys.executable, *sys.argv)],
                        fg_color=COLORS["accent"],
                        hover_color=COLORS["accent_hover"]
                    )
                    self.launcher.action_button.pack(pady=10)
                else:
                    # Installation failed or cancelled
                    self.launcher.show_error(
                        "Installation Issue",
                        "Python installation may have been cancelled or failed.\n"
                        "Please run the installer manually from Downloads folder.",
                        "Open Downloads",
                        lambda: [os.startfile(downloads_folder) if sys.platform == 'win32' else None, self.launcher.app.quit()]
                    )
                    
            except Exception as e:
                self.launcher.show_error(
                    "Installation Error",
                    f"Error running installer: {str(e)}\n\n"
                    f"Installer saved to:\n{installer_path}",
                    "Open Downloads",
                    lambda: [os.startfile(downloads_folder) if sys.platform == 'win32' else None, self.launcher.app.quit()]
                )
            
        except Exception as e:
            # Fallback to browser if download fails
            self.launcher.show_error(
                "Download Failed",
                f"Error: {str(e)}\n\nOpening download page in browser instead...",
                "Open Browser",
                lambda: [webbrowser.open("https://www.python.org/downloads/"), self.launcher.app.quit()]
            )
    
    def install_packages(self):
    
        print(f"[DEBUG] install_packages called")
        """Install required Python packages"""
        packages = ["pip", "customtkinter", "Pillow", "requests"]
        
        for i, package in enumerate(packages):
            progress = 0.3 + (i + 1) / len(packages) * 0.6  # 30-90%
            
            if package == "pip":
                self.launcher.update_status(
                    "📦",
                    "Updating package manager...",
                    "Upgrading pip to latest version",
                    progress
                )
                
                result = subprocess.run(
                    ["python", "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
            else:
                self.launcher.update_status(
                    "📦",
                    "Installing packages...",
                    f"Installing {package}",
                    progress
                )
                
                result = subprocess.run(
                    ["python", "-m", "pip", "install", "--upgrade", package, "--quiet"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
            
            if result.returncode != 0:
                # Don't fail on pip upgrade errors, just continue
                if package == "pip":
                    continue
                raise Exception(f"Failed to install {package}")
            
            time.sleep(0.2)  # Brief pause for visual feedback
    
    def launch_app(self):
    
        print(f"[DEBUG] launch_app called")
        """Launch the main application via BeamSkin Studio.bat"""
        self.launcher.update_status(
            "🚀",
            "Starting BeamSkin Studio...",
            "Loading application",
            0.95
        )
        
        time.sleep(0.5)
        
        # Get the parent directory (go up from launchers-scripts to root)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        bat_file_path = os.path.join(parent_dir, "BeamSkin Studio.bat")
        
        # Check if bat file exists
        if not os.path.exists(bat_file_path):
            self.launcher.show_error(
                "File Not Found",
                f"Could not find 'BeamSkin Studio.bat' in:\n{parent_dir}",
                "Close",
                self.launcher.app.quit
            )
            return
        
        # Launch bat file without console window (don't wait for it)
        if sys.platform == 'win32':
            # Use CREATE_NO_WINDOW flag on Windows and Popen to not wait
            process = subprocess.Popen(
                [bat_file_path],
                cwd=parent_dir,  # Set working directory to parent
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=True
            )
        else:
            # On other platforms, try to run it directly
            process = subprocess.Popen(
                [bat_file_path],
                cwd=parent_dir,
                shell=True
            )
        
        # Wait for main app window to appear before closing launcher
        time.sleep(2)  # Give app time to initialize and show window
        
        # Now hide and close launcher
        self.launcher.app.withdraw()
        self.launcher.app.quit()


def main():


    print(f"[DEBUG] main called")
    """Main launcher sequence"""
    launcher = LauncherWindow()
    setup = SetupManager(launcher)
    
    def startup_sequence():
    
        print(f"[DEBUG] startup_sequence called")
        """Run the startup checks and launch"""
        try:
            # Check Python
            launcher.update_status(
                "🔍",
                "Checking Python installation...",
                "Verifying Python is available",
                0.1
            )
            time.sleep(0.5)
            
            python_installed, version = setup.check_python()
            
            if not python_installed:
                # Download and install Python for user
                def download_and_install():
                    print(f"[DEBUG] download_and_install called")
                    setup.download_python_installer()
                
                launcher.show_choice(
                    "⚠️",
                    "Python Not Found",
                    "Python is required to run BeamSkin Studio.\nWould you like to download and install it now?",
                    "Download Python",
                    "Cancel",
                    download_and_install,
                    launcher.app.quit
                )
                return
            
            else:
                launcher.update_status(
                    "✅",
                    f"Python Found: {version}",
                    "Preparing dependencies...",
                    0.2
                )
                time.sleep(0.3)
                continue_startup()
            
        except Exception as e:
            launcher.show_error(
                "Startup Error",
                str(e)
            )
    
    def continue_startup():
    
        print(f"[DEBUG] continue_startup called")
        """Continue with package installation and app launch"""
        try:
            # Install/update packages
            launcher.update_status(
                "📦",
                "Checking dependencies...",
                "This will only take a moment",
                0.25
            )
            time.sleep(0.2)
            
            setup.install_packages()
            
            launcher.update_status(
                "✅",
                "All dependencies ready!",
                "Launching application...",
                0.95
            )
            time.sleep(0.3)
            
            # Launch app via bat file
            setup.launch_app()
            
        except Exception as e:
            launcher.show_error(
                "Setup Error",
                str(e)
            )
    
    # Start sequence in background thread
    threading.Thread(target=startup_sequence, daemon=True).start()
    
    # Run GUI
    launcher.run()


if __name__ == "__main__":
    main()