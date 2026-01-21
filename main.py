import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
from config import VEHICLE_IDS
from file_ops import generate_mod
import threading
import sys
import webbrowser
import time
import os
import json
import shutil
from tkinter import messagebox
import io
from datetime import datetime
import re
import copy

VEHICLE_FOLDER = os.path.join(os.getcwd(), "vehicles")
os.makedirs(VEHICLE_FOLDER, exist_ok=True)

def create_vehicle_folders(carid):
    """
    Creates:
    vehicles/<carid>/SKINNAME
    """
    car_folder = os.path.join(VEHICLE_FOLDER, carid)
    skin_folder = os.path.join(car_folder, "SKINNAME")
    os.makedirs(skin_folder, exist_ok=True)

def delete_vehicle_folders(carid):
    """
    Deletes:
    vehicles/<carid>/
    imagesforgui/vehicles/<carid>/
    """
    # Delete vehicle folder
    car_folder = os.path.join(VEHICLE_FOLDER, carid)
    if os.path.exists(car_folder):
        shutil.rmtree(car_folder)
    
    # Delete preview image folder
    image_folder = os.path.join("imagesforgui", "vehicles", carid)
    if os.path.exists(image_folder):
        shutil.rmtree(image_folder)
        print(f"Deleted preview image folder: {image_folder}")


