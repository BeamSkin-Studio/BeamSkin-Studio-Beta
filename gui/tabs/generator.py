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
        
        # Callback for notifications (passed from main window)
        self.show_notification = notification_callback or self._fallback_notification
        
        # Get references we need from state/sidebar
        self.mod_name_entry_sidebar = None  # Will be set by main window
        self.author_entry_sidebar = None    # Will be set by main window
        
        # UI Element references
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
        
        # Variables
        self.skin_name_var = ctk.StringVar()
        self.dds_path_var = ctk.StringVar()
        self.project_search_var = ctk.StringVar()
        
        # Config data variables
        self.add_config_data_var = ctk.BooleanVar(value=False)
        self.config_type_var = ctk.StringVar(value="Factory")
        self.config_name_var = ctk.StringVar()
        self.pc_file_path_var = ctk.StringVar()
        self.jpg_file_path_var = ctk.StringVar()
        
        # Load config types from file
        try:
            from utils.config_helper import load_config_types
            self.config_types = load_config_types()
        except ImportError:
            self.config_types = ["Factory", "Custom", "Police"]
            print("[DEBUG] Using default config types")
        
        # Project data structure
        self.project_data = {
            "mod_name": "",
            "author": "",
            "cars": {}
        }
        
        # Selected car for adding skins
        self.selected_car_for_skin: Optional[str] = None
        
        # Car ID list
        self.car_id_list = self._build_car_id_list()
        
        # Setup UI
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
        
        # Reload from JSON file to get latest vehicles
        vehicles = load_added_vehicles_json()
        state.added_vehicles.clear()
        state.added_vehicles.update(vehicles)
        
        # Add all built-in vehicles
        for carid, carname in state.vehicle_ids.items():
            # Skip if it's a custom vehicle (will be added from added_vehicles)
            if carid not in state.added_vehicles:
                car_list.append((carid, carname))
        
        # Add custom vehicles
        for carid, carname in state.added_vehicles.items():
            car_list.append((carid, carname))
        
        # Sort alphabetically by car name (case-insensitive)
        return sorted(car_list, key=lambda x: x[1].lower())
    
    def refresh_vehicle_list(self):
        """Refresh the vehicle list when new vehicles are added"""
        print(f"[DEBUG] refresh_vehicle_list called")
        print(f"[DEBUG] Rebuilding car ID list from added_vehicles.json...")
        
        # Rebuild the car list (this will reload from JSON)
        self.car_id_list = self._build_car_id_list()
        
        print(f"[DEBUG] Car list now has {len(self.car_id_list)} vehicles")
        print(f"[DEBUG] Custom vehicles in state: {len(state.added_vehicles)}")
        
        # Refresh the project display to update any car names
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
        self.generator_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.generator_scroll.pack(fill="both", expand=True, padx=0, pady=0)
        
        section_header = ctk.CTkFrame(self.generator_scroll, fg_color="transparent", height=60)
        section_header.pack(fill="x", padx=20, pady=(15, 10))
        section_header.pack_propagate(False)
        
        ctk.CTkLabel(
            section_header,
            text="Project Overview",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left", anchor="w")
        
        project_controls = ctk.CTkFrame(section_header, fg_color="transparent")
        project_controls.pack(side="right")
        
        self._create_button(project_controls, "💾 Save Project", self.save_project, "primary", 130, 32).pack(side="left", padx=3)
        self._create_button(project_controls, "📂 Load Project", self.load_project, "primary", 130, 32).pack(side="left", padx=3)
        self._create_button(project_controls, "Clear", self.clear_project, "danger", 100, 32).pack(side="left", padx=3)
        
        ctk.CTkLabel(
            self.generator_scroll,
            text="Vehicles in project",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        project_search_frame = ctk.CTkFrame(self.generator_scroll, fg_color="transparent")
        project_search_frame.pack(fill="x", padx=10, pady=(0, 5))
        
        self.project_search_entry = ctk.CTkEntry(
            project_search_frame,
            textvariable=self.project_search_var,
            height=32,
            corner_radius=8,
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            text_color="#888888"
        )
        self.project_search_entry.pack(fill="x")
        self._setup_placeholder(self.project_search_entry, "🔍 Search cars...")
        
        self.project_overview_container = ctk.CTkScrollableFrame(
            self.generator_scroll,
            corner_radius=12,
            fg_color=state.colors["frame_bg"]
        )
        self.project_overview_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.project_overview_frame = ctk.CTkFrame(self.project_overview_container, fg_color="transparent")
        self.project_overview_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.current_car_label = ctk.CTkLabel(
            self.generator_scroll,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["accent"]
        )
        
        ctk.CTkLabel(
            self.generator_scroll,
            text="Add Skins to Selected Car",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=20, pady=(20, 10))
        
        skin_card = self._create_card(self.generator_scroll)
        skin_card.pack(fill="x", padx=20, pady=(0, 15))
        
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
        
        # Configuration Name field - positioned between Skin Name and Config Type on same row
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
        
# Configuration files section - .pc and .jpg side by side
        self.config_files_container = ctk.CTkFrame(skin_card, fg_color="transparent")
        
        # Single row for both files
        config_files_row = ctk.CTkFrame(self.config_files_container, fg_color="transparent")
        config_files_row.pack(fill="x", padx=15, pady=(0, 10))
        
        # Left side - .pc file
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
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8
        )
        pc_browse_btn.pack(side="right")
        
        # Right side - .jpg file
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
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8
        )
        jpg_browse_btn.pack(side="right")
        
        self.dds_texture_label = ctk.CTkLabel(
            skin_card,
            text="DDS Texture",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=state.colors["text"]
        )
        self.dds_texture_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        dds_row = ctk.CTkFrame(skin_card, fg_color="transparent")
        dds_row.pack(fill="x", padx=15, pady=(0, 10))
        
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
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8
        )
        dds_browse.pack(side="right")
        
        self.dds_preview_label = ctk.CTkLabel(
            skin_card,
            text="",
            image=None,
            width=600,
            height=300
        )
        self.dds_preview_label.pack(padx=15, pady=(10, 10))
        
        add_skin_btn = ctk.CTkButton(
            skin_card,
            text="➕ Add Skin",
            command=self.add_skin_to_selected_car,
            height=40,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8
        )
        add_skin_btn.pack(fill="x", padx=15, pady=(5, 15))
        
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
            self.selected_car_for_skin = carid
            self.refresh_project_display()
            return
        
        for car_id in self.project_data["cars"].keys():
            if car_id.startswith(f"{carid}_"):
                self.show_notification(f"{display_name} is already in the project", "warning")
                self.selected_car_for_skin = carid if carid in self.project_data["cars"] else car_id
                self.refresh_project_display()
                return
        
        self.project_data["cars"][carid] = {
            "base_carid": carid,
            "skins": [],
            "temp_skin_name": "",
            "temp_dds_path": ""
        }
        
        self.selected_car_for_skin = carid
        self.show_notification(f"Added {display_name} to project", "success")
        
        print(f"[DEBUG] Selected car for skins: {self.selected_car_for_skin}")
        
        self.refresh_project_display()
    
    def remove_car_from_project(self, car_instance_id: str):
    
        print(f"[DEBUG] remove_car_from_project called")
        """Remove a car instance from the project"""
        if car_instance_id in self.project_data["cars"]:
            base_carid = self.project_data["cars"][car_instance_id].get("base_carid", car_instance_id)
            del self.project_data["cars"][car_instance_id]
            
            if self.selected_car_for_skin == car_instance_id:
                self.selected_car_for_skin = None
            
            car_name = state.vehicle_ids.get(base_carid, base_carid)
            self.show_notification(f"Removed {car_name}", "info")
            
            self.refresh_project_display()
    
    def select_car_for_skin(self, car_instance_id: str):
    
        print(f"[DEBUG] select_car_for_skin called")
        """Select a car to add skins to"""
        if car_instance_id in self.project_data["cars"]:
            self.selected_car_for_skin = car_instance_id
            print(f"[DEBUG] Selected car for adding skins: {car_instance_id}")
            self.refresh_project_display()
    
    def add_skin_to_selected_car(self):
    
        print(f"[DEBUG] add_skin_to_selected_car called")
        """Add a skin to the currently selected car"""
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
            
            if not config_name or config_name == "Enter configuration name...":
                self.show_notification("Please enter a configuration name", "warning")
                return
            
            if not pc_path or pc_path == "No .pc file selected...":
                self.show_notification("Please select a .pc file for config data", "warning")
                return
            
            if not jpg_path or jpg_path == "No .jpg file selected...":
                self.show_notification("Please select a .jpg file for config data", "warning")
                return
            
            if not os.path.exists(pc_path):
                self.show_notification(".pc file does not exist", "error")
                return
            
            if not os.path.exists(jpg_path):
                self.show_notification(".jpg file does not exist", "error")
                return
            
            skin_data["config_data"] = {
                "config_type": config_type,
                "config_name": config_name,
                "pc_path": pc_path,
                "jpg_path": jpg_path
            }
            print(f"[DEBUG] Adding skin with config data: Type={config_type}, Name={config_name}")
        
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
                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
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
            # Show config name label and field (between skin name and config type)
            self.config_name_label.pack(side="left", padx=(0, 8), after=self.skin_name_entry)
            self.config_name_entry.pack(side="left", padx=(0, 10), after=self.config_name_label)
            
            # Show config type dropdown (after config name)
            self.config_type_entry_row.pack(side="left")
            
            # Show config files container (.pc and .jpg files)
            self.config_files_container.pack(fill="x", pady=(0, 10), before=self.dds_texture_label)
            
            print("[DEBUG] Config data section shown")
        else:
            # Hide all config sections
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
            print(f"[DEBUG] Selected .pc file: {filename}")
    
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
            print(f"[DEBUG] Selected .jpg file: {filename}")
    
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
                
                if "mod_name" in loaded_data and self.mod_name_entry_sidebar:
                    self.mod_name_entry_sidebar.delete(0, "end")
                    self.mod_name_entry_sidebar.insert(0, loaded_data["mod_name"])
                    self.mod_name_entry_sidebar.configure(text_color=state.colors["text"])
                
                if "author" in loaded_data and self.author_entry_sidebar:
                    self.author_entry_sidebar.delete(0, "end")
                    self.author_entry_sidebar.insert(0, loaded_data["author"])
                    self.author_entry_sidebar.configure(text_color=state.colors["text"])
                
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
            # Clear project cars
            self.project_data["cars"] = {}
            self.selected_car_for_skin = None
            
            # Clear and restore placeholder for mod name entry in sidebar
            if self.mod_name_entry_sidebar:
                self.mod_name_entry_sidebar.delete(0, "end")
                self.mod_name_entry_sidebar.insert(0, "Enter mod name...")
                self.mod_name_entry_sidebar.configure(text_color="#888888")
                print(f"[DEBUG] Cleared mod name entry and restored placeholder")
            
            # Clear and restore placeholder for author entry in sidebar
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
        
        current_row = None
        for idx, (car_instance_id, car_info) in enumerate(filtered_cars.items()):
            base_carid = car_info.get("base_carid", car_instance_id)
            
            car_name = state.vehicle_ids.get(base_carid, base_carid)
            for cid, cname in self.car_id_list:
                if cid == base_carid:
                    car_name = cname
                    break
            
            print(f"[DEBUG]   - {car_instance_id}: {car_name} ({len(car_info['skins'])} skins)")
            
            if idx % 2 == 0:
                current_row = ctk.CTkFrame(self.project_overview_frame, fg_color="transparent")
                current_row.pack(fill="x", pady=4, padx=4)
            
            is_selected = (car_instance_id == self.selected_car_for_skin)
            
            car_card = ctk.CTkFrame(
                current_row,
                fg_color=state.colors["accent"] if is_selected else state.colors["card_bg"],
                corner_radius=10,
                border_width=2,
                border_color=state.colors["accent"] if is_selected else state.colors["border"]
            )
            car_card.pack(side="left", fill="both", expand=True, padx=4)
            
            def select_handler(cid=car_instance_id):
            
                print(f"[DEBUG] select_handler called")
                self.select_car_for_skin(cid)
            
            car_card.bind("<Button-1>", lambda e, cid=car_instance_id: select_handler(cid))
            
            header_row = ctk.CTkFrame(car_card, fg_color="transparent")
            header_row.pack(fill="x", padx=10, pady=(10, 5))
            
            display_text = f"{car_name}"
            if "_" in car_instance_id and car_instance_id != base_carid:
                instance_num = car_instance_id.split("_")[-1]
                display_text = f"{car_name} (Instance #{instance_num})"
            
            car_label = ctk.CTkLabel(
                header_row,
                text=display_text,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=state.colors["accent_text"] if is_selected else state.colors["text"],
                anchor="w"
            )
            car_label.pack(side="left", fill="x", expand=True)
            car_label.bind("<Button-1>", lambda e, cid=car_instance_id: select_handler(cid))
            
            remove_btn = ctk.CTkButton(
                header_row,
                text="✕",
                width=28,
                height=28,
                fg_color=state.colors["error"],
                hover_color=state.colors["error_hover"],
                text_color="white",
                font=ctk.CTkFont(size=13, weight="bold"),
                corner_radius=6,
                command=lambda c=car_instance_id: self.remove_car_from_project(c)
            )
            remove_btn.pack(side="right")
            
            skin_count_label = ctk.CTkLabel(
                car_card,
                text=f"🎨 {len(car_info['skins'])} skins",
                font=ctk.CTkFont(size=12),
                text_color=state.colors["accent_text"] if is_selected else state.colors["text_secondary"],
                anchor="w"
            )
            skin_count_label.pack(anchor="w", padx=10, pady=(0, 5))
            skin_count_label.bind("<Button-1>", lambda e, cid=car_instance_id: select_handler(cid))
            
            if car_info["skins"]:
                skins_container = ctk.CTkFrame(
                    car_card,
                    fg_color=state.colors["app_bg"],
                    corner_radius=8
                )
                skins_container.pack(fill="x", padx=8, pady=(5, 10))
                skins_container.bind("<Button-1>", lambda e, cid=car_instance_id: select_handler(cid))
                
                skins_header = ctk.CTkLabel(
                    skins_container,
                    text="Skins:",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=state.colors["text_secondary"],
                    anchor="w"
                )
                skins_header.pack(anchor="w", padx=8, pady=(6, 4))
                
                print(f"[DEBUG]     Rendering {len(car_info['skins'])} skins for {car_instance_id}...")
                for skin_idx, skin in enumerate(car_info["skins"]):
                    print(f"[DEBUG]       Creating skin row {skin_idx + 1}: {skin['name']}")
                    row_color = state.colors["app_bg"]
                    
                    # Check if skin has config data
                    has_config = "config_data" in skin
                    
                    skin_row = ctk.CTkFrame(
                        skins_container,
                        fg_color=row_color,
                        corner_radius=6,
                        height=36
                    )
                    skin_row.pack(fill="x", padx=4, pady=2)
                    skin_row.pack_propagate(False)
                    
                    # Left side: icon
                    icon_label = ctk.CTkLabel(
                        skin_row,
                        text="🎨",
                        font=ctk.CTkFont(size=14)
                    )
                    icon_label.pack(side="left", padx=(8, 6))
                    
                    # Build display text with config info inline
                    display_text = f"{skin_idx + 1}. {skin['name']}"
                    
                    if has_config:
                        config_data = skin["config_data"]
                        config_type = config_data.get('config_type', 'Unknown')
                        config_name = config_data.get('config_name', 'Unknown')
                        print(f"[DEBUG]       Config data: Type='{config_type}', Name='{config_name}'")
                        display_text += f"  |  Type: {config_type}  |  Config Name: {config_name}"
                    
                    skin_label = ctk.CTkLabel(
                        skin_row,
                        text=display_text,
                        text_color=state.colors["text"],
                        anchor="w",
                        font=ctk.CTkFont(size=13, weight="bold")
                    )
                    skin_label.pack(side="left", fill="x", expand=True, padx=(0, 8))
                    
                    # Right side: remove button
                    remove_skin_btn = ctk.CTkButton(
                        skin_row,
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
                    remove_skin_btn.pack(side="right", padx=6)
                    print(f"[DEBUG]       Skin row {skin_idx + 1} packed successfully")
                
                print(f"[DEBUG]     Finished rendering all {len(car_info['skins'])} skins")
                
                skins_container.update()
            
            car_card.update()
        
        self.update_current_car_label()
        
        if self.project_overview_frame:
            self.project_overview_frame.update()
        
        if self.project_overview_container:
            self.project_overview_container.update()
        
        self.after(1, self._force_scrollable_reflow)
        
        print(f"[DEBUG] ========== REFRESH COMPLETE (SUCCESS - {len(filtered_cars)} cars displayed) ==========\n")
    
    def update_current_car_label(self):
    
        print(f"[DEBUG] update_current_car_label called")
        """Update the label showing which car is selected"""
        if self.selected_car_for_skin and self.selected_car_for_skin in self.project_data["cars"]:
            base_carid = self.project_data["cars"][self.selected_car_for_skin].get("base_carid", self.selected_car_for_skin)
            
            car_name = state.vehicle_ids.get(base_carid, base_carid)
            for cid, cname in self.car_id_list:
                if cid == base_carid:
                    car_name = cname
                    break
            
            display_text = f"{car_name} ({base_carid})"
            if "_" in self.selected_car_for_skin and self.selected_car_for_skin != base_carid:
                instance_num = self.selected_car_for_skin.split("_")[-1]
                display_text = f"{car_name} - Instance #{instance_num} ({base_carid})"
            
            self.current_car_label.configure(text=f"Adding Skins to: {display_text}")
            self.current_car_label.pack(anchor="w", padx=10, pady=(10, 0))
        else:
            self.current_car_label.pack_forget()
    
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
        
        # Determine output path based on output mode
        output_mode = output_mode_var.get()
        
        if output_mode == "custom":
            # Custom mode - use the custom path from sidebar
            output_path = custom_output_var.get()
            if not output_path:
                self.show_notification("Please select a custom output location", "error")
                return
            print(f"[DEBUG] Output mode: Custom - {output_path}")
        elif output_mode == "steam":
            # Steam mode - use configured mods folder from settings
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
            # Unknown mode - should not happen
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