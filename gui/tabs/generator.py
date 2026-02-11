"""
Generator Tab
"""
from typing import Dict, List, Optional, Any, Callable
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
import threading
import json
import os

from gui.state import state

try:
    from utils.file_ops import load_added_vehicles_json
except ImportError:
    print("[WARNING] load_added_vehicles_json not found in file_ops")
    def load_added_vehicles_json():
        return {}

try:
    from core.file_ops import generate_multi_skin_mod
except ImportError:
    print("[WARNING] generate_multi_skin_mod not found, using fallback")
    def generate_multi_skin_mod(*args, **kwargs):
        print(f"[DEBUG] generate_multi_skin_mod called")
        messagebox.showerror("Error", "generate_multi_skin_mod function not available")

print(f"[DEBUG] Loading class: GeneratorTab")

class GeneratorTab(ctk.CTkFrame):
    """Complete generator tab - fully functional project creation and mod generation"""

    def __init__(self, parent: ctk.CTk, notification_callback: Callable[[str, str, int], None] = None):

        print(f"[DEBUG] __init__ called")
        super().__init__(parent, fg_color=state.colors["app_bg"])

        self.show_notification = notification_callback or self._fallback_notification

        self.mod_name_entry_sidebar = None
        self.author_entry_sidebar = None

        self.generator_scroll: Optional[ctk.CTkScrollableFrame] = None
        self.project_overview_frame: Optional[ctk.CTkFrame] = None
        self.project_search_entry: Optional[ctk.CTkEntry] = None
        self.current_car_label: Optional[ctk.CTkLabel] = None
        self.dds_preview_label: Optional[ctk.CTkLabel] = None
        self.progress_bar: Optional[ctk.CTkProgressBar] = None
        self.export_status_label: Optional[ctk.CTkLabel] = None
        self.skin_name_entry: Optional[ctk.CTkEntry] = None
        self.jpg_file_entry: Optional[ctk.CTkEntry] = None
        self.config_name_entry: Optional[ctk.CTkEntry] = None

        self.skin_name_var = ctk.StringVar()
        self.dds_path_var = ctk.StringVar()
        self.project_search_var = ctk.StringVar()

        self.add_config_data_var = ctk.BooleanVar(value=False)
        self.config_type_var = ctk.StringVar(value="Factory")
        self.config_name_var = ctk.StringVar()
        self.pc_file_path_var = ctk.StringVar()
        self.jpg_file_path_var = ctk.StringVar()

        self.add_material_properties_var = ctk.BooleanVar(value=False)
        self.material_properties_entries = {}
        self.material_properties_frame = None

        self.pc_file_from_project = False
        self.jpg_file_from_project = False

        try:
            from utils.config_helper import load_config_types
            self.config_types = load_config_types()
        except ImportError:
            self.config_types = ["Factory", "Custom", "Police"]
            print("[DEBUG] Using default config types")

        self.project_data = {
            "mod_name": "",
            "author": "",
            "cars": {}
        }

        self.selected_car_for_skin: Optional[str] = None

        self.selected_skin_index: Optional[int] = None
        self.editing_mode: bool = False
        
        self.add_skin_section_label: Optional[ctk.CTkLabel] = None
        self.add_skin_section_card: Optional[ctk.CTkFrame] = None

        self.car_id_list = self._build_car_id_list()

        self._setup_ui()
        self._bind_search()
        self.refresh_project_display()

    def set_sidebar_references(self, mod_name_entry, author_entry):

        print(f"[DEBUG] set_sidebar_references called")
        """Called by main window to provide sidebar entry references"""
        self.mod_name_entry_sidebar = mod_name_entry
        self.author_entry_sidebar = author_entry

    def _fallback_notification(self, message: str, type: str = "info", duration: int = 3000):
        """Fallback notification if none provided"""
        print(f"[{type.upper()}] {message}")

    def _build_car_id_list(self) -> List:
        """Build the car ID list from VEHICLE_IDS - sorted alphabetically by car name"""
        car_list = []

        vehicles = load_added_vehicles_json()
        state.added_vehicles.clear()
        state.added_vehicles.update(vehicles)

        for carid, carname in state.vehicle_ids.items():

            if carid not in state.added_vehicles:
                car_list.append((carid, carname))

        for carid, carname in state.added_vehicles.items():
            car_list.append((carid, carname))

        return sorted(car_list, key=lambda x: x[1].lower())

    def refresh_vehicle_list(self):
        """Refresh the vehicle list when new vehicles are added"""
        print(f"[DEBUG] refresh_vehicle_list called")
        print(f"[DEBUG] Rebuilding car ID list from added_vehicles.json...")

        self.car_id_list = self._build_car_id_list()

        print(f"[DEBUG] Car list now has {len(self.car_id_list)} vehicles")
        print(f"[DEBUG] Custom vehicles in state: {len(state.added_vehicles)}")

        self.refresh_project_display()

        print(f"[DEBUG] Vehicle list refresh complete")

    def get_real_value(self, entry: ctk.CTkEntry, placeholder: str) -> str:

        print(f"[DEBUG] get_real_value called")
        """Get real value from entry (not placeholder)"""
        if entry is None:
            return ""
        value = entry.get()
        return "" if value == placeholder else value

    def _setup_ui(self):
        """Set up the complete generator tab UI"""

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=0, pady=0)

        left_sidebar = ctk.CTkFrame(main_container, width=320, fg_color=state.colors["sidebar_bg"], corner_radius=0)
        left_sidebar.pack(side="left", fill="both", padx=0, pady=0)
        left_sidebar.pack_propagate(False)

        sidebar_header = ctk.CTkFrame(left_sidebar, fg_color="transparent", height=60)
        sidebar_header.pack(fill="x", padx=15, pady=(15, 10))
        sidebar_header.pack_propagate(False)

        ctk.CTkLabel(
            sidebar_header,
            text="PROJECT OVERVIEW",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text_secondary"]
        ).pack(side="top", fill="x", pady=(5, 0))

        project_controls = ctk.CTkFrame(left_sidebar, fg_color="transparent")
        project_controls.pack(fill="x", padx=15, pady=(0, 10))

        self._create_button(project_controls, "💾 Save", self.save_project, "primary", 90, 30).pack(side="left", padx=(0, 3))
        self._create_button(project_controls, "📂 Load", self.load_project, "primary", 90, 30).pack(side="left", padx=(0, 3))
        self._create_button(project_controls, "Clear", self.clear_project, "danger", 90, 30).pack(side="left")

        separator = ctk.CTkFrame(left_sidebar, height=2, fg_color=state.colors["border"])
        separator.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(
            left_sidebar,
            text="Vehicles",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=state.colors["text"]
        ).pack(fill="x", padx=15, pady=(0, 5))

        project_search_frame = ctk.CTkFrame(left_sidebar, fg_color="transparent")
        project_search_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.project_search_entry = ctk.CTkEntry(
            project_search_frame,
            textvariable=self.project_search_var,
            height=32,
            corner_radius=8,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color="#888888"
        )
        self.project_search_entry.pack(fill="x")
        self._setup_placeholder(self.project_search_entry, "🔍 Search cars...")

        self.project_overview_container = ctk.CTkScrollableFrame(
            left_sidebar,
            corner_radius=0,
            fg_color="transparent"
        )
        self.project_overview_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.project_overview_frame = ctk.CTkFrame(self.project_overview_container, fg_color="transparent")
        self.project_overview_frame.pack(fill="both", expand=True, padx=0, pady=0)

        self.generator_scroll = ctk.CTkScrollableFrame(main_container, fg_color="transparent")
        self.generator_scroll.pack(side="right", fill="both", expand=True, padx=0, pady=0)

        self.current_car_label = ctk.CTkLabel(
            self.generator_scroll,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["accent"]
        )

        self.add_skin_section_label = ctk.CTkLabel(
            self.generator_scroll,
            text="Add Skins to Selected Car",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=state.colors["text"]
        )
        self.add_skin_section_label.pack(anchor="w", padx=20, pady=(20, 5))
        self.add_skin_section_label.pack_forget()  # Hide initially

        skin_card = self._create_card(self.generator_scroll)
        skin_card.pack(fill="x", padx=20, pady=(0, 15))
        skin_card.pack_forget()  # Hide initially
        self.add_skin_section_card = skin_card

        header_row = ctk.CTkFrame(skin_card, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            header_row,
            text="Skin Name",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left", anchor="w")

        config_corner = ctk.CTkFrame(header_row, fg_color="transparent")
        config_corner.pack(side="right", anchor="e")

        config_toggle_row = ctk.CTkFrame(config_corner, fg_color="transparent")
        config_toggle_row.pack(anchor="e")

        ctk.CTkLabel(
            config_toggle_row,
            text="Add Config Data",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left", padx=(200, 8))

        config_toggle = ctk.CTkSwitch(
            config_toggle_row,
            text="",
            variable=self.add_config_data_var,
            command=self._toggle_config_data,
            onvalue=True,
            offvalue=False,
            fg_color="#3A3A3A",
            progress_color=state.colors["accent"],
            button_color=state.colors["text"],
            button_hover_color=state.colors["border"]
        )
        config_toggle.pack(side="right")

        entry_row = ctk.CTkFrame(skin_card, fg_color="transparent")
        entry_row.pack(fill="x", padx=15, pady=(0, 10))

        self.skin_name_entry = ctk.CTkEntry(
            entry_row,
            textvariable=self.skin_name_var,
            height=36,
            width=300,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        )
        self.skin_name_entry.pack(side="left", padx=(0, 10))
        self._setup_placeholder(self.skin_name_entry, "Enter skin name...")

        self.config_name_label = ctk.CTkLabel(
            entry_row,
            text="Config name:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=state.colors["text"]
        )
        self.config_name_entry = ctk.CTkEntry(
            entry_row,
            textvariable=self.config_name_var,
            height=36,
            width=300,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        )
        self._setup_placeholder(self.config_name_entry, "Enter configuration name...")

        self.config_type_entry_row = ctk.CTkFrame(entry_row, fg_color="transparent")

        ctk.CTkLabel(
            self.config_type_entry_row,
            text="Type:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 8))

        self.config_type_dropdown_inline = ctk.CTkOptionMenu(
            self.config_type_entry_row,
            variable=self.config_type_var,
            values=self.config_types,
            width=140,
            height=36,
            fg_color=state.colors["frame_bg"],
            button_color=state.colors["accent"],
            button_hover_color=state.colors["accent_hover"],
            text_color=state.colors["text"],
            dropdown_fg_color=state.colors["card_bg"],
            dropdown_hover_color=state.colors["card_hover"],
            dropdown_text_color=state.colors["text"]
        )
        self.config_type_dropdown_inline.pack(side="left")

        self.config_files_container = ctk.CTkFrame(skin_card, fg_color="transparent")

        config_files_row = ctk.CTkFrame(self.config_files_container, fg_color="transparent")
        config_files_row.pack(fill="x", padx=15, pady=(0, 10))

        pc_file_column = ctk.CTkFrame(config_files_row, fg_color="transparent")
        pc_file_column.pack(side="left", fill="both", expand=True, padx=(0, 10))

        ctk.CTkLabel(
            pc_file_column,
            text=".pc File (Vehicle Config)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", pady=(0, 3))

        pc_input_row = ctk.CTkFrame(pc_file_column, fg_color="transparent")
        pc_input_row.pack(fill="x")

        self.pc_file_entry = ctk.CTkEntry(
            pc_input_row,
            textvariable=self.pc_file_path_var,
            state="readonly",
            height=36,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        )
        self.pc_file_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._setup_placeholder(self.pc_file_entry, "No .pc file selected...")

        pc_browse_btn = ctk.CTkButton(
            pc_input_row,
            text="📁 Browse",
            command=self._browse_pc_file,
            width=100,
            height=36,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8
        )
        pc_browse_btn.pack(side="right")

        jpg_file_column = ctk.CTkFrame(config_files_row, fg_color="transparent")
        jpg_file_column.pack(side="right", fill="both", expand=True, padx=(10, 0))

        ctk.CTkLabel(
            jpg_file_column,
            text=".jpg File (Config Icon)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", pady=(0, 3))

        jpg_input_row = ctk.CTkFrame(jpg_file_column, fg_color="transparent")
        jpg_input_row.pack(fill="x")

        self.jpg_file_entry = ctk.CTkEntry(
            jpg_input_row,
            textvariable=self.jpg_file_path_var,
            state="readonly",
            height=36,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        )
        self.jpg_file_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._setup_placeholder(self.jpg_file_entry, "No .jpg file selected...")

        jpg_browse_btn = ctk.CTkButton(
            jpg_input_row,
            text="📁 Browse",
            command=self._browse_jpg_file,
            width=100,
            height=36,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8
        )
        jpg_browse_btn.pack(side="right")

        self.material_properties_container = ctk.CTkFrame(skin_card, fg_color="transparent")

        material_toggle_row = ctk.CTkFrame(self.material_properties_container, fg_color="transparent")
        material_toggle_row.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            material_toggle_row,
            text="Edit Material Properties",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left", padx=(0, 8))

        material_toggle = ctk.CTkSwitch(
            material_toggle_row,
            text="",
            variable=self.add_material_properties_var,
            command=self._toggle_material_properties,
            onvalue=True,
            offvalue=False,
            fg_color="#3A3A3A",
            progress_color=state.colors["accent"],
            button_color=state.colors["text"],
            button_hover_color=state.colors["border"]
        )
        material_toggle.pack(side="left")

        self.material_properties_frame = ctk.CTkScrollableFrame(
            self.material_properties_container,
            fg_color=state.colors["card_bg"],
            corner_radius=8,
            height=450
        )

        self.dds_texture_label = ctk.CTkLabel(
            skin_card,
            text="DDS Texture",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=state.colors["text"]
        )
        self.dds_texture_label.pack(anchor="w", padx=15, pady=(5, 5))

        dds_row = ctk.CTkFrame(skin_card, fg_color="transparent")
        dds_row.pack(fill="x", padx=15, pady=(0, 5))

        dds_entry = ctk.CTkEntry(
            dds_row,
            textvariable=self.dds_path_var,
            state="readonly",
            height=36,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        )
        dds_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._setup_placeholder(dds_entry, "No file selected...")

        dds_browse = ctk.CTkButton(
            dds_row,
            text="📁 Browse",
            command=self.browse_dds,
            width=100,
            height=36,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8
        )
        dds_browse.pack(side="right")

        self.dds_preview_label = ctk.CTkLabel(
            skin_card,
            text="",
            image=None,
            width=800,
            height=400
        )
        self.dds_preview_label.pack(padx=15, pady=(5, 5))

        self.material_properties_container.pack(fill="x", padx=15, pady=(10, 10), before=self.dds_texture_label)

        skin_button_frame = ctk.CTkFrame(skin_card, fg_color="transparent")
        skin_button_frame.pack(fill="x", padx=15, pady=(5, 15))

        self.add_skin_btn = ctk.CTkButton(
            skin_button_frame,
            text="➕ Add Skin",
            command=self.add_skin_to_selected_car,
            height=40,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8
        )
        self.add_skin_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.cancel_edit_btn = ctk.CTkButton(
            skin_button_frame,
            text="❌ Cancel",
            command=self.cancel_skin_editing,
            height=40,
            width=100,
            fg_color=state.colors["error"],
            hover_color=state.colors["error_hover"],
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8
        )

        self.export_status_label = ctk.CTkLabel(
            self.generator_scroll,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=state.colors["text_secondary"]
        )

        self.progress_bar = ctk.CTkProgressBar(
            self.generator_scroll,
            height=8,
            corner_radius=4,
            fg_color=state.colors["frame_bg"],
            progress_color=state.colors["accent"]
        )

    def _create_card(self, parent) -> ctk.CTkFrame:
        """Create a card container"""
        return ctk.CTkFrame(
            parent,
            fg_color=state.colors["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=state.colors["border"]
        )

    def _create_button(self, parent, text: str, command, style: str = "primary", width: int = 120, height: int = 36) -> ctk.CTkButton:
        """Create a styled button"""
        if style == "primary":
            fg_color = state.colors["accent"]
            hover_color = state.colors["accent_hover"]
            text_color = state.colors["accent_text"]
        elif style == "danger":
            fg_color = state.colors["error"]
            hover_color = state.colors["error_hover"]
            text_color = "white"
        else:
            fg_color = state.colors["card_bg"]
            hover_color = state.colors["card_hover"]
            text_color = state.colors["text"]

        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=height,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold")
        )

    def _setup_placeholder(self, entry: ctk.CTkEntry, placeholder: str):
        """Setup placeholder text for an entry"""
        entry._placeholder = placeholder
        if not entry.get():
            entry.insert(0, placeholder)
            entry.configure(text_color="#888888")

        def on_focus_in(event):

            print(f"[DEBUG] on_focus_in called")
            if entry.get() == placeholder:
                entry.delete(0, "end")
                entry.configure(text_color=state.colors["text"])

        def on_focus_out(event):

            print(f"[DEBUG] on_focus_out called")
            if not entry.get():
                entry.insert(0, placeholder)
                entry.configure(text_color="#888888")

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def _bind_search(self):
        """Bind search functionality"""
        self.project_search_var.trace_add("write", lambda *args: self.refresh_project_display())

    def add_car_to_project(self, carid: str, display_name: str):

        print(f"[DEBUG] add_car_to_project called")
        """Add a car to the project"""
        print(f"[DEBUG] Adding car to project: {display_name} ({carid})")

        if carid in self.project_data["cars"]:
            self.show_notification(f"{display_name} is already in the project", "warning")
            self.select_car_for_skin(carid)
            return

        for car_id in self.project_data["cars"].keys():
            if car_id.startswith(f"{carid}_"):
                self.show_notification(f"{display_name} is already in the project", "warning")
                existing_car_id = carid if carid in self.project_data["cars"] else car_id
                self.select_car_for_skin(existing_car_id)
                return

        self.project_data["cars"][carid] = {
            "base_carid": carid,
            "skins": [],
            "temp_skin_name": "",
            "temp_dds_path": ""
        }

        self.show_notification(f"Added {display_name} to project", "success")

        print(f"[DEBUG] Selected car for skins: {carid}")

        self.select_car_for_skin(carid)

    def remove_car_from_project(self, car_instance_id: str):

        print(f"[DEBUG] remove_car_from_project called")
        """Remove a car instance from the project"""
        if car_instance_id in self.project_data["cars"]:
            base_carid = self.project_data["cars"][car_instance_id].get("base_carid", car_instance_id)
            del self.project_data["cars"][car_instance_id]

            if self.selected_car_for_skin == car_instance_id:
                self.selected_car_for_skin = None
            
            # Hide the add skin section if no cars remain
            if not self.project_data["cars"]:
                if self.add_skin_section_label:
                    self.add_skin_section_label.pack_forget()
                if self.add_skin_section_card:
                    self.add_skin_section_card.pack_forget()

            car_name = state.vehicle_ids.get(base_carid, base_carid)
            self.show_notification(f"Removed {car_name}", "info")

            self.refresh_project_display()

    def _toggle_car_expansion(self, car_id: str):
        """Toggle expansion of car to show/hide skins"""
        print(f"[DEBUG] _toggle_car_expansion called for {car_id}")

        if self.expanded_car_id == car_id:
            self.expanded_car_id = None
        else:

            self.expanded_car_id = car_id
            self.select_car_for_skin(car_id)

    def select_car_for_skin(self, car_instance_id: str):

        print(f"[DEBUG] select_car_for_skin called")
        """Select a car to add skins to"""
        if car_instance_id in self.project_data["cars"]:

            if self.editing_mode and self.selected_car_for_skin != car_instance_id:
                print(f"[DEBUG] Canceling editing mode - switching from {self.selected_car_for_skin} to {car_instance_id}")
                self.editing_mode = False
                self.selected_skin_index = None
                self._update_button_ui()

            self.selected_car_for_skin = car_instance_id
            print(f"[DEBUG] Selected car for adding skins: {car_instance_id}")
            
            # Show the add skin section
            if self.add_skin_section_label:
                self.add_skin_section_label.pack(anchor="w", padx=20, pady=(20, 5))
            if self.add_skin_section_card:
                self.add_skin_section_card.pack(fill="x", padx=20, pady=(0, 15))

            if not self.editing_mode:
                self._reset_skin_form_fields()

            self.refresh_project_display()

    def add_skin_to_selected_car(self):

        print(f"[DEBUG] add_skin_to_selected_car called")
        """Add a skin to the currently selected car or update existing skin"""

        if self.editing_mode and self.selected_skin_index is not None:
            self.update_skin()
            return

        if not self.selected_car_for_skin:
            self.show_notification("Please select a car first", "warning")
            return

        skin_name = self.skin_name_var.get().strip()
        dds_path = self.dds_path_var.get().strip()

        if not skin_name or skin_name == "Enter skin name...":
            self.show_notification("Please enter a skin name", "warning")
            return

        if not dds_path or dds_path == "No file selected...":
            self.show_notification("Please select a DDS file", "warning")
            return

        if not os.path.exists(dds_path):
            self.show_notification("DDS file does not exist", "error")
            return

        skin_data = {
            "name": skin_name,
            "dds_path": dds_path
        }

        if self.add_config_data_var.get():
            config_type = self.config_type_var.get()
            config_name = self.config_name_var.get().strip()
            pc_path = self.pc_file_path_var.get().strip()
            jpg_path = self.jpg_file_path_var.get().strip()

            print(f"[DEBUG] ===== CONFIG DATA VALIDATION =====")
            print(f"[DEBUG] Config type: {config_type}")
            print(f"[DEBUG] Config name: '{config_name}'")
            print(f"[DEBUG] PC path from StringVar: '{pc_path}'")
            print(f"[DEBUG] JPG path from StringVar: '{jpg_path}'")

            if self.pc_file_entry:
                entry_value = self.pc_file_entry.get()
                print(f"[DEBUG] PC Entry widget value: '{entry_value}'")

            if not config_name or config_name == "Enter configuration name...":
                self.show_notification("Please enter a configuration name", "warning")
                return

            if not pc_path or pc_path == "No .pc file selected...":
                print(f"[DEBUG] PC path validation FAILED: empty or placeholder")
                self.show_notification("Please select a .pc file for config data", "warning")
                return

            if not jpg_path or jpg_path == "No .jpg file selected...":
                self.show_notification("Please select a .jpg file for config data", "warning")
                return

            print(f"[DEBUG] Checking if PC path exists: {pc_path}")
            print(f"[DEBUG] os.path.exists(pc_path): {os.path.exists(pc_path)}")
            print(f"[DEBUG] os.path.isfile(pc_path): {os.path.isfile(pc_path)}")

            if not os.path.exists(pc_path):
                print(f"[DEBUG] PC FILE PATH DOES NOT EXIST!")
                print(f"[DEBUG] Path attempted: '{pc_path}'")
                print(f"[DEBUG] Path length: {len(pc_path)}")
                print(f"[DEBUG] Path repr: {repr(pc_path)}")
                self.show_notification(".pc file does not exist", "error")
                return

            if not os.path.exists(jpg_path):
                print(f"[DEBUG] JPG FILE PATH DOES NOT EXIST!")
                self.show_notification(".jpg file does not exist", "error")
                return

            skin_data["config_data"] = {
                "config_type": config_type,
                "config_name": config_name,
                "pc_file_path": pc_path,
                "jpg_file_path": jpg_path
            }
            print(f"[DEBUG] Adding skin with config data: Type={config_type}, Name={config_name}")
            print(f"[DEBUG] ===== CONFIG DATA VALIDATION COMPLETE =====")

        if self.add_material_properties_var.get():
            material_properties = self._collect_material_properties()
            if material_properties:
                skin_data['material_properties'] = material_properties
                print(f"[DEBUG] Added material properties to skin: {len(material_properties)} materials")

        self.project_data["cars"][self.selected_car_for_skin]["skins"].append(skin_data)
        print(f"[DEBUG] Added skin '{skin_name}'. Total skins: {len(self.project_data['cars'][self.selected_car_for_skin]['skins'])}")

        self.skin_name_var.set("")
        self.dds_path_var.set("")
        self.config_name_var.set("")
        self.pc_file_path_var.set("")
        self.jpg_file_path_var.set("")

        try:
            if hasattr(self, 'dds_preview_label') and self.dds_preview_label:
                if hasattr(self.dds_preview_label, 'image'):
                    self.dds_preview_label.image = None
                try:
                    self.dds_preview_label.configure(image=None, text="")
                except:
                    pass
                print(f"[DEBUG] DDS preview cleared")
        except Exception as e:
            print(f"[DEBUG] Error with preview (non-critical, skipping): {e}")

        try:
            if self.skin_name_entry:
                self.skin_name_entry.master.focus()
                self.skin_name_entry.delete(0, "end")
                self.skin_name_entry.insert(0, "Enter skin name...")
                self.skin_name_entry.configure(text_color="#888888")
                if hasattr(self.skin_name_entry, '_placeholder'):
                    self.skin_name_entry.event_generate("<FocusOut>")
                print(f"[DEBUG] Skin name entry reset with placeholder")
        except Exception as e:
            print(f"[DEBUG] Error resetting skin name: {e}")

        try:
            if self.config_name_entry:
                self.config_name_entry.delete(0, "end")
                self.config_name_entry.insert(0, "Enter configuration name...")
                self.config_name_entry.configure(text_color="#888888")
        except Exception as e:
            print(f"[DEBUG] Error resetting config name: {e}")

        try:
            if self.pc_file_entry:
                self.pc_file_entry.configure(state="normal")
                self.pc_file_entry.delete(0, "end")
                self.pc_file_entry.insert(0, "No .pc file selected...")
                self.pc_file_entry.configure(text_color="#888888", state="readonly")
        except Exception as e:
            print(f"[DEBUG] Error resetting pc entry: {e}")

        try:
            if self.jpg_file_entry:
                self.jpg_file_entry.configure(state="normal")
                self.jpg_file_entry.delete(0, "end")
                self.jpg_file_entry.insert(0, "No .jpg file selected...")
                self.jpg_file_entry.configure(text_color="#888888", state="readonly")
        except Exception as e:
            print(f"[DEBUG] Error resetting jpg entry: {e}")

        self.show_notification(f"Added skin '{skin_name}'", "success")

        print(f"[DEBUG] Starting deselect/reselect refresh...")

        current = self.selected_car_for_skin
        print(f"[DEBUG] Current selection: {current}")

        self.selected_car_for_skin = None
        print(f"[DEBUG] Deselected - calling refresh...")
        self.refresh_project_display()

        self.update_idletasks()
        print(f"[DEBUG] Deselect refresh complete")

        print(f"[DEBUG] Scheduling reselect in 50ms...")
        self.after(50, lambda: self._reselect_car(current))

        print(f"[DEBUG] Skin addition complete!")

    def _force_scrollable_reflow(self):
        """Force the scrollable container to recalculate and redraw"""
        try:
            canvas = self.project_overview_container._parent_canvas
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.event_generate("<Configure>")
            print(f"[DEBUG] Scrollable reflow executed successfully")
        except Exception as e:
            print(f"[DEBUG] Scrollable reflow error (non-critical): {e}")

    def _reselect_car(self, car_id):
        """Re-select a car after a forced refresh"""
        self.selected_car_for_skin = car_id
        self.refresh_project_display()

        try:
            if hasattr(self, 'project_overview_frame') and self.project_overview_frame:
                for widget in self.project_overview_frame.winfo_children():
                    widget.update()
                self.project_overview_frame.update()

            if hasattr(self, 'project_overview_container') and self.project_overview_container:
                self.project_overview_container.update()

            self.update()

            print(f"[DEBUG] Car reselected with forced updates: {car_id}")
        except Exception as e:
            print(f"[DEBUG] Update error (non-critical): {e}")

    def _update_scroll_region(self):
        """Helper method to update the scroll region of the project overview frame"""
        if hasattr(self, 'project_overview_frame') and self.project_overview_frame:
            try:
                self.project_overview_frame.update_idletasks()
                if hasattr(self.project_overview_frame, '_parent_canvas'):
                    canvas = self.project_overview_frame._parent_canvas
                    canvas.configure(scrollregion=canvas.bbox("all"))
                    canvas.update()
                    print("[DEBUG] Scroll region updated successfully")
            except Exception as e:
                print(f"[DEBUG] Error updating scroll region: {e}")

    def select_skin_for_editing(self, car_instance_id: str, skin_index: int):
        """Select a skin for editing

        Args:
            car_instance_id: The car instance ID
            skin_index: Index of the skin to edit
        """
        print(f"[DEBUG] select_skin_for_editing called for car {car_instance_id}, skin index {skin_index}")

        if car_instance_id not in self.project_data["cars"]:
            print(f"[DEBUG] Car {car_instance_id} not found in project")
            return

        skins = self.project_data["cars"][car_instance_id]["skins"]
        if skin_index < 0 or skin_index >= len(skins):
            print(f"[DEBUG] Invalid skin index {skin_index}")
            return

        self.selected_car_for_skin = car_instance_id
        self.selected_skin_index = skin_index
        self.editing_mode = True

        self._update_button_ui()

        skin = skins[skin_index]
        print(f"[DEBUG] Editing skin: {skin['name']}")

        try:
            if self.skin_name_entry:
                self.skin_name_entry.delete(0, "end")
                self.skin_name_entry.insert(0, skin['name'])
                self.skin_name_entry.configure(text_color=state.colors["text"])
        except Exception as e:
            print(f"[DEBUG] Error setting skin name: {e}")

        try:
            if 'dds_path' in skin:
                self.dds_path_var.set(skin['dds_path'])

                try:
                    img = Image.open(skin['dds_path'])
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)

                    try:
                        self.dds_preview_label.configure(image="", text="")
                    except:
                        pass

                    if hasattr(self.dds_preview_label, 'image'):
                        old_image = self.dds_preview_label.image
                        self.dds_preview_label.image = None
                        del old_image

                    self.dds_preview_label.image = photo
                    self.dds_preview_label.configure(image=photo)

                    self.dds_preview_label.update_idletasks()

                    print(f"[DEBUG] Loaded DDS preview for editing: {skin['dds_path']}")
                except Exception as e:
                    print(f"[DEBUG] Could not load DDS preview: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        self.dds_preview_label.configure(image="", text="Preview unavailable")
                        if hasattr(self.dds_preview_label, 'image'):
                            self.dds_preview_label.image = None
                    except:
                        pass
        except Exception as e:
            print(f"[DEBUG] Error setting DDS path: {e}")

        try:
            if 'config_data' in skin:
                config_data = skin['config_data']
                print(f"[DEBUG] Config data found in skin: {config_data}")

                self.add_config_data_var.set(True)
                print(f"[DEBUG] Set add_config_data_var to True")

                self._toggle_config_data()
                print(f"[DEBUG] Called _toggle_config_data to show fields")

                self.update_idletasks()

                if 'config_type' in config_data:
                    self.config_type_var.set(config_data['config_type'])
                    print(f"[DEBUG] Set config_type to: {config_data['config_type']}")

                if 'config_name' in config_data and self.config_name_entry:
                    self.config_name_entry.delete(0, "end")
                    self.config_name_entry.insert(0, config_data['config_name'])
                    self.config_name_entry.configure(text_color=state.colors["text"])
                    print(f"[DEBUG] Set config_name to: {config_data['config_name']}")

                if 'pc_file_path' in config_data and self.pc_file_entry:

                    self.pc_file_path_var.set(config_data['pc_file_path'])

                    self.pc_file_from_project = True

                    self.pc_file_entry.configure(textvariable="")
                    self.pc_file_entry.configure(state="normal")
                    self.pc_file_entry.delete(0, "end")
                    self.pc_file_entry.insert(0, os.path.basename(config_data['pc_file_path']))
                    self.pc_file_entry.configure(text_color=state.colors["text"], state="readonly")
                    print(f"[DEBUG] Set PC file to: {config_data['pc_file_path']}")

                if 'jpg_file_path' in config_data and self.jpg_file_entry:

                    self.jpg_file_path_var.set(config_data['jpg_file_path'])

                    self.jpg_file_from_project = True

                    self.jpg_file_entry.configure(textvariable="")
                    self.jpg_file_entry.configure(state="normal")
                    self.jpg_file_entry.delete(0, "end")
                    self.jpg_file_entry.insert(0, os.path.basename(config_data['jpg_file_path']))
                    self.jpg_file_entry.configure(text_color=state.colors["text"], state="readonly")
                    print(f"[DEBUG] Set JPG file to: {config_data['jpg_file_path']}")
            else:

                self.add_config_data_var.set(False)

                self.config_type_var.set("Factory")

                if self.config_name_entry:
                    self.config_name_entry.delete(0, "end")
                    self.config_name_entry.insert(0, "Enter configuration name...")
                    self.config_name_entry.configure(text_color="#888888")

                self.pc_file_path_var.set("")
                if self.pc_file_entry:
                    self.pc_file_entry.configure(state="normal")
                    self.pc_file_entry.delete(0, "end")
                    self.pc_file_entry.insert(0, "No .pc file selected...")
                    self.pc_file_entry.configure(text_color="#888888", state="readonly")

                self.jpg_file_path_var.set("")
                if self.jpg_file_entry:
                    self.jpg_file_entry.configure(state="normal")
                    self.jpg_file_entry.delete(0, "end")
                    self.jpg_file_entry.insert(0, "No .jpg file selected...")
                    self.jpg_file_entry.configure(text_color="#888888", state="readonly")

                self._toggle_config_data()

            print(f"[DEBUG] Form populated with skin data")

        except Exception as e:
            print(f"[DEBUG] Error populating config data: {e}")
            import traceback
            traceback.print_exc()

        try:
            if 'material_properties' in skin:
                material_props = skin['material_properties']
                print(f"[DEBUG] Material properties found in skin: {len(material_props)} materials")

                self.add_material_properties_var.set(True)
                print(f"[DEBUG] Set add_material_properties_var to True")

                self._toggle_material_properties()

                self.update_idletasks()

                self._load_material_properties_into_ui(material_props)

                print(f"[DEBUG] Material properties populated in UI")
            else:
                print(f"[DEBUG] No material properties in this skin")

                self.add_material_properties_var.set(False)
                self._toggle_material_properties()

        except Exception as e:
            print(f"[DEBUG] Error populating material properties: {e}")
            import traceback
            traceback.print_exc()

        self.refresh_project_display()

        self.show_notification(f"Editing skin: {skin['name']}", "info")

    def _update_button_ui(self):
        """Update the Add/Update button text and show/hide cancel button based on editing mode"""
        if self.editing_mode:

            self.add_skin_btn.configure(text="💾 Update Skin")
            self.cancel_edit_btn.pack(side="left", padx=(5, 0))
        else:

            self.add_skin_btn.configure(text="➕ Add Skin")
            self.cancel_edit_btn.pack_forget()

    def cancel_skin_editing(self):
        """Cancel skin editing mode and clear the form"""
        print(f"[DEBUG] cancel_skin_editing called")

        self.editing_mode = False
        self.selected_skin_index = None

        self._update_button_ui()

        self._reset_skin_form_fields()

        self.refresh_project_display()

        self.show_notification("Cancelled editing", "info")

    def update_skin(self):
        """Update the selected skin with new values from the form"""
        print(f"[DEBUG] update_skin called")

        if not self.editing_mode or self.selected_skin_index is None:
            print(f"[DEBUG] Not in editing mode or no skin selected")
            return

        if not self.selected_car_for_skin or self.selected_car_for_skin not in self.project_data["cars"]:
            print(f"[DEBUG] No car selected or car not in project")
            self.cancel_skin_editing()
            return

        skin_name = self.get_real_value(self.skin_name_entry, "Enter skin name...").strip()
        dds_path = self.dds_path_var.get().strip()

        if not skin_name:
            self.show_notification("Skin name is required", "error")
            return

        if not dds_path or not os.path.exists(dds_path):
            self.show_notification("Please select a valid DDS file", "error")
            return

        skins = self.project_data["cars"][self.selected_car_for_skin]["skins"]
        if self.selected_skin_index >= len(skins):
            print(f"[DEBUG] Invalid skin index")
            self.cancel_skin_editing()
            return

        skin = skins[self.selected_skin_index]
        old_name = skin['name']

        skin['name'] = skin_name
        skin['dds_path'] = dds_path

        if self.add_config_data_var.get():
            config_name = self.get_real_value(self.config_name_entry, "Enter configuration name...").strip()
            pc_file_path = self.pc_file_path_var.get().strip()
            jpg_file_path = self.jpg_file_path_var.get().strip()

            print(f"[DEBUG] Config name: '{config_name}'")
            print(f"[DEBUG] PC file path from form: '{pc_file_path}'")
            print(f"[DEBUG] JPG file path from form: '{jpg_file_path}'")
            print(f"[DEBUG] PC file from project flag: {self.pc_file_from_project}")
            print(f"[DEBUG] JPG file from project flag: {self.jpg_file_from_project}")

            if not config_name:
                self.show_notification("Configuration name is required", "error")
                return

            existing_config = skin.get('config_data', {})
            existing_pc_path = existing_config.get('pc_file_path', '')
            existing_jpg_path = existing_config.get('jpg_file_path', '')

            print(f"[DEBUG] Existing PC path: '{existing_pc_path}'")
            print(f"[DEBUG] Existing JPG path: '{existing_jpg_path}'")
            print(f"[DEBUG] PC paths match: {pc_file_path == existing_pc_path}")
            print(f"[DEBUG] JPG paths match: {jpg_file_path == existing_jpg_path}")

            if self.pc_file_from_project and pc_file_path == existing_pc_path:
                print(f"[DEBUG] PC path unchanged from project load, skipping existence check")

                if not pc_file_path:
                    print(f"[DEBUG] PC file path is empty")
                    self.show_notification("Please select a valid .pc file", "error")
                    return
            elif pc_file_path != existing_pc_path:
                print(f"[DEBUG] PC path changed or new, validating existence...")

                if not pc_file_path or not os.path.exists(pc_file_path):
                    print(f"[DEBUG] PC file validation failed - path: '{pc_file_path}', exists: {os.path.exists(pc_file_path) if pc_file_path else False}")
                    self.show_notification("Please select a valid .pc file", "error")
                    return
            else:
                print(f"[DEBUG] PC path unchanged, skipping existence check")

                if not pc_file_path:
                    print(f"[DEBUG] PC file path is empty")
                    self.show_notification("Please select a valid .pc file", "error")
                    return

            if self.jpg_file_from_project and jpg_file_path == existing_jpg_path:
                print(f"[DEBUG] JPG path unchanged from project load, skipping existence check")

                if not jpg_file_path:
                    print(f"[DEBUG] JPG file path is empty")
                    self.show_notification("Please select a valid .jpg file", "error")
                    return
            elif jpg_file_path != existing_jpg_path:
                print(f"[DEBUG] JPG path changed or new, validating existence...")

                if not jpg_file_path or not os.path.exists(jpg_file_path):
                    print(f"[DEBUG] JPG file validation failed - path: '{jpg_file_path}', exists: {os.path.exists(jpg_file_path) if jpg_file_path else False}")
                    self.show_notification("Please select a valid .jpg file", "error")
                    return
            else:
                print(f"[DEBUG] JPG path unchanged, skipping existence check")

                if not jpg_file_path:
                    print(f"[DEBUG] JPG file path is empty")
                    self.show_notification("Please select a valid .jpg file", "error")
                    return

            skin['config_data'] = {
                'config_type': self.config_type_var.get(),
                'config_name': config_name,
                'pc_file_path': pc_file_path,
                'jpg_file_path': jpg_file_path
            }
        else:

            if 'config_data' in skin:
                del skin['config_data']

        if self.add_material_properties_var.get():
            material_properties = self._collect_material_properties()
            if material_properties:
                skin['material_properties'] = material_properties
                print(f"[DEBUG] Updated material properties: {len(material_properties)} materials")
        else:

            if 'material_properties' in skin:
                del skin['material_properties']
                print(f"[DEBUG] Removed material properties from skin")

        print(f"[DEBUG] Updated skin '{old_name}' -> '{skin_name}'")

        self.editing_mode = False
        self.selected_skin_index = None

        self._update_button_ui()

        self._reset_skin_form_fields()

        self.show_notification(f"Updated skin: {skin_name}", "success")

        current = self.selected_car_for_skin
        self.selected_car_for_skin = None
        self.refresh_project_display()
        self.after(50, lambda: self._reselect_car(current))

    def _reset_skin_form_fields(self):
        """Reset all skin form fields to their placeholder state"""
        try:

            if self.skin_name_entry:
                self.skin_name_entry.delete(0, "end")
                self.skin_name_entry.insert(0, "Enter skin name...")
                self.skin_name_entry.configure(text_color="#888888")
                if hasattr(self.skin_name_entry, '_placeholder'):
                    self.skin_name_entry.event_generate("<FocusOut>")
        except Exception as e:
            print(f"[DEBUG] Error resetting skin name: {e}")

        try:

            self.dds_path_var.set("")
            if self.dds_preview_label:
                self.dds_preview_label.image = None
                self.dds_preview_label.configure(image=None, text="No DDS selected")
        except Exception as e:
            print(f"[DEBUG] Error resetting DDS: {e}")

        try:

            self.add_config_data_var.set(False)
        except Exception as e:
            print(f"[DEBUG] Error resetting config checkbox: {e}")

        try:

            if self.config_name_entry:
                self.config_name_entry.delete(0, "end")
                self.config_name_entry.insert(0, "Enter configuration name...")
                self.config_name_entry.configure(text_color="#888888")
        except Exception as e:
            print(f"[DEBUG] Error resetting config name: {e}")

        try:

            self.pc_file_path_var.set("")

            self.pc_file_from_project = False
            if self.pc_file_entry:
                self.pc_file_entry.configure(state="normal")
                self.pc_file_entry.delete(0, "end")
                self.pc_file_entry.insert(0, "No .pc file selected...")
                self.pc_file_entry.configure(text_color="#888888", state="readonly")
        except Exception as e:
            print(f"[DEBUG] Error resetting PC file: {e}")

        try:

            self.jpg_file_path_var.set("")

            self.jpg_file_from_project = False
            if self.jpg_file_entry:
                self.jpg_file_entry.configure(state="normal")
                self.jpg_file_entry.delete(0, "end")
                self.jpg_file_entry.insert(0, "No .jpg file selected...")
                self.jpg_file_entry.configure(text_color="#888888", state="readonly")
        except Exception as e:
            print(f"[DEBUG] Error resetting JPG file: {e}")

        try:

            self._toggle_config_data()
        except Exception as e:
            print(f"[DEBUG] Error toggling config data visibility: {e}")

        try:

            self.add_material_properties_var.set(False)

            if self.material_properties_frame:
                self.material_properties_frame.pack_forget()

                for widget in self.material_properties_frame.winfo_children():
                    widget.destroy()
                self.material_properties_entries.clear()
                print("[DEBUG] Material properties UI cleared")
        except Exception as e:
            print(f"[DEBUG] Error resetting material properties: {e}")

    def remove_skin_from_car(self, car_instance_id: str, skin_index: int):

        print(f"[DEBUG] remove_skin_from_car called")
        """Remove a skin from a car"""
        if car_instance_id in self.project_data["cars"]:
            skins = self.project_data["cars"][car_instance_id]["skins"]
            if 0 <= skin_index < len(skins):
                skin_name = skins[skin_index]["name"]
                del skins[skin_index]
                self.show_notification(f"Removed skin '{skin_name}'", "info")
                self.refresh_project_display()
                self.update_idletasks()
                if hasattr(self, 'project_overview_frame') and self.project_overview_frame:
                    self.project_overview_frame.update_idletasks()
                    self.after(10, self._update_scroll_region)

    def browse_dds(self):

        print(f"[DEBUG] browse_dds called")
        """Browse for DDS file"""
        filename = filedialog.askopenfilename(
            title="Select DDS Texture",
            filetypes=[("DDS files", "*.dds"), ("All files", "*.*")]
        )

        if filename:
            self.dds_path_var.set(filename)

            try:
                img = Image.open(filename)
                img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)

                try:
                    self.dds_preview_label.configure(image=None, text="")
                except:
                    pass

                self.dds_preview_label.image = photo

                try:
                    self.dds_preview_label.configure(image=photo)
                except:
                    pass

                print(f"[DEBUG] DDS preview loaded: {filename}")
            except Exception as e:
                print(f"[DEBUG] Could not load DDS preview: {e}")
                try:
                    if hasattr(self, 'dds_preview_label') and self.dds_preview_label:
                        self.dds_preview_label.image = None
                        self.dds_preview_label.configure(text="Preview unavailable")
                except:
                    pass

    def _toggle_config_data(self):
        """Toggle visibility of config data section"""
        if self.add_config_data_var.get():

            self.config_name_label.pack(side="left", padx=(0, 8), after=self.skin_name_entry)
            self.config_name_entry.pack(side="left", padx=(0, 10), after=self.config_name_label)

            self.config_type_entry_row.pack(side="left")

            self.config_files_container.pack(fill="x", pady=(0, 10), before=self.material_properties_container)

            print("[DEBUG] Config data section shown")
        else:

            self.config_name_label.pack_forget()
            self.config_name_entry.pack_forget()
            self.config_type_entry_row.pack_forget()
            self.config_files_container.pack_forget()

            print("[DEBUG] Config data section hidden")

    def _browse_pc_file(self):
        """Browse for .pc file in BeamNG vehicles folder"""
        try:
            from utils.config_helper import get_beamng_vehicles_path
            vehicles_path = get_beamng_vehicles_path()
        except ImportError:
            import getpass
            username = getpass.getuser()
            vehicles_path = os.path.join(
                "C:\\Users", username, "AppData", "Local", "BeamNG",
                "BeamNG.drive", "current", "vehicles"
            )

        initial_dir = vehicles_path
        if self.selected_car_for_skin and self.selected_car_for_skin in self.project_data["cars"]:
            base_carid = self.project_data["cars"][self.selected_car_for_skin].get("base_carid")
            if base_carid:
                car_folder = os.path.join(vehicles_path, base_carid)
                if os.path.exists(car_folder):
                    initial_dir = car_folder

        filename = filedialog.askopenfilename(
            title="Select .pc File (Vehicle Config)",
            initialdir=initial_dir,
            filetypes=[("PC files", "*.pc"), ("All files", "*.*")]
        )

        if filename:

            self.pc_file_path_var.set(filename)

            self.pc_file_from_project = False
            print(f"[DEBUG] Selected .pc file: {filename}")
            print(f"[DEBUG] File exists: {os.path.exists(filename)}")
            print(f"[DEBUG] StringVar value set to: {self.pc_file_path_var.get()}")

    def _browse_jpg_file(self):
        """Browse for .jpg file in BeamNG vehicles folder"""
        try:
            from utils.config_helper import get_beamng_vehicles_path
            vehicles_path = get_beamng_vehicles_path()
        except ImportError:
            import getpass
            username = getpass.getuser()
            vehicles_path = os.path.join(
                "C:\\Users", username, "AppData", "Local", "BeamNG",
                "BeamNG.drive", "current", "vehicles"
            )

        initial_dir = vehicles_path
        if self.selected_car_for_skin and self.selected_car_for_skin in self.project_data["cars"]:
            base_carid = self.project_data["cars"][self.selected_car_for_skin].get("base_carid")
            if base_carid:
                car_folder = os.path.join(vehicles_path, base_carid)
                if os.path.exists(car_folder):
                    initial_dir = car_folder

        filename = filedialog.askopenfilename(
            title="Select .jpg File (Config Icon)",
            initialdir=initial_dir,
            filetypes=[("JPG files", "*.jpg"), ("JPEG files", "*.jpeg"), ("All files", "*.*")]
        )

        if filename:

            self.jpg_file_path_var.set(filename)

            self.jpg_file_from_project = False
            print(f"[DEBUG] Selected .jpg file: {filename}")
            print(f"[DEBUG] File exists: {os.path.exists(filename)}")
            print(f"[DEBUG] StringVar value set to: {self.jpg_file_path_var.get()}")

    def _toggle_material_properties(self):
        """Toggle visibility and populate material properties section"""
        print(f"\n[DEBUG] ========== _toggle_material_properties called ==========")
        print(f"[DEBUG] Checkbox state: {self.add_material_properties_var.get()}")

        if self.add_material_properties_var.get():
            try:
                print(f"[DEBUG] Attempting to show material properties...")

                print(f"[DEBUG] selected_car_for_skin: {self.selected_car_for_skin}")
                print(f"[DEBUG] Cars in project: {list(self.project_data['cars'].keys())}")

                if not self.selected_car_for_skin or self.selected_car_for_skin not in self.project_data["cars"]:
                    print(f"[DEBUG] No car selected or car not in project")
                    self.show_notification("Please select a car first", "warning")
                    self.add_material_properties_var.set(False)
                    return

                car_info = self.project_data["cars"][self.selected_car_for_skin]
                base_carid = car_info.get("base_carid")
                print(f"[DEBUG] base_carid: {base_carid}")

                if not base_carid:
                    print(f"[DEBUG] No base_carid found in car_info")
                    self.show_notification("Car configuration error", "error")
                    self.add_material_properties_var.set(False)
                    return

                if self.material_properties_entries:
                    print(f"[DEBUG] Material properties UI already exists with {len(self.material_properties_entries)} materials")
                    print(f"[DEBUG] Showing existing UI instead of regenerating...")
                    if self.material_properties_frame:
                        self.material_properties_frame.pack(fill="both", expand=True, pady=(5, 0))
                        print("[DEBUG] Material properties section shown (existing UI)")
                    return

                print(f"[DEBUG] Calling _load_material_structure for {base_carid}...")
                materials = self._load_material_structure(base_carid)
                print(f"[DEBUG] Materials loaded: {len(materials) if materials else 0} materials")

                if not materials:
                    print(f"[DEBUG] No materials found, showing error message...")

                    project_root = None
                    cwd_vehicles = os.path.join(os.getcwd(), "vehicles", base_carid)
                    if os.path.exists(cwd_vehicles):
                        project_root = os.getcwd()

                    if not project_root:
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        potential_root = os.path.dirname(os.path.dirname(script_dir))
                        if os.path.exists(os.path.join(potential_root, "vehicles", base_carid)):
                            project_root = potential_root

                    file_exists = False
                    if project_root:
                        vehicle_path = os.path.join(project_root, "vehicles", base_carid)
                        if os.path.exists(vehicle_path):
                            for root, dirs, files in os.walk(vehicle_path):
                                if 'skin.materials.json' in files or 'materials.json' in files:
                                    file_exists = True
                                    break

                    if file_exists:
                        self.show_notification(f"Material file found for {base_carid}, but contains no editable properties", "warning", 4000)
                    else:
                        self.show_notification(f"No material file found for {base_carid}", "warning", 4000)

                    self.add_material_properties_var.set(False)
                    return

                print(f"[DEBUG] Calling _populate_material_properties_ui...")
                print(f"[DEBUG] Materials to populate: {list(materials.keys())}")
                self._populate_material_properties_ui(materials)
                print(f"[DEBUG] _populate_material_properties_ui completed")

                print(f"[DEBUG] Showing material_properties_frame...")
                if self.material_properties_frame:
                    self.material_properties_frame.pack(fill="both", expand=True, pady=(5, 0))
                    print("[DEBUG] Material properties section shown")
                else:
                    print("[DEBUG] ERROR: material_properties_frame is None!")
                    self.show_notification("Material properties frame not initialized", "error")
                    self.add_material_properties_var.set(False)

            except Exception as e:
                print(f"[DEBUG] !!! EXCEPTION in _toggle_material_properties !!!")
                print(f"[DEBUG] Error: {e}")
                import traceback
                traceback.print_exc()
                self.show_notification(f"Error loading material properties: {str(e)}", "error", 5000)
                self.add_material_properties_var.set(False)
        else:
            print(f"[DEBUG] Hiding material properties section...")

            if self.material_properties_frame:
                self.material_properties_frame.pack_forget()
                print("[DEBUG] Material properties section hidden (widgets preserved)")
            else:
                print("[DEBUG] material_properties_frame is None, cannot hide")
        print(f"[DEBUG] ========== _toggle_material_properties finished ==========\n")

    def _load_material_structure(self, car_id: str) -> Dict:
        """
        Load material structure from skin.materials.json or materials.json
        Returns dict with material names and their editable properties
        """

        project_root = None

        cwd_vehicles = os.path.join(os.getcwd(), "vehicles", car_id)
        if os.path.exists(cwd_vehicles):
            project_root = os.getcwd()
            print(f"[DEBUG] Found vehicles folder using cwd: {cwd_vehicles}")

        if not project_root:
            script_dir = os.path.dirname(os.path.abspath(__file__))

            potential_root = os.path.dirname(os.path.dirname(script_dir))
            potential_vehicles = os.path.join(potential_root, "vehicles", car_id)
            if os.path.exists(potential_vehicles):
                project_root = potential_root
                print(f"[DEBUG] Found vehicles folder using script dir: {potential_vehicles}")

        if not project_root:
            current = os.getcwd()
            for _ in range(5):
                test_path = os.path.join(current, "vehicles", car_id)
                if os.path.exists(test_path):
                    project_root = current
                    print(f"[DEBUG] Found vehicles folder searching upward: {test_path}")
                    break
                parent = os.path.dirname(current)
                if parent == current:
                    break
                current = parent

        if project_root:
            vehicle_base_path = os.path.join(project_root, "vehicles", car_id)
            print(f"[DEBUG] Using project root: {project_root}")
            print(f"[DEBUG] Vehicle base path: {vehicle_base_path}")
        else:
            print(f"[DEBUG] Could not find vehicles folder in project, will try BeamNG installation only")
            vehicle_base_path = None

        material_data = {}
        files_found = []

        search_paths = []

        if vehicle_base_path and os.path.exists(vehicle_base_path):
            print(f"[DEBUG] Vehicle folder exists, scanning for subdirectories...")

            try:
                for item in os.listdir(vehicle_base_path):
                    item_path = os.path.join(vehicle_base_path, item)
                    if os.path.isdir(item_path):

                        search_paths.append(item_path)
                        print(f"[DEBUG] Found skin folder: {item_path}")
            except Exception as e:
                print(f"[DEBUG] Error reading vehicle folder: {e}")
        else:
            if vehicle_base_path:
                print(f"[DEBUG] Vehicle folder does not exist: {vehicle_base_path}")

        try:
            from core.settings import get_beamng_path
            beamng_path = get_beamng_path()
            search_paths.extend([
                os.path.join(beamng_path, "vehicles", car_id, "skins"),
                os.path.join(beamng_path, "vehicles", car_id)
            ])
        except:
            import getpass
            username = getpass.getuser()
            beamng_path = os.path.join("C:\\Users", username, "AppData", "Local", "BeamNG.drive", "0.33")
            search_paths.extend([
                os.path.join(beamng_path, "vehicles", car_id, "skins"),
                os.path.join(beamng_path, "vehicles", car_id)
            ])

        for search_path in search_paths:
            if not os.path.exists(search_path):
                print(f"[DEBUG] Search path does not exist: {search_path}")
                continue

            print(f"[DEBUG] Searching for materials in: {search_path}")

            try:
                for filename in os.listdir(search_path):
                    if filename in ['skin.materials.json', 'materials.json']:
                        filepath = os.path.join(search_path, filename)
                        files_found.append(filepath)
                        print(f"[DEBUG] Found material file: {filepath}")

                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                content = f.read()

                            import re

                            content = re.sub(r',(\s*[}\]])', r'\1', content)

                            try:
                                data = json.loads(content)
                            except json.JSONDecodeError as e:
                                print(f"[DEBUG] JSON decode error in {filename} even after cleanup: {e}")
                                print(f"[DEBUG] Error at line {e.lineno}, column {e.colno}")
                                import traceback
                                traceback.print_exc()
                                continue

                            for material_name, material_info in data.items():

                                if "Stages" not in material_info:
                                    continue

                                stages = material_info["Stages"]
                                if not stages or not isinstance(stages, list):
                                    continue

                                properties = {}
                                for stage_idx, stage in enumerate(stages):
                                    stage_properties = {}

                                    for prop in ["clearCoatFactor", "clearCoatRoughnessFactor", "metallicFactor", "roughnessFactor"]:
                                        if prop in stage:
                                            stage_properties[prop] = stage[prop]

                                    if stage_properties:
                                        properties[f"stage_{stage_idx}"] = stage_properties

                                if properties:

                                    part_name = material_name.split('.')[0] if '.' in material_name else material_name

                                    material_data[material_name] = {
                                        "part_name": part_name,
                                        "properties": properties
                                    }

                            if material_data:
                                print(f"[DEBUG] Loaded {len(material_data)} materials from: {filename}")
                                return material_data
                            else:

                                print(f"[DEBUG] Material file exists but contains no editable properties: {filepath}")

                        except Exception as e:
                            print(f"[DEBUG] Error loading {filename}: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
            except Exception as e:
                print(f"[DEBUG] Error listing directory {search_path}: {e}")
                continue

        if files_found:
            print(f"[DEBUG] Material files found but contained no editable properties:")
            for f in files_found:
                print(f"[DEBUG]   - {f}")
            print(f"[DEBUG] (No clearCoatFactor, clearCoatRoughnessFactor, metallicFactor, or roughnessFactor found)")
        else:
            print(f"[DEBUG] No material files found for {car_id} in any search path")

        return material_data

    def _populate_material_properties_ui(self, materials: Dict):
        """
        Populate the material properties UI with entry fields
        materials: Dict from _load_material_structure
        """

        for widget in self.material_properties_frame.winfo_children():
            widget.destroy()
        self.material_properties_entries.clear()

        header = ctk.CTkLabel(
            self.material_properties_frame,
            text="Material Properties",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=state.colors["text"]
        )
        header.pack(anchor="w", padx=15, pady=(15, 5))

        info_label = ctk.CTkLabel(
            self.material_properties_frame,
            text="Valid values: 0 to 1 (e.g., 0.5, 0.242426) or leave empty for null",
            font=ctk.CTkFont(size=10),
            text_color="#888888"
        )
        info_label.pack(anchor="w", padx=15, pady=(0, 10))

        for material_name, material_info in materials.items():
            part_name = material_info["part_name"]
            properties = material_info["properties"]

            material_section = ctk.CTkFrame(
                self.material_properties_frame,
                fg_color=state.colors["sidebar_bg"],
                corner_radius=6
            )
            material_section.pack(fill="x", padx=10, pady=(0, 10))

            material_header = ctk.CTkLabel(
                material_section,
                text=f"📦 {part_name}",
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=state.colors["text"],
                anchor="w"
            )
            material_header.pack(anchor="w", padx=10, pady=(8, 5))

            material_tech_name = ctk.CTkLabel(
                material_section,
                text=f"({material_name})",
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=state.colors["text"],
                anchor="w"
            )
            material_tech_name.pack(anchor="w", padx=10, pady=(0, 5))

            self.material_properties_entries[material_name] = {}

            for stage_key, stage_props in properties.items():
                stage_label = f"Stage {stage_key.split('_')[1]}"

                if len(properties) > 1:
                    stage_header = ctk.CTkLabel(
                        material_section,
                        text=stage_label,
                        font=ctk.CTkFont(size=10, weight="bold"),
                        text_color="#888888",
                        anchor="w"
                    )
                    stage_header.pack(anchor="w", padx=15, pady=(5, 3))

                for prop_name, prop_value in stage_props.items():
                    prop_row = ctk.CTkFrame(material_section, fg_color="transparent")
                    prop_row.pack(fill="x", padx=15, pady=2)

                    label_text = prop_name.replace("Factor", "").replace("clearCoat", "Clear Coat ")
                    label_text = label_text.replace("metallic", "Metallic").replace("roughness", "Roughness")

                    prop_label = ctk.CTkLabel(
                        prop_row,
                        text=f"{label_text}:",
                        font=ctk.CTkFont(size=12, weight="bold"),
                text_color=state.colors["text"],
                        width=140,
                        anchor="w"
                    )
                    prop_label.pack(side="left")

                    prop_entry = ctk.CTkEntry(
                        prop_row,
                        width=100,
                        height=28,
                        font=ctk.CTkFont(size=11),
                        fg_color=state.colors["app_bg"],
                        border_color=state.colors["border"],
                        border_width=1,
                        placeholder_text="0-1 or null"
                    )
                    prop_entry.pack(side="left", padx=(5, 0))

                    if prop_value is None:
                        prop_entry.insert(0, "null")
                    else:
                        prop_entry.insert(0, str(prop_value))

                    entry_key = f"{stage_key}_{prop_name}"
                    self.material_properties_entries[material_name][entry_key] = prop_entry

            spacer = ctk.CTkFrame(material_section, fg_color="transparent", height=5)
            spacer.pack()

    def _collect_material_properties(self) -> Dict:
        """Collect all material property values from the UI"""
        result = {}

        print("[DEBUG] ===== _collect_material_properties called =====")

        for material_name, entries in self.material_properties_entries.items():
            print(f"[DEBUG] Processing material: {material_name}")
            material_props = {}

            stages = {}
            for entry_key, entry_widget in entries.items():

                parts = entry_key.split('_', 2)
                if len(parts) < 3:
                    continue

                stage_num = parts[1]
                prop_name = parts[2]

                print(f"[DEBUG]   Entry: {entry_key}, Stage: {stage_num}, Prop: {prop_name}")

                try:
                    value = entry_widget.get().strip()
                    print(f"[DEBUG]   Raw value from UI: '{value}'")

                    if not value or value.lower() == "null":
                        if stage_num not in stages:
                            stages[stage_num] = {}
                        stages[stage_num][prop_name] = None
                        print(f"[DEBUG]   Set to None")
                        continue

                    if '.' in value:
                        numeric_value = float(value)
                    else:
                        numeric_value = int(value)

                    print(f"[DEBUG]   Converted to numeric: {numeric_value} (type: {type(numeric_value).__name__})")

                    if numeric_value < 0 or numeric_value > 1:
                        print(f"[WARNING] Value out of range for {material_name}.{prop_name}: {numeric_value} (must be 0-1)")
                        self.show_notification(f"Warning: {prop_name} value {numeric_value} is out of range (0-1)", "warning", 4000)

                        numeric_value = max(0, min(1, numeric_value))
                        print(f"[WARNING] Clamped to: {numeric_value}")

                    if stage_num not in stages:
                        stages[stage_num] = {}
                    stages[stage_num][prop_name] = numeric_value
                    print(f"[DEBUG]   ✓ Stored: stages['{stage_num}']['{prop_name}'] = {numeric_value}")

                except ValueError as e:
                    print(f"[WARNING] Invalid value for {material_name}.{prop_name}: '{value}' - Error: {e}")
                    self.show_notification(f"Invalid value for {prop_name}: '{value}'", "warning", 3000)
                    continue

            if stages:
                result[material_name] = stages
                print(f"[DEBUG] ✓ Added {material_name} with {len(stages)} stages")

                import json
                print(f"[DEBUG] Final structure for {material_name}:")
                print(f"[DEBUG] {json.dumps(stages, indent=4)}")

        print(f"[DEBUG] ===== Collected material properties from {len(result)} materials =====")
        if result:
            import json
            print(f"[DEBUG] Complete result structure:")
            print(f"[DEBUG] {json.dumps(result, indent=2)}")

        return result

    def _load_material_properties_into_ui(self, material_props: Dict):
        """Load saved material properties into the UI entries"""
        for material_name, stages in material_props.items():
            if material_name not in self.material_properties_entries:
                print(f"[DEBUG] Material {material_name} not found in UI, skipping")
                continue

            entries = self.material_properties_entries[material_name]

            for stage_num, properties in stages.items():
                for prop_name, prop_value in properties.items():
                    entry_key = f"stage_{stage_num}_{prop_name}"

                    if entry_key in entries:
                        entry = entries[entry_key]
                        entry.delete(0, "end")

                        if prop_value is None:
                            entry.insert(0, "null")
                            print(f"[DEBUG] Set {material_name}.{entry_key} = null")
                        else:
                            entry.insert(0, str(prop_value))
                            print(f"[DEBUG] Set {material_name}.{entry_key} = {prop_value}")
                    else:
                        print(f"[DEBUG] Entry {entry_key} not found for {material_name}")

    def save_project(self):

        print(f"[DEBUG] save_project called")
        """Save current project to file"""
        if not self.project_data["cars"]:
            self.show_notification("No cars in project to save", "warning")
            return

        mod_name = ""
        if self.mod_name_entry_sidebar:
            mod_name = self.get_real_value(self.mod_name_entry_sidebar, "Enter mod name...").strip()

        author = ""
        if self.author_entry_sidebar:
            author = self.get_real_value(self.author_entry_sidebar, "Your name...").strip()

        self.project_data["mod_name"] = mod_name
        self.project_data["author"] = author if author else "Unknown"

        filename = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".bsproject",
            filetypes=[("BeamSkin Project", "*.bsproject"), ("All files", "*.*")],
            initialfile=f"{mod_name}.bsproject" if mod_name else "project.bsproject"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.project_data, f, indent=2)
                print(f"[DEBUG] Project saved to: {filename}")
                self.show_notification("Project saved successfully", "success")
            except Exception as e:
                print(f"[DEBUG] Error saving project: {e}")
                self.show_notification(f"Error saving project: {str(e)}", "error")

    def load_project(self):

        print(f"[DEBUG] load_project called")
        """Load project from file"""
        filename = filedialog.askopenfilename(
            title="Load Project",
            filetypes=[("BeamSkin Project", "*.bsproject"), ("All files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'r') as f:
                    loaded_data = json.load(f)

                if "cars" not in loaded_data:
                    self.show_notification("Invalid project file", "error")
                    return

                self.project_data = loaded_data
                self.selected_car_for_skin = None

                self.editing_mode = False
                self.selected_skin_index = None

                self._update_button_ui()

                self._reset_skin_form_fields()

                if "mod_name" in loaded_data and self.mod_name_entry_sidebar:
                    self.mod_name_entry_sidebar.delete(0, "end")
                    self.mod_name_entry_sidebar.insert(0, loaded_data["mod_name"])
                    self.mod_name_entry_sidebar.configure(text_color=state.colors["text"])

                if "author" in loaded_data and self.author_entry_sidebar:
                    self.author_entry_sidebar.delete(0, "end")
                    self.author_entry_sidebar.insert(0, loaded_data["author"])
                    self.author_entry_sidebar.configure(text_color=state.colors["text"])
                
                # Hide the add skin section if loaded project has no cars
                if not loaded_data.get("cars"):
                    if self.add_skin_section_label:
                        self.add_skin_section_label.pack_forget()
                    if self.add_skin_section_card:
                        self.add_skin_section_card.pack_forget()

                print(f"[DEBUG] Project loaded from: {filename}")
                self.show_notification(f"Loaded project with {len(loaded_data['cars'])} cars", "success")

                self.refresh_project_display()

            except Exception as e:
                print(f"[DEBUG] Error loading project: {e}")
                self.show_notification(f"Error loading project: {str(e)}", "error")

    def clear_project(self):

        print(f"[DEBUG] clear_project called")
        """Clear the current project"""
        if not self.project_data["cars"]:
            self.show_notification("Project is already empty", "info")
            return

        from gui.components.dialogs import show_confirmation_dialog

        confirmed = show_confirmation_dialog(
            self.winfo_toplevel(),
            "Clear Project",
            "Are you sure you want to clear the project?\nAll unsaved changes will be lost."
        )

        if confirmed:

            self.project_data["cars"] = {}
            self.selected_car_for_skin = None

            self.editing_mode = False
            self.selected_skin_index = None

            self._update_button_ui()

            self._reset_skin_form_fields()
            
            # Hide the add skin section when no cars exist
            if self.add_skin_section_label:
                self.add_skin_section_label.pack_forget()
            if self.add_skin_section_card:
                self.add_skin_section_card.pack_forget()

            if self.mod_name_entry_sidebar:
                self.mod_name_entry_sidebar.delete(0, "end")
                self.mod_name_entry_sidebar.insert(0, "Enter mod name...")
                self.mod_name_entry_sidebar.configure(text_color="#888888")
                print(f"[DEBUG] Cleared mod name entry and restored placeholder")

            if self.author_entry_sidebar:
                self.author_entry_sidebar.delete(0, "end")
                self.author_entry_sidebar.insert(0, "Your name...")
                self.author_entry_sidebar.configure(text_color="#888888")
                print(f"[DEBUG] Cleared author entry and restored placeholder")

            self.show_notification("Project cleared", "info")
            self.refresh_project_display()

    def refresh_project_display(self):

        print(f"[DEBUG] refresh_project_display called")
        """Refresh the project overview display with 2-column grid layout"""
        print(f"[DEBUG] ========== REFRESH PROJECT DISPLAY ==========")
        print(f"[DEBUG] Cars in project: {len(self.project_data['cars'])}")

        for widget in self.project_overview_frame.winfo_children():
            widget.destroy()

        if not self.project_data["cars"]:
            empty_label = ctk.CTkLabel(
                self.project_overview_frame,
                text="No cars in project. Add cars from the sidebar →",
                font=ctk.CTkFont(size=13),
                text_color=state.colors["text_secondary"]
            )
            empty_label.pack(pady=40)
            self.update_current_car_label()
            print(f"[DEBUG] ========== REFRESH COMPLETE (EMPTY) ==========\n")
            return

        search_query = self.project_search_var.get().lower().strip()
        if search_query == "🔍 search cars...":
            search_query = ""

        filtered_cars = {}
        for car_instance_id, car_info in self.project_data["cars"].items():
            base_carid = car_info.get("base_carid", car_instance_id)

            car_name = state.vehicle_ids.get(base_carid, base_carid)
            for cid, cname in self.car_id_list:
                if cid == base_carid:
                    car_name = cname
                    break

            if not search_query or search_query in car_name.lower() or search_query in base_carid.lower():
                filtered_cars[car_instance_id] = car_info

        print(f"[DEBUG] Filtered cars: {len(filtered_cars)} (search: '{search_query}')")

        if not filtered_cars:
            no_results_label = ctk.CTkLabel(
                self.project_overview_frame,
                text=f"No cars match '{search_query}'",
                font=ctk.CTkFont(size=13),
                text_color=state.colors["text_secondary"]
            )
            no_results_label.pack(pady=40)
            self.update_current_car_label()
            print(f"[DEBUG] ========== REFRESH COMPLETE (NO RESULTS) ==========\n")
            return

        if not hasattr(self, 'expanded_car_id'):
            self.expanded_car_id = None

        for idx, (car_instance_id, car_info) in enumerate(filtered_cars.items()):
            base_carid = car_info.get("base_carid", car_instance_id)

            car_name = state.vehicle_ids.get(base_carid, base_carid)
            for cid, cname in self.car_id_list:
                if cid == base_carid:
                    car_name = cname
                    break

            print(f"[DEBUG]   - {car_instance_id}: {car_name} ({len(car_info['skins'])} skins)")

            is_selected = (car_instance_id == self.selected_car_for_skin)
            is_expanded = (car_instance_id == self.expanded_car_id)

            car_container = ctk.CTkFrame(self.project_overview_frame, fg_color="transparent", corner_radius=8)
            car_container.pack(fill="x", pady=2, padx=0)

            display_text = f"{car_name}"
            if "_" in car_instance_id and car_instance_id != base_carid:
                instance_num = car_instance_id.split("_")[-1]
                display_text = f"{car_name} (Instance #{instance_num})"

            display_text += f"  •  {len(car_info['skins'])} skins"

            car_button = ctk.CTkButton(
                car_container,
                text=display_text,
                fg_color=state.colors["accent"] if is_selected else state.colors["card_bg"],
                hover_color=state.colors["accent_hover"] if is_selected else state.colors["card_hover"],
                height=38,
                corner_radius=8,
                text_color=state.colors["accent_text"] if is_selected else state.colors["text"],
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda cid=car_instance_id: self._toggle_car_expansion(cid)
            )
            car_button.pack(fill="x")

            remove_btn = ctk.CTkButton(
                car_button,
                text="✕",
                width=28,
                height=28,
                fg_color=state.colors["error"],
                hover_color=state.colors["error_hover"],
                text_color="white",
                font=ctk.CTkFont(size=12, weight="bold"),
                corner_radius=6,
                command=lambda c=car_instance_id: self.remove_car_from_project(c)
            )
            remove_btn.place(relx=1.0, rely=0.5, anchor="e", x=-8)

            if is_expanded and car_info["skins"]:
                skins_container = ctk.CTkFrame(
                    car_container,
                    fg_color=state.colors["app_bg"],
                    corner_radius=6
                )
                skins_container.pack(fill="x", padx=5, pady=(5, 0))

                skins_header = ctk.CTkLabel(
                    skins_container,
                    text="Skins:",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=state.colors["text_secondary"],
                    anchor="w"
                )
                skins_header.pack(anchor="w", padx=6, pady=(4, 3))

                print(f"[DEBUG]     Rendering {len(car_info['skins'])} skins for {car_instance_id}...")
                for skin_idx, skin in enumerate(car_info["skins"]):
                    print(f"[DEBUG]       Creating skin row {skin_idx + 1}: {skin['name']}")

                    is_editing_this_skin = (
                        self.editing_mode and
                        self.selected_skin_index == skin_idx and
                        self.selected_car_for_skin == car_instance_id
                    )

                    row_color = state.colors["accent"] if is_editing_this_skin else state.colors["app_bg"]

                    has_config = "config_data" in skin

                    row_height = 75 if has_config else 38

                    skin_row = ctk.CTkFrame(
                        skins_container,
                        fg_color=state.colors["card_bg"] if not is_editing_this_skin else state.colors["accent"],
                        corner_radius=6,
                        height=row_height,
                        cursor="hand2"
                    )
                    skin_row.pack(fill="x", padx=6, pady=3)
                    skin_row.pack_propagate(False)

                    def edit_skin_handler(cid=car_instance_id, idx=skin_idx):
                        self.select_skin_for_editing(cid, idx)

                    skin_row.bind("<Button-1>", lambda e, cid=car_instance_id, idx=skin_idx: edit_skin_handler(cid, idx))

                    icon_label = ctk.CTkLabel(
                        skin_row,
                        text="✏️" if is_editing_this_skin else "🎨",
                        font=ctk.CTkFont(size=14),
                        cursor="hand2"
                    )
                    icon_label.pack(side="left", padx=(8, 6), anchor="n", pady=8)
                    icon_label.bind("<Button-1>", lambda e, cid=car_instance_id, idx=skin_idx: edit_skin_handler(cid, idx))

                    text_container = ctk.CTkFrame(skin_row, fg_color="transparent")
                    text_container.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=4)
                    text_container.bind("<Button-1>", lambda e, cid=car_instance_id, idx=skin_idx: edit_skin_handler(cid, idx))

                    skin_name_label = ctk.CTkLabel(
                        text_container,
                        text=f"{skin_idx + 1}. {skin['name']}",
                        text_color=state.colors["accent_text"] if is_editing_this_skin else state.colors["text"],
                        anchor="w",
                        font=ctk.CTkFont(size=12, weight="bold"),
                        cursor="hand2"
                    )
                    skin_name_label.pack(anchor="w", fill="x")
                    skin_name_label.bind("<Button-1>", lambda e, cid=car_instance_id, idx=skin_idx: edit_skin_handler(cid, idx))

                    if has_config:
                        config_data = skin["config_data"]
                        config_type = config_data.get('config_type', 'Unknown')
                        config_name = config_data.get('config_name', 'Unknown')
                        print(f"[DEBUG]       Config data: Type='{config_type}', Name='{config_name}'")

                        config_type_label = ctk.CTkLabel(
                            text_container,
                            text=f"Config Type: {config_type}",
                            text_color=state.colors["accent_text"] if is_editing_this_skin else state.colors["text_secondary"],
                            anchor="w",
                            font=ctk.CTkFont(size=10),
                            cursor="hand2"
                        )
                        config_type_label.pack(anchor="w", fill="x")
                        config_type_label.bind("<Button-1>", lambda e, cid=car_instance_id, idx=skin_idx: edit_skin_handler(cid, idx))

                        config_name_label = ctk.CTkLabel(
                            text_container,
                            text=f"Config Name: {config_name}",
                            text_color=state.colors["accent_text"] if is_editing_this_skin else state.colors["text_secondary"],
                            anchor="w",
                            font=ctk.CTkFont(size=10),
                            cursor="hand2"
                        )
                        config_name_label.pack(anchor="w", fill="x")
                        config_name_label.bind("<Button-1>", lambda e, cid=car_instance_id, idx=skin_idx: edit_skin_handler(cid, idx))

                    buttons_frame = ctk.CTkFrame(skin_row, fg_color="transparent")
                    buttons_frame.pack(side="right", padx=6, anchor="n", pady=4)

                    remove_skin_btn = ctk.CTkButton(
                        buttons_frame,
                        text="✕",
                        width=28,
                        height=28,
                        fg_color=state.colors["error"],
                        hover_color=state.colors["error_hover"],
                        text_color="white",
                        font=ctk.CTkFont(size=13, weight="bold"),
                        corner_radius=6,
                        command=lambda c=car_instance_id, i=skin_idx: self.remove_skin_from_car(c, i)
                    )
                    remove_skin_btn.pack(side="left", padx=2)
                    print(f"[DEBUG]       Skin row {skin_idx + 1} packed successfully")

                print(f"[DEBUG]     Finished rendering all {len(car_info['skins'])} skins")

                skins_container.update()

            car_container.update()

        self.update_current_car_label()

        if self.project_overview_frame:
            self.project_overview_frame.update()

        if self.project_overview_container:
            self.project_overview_container.update()

        self.after(1, self._force_scrollable_reflow)

        print(f"[DEBUG] ========== REFRESH COMPLETE (SUCCESS - {len(filtered_cars)} cars displayed) ==========\n")

    def update_current_car_label(self):

        print(f"[DEBUG] update_current_car_label called")
        """Update the label showing which car is selected - DISABLED"""

        pass

    def generate_mod(self, generate_button_topbar, output_mode_var, custom_output_var):

        print(f"[DEBUG] generate_mod called")
        """Generate the mod with all cars and skins"""
        print("[DEBUG] \n" + "="*50)
        print("[DEBUG] MULTI-SKIN MOD GENERATION INITIATED")
        print("[DEBUG] ="*50)

        mod_name = ""
        author_name = ""
        if self.mod_name_entry_sidebar:
            mod_name = self.get_real_value(self.mod_name_entry_sidebar, "Enter mod name...").strip()
        if self.author_entry_sidebar:
            author_name = self.get_real_value(self.author_entry_sidebar, "Your name...").strip()

        if not mod_name:
            self.show_notification("Please enter a ZIP name", "error")
            return

        if not self.project_data["cars"]:
            self.show_notification("Please add at least one car to the project", "error")
            return

        cars_without_skins = []
        for carid, car_info in self.project_data["cars"].items():
            if not car_info["skins"]:
                cars_without_skins.append(carid)

        if cars_without_skins:
            self.show_notification(f"Please add skins to: {', '.join(cars_without_skins)}", "error", 4000)
            return

        missing_files = []
        for carid, car_info in self.project_data["cars"].items():
            for skin in car_info["skins"]:
                if "config_data" in skin:
                    config_data = skin["config_data"]
                    skin_name = skin.get("name", "Unknown")

                    pc_path = config_data.get("pc_file_path")
                    if pc_path and not os.path.exists(pc_path):
                        missing_files.append(f"'{skin_name}' - .pc file: {os.path.basename(pc_path)}")

                    jpg_path = config_data.get("jpg_file_path")
                    if jpg_path and not os.path.exists(jpg_path):
                        missing_files.append(f"'{skin_name}' - .jpg file: {os.path.basename(jpg_path)}")

        if missing_files:
            error_msg = "Missing config files:\n" + "\n".join(missing_files[:5])
            if len(missing_files) > 5:
                error_msg += f"\n... and {len(missing_files) - 5} more"
            self.show_notification(error_msg, "error", 6000)
            print(f"[ERROR] Missing config files:")
            for missing in missing_files:
                print(f"  - {missing}")
            return

        output_mode = output_mode_var.get()

        if output_mode == "custom":

            output_path = custom_output_var.get()
            if not output_path:
                self.show_notification("Please select a custom output location", "error")
                return
            print(f"[DEBUG] Output mode: Custom - {output_path}")
        elif output_mode == "steam":

            try:
                from core.settings import get_mods_folder_path
                output_path = get_mods_folder_path()

                if not output_path:
                    self.show_notification("Mods folder not configured. Please set it in Settings.", "error", 4000)
                    return

                if not os.path.exists(output_path):
                    self.show_notification(f"Mods folder does not exist: {output_path}", "error", 4000)
                    return

                print(f"[DEBUG] Output mode: Steam - {output_path}")
            except ImportError:
                self.show_notification("Could not load settings. Please configure mods folder path.", "error", 4000)
                return
        else:

            output_path = None
            print(f"[DEBUG] Output mode: Default/Unknown")

        self.project_data["mod_name"] = mod_name
        self.project_data["author"] = author_name if author_name else "Unknown"

        print(f"[DEBUG] Mod Name: {mod_name}")
        print(f"[DEBUG] Author: {self.project_data['author']}")
        print(f"[DEBUG] Cars: {len(self.project_data['cars'])}")
        total_skins = sum(len(car_info['skins']) for car_info in self.project_data['cars'].values())
        print(f"[DEBUG] Total Skins: {total_skins}")

        self.export_status_label.configure(text="Preparing to export...")
        self.export_status_label.pack(padx=20, pady=(10, 5))
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 5))
        self.progress_bar.set(0)
        generate_button_topbar.configure(state="disabled")

        def update_status(message):

            print(f"[DEBUG] update_status called")
            self.export_status_label.configure(text=message)

        def update_progress(value):

            print(f"[DEBUG] update_progress called")
            if self.progress_bar.winfo_ismapped():
                self.progress_bar.set(value)

        def thread_fn():

            print(f"[DEBUG] thread_fn called")
            try:
                print("[DEBUG] \nStarting mod generation thread...")
                update_status("Processing skins...")

                def progress_with_status(value):

                    print(f"[DEBUG] progress_with_status called")
                    update_progress(value)
                    if value < 0.3:
                        update_status("Copying template files...")
                    elif value < 0.7:
                        update_status(f"Processing {total_skins} skins...")
                    else:
                        update_status("Creating ZIP archive...")

                if generate_multi_skin_mod:
                    generate_multi_skin_mod(
                        self.project_data,
                        output_path=output_path,
                        progress_callback=progress_with_status
                    )

                    update_status("Export completed successfully!")
                    print("[DEBUG] Mod generation completed successfully!")
                    print("[DEBUG] ="*50 + "\n")
                    self.show_notification(f"✓ Mod '{mod_name}' created with {total_skins} skins!", "success", 5000)

                    self.after(2000, lambda: self.show_notification("Project kept. Click 'Clear Project' to start new one.", "info", 4000))
                else:
                    update_status("Error: Generation function not available")
                    self.show_notification("Error: generate_multi_skin_mod function not found", "error", 5000)

            except FileExistsError as e:
                update_status("Error: File already exists")
                print(f"[DEBUG] ERROR: File already exists - {e}")
                self.show_notification(f"File already exists: {str(e)}", "error", 5000)
            except Exception as e:
                update_status("Error: Export failed")
                print(f"[DEBUG] ERROR: {e}")
                import traceback
                traceback.print_exc()
                self.show_notification(f"Error: {str(e)}", "error", 5000)
            finally:
                self.progress_bar.set(0)
                generate_button_topbar.configure(state="normal")
                self.after(2000, lambda: self.progress_bar.pack_forget())
                self.after(2000, lambda: self.export_status_label.pack_forget())

        threading.Thread(target=thread_fn, daemon=True).start()