def edit_material_json(json_path, skinname_folder, carid):
    """
    Edits the material JSON file to keep only the targeted skin sections,
    renames them to use 'skinname' as a placeholder, and updates the baseColorMap path.
    
    Rules:
    1. Only keep sections where the key ends with the same skin name
    2. Rename all kept entries to use '.skin.skinname' as placeholder
    3. Update name and mapTo fields to match the new key
    4. Update baseColorMap in Stage 2 (index 1) to the placeholder path format
    5. The generator will later replace 'skinname' with the actual skin name
    6. Keep all other properties unchanged
    """
    # Use 'skinname' as the placeholder
    skinname = "skinname"
    
    try:
        print(f"\n--- Starting JSON Edit Process ---")
        print(f"Reading JSON file: {json_path}")
        print(f"Target Car ID: {carid}")
        print(f"Using placeholder: 'skinname' (will be replaced by generator)")
        
        # Read the raw file content
        with open(json_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Clean the JSON content
        print("Cleaning JSON (removing comments and fixing trailing commas)...")
        
        # Remove single-line comments (// ...)
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove // comments but preserve strings that might contain //
            if '//' in line:
                # Simple approach: find // outside of strings
                in_string = False
                escape = False
                comment_pos = -1
                for i, char in enumerate(line):
                    if escape:
                        escape = False
                        continue
                    if char == '\\':
                        escape = True
                        continue
                    if char == '"':
                        in_string = not in_string
                    if not in_string and i < len(line) - 1 and line[i:i+2] == '//':
                        comment_pos = i
                        break
                if comment_pos >= 0:
                    line = line[:comment_pos]
            cleaned_lines.append(line)
        
        content = '\n'.join(cleaned_lines)
        
        # Remove block comments (/* ... */)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Fix trailing commas before } or ]
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Parse the cleaned JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"ERROR: Could not parse JSON even after cleaning - {e}")
            print("Attempting to save cleaned version for manual inspection...")
            cleaned_path = json_path + ".cleaned"
            with open(cleaned_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Cleaned JSON saved to: {cleaned_path}")
            raise
        
        print(f"Original JSON contains {len(data)} entries")
        
        # Find all skin names in the JSON
        # Extract the skin name suffix (e.g., ".skin.customskin")
        skin_suffixes = set()
        for key in data.keys():
            # Check if it's a skin key (contains ".skin.")
            if ".skin." in key:
                # Extract everything after ".skin."
                parts = key.split(".skin.")
                if len(parts) == 2:
                    skin_suffixes.add(f".skin.{parts[1]}")
        
        if not skin_suffixes:
            print("WARNING: No skin entries found in JSON")
            return
        
        # Use the first skin suffix found
        target_suffix = list(skin_suffixes)[0]
        print(f"Target skin suffix: {target_suffix}")
        
        # Filter and rename data
        filtered_data = {}
        for key, value in data.items():
            if key.endswith(target_suffix):
                # Extract the prefix (everything before ".skin.")
                parts = key.split(".skin.")
                if len(parts) == 2:
                    prefix = parts[0]
                    # Create new key with the new skinname
                    new_key = f"{prefix}.skin.{skinname}"
                    
                    print(f"Processing: {key} → {new_key}")
                    
                    # Deep copy the value to avoid modifying original
                    new_value = copy.deepcopy(value)
                    
                    # Update name and mapTo fields
                    if "name" in new_value:
                        new_value["name"] = new_key
                        print(f"  Updated name: {new_key}")
                    
                    if "mapTo" in new_value:
                        new_value["mapTo"] = new_key
                        print(f"  Updated mapTo: {new_key}")
                    
                    # Update baseColorMap in Stage 2 (index 1)
                    if "Stages" in new_value and isinstance(new_value["Stages"], list):
                        if len(new_value["Stages"]) > 1:  # Stage 2 exists
                            stage2 = new_value["Stages"][1]
                            if "baseColorMap" in stage2:
                                old_path = stage2["baseColorMap"]
                                # Construct new path based on the prefix
                                # Extract the base material name from prefix (e.g., ccf_main → ccf)
                                base_name = prefix.split('_')[0]
                                new_path = f"vehicles/{carid}/{skinname}/{base_name}_skin_{skinname}.dds"
                                stage2["baseColorMap"] = new_path
                                print(f"  Updated baseColorMap in Stage 2:")
                                print(f"    Old: {old_path}")
                                print(f"    New: {new_path}")
                    
                    filtered_data[new_key] = new_value
        
        print(f"\nFiltered JSON contains {len(filtered_data)} entries")
        
        # Write the edited JSON back to the folder
        json_filename = os.path.basename(json_path)
        output_path = os.path.join(skinname_folder, json_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=4)
        
        print(f"Edited JSON saved to: {output_path}")
        print(f"--- JSON Edit Complete ---\n")
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON format - {e}")
        raise Exception(f"Invalid JSON format: {str(e)}")
    except Exception as e:
        print(f"ERROR during JSON editing: {e}")
        raise
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON format - {e}")
        raise Exception(f"Invalid JSON format: {str(e)}")
    except Exception as e:
        print(f"ERROR during JSON editing: {e}")
        raise


# Example usage and testing function
def test_editor():
    """Test function to demonstrate usage"""
    # Example: edit_material_json("path/to/skin.materials.json", "output_folder", "mycar")
    pass


if __name__ == "__main__":
    test_editor()


def edit_jbeam_material(jbeam_path, skinname_folder, carid):
    """
    Edits the JBEAM file according to specifications:
    1. Keep only the FIRST skin entry encountered
    2. Rename it to carid_skin_skinname
    3. Update "authors" field to placeholder "Author Name"
    4. Update "name" field to placeholder "Skin Name"
    5. Update "globalSkin" to "skinname"
    6. Preserve all other fields (information.value, slotType, etc.)
    
    Note: "Author Name" and "Skin Name" are placeholders that will be replaced
    during mod generation with actual values from the Generator tab.
    """
    try:
        print(f"\n--- Starting JBEAM Edit Process ---")
        print(f"Reading JBEAM file: {jbeam_path}")
        print(f"Target Car ID: {carid}")
        print(f"Using placeholders: 'Author Name' and 'Skin Name' (will be replaced by generator)")
        
        # Read the raw file content
        with open(jbeam_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Clean the JBEAM content (remove comments)
        print("Cleaning JBEAM (removing comments)...")
        
        # Remove single-line comments (// ...)
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            if '//' in line:
                in_string = False
                escape = False
                comment_pos = -1
                for i, char in enumerate(line):
                    if escape:
                        escape = False
                        continue
                    if char == '\\':
                        escape = True
                        continue
                    if char == '"':
                        in_string = not in_string
                    if not in_string and i < len(line) - 1 and line[i:i+2] == '//':
                        comment_pos = i
                        break
                if comment_pos >= 0:
                    line = line[:comment_pos]
            cleaned_lines.append(line)
        
        content = '\n'.join(cleaned_lines)
        
        # Remove block comments (/* ... */)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Fix trailing commas before } or ]
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Parse the cleaned JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"ERROR: Could not parse JBEAM even after cleaning - {e}")
            print("Attempting to save cleaned version for manual inspection...")
            cleaned_path = jbeam_path + ".cleaned"
            with open(cleaned_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Cleaned JBEAM saved to: {cleaned_path}")
            raise
        
        print(f"Original JBEAM contains {len(data)} entries")
        
        # STEP 1: Find all skin entries (keys containing "_skin_")
        skin_entries = []
        for key in data.keys():
            if "_skin_" in key:
                skin_entries.append((key, data[key]))
        
        if not skin_entries:
            print("WARNING: No skin entries found in JBEAM")
            return
        
        print(f"Found {len(skin_entries)} skin entries")
        
        # STEP 2: Keep only the FIRST skin entry
        first_skin_key, first_skin_value = skin_entries[0]
        print(f"\n✓ Canonical skin identified: {first_skin_key}")
        
        if len(skin_entries) > 1:
            removed_skins = [key for key, _ in skin_entries[1:]]
            print(f"✗ Removing {len(removed_skins)} other skin(s): {', '.join(removed_skins)}")
        
        # STEP 3: Create the new skin entry
        new_key = f"{carid}_skin_skinname"
        new_value = copy.deepcopy(first_skin_value)
        
        print(f"\n✓ Renaming: {first_skin_key} → {new_key}")
        
        # STEP 4: Update authors and name fields to placeholders
        if "information" in new_value and isinstance(new_value["information"], dict):
            if "authors" in new_value["information"]:
                old_author = new_value["information"]["authors"]
                new_value["information"]["authors"] = "Author Name"
                print(f"  ✓ Updated authors: '{old_author}' → 'Author Name' (placeholder)")
            
            if "name" in new_value["information"]:
                old_name = new_value["information"]["name"]
                new_value["information"]["name"] = "Skin Name"
                print(f"  ✓ Updated name: '{old_name}' → 'Skin Name' (placeholder)")
            
            # Preserve value field
            if "value" in new_value["information"]:
                print(f"  ✓ Preserved value: {new_value['information']['value']}")
        
        # STEP 5: Update globalSkin to "skinname"
        if "globalSkin" in new_value:
            old_global_skin = new_value["globalSkin"]
            new_value["globalSkin"] = "skinname"
            print(f"  ✓ Updated globalSkin: '{old_global_skin}' → 'skinname'")
        
        # STEP 6: Preserve all other fields (slotType, etc.)
        if "slotType" in new_value:
            print(f"  ✓ Preserved slotType: '{new_value['slotType']}'")
        
        # Create the filtered data with only the new skin entry
        filtered_data = {new_key: new_value}
        
        print(f"\n--- Summary ---")
        print(f"Original skins: {len(skin_entries)}")
        print(f"Final skins: 1")
        print(f"Removed: {len(skin_entries) - 1}")
        
        # Write the edited JBEAM back to the folder, keeping original filename
        jbeam_filename = os.path.basename(jbeam_path)
        output_path = os.path.join(skinname_folder, jbeam_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=4)
        
        print(f"Edited JBEAM saved to: {output_path}")
        print(f"--- JBEAM Edit Complete ---\n")
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JBEAM format - {e}")
        raise Exception(f"Invalid JBEAM format: {str(e)}")
    except Exception as e:
        print(f"ERROR during JBEAM editing: {e}")
        raise


# -----------------------
# Theme System
# -----------------------
SETTINGS_FILE = "app_settings.json"

# Default settings
app_settings = {
    "theme": "dark"  # "dark" or "light"
}

# Load settings
if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, "r") as f:
            app_settings = json.load(f)
    except:
        pass

def save_settings():
    """Save app settings to file"""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(app_settings, f, indent=4)

# Theme color definitions
THEMES = {
    "dark": {
        "app_bg": "#0d0d0d",
        "frame_bg": "#1a1a1a",
        "card_bg": "#262626",
        "card_hover": "#333333",
        "text": "#f2f2f2",
        "text_secondary": "gray40",
        "accent": "#39E09B",
        "accent_hover": "#30BD82",
        "accent_text": "black",
        "tab_selected": "#262626",
        "tab_selected_hover": "#333333",
        "tab_unselected": "#1a1a1a",
        "tab_unselected_hover": "#262626",
        "border": "#333333",
        "error": "#E03939",
        "error_hover": "#BD3030"
    },
    "light": {
        "app_bg": "#f2f2f2",
        "frame_bg": "#e6e6e6",
        "card_bg": "#d9d9d9",
        "card_hover": "#cccccc",
        "text": "#0d0d0d",
        "text_secondary": "gray60",
        "accent": "#39E09B",
        "accent_hover": "#30BD82",
        "accent_text": "black",
        "tab_selected": "#d9d9d9",
        "tab_selected_hover": "#cccccc",
        "tab_unselected": "#e6e6e6",
        "tab_unselected_hover": "#d9d9d9",
        "border": "#cccccc",
        "error": "#E03939",
        "error_hover": "#BD3030"
    }
}

current_theme = app_settings["theme"]
colors = THEMES[current_theme]


ADDED_VEHICLES_FILE = "added_vehicles.json"
added_vehicles = {}  # carid -> carname

# Ensure save file exists
if not os.path.exists(ADDED_VEHICLES_FILE):
    with open(ADDED_VEHICLES_FILE, "w") as f:
        json.dump({}, f)

# Load existing developer-added vehicles
with open(ADDED_VEHICLES_FILE, "r") as f:
    try:
        added_vehicles = json.load(f)
    except:
        added_vehicles = {}

# DO NOT merge added_vehicles into VEHICLE_IDS
# We'll keep them separate to maintain carid -> carname mapping


# -----------------------
# Debug Mode Setup
# -----------------------
debug_mode_enabled = False
debug_window = None
debug_textbox = None

class DebugOutput(io.StringIO):
    """Custom output stream that writes to both console and debug window"""
    def __init__(self):
        super().__init__()
        self.terminal = sys.stdout
        
    def write(self, message):
        self.terminal.write(message)
        if debug_mode_enabled and debug_textbox is not None:
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                debug_textbox.insert("end", f"[{timestamp}] {message}")
                debug_textbox.see("end")
            except:
                pass
    
    def flush(self):
        self.terminal.flush()

def create_debug_window():
    """Create a separate window for debug output"""
    global debug_window, debug_textbox
    
    if debug_window is not None and debug_window.winfo_exists():
        debug_window.lift()
        return
    
    debug_window = ctk.CTkToplevel(app)
    debug_window.title("Debug Console")
    debug_window.geometry("800x600")
    debug_window.configure(fg_color=colors["app_bg"])
    
    # Header
    header_frame = ctk.CTkFrame(debug_window, corner_radius=12, fg_color=colors["frame_bg"])
    header_frame.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(header_frame, text="Debug Console", font=ctk.CTkFont(size=16, weight="bold"), text_color=colors["text"]).pack(side="left", padx=20, pady=10)
    
    # Clear button
    def clear_debug():
        debug_textbox.delete("0.0", "end")
        print("Debug console cleared")
    
    ctk.CTkButton(header_frame, text="Clear", width=80, command=clear_debug,
                  fg_color=colors["card_bg"], hover_color=colors["card_hover"], text_color=colors["text"]).pack(side="right", padx=10, pady=10)
    
    # Debug output textbox
    debug_textbox = ctk.CTkTextbox(debug_window, font=ctk.CTkFont(family="Consolas", size=11),
                                    fg_color=colors["frame_bg"], text_color=colors["accent"])
    debug_textbox.pack(fill="both", expand=True, padx=10, pady=(0,10))
    
    print("="*50)
    print("DEBUG MODE ENABLED")
    print("="*50)
    
    def on_debug_window_close():
        global debug_mode_enabled, debug_window
        debug_mode_enabled = False
        debug_mode_var.set(False)
        debug_window.destroy()
        debug_window = None
        print("Debug mode disabled")
    
    debug_window.protocol("WM_DELETE_WINDOW", on_debug_window_close)

def toggle_debug_mode():
    """Toggle debug mode on/off"""
    global debug_mode_enabled
    
    if debug_mode_var.get():
        debug_mode_enabled = True
        create_debug_window()
        print("Debug mode activated")
    else:
        debug_mode_enabled = False
        if debug_window is not None and debug_window.winfo_exists():
            debug_window.destroy()
        print("Debug mode deactivated")

# Redirect stdout to our custom output
sys.stdout = DebugOutput()


# -----------------------
# Hover Preview System
# -----------------------
hover_preview_window = None
hover_timer = None
current_hover_carid = None

def show_hover_preview(carid, x, y):
    """Show preview image for vehicle on hover"""
    global hover_preview_window
    
    # Close existing preview if any
    if hover_preview_window is not None:
        hover_preview_window.destroy()
        hover_preview_window = None
    
    # Construct image path
    image_path = os.path.join("imagesforgui", "vehicles", carid, "default.jpg")
    
    print(f"Attempting to load preview image: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"Preview image not found for carid: {carid}")
        return
    
    try:
        # Get car name
        car_name = carid  # Default to carid if not found
        for cid, cname in car_id_list:
            if cid == carid:
                car_name = cname
                break
        
        # Load and resize image
        img = Image.open(image_path)
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        
        print(f"Preview image loaded successfully for: {carid}")
        
        # Create preview window
        hover_preview_window = ctk.CTkToplevel(app)
        hover_preview_window.overrideredirect(True)  # Remove window decorations
        hover_preview_window.attributes('-topmost', True)
        hover_preview_window.configure(fg_color=colors["frame_bg"])
        
        # Position window near cursor
        hover_preview_window.geometry(f"+{x+20}+{y+20}")
        
        # Add image to window
        photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        label = ctk.CTkLabel(hover_preview_window, image=photo, text="")
        label.image = photo  # Keep reference
        label.pack(padx=5, pady=5)
        
        # Add car name and carid label
        ctk.CTkLabel(
            hover_preview_window, 
            text=f"Car Name: {car_name}  |  Car ID: {carid}", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=colors["text"]
        ).pack(pady=(0, 5))
        
    except Exception as e:
        print(f"Error loading preview image for {carid}: {e}")

def hide_hover_preview():
    """Hide the hover preview window"""
    global hover_preview_window, hover_timer, current_hover_carid
    
    if hover_timer is not None:
        app.after_cancel(hover_timer)
        hover_timer = None
    
    if hover_preview_window is not None:
        hover_preview_window.destroy()
        hover_preview_window = None
    
    current_hover_carid = None

def schedule_hover_preview(carid, widget):
    """Schedule preview to show after 1 second of hovering"""
    global hover_timer, current_hover_carid
    
    # Cancel existing timer
    if hover_timer is not None:
        app.after_cancel(hover_timer)
    
    current_hover_carid = carid
    
    # Get cursor position relative to screen
    x = widget.winfo_pointerx()
    y = widget.winfo_pointery()
    
    # Schedule preview to show after 1000ms (1 second)
    hover_timer = app.after(1000, lambda: show_hover_preview(carid, x, y))


# -----------------------
# Helper function to save added vehicles
# -----------------------
def save_added_vehicles():
    """Save the current added_vehicles dict to the JSON file."""
    with open(ADDED_VEHICLES_FILE, "w") as f:
        json.dump(added_vehicles, f, indent=4)




print("Starting BeamSkin Studio...")

# -----------------------
# Setup
# -----------------------
ctk.set_appearance_mode("dark" if current_theme == "dark" else "light")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("BeamSkin Studio")
app.geometry("1100x1350")
app.minsize(700, 600)  # Set minimum window size
app.resizable(False, True)  # Make window resizable
app.configure(fg_color=colors["app_bg"])

app.update_idletasks()
width, height = 1100, 1350
x = (app.winfo_screenwidth() // 2) - (width // 2)
y = (app.winfo_screenheight() // 2) - (height // 2) - 40 
app.geometry(f"{width}x{height}+{x}+{y}")

# -----------------------
# Theme Toggle Function
# -----------------------
def toggle_theme():
    """Toggle between light and dark theme"""
    global current_theme, colors
    
    # Ask user if they want to restart
    response = messagebox.askyesno(
        "Restart Required", 
        "Changing the theme requires restarting the application.\n\n"
        "⚠️ WARNING: Any unsaved changes will be lost!\n\n"
        "Do you want to restart now?",
        icon='warning'
    )
    
    if response:
        # Switch theme
        current_theme = "light" if current_theme == "dark" else "dark"
        colors = THEMES[current_theme]
        
        # Save setting
        app_settings["theme"] = current_theme
        save_settings()
        
        print(f"Theme changed to: {current_theme}")
        print("Restarting application...")
        
        # Restart the application
        import sys
        import subprocess
        
        # Close current app
        app.destroy()
        
        # Restart with same script
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit()
    else:
        # User cancelled, revert the switch
        if current_theme == "dark":
            theme_switch.deselect()
        else:
            theme_switch.select()

# -----------------------
# Variables
# -----------------------
mod_name_var = ctk.StringVar()
skin_name_var = ctk.StringVar()
author_var = ctk.StringVar()
dds_path_var = ctk.StringVar()
# Two variables: one for display (car name), one for actual carid
selected_carid = list(VEHICLE_IDS.keys())[0]  # Store the actual carid
vehicle_display_var = ctk.StringVar(value=VEHICLE_IDS[selected_carid])  # Display the car name in UI
output_mode_var = ctk.StringVar(value="steam")
custom_output_var = ctk.StringVar()
dds_preview_label = None
progress_bar = None
export_status_label = None

# -----------------------
# Functions
# -----------------------
def select_dds():
    path = filedialog.askopenfilename(title="Select DDS File", filetypes=[("DDS Files", "*.dds")])
    if path:
        dds_path_var.set(path)
        load_dds_preview(path)
        print(f"DDS file selected: {path}")

def load_dds_preview(file_path):
    try:
        img = Image.open(file_path)
        w, h = img.size
        print(f"DDS image loaded: {w}x{h}")
        max_size = 200
        if w > h:
            new_w = max_size
            new_h = int(max_size * (h / w))
        else:
            new_h = max_size
            new_w = int(max_size * (w / h))
        img.thumbnail((new_w, new_h), Image.Resampling.LANCZOS)
        photo = ctk.CTkImage(light_image=img, dark_image=img, size=(new_w, new_h))
        dds_preview_label.configure(image=photo, text="")
        dds_preview_label.image = photo
    except Exception as e:
        print(f"Failed to load DDS preview: {e}")
        dds_preview_label.configure(text="Preview\nUnavailable", image=None)

def select_custom_output():
    folder = filedialog.askdirectory(title="Select Output Directory")
    if folder:
        custom_output_var.set(folder)
        output_mode_var.set("custom")
        print(f"Custom output directory selected: {folder}")

def update_output_mode():
    if output_mode_var.get() == "custom":
        custom_output_frame.pack(fill="x", padx=(20,5), pady=(5,10))
    else:
        custom_output_frame.pack_forget()

def update_progress(value):
    if progress_bar.winfo_ismapped():
        progress_bar.set(value)

def on_generate():
    global selected_carid
    
    print("\n" + "="*50)
    print("GENERATE MOD INITIATED")
    print("="*50)
    
    if not mod_name_var.get():
        print("ERROR: No mod name provided")
        show_notification("Please enter a Mod Name", "error")
        return
    if not skin_name_var.get():
        print("ERROR: No skin name provided")
        show_notification("Please enter a Skin Name", "error")
        return
    if not dds_path_var.get():
        print("ERROR: No DDS file selected")
        show_notification("Please select a DDS file", "error")
        return

    output_path = custom_output_var.get() if output_mode_var.get() == "custom" else None

    if not selected_carid:
        print("ERROR: No vehicle selected")
        show_notification("Invalid vehicle selection", "error")
        return

    print(f"Mod Name: {mod_name_var.get()}")
    print(f"Skin Name: {skin_name_var.get()}")
    print(f"Author: {author_var.get()}")
    print(f"Vehicle ID: {selected_carid}")
    print(f"DDS Path: {dds_path_var.get()}")
    print(f"Output Mode: {output_mode_var.get()}")
    if output_path:
        print(f"Custom Output Path: {output_path}")
    
    export_status_label.configure(text="Preparing to export...")
    export_status_label.pack(padx=20, pady=(10,5))
    progress_bar.pack(fill="x", padx=20, pady=(0,5))
    progress_bar.set(0)
    generate_button.configure(state="disabled")

    def update_status(message):
        """Update the status label text"""
        export_status_label.configure(text=message)

    def thread_fn():
        try:
            print("\nStarting mod generation thread...")
            update_status("Copying template files...")
            
            # Create custom progress callback that also updates status
            def progress_with_status(value):
                update_progress(value)
                if value < 0.3:
                    update_status("Copying template files...")
                elif value < 0.5:
                    update_status("Processing DDS texture...")
                elif value < 0.8:
                    update_status("Updating configuration files...")
                else:
                    update_status("Creating ZIP archive...")
            
            generate_mod(
                mod_name_var.get(),
                selected_carid,
                skin_name_var.get(),
                dds_path_var.get(),
                output_path=output_path,
                progress_callback=progress_with_status,
                author=author_var.get()
            )
            update_status("Export completed successfully!")
            print("Mod generation completed successfully!")
            print("="*50 + "\n")
            show_notification("✓ Mod created and installed successfully!", "success", 5000)
        except FileExistsError as e:
            update_status("Error: File already exists")
            print(f"ERROR: File already exists - {e}")
            show_notification(f"File already exists: {str(e)}", "error", 5000)
        except Exception as e:
            update_status("Error: Export failed")
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            show_notification(f"Error: {str(e)}", "error", 5000)
        finally:
            progress_bar.set(0)
            generate_button.configure(state="normal")
            # Hide progress bar and status after a short delay
            app.after(2000, lambda: progress_bar.pack_forget())
            app.after(2000, lambda: export_status_label.pack_forget())

    threading.Thread(target=thread_fn, daemon=True).start()

# -----------------------
# Header
# -----------------------
header_frame = ctk.CTkFrame(app, corner_radius=12, fg_color=colors["frame_bg"])
header_frame.pack(fill="x")
ctk.CTkLabel(header_frame, text="BeamSkin Studio", font=ctk.CTkFont(size=20, weight="bold"), text_color=colors["text"]).pack(padx=20, pady=10)

# -----------------------
# Global Notification System
# -----------------------
notification_label = ctk.CTkLabel(app, text="", font=ctk.CTkFont(size=12, weight="bold"), 
                                  fg_color=colors["card_bg"], corner_radius=8, height=40)
notification_label.pack_forget()

def show_notification(message, type="info", duration=3000):
    """
    Show a notification message at the top of the app
    type: "success", "error", "info", "warning"
    duration: how long to show in milliseconds (0 = don't auto-hide)
    """
    # Set color based on type
    if type == "success":
        bg_color = "#2D5F3F"  # Dark green
        text_color = "#39E09B"  # Light green
    elif type == "error":
        bg_color = "#5F2D2D"  # Dark red
        text_color = "#E03939"  # Light red
    elif type == "warning":
        bg_color = "#5F4F2D"  # Dark yellow
        text_color = "#E0B939"  # Light yellow
    else:  # info
        bg_color = colors["card_bg"]
        text_color = colors["accent"]
    
    notification_label.configure(text=message, fg_color=bg_color, text_color=text_color)
    notification_label.pack(fill="x", padx=20, pady=(10,0))
    
    # Auto-hide after duration if specified
    if duration > 0:
        app.after(duration, lambda: notification_label.pack_forget())

def hide_notification():
    """Manually hide the notification"""
    notification_label.pack_forget()

# -----------------------
# Tabs with spacing
# -----------------------
tabview = ctk.CTkTabview(app, segmented_button_fg_color=colors["frame_bg"], 
                         segmented_button_selected_color=colors["tab_selected"],
                         segmented_button_selected_hover_color=colors["tab_selected_hover"],
                         segmented_button_unselected_color=colors["tab_unselected"],
                         segmented_button_unselected_hover_color=colors["tab_unselected_hover"],
                         height=40)
tabview.pack(fill="both", expand=True, padx=20, pady=10)

# Configure tab button font size and text color
tabview._segmented_button.configure(
    font=ctk.CTkFont(size=13, weight="bold"),
    text_color=colors["text"],
    text_color_disabled=colors["text"]
)

generator_tab = tabview.add("    Generator    ")
howto_tab = tabview.add("    How to Use    ")
carlist_tab = tabview.add("    Car ID List    ")
settings_tab = tabview.add("    Settings    ")
about_tab = tabview.add("    About    ")

# -----------------------
# Generator Tab - Multi-Car/Multi-Skin System
# -----------------------

# Store the current project data
project_data = {
    "mod_name": "",
    "author": "",
    "cars": {}  # carid -> {"skins": [{"name": "skinname", "dds_path": "path"}], "temp_skin_name": "", "temp_dds_path": ""}
}

selected_car_for_skin = None  # Currently selected car for adding skins
current_project_widgets = []  # Store widget references for updates
vehicle_buttons = []
vehicle_panel_visible = False

def toggle_vehicle_panel():
    global vehicle_panel_visible
    if vehicle_panel_visible:
        vehicle_panel.pack_forget()
        vehicle_panel_visible = False
        select_vehicle_button.configure(
            text="Select Vehicle",
            fg_color=colors["card_bg"],
            hover_color=colors["card_hover"]
        )
    else:
        vehicle_panel.pack(fill="x", padx=10, pady=(0,10), after=vehicle_display_entry)
        vehicle_panel_visible = True
        vehicle_search_entry.focus_set()
        select_vehicle_button.configure(
            text="Close",
            fg_color=colors["error"],
            hover_color=colors["error_hover"]
        )

def select_vehicle(carid):
    global selected_carid
    
    # Store the actual carid globally
    selected_carid = carid
    
    # Find and display the car name
    display_name = carid
    for btn, cid, dname in vehicle_buttons:
        if cid == carid:
            display_name = dname
            break
    
    print(f"Vehicle selected: {display_name} (ID: {carid})")
    vehicle_display_var.set(display_name)  # Show the display name in UI
    
    # Update button colors
    for btn, cid, dname in vehicle_buttons:
        btn.configure(fg_color=colors["card_bg"] if cid != carid else "blue")
    
    toggle_vehicle_panel()

def update_vehicle_list(*args):
    query = vehicle_search_var.get().lower()
    for btn, carid, display_name in vehicle_buttons:
        btn.master.pack_forget()
        if query in carid.lower() or query in display_name.lower():
            btn.master.pack(fill="x", pady=3, padx=5)
    vehicle_scroll_frame._parent_canvas.yview_moveto(0)

def _on_vehicle_mousewheel(event):
    scroll_amount = int(-1 * (event.delta / 120) * 15)
    vehicle_scroll_frame._parent_canvas.yview_scroll(scroll_amount, "units")
    return "break"

def bind_tree(widget, event, callback):
    widget.bind(event, callback)
    for child in widget.winfo_children():
        bind_tree(child, event, callback)

def update_progress(value):
    if progress_bar.winfo_ismapped():
        progress_bar.set(value)

def clear_project():
    """Clear the current project"""
    global project_data, selected_car_for_skin
    project_data = {
        "mod_name": "",
        "author": "",
        "cars": {}
    }
    selected_car_for_skin = None
    mod_name_var.set("")
    author_var.set("")
    skin_name_var.set("")
    dds_path_var.set("")
    dds_preview_label.configure(text="Preview", image=None)
    refresh_project_display()
    show_notification("Project cleared", "info", 2000)

def save_project():
    """Save the current project to a file"""
    global project_data
    
    # Save current inputs before saving
    if selected_car_for_skin:
        save_current_car_inputs()
    
    # Update project data with current form values
    project_data["mod_name"] = mod_name_var.get()
    project_data["author"] = author_var.get()
    
    if not project_data["cars"]:
        show_notification("No cars in project to save", "warning", 3000)
        return
    
    # Ask for save location
    file_path = filedialog.asksaveasfilename(
        title="Save Project",
        defaultextension=".bsproject",
        filetypes=[("BeamSkin Project", "*.bsproject"), ("All Files", "*.*")]
    )
    
    if file_path:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4)
            show_notification(f"✓ Project saved to {os.path.basename(file_path)}", "success", 3000)
            print(f"Project saved to: {file_path}")
        except Exception as e:
            show_notification(f"Failed to save project: {str(e)}", "error", 4000)
            print(f"ERROR saving project: {e}")

def load_project():
    """Load a project from a file"""
    global project_data, selected_car_for_skin
    
    # Ask for file to load
    file_path = filedialog.askopenfilename(
        title="Load Project",
        filetypes=[("BeamSkin Project", "*.bsproject"), ("All Files", "*.*")]
    )
    
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            # Validate loaded data
            if "cars" not in loaded_data:
                show_notification("Invalid project file", "error", 3000)
                return
            
            # Check if all DDS files still exist
            missing_files = []
            for car_id, car_info in loaded_data["cars"].items():
                for skin in car_info.get("skins", []):
                    dds_path = skin.get("dds_path", "")
                    if dds_path and not os.path.exists(dds_path):
                        # Get car name for better error message
                        base_carid = car_info.get("base_carid", car_id)
                        car_name = VEHICLE_IDS.get(base_carid, base_carid)
                        for cid, cname in car_id_list:
                            if cid == base_carid:
                                car_name = cname
                                break
                        
                        missing_files.append({
                            "car": car_name,
                            "car_id": car_id,
                            "skin": skin.get("name", "Unknown"),
                            "path": dds_path
                        })
            
            # If there are missing files, show error and don't load
            if missing_files:
                error_message = "Cannot load project - Missing DDS files:\n\n"
                for missing in missing_files:
                    error_message += f"• {missing['car']} - Skin '{missing['skin']}':\n  {missing['path']}\n\n"
                
                messagebox.showerror(
                    "Missing Files",
                    error_message.strip()
                )
                print(f"Project load failed - Missing files:")
                for missing in missing_files:
                    print(f"  {missing['car']} ({missing['car_id']}) - {missing['skin']}: {missing['path']}")
                return
            
            # Load the project
            project_data = loaded_data
            selected_car_for_skin = None
            
            # Update form fields
            mod_name_var.set(project_data.get("mod_name", ""))
            author_var.set(project_data.get("author", ""))
            skin_name_var.set("")
            dds_path_var.set("")
            dds_preview_label.configure(text="Preview", image=None)
            
            # Refresh display
            refresh_project_display()
            
            car_count = len(project_data["cars"])
            total_skins = sum(len(car_info['skins']) for car_info in project_data['cars'].values())
            show_notification(f"✓ Loaded project: {car_count} cars, {total_skins} skins", "success", 4000)
            print(f"Project loaded from: {file_path}")
            
        except Exception as e:
            show_notification(f"Failed to load project: {str(e)}", "error", 4000)
            print(f"ERROR loading project: {e}")

def add_car_to_project():
    """Add selected car to the project (can add same car multiple times)"""
    global selected_car_for_skin
    
    if not selected_carid:
        show_notification("Please select a vehicle first", "error")
        return
    
    # Generate unique ID for this car instance (carid + counter)
    base_carid = selected_carid
    car_instance_id = base_carid
    counter = 1
    
    # Find unique instance ID if car already exists
    while car_instance_id in project_data["cars"]:
        counter += 1
        car_instance_id = f"{base_carid}_{counter}"
    
    # Add car with empty skins list and temp input fields
    project_data["cars"][car_instance_id] = {
        "base_carid": base_carid,  # Store original carid for generation
        "skins": [],
        "temp_skin_name": "",
        "temp_dds_path": ""
    }
    selected_car_for_skin = car_instance_id
    
    # Get car name
    car_name = VEHICLE_IDS.get(base_carid, base_carid)
    for cid, cname in car_id_list:
        if cid == base_carid:
            car_name = cname
            break
    
    instance_text = f" (Instance #{counter})" if counter > 1 else ""
    show_notification(f"✓ Added '{car_name}'{instance_text} to project", "success", 2000)
    refresh_project_display()
    load_car_inputs(car_instance_id)

def remove_car_from_project(carid):
    """Remove a car from the project"""
    global selected_car_for_skin
    
    if carid in project_data["cars"]:
        del project_data["cars"][carid]
        
        if selected_car_for_skin == carid:
            selected_car_for_skin = None
            # Clear inputs when removing selected car
            skin_name_var.set("")
            dds_path_var.set("")
            dds_preview_label.configure(text="Preview", image=None)
        
        show_notification(f"Removed '{carid}' from project", "info", 2000)
        refresh_project_display()

def save_current_car_inputs():
    """Save current input values to the selected car's temp storage"""
    if selected_car_for_skin and selected_car_for_skin in project_data["cars"]:
        project_data["cars"][selected_car_for_skin]["temp_skin_name"] = skin_name_var.get()
        project_data["cars"][selected_car_for_skin]["temp_dds_path"] = dds_path_var.get()

def load_car_inputs(carid):
    """Load saved input values for the specified car"""
    if carid in project_data["cars"]:
        skin_name_var.set(project_data["cars"][carid]["temp_skin_name"])
        dds_path_var.set(project_data["cars"][carid]["temp_dds_path"])
        
        # Update DDS preview
        if project_data["cars"][carid]["temp_dds_path"]:
            load_dds_preview(project_data["cars"][carid]["temp_dds_path"])
        else:
            dds_preview_label.configure(text="Preview", image=None)

def add_skin_to_car():
    """Add a skin to the currently selected car"""
    if not selected_car_for_skin:
        show_notification("Please select a car from the project first", "error")
        return
    
    skin_name = skin_name_var.get().strip()
    dds_path = dds_path_var.get().strip()
    
    if not skin_name:
        show_notification("Please enter a skin name", "error")
        return
    
    if not dds_path:
        show_notification("Please select a DDS file", "error")
        return
    
    # Add skin to the selected car
    project_data["cars"][selected_car_for_skin]["skins"].append({
        "name": skin_name,
        "dds_path": dds_path
    })
    
    # Clear inputs for this car
    skin_name_var.set("")
    dds_path_var.set("")
    project_data["cars"][selected_car_for_skin]["temp_skin_name"] = ""
    project_data["cars"][selected_car_for_skin]["temp_dds_path"] = ""
    dds_preview_label.configure(text="Preview", image=None)
    
    show_notification(f"✓ Added skin '{skin_name}' to {selected_car_for_skin}", "success", 2000)
    refresh_project_display()

def select_car_for_skin(carid):
    """Select a car to add skins to"""
    global selected_car_for_skin
    
    # Save current car's inputs before switching
    if selected_car_for_skin:
        save_current_car_inputs()
    
    selected_car_for_skin = carid
    
    # Load the new car's inputs
    load_car_inputs(carid)
    
    refresh_project_display()
    
    # Get car name
    car_name = VEHICLE_IDS.get(carid, carid)
    for cid, cname in car_id_list:
        if cid == carid:
            car_name = cname
            break
    
    show_notification(f"Selected '{car_name}' - Add skins below", "info", 2000)

def remove_skin_from_car(carid, skin_index):
    """Remove a skin from a car"""
    if carid in project_data["cars"]:
        skin = project_data["cars"][carid]["skins"][skin_index]
        project_data["cars"][carid]["skins"].pop(skin_index)
        show_notification(f"Removed skin '{skin['name']}' from {carid}", "info", 2000)
        refresh_project_display()

def refresh_project_display():
    """Refresh the project overview display"""
    # Clear existing widgets
    for widget in project_overview_frame.winfo_children():
        widget.destroy()
    
    if not project_data["cars"]:
        ctk.CTkLabel(
            project_overview_frame,
            text="No cars added yet. Select a vehicle and click 'Add Car to Project'.",
            text_color=colors["text_secondary"],
            font=ctk.CTkFont(size=12)
        ).pack(pady=20)
        return
    
    # Display each car and its skins
    for car_instance_id, car_info in project_data["cars"].items():
        # Get base carid (for multiple instances of same car)
        base_carid = car_info.get("base_carid", car_instance_id)
        
        # Get car name
        car_name = VEHICLE_IDS.get(base_carid, base_carid)
        for cid, cname in car_id_list:
            if cid == base_carid:
                car_name = cname
                break
        
        # Add instance number if this is a duplicate
        display_name = car_name
        if "_" in car_instance_id and car_instance_id != base_carid:
            instance_num = car_instance_id.split("_")[-1]
            display_name = f"{car_name} (Instance #{instance_num})"
        
        # Car card
        is_selected = (selected_car_for_skin == car_instance_id)
        car_card = ctk.CTkFrame(
            project_overview_frame,
            corner_radius=12,
            fg_color=colors["accent"] if is_selected else colors["card_bg"],
            border_width=2,
            border_color=colors["accent"] if is_selected else colors["border"],
            cursor="hand2"  # Show hand cursor
        )
        car_card.pack(fill="x", padx=5, pady=5)
        
        # Make entire card clickable
        car_card.bind("<Button-1>", lambda e, c=car_instance_id: select_car_for_skin(c))
        
        # Car header
        car_header = ctk.CTkFrame(car_card, fg_color="transparent", cursor="hand2")
        car_header.pack(fill="x", padx=8, pady=6)
        car_header.bind("<Button-1>", lambda e, c=car_instance_id: select_car_for_skin(c))
        
        car_label = ctk.CTkLabel(
            car_header,
            text=f"🚗 {display_name} ({base_carid})",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["accent_text"] if is_selected else colors["text"],
            anchor="w",
            cursor="hand2"
        )
        car_label.pack(side="left", fill="x", expand=True)
        car_label.bind("<Button-1>", lambda e, c=car_instance_id: select_car_for_skin(c))
        
        # Selected indicator (no select button needed - just visual indicator)
        if is_selected:
            selected_indicator = ctk.CTkLabel(
                car_header,
                text="● Selected",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=colors["accent_text"]
            )
            selected_indicator.pack(side="right", padx=5)
            selected_indicator.bind("<Button-1>", lambda e, c=car_instance_id: select_car_for_skin(c))
        
        # Remove car button (prevent click propagation)
        remove_car_btn = ctk.CTkButton(
            car_header,
            text="Remove",
            width=80,
            height=28,
            fg_color=colors["error"],
            hover_color=colors["error_hover"],
            text_color=colors["accent_text"],
            command=lambda c=car_instance_id: remove_car_from_project(c)
        )
        remove_car_btn.pack(side="right", padx=5)
        
        # Skins list
        skins_frame = ctk.CTkFrame(car_card, fg_color="transparent", cursor="hand2")
        skins_frame.pack(fill="x", padx=8, pady=(0, 8))
        skins_frame.bind("<Button-1>", lambda e, c=car_instance_id: select_car_for_skin(c))
        
        if not car_info["skins"]:
            no_skins_label = ctk.CTkLabel(
                skins_frame,
                text="No skins added yet - Click to add skins",
                text_color=colors["text_secondary"] if not is_selected else colors["accent_text"],
                font=ctk.CTkFont(size=11),
                cursor="hand2"
            )
            no_skins_label.pack(anchor="w", padx=5, pady=3)
            no_skins_label.bind("<Button-1>", lambda e, c=car_instance_id: select_car_for_skin(c))
        else:
            for idx, skin in enumerate(car_info["skins"]):
                skin_row = ctk.CTkFrame(skins_frame, corner_radius=8, fg_color=colors["frame_bg"], cursor="hand2")
                skin_row.pack(fill="x", pady=2, padx=5)
                skin_row.bind("<Button-1>", lambda e, c=car_instance_id: select_car_for_skin(c))
                
                skin_label = ctk.CTkLabel(
                    skin_row,
                    text=f"  • {skin['name']}",
                    text_color=colors["text"],
                    anchor="w",
                    font=ctk.CTkFont(size=11),
                    cursor="hand2"
                )
                skin_label.pack(side="left", fill="x", expand=True, padx=5, pady=5)
                skin_label.bind("<Button-1>", lambda e, c=car_instance_id: select_car_for_skin(c))
                
                remove_skin_btn = ctk.CTkButton(
                    skin_row,
                    text="Remove",
                    width=70,
                    height=24,
                    fg_color=colors["error"],
                    hover_color=colors["error_hover"],
                    text_color=colors["accent_text"],
                    font=ctk.CTkFont(size=10),
                    command=lambda c=car_instance_id, i=idx: remove_skin_from_car(c, i)
                )
                remove_skin_btn.pack(side="right", padx=5, pady=3)
    
    # Update the current car label
    update_current_car_label()

def generate_multi_skin_mod():
    """Generate the mod with all cars and skins"""
    global project_data
    
    print("\n" + "="*50)
    print("MULTI-SKIN MOD GENERATION INITIATED")
    print("="*50)
    
    # Validation
    mod_name = mod_name_var.get().strip()
    author_name = author_var.get().strip()
    
    if not mod_name:
        show_notification("Please enter a ZIP name", "error")
        return
    
    if not project_data["cars"]:
        show_notification("Please add at least one car to the project", "error")
        return
    
    # Check if all cars have at least one skin
    cars_without_skins = []
    for carid, car_info in project_data["cars"].items():
        if not car_info["skins"]:
            cars_without_skins.append(carid)
    
    if cars_without_skins:
        show_notification(f"Please add skins to: {', '.join(cars_without_skins)}", "error", 4000)
        return
    
    output_path = custom_output_var.get() if output_mode_var.get() == "custom" else None
    
    # Update project data
    project_data["mod_name"] = mod_name
    project_data["author"] = author_name if author_name else "Unknown"
    
    print(f"Mod Name: {mod_name}")
    print(f"Author: {project_data['author']}")
    print(f"Cars: {len(project_data['cars'])}")
    total_skins = sum(len(car_info['skins']) for car_info in project_data['cars'].values())
    print(f"Total Skins: {total_skins}")
    
    export_status_label.configure(text="Preparing to export...")
    export_status_label.pack(padx=20, pady=(10,5))
    progress_bar.pack(fill="x", padx=20, pady=(0,5))
    progress_bar.set(0)
    generate_button.configure(state="disabled")

    def update_status(message):
        """Update the status label text"""
        export_status_label.configure(text=message)

    def thread_fn():
        try:
            print("\nStarting mod generation thread...")
            update_status("Processing skins...")
            
            # Create custom progress callback
            def progress_with_status(value):
                update_progress(value)
                if value < 0.3:
                    update_status("Copying template files...")
                elif value < 0.7:
                    update_status(f"Processing {total_skins} skins...")
                else:
                    update_status("Creating ZIP archive...")
            
            # Import and call the multi-skin generator
            from file_ops import generate_multi_skin_mod as gen_multi
            gen_multi(
                project_data,
                output_path=output_path,
                progress_callback=progress_with_status
            )
            
            update_status("Export completed successfully!")
            print("Mod generation completed successfully!")
            print("="*50 + "\n")
            show_notification(f"✓ Mod '{mod_name}' created with {total_skins} skins!", "success", 5000)
            
            # Ask if user wants to clear project
            app.after(2000, lambda: show_notification("Project kept. Click 'Clear Project' to start new one.", "info", 4000))
            
        except FileExistsError as e:
            update_status("Error: File already exists")
            print(f"ERROR: File already exists - {e}")
            show_notification(f"File already exists: {str(e)}", "error", 5000)
        except Exception as e:
            update_status("Error: Export failed")
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            show_notification(f"Error: {str(e)}", "error", 5000)
        finally:
            progress_bar.set(0)
            generate_button.configure(state="normal")
            # Hide progress bar and status after a short delay
            app.after(2000, lambda: progress_bar.pack_forget())
            app.after(2000, lambda: export_status_label.pack_forget())

    threading.Thread(target=thread_fn, daemon=True).start()

# Build the Generator Tab UI - wrapped in scrollable frame
generator_scroll = ctk.CTkScrollableFrame(generator_tab, fg_color="transparent")
generator_scroll.pack(fill="both", expand=True, padx=0, pady=0)

ctk.CTkLabel(generator_scroll, text="Project Settings", font=ctk.CTkFont(size=14, weight="bold"), text_color=colors["text"]).pack(anchor="w", padx=10, pady=(10,0))

# Mod name and author in a frame
settings_frame = ctk.CTkFrame(generator_scroll, corner_radius=12, fg_color=colors["frame_bg"])
settings_frame.pack(fill="x", padx=10, pady=(5,10))

ctk.CTkLabel(settings_frame, text="ZIP Name:", text_color=colors["text"]).grid(row=0, column=0, padx=10, pady=5, sticky="w")
ctk.CTkEntry(settings_frame, textvariable=mod_name_var, fg_color=colors["card_bg"], text_color=colors["text"]).grid(row=0, column=1, padx=10, pady=5, sticky="ew")

ctk.CTkLabel(settings_frame, text="Author:", text_color=colors["text"]).grid(row=1, column=0, padx=10, pady=5, sticky="w")
ctk.CTkEntry(settings_frame, textvariable=author_var, fg_color=colors["card_bg"], text_color=colors["text"]).grid(row=1, column=1, padx=10, pady=5, sticky="ew")

settings_frame.columnconfigure(1, weight=1)

# Vehicle selection and add to project
ctk.CTkLabel(generator_scroll, text="Add Vehicles to Project", font=ctk.CTkFont(size=14, weight="bold"), text_color=colors["text"]).pack(anchor="w", padx=10, pady=(10,0))

ctk.CTkLabel(generator_scroll, text="Selected Vehicle:", text_color=colors["text"], font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,0))
vehicle_display_entry = ctk.CTkEntry(generator_scroll, textvariable=vehicle_display_var, state="readonly", fg_color=colors["card_bg"], text_color=colors["text"])
vehicle_display_entry.pack(fill="x", padx=10, pady=(0,5))

vehicle_buttons_frame = ctk.CTkFrame(generator_scroll, fg_color="transparent")
vehicle_buttons_frame.pack(fill="x", padx=10, pady=(0,10))

select_vehicle_button = ctk.CTkButton(vehicle_buttons_frame, text="Select Vehicle", command=toggle_vehicle_panel, fg_color=colors["card_bg"], hover_color=colors["card_hover"], text_color=colors["text"])
select_vehicle_button.pack(side="left", fill="x", expand=True, padx=(0,5))

add_car_button = ctk.CTkButton(vehicle_buttons_frame, text="Add Car to Project", command=add_car_to_project, fg_color=colors["accent"], hover_color=colors["accent_hover"], text_color=colors["accent_text"])
add_car_button.pack(side="right", fill="x", expand=True, padx=(5,0))

vehicle_panel = ctk.CTkFrame(generator_scroll, corner_radius=12, fg_color=colors["frame_bg"])
vehicle_panel.pack_forget()
vehicle_search_var = ctk.StringVar()
vehicle_search_var.trace_add("write", update_vehicle_list)
vehicle_search_entry = ctk.CTkEntry(vehicle_panel, textvariable=vehicle_search_var, placeholder_text="Search for your vehicle here", placeholder_text_color=colors["text_secondary"], fg_color=colors["card_bg"], text_color=colors["text"])
vehicle_search_entry.pack(fill="x", padx=5, pady=5)

vehicle_scroll_frame = ctk.CTkScrollableFrame(vehicle_panel, height=150, corner_radius=12, fg_color=colors["frame_bg"])
vehicle_scroll_frame.pack(fill="x", padx=5, pady=5)
vehicle_scroll_frame.bind("<Enter>", lambda e: bind_tree(vehicle_scroll_frame, "<MouseWheel>", _on_vehicle_mousewheel))
vehicle_scroll_frame.bind("<Leave>", lambda e: vehicle_scroll_frame.unbind_all("<MouseWheel>"))

# Vehicle buttons in card style
sorted_vehicles = sorted(VEHICLE_IDS.keys(), key=lambda carid: VEHICLE_IDS[carid].lower())
for carid in sorted_vehicles:
    row_frame = ctk.CTkFrame(vehicle_scroll_frame, corner_radius=12, fg_color=colors["frame_bg"])
    row_frame.pack(fill="x", pady=3, padx=5)

    display_name = VEHICLE_IDS[carid]
    
    btn = ctk.CTkButton(
        row_frame,
        text=display_name,
        command=lambda c=carid: select_vehicle(c),
        fg_color=colors["card_bg"],
        hover_color=colors["card_hover"],
        height=35,
        corner_radius=12,
        text_color=colors["text"]
    )
    btn.pack(fill="x", padx=8, pady=6)
    
    btn.bind("<Enter>", lambda e, c=carid, w=btn: schedule_hover_preview(c, w))
    btn.bind("<Leave>", lambda e: hide_hover_preview())
    
    vehicle_buttons.append((btn, carid, display_name))

# Set initial button colors
for btn, carid, display_name in vehicle_buttons:
    btn.configure(fg_color=colors["card_bg"] if carid != selected_carid else "blue")

# Project Overview
ctk.CTkLabel(generator_scroll, text="Project Overview", font=ctk.CTkFont(size=14, weight="bold"), text_color=colors["text"]).pack(anchor="w", padx=10, pady=(10,5))

project_controls_frame = ctk.CTkFrame(generator_scroll, fg_color="transparent")
project_controls_frame.pack(fill="x", padx=10, pady=(0,5))

save_project_btn = ctk.CTkButton(
    project_controls_frame,
    text="💾 Save Project",
    command=save_project,
    fg_color=colors["accent"],
    hover_color=colors["accent_hover"],
    text_color=colors["accent_text"],
    width=120
)
save_project_btn.pack(side="left", padx=(0,5))

load_project_btn = ctk.CTkButton(
    project_controls_frame,
    text="📁 Load Project",
    command=load_project,
    fg_color=colors["accent"],
    hover_color=colors["accent_hover"],
    text_color=colors["accent_text"],
    width=120
)
load_project_btn.pack(side="left", padx=5)

clear_project_btn = ctk.CTkButton(
    project_controls_frame,
    text="Clear Project",
    command=clear_project,
    fg_color=colors["error"],
    hover_color=colors["error_hover"],
    text_color=colors["accent_text"],
    width=120
)
clear_project_btn.pack(side="right")

project_overview_frame = ctk.CTkScrollableFrame(generator_scroll, height=150, corner_radius=12, fg_color=colors["frame_bg"])
project_overview_frame.pack(fill="x", padx=10, pady=(0,10))

# Add Skin Section
current_car_label = ctk.CTkLabel(generator_scroll, text="", font=ctk.CTkFont(size=14, weight="bold"), text_color=colors["accent"])

def update_current_car_label():
    """Update the label showing which car is selected"""
    if selected_car_for_skin and selected_car_for_skin in project_data["cars"]:
        # Get base carid
        base_carid = project_data["cars"][selected_car_for_skin].get("base_carid", selected_car_for_skin)
        
        # Get car name
        car_name = VEHICLE_IDS.get(base_carid, base_carid)
        for cid, cname in car_id_list:
            if cid == base_carid:
                car_name = cname
                break
        
        # Add instance number if applicable
        display_text = f"{car_name} ({base_carid})"
        if "_" in selected_car_for_skin and selected_car_for_skin != base_carid:
            instance_num = selected_car_for_skin.split("_")[-1]
            display_text = f"{car_name} - Instance #{instance_num} ({base_carid})"
        
        current_car_label.configure(text=f"Adding Skins to: {display_text}")
        current_car_label.pack(anchor="w", padx=10, pady=(10,0))
    else:
        current_car_label.pack_forget()

ctk.CTkLabel(generator_scroll, text="Add Skins to Selected Car", font=ctk.CTkFont(size=14, weight="bold"), text_color=colors["text"]).pack(anchor="w", padx=10, pady=(10,5))

skin_input_frame = ctk.CTkFrame(generator_scroll, corner_radius=12, fg_color=colors["frame_bg"])
skin_input_frame.pack(fill="x", padx=10, pady=(0,10))

ctk.CTkLabel(skin_input_frame, text="Skin Name:", text_color=colors["text"], font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,0))
ctk.CTkEntry(skin_input_frame, textvariable=skin_name_var, fg_color=colors["card_bg"], text_color=colors["text"]).pack(fill="x", padx=10, pady=(0,10))

ctk.CTkLabel(skin_input_frame, text="DDS Texture:", text_color=colors["text"], font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,0))
dds_frame = ctk.CTkFrame(skin_input_frame, fg_color="transparent")
dds_frame.pack(fill="x", padx=10, pady=(0,10))
dds_entry = ctk.CTkEntry(dds_frame, textvariable=dds_path_var, state="readonly", fg_color=colors["card_bg"], text_color=colors["text"])
dds_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
dds_button = ctk.CTkButton(dds_frame, text="Browse", width=80, command=select_dds, fg_color=colors["card_bg"], hover_color=colors["card_hover"], text_color=colors["text"])
dds_button.pack(side="right")

