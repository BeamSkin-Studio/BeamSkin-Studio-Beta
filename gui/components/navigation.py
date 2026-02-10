"""
Navigation Components - Sidebar and Topbar
"""
from typing import Callable, Optional
import customtkinter as ctk
from tkinter import filedialog
from gui.state import state
from gui.components.preview import HoverPreviewManager


print(f"[DEBUG] Loading class: Sidebar")


class Sidebar(ctk.CTkFrame):
    """Left sidebar with project settings and vehicle list"""
    
    def __init__(self, parent: ctk.CTk, preview_manager: HoverPreviewManager):
    
        print(f"[DEBUG] __init__ called")
        super().__init__(parent, width=280, fg_color=state.colors["sidebar_bg"], corner_radius=0)
        self.pack_propagate(False)
        self.preview_manager = preview_manager
        
        # Variables
        self.output_mode_var = ctk.StringVar(value="steam")
        self.custom_output_var = ctk.StringVar()
        self.sidebar_search_var = ctk.StringVar()
        self.sidebar_search_placeholder = "🔍 Search vehicles..."  # Placeholder text
        
        # Track expanded vehicle
        self.expanded_vehicle_carid: Optional[str] = None
        
        # UI references
        self.custom_output_frame: Optional[ctk.CTkFrame] = None
        self.sidebar_scroll: Optional[ctk.CTkScrollableFrame] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the sidebar UI"""
        # Header
        sidebar_header = ctk.CTkFrame(self, height=40, fg_color="transparent")
        sidebar_header.pack(fill="x", padx=15, pady=(10, 0))
        sidebar_header.pack_propagate(False)
        
        ctk.CTkLabel(
            sidebar_header,
            text="PROJECT SETTINGS",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(side="top", fill="x", pady=(5, 0))
        
        # ZIP Name label
        ctk.CTkLabel(
            self,
            text="ZIP Name",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(5, 5))
        
        # ZIP Name input
        self.mod_name_var = ctk.StringVar()
        self.mod_name_entry = ctk.CTkEntry(
            self,
            textvariable=self.mod_name_var,
            height=36,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        )
        self.mod_name_entry.pack(fill="x", padx=15, pady=(0, 10))
        
        self.mod_name_placeholder = "Enter mod name..."
        self.mod_name_entry.insert(0, self.mod_name_placeholder)
        self.mod_name_entry.configure(text_color="#888888")
        
        self.mod_name_entry.bind("<FocusIn>", self._on_mod_name_focus_in)
        self.mod_name_entry.bind("<FocusOut>", self._on_mod_name_focus_out)
        
        # Author label
        ctk.CTkLabel(
            self,
            text="Author",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(0, 5))
        
        # Author input
        self.author_var = ctk.StringVar()
        self.author_entry = ctk.CTkEntry(
            self,
            textvariable=self.author_var,
            height=36,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        )
        self.author_entry.pack(fill="x", padx=15, pady=(0, 15))
        
        self.author_placeholder = "Your name..."
        self.author_entry.insert(0, self.author_placeholder)
        self.author_entry.configure(text_color="#888888")
        
        self.author_entry.bind("<FocusIn>", self._on_author_focus_in)
        self.author_entry.bind("<FocusOut>", self._on_author_focus_out)
        
        # Output Location label
        ctk.CTkLabel(
            self,
            text="Output Location",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(0, 5))
        
        # Steam output option
        steam_option_sidebar = ctk.CTkFrame(self, fg_color=state.colors["frame_bg"], corner_radius=8, height=45)
        steam_option_sidebar.pack(fill="x", padx=15, pady=(0, 5))
        steam_option_sidebar.pack_propagate(False)
        
        self.steam_icon_label = ctk.CTkLabel(steam_option_sidebar, text="", image=None)
        self.steam_icon_label.pack(side="left", padx=(10, 5), pady=10)
        
        self.steam_radio_sidebar = ctk.CTkRadioButton(
            steam_option_sidebar,
            text="Steam default",
            variable=self.output_mode_var,
            value="steam",
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.steam_radio_sidebar.pack(side="left", padx=0, pady=10)
        
        # Custom output option
        custom_option_sidebar = ctk.CTkFrame(self, fg_color=state.colors["frame_bg"], corner_radius=8, height=45)
        custom_option_sidebar.pack(fill="x", padx=15, pady=(0, 5))
        custom_option_sidebar.pack_propagate(False)
        
        self.custom_icon_label = ctk.CTkLabel(custom_option_sidebar, text="", image=None)
        self.custom_icon_label.pack(side="left", padx=(10, 5), pady=10)
        
        self.custom_radio_sidebar = ctk.CTkRadioButton(
            custom_option_sidebar,
            text="Custom Location",
            variable=self.output_mode_var,
            value="custom",
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.custom_radio_sidebar.pack(side="left", padx=0, pady=10)
        
        # Store reference to custom_option_sidebar for positioning
        self.custom_option_sidebar = custom_option_sidebar
        
        # Bind output mode changes BEFORE creating custom output frame
        self.output_mode_var.trace_add("write", lambda *args: self._update_output_mode())
        
        # Custom output frame (shown/hidden based on selection)
        self.custom_output_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        custom_output_entry = ctk.CTkEntry(
            self.custom_output_frame,
            textvariable=self.custom_output_var,
            placeholder_text="Select folder...",
            placeholder_text_color="#888888",
            state="readonly",
            height=32,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=10)
        )
        custom_output_entry.pack(side="left", fill="x", expand=True, padx=(15, 5))
        
        custom_browse_btn = ctk.CTkButton(
            self.custom_output_frame,
            text="📁",
            width=32,
            height=32,
            command=self.select_custom_output,
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"],
            corner_radius=8,
            font=ctk.CTkFont(size=14)
        )
        custom_browse_btn.pack(side="right", padx=(0, 15))
        
        # Separator
        separator = ctk.CTkFrame(self, height=2, fg_color=state.colors["border"])
        separator.pack(fill="x", padx=15, pady=(10, 10))
        
        # Vehicles label
        ctk.CTkLabel(
            self,
            text="Vehicles",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(0, 5))
        
        # Vehicle search
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=(0, 8))
        
        self.sidebar_search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.sidebar_search_var,
            height=32,
            fg_color=state.colors["frame_bg"],
            border_color=state.colors["border"],
            border_width=1,
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=11),
            corner_radius=6
        )
        self.sidebar_search_entry.pack(fill="x")
        
        # Set initial placeholder
        self.sidebar_search_var.set(self.sidebar_search_placeholder)
        self.sidebar_search_entry.configure(text_color="#888888")
        
        # Bind focus events for placeholder
        self.sidebar_search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.sidebar_search_entry.bind("<FocusOut>", self._on_search_focus_out)
        
        # Bind search
        self.sidebar_search_var.trace_add("write", lambda *args: self._filter_vehicles())
        
        # Scrollable vehicle list
        self.sidebar_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=state.colors["border"],
            scrollbar_button_hover_color=state.colors["card_hover"]
        )
        self.sidebar_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))
    
    def _on_mod_name_focus_in(self, event):
        """Handle focus in for mod name entry"""
        if self.mod_name_entry.get() == self.mod_name_placeholder:
            self.mod_name_entry.delete(0, "end")
            self.mod_name_entry.configure(text_color=state.colors["text"])
    
    def _on_mod_name_focus_out(self, event):
        """Handle focus out for mod name entry"""
        if not self.mod_name_entry.get():
            self.mod_name_entry.insert(0, self.mod_name_placeholder)
            self.mod_name_entry.configure(text_color="#888888")
    
    def _on_author_focus_in(self, event):
        """Handle focus in for author entry"""
        if self.author_entry.get() == self.author_placeholder:
            self.author_entry.delete(0, "end")
            self.author_entry.configure(text_color=state.colors["text"])
    
    def _on_author_focus_out(self, event):
        """Handle focus out for author entry"""
        if not self.author_entry.get():
            self.author_entry.insert(0, self.author_placeholder)
            self.author_entry.configure(text_color="#888888")
    
    def _on_search_focus_in(self, event):
        """Handle focus in for search entry - remove placeholder"""
        if self.sidebar_search_var.get() == self.sidebar_search_placeholder:
            self.sidebar_search_var.set("")
            self.sidebar_search_entry.configure(text_color=state.colors["text"])
    
    def _on_search_focus_out(self, event):
        """Handle focus out for search entry - restore placeholder if empty"""
        if not self.sidebar_search_var.get():
            self.sidebar_search_var.set(self.sidebar_search_placeholder)
            self.sidebar_search_entry.configure(text_color="#888888")
    
    def _update_output_mode(self):
        """Update output mode visibility"""
        if self.output_mode_var.get() == "custom":
            # Pack right after custom_option_sidebar
            self.custom_output_frame.pack(fill="x", pady=(0, 10), padx=0, after=self.custom_option_sidebar)
        else:
            self.custom_output_frame.pack_forget()
    
    def _filter_vehicles(self):
        """Filter vehicle buttons based on search"""
        search_query = self.sidebar_search_var.get()
        
        # Ignore placeholder text
        if search_query == self.sidebar_search_placeholder:
            search_query = ""
        
        search_query = search_query.lower()
        
        for container, carid, display_name, add_btn_frame in state.sidebar_vehicle_buttons:
            # Check if vehicle matches search
            matches = (
                not search_query or
                search_query in display_name.lower() or
                search_query in carid.lower()
            )
            
            if matches:
                container.pack(fill="x", pady=2, padx=0)
            else:
                container.pack_forget()
    
    def _get_real_value(self, value: str, placeholder: str) -> str:
        """Get real value, ignoring placeholder"""
        return "" if value == placeholder else value
    
    def select_custom_output(self):
    
        print(f"[DEBUG] select_custom_output called")
        """Select custom output directory"""
        temp_window = ctk.CTkToplevel(self.winfo_toplevel())
        temp_window.withdraw()  # Keep it hidden
        temp_window.attributes('-alpha', 0)  # Make it completely transparent
        
        if self.custom_output_frame.winfo_ismapped():
            x = self.custom_output_frame.winfo_rootx()
            y = self.custom_output_frame.winfo_rooty() + self.custom_output_frame.winfo_height() + 10
            temp_window.geometry(f"1x1+{x}+{y}")
        
        # Update to ensure window is positioned before dialog opens
        temp_window.update()
        
        folder = filedialog.askdirectory(
            title="Select Output Directory",
            parent=temp_window
        )
        
        # Clean up temporary window
        temp_window.destroy()
        
        if folder:
            self.custom_output_var.set(folder)
            self.output_mode_var.set("custom")
            print(f"[DEBUG] Custom output directory selected: {folder}")
    
    def populate_vehicles(self, add_callback: Callable[[str, str], None]):
    
        print(f"[DEBUG] populate_vehicles called")
        """Populate sidebar with vehicle buttons
        
        Args:
            add_callback: Function that takes (carid, display_name) and adds vehicle to project
        """
        print("[DEBUG] Populating sidebar with vehicles...")
        
        # Build combined dict of ALL vehicles (built-in + custom)
        all_vehicles = {}
        
        # Add built-in vehicles (skip if already in added_vehicles to prevent duplicates)
        for carid, display_name in state.vehicle_ids.items():
            if carid not in state.added_vehicles:  # Skip custom vehicles here
                all_vehicles[carid] = display_name
        
        # Add custom vehicles
        for carid, carname in state.added_vehicles.items():
            all_vehicles[carid] = carname
        
        # Sort all vehicles by display name
        sorted_vehicles = sorted(all_vehicles.items(), key=lambda x: x[1].lower())
        
        # Add buttons for all vehicles
        for carid, display_name in sorted_vehicles:
            self._add_vehicle_button(carid, display_name, add_callback)
        
        print(f"[DEBUG] Added {len(state.sidebar_vehicle_buttons)} vehicles to sidebar")
    
    def _add_vehicle_button(self, carid: str, display_name: str, add_callback: Callable[[str, str], None]):
        """Add a single vehicle button to the sidebar
        
        Args:
            carid: Vehicle ID
            display_name: Display name for the vehicle
            add_callback: Function that takes (carid, display_name) to add vehicle
        """
        # Find insertion position (alphabetically)
        insert_position = len(state.sidebar_vehicle_buttons)
        for i, (container, cid, dname, add_btn_frame) in enumerate(state.sidebar_vehicle_buttons):
            if dname.lower() > display_name.lower():
                insert_position = i
                break
        
        # Container frame
        container_frame = ctk.CTkFrame(self.sidebar_scroll, corner_radius=8, fg_color="transparent")
        
        # Main button
        btn = ctk.CTkButton(
            container_frame,
            text=display_name,
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            height=38,
            corner_radius=8,
            text_color=state.colors["text"],
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        btn.pack(fill="x")
        
        # Add button frame (initially hidden)
        add_button_frame = ctk.CTkFrame(container_frame, fg_color="transparent")
        
        add_btn = ctk.CTkButton(
            add_button_frame,
            text="➕ Add to Project",
            command=lambda c=carid, d=display_name: add_callback(c, d),
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        add_btn.pack(fill="x")
        
        # Toggle add button on click
        btn.configure(command=lambda c=carid, frame=add_button_frame: self._toggle_vehicle_add_button(c, frame))
        
        # Hover preview - FIXED: Using correct method name
        btn.bind("<Enter>", lambda e, c=carid: self.preview_manager.schedule_hover_preview(c, btn))
        btn.bind("<Leave>", lambda e: self.preview_manager.hide_hover_preview())
        
        # Store reference
        state.sidebar_vehicle_buttons.insert(insert_position, (container_frame, carid, display_name, add_button_frame))
        
        # Repack all in order
        for widget in self.sidebar_scroll.winfo_children():
            if widget in [container for container, _, _, _ in state.sidebar_vehicle_buttons]:
                widget.pack_forget()
        
        for container, cid, dname, add_frame in state.sidebar_vehicle_buttons:
            container.pack(fill="x", pady=2, padx=0)
    
    def _toggle_vehicle_add_button(self, carid: str, add_button_frame: ctk.CTkFrame):
        """Toggle the add button for a vehicle"""
        if self.expanded_vehicle_carid == carid:
            # Collapse
            add_button_frame.pack_forget()
            self.expanded_vehicle_carid = None
        else:
            # Collapse any previously expanded
            if self.expanded_vehicle_carid is not None:
                for btn_frame, car_id, _, add_btn_frame in state.sidebar_vehicle_buttons:
                    if car_id == self.expanded_vehicle_carid:
                        add_btn_frame.pack_forget()
                        break
            
            # Expand this one
            add_button_frame.pack(fill="x", padx=5, pady=(0, 5))
            self.expanded_vehicle_carid = carid
    
    def update_icons(self, steam_icon, folder_icon):
    
        print(f"[DEBUG] update_icons called")
        """Update output icons based on current theme"""
        if steam_icon:
            self.steam_icon_label.configure(image=steam_icon)
        if folder_icon:
            self.custom_icon_label.configure(image=folder_icon)


print(f"[DEBUG] Loading class: Topbar")


class Topbar(ctk.CTkFrame):
    """Top navigation bar with menu and generate button"""
    
    def __init__(self, parent: ctk.CTk, on_view_change: Callable[[str], None], on_generate: Callable[[], None], 
                 logo_image=None):
    
        print(f"[DEBUG] __init__ called")
        # height=60 is the topbar height - reduce to 50 or 55 if logo needs less space
        super().__init__(parent, height=60, fg_color=state.colors["topbar_bg"], corner_radius=0)
        self.pack_propagate(False)
        
        self.on_view_change = on_view_change
        self.on_generate = on_generate
        self.logo_image = logo_image
        
        self.menu_buttons = {}
        
        self._setup_ui()
    


    # # # # # # # # #
    # LOGO POSITION #
    # # # # # # # # #
    def _setup_ui(self):
        """Set up the topbar UI"""
        # Logo and Title container
        logo_container = ctk.CTkFrame(self, fg_color="transparent")
        # x=20 is left/right position, y=5 is up/down
        logo_container.place(x=25, y=-35) 
        
        # Logo image (if provided)
        if self.logo_image:
            logo_label = ctk.CTkLabel(
                logo_container,
                text="",
                image=self.logo_image
            )
            logo_label.pack(side="left", padx=(0, 0))
        else:
            # Fallback to text if no logo
            title_container = ctk.CTkFrame(logo_container, fg_color="transparent")
            title_container.pack(side="left")
            
            ctk.CTkLabel(
                title_container,
                text="BeamSkin Studio",
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color=state.colors["accent"]
            ).pack(anchor="w")
            
            ctk.CTkLabel(
                title_container,
                text="Professional Skin Modding Tool",
                font=ctk.CTkFont(size=10),
                text_color=state.colors["text_secondary"]
            ).pack(anchor="w")
        
        # Menu position
        self.menu_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.menu_frame.pack(side="left", padx=(150, 40))  # (left_padding, right_padding) / 
        
        # Menu buttons
        menu_items = [
            ("Project", "generator"),
            ("How to Use", "howto"),
            ("Car List", "carlist"),
            ("Add Vehicles", "add_vehicles"),
            ("Settings", "settings"),
            ("About", "about")
        ]
        
        for btn_text, view_name in menu_items:
            is_first = (view_name == "generator")
            btn = ctk.CTkButton(
                self.menu_frame,
                text=f"   {btn_text}   ",
                width=110,
                height=36,
                fg_color=state.colors["accent"] if is_first else "transparent",
                hover_color=state.colors["accent_hover"] if is_first else state.colors["card_hover"],
                text_color=state.colors["accent_text"] if is_first else state.colors["text_secondary"],
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold" if is_first else "normal"),
                command=lambda v=view_name: self.on_view_change(v)
            )
            btn.pack(side="left", padx=3)
            self.menu_buttons[view_name] = btn
        
        # Generate button
        self.generate_button = ctk.CTkButton(
            self,
            text="✨ Generate Mod",
            command=self.on_generate,
            height=40,
            width=150,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.generate_button.pack(side="right", padx=25)
    
    def update_logo(self, logo_image):
    
        print(f"[DEBUG] update_logo called")
        """Update the logo image when theme changes"""
        self.logo_image = logo_image
        # Rebuild the UI to show the new logo
        for widget in self.winfo_children():
            widget.destroy()
        self._setup_ui()