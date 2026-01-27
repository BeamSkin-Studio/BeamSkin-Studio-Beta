"""
Settings Tab - Theme editor and developer toggles
"""
from typing import Dict, Tuple, Optional
import customtkinter as ctk
from tkinter import messagebox, colorchooser
import sys
import os
from gui.state import state
from core.settings import reset_theme_colors, update_theme_color, DEFAULT_THEMES
from utils.debug import toggle_debug_mode
from gui.components.path_configuration import PathConfigurationSection


print(f"[DEBUG] Loading class: SettingsTab")


class SettingsTab(ctk.CTkFrame):
    """Settings tab with theme customization and developer mode"""
    
    def __init__(self, parent: ctk.CTk, main_container: ctk.CTkFrame, menu_frame: ctk.CTkFrame,
                 menu_buttons: Dict[str, ctk.CTkButton], switch_view_callback, notification_callback=None):
    
        print(f"[DEBUG] __init__ called")
        super().__init__(parent, fg_color=state.colors["app_bg"])
        
        self.main_container = main_container
        self.menu_frame = menu_frame
        self.menu_buttons = menu_buttons
        self.switch_view_callback = switch_view_callback
        self.notification_callback = notification_callback
        
        # FIXED: Get the actual root window, not the parent frame
        # Walk up the widget hierarchy to find the CTk root window
        self.root_app = self._get_root_window()
        
        # State variables
        self.developer_mode_var = ctk.BooleanVar(value=False)
        self.debug_mode_var = ctk.BooleanVar(value=False)
        
        # Theme editor frames
        self.dark_theme_edit_frame: Optional[ctk.CTkFrame] = None
        self.light_theme_edit_frame: Optional[ctk.CTkFrame] = None
        self.dark_color_entries: Dict[str, Tuple[ctk.CTkEntry, ctk.CTkLabel]] = {}
        self.light_color_entries: Dict[str, Tuple[ctk.CTkEntry, ctk.CTkLabel]] = {}
        
        # Developer tab reference (created dynamically)
        self.developer_tab: Optional[ctk.CTkFrame] = None
        
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
    
    def _setup_ui(self):
        """Set up the settings UI"""
        # Create scrollable canvas
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
        
        # Title
        ctk.CTkLabel(
            self.settings_scrollable_frame,
            text="Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        # === PATH CONFIGURATION SECTION ===
        self.path_config = PathConfigurationSection(
            self.settings_scrollable_frame,
            notification_callback=self.show_notification
        )
        self.path_config.pack(fill="x", padx=10, pady=(10, 15))
        
        # Separator after path config
        ctk.CTkLabel(
            self.settings_scrollable_frame,
            text="─" * 60,
            text_color=state.colors["border"]
        ).pack(pady=10)
        
        # Theme toggle
        theme_frame = ctk.CTkFrame(self.settings_scrollable_frame, fg_color="transparent")
        theme_frame.pack(anchor="w", padx=10, pady=(0, 10), fill="x")
        
        ctk.CTkLabel(theme_frame, text="Theme:", text_color=state.colors["text"]).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(theme_frame, text="Dark Mode", text_color=state.colors["text"]).pack(side="left", padx=(0, 5))
        
        self.theme_switch = ctk.CTkSwitch(theme_frame, text="", command=self._toggle_theme, width=50)
        if state.current_theme == "light":
            self.theme_switch.select()
        self.theme_switch.pack(side="left", padx=5)
        ctk.CTkLabel(theme_frame, text="Light Mode", text_color=state.colors["text"]).pack(side="left")
        
        # --- Developer Section ---
        # Create a container frame to keep developer items together
        self.dev_container = ctk.CTkFrame(self.settings_scrollable_frame, fg_color="transparent")
        self.dev_container.pack(anchor="w", padx=10, pady=(0, 5), fill="x")
        
        # Developer Mode Checkbox (now inside dev_container)
        developer_checkbox = ctk.CTkCheckBox(
            self.dev_container,
            text="Developer Mode",
            variable=self.developer_mode_var,
            command=self._toggle_developer_mode
        )
        developer_checkbox.pack(anchor="w", pady=(0, 5))
        
        # Debug mode frame (now inside dev_container)
        self.debug_mode_frame = ctk.CTkFrame(self.dev_container, fg_color="transparent")
        
        # If developer mode is already enabled (e.g. on refresh), show the debug toggle immediately
        if self.developer_mode_var.get():
            self.debug_mode_frame.pack(anchor="w", padx=20, pady=(0, 5))
        
        # FIXED: Pass the actual root window, not self.parent_app
        debug_checkbox = ctk.CTkCheckBox(
            self.debug_mode_frame,
            text="Debug Mode (Opens debug console)",
            variable=self.debug_mode_var,
            command=self._toggle_debug_mode  # Use wrapper method
        )
        debug_checkbox.pack(anchor="w")
        
        # Separator
        ctk.CTkLabel(
            self.settings_scrollable_frame,
            text="─" * 60,
            text_color=state.colors["border"]
        ).pack(pady=10)
        
        # Theme Customization
        ctk.CTkLabel(
            self.settings_scrollable_frame,
            text="Theme Customization",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(
            self.settings_scrollable_frame,
            text="Customize theme colors (requires restart to apply)",
            font=ctk.CTkFont(size=11),
            text_color=state.colors["text_secondary"]
        ).pack(anchor="w", padx=10, pady=(0, 10))
        
        # Editors container - CRITICAL: This uses grid layout for 50/50 split
        self.editors_container = ctk.CTkFrame(self.settings_scrollable_frame, fg_color="transparent")
        
        # Dark theme toggle
        dark_edit_frame = ctk.CTkFrame(self.settings_scrollable_frame, fg_color="transparent")
        dark_edit_frame.pack(anchor="w", padx=10, pady=(0, 5), fill="x")
        
        ctk.CTkLabel(
            dark_edit_frame,
            text="Edit Dark Theme Colors",
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 10))
        
        self.dark_edit_switch = ctk.CTkSwitch(
            dark_edit_frame,
            text="",
            command=self._toggle_dark_theme_editor,
            width=50
        )
        self.dark_edit_switch.pack(side="left")
        
        # Light theme toggle
        light_edit_frame = ctk.CTkFrame(self.settings_scrollable_frame, fg_color="transparent")
        light_edit_frame.pack(anchor="w", padx=10, pady=(0, 10), fill="x")
        
        ctk.CTkLabel(
            light_edit_frame,
            text="Edit Light Theme Colors",
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 10))
        
        self.light_edit_switch = ctk.CTkSwitch(
            light_edit_frame,
            text="",
            command=self._toggle_light_theme_editor,
            width=50
        )
        self.light_edit_switch.pack(side="left")
    
    def _toggle_debug_mode(self):
        """Wrapper to toggle debug mode with correct app reference"""
        print(f"[DEBUG] _toggle_debug_mode called")
        print(f"[DEBUG] root_app type: {type(self.root_app)}")
        print(f"[DEBUG] root_app is CTk: {isinstance(self.root_app, ctk.CTk)}")
        
        if self.root_app:
            toggle_debug_mode(self.root_app, state.colors, on_close=self._on_debug_window_closed)
        else:
            print("[ERROR] Cannot toggle debug mode - no root window found!")
            self.debug_mode_var.set(False)  # Uncheck the checkbox
    
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
                self.settings_scrollbar.pack(side="right", fill="y")
                self.settings_canvas.after(10, lambda: self.settings_canvas.itemconfig(
                    self.settings_window_id, width=self.settings_canvas.winfo_width()))
        else:
            if self.settings_scrollbar.winfo_ismapped():
                self.settings_scrollbar.pack_forget()
                self.settings_canvas.after(10, lambda: self.settings_canvas.itemconfig(
                    self.settings_window_id, width=self.settings_canvas.winfo_width()))
    
    def _toggle_theme(self):
        """Toggle between light and dark themes with app restart"""
        print("[DEBUG] _toggle_theme called")
        
        # Determine the new theme
        new_theme = "light" if state.current_theme == "dark" else "dark"
        
        # Show themed confirmation dialog
        from gui.confirmation_dialog import askyesno
        response = askyesno(
            self.winfo_toplevel(),
            "Restart Required",
            f"Switch to {new_theme.title()} Mode?\n\n"
            f"The application will restart to apply the theme change.",
            state.colors,
            icon="🔄",
            danger=False
        )
        
        if response:
            print(f"[DEBUG] User confirmed theme switch to {new_theme}")
            
            # Apply the theme change
            try:
                from core.settings import toggle_theme
                toggle_theme(self.root_app)
                print(f"[DEBUG] Theme setting saved to {new_theme}")
            except Exception as e:
                print(f"[ERROR] Failed to toggle theme: {e}")
                from gui.confirmation_dialog import showerror
                showerror(
                    self.winfo_toplevel(),
                    "Error",
                    f"Failed to save theme setting:\n{e}",
                    state.colors
                )
                # Revert switch
                self._revert_theme_switch()
                return
            
            # Restart the application
            self._restart_application()
        else:
            print("[DEBUG] User cancelled theme switch - reverting toggle")
            # Revert the switch to its previous position
            self._revert_theme_switch()
    
    def _revert_theme_switch(self):
        """Revert the theme switch to match the current theme"""
        print(f"[DEBUG] Reverting theme switch to match current theme: {state.current_theme}")
        if state.current_theme == "light":
            # Should be selected (on)
            if not self.theme_switch.get():
                self.theme_switch.select()
        else:
            # Should be deselected (off)
            if self.theme_switch.get():
                self.theme_switch.deselect()
    
    def _restart_application(self):
        """Restart the application to apply theme changes"""
        print("[DEBUG] _restart_application called")
        
        try:
            python = sys.executable
            
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                script = sys.executable
            else:
                script = os.path.abspath(sys.argv[0])
            
            print(f"[DEBUG] Python executable: {python}")
            print(f"[DEBUG] Script path: {script}")
            
            print("[DEBUG] Closing current application window...")
            if self.root_app:
                self.root_app.withdraw()  # Hide window first
                self.root_app.quit()      # Stop mainloop
            
            # Start new instance
            print("[DEBUG] Starting new application instance...")
            import subprocess
            
            if sys.platform == 'win32':
                if getattr(sys, 'frozen', False):
                    # Executable
                    subprocess.Popen([script], creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    # Script - use pythonw to avoid console
                    pythonw = python.replace('python.exe', 'pythonw.exe')
                    if os.path.exists(pythonw):
                        subprocess.Popen([pythonw, script])
                    else:
                        subprocess.Popen([python, script], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # Linux/Mac
                subprocess.Popen([python, script])
            
            print("[DEBUG] New instance started, exiting current process...")
            
            # Force exit
            sys.exit(0)
            
        except Exception as e:
            print(f"[ERROR] Failed to restart application: {e}")
            import traceback
            traceback.print_exc()
            
            messagebox.showerror(
                "Restart Failed",
                f"Failed to restart the application:\n\n{e}\n\n"
                f"Please close and restart the application manually to see the theme changes."
            )
            
            if self.root_app:
                self.root_app.quit()
    
    def _toggle_developer_mode(self):
        """Toggle developer mode and show/hide developer tab"""
        print(f"[DEBUG] Developer mode toggled: {self.developer_mode_var.get()}")
        
        if self.developer_mode_var.get():
            print("[DEBUG] Developer mode enabled")
            
            # Show debug mode checkbox (it will now appear directly under the developer toggle)
            self.debug_mode_frame.pack(anchor="w", padx=20, pady=(0, 5))
            
            # Create developer tab if it doesn't exist
            if self.developer_tab is None:
                from gui.tabs.developer import DeveloperTab
                
                # Get notification callback from root app
                notification_callback = None
                if self.root_app and hasattr(self.root_app, 'show_notification'):
                    notification_callback = self.root_app.show_notification
                    print(f"[DEBUG] Found notification callback from root app")
                else:
                    print(f"[DEBUG] Warning: No notification callback found in root app")
                
                self.developer_tab = DeveloperTab(self.main_container, notification_callback)
                print(f"[DEBUG] Developer tab created successfully")
            
            # Add Developer button to menu - get current references from topbar
            if "developer" not in self.menu_buttons:
                try:
                    # Get current topbar from root app
                    current_menu_frame = None
                    current_menu_buttons = None
                    
                    if self.root_app and hasattr(self.root_app, 'topbar'):
                        current_menu_frame = self.root_app.topbar.menu_frame
                        current_menu_buttons = self.root_app.topbar.menu_buttons
                        print(f"[DEBUG] Got current menu_frame and menu_buttons from topbar")
                    else:
                        # Fallback to stored references
                        current_menu_frame = self.menu_frame
                        current_menu_buttons = self.menu_buttons
                        print(f"[DEBUG] Using stored menu_frame reference")
                    
                    # Verify the menu_frame still exists
                    if current_menu_frame and current_menu_frame.winfo_exists():
                        dev_button = ctk.CTkButton(
                            current_menu_frame,
                            text="Developer",
                            fg_color="transparent",
                            text_color=state.colors["text_secondary"],
                            hover_color=state.colors["card_hover"],
                            font=ctk.CTkFont(size=12),
                            command=lambda: self.switch_view_callback("developer")
                        )
                        dev_button.pack(side="left", padx=5)
                        current_menu_buttons["developer"] = dev_button
                        
                        # Update stored reference
                        self.menu_buttons = current_menu_buttons
                        print(f"[DEBUG] Developer menu button added successfully")
                    else:
                        print(f"[ERROR] menu_frame no longer exists or is invalid")
                        self.developer_mode_var.set(False)  # Revert the toggle
                        
                except Exception as e:
                    print(f"[ERROR] Failed to add Developer button: {e}")
                    import traceback
                    traceback.print_exc()
                    self.developer_mode_var.set(False)  # Revert the toggle
        else:
            print("[DEBUG] Developer mode disabled")
            
            # Hide debug mode checkbox and uncheck it
            self.debug_mode_frame.pack_forget()
            self.debug_mode_var.set(False)
            
            # Remove Developer button from menu
            if "developer" in self.menu_buttons:
                try:
                    self.menu_buttons["developer"].destroy()
                    del self.menu_buttons["developer"]
                    print(f"[DEBUG] Developer menu button removed successfully")
                except Exception as e:
                    print(f"[ERROR] Failed to remove Developer button: {e}")
                    # Still remove from dict even if destroy failed
                    if "developer" in self.menu_buttons:
                        del self.menu_buttons["developer"]
    
    def _toggle_dark_theme_editor(self):
        """Toggle dark theme editor visibility"""
        if self.dark_edit_switch.get():
            print("[DEBUG] Showing dark theme editor")
            if self.dark_theme_edit_frame is None:
                self._create_dark_theme_editor()
            
            # Use grid for 50/50 split
            self.editors_container.pack(fill="both", expand=True, padx=10, pady=10)
            self.editors_container.grid_columnconfigure(0, weight=1)
            self.editors_container.grid_columnconfigure(1, weight=1)
            
            self.dark_theme_edit_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
            
            # If light editor is also visible, place it in column 1
            if self.light_edit_switch.get() and self.light_theme_edit_frame:
                self.light_theme_edit_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        else:
            print("[DEBUG] Hiding dark theme editor")
            if self.dark_theme_edit_frame:
                self.dark_theme_edit_frame.grid_forget()
            
            # If no editors are visible, hide container
            if not self.light_edit_switch.get():
                self.editors_container.pack_forget()
    
    def _toggle_light_theme_editor(self):
        """Toggle light theme editor visibility"""
        if self.light_edit_switch.get():
            print("[DEBUG] Showing light theme editor")
            if self.light_theme_edit_frame is None:
                self._create_light_theme_editor()
            
            # Use grid for 50/50 split
            self.editors_container.pack(fill="both", expand=True, padx=10, pady=10)
            self.editors_container.grid_columnconfigure(0, weight=1)
            self.editors_container.grid_columnconfigure(1, weight=1)
            
            self.light_theme_edit_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
            
            # If dark editor is also visible, place it in column 0
            if self.dark_edit_switch.get() and self.dark_theme_edit_frame:
                self.dark_theme_edit_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        else:
            print("[DEBUG] Hiding light theme editor")
            if self.light_theme_edit_frame:
                self.light_theme_edit_frame.grid_forget()
            
            # If no editors are visible, hide container
            if not self.dark_edit_switch.get():
                self.editors_container.pack_forget()
    
    def _create_color_row(self, parent, theme_name, color_key, entries_dict):
        """Create a color input row with live preview"""
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        
        # Label
        label = ctk.CTkLabel(
            row_frame,
            text=state.color_labels[color_key],
            width=150,
            anchor="w",
            text_color=state.colors["text"]
        )
        label.pack(side="left", padx=(0, 10))
        
        # Color preview box
        current_color = state.themes[theme_name][color_key]
        preview = ctk.CTkLabel(
            row_frame,
            text="",
            width=30,
            height=20,
            fg_color=current_color,
            corner_radius=4
        )
        preview.pack(side="left", padx=(0, 10))
        
        # Entry field
        entry = ctk.CTkEntry(
            row_frame,
            width=100,
            placeholder_text="#RRGGBB"
        )
        entry.insert(0, current_color)
        entry.pack(side="left", padx=(0, 10))
        
        # Live preview update
        def update_preview(event=None):
            print(f"[DEBUG] update_preview called")
            color = entry.get().strip()
            if color.startswith('#') and len(color) in [4, 7]:
                try:
                    preview.configure(fg_color=color)
                except:
                    pass
        
        entry.bind("<KeyRelease>", update_preview)
        
        # Color picker button
        def pick_color():
            print(f"[DEBUG] pick_color called")
            color = colorchooser.askcolor(
                color=current_color,
                title=f"Choose {state.color_labels[color_key]}"
            )
            if color[1]:
                entry.delete(0, 'end')
                entry.insert(0, color[1])
                update_preview()
        
        picker_btn = ctk.CTkButton(
            row_frame,
            text="🎨",
            width=30,
            command=pick_color,
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"]
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
            # Fallback to messagebox if no callback provided
            if type == "error":
                messagebox.showerror("Error", message)
            elif type == "warning":
                messagebox.showwarning("Warning", message)
            else:
                messagebox.showinfo("Info", message)