dds_preview_label = ctk.CTkLabel(skin_input_frame, text="Preview", fg_color=colors["frame_bg"], corner_radius=12, width=150, height=150, text_color=colors["text"])
dds_preview_label.pack(padx=10, pady=(0,5))

add_skin_button = ctk.CTkButton(skin_input_frame, text="Add Skin to Selected Car", command=add_skin_to_car, 
                                fg_color=colors["accent"], hover_color=colors["accent_hover"], text_color=colors["accent_text"],
                                height=35, font=ctk.CTkFont(size=13, weight="bold"))
add_skin_button.pack(fill="x", padx=10, pady=(0,5))

# Output
ctk.CTkLabel(generator_scroll, text="Output Location", font=ctk.CTkFont(size=12, weight="bold"), text_color=colors["text"]).pack(anchor="w", padx=10, pady=(10,5))
output_frame = ctk.CTkFrame(generator_scroll, fg_color="transparent")
output_frame.pack(fill="x", padx=10, pady=(0,10))

steam_radio = ctk.CTkRadioButton(
    output_frame,
    text="Steam (Default Mod folder location)",
    variable=output_mode_var,
    value="steam",
    text_color=colors["text"]
)
steam_radio.pack(anchor="w", pady=2)

custom_radio = ctk.CTkRadioButton(
    output_frame,
    text="Custom Location",
    variable=output_mode_var,
    value="custom",
    text_color=colors["text"]
)
custom_radio.pack(anchor="w", pady=2)

