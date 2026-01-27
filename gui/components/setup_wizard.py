"""
First-Time Setup Wizard for BeamNG.drive Installation
"""
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image
import os
from typing import Optional, Callable

print("[DEBUG] setup_wizard.py loaded")


class SetupWizard:
    """First-time setup wizard for BeamNG.drive paths"""
    
    def __init__(self, parent, colors: dict, on_complete: Callable[[dict], None]):
        """
        Create setup wizard
        
        Args:
            parent: Parent window
            colors: Theme colors dictionary
            on_complete: Callback function called with paths dict when setup is complete
        """
        self.colors = colors
        self.on_complete = on_complete
        self.parent = parent  # Store parent reference
        self.paths = {
            "beamng_install": "",
            "mods_folder": ""
        }
        
        # Create toplevel dialog - LARGER SIZE
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("BeamSkin Studio - First Time Setup")
        self.dialog.geometry("850x750")  # Increased from 800x700
        self.dialog.resizable(False, False)
        
        # Make it modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (850 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (750 // 2)
        self.dialog.geometry(f"850x750+{x}+{y}")
        
        # Keep on top initially
        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.attributes('-topmost', True)
        self.dialog.after(100, lambda: self.dialog.attributes('-topmost', False))
        
        # Allow closing to exit the program
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_exit_program)
        
        # Main frame (non-scrollable, larger dialog should fit everything)
        main_frame = ctk.CTkFrame(self.dialog, fg_color=colors["frame_bg"])
        main_frame.pack(fill="both", expand=True, padx=25, pady=(25, 30))  # Increased bottom padding
        
        # Header
        self._create_header(main_frame)
        
        # Setup sections
        self._create_beamng_section(main_frame)
        self._create_mods_section(main_frame)
        
        # Buttons
        self._create_buttons(main_frame)
        
        # Note: Entry and status widgets are created in the section methods above
    
    def _create_header(self, parent):
        """Create header section"""
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))  # Reduced from 20 to 15
        
        # Logo
        try:
            logo_path = os.path.join("gui", "Icons", "BeamSkin_Studio_White.png")
            if os.path.exists(logo_path):
                logo_image = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(100, 100)  # Reduced from 120 to 100
                )
                ctk.CTkLabel(
                    header_frame,
                    image=logo_image,
                    text=""
                ).pack(pady=(0, 10))  # Reduced from 15 to 10
            else:
                # Fallback to emoji if logo not found
                ctk.CTkLabel(
                    header_frame,
                    text="🎮",
                    font=ctk.CTkFont(size=40),  # Reduced from 48
                    text_color=self.colors["text"]
                ).pack(pady=(0, 8))
        except Exception as e:
            print(f"[DEBUG] Could not load logo: {e}")
            # Fallback to emoji
            ctk.CTkLabel(
                header_frame,
                text="🎮",
                font=ctk.CTkFont(size=40),
                text_color=self.colors["text"]
            ).pack(pady=(0, 8))
        
        # Title
        ctk.CTkLabel(
            header_frame,
            text="Welcome to BeamSkin Studio!",
            font=ctk.CTkFont(size=22, weight="bold"),  # Reduced from 24
            text_color=self.colors["text"]
        ).pack()
        
        # Subtitle
        ctk.CTkLabel(
            header_frame,
            text="Let's set up your BeamNG.drive paths",
            font=ctk.CTkFont(size=13),  # Reduced from 14
            text_color=self.colors["text_secondary"]
        ).pack(pady=(4, 0))  # Reduced from 5 to 4
    
    def _create_beamng_section(self, parent):
        """Create BeamNG installation path section"""
        section_frame = ctk.CTkFrame(parent, fg_color=self.colors["card_bg"], corner_radius=12)
        section_frame.pack(fill="x", pady=(0, 12))  # Reduced from 15 to 12
        
        # Section title
        title_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(12, 8))  # Reduced padding
        
        ctk.CTkLabel(
            title_frame,
            text="1. BeamNG.drive Installation",
            font=ctk.CTkFont(size=15, weight="bold"),  # Reduced from 16
            text_color=self.colors["text"],
            anchor="w"
        ).pack(side="left")
        
        # Description
        ctk.CTkLabel(
            section_frame,
            text="Required for extracting UV maps from vehicle files",
            font=ctk.CTkFont(size=11),  # Reduced from 12
            text_color=self.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=20, pady=(0, 8))  # Reduced from 10 to 8
        
        # Path display and button
        path_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 12))  # Reduced from 15 to 12
        
        self.beamng_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="No path selected",
            font=ctk.CTkFont(size=12),
            height=38,  # Reduced from 40
            fg_color=self.colors["frame_bg"],
            border_color=self.colors["border"]
        )
        self.beamng_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(
            path_frame,
            text="Browse...",
            command=self._browse_beamng,
            width=100,
            height=38,  # Reduced from 40
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color=self.colors["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="right")
        
        # Status label
        self.beamng_status = ctk.CTkLabel(
            section_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"],
            anchor="w"
        )
        self.beamng_status.pack(fill="x", padx=20, pady=(0, 8))  # Reduced from 10 to 8
    
    def _create_mods_section(self, parent):
        """Create mods folder path section"""
        section_frame = ctk.CTkFrame(parent, fg_color=self.colors["card_bg"], corner_radius=12)
        section_frame.pack(fill="x", pady=(0, 12))  # Reduced from 15 to 12
        
        # Section title
        title_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(12, 8))  # Reduced padding
        
        ctk.CTkLabel(
            title_frame,
            text="2. BeamNG Mods Folder",
            font=ctk.CTkFont(size=15, weight="bold"),  # Reduced from 16
            text_color=self.colors["text"],
            anchor="w"
        ).pack(side="left")
        
        # Description
        ctk.CTkLabel(
            section_frame,
            text="Used for the 'Save to Steam' option when generating mods",
            font=ctk.CTkFont(size=11),  # Reduced from 12
            text_color=self.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=20, pady=(0, 8))  # Reduced from 10 to 8
        
        # Path display and button
        path_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 12))  # Reduced from 15 to 12
        
        self.mods_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="No path selected",
            font=ctk.CTkFont(size=12),
            height=38,  # Reduced from 40
            fg_color=self.colors["frame_bg"],
            border_color=self.colors["border"]
        )
        self.mods_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(
            path_frame,
            text="Browse...",
            command=self._browse_mods,
            width=100,
            height=38,  # Reduced from 40
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color=self.colors["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="right")
        
        # Status label
        self.mods_status = ctk.CTkLabel(
            section_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"],
            anchor="w"
        )
        self.mods_status.pack(fill="x", padx=20, pady=(0, 8))  # Reduced from 10 to 8
    
    def _create_buttons(self, parent):
        """Create button section"""
        print("[DEBUG] Creating buttons section...")
        
        # Add separator
        separator = ctk.CTkFrame(parent, height=2, fg_color=self.colors["border"])
        separator.pack(fill="x", pady=(15, 12))  # Reduced padding
        print("[DEBUG] Separator created")
        
        # Add helper text
        helper_frame = ctk.CTkFrame(parent, fg_color=self.colors["card_bg"], corner_radius=8)
        helper_frame.pack(fill="x", pady=(0, 12))  # Reduced from 15 to 12
        
        ctk.CTkLabel(
            helper_frame,
            text="⚠️ Both paths are required. You can change them later in Settings.",
            font=ctk.CTkFont(size=11, weight="bold"),  # Reduced from 12
            text_color=self.colors["warning"],
            wraplength=700,  # Increased for wider dialog
            justify="center"
        ).pack(padx=15, pady=10)  # Reduced from 12 to 10
        print("[DEBUG] Helper text created")
        
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=(0, 10))  # Added bottom padding
        print("[DEBUG] Button frame created")
        
        # Configure grid for equal spacing
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        
        # Exit button (left) - closes the entire program
        exit_btn = ctk.CTkButton(
            button_frame,
            text="✕ Exit Program",
            command=self._on_exit_program,
            height=48,  # Reduced from 50
            fg_color=self.colors["error"],
            hover_color=self.colors["error_hover"],
            text_color="white",
            border_width=0,
            font=ctk.CTkFont(size=14),
            corner_radius=8
        )
        exit_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        print("[DEBUG] Exit button created and placed")
        
        # Continue button (right)
        self.continue_btn = ctk.CTkButton(
            button_frame,
            text="✓ Continue",
            command=self._on_continue,
            height=48,  # Reduced from 50
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color=self.colors["accent_text"],
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=8
        )
        self.continue_btn.grid(row=0, column=1, padx=(10, 0), sticky="ew")
        print(f"[DEBUG] Continue button created and placed")
        print(f"[DEBUG] Continue button fg_color: {self.colors['accent']}")
        print(f"[DEBUG] Continue button text_color: {self.colors['accent_text']}")
        
        # Force update to ensure rendering
        button_frame.update_idletasks()
        print("[DEBUG] Button frame updated")
    
    def _browse_beamng(self):
        """Browse for BeamNG.drive installation folder"""
        print("[DEBUG] _browse_beamng called")
        
        # Temporarily release grab so file dialog can work
        self.dialog.grab_release()
        
        try:
            path = filedialog.askdirectory(
                parent=self.dialog,
                title="Select BeamNG.drive Installation Folder",
                initialdir="C:/Program Files (x86)/Steam/steamapps/common" if os.name == 'nt' else "~"
            )
            
            print(f"[DEBUG] User selected path: {path}")
            
            if path:
                # Validate the path
                print(f"[DEBUG] Validating path: {path}")
                if self._validate_beamng_path(path):
                    print(f"[DEBUG] Path is valid, updating UI")
                    self.paths["beamng_install"] = path
                    self.beamng_entry.delete(0, "end")
                    self.beamng_entry.insert(0, path)
                    
                    self.beamng_status.configure(
                        text="✓ Valid BeamNG.drive installation found",
                        text_color=self.colors["success"]
                    )
                    print(f"[DEBUG] BeamNG path set: {path}")
                else:
                    print(f"[DEBUG] Path validation failed")
                    self.beamng_status.configure(
                        text="✗ Invalid path - BeamNG.drive not found here",
                        text_color=self.colors["error"]
                    )
                    print(f"[DEBUG] Invalid BeamNG path: {path}")
            else:
                print("[DEBUG] User cancelled dialog")
        finally:
            # Re-establish grab
            self.dialog.grab_set()
    
    def _browse_mods(self):
        """Browse for BeamNG mods folder"""
        print("[DEBUG] _browse_mods called")
        
        # Temporarily release grab so file dialog can work
        self.dialog.grab_release()
        
        try:
            path = filedialog.askdirectory(
                parent=self.dialog,
                title="Select BeamNG Mods Folder",
                initialdir=os.path.expanduser("~/AppData/Local/BeamNG.drive/current/mods") if os.name == 'nt' else "~"
            )
            
            print(f"[DEBUG] User selected path: {path}")
            
            if path:
                # Validate the path
                print(f"[DEBUG] Validating path: {path}")
                if self._validate_mods_path(path):
                    print(f"[DEBUG] Path is valid, updating UI")
                    self.paths["mods_folder"] = path
                    self.mods_entry.delete(0, "end")
                    self.mods_entry.insert(0, path)
                    
                    self.mods_status.configure(
                        text="✓ Valid mods folder selected",
                        text_color=self.colors["success"]
                    )
                    print(f"[DEBUG] Mods path set: {path}")
                else:
                    print(f"[DEBUG] Path validation failed")
                    self.mods_status.configure(
                        text="✗ Invalid path - not a valid mods folder",
                        text_color=self.colors["error"]
                    )
                    print(f"[DEBUG] Invalid mods path: {path}")
            else:
                print("[DEBUG] User cancelled dialog")
        finally:
            # Re-establish grab
            self.dialog.grab_set()
    
    def _validate_beamng_path(self, path: str) -> bool:
        """
        Validate BeamNG.drive installation path
        
        Checks for the existence of key files/folders:
        - Bin64/BeamNG.drive.x64.exe (or BeamNG.drive.exe on 32-bit)
        - content/ folder
        
        Args:
            path: Path to validate
        
        Returns:
            True if valid, False otherwise
        """
        print(f"[DEBUG] _validate_beamng_path called with: {path}")
        
        if not os.path.exists(path):
            print(f"[DEBUG] Path does not exist: {path}")
            return False
        
        # Check for executable
        exe_path_64 = os.path.join(path, "Bin64", "BeamNG.drive.x64.exe")
        exe_path = os.path.join(path, "Bin64", "BeamNG.drive.exe")
        
        print(f"[DEBUG] Checking for exe at: {exe_path_64}")
        print(f"[DEBUG] Exists: {os.path.exists(exe_path_64)}")
        print(f"[DEBUG] Checking for exe at: {exe_path}")
        print(f"[DEBUG] Exists: {os.path.exists(exe_path)}")
        
        has_exe = os.path.exists(exe_path_64) or os.path.exists(exe_path)
        
        # Check for content folder
        content_path = os.path.join(path, "content")
        print(f"[DEBUG] Checking for content folder at: {content_path}")
        print(f"[DEBUG] Exists: {os.path.exists(content_path)}")
        
        has_content = os.path.exists(content_path) and os.path.isdir(content_path)
        
        print(f"[DEBUG] has_exe: {has_exe}, has_content: {has_content}")
        print(f"[DEBUG] Validation result: {has_exe and has_content}")
        
        return has_exe and has_content
    
    def _validate_mods_path(self, path: str) -> bool:
        """
        Validate mods folder path
        
        Simple validation - just checks if it's a valid directory
        
        Args:
            path: Path to validate
        
        Returns:
            True if valid, False otherwise
        """
        print(f"[DEBUG] _validate_mods_path called with: {path}")
        
        exists = os.path.exists(path)
        is_dir = os.path.isdir(path) if exists else False
        
        print(f"[DEBUG] Path exists: {exists}, is directory: {is_dir}")
        print(f"[DEBUG] Validation result: {exists and is_dir}")
        
        return exists and is_dir
    
    def _on_exit_program(self):
        """Handle exit program button - closes the entire application"""
        print("[DEBUG] Setup wizard: User chose to exit program")
        print("[DEBUG] Destroying dialog...")
        
        try:
            self.dialog.destroy()
        except Exception as e:
            print(f"[DEBUG] Error destroying dialog: {e}")
        
        print("[DEBUG] Destroying parent window...")
        try:
            self.parent.quit()
            self.parent.destroy()
        except Exception as e:
            print(f"[DEBUG] Error destroying parent: {e}")
        
        print("[DEBUG] Force exiting application...")
        import os
        os._exit(0)  # Force exit - more aggressive than sys.exit()
    
    def _on_continue(self):
        """Handle continue button"""
        # BOTH paths are required
        if not self.paths["beamng_install"]:
            self.beamng_status.configure(
                text="⚠ BeamNG.drive installation path is required",
                text_color=self.colors["warning"]
            )
            return
        
        if not self.paths["mods_folder"]:
            self.mods_status.configure(
                text="⚠ Mods folder path is required",
                text_color=self.colors["warning"]
            )
            return
        
        print(f"[DEBUG] Setup wizard: Complete with paths: {self.paths}")
        self.on_complete(self.paths)
        self.dialog.destroy()
    
    def show(self):
        """Show the dialog and wait for completion"""
        self.dialog.wait_window()


def show_setup_wizard(parent, colors: dict, on_complete: Callable[[dict], None]):
    """
    Show the setup wizard dialog
    
    Args:
        parent: Parent window
        colors: Theme colors dictionary
        on_complete: Callback function called with paths dict when setup is complete
    """
    wizard = SetupWizard(parent, colors, on_complete)
    wizard.show()