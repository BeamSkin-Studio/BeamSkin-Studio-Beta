"""
Settings Tab
"""
from typing import Dict, Tuple, Optional
import customtkinter as ctk
from tkinter import messagebox, colorchooser
import sys
import os
from gui.state import state
from core.settings import reset_theme_colors, update_theme_color, DEFAULT_THEMES
from core.localization import t, set_language, get_available_languages, get_current_language
from utils.debug import toggle_debug_mode
from gui.components.path_configuration import PathConfigurationSection

print(f"[DEBUG] Loading class: SettingsTab")

class SettingsTab(ctk.CTkFrame):
    """Settings tab with theme customization and debug mode"""

    def __init__(self, parent: ctk.CTk, main_container: ctk.CTkFrame, menu_frame: ctk.CTkFrame,
                 menu_buttons: Dict[str, ctk.CTkButton], switch_view_callback, notification_callback=None):

        print(f"[DEBUG] __init__ called")
        super().__init__(parent, fg_color=state.colors["app_bg"])

        self.main_container = main_container
        self.menu_frame = menu_frame
        self.menu_buttons = menu_buttons
        self.switch_view_callback = switch_view_callback
        self.notification_callback = notification_callback

        self.root_app = self._get_root_window()

        self.debug_mode_var = ctk.BooleanVar(value=False)

        self.dark_theme_edit_frame: Optional[ctk.CTkFrame] = None
        self.light_theme_edit_frame: Optional[ctk.CTkFrame] = None
        self.dark_color_entries: Dict[str, Tuple[ctk.CTkEntry, ctk.CTkLabel]] = {}
        self.light_color_entries: Dict[str, Tuple[ctk.CTkEntry, ctk.CTkLabel]] = {}

        self._setup_ui()

    def _get_root_window(self):
        """Walk up the widget hierarchy to find the CTk root window"""
        widget = self
        while widget:
            if isinstance(widget, ctk.CTk):
                return widget
            try:
                widget = widget.master
            except:
                break
        try:
            return self.winfo_toplevel()
        except:
            print("[ERROR] Could not find root window!")
            return None

    def refresh_ui(self):
        """Refresh UI text after language change"""
        print("[DEBUG] SettingsTab.refresh_ui called")
        # This will rebuild the entire settings UI with new translations
        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()
        # Rebuild UI with new language
        self._setup_ui()

    def _setup_ui(self):
        """Set up the settings UI"""

        self.settings_canvas = ctk.CTkCanvas(self, bg=state.colors["app_bg"], highlightthickness=0)
        self.settings_scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.settings_canvas.yview)
        self.settings_scrollable_frame = ctk.CTkFrame(self.settings_canvas, fg_color=state.colors["app_bg"])

        self.settings_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all"))
        )

        self.settings_window_id = self.settings_canvas.create_window((0, 0), window=self.settings_scrollable_frame, anchor="nw")
        self.settings_canvas.configure(yscrollcommand=self.settings_scrollbar.set)

        self.settings_canvas.pack(side="left", fill="both", expand=True)

        self.settings_canvas.bind("<Configure>", self._check_settings_scroll)
        self.settings_canvas.after(100, self._check_settings_scroll)

        # Main Title
        ctk.CTkLabel(
            self.settings_scrollable_frame,
            text=t("settings.title"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=20, pady=(20, 10))

        # ═══════════════════════════════════════════════════════
        # PATH CONFIGURATION SECTION
        # ═══════════════════════════════════════════════════════
        self.path_config = PathConfigurationSection(
            self.settings_scrollable_frame,
            notification_callback=self.show_notification
        )
        self.path_config.pack(fill="x", padx=20, pady=(0, 20))

        # ═══════════════════════════════════════════════════════
        # APPEARANCE SECTION
        # ═══════════════════════════════════════════════════════
        appearance_card = ctk.CTkFrame(
            self.settings_scrollable_frame,
            fg_color=state.colors["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=state.colors["border"]
        )
        appearance_card.pack(fill="x", padx=20, pady=(0, 20))

        # Section Header
        ctk.CTkLabel(
            appearance_card,
            text=t("settings.appearance"),
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=20, pady=(20, 15))

        # Theme Toggle
        theme_frame = ctk.CTkFrame(appearance_card, fg_color="transparent")
        theme_frame.pack(anchor="w", padx=20, pady=(0, 15), fill="x")

        ctk.CTkLabel(
            theme_frame,
            text=t("settings.theme"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 15))
        
        ctk.CTkLabel(
            theme_frame,
            text=t("settings.theme_dark"),
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 5))

        self.theme_switch = ctk.CTkSwitch(theme_frame, text="", command=self._toggle_theme, width=50)
        if state.current_theme == "light":
            self.theme_switch.select()
        self.theme_switch.pack(side="left", padx=5)
        
        ctk.CTkLabel(
            theme_frame,
            text=t("settings.theme_light"),
            text_color=state.colors["text"]
        ).pack(side="left")

        # Language Selector
        self._setup_language_selector(appearance_card)

        # Bottom padding for appearance card
        ctk.CTkLabel(appearance_card, text="", height=5).pack()

        # ═══════════════════════════════════════════════════════
        # ADVANCED SECTION
        # ═══════════════════════════════════════════════════════
        advanced_card = ctk.CTkFrame(
            self.settings_scrollable_frame,
            fg_color=state.colors["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=state.colors["border"]
        )
        advanced_card.pack(fill="x", padx=20, pady=(0, 20))

        # Section Header
        ctk.CTkLabel(
            advanced_card,
            text=t("settings.advanced"),
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=20, pady=(20, 15))

        # Debug Mode
        debug_checkbox = ctk.CTkCheckBox(
            advanced_card,
            text=t("settings.debug_mode"),
            variable=self.debug_mode_var,
            command=self._toggle_debug_mode,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        debug_checkbox.pack(anchor="w", padx=20, pady=(0, 5))
        
        # Debug mode description
        ctk.CTkLabel(
            advanced_card,
            text=t("settings.debug_mode_desc"),
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text_secondary"],
            wraplength=600,
            justify="left"
        ).pack(anchor="w", padx=40, pady=(0, 20))

        # ═══════════════════════════════════════════════════════
        # THEME CUSTOMIZATION SECTION
        # ═══════════════════════════════════════════════════════
        theme_custom_card = ctk.CTkFrame(
            self.settings_scrollable_frame,
            fg_color=state.colors["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=state.colors["border"]
        )
        theme_custom_card.pack(fill="x", padx=20, pady=(0, 20))

        # Section Header
        ctk.CTkLabel(
            theme_custom_card,
            text=t("settings.theme_customization"),
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=20, pady=(20, 5))

        ctk.CTkLabel(
            theme_custom_card,
            text=t("settings.customize_desc"),
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text_secondary"],
            wraplength=600,
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 15))

        self.editors_container = ctk.CTkFrame(theme_custom_card, fg_color="transparent")

        # Dark Theme Editor Toggle
        dark_edit_frame = ctk.CTkFrame(theme_custom_card, fg_color="transparent")
        dark_edit_frame.pack(anchor="w", padx=20, pady=(0, 10), fill="x")

        ctk.CTkLabel(
            dark_edit_frame,
            text=t("settings.edit_dark"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 15))

        self.dark_edit_switch = ctk.CTkSwitch(
            dark_edit_frame,
            text="",
            command=self._toggle_dark_theme_editor,
            width=50
        )
        self.dark_edit_switch.pack(side="left")

        # Light Theme Editor Toggle
        light_edit_frame = ctk.CTkFrame(theme_custom_card, fg_color="transparent")
        light_edit_frame.pack(anchor="w", padx=20, pady=(0, 20), fill="x")

        ctk.CTkLabel(
            light_edit_frame,
            text=t("settings.edit_light"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 15))

        self.light_edit_switch = ctk.CTkSwitch(
            light_edit_frame,
            text="",
            command=self._toggle_light_theme_editor,
            width=50
        )
        self.light_edit_switch.pack(side="left")

        # Bottom padding
        ctk.CTkLabel(self.settings_scrollable_frame, text="", height=20).pack()

    def _setup_language_selector(self, parent_frame):
        """Set up the language selection UI"""
        from PIL import Image
        
        # Language Section Frame - within provided parent (appearance card)
        language_section = ctk.CTkFrame(parent_frame, fg_color="transparent")
        language_section.pack(anchor="w", padx=20, pady=(0, 15), fill="x")
        
        # Language label
        ctk.CTkLabel(
            language_section,
            text=t("settings.language"),
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left", padx=(0, 15))
        
        # Get available languages
        available_langs = get_available_languages()
        current_lang = get_current_language()
        
        # Check if languages are available
        if not available_langs:
            print("[ERROR] No languages available!")
            return
        
        # Get program root directory
        if getattr(sys, 'frozen', False):
            program_root = os.path.dirname(sys.executable)
        else:
            # Get the actual script location and go up to root
            try:
                # This file is gui/tabs/settings.py, so go up 2 levels to get to root
                current_file = os.path.abspath(__file__)
                gui_dir = os.path.dirname(current_file)  # gui/tabs
                gui_parent = os.path.dirname(gui_dir)     # gui
                program_root = os.path.dirname(gui_parent) # root
                print(f"[DEBUG] Resolved path: file={current_file}, gui={gui_dir}, gui_parent={gui_parent}, root={program_root}")
            except:
                # Fallback: use current working directory
                program_root = os.getcwd()
                print(f"[DEBUG] Using fallback path: {program_root}")
        
        self.flags_dir = os.path.join(program_root, "imagesforgui", "flags")
        
        # Debug output
        print(f"[DEBUG] Program root: {program_root}")
        print(f"[DEBUG] Flags directory: {self.flags_dir}")
        print(f"[DEBUG] Flags directory exists: {os.path.exists(self.flags_dir)}")
        if os.path.exists(self.flags_dir):
            try:
                files = os.listdir(self.flags_dir)
                print(f"[DEBUG] Files in flags directory: {files}")
            except Exception as e:
                print(f"[DEBUG] Error listing flags directory: {e}")
        
        # Container for flag image and button
        lang_container = ctk.CTkFrame(language_section, fg_color="transparent")
        lang_container.pack(side="left")
        
        # Load and display current language flag
        # Get default language as fallback
        default_lang = list(available_langs.keys())[0] if available_langs else "en_US"
        current_lang_info = available_langs.get(current_lang, available_langs.get(default_lang, {"flag": "US", "native": "English"}))
        flag_code = current_lang_info.get("flag", "US")
        # Clean up flag code - remove spaces, underscores, convert to uppercase, take first 2 chars
        flag_code = flag_code.replace(" ", "").replace("-", "").replace("_", "").upper()
        if len(flag_code) > 2:
            flag_code = flag_code[:2]
        
        # Special case: "EN" should map to "US" or "GB" 
        if flag_code == "EN":
            flag_code = "US"  # Default English to US flag
        
        # Convert to lowercase for filename (flag files are lowercase)
        flag_filename = flag_code.lower()
        flag_path = os.path.join(self.flags_dir, f"{flag_filename}.png")
        
        print(f"[DEBUG] Current language: {current_lang}")
        print(f"[DEBUG] Current language info: {current_lang_info}")
        print(f"[DEBUG] Original flag code: {current_lang_info.get('flag')}, cleaned: {flag_code}, filename: {flag_filename}")
        print(f"[DEBUG] Flag path: {flag_path}")
        print(f"[DEBUG] Flag file exists: {os.path.exists(flag_path)}")
        
        self.current_flag_label = None
        if os.path.exists(flag_path):
            try:
                flag_image = Image.open(flag_path)
                flag_image = flag_image.resize((24, 24), Image.Resampling.LANCZOS)
                flag_photo = ctk.CTkImage(light_image=flag_image, dark_image=flag_image, size=(24, 24))
                self.current_flag_label = ctk.CTkLabel(lang_container, image=flag_photo, text="")
                self.current_flag_label.image = flag_photo  # Keep reference to prevent garbage collection
                self.current_flag_label.pack(side="left", padx=(0, 5))
                print(f"[DEBUG] Flag image loaded successfully")
            except Exception as e:
                print(f"[ERROR] Failed to load flag image {flag_path}: {e}")
        else:
            print(f"[WARNING] Flag file not found: {flag_path}")
        
        # Create button to open language selector
        self.language_button = ctk.CTkButton(
            lang_container,
            text=current_lang_info.get("native", "English"),
            command=self._open_language_selector,
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["text"],
            border_width=1,
            border_color=state.colors["border"],
            width=200
        )
        self.language_button.pack(side="left")

    def _open_language_selector(self):
        """Open the language selection window"""
        print("[DEBUG] _open_language_selector called")
        # Prevent multiple windows from opening
        if hasattr(self, '_lang_window') and self._lang_window and self._lang_window.winfo_exists():
            print("[DEBUG] Window already exists, focusing it")
            self._lang_window.focus()
            return
        
        print("[DEBUG] Creating new language selector window")
        try:
            parent = self.root_app if self.root_app else self
            self._lang_window = LanguageSelectorWindow(parent, self.flags_dir, self._on_language_selected)
            print("[DEBUG] Language selector window created successfully")
        except Exception as e:
            print(f"[ERROR] Failed to create language selector window: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_language_selected(self, lang_code):
        """Handle language selection from the selector window"""
        from PIL import Image
        
        print(f"[DEBUG] Changing language to: {lang_code}")
        
        # Set the new language
        if set_language(lang_code):
            # Update flag image and button text
            available_langs = get_available_languages()
            lang_info = available_langs.get(lang_code)
            if lang_info:
                # Update button text
                self.language_button.configure(text=lang_info.get("native", "English"))
                
                # Update flag image
                if self.current_flag_label:
                    flag_code = lang_info.get("flag", "US")
                    # Clean up flag code
                    flag_code = flag_code.replace(" ", "").replace("-", "").replace("_", "").upper()
                    if len(flag_code) > 2:
                        flag_code = flag_code[:2]
                    
                    # Special case: "EN" should map to "US"
                    if flag_code == "EN":
                        flag_code = "US"
                    
                    # Convert to lowercase for filename
                    flag_filename = flag_code.lower()
                    flag_path = os.path.join(self.flags_dir, f"{flag_filename}.png")
                    
                    if os.path.exists(flag_path):
                        try:
                            flag_image = Image.open(flag_path)
                            flag_image = flag_image.resize((24, 24), Image.Resampling.LANCZOS)
                            flag_photo = ctk.CTkImage(light_image=flag_image, dark_image=flag_image, size=(24, 24))
                            self.current_flag_label.configure(image=flag_photo)
                            self.current_flag_label.image = flag_photo  # Keep a reference
                        except Exception as e:
                            print(f"[ERROR] Failed to update flag image {flag_path}: {e}")
            
            # Refresh all UI (tabs, topbar, sidebar) with new language strings
            self._refresh_all_ui()

            # Update menu buttons
            if self.menu_buttons:
                self._update_menu_button_text()
            
            # Show notification
            if self.notification_callback:
                self.notification_callback(
                    f"Language changed to {lang_info.get('native', 'Unknown')}",
                    type="success"
                )
            
            print(f"[DEBUG] Language changed successfully to {lang_code}")

    def _update_menu_button_text(self):
        """Update menu button text after language change"""
        button_translations = {
            'generator': 'menu.generator',
            'carlist': 'menu.carlist',
            'add_vehicles': 'menu.add_vehicles',
            'settings': 'menu.settings',
            'howto': 'menu.HowToTab',
            'about': 'menu.about'
        }
        
        for btn_name, translation_key in button_translations.items():
            if btn_name in self.menu_buttons:
                self.menu_buttons[btn_name].configure(text=t(translation_key))

    def _toggle_debug_mode(self):
        """Wrapper to toggle debug mode with correct app reference"""
        print(f"[DEBUG] _toggle_debug_mode called")
        print(f"[DEBUG] root_app type: {type(self.root_app)}")
        print(f"[DEBUG] root_app is CTk: {isinstance(self.root_app, ctk.CTk)}")

        if self.root_app:
            toggle_debug_mode(self.root_app, state.colors, on_close=self._on_debug_window_closed)
        else:
            print("[ERROR] Cannot toggle debug mode - no root window found!")
            self.debug_mode_var.set(False)

    def _on_debug_window_closed(self):
        """Called when debug window is closed - turn off the toggle"""
        print("[DEBUG] Debug window closed, turning off toggle")
        self.debug_mode_var.set(False)

    def _check_settings_scroll(self, event=None):
        """Only show scrollbar when content exceeds visible area AND resize frame width"""
        canvas_width = self.settings_canvas.winfo_width()
        if canvas_width > 1:
            self.settings_canvas.itemconfig(self.settings_window_id, width=canvas_width)

        self.settings_canvas.update_idletasks()

        bbox = self.settings_canvas.bbox("all")
        if bbox and bbox[3] > self.settings_canvas.winfo_height():
            if not self.settings_scrollbar.winfo_ismapped():
                self.settings_scrollbar.pack(side="right", fill="y", before=self.settings_canvas)
        else:
            if self.settings_scrollbar.winfo_ismapped():
                self.settings_scrollbar.pack_forget()

    def _toggle_theme(self):
        """Toggle between dark and light themes"""
        print(f"[DEBUG] _toggle_theme called")

        from core.settings import toggle_theme, THEMES

        new_theme = toggle_theme(self.root_app)

        # Force state in sync regardless of core/settings version
        state.current_theme = new_theme
        state.colors.update(THEMES[new_theme])

        print(f"[DEBUG] Theme toggled to: {new_theme}")

        ctk.set_appearance_mode("dark" if new_theme == "dark" else "light")

        self._refresh_all_ui()

    def _refresh_all_ui(self):
        """Rebuild all UI components after a theme change"""
        print(f"[DEBUG] _refresh_all_ui called")

        if not self.root_app:
            print("[WARNING] Cannot refresh UI - root_app not found")
            return

        # Rebuild every tab that supports it
        if hasattr(self.root_app, 'tabs'):
            for tab_name, tab in self.root_app.tabs.items():
                if hasattr(tab, 'refresh_ui'):
                    try:
                        tab.refresh_ui()
                        print(f"[DEBUG] Rebuilt tab: {tab_name}")
                    except Exception as e:
                        print(f"[ERROR] Failed to rebuild {tab_name}: {e}")

        # Rebuild topbar (handles its own background + buttons)
        if hasattr(self.root_app, 'topbar'):
            try:
                self.root_app.topbar.refresh_ui()
                print("[DEBUG] Rebuilt topbar")
            except Exception as e:
                print(f"[ERROR] Failed to rebuild topbar: {e}")

        # Update logo icons for the new theme
        if hasattr(self.root_app, '_update_output_icons'):
            self.root_app._update_output_icons()

        # Rebuild sidebar
        if hasattr(self.root_app, 'sidebar'):
            try:
                self.root_app.sidebar.refresh_ui(
                    getattr(self.root_app, '_add_vehicle_to_project_from_sidebar', None)
                )
                print("[DEBUG] Rebuilt sidebar")
            except Exception as e:
                print(f"[ERROR] Failed to rebuild sidebar: {e}")

        # Re-apply active tab highlight
        if hasattr(self.root_app, 'switch_view') and hasattr(self.root_app, 'current_tab'):
            self.root_app.switch_view(self.root_app.current_tab)

    def _toggle_dark_theme_editor(self):
        """Toggle dark theme color editor"""
        print(f"[DEBUG] _toggle_dark_theme_editor called")

        if self.dark_edit_switch.get():
            print("[DEBUG] Opening dark theme editor")
            if not self.dark_theme_edit_frame:
                self._create_dark_theme_editor()

            self.dark_theme_edit_frame.pack(fill="x", padx=10, pady=(0, 10), before=self.editors_container)
            self.editors_container.pack(fill="x", padx=10, pady=(0, 10))
        else:
            print("[DEBUG] Closing dark theme editor")
            if self.dark_theme_edit_frame:
                self.dark_theme_edit_frame.pack_forget()
                self.editors_container.pack_forget()

    def _toggle_light_theme_editor(self):
        """Toggle light theme color editor"""
        print(f"[DEBUG] _toggle_light_theme_editor called")

        if self.light_edit_switch.get():
            print("[DEBUG] Opening light theme editor")
            if not self.light_theme_edit_frame:
                self._create_light_theme_editor()

            self.light_theme_edit_frame.pack(fill="x", padx=10, pady=(0, 10), before=self.editors_container)
            self.editors_container.pack(fill="x", padx=10, pady=(0, 10))
        else:
            print("[DEBUG] Closing light theme editor")
            if self.light_theme_edit_frame:
                self.light_theme_edit_frame.pack_forget()
                self.editors_container.pack_forget()

    def _create_color_row(self, parent, theme_name, color_key, entries_dict):
        """Create a single color editing row"""
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        label_text = state.color_labels.get(color_key, color_key)
        ctk.CTkLabel(
            row_frame,
            text=label_text,
            width=150,
            anchor="w",
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 10))

        current_color = state.themes[theme_name][color_key]

        entry = ctk.CTkEntry(
            row_frame,
            width=100,
            fg_color=state.colors["card_bg"],
            text_color=state.colors["text"],
            border_color=state.colors["border"]
        )
        entry.insert(0, current_color)
        entry.pack(side="left", padx=(0, 10))

        preview = ctk.CTkLabel(
            row_frame,
            text="",
            width=60,
            height=25,
            fg_color=current_color,
            corner_radius=5
        )
        preview.pack(side="left", padx=(0, 10))

        def pick_color():
            color = colorchooser.askcolor(title=f"Choose {label_text}", initialcolor=current_color)
            if color[1]:
                entry.delete(0, 'end')
                entry.insert(0, color[1])
                preview.configure(fg_color=color[1])

        picker_btn = ctk.CTkButton(
            row_frame,
            text="Pick",
            width=60,
            command=pick_color,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"]
        )
        picker_btn.pack(side="left")

        entries_dict[color_key] = (entry, preview)

    def _create_dark_theme_editor(self):
        """Create dark theme color editor"""
        print("[DEBUG] create_dark_theme_editor called")
        self.dark_theme_edit_frame = ctk.CTkFrame(self.editors_container, fg_color=state.colors["card_bg"], corner_radius=10)

        header_frame = ctk.CTkFrame(self.dark_theme_edit_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame,
            text="Dark Theme Colors",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left")

        reset_btn = ctk.CTkButton(
            header_frame,
            text="Reset to Default",
            width=120,
            height=28,
            command=self._reset_dark_theme,
            fg_color=state.colors["warning"],
            hover_color="#e67e22",
            text_color="#0a0a0a"
        )
        reset_btn.pack(side="right", padx=5)

        colors_scroll = ctk.CTkScrollableFrame(
            self.dark_theme_edit_frame,
            height=300,
            fg_color="transparent"
        )
        colors_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        for color_key in state.editable_color_keys:
            self._create_color_row(colors_scroll, "dark", color_key, self.dark_color_entries)

        button_frame = ctk.CTkFrame(self.dark_theme_edit_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=10)

        apply_btn = ctk.CTkButton(
            button_frame,
            text="Apply Changes",
            height=35,
            command=self._apply_dark_theme_changes,
            fg_color=state.colors["success"],
            hover_color="#2fc97f",
            text_color="#0a0a0a",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        apply_btn.pack(fill="x")
        print(f"[DEBUG] Dark theme editor created with {len(state.editable_color_keys)} colors")

    def _create_light_theme_editor(self):
        """Create light theme color editor"""
        print("[DEBUG] create_light_theme_editor called")
        self.light_theme_edit_frame = ctk.CTkFrame(self.editors_container, fg_color=state.colors["card_bg"], corner_radius=10)

        header_frame = ctk.CTkFrame(self.light_theme_edit_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame,
            text="Light Theme Colors",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left")

        reset_btn = ctk.CTkButton(
            header_frame,
            text="Reset to Default",
            width=120,
            height=28,
            command=self._reset_light_theme,
            fg_color=state.colors["warning"],
            hover_color="#e67e22",
            text_color="#0a0a0a"
        )
        reset_btn.pack(side="right", padx=5)

        colors_scroll = ctk.CTkScrollableFrame(
            self.light_theme_edit_frame,
            height=300,
            fg_color="transparent"
        )
        colors_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        for color_key in state.editable_color_keys:
            self._create_color_row(colors_scroll, "light", color_key, self.light_color_entries)

        button_frame = ctk.CTkFrame(self.light_theme_edit_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=10)

        apply_btn = ctk.CTkButton(
            button_frame,
            text="Apply Changes",
            height=35,
            command=self._apply_light_theme_changes,
            fg_color=state.colors["success"],
            hover_color="#2fc97f",
            text_color="#0a0a0a",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        apply_btn.pack(fill="x")
        print(f"[DEBUG] Light theme editor created with {len(state.editable_color_keys)} colors")

    def _reset_dark_theme(self):
        """Reset dark theme to default"""
        print("[DEBUG] reset_dark_theme called")
        response = messagebox.askyesno(
            "Reset Dark Theme",
            "Are you sure you want to reset the dark theme to default colors?\n\nThis action cannot be undone.",
            icon='warning'
        )

        if response:
            print("[DEBUG] User confirmed dark theme reset")
            if reset_theme_colors("dark"):
                for color_key, (entry, preview) in self.dark_color_entries.items():
                    default_color = DEFAULT_THEMES["dark"][color_key]
                    entry.delete(0, 'end')
                    entry.insert(0, default_color)
                    preview.configure(fg_color=default_color)

                print("[DEBUG] Dark theme reset complete")
                messagebox.showinfo(
                    "Theme Reset",
                    "Dark theme has been reset to default colors.\n\nRestart the application to see changes."
                )
        else:
            print("[DEBUG] User cancelled dark theme reset")

    def _reset_light_theme(self):
        """Reset light theme to default"""
        print("[DEBUG] reset_light_theme called")
        response = messagebox.askyesno(
            "Reset Light Theme",
            "Are you sure you want to reset the light theme to default colors?\n\nThis action cannot be undone.",
            icon='warning'
        )

        if response:
            print("[DEBUG] User confirmed light theme reset")
            if reset_theme_colors("light"):
                for color_key, (entry, preview) in self.light_color_entries.items():
                    default_color = DEFAULT_THEMES["light"][color_key]
                    entry.delete(0, 'end')
                    entry.insert(0, default_color)
                    preview.configure(fg_color=default_color)

                print("[DEBUG] Light theme reset complete")
                messagebox.showinfo(
                    "Theme Reset",
                    "Light theme has been reset to default colors.\n\nRestart the application to see changes."
                )
        else:
            print("[DEBUG] User cancelled light theme reset")

    def _apply_dark_theme_changes(self):
        """Apply dark theme color changes"""
        print("[DEBUG] apply_dark_theme_changes called")
        for color_key, (entry, preview) in self.dark_color_entries.items():
            color_value = entry.get().strip()

            if not color_value.startswith('#') or len(color_value) not in [4, 7]:
                print(f"[DEBUG] Invalid color code: {color_value}")
                messagebox.showerror(
                    "Invalid Color",
                    f"Invalid color code for {state.color_labels[color_key]}: {color_value}\n\nPlease use format #RGB or #RRGGBB"
                )
                return

            update_theme_color("dark", color_key, color_value)
            preview.configure(fg_color=color_value)
            print(f"[DEBUG] Updated dark.{color_key} = {color_value}")

        print("[DEBUG] All dark theme colors applied")
        messagebox.showinfo(
            "Colors Applied",
            "Dark theme colors have been saved!\n\nRestart the application to see changes."
        )

    def _apply_light_theme_changes(self):
        """Apply light theme color changes"""
        print("[DEBUG] apply_light_theme_changes called")
        for color_key, (entry, preview) in self.light_color_entries.items():
            color_value = entry.get().strip()

            if not color_value.startswith('#') or len(color_value) not in [4, 7]:
                print(f"[DEBUG] Invalid color code: {color_value}")
                messagebox.showerror(
                    "Invalid Color",
                    f"Invalid color code for {state.color_labels[color_key]}: {color_value}\n\nPlease use format #RGB or #RRGGBB"
                )
                return

            update_theme_color("light", color_key, color_value)
            preview.configure(fg_color=color_value)
            print(f"[DEBUG] Updated light.{color_key} = {color_value}")

        print("[DEBUG] All light theme colors applied")
        messagebox.showinfo(
            "Colors Applied",
            "Light theme colors have been saved!\n\nRestart the application to see changes."
        )

    def show_notification(self, message: str, type: str = "info", duration: int = 3000):
        """
        Show notification - uses callback if available, otherwise shows messagebox

        Args:
            message: Notification message
            type: Notification type ("info", "success", "error", "warning")
            duration: Duration in milliseconds (ignored for messagebox)
        """
        if self.notification_callback:
            self.notification_callback(message, type, duration)
        else:

            if type == "error":
                messagebox.showerror("Error", message)
            elif type == "warning":
                messagebox.showwarning("Warning", message)
            else:
                messagebox.showinfo("Info", message)


class LanguageSelectorWindow(ctk.CTkToplevel):
    """Language selection window with search functionality"""
    
    def __init__(self, parent, flags_dir, callback):
        super().__init__(parent)
        
        print("[DEBUG] LanguageSelectorWindow.__init__ started")
        
        self.flags_dir = flags_dir
        self.callback = callback
        self.available_langs = get_available_languages()
        self.current_lang = get_current_language()
        self.closing = False
        
        # Window configuration
        self.title("Select Language")
        self.resizable(False, False)
        self.configure(fg_color=state.colors["app_bg"])
        
        # Make this window stay on top of the parent window
        self.transient(parent)
        self.attributes('-topmost', True)
        
        # Center the window
        self.update_idletasks()
        width = 500
        height = 600
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Debug flag directory
        print(f"[DEBUG] Language selector flags_dir: {self.flags_dir}")
        print(f"[DEBUG] Flags directory exists: {os.path.exists(self.flags_dir)}")
        if os.path.exists(self.flags_dir):
            files = os.listdir(self.flags_dir)
            print(f"[DEBUG] Number of flag files: {len(files)}")
        
        print("[DEBUG] About to setup UI")
        self._setup_ui()
        print("[DEBUG] LanguageSelectorWindow.__init__ completed")
        
        # Set up close protocol after UI is ready
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Focus and make modal
        self.lift()
        self.focus_force()
        self.grab_set()
    
    def _on_close(self):
        """Handle window close event"""
        print("[DEBUG] _on_close called")
        if not self.closing:
            self.closing = True
            try:
                self.grab_release()
            except:
                pass
            self.destroy()
            print("[DEBUG] Window destroyed")
    
    def _setup_ui(self):
        """Setup the language selector UI"""
        from PIL import Image
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header_frame,
            text="Select Language",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            header_frame,
            text="Choose your preferred language",
            font=ctk.CTkFont(size=12),
            text_color=state.colors["text_secondary"]
        ).pack(anchor="w", pady=(5, 0))
        
        # Search bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=10)
        
        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search languages...",
            height=40,
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self._on_search)
        
        # Scrollable frame for languages
        self.languages_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=state.colors["app_bg"],
            scrollbar_button_color=state.colors["accent"],
            scrollbar_button_hover_color=state.colors["accent_hover"]
        )
        self.languages_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Load all languages
        self._display_languages()
        
        # Close button
        close_btn = ctk.CTkButton(
            self,
            text="Cancel",
            command=self._on_close,
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"],
            height=40
        )
        close_btn.pack(fill="x", padx=20, pady=(0, 20))
    
    def _display_languages(self, filter_text=""):
        """Display language options with flags"""
        from PIL import Image
        
        # Clear existing widgets
        for widget in self.languages_frame.winfo_children():
            widget.destroy()
        
        # Filter languages
        filtered_langs = {}
        for lang_code, lang_info in self.available_langs.items():
            if filter_text.lower() in lang_info.get("native", "").lower() or \
               filter_text.lower() in lang_info.get("name", "").lower():
                filtered_langs[lang_code] = lang_info
        
        # Sort by native name
        sorted_langs = sorted(filtered_langs.items(), key=lambda x: x[1].get("native", ""))
        
        # Display languages
        for lang_code, lang_info in sorted_langs:
            self._create_language_button(lang_code, lang_info)
        
        # Show "no results" if nothing found
        if not filtered_langs:
            ctk.CTkLabel(
                self.languages_frame,
                text="No languages found",
                text_color=state.colors["text_secondary"],
                font=ctk.CTkFont(size=14)
            ).pack(pady=50)
    
    def _create_language_button(self, lang_code, lang_info):
        """Create a button for a language option"""
        from PIL import Image
        
        # Is this the current language?
        is_current = (lang_code == self.current_lang)
        
        normal_color = state.colors["accent"] if is_current else state.colors["card_bg"]
        hover_color  = state.colors["accent_hover"] if is_current else state.colors["card_hover"]

        # Create button frame
        btn_frame = ctk.CTkFrame(
            self.languages_frame,
            fg_color=normal_color,
            corner_radius=8,
            height=60
        )
        btn_frame.pack(fill="x", pady=5)
        btn_frame.pack_propagate(False)

        def _on_enter(e): btn_frame.configure(fg_color=hover_color)
        def _on_leave(e): btn_frame.configure(fg_color=normal_color)

        # Make the frame clickable
        btn_frame.bind("<Button-1>", lambda e: self._select_language(lang_code))
        btn_frame.bind("<Enter>", _on_enter)
        btn_frame.bind("<Leave>", _on_leave)
        
        # Inner container for flag and text
        inner_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        inner_frame.pack(fill="both", expand=True, padx=15, pady=10)
        inner_frame.bind("<Button-1>", lambda e: self._select_language(lang_code))
        inner_frame.bind("<Enter>", _on_enter)
        inner_frame.bind("<Leave>", _on_leave)
        
        # Flag image
        flag_code = lang_info.get("flag", "US")
        # Clean up flag code - remove spaces, underscores, convert to uppercase, take first 2 chars
        flag_code = flag_code.replace(" ", "").replace("-", "").replace("_", "").upper()
        if len(flag_code) > 2:
            flag_code = flag_code[:2]
        
        # Special case: "EN" should map to "US"
        if flag_code == "EN":
            flag_code = "US"
        
        # Convert to lowercase for filename (flag files are lowercase)
        flag_filename = flag_code.lower()
        flag_path = os.path.join(self.flags_dir, f"{flag_filename}.png")
        
        # Only print if flag not found (reduce spam)
        if not os.path.exists(flag_path):
            print(f"[DEBUG] Creating button for {lang_code}, flag not found: {flag_filename}")
        
        if os.path.exists(flag_path):
            try:
                flag_image = Image.open(flag_path)
                flag_image = flag_image.resize((32, 32), Image.Resampling.LANCZOS)
                flag_photo = ctk.CTkImage(light_image=flag_image, dark_image=flag_image, size=(32, 32))
                flag_label = ctk.CTkLabel(inner_frame, image=flag_photo, text="")
                flag_label.image = flag_photo  # Keep reference
                flag_label.pack(side="left", padx=(0, 15))
                flag_label.bind("<Button-1>", lambda e: self._select_language(lang_code))
                flag_label.bind("<Enter>", _on_enter)
                flag_label.bind("<Leave>", _on_leave)
            except Exception as e:
                print(f"[ERROR] Failed to load flag image {flag_path}: {e}")
        
        # Text container
        text_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True)
        text_frame.bind("<Button-1>", lambda e: self._select_language(lang_code))
        text_frame.bind("<Enter>", _on_enter)
        text_frame.bind("<Leave>", _on_leave)
        
        # Native name
        native_label = ctk.CTkLabel(
            text_frame,
            text=lang_info.get("native", lang_code),
            font=ctk.CTkFont(size=16, weight="bold" if is_current else "normal"),
            text_color="#ffffff" if is_current else state.colors["text"],
            anchor="w"
        )
        native_label.pack(anchor="w")
        native_label.bind("<Button-1>", lambda e: self._select_language(lang_code))
        native_label.bind("<Enter>", _on_enter)
        native_label.bind("<Leave>", _on_leave)
        
        # English name
        english_label = ctk.CTkLabel(
            text_frame,
            text=lang_info.get("name", ""),
            font=ctk.CTkFont(size=12),
            text_color="#e0e0e0" if is_current else state.colors["text_secondary"],
            anchor="w"
        )
        english_label.pack(anchor="w")
        english_label.bind("<Button-1>", lambda e: self._select_language(lang_code))
        english_label.bind("<Enter>", _on_enter)
        english_label.bind("<Leave>", _on_leave)
        
        # Current indicator
        if is_current:
            indicator = ctk.CTkLabel(
                inner_frame,
                text="✓",
                font=ctk.CTkFont(size=24, weight="bold"),
                text_color="#ffffff"
            )
            indicator.pack(side="right")
            indicator.bind("<Button-1>", lambda e: self._select_language(lang_code))
            indicator.bind("<Enter>", _on_enter)
            indicator.bind("<Leave>", _on_leave)
    
    def _on_search(self, event):
        """Handle search input"""
        filter_text = self.search_entry.get()
        self._display_languages(filter_text)
    
    def _select_language(self, lang_code):
        """Handle language selection"""
        print(f"[DEBUG] _select_language called with {lang_code}")
        if not self.closing:
            self.closing = True
            self.grab_release()
            self.callback(lang_code)
            self.destroy()
            print("[DEBUG] Language selected and window destroyed")