custom_output_frame = ctk.CTkFrame(output_frame, corner_radius=12, fg_color=colors["frame_bg"])
custom_output_frame.pack_forget()

custom_output_entry = ctk.CTkEntry(custom_output_frame, textvariable=custom_output_var, state="readonly", fg_color=colors["card_bg"], text_color=colors["text"])
custom_output_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)

custom_browse_button = ctk.CTkButton(custom_output_frame, text="Browse", width=80, command=select_custom_output, fg_color=colors["card_bg"], hover_color=colors["card_hover"], text_color=colors["text"])
custom_browse_button.pack(side="right", padx=5, pady=5)

steam_radio.configure(command=update_output_mode)
custom_radio.configure(command=update_output_mode)

# Export status and progress
export_status_label = ctk.CTkLabel(generator_scroll, text="", text_color=colors["text"], font=ctk.CTkFont(size=12))
export_status_label.pack(padx=20, pady=(10,5))
export_status_label.pack_forget()

progress_bar = ctk.CTkProgressBar(generator_scroll)
progress_bar.pack_forget()

generate_button = ctk.CTkButton(generator_scroll, text="Generate Mod", height=40, command=generate_multi_skin_mod,
                                font=ctk.CTkFont(size=14, weight="bold"), fg_color=colors["accent"], hover_color=colors["accent_hover"], text_color=colors["accent_text"])
