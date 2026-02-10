"""
Settings Tab - Application settings and configuration
Cross-platform path configuration with Linux support
"""
import customtkinter as ctk
from tkinter import filedialog
import os
import platform
from gui.state import state
from core.settings import (
    set_beamng_paths, 
    get_beamng_install_path, 
    get_mods_folder_path,
    save_settings
)
from utils.config_helper import get_beamng_default_install_paths, get_beamng_mods_default_paths


class PathConfigurationSection:
    """Section for configuring BeamNG.drive paths - Cross-platform"""
    
    def __init__(self, parent, notification_callback=None):
        """
        Create path configuration section
        
        Args:
            parent: Parent frame
            notification_callback: Optional callback for showing notifications
        """
        self.notification_callback = notification_callback
        self.system = platform.system()
        
        # Main section frame
        self.frame = ctk.CTkFrame(parent, fg_color=state.colors["card_bg"], corner_radius=12)
        
        # Section header
        header_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 15))
        
        ctk.CTkLabel(
            header_frame,
            text="🎮 BeamNG.drive Paths",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(side="left")
        
        # Platform indicator
        platform_emoji = {
            "Windows": "🪟",
            "Linux": "🐧",
            "Darwin": "🍎"
        }.get(self.system, "💻")
        
        ctk.CTkLabel(
            header_frame,
            text=f"{platform_emoji} {self.system}",
            font=ctk.CTkFont(size=12),
            text_color=state.colors["text_secondary"],
            anchor="e"
        ).pack(side="right", padx=(10, 0))
        
        # Description
        ctk.CTkLabel(
            self.frame,
            text="Configure paths for BeamNG.drive installation and mods folder",
            font=ctk.CTkFont(size=12),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=20, pady=(0, 20))
        
        # BeamNG Installation Path
        self._create_beamng_path_config()
        
        # Mods Folder Path
        self._create_mods_path_config()
        
        # Load current paths
        self._load_current_paths()
    
    def _create_beamng_path_config(self):
        """Create BeamNG installation path configuration"""
        config_frame = ctk.CTkFrame(self.frame, fg_color=state.colors["frame_bg"], corner_radius=8)
        config_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        # Label
        label_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        label_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            label_frame,
            text="BeamNG.drive Installation",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(side="left")
        
        ctk.CTkLabel(
            config_frame,
            text="Required for extracting UV maps from vehicle files",
            font=ctk.CTkFont(size=11),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(0, 10))
        
        # Path entry and button
        path_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.beamng_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="No path set",
            font=ctk.CTkFont(size=12),
            height=35,
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"]
        )
        self.beamng_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_frame = ctk.CTkFrame(path_frame, fg_color="transparent")
        btn_frame.pack(side="right")
        
        ctk.CTkButton(
            btn_frame,
            text="Browse",
            command=self._browse_beamng,
            width=80,
            height=35,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            btn_frame,
            text="Clear",
            command=self._clear_beamng,
            width=70,
            height=35,
            fg_color=state.colors["card_hover"],
            hover_color=state.colors["border"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=12)
        ).pack(side="left")
        
        # Status label
        self.beamng_status = ctk.CTkLabel(
            config_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=state.colors["text_secondary"],
            anchor="w"
        )
        self.beamng_status.pack(fill="x", padx=15, pady=(0, 10))
    
    def _create_mods_path_config(self):
        """Create mods folder path configuration"""
        config_frame = ctk.CTkFrame(self.frame, fg_color=state.colors["frame_bg"], corner_radius=8)
        config_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Label
        label_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        label_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            label_frame,
            text="BeamNG Mods Folder",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(side="left")
        
        ctk.CTkLabel(
            config_frame,
            text="Used for 'Save to Steam' option when generating mods",
            font=ctk.CTkFont(size=11),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(0, 10))
        
        # Path entry and button
        path_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.mods_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="No path set",
            font=ctk.CTkFont(size=12),
            height=35,
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"]
        )
        self.mods_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_frame = ctk.CTkFrame(path_frame, fg_color="transparent")
        btn_frame.pack(side="right")
        
        ctk.CTkButton(
            btn_frame,
            text="Browse",
            command=self._browse_mods,
            width=80,
            height=35,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            btn_frame,
            text="Clear",
            command=self._clear_mods,
            width=70,
            height=35,
            fg_color=state.colors["card_hover"],
            hover_color=state.colors["border"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=12)
        ).pack(side="left")
        
        # Status label
        self.mods_status = ctk.CTkLabel(
            config_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=state.colors["text_secondary"],
            anchor="w"
        )
        self.mods_status.pack(fill="x", padx=15, pady=(0, 10))
    
    def _load_current_paths(self):
        """Load and display current paths from settings"""
        beamng_path = get_beamng_install_path()
        mods_path = get_mods_folder_path()
        
        if beamng_path:
            self.beamng_entry.delete(0, "end")
            self.beamng_entry.insert(0, beamng_path)
            self._validate_beamng_path(beamng_path, show_success=False)
        
        if mods_path:
            self.mods_entry.delete(0, "end")
            self.mods_entry.insert(0, mods_path)
            self._validate_mods_path(mods_path, show_success=False)
    
    def reload_paths(self):
        """Public method to reload paths from settings (can be called externally)"""
        print("[DEBUG] PathConfigurationSection.reload_paths called")
        self._load_current_paths()
    
    def _browse_beamng(self):
        """Browse for BeamNG.drive installation folder"""
        print("[DEBUG] PathConfiguration._browse_beamng called")
        
        # Try to get a good initial directory
        initial_dir = get_beamng_install_path()
        
        if not initial_dir or not os.path.exists(initial_dir):
            # Get platform-specific default paths
            default_paths = get_beamng_default_install_paths()
            if default_paths:
                initial_dir = default_paths[0]
            else:
                initial_dir = os.path.expanduser("~")
        
        print(f"[DEBUG] Initial directory: {initial_dir}")
        print(f"[DEBUG] Platform: {self.system}")
        
        path = filedialog.askdirectory(
            title="Select BeamNG.drive Installation Folder",
            initialdir=initial_dir
        )
        
        print(f"[DEBUG] User selected path: {path}")
        
        if path:
            print(f"[DEBUG] Validating path...")
            if self._validate_beamng_path(path):
                print(f"[DEBUG] Path valid, saving...")
                self.beamng_entry.delete(0, "end")
                self.beamng_entry.insert(0, path)
                set_beamng_paths(beamng_install=path)
                
                if self.notification_callback:
                    self.notification_callback(
                        "BeamNG.drive installation path updated successfully",
                        type="success"
                    )
                print(f"[DEBUG] Path saved successfully")
            else:
                print(f"[DEBUG] Path validation failed")
        else:
            print("[DEBUG] User cancelled dialog")
    
    def _browse_mods(self):
        """Browse for BeamNG mods folder"""
        print("[DEBUG] PathConfiguration._browse_mods called")
        
        # Try to get a good initial directory
        initial_dir = get_mods_folder_path()
        
        if not initial_dir or not os.path.exists(initial_dir):
            # Get platform-specific default paths
            default_paths = get_beamng_mods_default_paths()
            if default_paths:
                initial_dir = default_paths[0]
            else:
                initial_dir = os.path.expanduser("~")
        
        print(f"[DEBUG] Initial mods directory: {initial_dir}")
        
        path = filedialog.askdirectory(
            title="Select BeamNG Mods Folder",
            initialdir=initial_dir
        )
        
        print(f"[DEBUG] User selected mods path: {path}")
        
        if path:
            if self._validate_mods_path(path):
                self.mods_entry.delete(0, "end")
                self.mods_entry.insert(0, path)
                set_beamng_paths(mods_folder=path)
                
                if self.notification_callback:
                    self.notification_callback(
                        "Mods folder path updated successfully",
                        type="success"
                    )
                print(f"[DEBUG] Mods path saved successfully")
    
    def _clear_beamng(self):
        """Clear BeamNG installation path"""
        self.beamng_entry.delete(0, "end")
        self.beamng_status.configure(text="")
        set_beamng_paths(beamng_install="")
        
        if self.notification_callback:
            self.notification_callback(
                "BeamNG.drive installation path cleared",
                type="info"
            )
    
    def _clear_mods(self):
        """Clear mods folder path"""
        self.mods_entry.delete(0, "end")
        self.mods_status.configure(text="")
        set_beamng_paths(mods_folder="")
        
        if self.notification_callback:
            self.notification_callback(
                "Mods folder path cleared",
                type="info"
            )
    
    def _validate_beamng_path(self, path: str, show_success: bool = True) -> bool:
        """Validate BeamNG.drive installation path - Cross-platform"""
        if not os.path.exists(path):
            self.beamng_status.configure(
                text="✗ Path does not exist",
                text_color=state.colors["error"]
            )
            return False
        
        # Platform-specific validation
        if self.system == "Windows":
            # Check for executable
            exe_path_64 = os.path.join(path, "Bin64", "BeamNG.drive.x64.exe")
            exe_path = os.path.join(path, "Bin64", "BeamNG.drive.exe")
            has_exe = os.path.exists(exe_path_64) or os.path.exists(exe_path)
        
        elif self.system == "Linux":
            # On Linux, check for BeamNG or BeamNG.drive binary
            exe_path = os.path.join(path, "BeamNG.drive.x64")
            exe_path_alt = os.path.join(path, "Bin64", "BeamNG.drive.x64")
            exe_path_alt2 = os.path.join(path, "BeamNG")
            has_exe = (os.path.exists(exe_path) or 
                      os.path.exists(exe_path_alt) or
                      os.path.exists(exe_path_alt2))
        
        elif self.system == "Darwin":
            # On macOS, it could be a .app bundle
            if path.endswith(".app"):
                has_exe = os.path.isdir(path)
            else:
                exe_path = os.path.join(path, "BeamNG.drive")
                exe_path_alt = os.path.join(path, "Bin64", "BeamNG.drive")
                has_exe = os.path.exists(exe_path) or os.path.exists(exe_path_alt)
        
        else:
            # Unknown platform - just check if directory exists
            has_exe = True
        
        # Check for content folder (common across all platforms)
        content_path = os.path.join(path, "content")
        has_content = os.path.exists(content_path) and os.path.isdir(content_path)
        
        if not has_exe or not has_content:
            self.beamng_status.configure(
                text="✗ Invalid BeamNG.drive installation",
                text_color=state.colors["error"]
            )
            return False
        
        if show_success:
            self.beamng_status.configure(
                text="✓ Valid BeamNG.drive installation",
                text_color=state.colors["success"]
            )
        else:
            self.beamng_status.configure(text="")
        
        return True
    
    def _validate_mods_path(self, path: str, show_success: bool = True) -> bool:
        """Validate mods folder path"""
        if not os.path.exists(path):
            self.mods_status.configure(
                text="✗ Path does not exist",
                text_color=state.colors["error"]
            )
            return False
        
        if not os.path.isdir(path):
            self.mods_status.configure(
                text="✗ Path is not a directory",
                text_color=state.colors["error"]
            )
            return False
        
        if show_success:
            self.mods_status.configure(
                text="✓ Valid mods folder",
                text_color=state.colors["success"]
            )
        else:
            self.mods_status.configure(text="")
        
        return True
    
    def pack(self, **kwargs):
        """Pack the section frame"""
        self.frame.pack(**kwargs)
    
    def pack_forget(self):
        """Hide the section frame"""
        self.frame.pack_forget()
