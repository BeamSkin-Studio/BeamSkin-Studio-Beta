"""
Language Selection Dialog - First launch language picker
Enhanced with full localization support
"""
import customtkinter as ctk
from gui.icon_helper import set_window_icon
from typing import Callable, Optional

try:
    from core.localization import get_available_languages, set_language, get_localization, t
except ImportError:
    print("[ERROR] Failed to import localization module")
    def get_available_languages():
        return {"en": {"name": "English", "native": "English", "flag": "🇬🇧"}}
    def set_language(lang): return True
    def get_localization(): return None
    def t(key, **kwargs): return key

class LanguageSelectionDialog:
    """Dialog for selecting application language on first launch"""
    
    def __init__(self, parent, colors: dict, on_complete: Optional[Callable] = None):
        """
        Create language selection dialog
        
        Args:
            parent: Parent window
            colors: Theme colors dictionary
            on_complete: Callback function when language is selected
        """
        self.colors = colors
        self.on_complete = on_complete
        self.selected_language = None
        
        # Create dialog window
        self.dialog = ctk.CTkToplevel(parent)
        set_window_icon(self.dialog)
        self.dialog.title(t("language_selection.title", default="Select Your Language"))
        self.dialog.geometry("700x600")
        self.dialog.resizable(False, False)
        
        # Make modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center on screen
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"700x600+{x}+{y}")
        
        # Bring to front
        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.attributes('-topmost', True)
        self.dialog.after(100, lambda: self.dialog.attributes('-topmost', False))
        
        # Prevent closing without selection
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the dialog UI"""
        # Main frame
        main_frame = ctk.CTkFrame(self.dialog, fg_color=self.colors["frame_bg"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header with icon
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(pady=(20, 10))
        
        ctk.CTkLabel(
            header_frame,
            text="🌍",
            font=ctk.CTkFont(size=64)
        ).pack()
        
        # Title
        ctk.CTkLabel(
            main_frame,
            text=t("language_selection.title", default="Select Your Language"),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=self.colors["text"]
        ).pack(pady=(10, 5))
        
        # Description
        ctk.CTkLabel(
            main_frame,
            text=t("language_selection.subtitle", default="Choose your preferred language for BeamSkin Studio"),
            font=ctk.CTkFont(size=14),
            text_color=self.colors["text_secondary"]
        ).pack(pady=(0, 20))
        
        # Scrollable language list
        languages_frame = ctk.CTkScrollableFrame(
            main_frame,
            fg_color=self.colors["card_bg"],
            corner_radius=10,
            height=320
        )
        languages_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Get available languages
        available_languages = get_available_languages()
        current_language = get_localization().current_language if get_localization() else "en"
        
        # Create language buttons
        self.language_buttons = {}
        for lang_code, lang_info in sorted(available_languages.items(), key=lambda x: x[1]['name']):
            self._create_language_button(
                languages_frame,
                lang_code,
                lang_info,
                is_selected=(lang_code == current_language)
            )
        
        # Continue button
        self.continue_button = ctk.CTkButton(
            main_frame,
            text=t("language_selection.continue", default="Continue"),
            command=self._on_continue,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color=self.colors["accent_text"],
            height=45,
            corner_radius=8,
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.continue_button.pack(fill="x", padx=20, pady=(0, 10))
        
        # Set initial selection if a language is already set
        if current_language:
            self.selected_language = current_language
    
    def _create_language_button(self, parent, lang_code: str, lang_info: dict, is_selected: bool = False):
        """Create a language selection button"""
        # Create clickable frame instead of button to avoid geometry manager issues
        btn_frame = ctk.CTkFrame(
            parent,
            fg_color=self.colors["accent"] if is_selected else self.colors["card_bg"],
            corner_radius=8,
            height=60
        )
        btn_frame.pack(fill="x", padx=10, pady=5)
        btn_frame.pack_propagate(False)
        
        # Make the frame clickable
        btn_frame.bind("<Button-1>", lambda e: self._select_language(lang_code))
        btn_frame.bind("<Enter>", lambda e: btn_frame.configure(
            fg_color=self.colors["accent_hover"] if is_selected else self.colors["card_hover"]
        ))
        btn_frame.bind("<Leave>", lambda e: btn_frame.configure(
            fg_color=self.colors["accent"] if is_selected else self.colors["card_bg"]
        ))
        
        # Content frame
        content_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=10)
        content_frame.bind("<Button-1>", lambda e: self._select_language(lang_code))
        
        # Left side - Flag and names
        left_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True)
        left_frame.bind("<Button-1>", lambda e: self._select_language(lang_code))
        
        # Flag
        flag_label = ctk.CTkLabel(
            left_frame,
            text=lang_info["flag"],
            font=ctk.CTkFont(size=32)
        )
        flag_label.pack(side="left", padx=(0, 15))
        flag_label.bind("<Button-1>", lambda e: self._select_language(lang_code))
        
        # Names frame
        names_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        names_frame.pack(side="left", fill="both", expand=True)
        names_frame.bind("<Button-1>", lambda e: self._select_language(lang_code))
        
        # Native name (larger)
        native_label = ctk.CTkLabel(
            names_frame,
            text=lang_info["native"],
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["accent_text"] if is_selected else self.colors["text"],
            anchor="w"
        )
        native_label.pack(anchor="w")
        native_label.bind("<Button-1>", lambda e: self._select_language(lang_code))
        
        # English name (smaller)
        if lang_info["native"] != lang_info["name"]:
            english_label = ctk.CTkLabel(
                names_frame,
                text=lang_info["name"],
                font=ctk.CTkFont(size=12),
                text_color=self.colors["accent_text"] if is_selected else self.colors["text_secondary"],
                anchor="w"
            )
            english_label.pack(anchor="w")
            english_label.bind("<Button-1>", lambda e: self._select_language(lang_code))
        
        # Right side - Selection indicator
        if is_selected:
            check_label = ctk.CTkLabel(
                content_frame,
                text="✓",
                font=ctk.CTkFont(size=24, weight="bold"),
                text_color=self.colors["accent_text"]
            )
            check_label.pack(side="right", padx=(10, 0))
            check_label.bind("<Button-1>", lambda e: self._select_language(lang_code))
        
        # Store button reference
        self.language_buttons[lang_code] = btn_frame
    
    def _select_language(self, lang_code: str):
        """Handle language selection"""
        print(f"[DEBUG] Language selected: {lang_code}")
        
        # Update selection
        self.selected_language = lang_code
        
        # Update button appearances
        for code, btn_frame in self.language_buttons.items():
            if code == lang_code:
                btn_frame.configure(fg_color=self.colors["accent"])
            else:
                btn_frame.configure(fg_color="transparent")
        
        # Set the language immediately
        set_language(lang_code)
        
        # Recreate the entire dialog to show checkmark and update text
        for widget in self.dialog.winfo_children():
            widget.destroy()
        
        # Recreate UI with new selection
        self._create_ui()
    
    def _on_continue(self):
        """Handle continue button click"""
        if self.selected_language:
            print(f"[DEBUG] Language selection confirmed: {self.selected_language}")
            
            # Set the language
            set_language(self.selected_language)
            
            # Save to settings
            from core.settings import app_settings, save_settings
            app_settings["language"] = self.selected_language
            save_settings()
            
            # Call completion callback
            if self.on_complete:
                self.on_complete(self.selected_language)
            
            # Close dialog
            self.dialog.destroy()
        else:
            print("[DEBUG] No language selected, using default")
            self._on_cancel()
    
    def _on_cancel(self):
        """Handle cancel/close - use default language"""
        print("[DEBUG] Language selection cancelled, using default")
        
        # Ensure a language is set
        if not self.selected_language:
            from core.localization import DEFAULT_LANGUAGE
            set_language(DEFAULT_LANGUAGE)
            self.selected_language = DEFAULT_LANGUAGE
        
        # Call completion callback
        if self.on_complete:
            self.on_complete(self.selected_language)
        
        # Close dialog
        self.dialog.destroy()
    
    def show(self):
        """Show the dialog and wait for completion"""
        self.dialog.wait_window()
        return self.selected_language


def show_language_selection(parent, colors: dict, on_complete: Optional[Callable] = None) -> str:
    """
    Show language selection dialog
    
    Args:
        parent: Parent window
        colors: Theme colors dictionary
        on_complete: Optional callback when language is selected
    
    Returns:
        Selected language code
    """
    dialog = LanguageSelectionDialog(parent, colors, on_complete)
    return dialog.show()