generate_button.pack(padx=20, pady=10, fill="x")

# Initialize display
refresh_project_display()

# -----------------------
# How to Use Tab
# -----------------------

# Create a frame to hold the chapter buttons and content
howto_main_frame = ctk.CTkFrame(howto_tab, fg_color="transparent")
howto_main_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Chapter navigation frame at the top - TWO ROWS
chapter_nav_frame = ctk.CTkFrame(
    howto_main_frame, 
    fg_color=colors["frame_bg"], 
    corner_radius=12
)
chapter_nav_frame.pack(fill="x", pady=(0,10))

# Create two row frames inside the navigation frame
row1_frame = ctk.CTkFrame(chapter_nav_frame, fg_color="transparent")
row1_frame.pack(fill="x", padx=5, pady=(10, 5))

row2_frame = ctk.CTkFrame(chapter_nav_frame, fg_color="transparent")
row2_frame.pack(fill="x", padx=5, pady=(5, 10))

# Content frame
howto_text = ctk.CTkTextbox(howto_main_frame, width=580, height=900,
                            font=ctk.CTkFont(size=14, weight="bold"), fg_color=colors["frame_bg"], text_color=colors["text"])
howto_text.pack(fill="both", expand=True)

# Chapter content dictionary
chapters = {
    "Chapter 1": ("Skin Modding Basics", """
────────────────────────────
Chapter 1: Skin Modding Basics
────────────────────────────

Before using the tool, you need to create your skin texture.

Recommended Programs
- Paint.NET (Free – recommended for beginners)
- Adobe Photoshop (Paid – requires a DDS plugin)

Required File Format
Your skin must be saved as a .DDS file.
Other formats (PNG, JPG, etc.) will not work.

DDS File Naming:
carid_skin_Skinname.dds

Naming Breakdown
- carid – Vehicle identifier (single word).
  - You can find the correct carid in the "Car ID List" tab.
- skin – Must stay exactly as written
- Skinname – One word, no spaces

Incorrect file names will cause the skin to not load.
"""),
    "Chapter 2": ("Using the Generator Tab", """
────────────────────────────
Chapter 2: Using the Generator Tab
────────────────────────────

The Generator tab uses a multi-car, multi-skin project system.
You can add multiple vehicles and multiple skins per vehicle,
then export everything into a single mod ZIP file.

Project Settings:

ZIP Name
- One word only
- No spaces or special characters
- This becomes the mod filename
Example: MyCoolSkins

Author
- Your name or creator name
- Appears in all skin information
- Spaces allowed

Adding Vehicles to Project:

1. Click "Select Vehicle" to open the vehicle selector
2. Search for your vehicle by name or car ID
3. Click the vehicle to select it
4. Click "Add Car to Project"
5. The vehicle appears in the Project Overview

You can add the same vehicle multiple times if you want
different sets of skins organized separately.

Adding Skins to Vehicles:

1. Click on a vehicle card in the Project Overview
   to select it for adding skins
2. Enter the Skin Name (display name shown in-game)
   • Spaces allowed
   • Example: My Cool Racing Skin
3. Click Browse and select your .dds file
4. Click "Add Skin to Selected Car"

You can add as many skins as you want to each vehicle.

Project Management:

- Save Project: Save your current work to a .bsproject file
  to continue later
- Load Project: Load a previously saved project
- Clear Project: Start fresh (removes all cars and skins)

Generate Mod:

Once you've added all vehicles and skins:
1. Review your project in the Project Overview
2. Choose output location (Steam or Custom)
3. Click "Generate Mod"

The tool will create a single ZIP file containing all
your skins for all vehicles.
"""),
    "Chapter 3": ("Output Location", """
────────────────────────────
Chapter 3: Output Location
────────────────────────────

Steam (Default)
Exports automatically to:
C:\\Users\\username\\AppData\\Local\\BeamNG\\BeamNG.drive\\current\\mods

Custom Location
Choose your own folder for exporting.
Useful if you have a custom mod directory or want to 
organize your mods differently.
"""),
    "Chapter 4": ("Car ID List", """
────────────────────────────
Chapter 4: Car ID List
────────────────────────────

The Car ID List tab shows all available vehicles.
- Search by car name or car ID
- Click "Copy ID" to copy the car ID to clipboard
- Hover over any vehicle to see a preview image
- Use this when naming your DDS files
"""),
    "Chapter 5": ("Developer Mode", """
────────────────────────────
Chapter 5: Developer Mode (Advanced)
────────────────────────────

Developer Mode allows you to add custom vehicles 
that aren't in the default list.

⚠️ IMPORTANT: Getting the Correct Car ID

The Car ID MUST be exactly correct, or skins won't work.

How to Find the Correct Car ID:
1. Launch BeamNG.drive
2. Load into any map
3. Spawn the vehicle you want to add
4. Open the console (~ key)
5. Look for the message: "Vehicle replaced: carid"
6. The text shown is your exact Car ID

Example console output:
"Vehicle replaced: civetta_scintilla"
Your Car ID is: civetta_scintilla

To Enable Developer Mode:
1. Go to Settings tab
2. Toggle "Developer Mode" on
3. A new "Developer" tab will appear

Adding Custom Vehicles:
1. Get the exact Car ID from BeamNG console (see above)
2. Enter the Car ID exactly as shown (case-sensitive)
   • No spaces
   • Must match console output exactly
3. Enter the Car Name (how it appears in menus)
   • This can be anything you want
   • Spaces allowed
4. Select the vehicle's JSON file (materials.json)
5. Select the vehicle's JBEAM file (.jbeam skin file)
6. (Optional) Select a preview image (.jpg only)
7. Click "Add Vehicle"

What the Tool Does Automatically:
- Identifies the canonical skin variant
- Removes alternative skin variants
- Removes palette-based color logic
- Updates material paths for the new vehicle
- Creates the necessary folder structure
- Processes JSON and JBEAM files
- Adds the vehicle to all menus
- Saves it for future sessions

The tool keeps only the FIRST skin variant found in
your files and removes all others. It also removes
color palette logic that could interfere with custom
skins.

Managing Custom Vehicles:
- View all added vehicles in the Developer tab
- Search added vehicles by name or ID
- Delete vehicles you no longer need
- Hover over vehicles to see preview images
- Changes are saved automatically

Where to Find Vehicle Files:
Vehicle JSON and JBEAM files are typically found in:
C:\\Program Files (x86)\\Steam\\steamapps\\common\\BeamNG.drive\\content\\vehicles\\

Look in the vehicle's folder, then in the "skin" subfolder:
- materials.json (or similar .json file)
- .jbeam file (usually named vehicleid_skin.jbeam)

Preview Images (Optional):
If you want hover previews for your custom vehicle:
- Use a .jpg or .jpeg image
- The tool will copy it to the correct location
- Recommended size: 400x400 or larger
"""),
    "Chapter 6": ("Debug Mode", """
────────────────────────────
Chapter 6: Debug Mode (Advanced)
────────────────────────────

Debug Mode is available when Developer Mode is enabled.
It opens a separate console window showing detailed 
information about what the tool is doing.

To Enable Debug Mode:
1. Enable Developer Mode first
2. Toggle "Debug Mode" in Settings
3. A debug console window will open

What Debug Mode Shows:
- Vehicle selections and additions
- File operations and processing
- JSON/JBEAM editing details
- Canonical skin detection
- Variant removal operations
- Mod generation progress
- Detailed error messages
- All developer actions

Useful For:
- Troubleshooting issues
- Understanding processing steps
- Seeing which skin variants were kept/removed
- Verifying correct Car ID
- Reporting bugs to the developer

The debug console has a "Clear" button to remove 
old messages. Closing the console automatically 
disables debug mode.
"""),
    "Chapter 7": ("Theme Settings", """
────────────────────────────
Chapter 7: Theme Settings
────────────────────────────

You can switch between Dark Mode and Light Mode 
in the Settings tab.

Your theme preference is automatically saved and 
will be remembered when you restart the app.

⚠️ Note: After changing the theme, you'll need to 
restart the application for it to fully apply.
The tool will ask for confirmation before restarting.
"""),
    "Chapter 8": ("Tips & Troubleshooting", """
────────────────────────────
Chapter 8: Tips & Troubleshooting
────────────────────────────

Skin Not Appearing In-Game?
- Verify DDS filename matches the carid EXACTLY
- Check that the ZIP name doesn't already exist
- Restart BeamNG.drive after adding the mod
- Check the mod is in the correct mods folder
- Make sure you selected the correct vehicle in the project

DDS File Issues?
- Ensure you're using DDS format (not PNG/JPG)
- Use BC3/DXT5 compression for best compatibility
- Resolution should be power of 2 (1024, 2048, 4096)
- File name format: carid_skin_skinname.dds

Custom Vehicle Not Working?
- Verify the Car ID is EXACTLY as shown in BeamNG console
- Check "Vehicle replaced: carid" message in-game
- The Car ID is case-sensitive and must match exactly
- Verify JSON and JBEAM files are from the correct vehicle
- Make sure you selected files from the "skin" subfolder
- Enable Debug Mode to see detailed processing information
- Check if canonical skin was detected correctly

Car ID Verification:
If you're unsure about the Car ID:
1. Load BeamNG.drive
2. Spawn the vehicle
3. Open console (~ key)
4. Look for "Vehicle replaced: exactcarid"
5. Use that exact text as your Car ID

ZIP Already Exists Error?
- Choose a different ZIP name
- Delete the old ZIP from the mods folder
- The tool prevents overwriting existing mods

Preview Images Not Showing?
- Make sure you selected a .jpg or .jpeg file
- The image should be at least 400x400 pixels
- Hover over the vehicle card for 1 second to see preview
- Check that the image was added when creating the vehicle

Project Files:
- Save your projects regularly using "Save Project"
- Project files use .bsproject extension
- Projects remember all vehicles and skins
- Load saved projects to continue work later

Performance Tips:
- Close unused tabs to save memory
- Clear debug console regularly if using Debug Mode
- Organize your DDS files in folders by vehicle
- Save projects before generating large mods
"""),
    "Chapter 9": ("Understanding the Processing", """
────────────────────────────
Chapter 9: Understanding the Processing
────────────────────────────

When you add a custom vehicle, the tool automatically
processes the JSON and JBEAM files:

JSON Processing:
1. Finds the first .skin.<variant> in the file
2. That variant becomes the "canonical" skin
3. Removes ALL other skin variants
4. Removes color palette logic (colorPaletteMap, etc.)
5. Updates material names and paths
6. Preserves all other settings exactly

JBEAM Processing:
1. Finds the first _skin_ entry in the file
2. Keeps only that entry, removes all others
3. Updates skin name to placeholder
4. Updates author and skin name fields
5. Preserves all other settings (value, slotType, etc.)

This ensures your custom skins work correctly without
interference from palette systems or multiple variants.

Enable Debug Mode to see exactly what the tool is doing
during processing.
"""),
    "Chapter 10": ("Final Notes", """
────────────────────────────
Chapter 10: Final Notes
────────────────────────────

- Always verify the Car ID using the BeamNG console
- Double-check all names before generating
- Keep backups of your original DDS files
- Save projects regularly to avoid losing work
- Test skins in-game before sharing
- Join the BeamNG modding community for help

Additional Resources:
- BeamNG Forums: forum.beamng.com
- BeamNG Documentation: documentation.beamng.com
- Modding Discord servers

You are now ready to create amazing skins!

────────────────────────────
""")
}

