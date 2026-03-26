"""
Main Window - Entry point for the BeamSkin Studio application
"""
from typing import Dict, Optional
import customtkinter as ctk
from PIL import Image
import os

from gui.state import state
from core.localization import t, get_localization
from gui.components.preview import HoverPreviewManager
from gui.components.navigation import Sidebar, Topbar
from gui.components.dialogs import show_update_dialog, show_wip_warning, show_notification
from gui.tabs.settings import SettingsTab
from gui.tabs.car_list import CarListTab
from gui.tabs.generator import GeneratorTab
from gui.tabs.howto import HowToTab
from gui.tabs.add_vehicles import AddVehiclesTab, load_added_vehicles_at_startup
from gui.tabs.about import AboutTab

class OnlineUnavailableTab(ctk.CTkFrame):

    def __init__(self, parent, **kwargs):
        kwargs.pop("notification_callback", None)
        super().__init__(parent, fg_color=state.colors["app_bg"], corner_radius=0)
        self._build_overlay()

    def _build_overlay(self):
        overlay = ctk.CTkFrame(
            self,
            fg_color=state.colors["app_bg"],
            corner_radius=0,
        )
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(
            overlay,
            fg_color=state.colors["frame_bg"],
            corner_radius=16,
            border_width=1,
            border_color=state.colors["border"],
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            card,
            text="🚧",
            font=ctk.CTkFont(size=52),
        ).pack(padx=48, pady=(36, 8))

        ctk.CTkLabel(
            card,
            text=t("online.unavailable"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=state.colors["text"],
        ).pack(padx=48, pady=(0, 6))

        ctk.CTkLabel(
            card,
            text=t("online.online_server"),
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text_secondary"],
            justify="center",
        ).pack(padx=48, pady=(0, 28))

    def refresh_ui(self):
        """Called during language/theme rebuilds — recreate the overlay labels."""
        for widget in self.winfo_children():
            widget.destroy()
        self.configure(fg_color=state.colors["app_bg"])
        self._build_overlay()

# ─────────────────────────────────────────────────────────────────────────────

from utils.debug import setup_universal_scroll_handler

print(f"[DEBUG] Loading class: BeamSkinStudioApp")

class BeamSkinStudioApp(ctk.CTk):

    def __init__(self):

        print(f"[DEBUG] __init__ called")
        super().__init__()
        self.withdraw()

        # Load current language immediately
        localization = get_localization()
        print(f"[DEBUG] Loaded language: {localization.current_language}")

        self.title("BeamSkin Studio")

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

        ctk.set_appearance_mode("dark" if state.current_theme == "dark" else "light")
        ctk.set_default_color_theme("blue")

        self.preview_overlay = self._create_preview_overlay()
        self.preview_manager = HoverPreviewManager(self, self.preview_overlay)

        self.steam_icon_white: Optional[ctk.CTkImage] = None
        self.steam_icon_black: Optional[ctk.CTkImage] = None
        self.folder_icon_white: Optional[ctk.CTkImage] = None
        self.folder_icon_black: Optional[ctk.CTkImage] = None

        self.logo_white: Optional[ctk.CTkImage] = None
        self.logo_black: Optional[ctk.CTkImage] = None

        self._load_output_icons()
        self._load_logos()

        self.topbar: Optional[Topbar] = None
        self.sidebar: Optional[Sidebar] = None
        self.main_container: Optional[ctk.CTkFrame] = None
        self.tabs: Dict[str, ctk.CTkFrame] = {}
        self.current_tab: str = "generator"

        self._setup_ui()
        self._update_output_icons()

        self.after(150, self._apply_startup_language)

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def show_notification(self, message: str, type: str = "info", duration: int = 3000):

        print(f"[DEBUG] show_notification called")
        show_notification(self, message, type, duration)

    def _create_preview_overlay(self) -> ctk.CTkFrame:
        preview_overlay = ctk.CTkFrame(
            self,
            fg_color=state.colors["card_bg"],
            border_color=state.colors["accent"],
            border_width=2,
            corner_radius=10
        )
        return preview_overlay

    def _load_output_icons(self):
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
        icon_dir = os.path.join("gui", "Icons")

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

        if self.topbar and logo:
            self.topbar.update_logo(logo)
            print(f"[DEBUG] Updated logo for {state.current_theme} theme")

    def _setup_ui(self):
        current_logo = self.logo_white if state.current_theme == "dark" else self.logo_black

        self.topbar = Topbar(
            self,
            on_view_change=self.switch_view,
            on_generate=self._generate_mod,
            logo_image=current_logo
        )
        self.topbar.pack(fill="x", side="top")

        self.main_container = ctk.CTkFrame(self, fg_color=state.colors["app_bg"])
        self.main_container.pack(fill="both", expand=True)

        self.sidebar = Sidebar(self.main_container, self.preview_manager)
        self.sidebar.pack(fill="y", side="left")

        self._create_tabs()

        self.sidebar.populate_vehicles(self._add_vehicle_to_project_from_sidebar)

        generator_tab = self.tabs.get("generator")
        if generator_tab and isinstance(generator_tab, GeneratorTab):
            generator_tab.set_sidebar_references(
                self.sidebar.mod_name_entry,
                self.sidebar.author_entry,
                self.sidebar  # stable object; entries looked up dynamically after rebuilds
            )

        self.switch_view("generator")

        self.after(50, lambda: setup_universal_scroll_handler(self))

    def _create_tabs(self):

        self.tabs["generator"] = GeneratorTab(
            self.main_container,
            notification_callback=self.show_notification
        )

        self.tabs["howto"] = HowToTab(self.main_container)

        self.tabs["carlist"] = CarListTab(self.main_container, self.preview_manager, self)

        self.tabs["add_vehicles"] = AddVehiclesTab(
            self.main_container,
            notification_callback=self.show_notification
        )

        self.tabs["settings"] = SettingsTab(
            self.main_container,
            self.main_container,
            self.topbar.menu_frame,
            self.topbar.menu_buttons,
            self.switch_view,
            notification_callback=self.show_notification
        )

        self.tabs["about"] = AboutTab(self.main_container)

        self.tabs["online_tab"] = OnlineUnavailableTab(
            self.main_container,
            notification_callback=self.show_notification
        )

    def switch_view(self, view_name: str):

        print(f"[DEBUG] switch_view called")
        print(f"[DEBUG] Switching to view: {view_name}")

        for btn_name, btn in self.topbar.menu_buttons.items():
            if btn_name == view_name:
                btn.configure(
                    fg_color=state.colors["tab_selected"],
                    hover_color=state.colors["tab_selected_hover"],
                    text_color=state.colors["text"],
                    font=ctk.CTkFont(size=12, weight="bold")
                )
            else:
                btn.configure(
                    fg_color=state.colors["tab_unselected"],
                    hover_color=state.colors["tab_unselected_hover"],
                    text_color=state.colors["text_secondary"],
                    font=ctk.CTkFont(size=12, weight="normal")
                )

        for tab_name, tab in self.tabs.items():
            tab.pack_forget()

        if view_name != "generator":
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(fill="y", side="left")

        if view_name == "generator":
            self.topbar.generate_button.pack(side="right", padx=25)
        else:
            self.topbar.generate_button.pack_forget()

        if view_name in self.tabs:

            self.tabs[view_name].pack(fill="both", expand=True, side="left")
            print(f"[DEBUG] Showing tab: {view_name}")
        else:
            print(f"[DEBUG] ERROR: Tab '{view_name}' not found")

        self.current_tab = view_name

        self.update_idletasks()
        self.after(50, lambda: setup_universal_scroll_handler(self))

    def _generate_mod(self):
        print("[DEBUG] Generate mod button clicked")

        generator_tab = self.tabs.get("generator")
        if generator_tab and isinstance(generator_tab, GeneratorTab):

            generator_tab.generate_mod(
                self.topbar.generate_button,
                self.sidebar.output_mode_var,
                self.sidebar.custom_output_var
            )
        else:
            print("[DEBUG] ERROR: Generator tab not found or wrong type")

    def _add_vehicle_to_project_from_sidebar(self, carid: str, display_name: str):
        print(f"[DEBUG] Sidebar: Add vehicle clicked - {display_name} ({carid})")

        generator_tab = self.tabs.get("generator")
        if generator_tab and isinstance(generator_tab, GeneratorTab):

            generator_tab.add_car_to_project(carid, display_name)

            for btn_frame, car_id, _, add_btn_frame in state.sidebar_vehicle_buttons:
                if car_id == carid:
                    add_btn_frame.pack_forget()
                    break

            self.sidebar.expanded_vehicle_carid = None

            print(f"[DEBUG] Successfully added {display_name} to generator tab")
        else:
            print(f"[DEBUG] ERROR: Could not find generator tab")

    def _apply_startup_language(self):
        try:
            from core.localization import get_localization, set_language
            from core.settings import app_settings

            loc        = get_localization()
            saved_lang = app_settings.get("language", "en_US")

            print(f"[DEBUG] _apply_startup_language: saved={saved_lang!r}  current={loc.current_language!r}")
            if saved_lang != loc.current_language or not loc.translations:
                ok = set_language(saved_lang)
                print(f"[DEBUG] set_language({saved_lang!r}) -> {ok}")

            # Always refresh all widgets on startup so the UI reflects the
            # loaded language even when saved_lang == current_language.
            settings_tab = self.tabs.get("settings")
            if settings_tab and hasattr(settings_tab, "_refresh_all_ui"):
                settings_tab._refresh_all_ui()
                print("[DEBUG] _apply_startup_language: full UI refresh done")
            else:
                for tab_name, tab in self.tabs.items():
                    if hasattr(tab, "refresh_ui"):
                        try:
                            tab.refresh_ui()
                        except Exception as e:
                            print(f"[ERROR] refresh_ui failed for {tab_name}: {e}")

        except Exception as e:
            import traceback
            print(f"[ERROR] _apply_startup_language failed: {e}")
            traceback.print_exc()

        # Sidebar.refresh_ui() destroys and recreates entry widgets; re-wire
        # the generator tab's references so load/save/clear project still work.
        self._rewire_sidebar_references()

    def _on_closing(self):
        print("[DEBUG] \nShutting down BeamSkin Studio...")
        self.destroy()

    def show_startup_warning(self):

        print(f"[DEBUG] show_startup_warning called")
        show_wip_warning(self)

    def show_setup_wizard(self):
        print("[DEBUG] Showing first-time setup wizard...")

        from gui.components.setup_wizard import show_setup_wizard
        from core.settings import set_beamng_paths, mark_setup_complete

        def on_setup_complete(paths: dict):
            print(f"[DEBUG] Setup wizard completed with paths: {paths}")

            set_beamng_paths(
                beamng_install=paths.get("beamng_install", ""),
                mods_folder=paths.get("mods_folder", "")
            )

            mark_setup_complete()

            # Apply the language chosen in the wizard to all already-built tabs.
            # _apply_startup_language fired 150 ms after launch (while the wizard
            # was still open) and saw no change at that point, so we must do the
            # refresh here now that the wizard has finished.
            from core.localization import get_localization
            from core.settings import app_settings as _app_settings
            _chosen_lang = _app_settings.get("language", "en_US")
            _loc = get_localization()
            print(f"[DEBUG] on_setup_complete: refreshing UI for language={_chosen_lang!r}")
            # Ensure the localization object is loaded with the chosen language
            if _loc.current_language != _chosen_lang:
                _loc.set_language(_chosen_lang)
            settings_tab = self.tabs.get("settings")
            if settings_tab and hasattr(settings_tab, "_refresh_all_ui"):
                settings_tab._refresh_all_ui()
                print("[DEBUG] on_setup_complete: full UI refresh via _refresh_all_ui")
            else:
                for _tab_name, _tab in self.tabs.items():
                    if hasattr(_tab, "refresh_ui"):
                        try:
                            _tab.refresh_ui()
                        except Exception as _e:
                            print(f"[ERROR] refresh_ui failed for {_tab_name}: {_e}")
                print("[DEBUG] on_setup_complete: individual tab refresh done")

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

            if paths.get("beamng_install") or paths.get("mods_folder"):
                self.show_notification(
                    "Setup complete! Paths saved successfully.",
                    type="success",
                    duration=3000
                )

            # Re-wire sidebar references in case the setup wizard triggered a
            # language change that caused Sidebar.refresh_ui() to run.
            self._rewire_sidebar_references()

            def _post_setup_startup():
                self.show_startup_warning()  # blocks (wait_window) until dismissed
                from gui.components.changelog_dialog import show_changelog_if_needed
                from core.updater import CURRENT_VERSION
                show_changelog_if_needed(self, CURRENT_VERSION)

            self.after(500, _post_setup_startup)

        show_setup_wizard(self, state.colors, on_setup_complete)

    def _rewire_sidebar_references(self):
        """Re-wire generator tab's sidebar entry references after any sidebar rebuild.

        Must be called any time Sidebar.refresh_ui() is invoked, because that
        method destroys and recreates mod_name_entry / author_entry.  Holding a
        stale reference to a destroyed widget causes the 'invalid command name'
        error when load_project (or clear_project) tries to manipulate those entries.
        """
        generator_tab = self.tabs.get("generator")
        if generator_tab and isinstance(generator_tab, GeneratorTab) and self.sidebar:
            try:
                generator_tab.set_sidebar_references(
                    self.sidebar.mod_name_entry,
                    self.sidebar.author_entry,
                    self.sidebar  # stable object; entries looked up dynamically after rebuilds
                )
                print("[DEBUG] _rewire_sidebar_references: sidebar references updated")
            except Exception as e:
                print(f"[ERROR] _rewire_sidebar_references failed: {e}")

    def prompt_update(self, new_version: str):

        print(f"[DEBUG] prompt_update called")
        show_update_dialog(self, new_version)

def main():

    print(f"[DEBUG] main called")
    print("[DEBUG] Starting BeamSkin Studio...")

    print("[DEBUG] Loading custom vehicles from added_vehicles.json...")
    load_added_vehicles_at_startup()

    app = BeamSkinStudioApp()

    app.mainloop()

if __name__ == "__main__":
    main()