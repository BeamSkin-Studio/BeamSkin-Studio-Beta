"""
Car List Tab
"""
from typing import List, Tuple
import os
import zipfile
import re
from tkinter import filedialog
import customtkinter as ctk
from gui.state import state
from gui.components.preview import HoverPreviewManager
from gui.components.dialogs import show_notification

try:
    from utils.file_ops import load_added_vehicles_json
except ImportError:
    print("[WARNING] load_added_vehicles_json not found in file_ops")
    def load_added_vehicles_json():
        return {}

class CarListTab(ctk.CTkFrame):
    """Car list tab with search and UV map extraction"""

    def __init__(self, parent: ctk.CTk, preview_manager: HoverPreviewManager, app):
        super().__init__(parent, fg_color=state.colors["app_bg"])
        self.preview_manager = preview_manager
        self.app = app

        self.carlist_search_var = ctk.StringVar()
        self.carlist_scroll: ctk.CTkScrollableFrame = None

        self._setup_ui()
        self._populate_car_list()

    def _setup_ui(self):
        """Set up the car list UI"""

        carlist_search_entry = ctk.CTkEntry(
            self,
            textvariable=self.carlist_search_var,
            placeholder_text="Search Car ID...",
            placeholder_text_color="#888888",
            fg_color=state.colors["card_bg"],
            text_color=state.colors["text"]
        )
        carlist_search_entry.pack(fill="x", padx=10, pady=(10, 5))

        self.carlist_scroll = ctk.CTkScrollableFrame(self, fg_color=state.colors["frame_bg"])
        self.carlist_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.carlist_search_var.trace_add("write", self._update_carlist)

    def _populate_car_list(self):
        """Populate the car list with all vehicles"""

        vehicles = load_added_vehicles_json()
        state.added_vehicles.clear()
        state.added_vehicles.update(vehicles)

        car_id_list = [
            ("autobello", "Autobello Piccolina"), ("atv", "FPU Wydra"), ("barstow", "Gavril Barstow"),
            ("bastion", "Bruckell Bastion"), ("bluebuck", "Gavril Bluebuck"), ("bolide", "Civetta Bolide"),
            ("burnside", "Burnside Special"), ("covet", "Ibishu Covet"), ("citybus", "Wentward DT40L"),
            ("bx", "Ibishu BX-Series"), ("dryvan", "Dry Van Trailer"), ("dumptruck", "Hirochi HT-55"),
            ("etk800", "ETK 800 Series"), ("etkc", "ETK K Series"), ("etki", "ETK I Series"),
            ("fullsize", "Gavril Grand Marshal"), ("hopper", "Ibishu Hopper"), ("lansdale", "Soliad Lansdale"),
            ("legran", "Bruckell Legran"), ("midsize", "Newer Ibishu Pessima"), ("miramar", "Ibishu Miramar"),
            ("moonhawk", "Bruckell Moonhawk"), ("md_series", "Gavril MD-Series"), ("midtruck", "Autobello Stambecco"),
            ("nine", "Bruckell Nine"), ("pessima", "Older Ibishu Pessima"), ("pickup", "Gavril D Series"),
            ("pigeon", "Ibishu Pigeon"), ("racetruck", "SP Dunekicker"), ("roamer", "Gavril Roamer"),
            ("rockbouncer", "SP Rockbasher"), ("sbr", "Hirochi SBR4"), ("scintilla", "Civetta Scintilla"),
            ("sunburst2", "Hirochi Sunburst"), ("us_semi", "Gavril T Series"), ("utv", "Hirochi Aurata"),
            ("van", "Gavril H Series"), ("vivace", "Cherrier FCV"), ("wendover", "Soliad Wendover"),
            ("wigeon", "Ibishu Wigeon"), ("wl40", "Hirochi WL-40")
        ]

        for carid, name in car_id_list:
            self._add_carlist_card(carid, name, developer_added=False)

        for carid, carname in state.added_vehicles.items():
            self._add_carlist_card(carid, carname, developer_added=True)

    def refresh_vehicle_list(self):
        """Refresh the vehicle list when new vehicles are added"""
        print(f"[DEBUG] CarListTab: refresh_vehicle_list called")

        for card_frame, carid, name in state.carlist_items:
            card_frame.destroy()

        state.carlist_items.clear()

        self._populate_car_list()

        self._update_carlist()

        print(f"[DEBUG] CarListTab: Vehicle list refreshed with {len(state.carlist_items)} vehicles")

    def _add_carlist_card(self, carid: str, name: str, developer_added: bool = False):
        """Add a vehicle card to the car list"""

        insert_position = len(state.carlist_items)
        for i, (card, cid, cname) in enumerate(state.carlist_items):
            if cname.lower() > name.lower():
                insert_position = i
                break

        card_frame = ctk.CTkFrame(
            self.carlist_scroll,
            corner_radius=14,
            fg_color=state.colors["card_bg"],
            border_width=1,
            border_color=state.colors["border"]
        )

        inner_frame = ctk.CTkFrame(
            card_frame,
            corner_radius=14,
            fg_color="transparent"
        )
        inner_frame.pack(fill="x", padx=4, pady=4)

        text_container = ctk.CTkFrame(inner_frame, fg_color="transparent")
        text_container.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        ctk.CTkLabel(
            text_container,
            text="🚗",
            font=ctk.CTkFont(size=20),
            anchor="w"
        ).pack(side="left", padx=(0, 10))

        text_stack = ctk.CTkFrame(text_container, fg_color="transparent")
        text_stack.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_stack,
            text=name,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_stack,
            text=carid,
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text_secondary"]
        ).pack(anchor="w")

        btn_container = ctk.CTkFrame(inner_frame, fg_color="transparent")
        btn_container.pack(side="right", padx=8, pady=8)

        if not developer_added:
            uv_btn = ctk.CTkButton(
                btn_container,
                text="🖼 UV Map",
                width=110,
                height=36,
                fg_color=state.colors["success"],
                hover_color=state.colors["accent_hover"],
                text_color=state.colors["accent_text"],
                corner_radius=10,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda c=carid: self._get_uv_map(c)
            )
            uv_btn.pack(side="left", padx=4)
            uv_btn.bind("<Enter>", lambda e: self.preview_manager.hide_hover_preview(force=True), add=True)

        copy_btn = ctk.CTkButton(
            btn_container,
            text="📋 Copy ID",
            width=100,
            height=36,
            fg_color=state.colors["frame_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"],
            corner_radius=10,
            font=ctk.CTkFont(size=12),
            border_width=1,
            border_color=state.colors["border"],
            command=lambda c=carid: self._copy_carid(c)
        )
        copy_btn.pack(side="left", padx=4)
        copy_btn.bind("<Enter>", lambda e: self.preview_manager.hide_hover_preview(force=True), add=True)

        self.preview_manager.setup_robust_hover(card_frame, carid)

        state.carlist_items.insert(insert_position, (card_frame, carid, name))

        for widget in self.carlist_scroll.winfo_children():
            widget.pack_forget()

        for card, cid, cname in state.carlist_items:
            card.pack(fill="x", pady=8, padx=8)

    def _update_carlist(self, *args):
        """Filter car list based on search query"""
        query = self.carlist_search_var.get().lower()
        for row_frame, carid, name in state.carlist_items:
            row_frame.pack_forget()
            if query in carid.lower() or query in name.lower():
                row_frame.pack(fill="x", pady=8, padx=8)
        try:
            self.carlist_scroll._parent_canvas.yview_moveto(0)
        except:
            pass

    def _copy_carid(self, carid: str):
        """Copy car ID to clipboard"""
        self.master.clipboard_clear()
        self.master.clipboard_append(carid)
        print(f"[DEBUG] Car ID '{carid}' copied to clipboard")
        show_notification(self.app, f"Copied '{carid}' to clipboard", "success", 2000)

    def _get_uv_map(self, carid: str):
        """Search for UV map in BeamNG installation and prompt user to copy it"""
        # Get BeamNG installation path from user settings
        from core.settings import get_beamng_install_path
        
        beamng_install = get_beamng_install_path()
        
        # Check if BeamNG path is configured
        if not beamng_install:
            show_notification(self.app, "⚠️ BeamNG.drive installation path not configured. Please set it in Settings.", "warning", 5000)
            print(f"[DEBUG] UV Map search failed: BeamNG installation path not configured")
            return
        
        # Build the path to the vehicles folder
        beamng_path = os.path.join(beamng_install, "content", "vehicles")
        
        # Check if the vehicles folder exists
        if not os.path.exists(beamng_path):
            show_notification(self.app, f"❌ Vehicles folder not found at: {beamng_path}", "error", 5000)
            print(f"[DEBUG] UV Map search failed: Vehicles folder does not exist - {beamng_path}")
            return
        
        zip_file_path = os.path.join(beamng_path, f"{carid}.zip")

        if not os.path.exists(zip_file_path):
            show_notification(self.app, f"❌ Vehicle ZIP not found: {carid}.zip", "error", 4000)
            print(f"[DEBUG] UV Map search failed: ZIP file does not exist - {zip_file_path}")
            return

        try:
            search_common = False
            common_search_dirs = []

            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                all_files = zip_ref.namelist()
                for file_path in all_files:
                    filename_lower = os.path.basename(file_path).lower()
                    if "ambulance" in filename_lower:
                        search_common = True
                        common_search_dirs.append("vehicles/common/pickup/")
                        break

            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                all_files = zip_ref.namelist()

                target_dir = f"vehicles/{carid}/"
                found_files = []

                for file_path in all_files:
                    if file_path.startswith(target_dir):
                        filename_lower = os.path.basename(file_path).lower()

                        if "color" in filename_lower:
                            continue

                        if filename_lower.startswith("skin_"):
                            continue

                        if re.search(r'_skin_\w+_uv\d*\.', filename_lower):
                            continue

                        has_skin_and_uv = "skin" in filename_lower and "uv" in filename_lower
                        has_uvmap = "uvmap" in filename_lower
                        has_uv_layout = "uv1_layout" in filename_lower or "uv_layout" in filename_lower

                        if has_skin_and_uv or has_uvmap or has_uv_layout:
                            if filename_lower.endswith(('.dds', '.png', '.jpg', '.jpeg')):
                                found_files.append((file_path, zip_file_path))

                if search_common and common_search_dirs:
                    common_zip_path = os.path.join(beamng_path, "common.zip")
                    if os.path.exists(common_zip_path):
                        print(f"[DEBUG] Also searching in common.zip for ambulance UV maps...")
                        with zipfile.ZipFile(common_zip_path, 'r') as common_zip:
                            common_files = common_zip.namelist()

                            for search_dir in common_search_dirs:
                                for file_path in common_files:
                                    if file_path.startswith(search_dir):
                                        filename_lower = os.path.basename(file_path).lower()

                                        if "color" in filename_lower:
                                            continue
                                        if filename_lower.startswith("skin_"):
                                            continue
                                        if re.search(r'_skin_\w+_uv\d*\.', filename_lower):
                                            continue

                                        has_skin_and_uv = "skin" in filename_lower and "uv" in filename_lower
                                        has_uvmap = "uvmap" in filename_lower
                                        has_uv_layout = "uv1_layout" in filename_lower or "uv_layout" in filename_lower

                                        if has_skin_and_uv or has_uvmap or has_uv_layout:
                                            if filename_lower.endswith(('.dds', '.png', '.jpg', '.jpeg')):
                                                found_files.append((file_path, common_zip_path))

                if not found_files:
                    show_notification(self.app, f"❌ No UV map files found for '{carid}'", "error", 4000)
                    print(f"[DEBUG] UV Map search failed: No UV files found in {zip_file_path}")
                    return

                selected_files = []
                if len(found_files) == 1:
                    selected_files = [found_files[0]]
                    file_path, source_zip = found_files[0]
                    print(f"[DEBUG] UV Map found in ZIP: {file_path} (from {os.path.basename(source_zip)})")
                else:
                    print(f"[DEBUG] Multiple UV maps found ({len(found_files)})")

                    dialog = ctk.CTkToplevel(self.app)
                    dialog.title("Select UV Map(s)")
                    dialog.geometry("600x400")
                    dialog.transient(self.app)
                    dialog.grab_set()

                    dialog.update_idletasks()
                    x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
                    y = (dialog.winfo_screenheight() // 2) - (400 // 2)
                    dialog.geometry(f"600x400+{x}+{y}")

                    ctk.CTkLabel(
                        dialog,
                        text=f"Multiple UV maps found for {carid}\nSelect one or more files:",
                        font=ctk.CTkFont(size=14, weight="bold"),
                        text_color=state.colors["text"]
                    ).pack(pady=20)

                    scroll_frame = ctk.CTkScrollableFrame(dialog, fg_color=state.colors["frame_bg"])
                    scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0,20))

                    checkbox_vars = {}

                    for file_info in found_files:
                        file_path, source_zip = file_info
                        filename = os.path.basename(file_path)
                        source_name = os.path.basename(source_zip)
                        display_text = f"{filename} (from {source_name})" if source_zip != zip_file_path else filename

                        var = ctk.BooleanVar(value=False)
                        checkbox_vars[file_info] = var

                        checkbox = ctk.CTkCheckBox(
                            scroll_frame,
                            text=display_text,
                            variable=var,
                            font=ctk.CTkFont(size=12),
                            text_color=state.colors["text"]
                        )
                        checkbox.pack(anchor="w", pady=5, padx=10)

                    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
                    btn_frame.pack(fill="x", padx=20, pady=(0,20))

                    def select_all():
                        for var in checkbox_vars.values():
                            var.set(True)

                    def deselect_all():
                        for var in checkbox_vars.values():
                            var.set(False)

                    def on_select():
                        nonlocal selected_files
                        selected_files = [path for path, var in checkbox_vars.items() if var.get()]
                        if selected_files:
                            dialog.destroy()
                        else:
                            show_notification(self.app, "Please select at least one UV map file", "error", 2000)

                    def on_cancel():
                        nonlocal selected_files
                        selected_files = []
                        dialog.destroy()

                    ctk.CTkButton(
                        btn_frame,
                        text="Select All",
                        command=select_all,
                        fg_color=state.colors["card_bg"],
                        hover_color=state.colors["card_hover"],
                        text_color=state.colors["text"],
                        width=100
                    ).pack(side="left", padx=5)

                    ctk.CTkButton(
                        btn_frame,
                        text="Deselect All",
                        command=deselect_all,
                        fg_color=state.colors["card_bg"],
                        hover_color=state.colors["card_hover"],
                        text_color=state.colors["text"],
                        width=100
                    ).pack(side="left", padx=5)

                    ctk.CTkButton(
                        btn_frame,
                        text="OK",
                        command=on_select,
                        fg_color=state.colors["accent"],
                        hover_color=state.colors["accent_hover"],
                        text_color=state.colors["accent_text"],
                        width=100
                    ).pack(side="right", padx=5)

                    ctk.CTkButton(
                        btn_frame,
                        text="Cancel",
                        command=on_cancel,
                        fg_color=state.colors["error"],
                        hover_color=state.colors["error_hover"],
                        text_color=state.colors["accent_text"],
                        width=100
                    ).pack(side="right", padx=5)

                    self.app.wait_window(dialog)

                    if not selected_files:
                        print("[DEBUG] User cancelled UV map selection")
                        return

                print(f"[DEBUG] Selected UV Map(s): {[(os.path.basename(f), os.path.basename(z)) for f, z in selected_files]}")

                if len(selected_files) == 1:
                    file_path, source_zip = selected_files[0]
                    file_ext = os.path.splitext(file_path)[1]
                    destination = filedialog.asksaveasfilename(
                        title="Save UV Map As",
                        defaultextension=file_ext,
                        initialfile=os.path.basename(file_path),
                        filetypes=[
                            ("All Files", "*.*"),
                            ("DDS Files", "*.dds"),
                            ("PNG Files", "*.png"),
                            ("JPG Files", "*.jpg")
                        ]
                    )

                    if destination:
                        with zipfile.ZipFile(source_zip, 'r') as source_zip_ref:
                            with source_zip_ref.open(file_path) as source:
                                with open(destination, 'wb') as target:
                                    target.write(source.read())

                        show_notification(self.app, f"✅ UV map copied successfully!", "success", 3000)
                        print(f"[DEBUG] UV Map extracted from {source_zip} to {destination}")
                else:
                    destination_folder = filedialog.askdirectory(
                        title="Select Folder to Save UV Maps"
                    )

                    if destination_folder:
                        success_count = 0
                        for file_info in selected_files:
                            file_path, source_zip = file_info
                            filename = os.path.basename(file_path)
                            destination = os.path.join(destination_folder, filename)

                            try:
                                with zipfile.ZipFile(source_zip, 'r') as source_zip_ref:
                                    with source_zip_ref.open(file_path) as source:
                                        with open(destination, 'wb') as target:
                                            target.write(source.read())
                                success_count += 1
                                print(f"[DEBUG] UV Map extracted: {filename} from {os.path.basename(source_zip)} to {destination}")
                            except Exception as e:
                                print(f"[DEBUG] Failed to extract {filename}: {e}")

                        show_notification(self.app, f"✅ {success_count} UV map(s) copied successfully!", "success", 3000)
                        print(f"[DEBUG] {success_count}/{len(selected_files)} UV maps extracted to {destination_folder}")

        except zipfile.BadZipFile:
            show_notification(self.app, f"❌ Invalid ZIP file: {carid}.zip", "error", 4000)
            print(f"[DEBUG] Error: {zip_file_path} is not a valid ZIP file")
        except Exception as e:
            show_notification(self.app, f"❌ Failed to extract UV map: {str(e)}", "error", 4000)
            print(f"[DEBUG] Error extracting UV map: {e}")
            import traceback
            traceback.print_exc()