# Store chapter buttons for styling
chapter_buttons = []

def load_chapter(chapter_key):
    """Load a specific chapter into the text box"""
    chapter_title, chapter_content = chapters[chapter_key]
    howto_text.configure(state="normal")
    howto_text.delete("0.0", "end")
    howto_text.insert("0.0", chapter_content)
    howto_text.configure(state="disabled")
    
    # Update button colors
    for btn, key in chapter_buttons:
        if key == chapter_key:
            btn.configure(fg_color=colors["accent"], text_color=colors["accent_text"])
        else:
            btn.configure(fg_color=colors["card_bg"], text_color=colors["text"])
    
    print(f"Loaded: {chapter_key} - {chapter_title}")

def load_all_chapters():
    """Load all chapters into the text box"""
    howto_text.configure(state="normal")
    howto_text.delete("0.0", "end")
    
    # Add a header
    howto_text.insert("0.0", """How to Use Guide

This guide will walk you through the basics of creating a skin and using the modding tool to package it correctly.
Follow each chapter carefully to ensure your skin works in-game.

Use the chapter buttons above to jump to specific sections, or scroll through all chapters below.

""")
    
    # Add all chapters
    for chapter_key in sorted(chapters.keys(), key=lambda x: int(x.split()[1])):
        chapter_title, chapter_content = chapters[chapter_key]
        howto_text.insert("end", chapter_content)
        howto_text.insert("end", "\n")
    
    howto_text.configure(state="disabled")
    
    # Reset button colors
    for btn, key in chapter_buttons:
        btn.configure(fg_color=colors["card_bg"], text_color=colors["text"])
    
    print("Loaded all chapters")

# Create "View All" button in first row
view_all_btn = ctk.CTkButton(
    row1_frame,
    text="📖 View All Chapters",
    command=load_all_chapters,
    width=150,
    height=35,
    fg_color=colors["card_bg"],
    hover_color=colors["card_hover"],
    text_color=colors["text"],
    font=ctk.CTkFont(size=12, weight="bold"),
    corner_radius=8
)
view_all_btn.pack(side="left", padx=5)

# Create chapter navigation buttons - SORTED NUMERICALLY
# Split chapters into two rows (View All + 5 chapters in row 1, 5 chapters in row 2)
sorted_chapters = sorted(chapters.keys(), key=lambda x: int(x.split()[1]))

# First row: View All + Chapters 1-5
for chapter_key in sorted_chapters[:5]:
    chapter_title, _ = chapters[chapter_key]
    
    btn = ctk.CTkButton(
        row1_frame,
        text=chapter_title,
        command=lambda k=chapter_key: load_chapter(k),
        width=150,
        height=35,
        fg_color=colors["card_bg"],
        hover_color=colors["card_hover"],
        text_color=colors["text"],
        font=ctk.CTkFont(size=11),
        corner_radius=8
    )
    btn.pack(side="left", padx=5)
    chapter_buttons.append((btn, chapter_key))

# Second row: Chapters 6-10
for chapter_key in sorted_chapters[5:]:
    chapter_title, _ = chapters[chapter_key]
    
    btn = ctk.CTkButton(
        row2_frame,
        text=chapter_title,
        command=lambda k=chapter_key: load_chapter(k),
        width=150,
        height=35,
        fg_color=colors["card_bg"],
        hover_color=colors["card_hover"],
        text_color=colors["text"],
        font=ctk.CTkFont(size=11),
        corner_radius=8
    )
    btn.pack(side="left", padx=5)
    chapter_buttons.append((btn, chapter_key))

# Load all chapters by default
load_all_chapters()

# -----------------------
# Car ID List Tab
# -----------------------
carlist_search_var = ctk.StringVar()
carlist_search_entry = ctk.CTkEntry(
    carlist_tab,
    textvariable=carlist_search_var,
    placeholder_text="Search Car ID...",
    placeholder_text_color=colors["text_secondary"],
    fg_color=colors["card_bg"],
    text_color=colors["text"]
)
carlist_search_entry.pack(fill="x", padx=10, pady=(10,5))

carlist_scroll = ctk.CTkScrollableFrame(carlist_tab, fg_color=colors["frame_bg"])
carlist_scroll.pack(fill="both", expand=True, padx=10, pady=10)

def _on_carlist_mousewheel(event):
    scroll_amount = int(-1 * (event.delta / 120) * 15)
    carlist_scroll._parent_canvas.yview_scroll(scroll_amount, "units")
    return "break"

carlist_scroll.bind("<Enter>", lambda e: bind_tree(carlist_scroll, "<MouseWheel>", _on_carlist_mousewheel))
carlist_scroll.bind("<Leave>", lambda e: carlist_scroll.unbind_all("<MouseWheel>"))

carlist_font = ctk.CTkFont(size=14, weight="bold")
carlist_items = []

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

def copy_carid(carid):
    app.clipboard_clear()
    app.clipboard_append(carid)
    show_notification(f"✓ Car ID '{carid}' copied to clipboard!", "success", 2000)

def bind_hover(frame, widgets, normal_color=None, hover_color=None):
    if normal_color is None:
        normal_color = colors["card_bg"]
    if hover_color is None:
        hover_color = colors["card_hover"]
        
    def on_enter(e):
        frame.configure(fg_color=hover_color)
    def on_leave(e):
        frame.configure(fg_color=normal_color)
    
    frame.bind("<Enter>", on_enter)
    frame.bind("<Leave>", on_leave)
    for w in widgets:
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)

