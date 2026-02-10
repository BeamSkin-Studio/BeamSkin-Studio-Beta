"""GitHub update checker with custom UI
"""
import requests
from tkinter import messagebox
import webbrowser
import customtkinter as ctk
import re
import os
import sys

def get_base_path():
    print(f"[DEBUG] get_base_path called")
    """Get the base path for resources (works in dev and PyInstaller)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return sys._MEIPASS
    else:
        # Running in development
        return os.path.dirname(os.path.abspath(__file__))

def read_version():
    print(f"[DEBUG] read_version called")
    """Read version from version.txt and return formatted version string"""
    print(f"[DEBUG] ========== READING VERSION FILE ==========")
    
    # Try multiple paths to find version.txt
    possible_paths = [
        os.path.join(get_base_path(), 'version.txt'),  # PyInstaller bundled
        os.path.join(os.getcwd(), 'version.txt'),      # Current directory
        'version.txt',                                  # Relative to script
    ]
    
    for version_path in possible_paths:
        if os.path.exists(version_path):
            try:
                with open(version_path, 'r') as f:
                    content = f.read().strip()
                    print(f"[DEBUG] Raw version content: {content}")
                    
                    # Parse the version number (supports multiple formats)
                    # Format 1: "0.5.4.0" (4 components)
                    # Format 2: "0.5.4" (3 components)
                    # Format 3: "Version: 0.5.4.0"
                    
                    # Remove "Version:" prefix if present
                    if "Version:" in content:
                        content = content.replace("Version:", "").strip()
                    
                    # Split by dots and validate
                    parts = content.split('.')
                    
                    # Convert to version string with status
                    if len(parts) >= 3:
                        major, minor, patch = parts[0], parts[1], parts[2]
                        
                        # Check if there's a 4th component or status indicator
                        if len(parts) >= 4:
                            # If 4th part is a number (like 0), it's a build number - treat as Beta
                            try:
                                build = int(parts[3])
                                if build == 0:
                                    status = "Beta"
                                else:
                                    status = f"Build {build}"
                            except ValueError:
                                # If 4th part is text (like "Beta"), use it as status
                                status = parts[3].capitalize()
                        else:
                            # No 4th component = stable release
                            status = "Stable"
                        
                        version = f"{major}.{minor}.{patch}.{status}"
                    else:
                        # Fallback for malformed version
                        version = content
                    
                    print(f"[DEBUG] Version loaded from: {version_path}")
                    print(f"[DEBUG] Formatted version: {version}")
                    return version
            except Exception as e:
                print(f"[DEBUG] Failed to read {version_path}: {e}")
                continue
    
    print(f"[DEBUG] WARNING: version.txt not found in any location")
    print(f"[DEBUG] Searched paths:")
    for path in possible_paths:
        print(f"[DEBUG]   - {path}")
    return "0.0.0.Unknown"

CURRENT_VERSION = read_version()

# Global to store app reference
_app_instance = None
_colors = None

def set_app_instance(app, colors):
    print(f"[DEBUG] set_app_instance called")
    """Set the app instance and colors for update prompts"""
    global _app_instance, _colors
    _app_instance = app
    _colors = colors

def parse_version(version_string):
    print(f"[DEBUG] parse_version called")
    """
    Parse version string into comparable tuple.
    Examples:
        "0.3.6.Beta" -> (0, 3, 6, 'beta')
        "0.4.0.Beta" -> (0, 4, 0, 'beta')
        "1.0.0.Stable" -> (1, 0, 0, 'stable')
    """
    # Remove common prefixes
    version_string = version_string.lower().strip()
    version_string = version_string.replace('version:', '').replace('v', '').strip()
    
    # Extract numbers and suffix
    match = re.match(r'(\d+)\.(\d+)\.(\d+)\.?(.*)', version_string)
    if match:
        major, minor, patch, suffix = match.groups()
        major, minor, patch = int(major), int(minor), int(patch)
        
        # Normalize suffix
        suffix = suffix.lower().strip() if suffix else 'stable'
        
        # Version tuple: (major, minor, patch, suffix_priority)
        # Lower suffix_priority = newer (stable > rc > beta > alpha)
        suffix_priority = {
            'stable': 0,
            '': 0,
            'rc': 1,
            'beta': 2,
            'alpha': 3
        }.get(suffix, 2)  # Default to beta priority if unknown
        
        return (major, minor, patch, suffix_priority)
    
    # Fallback for unparseable versions
    return (0, 0, 0, 999)

def is_newer_version(remote_version, current_version):
    print(f"[DEBUG] is_newer_version called")
    """
    Compare two version strings to see if remote is newer.
    Returns True if remote_version is newer than current_version.
    """
    try:
        remote_tuple = parse_version(remote_version)
        current_tuple = parse_version(current_version)
        
        print(f"[DEBUG] Parsed current: {current_version} -> {current_tuple}")
        print(f"[DEBUG] Parsed remote: {remote_version} -> {remote_tuple}")
        
        # Compare tuples (higher is newer, except for suffix_priority where lower is newer)
        if remote_tuple[:3] != current_tuple[:3]:
            # Different major/minor/patch - compare numerically
            return remote_tuple[:3] > current_tuple[:3]
        else:
            # Same version numbers, compare suffix (lower suffix_priority is newer)
            return remote_tuple[3] < current_tuple[3]
            
    except Exception as e:
        print(f"[DEBUG] Version comparison error: {e}")
        # If parsing fails, fall back to string comparison
        return remote_version != current_version

def prompt_update(new_version):
    print(f"[DEBUG] prompt_update called")
    """Show custom update notification window"""
    print(f"\n[DEBUG] ========== UPDATE PROMPT ==========")
    print(f"[DEBUG] Showing update dialog for version: {new_version}")
    
    if _app_instance is None or _colors is None:
        # Fallback to simple messagebox
        response = messagebox.askyesno(
            "Update Available",
            f"A new version is available!\n\n"
            f"Current: {CURRENT_VERSION}\n"
            f"Latest: {new_version}\n\n"
            f"Would you like to download it now?"
        )
        if response:
            webbrowser.open("https://github.com/johanssonserlanderkevin-sys/BeamSkin-Studio")
        return
    
    update_window = ctk.CTkToplevel(_app_instance)
    update_window.title("Update Available")
    update_window.geometry("500x350")
    update_window.resizable(False, False)
    update_window.transient(_app_instance)
    update_window.grab_set()
    
    update_window.update_idletasks()
    width = update_window.winfo_width()
    height = update_window.winfo_height()
    x = (update_window.winfo_screenwidth() // 2) - (width // 2)
    y = (update_window.winfo_screenheight() // 2) - (height // 2)
    update_window.geometry(f"{width}x{height}+{x}+{y}")
    
    # Main frame
    main_frame = ctk.CTkFrame(update_window, fg_color=_colors["frame_bg"])
    main_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    # Title
    title_label = ctk.CTkLabel(
        main_frame,
        text="Update Available!",
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=_colors["accent"]
    )
    title_label.pack(pady=(5, 15))
    
    # Version info frame
    info_frame = ctk.CTkFrame(main_frame, fg_color=_colors["card_bg"], corner_radius=10)
    info_frame.pack(fill="x", padx=10, pady=10)
    
    current_label = ctk.CTkLabel(
        info_frame,
        text=f"Current Version: {CURRENT_VERSION}",
        font=ctk.CTkFont(size=13),
        text_color=_colors["text"]
    )
    current_label.pack(pady=(10, 5))
    
    arrow_label = ctk.CTkLabel(
        info_frame,
        text="↓",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=_colors["accent"]
    )
    arrow_label.pack(pady=2)
    
    new_label = ctk.CTkLabel(
        info_frame,
        text=f"New Version: {new_version}",
        font=ctk.CTkFont(size=19, weight="bold"),
        text_color=_colors["accent"]
    )
    new_label.pack(pady=(5, 10))
    
    # Message
    message_label = ctk.CTkLabel(
        main_frame,
        text="A new version of BeamSkin Studio is available!\n"
             "Would you like to download it now?",
        font=ctk.CTkFont(size=12),
        text_color=_colors["text"],
        justify="center"
    )
    message_label.pack(pady=15)
    
    # Buttons frame
    button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(pady=10, fill="x", padx=20)
    
    def download_update():
        print(f"[DEBUG] download_update called")
        """Open GitHub releases page"""
        print(f"[DEBUG] Opening GitHub releases page...")
        webbrowser.open("https://github.com/johanssonserlanderkevin-sys/BeamSkin-Studio")
        update_window.destroy()
    
    def maybe_later():
        print(f"[DEBUG] maybe_later called")
        """Close update window"""
        print(f"[DEBUG] User chose maybe later")
        update_window.destroy()
    
    # Download button
    download_btn = ctk.CTkButton(
        button_frame,
        text="Download Update",
        command=download_update,
        fg_color=_colors["accent"],
        hover_color=_colors["accent_hover"],
        text_color=_colors["accent_text"],
        height=40,
        corner_radius=8,
        font=ctk.CTkFont(size=13, weight="bold")
    )
    download_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
    
    # Skip button
    skip_btn = ctk.CTkButton(
        button_frame,
        text="Maybe Later",
        command=maybe_later,
        fg_color=_colors["card_bg"],
        hover_color=_colors["card_hover"],
        text_color=_colors["text"],
        height=40,
        corner_radius=8,
        font=ctk.CTkFont(size=13)
    )
    skip_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

def check_for_updates():
    print(f"[DEBUG] check_for_updates called")
    """Check for updates from GitHub repository"""
    print(f"\n[DEBUG] ========== UPDATE CHECK STARTED ==========")
    print(f"[DEBUG] Current version: {CURRENT_VERSION}")
    
    url = "https://raw.githubusercontent.com/johanssonserlanderkevin-sys/BeamSkin-Studio/main/version.txt"
    
    try:
        response = requests.get(url, timeout=3)
        
        if response.status_code == 200:
            content = response.text.strip()
            
            # Parse remote version using same logic
            if "Version:" in content:
                content = content.replace("Version:", "").strip()
            
            parts = content.split('.')
            if len(parts) >= 3:
                major, minor, patch = parts[0], parts[1], parts[2]
                if len(parts) >= 4:
                    try:
                        build = int(parts[3])
                        status = "Beta" if build == 0 else f"Build {build}"
                    except ValueError:
                        status = parts[3].capitalize()
                else:
                    status = "Stable"
                latest_version = f"{major}.{minor}.{patch}.{status}"
            else:
                latest_version = content
            
            print(f"[DEBUG] Latest version from GitHub: {latest_version}")
            
            # Use proper version comparison instead of simple string equality
            if is_newer_version(latest_version, CURRENT_VERSION):
                print(f"[DEBUG] UPDATE AVAILABLE! {CURRENT_VERSION} -> {latest_version}")
                # Use app.after to safely trigger the popup from a background thread
                if _app_instance:
                    _app_instance.after(0, lambda: prompt_update(latest_version))
                else:
                    # Fallback if app not set
                    response = messagebox.askyesno(
                        "Update Available",
                        f"Version {latest_version} is available!\nDownload now?"
                    )
                    if response:
                        webbrowser.open("https://github.com/johanssonserlanderkevin-sys/BeamSkin-Studio")
            else:
                print(f"[DEBUG] Already on latest version (or newer)")
    except Exception as e:
        print(f"[DEBUG] Update check failed: {e}")
    
    print(f"[DEBUG] ========== UPDATE CHECK COMPLETE ==========\n")
