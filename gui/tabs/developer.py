"""
Developer Tab
"""
import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Optional
import os
import json
import sys

from gui.state import state

# Import confirmation dialog with fallback
try:
    from gui import confirmation_dialog
except ImportError:
    try:
        import gui.confirmation_dialog as confirmation_dialog
    except ImportError:
        print("[WARNING] confirmation_dialog module not found, will use fallback dialogs")
        confirmation_dialog = None


def load_added_vehicles_at_startup():


    print(f"[DEBUG] load_added_vehicles_at_startup called")
    """Load added_vehicles.json at application startup
    
    This should be called from state.py or main_window.py during initialization
    to ensure custom vehicles are loaded from disk on app launch.
    """
    try:
        vehicles_folder = "vehicles"
        json_path = os.path.join(vehicles_folder, "added_vehicles.json")
        
        if not os.path.exists(json_path):
            print(f"[DEBUG] No added_vehicles.json found at startup - will create on first save")
            return
        
        print(f"[DEBUG] Loading added_vehicles from: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            loaded_vehicles = json.load(f)
        
        print(f"[DEBUG] Found {len(loaded_vehicles)} custom vehicles in file")
        
        # Update state with loaded data
        state.added_vehicles.clear()
        state.added_vehicles.update(loaded_vehicles)
        
        # NOTE: Do NOT add to vehicle_ids - this causes duplicates in sidebar
        # The sidebar populates from both vehicle_ids and added_vehicles,
        # so adding to both would show each custom vehicle twice
        
        print(f"[DEBUG] Startup: Loaded {len(state.added_vehicles)} custom vehicles")
        
    except Exception as e:
        print(f"[ERROR] Failed to load added_vehicles.json at startup: {e}")
        import traceback
        traceback.print_exc()


print(f"[DEBUG] Loading class: DeveloperTab")


class DeveloperTab(ctk.CTkFrame):
    """Complete developer tab for custom vehicle management"""
    
    def __init__(self, parent: ctk.CTk, notification_callback: Callable[[str, str, int], None] = None, 
                 refresh_callbacks: dict = None):
    
        print(f"[DEBUG] __init__ called")
        super().__init__(parent, fg_color=state.colors["app_bg"])
        
        # Callback for notifications
        self.show_notification = notification_callback or self._fallback_notification
        
        # Callbacks to refresh other tabs
        self.refresh_callbacks = refresh_callbacks or {}
        
        # Variables for adding vehicles
        self.carid_var = ctk.StringVar()
        self.carname_var = ctk.StringVar()
        self.json_path_var = ctk.StringVar()
        self.jbeam_path_var = ctk.StringVar()
        self.image_path_var = ctk.StringVar()
        
        # Search
        self.dev_search_var = ctk.StringVar()
        self.dev_search_placeholder = "🔍 Search vehicles..."
        
        # UI references
        self.dev_status_label: Optional[ctk.CTkLabel] = None
        self.dev_progress_bar: Optional[ctk.CTkProgressBar] = None
        self.dev_list_scroll: Optional[ctk.CTkScrollableFrame] = None
        
        # Store parent reference for dialogs
        self.parent = parent
        
        self._setup_ui()
        self.refresh_developer_list()
    
    def _fallback_notification(self, message: str, type: str = "info", duration: int = 3000):
        """Fallback notification"""
        print(f"[{type.upper()}] {message}")
    
    def _show_confirmation_dialog(self, title: str, message: str, danger: bool = False) -> bool:
        """Show confirmation dialog with fallback to tkinter messagebox"""
        if confirmation_dialog:
            # Use themed dialog
            return confirmation_dialog.askyesno(
                parent=self.parent,
                title=title,
                message=message,
                colors=state.colors,
                icon="🗑️" if danger else "❓",
                danger=danger
            )
        else:
            # Fallback to tkinter messagebox
            from tkinter import messagebox
            return messagebox.askyesno(title, message)
    
    def _save_added_vehicles_to_file(self):
        """Save added_vehicles to JSON file in vehicles folder
        
        This is the CRITICAL FIX - we need to explicitly save to the JSON file,
        not rely on save_settings() which may not be working correctly.
        """
        try:
            vehicles_folder = "vehicles"
            os.makedirs(vehicles_folder, exist_ok=True)
            
            # Path to added_vehicles.json
            json_path = os.path.join(vehicles_folder, "added_vehicles.json")
            
            print(f"[DEBUG] Saving added_vehicles to: {json_path}")
            print(f"[DEBUG] Current added_vehicles: {state.added_vehicles}")
            
            # Write to file
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(state.added_vehicles, f, indent=2)
            
            print(f"[DEBUG] Successfully saved {len(state.added_vehicles)} vehicles to {json_path}")
            
            if os.path.exists(json_path):
                file_size = os.path.getsize(json_path)
                print(f"[DEBUG] File exists, size: {file_size} bytes")
                
                # Read it back to verify
                with open(json_path, 'r', encoding='utf-8') as f:
                    verified_data = json.load(f)
                    print(f"[DEBUG] Verified: File contains {len(verified_data)} vehicles")
            else:
                print(f"[ERROR] File was not created at {json_path}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to save added_vehicles.json: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _reload_added_vehicles_from_file(self):
        """Reload added_vehicles from JSON file into state
        
        CRITICAL FIX: After saving, we need to reload the data into state
        so that other tabs can see the new vehicles.
        Also updates vehicle_ids in state so all lookups work correctly.
        """
        try:
            vehicles_folder = "vehicles"
            json_path = os.path.join(vehicles_folder, "added_vehicles.json")
            
            if not os.path.exists(json_path):
                print(f"[DEBUG] No added_vehicles.json file found at {json_path}")
                return False
            
            print(f"[DEBUG] Reloading added_vehicles from: {json_path}")
            
            with open(json_path, 'r', encoding='utf-8') as f:
                loaded_vehicles = json.load(f)
            
            print(f"[DEBUG] Loaded {len(loaded_vehicles)} vehicles from file")
            
            # Update state with loaded data
            state.added_vehicles.clear()
            state.added_vehicles.update(loaded_vehicles)
            
            # NOTE: Do NOT add to vehicle_ids - this causes duplicates in sidebar
            # The sidebar populates from both vehicle_ids and added_vehicles
            
            print(f"[DEBUG] State updated with {len(state.added_vehicles)} custom vehicles")
            print(f"[DEBUG] Current state.added_vehicles: {state.added_vehicles}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to reload added_vehicles.json: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _refresh_all_tabs(self):
        """Refresh vehicle lists in all tabs after adding/removing a vehicle
        
        This uses the integrated refresh system from our vehicle management updates.
        Uses multiple fallback methods to find the main window.
        """
        print(f"[DEBUG] _refresh_all_tabs called")
        print(f"[DEBUG] Current state.added_vehicles: {state.added_vehicles}")
        
        main_window = None
        
        try:
            # Method 1: Try standard navigation path (DeveloperTab -> SettingsTab -> MainWindow)
            print(f"[DEBUG] Trying method 1: self.master.master")
            if hasattr(self.master, 'master'):
                potential_main = self.master.master
                if hasattr(potential_main, 'tabs'):
                    main_window = potential_main
                    print(f"[DEBUG] ✓ Found main window via self.master.master")
            
            # Method 2: Search upward through widget hierarchy
            if not main_window:
                print(f"[DEBUG] Trying method 2: searching widget tree")
                widget = self.master
                for level in range(6):  # Try up to 6 levels up
                    if hasattr(widget, 'tabs'):
                        main_window = widget
                        print(f"[DEBUG] ✓ Found main window at level {level} in widget tree")
                        break
                    if hasattr(widget, 'master'):
                        widget = widget.master
                    else:
                        break
            
            # Method 3: Get toplevel window and search
            if not main_window:
                print(f"[DEBUG] Trying method 3: winfo_toplevel()")
                try:
                    root = self.winfo_toplevel()
                    if hasattr(root, 'tabs'):
                        main_window = root
                        print(f"[DEBUG] ✓ Found main window via winfo_toplevel()")
                except:
                    pass
            
            # Method 4: Try getting from winfo_children of root
            if not main_window:
                print(f"[DEBUG] Trying method 4: searching root children")
                try:
                    root = self.winfo_toplevel()
                    for child in root.winfo_children():
                        if hasattr(child, 'tabs'):
                            main_window = child
                            print(f"[DEBUG] ✓ Found main window in root children")
                            break
                except:
                    pass
            
            if not main_window:
                print(f"[ERROR] Could not find main window with tabs attribute")
                print(f"[DEBUG] self.master = {self.master}")
                print(f"[DEBUG] self.master type = {type(self.master)}")
                if hasattr(self.master, 'master'):
                    print(f"[DEBUG] self.master.master = {self.master.master}")
                    print(f"[DEBUG] self.master.master type = {type(self.master.master)}")
                return
            
            print(f"[DEBUG] Main window found: {type(main_window)}")
            print(f"[DEBUG] Available tabs: {list(main_window.tabs.keys())}")
            
            # Refresh generator tab
            generator_tab = main_window.tabs.get('generator')
            if generator_tab:
                print(f"[DEBUG] Generator tab found: {type(generator_tab)}")
                if hasattr(generator_tab, 'refresh_vehicle_list'):
                    print(f"[DEBUG] Calling generator_tab.refresh_vehicle_list()...")
                    generator_tab.refresh_vehicle_list()
                    print(f"[DEBUG] ✓ Generator tab refreshed")
                else:
                    print(f"[WARNING] Generator tab missing refresh_vehicle_list method")
                    print(f"[DEBUG] Generator tab methods: {[m for m in dir(generator_tab) if 'refresh' in m.lower()]}")
            else:
                print(f"[WARNING] Generator tab not found in tabs dict")
            
            # Refresh car list tab
            carlist_tab = main_window.tabs.get('carlist')
            if carlist_tab:
                print(f"[DEBUG] Car list tab found: {type(carlist_tab)}")
                if hasattr(carlist_tab, 'refresh_vehicle_list'):
                    print(f"[DEBUG] Calling carlist_tab.refresh_vehicle_list()...")
                    carlist_tab.refresh_vehicle_list()
                    print(f"[DEBUG] ✓ Car list tab refreshed")
                else:
                    print(f"[WARNING] Car list tab missing refresh_vehicle_list method")
            else:
                print(f"[WARNING] Car list tab not found in tabs dict")
            
            # Refresh sidebar (this is where vehicles are listed for adding to project)
            if hasattr(main_window, 'sidebar'):
                print(f"[DEBUG] Sidebar found, refreshing...")
                try:
                    # CRITICAL: Clear sidebar state BEFORE repopulating
                    # This prevents duplicates when refresh is called
                    if hasattr(state, 'sidebar_vehicle_buttons'):
                        print(f"[DEBUG] Clearing {len(state.sidebar_vehicle_buttons)} existing sidebar buttons...")
                        # Destroy all existing vehicle buttons
                        for btn_frame, car_id, car_name, add_btn_frame in state.sidebar_vehicle_buttons:
                            try:
                                btn_frame.destroy()
                            except:
                                pass
                        # Clear the list
                        state.sidebar_vehicle_buttons.clear()
                        print(f"[DEBUG] Sidebar state cleared")
                    
                    # Check if sidebar has a refresh method
                    if hasattr(main_window.sidebar, 'populate_vehicles'):
                        print(f"[DEBUG] Calling sidebar.populate_vehicles()...")
                        # Get the callback function from main window
                        if hasattr(main_window, '_add_vehicle_to_project_from_sidebar'):
                            main_window.sidebar.populate_vehicles(main_window._add_vehicle_to_project_from_sidebar)
                            print(f"[DEBUG] ✓ Sidebar refreshed")
                        else:
                            print(f"[WARNING] Main window missing _add_vehicle_to_project_from_sidebar")
                    else:
                        print(f"[WARNING] Sidebar missing populate_vehicles method")
                except Exception as e:
                    print(f"[ERROR] Failed to refresh sidebar: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[WARNING] Main window has no sidebar attribute")
            
            print(f"[DEBUG] _refresh_all_tabs completed")
            
        except Exception as e:
            print(f"[ERROR] Failed to refresh tabs: {e}")
            import traceback
            traceback.print_exc()
    
    def _setup_ui(self):
        """Set up the developer tab UI"""
        # Title
        ctk.CTkLabel(
            self,
            text="Add New Vehicle",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=state.colors["text"]
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        # Input frame
        input_frame = ctk.CTkFrame(self, fg_color=state.colors["frame_bg"], corner_radius=12)
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Car ID
        ctk.CTkLabel(
            input_frame,
            text="Car ID:",
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text"]
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        ctk.CTkEntry(
            input_frame,
            textvariable=self.carid_var,
            placeholder_text="e.g., mycar",
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        ).grid(row=0, column=1, sticky="ew", padx=10, pady=(10, 5))
        
        # Car Name
        ctk.CTkLabel(
            input_frame,
            text="Car Name:",
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text"]
        ).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        ctk.CTkEntry(
            input_frame,
            textvariable=self.carname_var,
            placeholder_text="e.g., My Custom Car",
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"]
        ).grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        
        # JSON File
        ctk.CTkLabel(
            input_frame,
            text="JSON File:",
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text"]
        ).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        
        json_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        json_frame.grid(row=2, column=1, sticky="ew", padx=10, pady=5)
        json_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(
            json_frame,
            textvariable=self.json_path_var,
            placeholder_text="Select info_<carid>.json file",
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"],
            state="readonly"
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        ctk.CTkButton(
            json_frame,
            text="Browse",
            width=80,
            command=self._browse_json,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"]
        ).grid(row=0, column=1)
        
        # JBeam File
        ctk.CTkLabel(
            input_frame,
            text="JBeam File:",
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text"]
        ).grid(row=3, column=0, sticky="w", padx=10, pady=5)
        
        jbeam_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        jbeam_frame.grid(row=3, column=1, sticky="ew", padx=10, pady=5)
        jbeam_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(
            jbeam_frame,
            textvariable=self.jbeam_path_var,
            placeholder_text="Select <carid>.jbeam file",
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"],
            state="readonly"
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        ctk.CTkButton(
            jbeam_frame,
            text="Browse",
            width=80,
            command=self._browse_jbeam,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"]
        ).grid(row=0, column=1)
        
        # Image File
        ctk.CTkLabel(
            input_frame,
            text="Image File:",
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text"]
        ).grid(row=4, column=0, sticky="w", padx=10, pady=5)
        
        image_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        image_frame.grid(row=4, column=1, sticky="ew", padx=10, pady=5)
        image_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(
            image_frame,
            textvariable=self.image_path_var,
            placeholder_text="Select vehicle image (optional)",
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"],
            state="readonly"
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        ctk.CTkButton(
            image_frame,
            text="Browse",
            width=80,
            command=self._browse_image,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"]
        ).grid(row=0, column=1)
        
        input_frame.grid_columnconfigure(1, weight=1)
        
        # Add button
        ctk.CTkButton(
            input_frame,
            text="➕ Add Vehicle",
            command=self.add_vehicle,
            fg_color=state.colors["success"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 10))
        
        # Status and progress container (always visible, reserved space)
        status_container = ctk.CTkFrame(self, fg_color="transparent", height=60)
        status_container.pack(fill="x", padx=10, pady=(5, 0))
        status_container.pack_propagate(False)  # Maintain fixed height
        
        # Status label (inside container)
        self.dev_status_label = ctk.CTkLabel(
            status_container,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=state.colors["text"]
        )
        
        # Progress bar (inside container)
        self.dev_progress_bar = ctk.CTkProgressBar(
            status_container,
            progress_color=state.colors["accent"]
        )
        
        # List header with centered search
        list_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        list_header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # Title on left
        ctk.CTkLabel(
            list_header_frame,
            text="Added Vehicles",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=state.colors["text"]
        ).pack(side="left")
        
        # Centered search using place
        self.dev_search_entry = ctk.CTkEntry(
            list_header_frame,
            textvariable=self.dev_search_var,
            width=300,
            height=34,
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            border_width=1,
            text_color=state.colors["text"],
            corner_radius=6
        )
        self.dev_search_entry.place(relx=0.5, rely=0.5, anchor="center")
        
        # Set initial placeholder
        self.dev_search_var.set(self.dev_search_placeholder)
        self.dev_search_entry.configure(text_color="#888888")
        
        # Bind focus events for placeholder
        self.dev_search_entry.bind("<FocusIn>", self._on_dev_search_focus_in)
        self.dev_search_entry.bind("<FocusOut>", self._on_dev_search_focus_out)
        
        # Bind search with placeholder check
        self.dev_search_var.trace("w", lambda *args: self.refresh_developer_list())
        
        # Vehicle list
        self.dev_list_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=state.colors["frame_bg"],
            corner_radius=12
        )
        self.dev_list_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _browse_json(self):
        """Browse for JSON file"""
        filename = filedialog.askopenfilename(
            title="Select info JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.json_path_var.set(filename)
    
    def _browse_jbeam(self):
        """Browse for JBeam file"""
        filename = filedialog.askopenfilename(
            title="Select JBeam file",
            filetypes=[("JBeam files", "*.jbeam"), ("All files", "*.*")]
        )
        if filename:
            self.jbeam_path_var.set(filename)
    
    def _browse_image(self):
        """Browse for image file"""
        filename = filedialog.askopenfilename(
            title="Select vehicle image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.dds"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.image_path_var.set(filename)
    
    def add_vehicle(self):
    
        print(f"[DEBUG] add_vehicle called")
        """Add a custom vehicle"""
        carid = self.carid_var.get().strip()
        carname = self.carname_var.get().strip()
        json_path = self.json_path_var.get().strip()
        jbeam_path = self.jbeam_path_var.get().strip()
        image_path = self.image_path_var.get().strip()
        
        # Validation
        if not carid or not carname:
            self.show_notification("Car ID and Name are required", "error")
            return
        
        if not json_path or not jbeam_path:
            self.show_notification("JSON and JBeam files are required", "error")
            return
        
        if not os.path.exists(json_path) or not os.path.exists(jbeam_path):
            self.show_notification("Selected files do not exist", "error")
            return
        
        if image_path and not os.path.exists(image_path):
            self.show_notification("Selected image does not exist", "error")
            return
        
        # Check if already exists
        if carid in state.added_vehicles:
            self.show_notification(f"Vehicle '{carid}' already exists", "error")
            return
        
        # Show progress
        self.dev_status_label.pack(padx=10, pady=(5, 0))
        self.dev_progress_bar.pack(fill="x", padx=10, pady=(5, 5))
        self.dev_status_label.configure(text="Processing vehicle files...")
        self.dev_progress_bar.set(0.3)
        
        try:
            # Process vehicle
            from core.developer import process_custom_vehicle
            
            success = process_custom_vehicle(
                carid=carid,
                carname=carname,
                json_path=json_path,
                jbeam_path=jbeam_path,
                image_path=image_path if image_path else None
            )
            
            if success:
                self.dev_status_label.configure(text="Saving vehicle data...")
                self.dev_progress_bar.set(0.7)
                
                # NOTE: core.developer.process_custom_vehicle() already saves to JSON
                # So we just need to reload state and refresh tabs
                
                # Reload state from JSON file
                self._reload_added_vehicles_from_file()
                
                # Success
                self.dev_status_label.configure(text="Vehicle added successfully!")
                self.dev_progress_bar.set(1.0)
                
                # Clear inputs
                self.carid_var.set("")
                self.carname_var.set("")
                self.json_path_var.set("")
                self.jbeam_path_var.set("")
                self.image_path_var.set("")
                
                self.show_notification(f"✅ Added vehicle '{carname}'", "success", 3000)
                self.refresh_developer_list()
                
                # Refresh other tabs using the integrated system
                print(f"[DEBUG] Refreshing all tabs after adding vehicle...")
                self._refresh_all_tabs()
                print(f"[DEBUG] All tabs refreshed successfully")
                
            else:
                self.dev_status_label.configure(text="Error: Processing failed")
                self.show_notification("Failed to process vehicle files", "error")
        
        except ImportError:
            self.dev_status_label.configure(text="Error: Developer module not found")
            self.show_notification("Developer module not available", "error")
            print("[ERROR] core.developer module not found")
        except Exception as e:
            self.dev_status_label.configure(text=f"Error: {str(e)}")
            self.show_notification(f"Error: {str(e)}", "error")
            print(f"[ERROR] Failed to add vehicle: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Hide progress after delay
            self.after(2000, lambda: self.dev_progress_bar.pack_forget())
            self.after(2000, lambda: self.dev_status_label.pack_forget())
    
    def delete_vehicle(self, carid: str):
    
        print(f"[DEBUG] delete_vehicle called")
        """Delete a custom vehicle using themed confirmation dialog"""
        carname = state.added_vehicles.get(carid, carid)
        
        # Show confirmation dialog (themed or fallback)
        response = self._show_confirmation_dialog(
            title="Confirm Delete",
            message=f"Are you sure you want to delete '{carname}'?\n\nThis will remove the vehicle from all menus and delete all associated files.",
            danger=True
        )
        
        if response:
            if carid in state.added_vehicles:
                try:
                    from core.developer import delete_custom_vehicle
                    file_delete_success = delete_custom_vehicle(carid)
                    
                    if not file_delete_success:
                        print(f"[WARNING] Failed to delete some files for {carid}")
                except ImportError:
                    print(f"[WARNING] core.developer module not found, only removing from state")
                except Exception as e:
                    print(f"[ERROR] Failed to delete vehicle files: {e}")
                
                # NOTE: core.developer.delete_custom_vehicle() already removes from JSON
                # So we just need to reload state and refresh tabs
                
                # Reload state from JSON file
                self._reload_added_vehicles_from_file()
                
                self.show_notification(f"Deleted vehicle '{carname}'", "info")
                self.refresh_developer_list()
                
                # Refresh all tabs using the integrated system
                print(f"[DEBUG] Refreshing all tabs after deleting vehicle...")
                self._refresh_all_tabs()
                print(f"[DEBUG] All tabs refreshed successfully")
    
    def _on_dev_search_focus_in(self, event):
        """Handle focus in for dev search entry - remove placeholder"""
        if self.dev_search_var.get() == self.dev_search_placeholder:
            self.dev_search_var.set("")
            self.dev_search_entry.configure(text_color=state.colors["text"])
    
    def _on_dev_search_focus_out(self, event):
        """Handle focus out for dev search entry - restore placeholder if empty"""
        if not self.dev_search_var.get():
            self.dev_search_var.set(self.dev_search_placeholder)
            self.dev_search_entry.configure(text_color="#888888")
    
    def refresh_developer_list(self):
    
        print(f"[DEBUG] refresh_developer_list called")
        """Refresh the list of custom vehicles"""
        # Clear existing items
        for widget in self.dev_list_scroll.winfo_children():
            widget.destroy()
        
        search_query = self.dev_search_var.get()
        
        # Ignore placeholder text
        if search_query == self.dev_search_placeholder:
            search_query = ""
        
        search_query = search_query.lower().strip()
        
        if not state.added_vehicles:
            empty_label = ctk.CTkLabel(
                self.dev_list_scroll,
                text="No custom vehicles added yet",
                font=ctk.CTkFont(size=13),
                text_color=state.colors["text_secondary"]
            )
            empty_label.pack(pady=20)
            return
        
        # Filter and display vehicles
        for carid, carname in sorted(state.added_vehicles.items(), key=lambda x: x[1].lower()):
            if search_query and search_query not in carid.lower() and search_query not in carname.lower():
                continue
            
            self._add_vehicle_card(carid, carname)
    
    def _add_vehicle_card(self, carid: str, carname: str):
        """Add a vehicle card to the list"""
        card = ctk.CTkFrame(
            self.dev_list_scroll,
            fg_color=state.colors["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=state.colors["border"]
        )
        card.pack(fill="x", padx=5, pady=5)
        
        # Vehicle info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=15, pady=10)
        
        ctk.CTkLabel(
            info_frame,
            text=carname,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=carid,
            font=ctk.CTkFont(size=12),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(anchor="w")
        
        # Delete button
        delete_btn = ctk.CTkButton(
            card,
            text="🗑️ Delete",
            width=100,
            height=32,
            fg_color=state.colors["error"],
            hover_color=state.colors["error_hover"],
            text_color=state.colors["accent_text"],
            command=lambda c=carid: self.delete_vehicle(c)
        )
        delete_btn.pack(side="right", padx=10, pady=10)