for carid, name in car_id_list:
    card_frame = ctk.CTkFrame(
        carlist_scroll,
        corner_radius=12,
        fg_color=colors["card_bg"],
        border_width=1,
        border_color=colors["border"]
    )
    card_frame.pack(fill="x", pady=8, padx=8)

    inner_frame = ctk.CTkFrame(
        card_frame,
        corner_radius=12,
        fg_color=colors["card_bg"],
        border_width=0
    )
    inner_frame.pack(fill="x", padx=5, pady=5)

    lbl = ctk.CTkLabel(
        inner_frame,
        text=f"{carid}  —  {name}",
        anchor="w",
        justify="left",
        font=carlist_font,
        text_color=colors["text"]
    )
    lbl.pack(side="left", fill="x", expand=True, padx=(10,5), pady=8)

    btn = ctk.CTkButton(
        inner_frame,
        text="Copy ID",
        width=90,
        height=28,
        fg_color=colors["accent"],
        hover_color=colors["accent_hover"],
        text_color=colors["accent_text"],
        corner_radius=12,
        command=lambda c=carid: copy_carid(c)
    )
    btn.pack(side="right", padx=10, pady=8)

    # Add hover preview bindings to card
    card_frame.bind("<Enter>", lambda e, c=carid, w=card_frame: schedule_hover_preview(c, w))
    card_frame.bind("<Leave>", lambda e: hide_hover_preview())
    lbl.bind("<Enter>", lambda e, c=carid, w=lbl: schedule_hover_preview(c, w))
    lbl.bind("<Leave>", lambda e: hide_hover_preview())
    inner_frame.bind("<Enter>", lambda e, c=carid, w=inner_frame: schedule_hover_preview(c, w))
    inner_frame.bind("<Leave>", lambda e: hide_hover_preview())

    bind_hover(card_frame, [inner_frame, lbl, btn])

    carlist_items.append((card_frame, carid, name))

def update_carlist(*args):
    query = carlist_search_var.get().lower()
    for row_frame, carid, name in carlist_items:
        row_frame.pack_forget()
        if query in carid.lower() or query in name.lower():
            row_frame.pack(fill="x", pady=8, padx=8)
    carlist_scroll._parent_canvas.yview_moveto(0)

carlist_search_var.trace_add("write", update_carlist)

# -----------------------
# Settings Tab
# -----------------------
developer_mode_var = ctk.BooleanVar(value=False)
debug_mode_var = ctk.BooleanVar(value=False)

# Frame to hold debug mode toggle (hidden by default)
debug_mode_frame = ctk.CTkFrame(settings_tab, fg_color="transparent")

def toggle_developer_mode():
    if developer_mode_var.get():
        print("Developer mode enabled")
        if "    Developer    " not in tabview._tab_dict:
            tabview.add("    Developer    ")
            setup_developer_tab()
        debug_mode_frame.pack(anchor="w", padx=10, pady=(0,10))
    else:
        print("Developer mode disabled")
        if "    Developer    " in tabview._tab_dict:
            tabview.delete("    Developer    ")
        debug_mode_frame.pack_forget()
        if debug_mode_var.get():
            debug_mode_var.set(False)
            toggle_debug_mode()

ctk.CTkLabel(settings_tab, text="Settings", font=ctk.CTkFont(size=16, weight="bold"), text_color=colors["text"]).pack(anchor="w", padx=10, pady=(10,5))

# Theme toggle
theme_frame = ctk.CTkFrame(settings_tab, fg_color="transparent")
theme_frame.pack(anchor="w", padx=10, pady=(0,10), fill="x")

ctk.CTkLabel(theme_frame, text="Theme:", text_color=colors["text"]).pack(side="left", padx=(0,10))
ctk.CTkLabel(theme_frame, text="Dark Mode", text_color=colors["text"]).pack(side="left", padx=(0,5))
theme_switch = ctk.CTkSwitch(theme_frame, text="", command=toggle_theme, width=50)
if current_theme == "light":
    theme_switch.select()
theme_switch.pack(side="left", padx=5)
ctk.CTkLabel(theme_frame, text="Light Mode", text_color=colors["text"]).pack(side="left")

# Developer mode toggle
developer_checkbox = ctk.CTkCheckBox(
    settings_tab,
    text="Developer Mode",
    variable=developer_mode_var,
    command=toggle_developer_mode
)
developer_checkbox.pack(anchor="w", padx=10, pady=(0,10))

# Debug mode toggle (only visible when developer mode is on)
debug_checkbox = ctk.CTkCheckBox(
    debug_mode_frame,
    text="Debug Mode (Opens debug console)",
    variable=debug_mode_var,
    command=toggle_debug_mode
)
debug_checkbox.pack(anchor="w")

# -----------------------
# About Tab
# -----------------------
about_frame = ctk.CTkFrame(about_tab, fg_color=colors["frame_bg"])
about_frame.pack(fill="both", expand=True, padx=20, pady=20)

ctk.CTkLabel(about_frame, text="BeamSkin Studio", font=ctk.CTkFont(size=26, weight="bold"), text_color=colors["text"]).pack(pady=(10,5))
ctk.CTkLabel(about_frame, text="Credits:", font=ctk.CTkFont(size=22, weight="bold"), text_color=colors["text"]).pack(pady=(50,5))
ctk.CTkLabel(about_frame, text="Developer:", font=ctk.CTkFont(size=19, weight="bold"), text_color=colors["text"]).pack(pady=(10,0))

socials_frame = ctk.CTkFrame(about_frame, fg_color="transparent", height=0)
socials_frame.pack_forget()

def toggle_socials(frame):
    target_height = 45
    if frame.winfo_ismapped():
        def collapse():
            frame.pack_propagate(False)
            for i in range(frame.winfo_height(), -1, -5):
                frame.configure(height=max(0,i))
                time.sleep(0.01)
            frame.pack_forget()
        threading.Thread(target=collapse, daemon=True).start()
    else:
        frame.configure(height=0)
        frame.pack(fill="x", pady=(2,10))
        frame.pack_propagate(False)
        def expand():
            for i in range(0, target_height+2, 5):
                frame.configure(height=i)
                time.sleep(0.01)
            frame.pack_propagate(True)
        threading.Thread(target=expand, daemon=True).start()

ctk.CTkButton(about_frame, text="@Burzt_YT", font=ctk.CTkFont(size=17, weight="bold"), command=lambda: toggle_socials(socials_frame), fg_color=colors["card_bg"], hover_color=colors["card_hover"], text_color=colors["text"]).pack(pady=(2,0))
ctk.CTkButton(socials_frame, text="Linktree", width=120, font=ctk.CTkFont(size=15), fg_color=colors["accent"],
               hover_color=colors["accent_hover"], text_color=colors["accent_text"],
               command=lambda: [webbrowser.open("https://linktr.ee/burzt_yt"), toggle_socials(socials_frame)]).pack(pady=5)

ctk.CTkLabel(about_frame, text="Version: V.0.1.0", font=ctk.CTkFont(size=14), text_color=colors["text"]).pack(side="bottom", pady=(0,10))

# -----------------------
# Developer Tab setup
# -----------------------
developer_tab = None

if os.path.exists(ADDED_VEHICLES_FILE):
    try:
        with open(ADDED_VEHICLES_FILE, "r") as f:
            added_vehicles = json.load(f)
    except:
        added_vehicles = {}

