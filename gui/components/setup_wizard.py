"""
First-Time Setup Wizard for BeamSkin Studio
"""
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image
import os
from typing import Optional, Callable
from gui.icon_helper import set_window_icon

try:
    from core.localization import t, set_language, get_available_languages
except ImportError:
    def t(key, **kwargs): return key
    def set_language(lang): return True
    def get_available_languages(): return {}

print("[DEBUG] setup_wizard.py loaded with localization")

class SetupWizard:
    """Multi-step setup wizard: 1. Language → 2. Paths"""

    def __init__(self, parent, colors: dict, on_complete: Callable[[dict], None]):
        self.colors = colors
        self.on_complete = on_complete
        self.parent = parent
        self.paths = {
            "beamng_install": "",
            "mods_folder": ""
        }
        self.selected_language = None
        self.current_step = 1  # 1 = Language, 2 = Paths
        self._lang_scroll = None
        self._search_var = None
        self._search_trace_id = None

        # Create dialog
        self.dialog = ctk.CTkToplevel(parent)
        set_window_icon(self.dialog)
        self.dialog.title(t("setup_wizard.title", default="Welcome to BeamSkin Studio"))
        self.dialog.geometry("850x750")
        self.dialog.resizable(False, False)

        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on screen
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (850 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (750 // 2)
        self.dialog.geometry(f"850x750+{x}+{y}")

        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.attributes('-topmost', True)
        self.dialog.after(100, lambda: self.dialog.attributes('-topmost', False))

        self.dialog.protocol("WM_DELETE_WINDOW", self._on_exit_program)

        # Create main container
        self.main_frame = ctk.CTkFrame(self.dialog, fg_color=colors["frame_bg"])
        self.main_frame.pack(fill="both", expand=True, padx=25, pady=(25, 30))

        # Show language selection first
        self._show_language_step()

    def _show_language_step(self):
        print("[DEBUG] Showing language selection step")

        # Reset search state so stale trace callbacks don't reference destroyed widgets
        self._lang_scroll = None
        self._search_var = None

        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Header
        self._create_header_language()

        # Language selection content
        content_frame = ctk.CTkFrame(self.main_frame, fg_color=self.colors["card_bg"], corner_radius=12)
        content_frame.pack(fill="both", expand=True, pady=(0, 15))

        # ── Search bar ──────────────────────────────────────────────────── #
        search_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=25, pady=(20, 8))

        self._search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self._search_var,
            placeholder_text="🔍  " + t("language_selection.search", default="Search languages…"),
            font=ctk.CTkFont(size=13),
            height=38,
            fg_color=self.colors["frame_bg"],
            border_color=self.colors["border"],
            corner_radius=8,
        )
        search_entry.pack(fill="x")

        # ── Scrollable language list ─────────────────────────────────────── #
        languages_scroll = ctk.CTkScrollableFrame(
            content_frame,
            fg_color=self.colors["frame_bg"],
            corner_radius=8
        )
        languages_scroll.pack(fill="both", expand=True, padx=25, pady=(4, 25))

        # Get available languages once
        available_languages = get_available_languages()
        if not available_languages:
            available_languages = {"en": {"name": "English", "native": "English", "flag": "🇬🇧"}}

        self._all_languages = dict(
            sorted(available_languages.items(), key=lambda x: x[1]["name"])
        )
        self.language_buttons = {}
        self._lang_scroll = languages_scroll

        # Initial render (no filter)
        self._render_language_list("")

        # Wire up live search — remove any previous trace first to avoid accumulation.
        # _show_language_step() is called on every language click, so without cleanup
        # each call leaves an orphaned callback referencing the old StringVar.
        def _on_search_change(*_):
            if self._search_var is not None:
                self._render_language_list(self._search_var.get())

        self._search_trace_id = self._search_var.trace_add("write", _on_search_change)

        # Buttons
        self._create_buttons_language()

    def _render_language_list(self, query: str):
        if self._lang_scroll is None:
            return
        for widget in self._lang_scroll.winfo_children():
            widget.destroy()
        self.language_buttons = {}

        q = query.strip().lower()
        for lang_code, lang_info in self._all_languages.items():
            # Match against native name, English name, or lang code
            if q and not any(
                q in s.lower()
                for s in (lang_info.get("native", ""), lang_info.get("name", ""), lang_code)
            ):
                continue
            self._create_language_option(self._lang_scroll, lang_code, lang_info)

    def _create_header_language(self):
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        # Logo
        try:
            logo_path = os.path.join("gui", "Icons", "BeamSkin_Studio_White.png")
            if os.path.exists(logo_path):
                logo_image = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(80, 80)
                )
                ctk.CTkLabel(header_frame, image=logo_image, text="").pack(pady=(0, 10))
        except Exception as e:
            print(f"[DEBUG] Could not load logo: {e}")
            ctk.CTkLabel(header_frame, text="🌍", font=ctk.CTkFont(size=48)).pack(pady=(0, 8))

        ctk.CTkLabel(
            header_frame,
            text=t("setup_wizard.title", default="Welcome to BeamSkin Studio!"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.colors["text"]
        ).pack()

        ctk.CTkLabel(
            header_frame,
            text=t("language_selection.selection", default="Language Selection"),
            font=ctk.CTkFont(size=13),
            text_color=self.colors["text_secondary"]
        ).pack(pady=(4, 0))

    def _create_language_option(self, parent, lang_code: str, lang_info: dict):
        is_selected = self.selected_language == lang_code

        # Create a clickable frame instead of button to avoid geometry manager issues
        btn_frame = ctk.CTkFrame(
            parent,
            fg_color=self.colors["accent"] if is_selected else self.colors["card_bg"],
            corner_radius=8,
            height=65
        )
        btn_frame.pack(fill="x", padx=5, pady=3)
        btn_frame.pack_propagate(False)
        
        # Make the frame clickable
        btn_frame.bind("<Button-1>", lambda e: self._select_language(lang_code))
        btn_frame.bind("<Enter>", lambda e: btn_frame.configure(
            fg_color=self.colors["accent_hover"] if is_selected else self.colors["card_hover"]
        ))
        btn_frame.bind("<Leave>", lambda e: btn_frame.configure(
            fg_color=self.colors["accent"] if is_selected else self.colors["card_bg"]
        ))

        # Content container
        content = ctk.CTkFrame(btn_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=8)
        content.bind("<Button-1>", lambda e: self._select_language(lang_code))

        # Left side - flag and names
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)
        left.bind("<Button-1>", lambda e: self._select_language(lang_code))

        # Flag
        flag_lbl = ctk.CTkLabel(left, text=lang_info["flag"], font=ctk.CTkFont(size=28))
        flag_lbl.pack(side="left", padx=(0, 12))
        flag_lbl.bind("<Button-1>", lambda e: self._select_language(lang_code))

        # Names container
        names = ctk.CTkFrame(left, fg_color="transparent")
        names.pack(side="left", fill="both", expand=True)
        names.bind("<Button-1>", lambda e: self._select_language(lang_code))

        # Native name
        native_lbl = ctk.CTkLabel(
            names,
            text=lang_info["native"],
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors["accent_text"] if is_selected else self.colors["text"],
            anchor="w"
        )
        native_lbl.pack(anchor="w")
        native_lbl.bind("<Button-1>", lambda e: self._select_language(lang_code))

        # English name (smaller) shown under native when different
        if lang_info.get("name", "") != lang_info.get("native", ""):
            eng_lbl = ctk.CTkLabel(
                names,
                text=lang_info.get("name", ""),
                font=ctk.CTkFont(size=11),
                text_color=self.colors["accent_text"] if is_selected else self.colors["text_secondary"],
                anchor="w",
            )
            eng_lbl.pack(anchor="w")
            eng_lbl.bind("<Button-1>", lambda e, lc=lang_code: self._select_language(lc))

        # Checkmark for selected
        if is_selected:
            check = ctk.CTkLabel(
                content, 
                text="✓", 
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color=self.colors["accent_text"]
            )
            check.pack(side="right", padx=(8, 0))
            check.bind("<Button-1>", lambda e: self._select_language(lang_code))

        self.language_buttons[lang_code] = btn_frame

    def _select_language(self, lang_code: str):
        print(f"[DEBUG] Language selected: {lang_code}")
        self.selected_language = lang_code
        set_language(lang_code)
        self._show_language_step()

    def _create_buttons_language(self):
        footer = ctk.CTkFrame(self.main_frame, fg_color=self.colors["card_bg"], corner_radius=12, height=72)
        footer.pack(fill="x", pady=(10, 0))
        footer.pack_propagate(False)
        ctk.CTkFrame(footer, fg_color=self.colors["border"], height=1).pack(fill="x")
        row = ctk.CTkFrame(footer, fg_color="transparent")
        row.place(relx=0.5, rely=0.58, anchor="center")
        ctk.CTkButton(
            row, text=t("common.cancel", default="Exit"), command=self._on_exit_program,
            height=40, width=160, fg_color=self.colors["frame_bg"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text"],
            border_width=1, border_color=self.colors["border"],
            font=ctk.CTkFont(size=13), corner_radius=8,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            row, text=t("common.next", default="Next") + "  →", command=self._on_language_next,
            height=40, width=160, fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"], text_color=self.colors["accent_text"],
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
        ).pack(side="left")

    def _on_language_next(self):
        if not self.selected_language:
            # Default to English if nothing selected
            self.selected_language = "en"
            set_language("en")
        
        print(f"[DEBUG] Moving to paths step with language: {self.selected_language}")
        
        # Save language to settings (non-fatal — still proceed on error)
        try:
            from core.settings import app_settings, save_settings
            app_settings["language"] = self.selected_language
            save_settings()
        except Exception as e:
            print(f"[ERROR] Failed to save language setting: {e}")
        
        # Move to paths step
        self._show_paths_step()

    def _show_paths_step(self):
        print("[DEBUG] Showing paths configuration step")

        # Nullify lang-step state BEFORE destroying widgets. If any in-flight
        # StringVar trace fires during widget teardown it will hit the
        # `if self._lang_scroll is None: return` guard in _render_language_list
        # and exit cleanly instead of crashing on a destroyed frame (silent TclError
        # is what caused the Next button to appear to do nothing).
        self._lang_scroll = None
        self._search_var = None
        self._search_trace_id = None

        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self._create_header_paths()
        self._create_beamng_section(self.main_frame)
        self._create_mods_section(self.main_frame)
        self._create_buttons_paths()

    def _create_header_paths(self):
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        try:
            logo_path = os.path.join("gui", "Icons", "BeamSkin_Studio_White.png")
            if os.path.exists(logo_path):
                logo_image = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(80, 80)
                )
                ctk.CTkLabel(header_frame, image=logo_image, text="").pack(pady=(0, 10))
        except:
            ctk.CTkLabel(header_frame, text="🎮", font=ctk.CTkFont(size=40)).pack(pady=(0, 8))

        ctk.CTkLabel(
            header_frame,
            text=t("setup_wizard.title", default="Welcome to BeamSkin Studio!"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.colors["text"]
        ).pack()

        ctk.CTkLabel(
            header_frame,
            text=t("setup_wizard.step_paths", default="Configure Paths"),
            font=ctk.CTkFont(size=13),
            text_color=self.colors["text_secondary"]
        ).pack(pady=(4, 0))

    def _create_beamng_section(self, parent):
        section_frame = ctk.CTkFrame(parent, fg_color=self.colors["card_bg"], corner_radius=12)
        section_frame.pack(fill="x", pady=(0, 12))

        title_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(12, 8))

        ctk.CTkLabel(
            title_frame,
            text="1. " + t("setup_wizard.beamng_install", default="BeamNG.drive Installation"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.colors["text"],
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            section_frame,
            text=t("setup_wizard.beamng_description", default="Required for extracting UV maps from vehicle files"),
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=20, pady=(0, 8))

        path_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 12))

        self.beamng_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text=t("setup_wizard.no_path_selected", default="No path selected"),
            font=ctk.CTkFont(size=12),
            height=38,
            fg_color=self.colors["frame_bg"],
            border_color=self.colors["border"]
        )
        self.beamng_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            path_frame,
            text=t("common.browse", default="Browse..."),
            command=self._browse_beamng,
            width=100,
            height=38,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color=self.colors["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="right")

        self.beamng_status = ctk.CTkLabel(
            section_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"],
            anchor="w"
        )
        self.beamng_status.pack(fill="x", padx=20, pady=(0, 8))

    def _create_mods_section(self, parent):
        """Create mods folder path section"""
        section_frame = ctk.CTkFrame(parent, fg_color=self.colors["card_bg"], corner_radius=12)
        section_frame.pack(fill="x", pady=(0, 12))

        title_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(12, 8))

        ctk.CTkLabel(
            title_frame,
            text="2. " + t("setup_wizard.mods_folder", default="BeamNG Mods Folder"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.colors["text"],
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            section_frame,
            text=t("setup_wizard.mods_description", default="Used for the 'Save to Steam' option when generating mods"),
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"],
            anchor="w"
        ).pack(fill="x", padx=20, pady=(0, 8))

        path_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 12))

        self.mods_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text=t("setup_wizard.no_path_selected", default="No path selected"),
            font=ctk.CTkFont(size=12),
            height=38,
            fg_color=self.colors["frame_bg"],
            border_color=self.colors["border"]
        )
        self.mods_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            path_frame,
            text=t("common.browse", default="Browse..."),
            command=self._browse_mods,
            width=100,
            height=38,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color=self.colors["accent_text"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="right")

        self.mods_status = ctk.CTkLabel(
            section_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self.colors["text_secondary"],
            anchor="w"
        )
        self.mods_status.pack(fill="x", padx=20, pady=(0, 8))

    def _create_buttons_paths(self):
        footer = ctk.CTkFrame(self.main_frame, fg_color=self.colors["card_bg"], corner_radius=12, height=72)
        footer.pack(fill="x", pady=(10, 0))
        footer.pack_propagate(False)
        ctk.CTkFrame(footer, fg_color=self.colors["border"], height=1).pack(fill="x")
        row = ctk.CTkFrame(footer, fg_color="transparent")
        row.place(relx=0.5, rely=0.58, anchor="center")
        ctk.CTkButton(
            row, text="←  " + t("common.back", default="Back"), command=self._on_back_to_language,
            height=40, width=160, fg_color=self.colors["frame_bg"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text"],
            border_width=1, border_color=self.colors["border"],
            font=ctk.CTkFont(size=13), corner_radius=8,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            row, text="✓  " + t("common.finish", default="Finish"), command=self._on_paths_finish,
            height=40, width=160, fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"], text_color=self.colors["accent_text"],
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
        ).pack(side="left")

    def _on_back_to_language(self):
        self._show_language_step()

    def _browse_beamng(self):
        self.dialog.grab_release()
        
        try:
            path = filedialog.askdirectory(
                parent=self.dialog,
                title="Select BeamNG.drive Installation Folder",
                initialdir="C:/Program Files (x86)/Steam/steamapps/common" if os.name == 'nt' else "~"
            )

            if path:
                if self._validate_beamng_path(path):
                    self.paths["beamng_install"] = path
                    self.beamng_entry.delete(0, "end")
                    self.beamng_entry.insert(0, path)
                    self.beamng_status.configure(
                        text=t("setup_wizard.beamng_valid", default="✓ Valid BeamNG.drive installation found"),
                        text_color=self.colors["success"]
                    )
                else:
                    self.beamng_status.configure(
                        text=t("setup_wizard.beamng_invalid", default="✗ Invalid path - BeamNG.drive not found here"),
                        text_color=self.colors["error"]
                    )
        finally:
            self.dialog.grab_set()

    def _browse_mods(self):
        self.dialog.grab_release()
        
        try:
            path = filedialog.askdirectory(
                parent=self.dialog,
                title="Select BeamNG Mods Folder",
                initialdir=os.path.expanduser("~/AppData/Local/BeamNG.drive/current/mods") if os.name == 'nt' else "~"
            )

            if path:
                if self._validate_mods_path(path):
                    self.paths["mods_folder"] = path
                    self.mods_entry.delete(0, "end")
                    self.mods_entry.insert(0, path)
                    self.mods_status.configure(
                        text=t("setup_wizard.mods_valid", default="✓ Valid mods folder selected"),
                        text_color=self.colors["success"]
                    )
                else:
                    self.mods_status.configure(
                        text=t("setup_wizard.mods_invalid", default="✗ Invalid path - not a valid mods folder"),
                        text_color=self.colors["error"]
                    )
        finally:
            self.dialog.grab_set()

    def _validate_beamng_path(self, path: str) -> bool:
        if not os.path.exists(path):
            return False

        exe_path_64 = os.path.join(path, "Bin64", "BeamNG.drive.x64.exe")
        exe_path = os.path.join(path, "Bin64", "BeamNG.drive.exe")
        has_exe = os.path.exists(exe_path_64) or os.path.exists(exe_path)

        content_path = os.path.join(path, "content")
        has_content = os.path.exists(content_path) and os.path.isdir(content_path)

        return has_exe and has_content

    def _validate_mods_path(self, path: str) -> bool:
        """Validate mods folder path"""
        return os.path.exists(path) and os.path.isdir(path)

    def _on_exit_program(self):
        print("[DEBUG] Setup wizard: User chose to exit program")
        try:
            self.dialog.destroy()
        except:
            pass
        try:
            self.parent.quit()
            self.parent.destroy()
        except:
            pass
        import os
        os._exit(0)

    def _on_paths_finish(self):
        print(f"[DEBUG] Setup wizard: Complete with paths: {self.paths}")

        # Destroy the dialog FIRST so it always closes regardless of what
        # on_complete does. The old order was on_complete() then destroy():
        # any exception thrown inside the callback (UI refresh, path reload,
        # language change, etc.) is silently swallowed by Tkinter, leaving
        # the wizard frozen on screen with the button appearing to do nothing.
        try:
            self.dialog.destroy()
        except Exception as e:
            print(f"[ERROR] Failed to destroy setup wizard dialog: {e}")

        try:
            self.on_complete(self.paths)
        except Exception as e:
            import traceback
            print(f"[ERROR] on_complete callback raised an exception: {e}")
            traceback.print_exc()

    def show(self):
        self.dialog.wait_window()

def show_setup_wizard(parent, colors: dict, on_complete: Callable[[dict], None]):
    wizard = SetupWizard(parent, colors, on_complete)
    wizard.show()