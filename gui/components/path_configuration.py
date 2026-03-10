"""
Settings Tab - Application settings and configuration
Cross-platform path configuration with Linux support
"""
import customtkinter as ctk
from tkinter import filedialog
import os
import platform
from gui.state import state
from core.localization import t
from core.settings import (
    set_beamng_paths,
    get_beamng_install_path,
    get_mods_folder_path,
    save_settings
)
from utils.config_helper import get_beamng_default_install_paths, get_beamng_mods_default_paths

class PathConfigurationSection:

    def __init__(self, parent, notification_callback=None):
        
        self.notification_callback = notification_callback
        self.system = platform.system()

        self.frame = ctk.CTkFrame(parent, fg_color=state.colors["card_bg"], corner_radius=12)

        header_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 15))

        ctk.CTkLabel(
            header_frame,
            text=t("settings.beamng_paths"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(side="left")

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

        ctk.CTkLabel(
            self.frame,
            text=t("settings.beamng_paths_desc"),
            font=ctk.CTkFont(size=16),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=20, pady=(0, 20))

        self._create_beamng_path_config()

        self._create_mods_path_config()

        self._load_current_paths()

    def _create_beamng_path_config(self):
        config_frame = ctk.CTkFrame(self.frame, fg_color=state.colors["frame_bg"], corner_radius=8)
        config_frame.pack(fill="x", padx=20, pady=(0, 15))

        label_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        label_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            label_frame,
            text=t("settings.beamng_install"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            config_frame,
            text=t("settings.beamng_uvpath_desc"),
            font=ctk.CTkFont(size=14),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(0, 10))

        path_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.beamng_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="beamng_uvpath_desc",
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
            text=t("common.browse"),
            command=self._browse_beamng,
            width=80,
            height=35,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(0, 5))

        self.beamng_status = ctk.CTkLabel(
            config_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=state.colors["text_secondary"],
            anchor="w"
        )
        self.beamng_status.pack(fill="x", padx=15, pady=(0, 10))

    def _create_mods_path_config(self):

        config_frame = ctk.CTkFrame(self.frame, fg_color=state.colors["frame_bg"], corner_radius=8)
        config_frame.pack(fill="x", padx=20, pady=(0, 20))

        label_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        label_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            label_frame,
            text=t("settings.beamng_modpath"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            config_frame,
            text=t("settings.beamng_modpath_desc"),
            font=ctk.CTkFont(size=14),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(0, 10))

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
            text=t("common.browse"),
            command=self._browse_mods,
            width=80,
            height=35,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(0, 5))

        self.mods_status = ctk.CTkLabel(
            config_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=state.colors["text_secondary"],
            anchor="w"
        )
        self.mods_status.pack(fill="x", padx=15, pady=(0, 10))

    def _load_current_paths(self):
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
        print("[DEBUG] PathConfigurationSection.reload_paths called")
        self._load_current_paths()

    def _browse_beamng(self):
        print("[DEBUG] PathConfiguration._browse_beamng called")

        initial_dir = get_beamng_install_path()

        if not initial_dir or not os.path.exists(initial_dir):

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
        print("[DEBUG] PathConfiguration._browse_mods called")

        initial_dir = get_mods_folder_path()

        if not initial_dir or not os.path.exists(initial_dir):

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

        if self.system == "Windows":

            exe_path_64 = os.path.join(path, "Bin64", "BeamNG.drive.x64.exe")
            exe_path = os.path.join(path, "Bin64", "BeamNG.drive.exe")
            has_exe = os.path.exists(exe_path_64) or os.path.exists(exe_path)

        elif self.system == "Linux":

            exe_path = os.path.join(path, "BeamNG.drive.x64")
            exe_path_alt = os.path.join(path, "Bin64", "BeamNG.drive.x64")
            exe_path_alt2 = os.path.join(path, "BeamNG")
            has_exe = (os.path.exists(exe_path) or
                      os.path.exists(exe_path_alt) or
                      os.path.exists(exe_path_alt2))

        elif self.system == "Darwin":

            if path.endswith(".app"):
                has_exe = os.path.isdir(path)
            else:
                exe_path = os.path.join(path, "BeamNG.drive")
                exe_path_alt = os.path.join(path, "Bin64", "BeamNG.drive")
                has_exe = os.path.exists(exe_path) or os.path.exists(exe_path_alt)

        else:

            has_exe = True

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
        """Validate mods folder path - accepts any existing directory named 'mods'"""
        if not path or not path.strip():
            self.mods_status.configure(
                text="✗ No path provided",
                text_color=state.colors["error"]
            )
            return False
            
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

        # Check if the folder is named "mods" or is clearly a mods folder
        folder_name = os.path.basename(path).lower()
        if folder_name != "mods":
            # Allow it anyway but show a warning
            if show_success:
                self.mods_status.configure(
                    text="⚠ Valid directory (not named 'mods', but accepted)",
                    text_color=state.colors["warning"]
                )
            else:
                self.mods_status.configure(text="")
        else:
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