def setup_developer_tab():
    global developer_tab
    developer_tab = tabview._tab_dict.get("    Developer    ")
    if developer_tab is None:
        developer_tab = tabview.add("    Developer    ")
    
    for widget in developer_tab.winfo_children():
        widget.destroy()
    
    ctk.CTkLabel(developer_tab, text="Add New Vehicle", font=ctk.CTkFont(size=16, weight="bold"), text_color=colors["text"]).pack(anchor="w", padx=10, pady=(10,5))
    
    input_frame = ctk.CTkFrame(developer_tab, fg_color=colors["frame_bg"], corner_radius=12)
    input_frame.pack(fill="x", padx=10, pady=(0,10))
    
    carid_var = ctk.StringVar()
    carname_var = ctk.StringVar()
    
    ctk.CTkLabel(input_frame, text="Car ID:", text_color=colors["text"]).grid(row=0, column=0, padx=5, pady=5, sticky="w")
    carid_entry = ctk.CTkEntry(input_frame, textvariable=carid_var, fg_color=colors["card_bg"], text_color=colors["text"])
    carid_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    ctk.CTkLabel(input_frame, text="Car Name:", text_color=colors["text"]).grid(row=1, column=0, padx=5, pady=5, sticky="w")
    carname_entry = ctk.CTkEntry(input_frame, textvariable=carname_var, fg_color=colors["card_bg"], text_color=colors["text"])
    carname_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    
    json_path_var = ctk.StringVar()
    ctk.CTkLabel(input_frame, text="JSON File:", text_color=colors["text"]).grid(row=2, column=0, padx=5, pady=5, sticky="w")
    json_entry = ctk.CTkEntry(input_frame, textvariable=json_path_var, state="readonly", fg_color=colors["card_bg"], text_color=colors["text"])
    json_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    
    def select_json_file():
        path = filedialog.askopenfilename(title="Select JSON File", filetypes=[("JSON Files", "*.json")])
        if path:
            json_path_var.set(path)
            print(f"JSON file selected: {path}")
    
    json_browse_btn = ctk.CTkButton(input_frame, text="Browse", width=80, command=select_json_file,
                                    fg_color=colors["card_bg"], hover_color=colors["card_hover"], text_color=colors["text"])
    json_browse_btn.grid(row=2, column=2, padx=5, pady=5)
    
    jbeam_path_var = ctk.StringVar()
    ctk.CTkLabel(input_frame, text="JBEAM File:", text_color=colors["text"]).grid(row=3, column=0, padx=5, pady=5, sticky="w")
    jbeam_entry = ctk.CTkEntry(input_frame, textvariable=jbeam_path_var, state="readonly", fg_color=colors["card_bg"], text_color=colors["text"])
    jbeam_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
    
    def select_jbeam_file():
        path = filedialog.askopenfilename(title="Select JBEAM File", filetypes=[("JBEAM Files", "*.jbeam")])
        if path:
            jbeam_path_var.set(path)
            print(f"JBEAM file selected: {path}")
    
    jbeam_browse_btn = ctk.CTkButton(input_frame, text="Browse", width=80, command=select_jbeam_file,
                                     fg_color=colors["card_bg"], hover_color=colors["card_hover"], text_color=colors["text"])
    jbeam_browse_btn.grid(row=3, column=2, padx=5, pady=5)
    
    # Add preview image field (optional)
    image_path_var = ctk.StringVar()
    ctk.CTkLabel(input_frame, text="Preview Image (Optional):", text_color=colors["text"]).grid(row=4, column=0, padx=5, pady=5, sticky="w")
    image_entry = ctk.CTkEntry(input_frame, textvariable=image_path_var, state="readonly", fg_color=colors["card_bg"], text_color=colors["text"])
    image_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
    
    def select_image_file():
        path = filedialog.askopenfilename(
            title="Select Preview Image (JPG only)", 
            filetypes=[("JPEG Images", "*.jpg"), ("JPEG Images", "*.jpeg")]
        )
        if path:
            # Validate it's a JPG file
            if path.lower().endswith(('.jpg', '.jpeg')):
                image_path_var.set(path)
                print(f"Preview image selected: {path}")
            else:
                show_notification("Please select a JPG/JPEG image file", "error")
    
    image_browse_btn = ctk.CTkButton(input_frame, text="Browse", width=80, command=select_image_file,
                                     fg_color=colors["card_bg"], hover_color=colors["card_hover"], text_color=colors["text"])
    image_browse_btn.grid(row=4, column=2, padx=5, pady=5)
    
    input_frame.columnconfigure(1, weight=1)
    
    # Add status label and progress bar (hidden by default)
    dev_status_label = ctk.CTkLabel(developer_tab, text="", text_color=colors["text"], font=ctk.CTkFont(size=12))
    dev_status_label.pack(padx=10, pady=(10,5))
    dev_status_label.pack_forget()
    
    dev_progress_bar = ctk.CTkProgressBar(developer_tab)
    dev_progress_bar.pack(fill="x", padx=10, pady=(0,5))
    dev_progress_bar.pack_forget()

    def add_vehicle():
        carid = carid_var.get().strip()
        carname = carname_var.get().strip()
        json_path = json_path_var.get().strip()
        jbeam_path = jbeam_path_var.get().strip()
        image_path = image_path_var.get().strip()

        print(f"\nAttempting to add vehicle: {carname} (ID: {carid})")

        if not carid or not carname:
            print("ERROR: Car ID or Car Name is empty")
            show_notification("Car ID and Car Name cannot be empty", "error")
            return

        if " " in carid:
            print("ERROR: Car ID contains spaces")
            show_notification("Car ID cannot contain spaces", "error")
            return

        if not json_path:
            print("ERROR: No JSON file selected")
            show_notification("Please select a JSON file", "error")
            return

        # JBEAM is now optional
        if jbeam_path:
            print("JBEAM file will be processed")
        else:
            print("No JBEAM file selected - skipping JBEAM processing")
        
        # Preview image is optional
        if image_path:
            print(f"Preview image will be copied: {image_path}")
        else:
            print("No preview image selected - skipping image copy")

        if carid in [v[0] for v in car_id_list] or carid in added_vehicles:
            print(f"ERROR: Car ID '{carid}' already exists")
            show_notification(f"Car ID '{carid}' already exists", "error")
            return

        # Show progress UI above "Added Vehicles" section
        dev_status_label.configure(text="Preparing to add vehicle...")
        dev_status_label.pack(padx=10, pady=(10,5))
        dev_progress_bar.pack(fill="x", padx=10, pady=(0,10))
        dev_progress_bar.set(0)
        add_button.configure(state="disabled", text="Adding...")

        def update_progress(value, status_text):
            """Update progress bar and status label"""
            dev_progress_bar.set(value)
            dev_status_label.configure(text=status_text)
            developer_tab.update_idletasks()

        try:
            update_progress(0.1, "Saving vehicle information...")
            added_vehicles[carid] = carname
            save_added_vehicles()
            print(f"Vehicle saved to added_vehicles.json")

            update_progress(0.2, "Creating vehicle folders...")
            create_vehicle_folders(carid)
            print(f"Created vehicle folders for {carid}")

            skinname_folder = os.path.join(VEHICLE_FOLDER, carid, "SKINNAME")
            
            # Edit and copy the JSON file (using 'skinname' as placeholder)
            update_progress(0.3, "Processing JSON file...")
            print(f"\n--- Processing JSON file ---")
            edit_material_json(json_path, skinname_folder, carid)
            
            if jbeam_path:
                # Edit and copy the JBEAM file (using 'skinname' as placeholder)
                update_progress(0.6, "Processing JBEAM file...")
                print(f"\n--- Processing JBEAM file ---")
                edit_jbeam_material(jbeam_path, skinname_folder, carid)
                
                # Check if JBEAM was actually saved (with original filename)
                jbeam_filename = os.path.basename(jbeam_path)
                jbeam_output = os.path.join(skinname_folder, jbeam_filename)
                if not os.path.exists(jbeam_output):
                    print(f"\nWARNING: JBEAM file was not created!")
                    print(f"Expected location: {jbeam_output}")
                    raise Exception(
                        "Failed to process JBEAM file.\n\n"
                        "Please make sure the selected JBEAM file is valid."
                    )
            
            # Copy preview image if provided
            if image_path:
                update_progress(0.7, "Copying preview image...")
                print(f"\n--- Copying preview image ---")
                
                # Create image folder structure: imagesforgui/vehicles/{carid}/
                image_folder = os.path.join("imagesforgui", "vehicles", carid)
                os.makedirs(image_folder, exist_ok=True)
                
                # Copy and rename to default.jpg
                import shutil as img_shutil
                dest_path = os.path.join(image_folder, "default.jpg")
                img_shutil.copy2(image_path, dest_path)
                
                print(f"Preview image copied to: {dest_path}")
            
            update_progress(0.8, "Updating vehicle lists...")
            car_id_list.append((carid, carname))
            add_carlist_card(carid, carname, developer_added=True)
            add_vehicle_button(carid, display_name=carname)

            update_progress(0.9, "Cleaning up...")
            carid_var.set("")
            carname_var.set("")
            json_path_var.set("")
            jbeam_path_var.set("")
            image_path_var.set("")
            
            update_progress(1.0, "Vehicle added successfully!")
            print(f"Vehicle '{carname}' added successfully!\n")
            
            # Hide progress UI after a short delay
            app.after(2000, lambda: dev_progress_bar.pack_forget())
            app.after(2000, lambda: dev_status_label.pack_forget())
            
            show_notification(f"✓ Vehicle '{carname}' added successfully!", "success", 5000)
            refresh_developer_list()
            
        except Exception as e:
            print(f"ERROR processing files: {e}")
            dev_status_label.configure(text="Error: Failed to add vehicle")
            show_notification(f"Failed to add vehicle: {str(e)}", "error", 5000)
            delete_vehicle_folders(carid)
            del added_vehicles[carid]
            save_added_vehicles()
            
            # Hide progress UI after error
            app.after(2000, lambda: dev_progress_bar.pack_forget())
            app.after(2000, lambda: dev_status_label.pack_forget())
        finally:
            add_button.configure(state="normal", text="Add Vehicle")

    add_button = ctk.CTkButton(input_frame, text="Add Vehicle", command=add_vehicle,
                               fg_color=colors["accent"], hover_color=colors["accent_hover"], text_color=colors["accent_text"])
    add_button.grid(row=5, column=0, columnspan=3, padx=5, pady=10)
    
    # "Added Vehicles" section header
    ctk.CTkLabel(developer_tab, text="Added Vehicles", font=ctk.CTkFont(size=14, weight="bold"), text_color=colors["text"]).pack(anchor="w", padx=10, pady=(10,5))
    
    # Add status label and progress bar - appears above search
    dev_status_label = ctk.CTkLabel(developer_tab, text="", text_color=colors["text"], font=ctk.CTkFont(size=12))
    dev_status_label.pack_forget()
    
    dev_progress_bar = ctk.CTkProgressBar(developer_tab)
    dev_progress_bar.pack_forget()
    
    # Search box for added vehicles
    dev_search_var = ctk.StringVar()
    dev_search_entry = ctk.CTkEntry(
        developer_tab,
        textvariable=dev_search_var,
        placeholder_text="Search added vehicles...",
        placeholder_text_color=colors["text_secondary"],
        fg_color=colors["card_bg"],
        text_color=colors["text"]
    )
    dev_search_entry.pack(fill="x", padx=10, pady=(0,5))
    
    # List frame for added vehicles
    dev_list_frame = ctk.CTkScrollableFrame(developer_tab, height=300, fg_color=colors["frame_bg"], corner_radius=12)
    dev_list_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))
    
    # Store list items for search filtering
    dev_list_items = []

    def delete_vehicle(carid):
        print(f"\nDeleting vehicle: {carid}")
        if carid in added_vehicles:
            del added_vehicles[carid]
            save_added_vehicles()

            delete_vehicle_folders(carid)
            print(f"Deleted vehicle folders for {carid}")

            for i, item in enumerate(car_id_list):
                if item[0] == carid:
                    car_id_list.pop(i)
                    break

            for i, (btn, cid, dname) in enumerate(vehicle_buttons):
                if cid == carid:
                    btn.master.destroy()
                    vehicle_buttons.pop(i)
                    break

            for i, (card, c, n) in enumerate(carlist_items):
                if c == carid:
                    card.destroy()
                    carlist_items.pop(i)
                    break

            print(f"Vehicle '{carid}' deleted successfully\n")
            refresh_developer_list()

    def refresh_developer_list():
        global dev_list_items
        dev_list_items = []
        
        for widget in dev_list_frame.winfo_children():
            widget.destroy()
            
        for carid, carname in added_vehicles.items():
            row = ctk.CTkFrame(dev_list_frame, corner_radius=12, fg_color=colors["card_bg"])
            row.pack(fill="x", pady=4, padx=4)
            
            lbl = ctk.CTkLabel(row, text=f"{carid} — {carname}", anchor="w", text_color=colors["text"])
            lbl.pack(side="left", fill="x", expand=True, padx=5, pady=5)
            
            del_btn = ctk.CTkButton(row, text="Delete", width=80, fg_color=colors["error"],
                                    hover_color=colors["error_hover"], text_color=colors["accent_text"],
                                    command=lambda c=carid: delete_vehicle(c))
            del_btn.pack(side="right", padx=5, pady=5)
            
            # Add hover preview bindings
            row.bind("<Enter>", lambda e, c=carid, w=row: schedule_hover_preview(c, w))
            row.bind("<Leave>", lambda e: hide_hover_preview())
            lbl.bind("<Enter>", lambda e, c=carid, w=lbl: schedule_hover_preview(c, w))
            lbl.bind("<Leave>", lambda e: hide_hover_preview())
            
            # Store for search filtering
            dev_list_items.append((row, carid, carname))
    
    def update_dev_list(*args):
        """Filter the developer list based on search query"""
        query = dev_search_var.get().lower()
        for row, carid, carname in dev_list_items:
            row.pack_forget()
            if query in carid.lower() or query in carname.lower():
                row.pack(fill="x", pady=4, padx=4)
        dev_list_frame._parent_canvas.yview_moveto(0)
    
    dev_search_var.trace_add("write", update_dev_list)

    refresh_developer_list()

def add_carlist_card(carid, name, developer_added=False):
    insert_position = 0
    for i, (card, cid, cname) in enumerate(carlist_items):
        if cname.lower() > name.lower():
            insert_position = i
            break
        insert_position = i + 1
    
    card_frame = ctk.CTkFrame(
        carlist_scroll,
        corner_radius=12,
        fg_color=colors["card_bg"],
        border_width=1,
        border_color=colors["border"]
    )

    inner_frame = ctk.CTkFrame(
        card_frame,
        corner_radius=12,
        fg_color=colors["card_bg"],
        border_width=0
    )
    inner_frame.pack(fill="x", padx=5, pady=5)

    lbl = ctk.CTkLabel(
        inner_frame,
        text=f"{carid}  —  {name}",
        anchor="w",
        justify="left",
        font=carlist_font,
        text_color=colors["text"]
    )
    lbl.pack(side="left", fill="x", expand=True, padx=(10,5), pady=8)

    btn = ctk.CTkButton(
        inner_frame,
        text="Copy ID",
        width=90,
        height=28,
        fg_color=colors["accent"],
        hover_color=colors["accent_hover"],
        text_color=colors["accent_text"],
        corner_radius=12,
        command=lambda c=carid: copy_carid(c)
    )
    btn.pack(side="right", padx=10, pady=8)

    # Add hover preview bindings
    card_frame.bind("<Enter>", lambda e, c=carid, w=card_frame: schedule_hover_preview(c, w))
    card_frame.bind("<Leave>", lambda e: hide_hover_preview())
    lbl.bind("<Enter>", lambda e, c=carid, w=lbl: schedule_hover_preview(c, w))
    lbl.bind("<Leave>", lambda e: hide_hover_preview())
    inner_frame.bind("<Enter>", lambda e, c=carid, w=inner_frame: schedule_hover_preview(c, w))
    inner_frame.bind("<Leave>", lambda e: hide_hover_preview())

    bind_hover(card_frame, [inner_frame, lbl, btn])

    carlist_items.insert(insert_position, (card_frame, carid, name))
    
    for widget in carlist_scroll.winfo_children():
        widget.pack_forget()
    
    for card, cid, cname in carlist_items:
        card.pack(fill="x", pady=8, padx=8)

def add_vehicle_button(carid, display_name=None):
    name_to_show = display_name if display_name else carid
    
    insert_position = 0
    for i, (btn, cid, dname) in enumerate(vehicle_buttons):
        if dname.lower() > name_to_show.lower():
            insert_position = i
            break
        insert_position = i + 1
    
    row_frame = ctk.CTkFrame(vehicle_scroll_frame, corner_radius=12, fg_color=colors["frame_bg"])

    btn = ctk.CTkButton(
        row_frame,
        text=name_to_show,
        command=lambda c=carid: select_vehicle(c),
        fg_color=colors["card_bg"],
        hover_color=colors["card_hover"],
        height=35,
        corner_radius=12,
        text_color=colors["text"]
    )
    btn.pack(fill="x", padx=8, pady=6)

    # Add hover preview bindings
    btn.bind("<Enter>", lambda e, c=carid, w=btn: schedule_hover_preview(c, w))
    btn.bind("<Leave>", lambda e: hide_hover_preview())

    vehicle_buttons.insert(insert_position, (btn, carid, name_to_show))
    
    for widget in vehicle_scroll_frame.winfo_children():
        widget.pack_forget()
    
    for button, cid, dname in vehicle_buttons:
        button.master.pack(fill="x", pady=3, padx=5)

for carid, carname in added_vehicles.items():
    add_carlist_card(carid, carname, developer_added=True)
    add_vehicle_button(carid, display_name=carname)
    car_id_list.append((carid, carname))

def on_closing():
    print("\nShutting down BeamSkin Studio...")
    app.destroy()
app.protocol("WM_DELETE_WINDOW", on_closing)

if __name__ == "__main__":
    app.mainloop()