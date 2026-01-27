"""
Main Window - Entry point for the BeamSkin Studio application
"""
from typing import Dict, Optional
import customtkinter as ctk
from PIL import Image
import os

from gui.state import state
from gui.components.preview import HoverPreviewManager
from gui.components.navigation import Sidebar, Topbar
from gui.components.dialogs import show_update_dialog, show_wip_warning, show_notification
from gui.tabs.settings import SettingsTab
from gui.tabs.car_list import CarListTab
from gui.tabs.generator import GeneratorTab
from gui.tabs.howto import HowToTab
from gui.tabs.developer import DeveloperTab, load_added_vehicles_at_startup
from gui.tabs.about import AboutTab

from utils.debug import setup_universal_scroll_handler


print(f"[DEBUG] Loading class: BeamSkinStudioApp")


class BeamSkinStudioApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
    
        print(f"[DEBUG] __init__ called")
        super().__init__()
        
        # Window setup
        self.title("BeamSkin Studio")
        
        # Set window icon
        icon_path = os.path.join("gui", "Icons", "BeamSkin_Studio.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
                print(f"[DEBUG] Set window icon: {icon_path}")
            except Exception as e:
                print(f"[DEBUG] Failed to set icon: {e}")
        
        self.geometry("1600x1200")
        self.minsize(1000, 1000)
        self.configure(fg_color=state.colors["app_bg"])
        
        # Set appearance
        ctk.set_appearance_mode("dark" if state.current_theme == "dark" else "light")
        ctk.set_default_color_theme("blue")
        
        # Initialize managers
        self.preview_overlay = self._create_preview_overlay()
        self.preview_manager = HoverPreviewManager(self, self.preview_overlay)
        
        # Icon references
        self.steam_icon_white: Optional[ctk.CTkImage] = None
        self.steam_icon_black: Optional[ctk.CTkImage] = None
        self.folder_icon_white: Optional[ctk.CTkImage] = None
        self.folder_icon_black: Optional[ctk.CTkImage] = None
        
        # Logo references
        self.logo_white: Optional[ctk.CTkImage] = None
        self.logo_black: Optional[ctk.CTkImage] = None
        
        # Load icons and logos
        self._load_output_icons()
        self._load_logos()
        
        # UI Components
        self.topbar: Optional[Topbar] = None
        self.sidebar: Optional[Sidebar] = None
        self.main_container: Optional[ctk.CTkFrame] = None
        self.tabs: Dict[str, ctk.CTkFrame] = {}
        self.current_tab: str = "generator"
        
        self._setup_ui()
        self._update_output_icons()
        
        # Bind closing event
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def show_notification(self, message: str, type: str = "info", duration: int = 3000):
    
        print(f"[DEBUG] show_notification called")
        """Show a notification at the top of the app
        
        Args:
            message: Notification message
            type: Notification type ('info', 'success', 'warning', 'error')
            duration: How long to show notification in milliseconds
        """
        show_notification(self, message, type, duration)
    
    def _create_preview_overlay(self) -> ctk.CTkFrame:
        """Create the preview overlay frame"""
        preview_overlay = ctk.CTkFrame(
            self,
            fg_color=state.colors["card_bg"],
            border_color=state.colors["accent"],
            border_width=2,
            corner_radius=10
        )
        return preview_overlay
    
    def _load_output_icons(self):
        """Load output icons for both themes"""
        icon_dir = os.path.join("gui", "Icons")
        icon_size = (20, 20)
        
        try:
            steam_white_path = os.path.join(icon_dir, "Steam_logo_white.png")
            steam_black_path = os.path.join(icon_dir, "Steam_logo_black.png")
            
            if os.path.exists(steam_white_path):
                self.steam_icon_white = ctk.CTkImage(
                    light_image=Image.open(steam_white_path),
                    dark_image=Image.open(steam_white_path),
                    size=icon_size
                )
                print(f"[DEBUG] Loaded Steam white icon from: {steam_white_path}")
            
            if os.path.exists(steam_black_path):
                self.steam_icon_black = ctk.CTkImage(
                    light_image=Image.open(steam_black_path),
                    dark_image=Image.open(steam_black_path),
                    size=icon_size
                )
                print(f"[DEBUG] Loaded Steam black icon from: {steam_black_path}")
            
            folder_white_path = os.path.join(icon_dir, "Folder_logo_white.png")
            folder_black_path = os.path.join(icon_dir, "Folder_logo_black.png")
            
            if os.path.exists(folder_white_path):
                self.folder_icon_white = ctk.CTkImage(
                    light_image=Image.open(folder_white_path),
                    dark_image=Image.open(folder_white_path),
                    size=icon_size
                )
                print(f"[DEBUG] Loaded Folder white icon from: {folder_white_path}")
            
            if os.path.exists(folder_black_path):
                self.folder_icon_black = ctk.CTkImage(
                    light_image=Image.open(folder_black_path),
                    dark_image=Image.open(folder_black_path),
                    size=icon_size
                )
                print(f"[DEBUG] Loaded Folder black icon from: {folder_black_path}")
                
        except Exception as e:
            print(f"[ERROR] Failed to load output icons: {e}")
    
    def _load_logos(self):
        """Load logo images for both themes"""
        icon_dir = os.path.join("gui", "Icons")
        # Logo size
        logo_size = (100, 100)
        
        try:
            logo_white_path = os.path.join(icon_dir, "BeamSkin_Studio_White.png")
            logo_black_path = os.path.join(icon_dir, "BeamSkin_Studio_Black.png")
            
            if os.path.exists(logo_white_path):
                self.logo_white = ctk.CTkImage(
                    light_image=Image.open(logo_white_path),
                    dark_image=Image.open(logo_white_path),
                    size=logo_size
                )
                print(f"[DEBUG] Loaded white logo from: {logo_white_path}")
            
            if os.path.exists(logo_black_path):
                self.logo_black = ctk.CTkImage(
                    light_image=Image.open(logo_black_path),
                    dark_image=Image.open(logo_black_path),
                    size=logo_size
                )
                print(f"[DEBUG] Loaded black logo from: {logo_black_path}")
                
        except Exception as e:
            print(f"[ERROR] Failed to load logos: {e}")
    
    def _update_output_icons(self):
        """Update icon labels and logo based on current theme"""
        if self.sidebar:
            if state.current_theme == "dark":
                steam_icon = self.steam_icon_white
                folder_icon = self.folder_icon_white
                logo = self.logo_white
            else:
                steam_icon = self.steam_icon_black
                folder_icon = self.folder_icon_black
                logo = self.logo_black
            
            self.sidebar.update_icons(steam_icon, folder_icon)
            print(f"[DEBUG] Updated output icons for {state.current_theme} theme")
        
        # Update logo in topbar
        if self.topbar and logo:
            self.topbar.update_logo(logo)
            print(f"[DEBUG] Updated logo for {state.current_theme} theme")
    
    def _setup_ui(self):
        """Set up the main UI"""
        current_logo = self.logo_white if state.current_theme == "dark" else self.logo_black
        
        # Topbar
        self.topbar = Topbar(
            self,
            on_view_change=self.switch_view,
            on_generate=self._generate_mod,
            logo_image=current_logo
        )
        self.topbar.pack(fill="x", side="top")
        
        # Main container
        self.main_container = ctk.CTkFrame(self, fg_color=state.colors["app_bg"])
        self.main_container.pack(fill="both", expand=True)
        
        # Sidebar
        self.sidebar = Sidebar(self.main_container, self.preview_manager)
        self.sidebar.pack(fill="y", side="left")
        
        self._create_tabs()
        
        self.sidebar.populate_vehicles(self._add_vehicle_to_project_from_sidebar)
        
        # Connect sidebar entries to generator tab
        generator_tab = self.tabs.get("generator")
        if generator_tab and isinstance(generator_tab, GeneratorTab):
            generator_tab.set_sidebar_references(
                self.sidebar.mod_name_entry,
                self.sidebar.author_entry
            )
        
        # Show initial tab
        self.switch_view("generator")
        
        self.after(50, lambda: setup_universal_scroll_handler(self))
    
    def _create_tabs(self):
        """Create all application tabs"""
        # Generator tab (main content area) - pass notification callback
        self.tabs["generator"] = GeneratorTab(
            self.main_container,
            notification_callback=self.show_notification
        )
        
        # How To tab
        self.tabs["howto"] = HowToTab(self.main_container)
        
        # Car List tab - pass app reference for notifications
        self.tabs["carlist"] = CarListTab(self.main_container, self.preview_manager, self)
        
        # Settings tab
        self.tabs["settings"] = SettingsTab(
            self.main_container,
            self.main_container,
            self.topbar.menu_frame,
            self.topbar.menu_buttons,
            self.switch_view,
            notification_callback=self.show_notification
        )
        
        # About tab
        self.tabs["about"] = AboutTab(self.main_container)
    
    def switch_view(self, view_name: str):
    
        print(f"[DEBUG] switch_view called")
        """Switch between main views"""
        print(f"[DEBUG] Switching to view: {view_name}")
        
        settings_tab = self.tabs.get("settings")
        
        # Update menu button colors
        for btn_name, btn in self.topbar.menu_buttons.items():
            if btn_name == view_name:
                # Selected tab - no hover effect
                btn.configure(
                    fg_color=state.colors["accent"],
                    hover_color=state.colors["accent"],  # Same as fg_color = no hover effect
                    text_color=state.colors["accent_text"],
                    font=ctk.CTkFont(size=12, weight="bold")
                )
            else:
                # Unselected tabs - normal hover
                btn.configure(
                    fg_color="transparent",
                    hover_color=state.colors["card_hover"],
                    text_color=state.colors["text_secondary"],
                    font=ctk.CTkFont(size=12, weight="normal")
                )
        
        # Hide all regular tabs
        for tab_name, tab in self.tabs.items():
            tab.pack_forget()
        
        # Hide developer tab if it exists
        if settings_tab and isinstance(settings_tab, SettingsTab):
            if settings_tab.developer_tab:
                settings_tab.developer_tab.pack_forget()
                print("[DEBUG] Hid developer tab")
        
        # Hide sidebar for non-generator views
        if view_name != "generator":
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(fill="y", side="left")
        
        # Show/hide Generate button based on view
        if view_name == "generator":
            self.topbar.generate_button.pack(side="right", padx=25)
        else:
            self.topbar.generate_button.pack_forget()
        
        # Show requested tab
        if view_name in self.tabs:
            # Show regular tab
            self.tabs[view_name].pack(fill="both", expand=True, side="left")
            print(f"[DEBUG] Showing regular tab: {view_name}")
        elif view_name == "developer":
            if settings_tab and isinstance(settings_tab, SettingsTab):
                if settings_tab.developer_tab:
                    settings_tab.developer_tab.pack(fill="both", expand=True, side="left")
                    print(f"[DEBUG] Successfully showed developer tab")
                else:
                    print(f"[DEBUG] ERROR: Developer tab doesn't exist yet - has developer mode been enabled?")
            else:
                print(f"[DEBUG] ERROR: Settings tab not found or wrong type")
        
        self.current_tab = view_name
        
        # Update UI
        self.update_idletasks()
        self.after(50, lambda: setup_universal_scroll_handler(self))
    
    def _generate_mod(self):
        """Generate mod - calls the generator tab's method"""
        print("[DEBUG] Generate mod button clicked")
        
        generator_tab = self.tabs.get("generator")
        if generator_tab and isinstance(generator_tab, GeneratorTab):
            # Call the generator tab's generate_mod method
            generator_tab.generate_mod(
                self.topbar.generate_button,
                self.sidebar.output_mode_var,
                self.sidebar.custom_output_var
            )
        else:
            print("[DEBUG] ERROR: Generator tab not found or wrong type")
    
    def _add_vehicle_to_project_from_sidebar(self, carid: str, display_name: str):
        """Add a vehicle to the project from sidebar
        
        This is called when user clicks "Add to Project" in the sidebar.
        It forwards the request to the GeneratorTab.
        
        Args:
            carid: Vehicle ID (e.g., "etk800")
            display_name: Display name (e.g., "ETK 800 Series")
        """
        print(f"[DEBUG] Sidebar: Add vehicle clicked - {display_name} ({carid})")
        
        generator_tab = self.tabs.get("generator")
        if generator_tab and isinstance(generator_tab, GeneratorTab):
            # Call the generator tab's add_car_to_project method
            generator_tab.add_car_to_project(carid, display_name)
            
            # Collapse the add button in sidebar
            for btn_frame, car_id, _, add_btn_frame in state.sidebar_vehicle_buttons:
                if car_id == carid:
                    add_btn_frame.pack_forget()
                    break
            
            # Collapse any expanded vehicle
            self.sidebar.expanded_vehicle_carid = None
            
            print(f"[DEBUG] Successfully added {display_name} to generator tab")
        else:
            print(f"[DEBUG] ERROR: Could not find generator tab")
    
    def _on_closing(self):
        """Handle window closing"""
        print("[DEBUG] \nShutting down BeamSkin Studio...")
        self.destroy()
    
    def show_startup_warning(self):
    
        print(f"[DEBUG] show_startup_warning called")
        """Show WIP warning dialog"""
        show_wip_warning(self)
    
    def show_setup_wizard(self):
        """Show first-time setup wizard"""
        print("[DEBUG] Showing first-time setup wizard...")
        
        from gui.components.setup_wizard import show_setup_wizard
        from core.settings import set_beamng_paths, mark_setup_complete
        
        def on_setup_complete(paths: dict):
            print(f"[DEBUG] Setup wizard completed with paths: {paths}")
            
            # Save paths to settings
            set_beamng_paths(
                beamng_install=paths.get("beamng_install", ""),
                mods_folder=paths.get("mods_folder", "")
            )
            
            # Mark setup as complete
            mark_setup_complete()
            
            # Reload paths in settings tab if it exists
            if "settings" in self.tabs:
                settings_tab = self.tabs["settings"]
                try:
                    if hasattr(settings_tab, 'path_config'):
                        settings_tab.path_config.reload_paths()
                        print("[DEBUG] Reloaded paths in settings tab")
                    else:
                        print("[DEBUG] Settings tab doesn't have path_config attribute")
                except Exception as e:
                    print(f"[DEBUG] Could not reload paths in settings tab: {e}")
            else:
                print("[DEBUG] Settings tab not found in self.tabs")
            
            # Show success notification
            if paths.get("beamng_install") or paths.get("mods_folder"):
                self.show_notification(
                    "Setup complete! Paths saved successfully.",
                    type="success",
                    duration=3000
                )
            
            # Show WIP warning after setup
            self.after(500, self.show_startup_warning)
        
        show_setup_wizard(self, state.colors, on_setup_complete)
    
    def prompt_update(self, new_version: str):
    
        print(f"[DEBUG] prompt_update called")
        """Show update notification"""
        show_update_dialog(self, new_version)


def main():


    print(f"[DEBUG] main called")
    """Entry point for the application"""
    print("[DEBUG] Starting BeamSkin Studio...")
    
    # Load custom vehicles from disk BEFORE creating the app
    print("[DEBUG] Loading custom vehicles from added_vehicles.json...")
    load_added_vehicles_at_startup()
    
    app = BeamSkinStudioApp()
    
    app.mainloop()


if __name__ == "__main__":
    main()