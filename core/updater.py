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

        return sys._MEIPASS
    else:

        return os.path.dirname(os.path.abspath(__file__))

def read_version():
    print(f"[DEBUG] read_version called")
    """Read version from version.txt and return formatted version string"""
    print(f"[DEBUG] ========== READING VERSION FILE ==========")

    possible_paths = [
        os.path.join(get_base_path(), 'version.txt'),
        os.path.join(os.getcwd(), 'version.txt'),
        'version.txt',
    ]

    for version_path in possible_paths:
        if os.path.exists(version_path):
            try:
                with open(version_path, 'r') as f:
                    content = f.read().strip()
                    print(f"[DEBUG] Raw version content: {content}")

                    if "Version:" in content:
                        content = content.replace("Version:", "").strip()

                    parts = content.split('.')

                    if len(parts) >= 3:
                        major, minor, patch = parts[0], parts[1], parts[2]

                        if len(parts) >= 4:

                            try:
                                build = int(parts[3])
                                if build == 0:
                                    status = "Beta"
                                else:
                                    status = f"Build {build}"
                            except ValueError:

                                status = parts[3].capitalize()
                        else:

                            status = "Stable"

                        version = f"{major}.{minor}.{patch}.{status}"
                    else:

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

    version_string = version_string.lower().strip()
    version_string = version_string.replace('version:', '').replace('v', '').strip()

    match = re.match(r'(\d+)\.(\d+)\.(\d+)\.?(.*)', version_string)
    if match:
        major, minor, patch, suffix = match.groups()
        major, minor, patch = int(major), int(minor), int(patch)

        suffix = suffix.lower().strip() if suffix else 'stable'

        suffix_priority = {
            'stable': 0,
            '': 0,
            'rc': 1,
            'beta': 2,
            'alpha': 3
        }.get(suffix, 2)

        return (major, minor, patch, suffix_priority)

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

        if remote_tuple[:3] != current_tuple[:3]:

            return remote_tuple[:3] > current_tuple[:3]
        else:

            return remote_tuple[3] < current_tuple[3]

    except Exception as e:
        print(f"[DEBUG] Version comparison error: {e}")

        return remote_version != current_version

def prompt_update(new_version):
    print(f"[DEBUG] prompt_update called")
    """Show custom update notification window"""
    print(f"\n[DEBUG] ========== UPDATE PROMPT ==========")
    print(f"[DEBUG] Showing update dialog for version: {new_version}")

    if _app_instance is None or _colors is None:

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
    update_window.geometry("500x400")  # Increased from 350 to 400 for download progress
    update_window.resizable(False, False)
    update_window.transient(_app_instance)
    update_window.grab_set()

    update_window.update_idletasks()
    width = update_window.winfo_width()
    height = update_window.winfo_height()
    x = (update_window.winfo_screenwidth() // 2) - (width // 2)
    y = (update_window.winfo_screenheight() // 2) - (height // 2)
    update_window.geometry(f"{width}x{height}+{x}+{y}")

    main_frame = ctk.CTkFrame(update_window, fg_color=_colors["frame_bg"])
    main_frame.pack(fill="both", expand=True, padx=15, pady=15)

    title_label = ctk.CTkLabel(
        main_frame,
        text="Update Available!",
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=_colors["accent"]
    )
    title_label.pack(pady=(5, 15))

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

    message_label = ctk.CTkLabel(
        main_frame,
        text="A new version of BeamSkin Studio is available!\n"
             "Would you like to download it now?",
        font=ctk.CTkFont(size=12),
        text_color=_colors["text"],
        justify="center"
    )
    message_label.pack(pady=15)

    button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(pady=10, fill="x", padx=20)

    def download_update():
        print(f"[DEBUG] download_update called")
        """Download the latest repository ZIP"""
        print(f"[DEBUG] Downloading latest version ZIP...")
        
        # Update button to show downloading status
        download_btn.configure(text="Downloading Update...", state="disabled")
        skip_btn.configure(state="disabled")
        update_window.update()
        
        # Add status label
        status_label = ctk.CTkLabel(
            main_frame,
            text="Downloading update, please wait...",
            font=ctk.CTkFont(size=11),
            text_color=_colors["text"],
            wraplength=450  # Ensure text wraps properly
        )
        status_label.pack(pady=(0, 5))
        update_window.update()
        
        try:
            # GitHub repository ZIP URL
            zip_url = "https://github.com/johanssonserlanderkevin-sys/BeamSkin-Studio/archive/refs/heads/main.zip"
            
            # Get user's Downloads folder
            if sys.platform == 'win32':
                import winreg
                sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
                downloads_guid = '{374DE290-123F-4565-9164-39C4925E467B}'
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                    downloads_folder = winreg.QueryValueEx(key, downloads_guid)[0]
            else:
                downloads_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
            
            # Create filename with version
            filename = f"BeamSkin-Studio-{new_version}.zip"
            filepath = os.path.join(downloads_folder, filename)
            
            # Download the file
            status_label.configure(text=f"Downloading {filename}...")
            update_window.update()
            
            response = requests.get(zip_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Update progress
                        progress_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        status_label.configure(
                            text=f"Downloading: {progress_mb:.1f} MB / {total_mb:.1f} MB"
                        )
                        update_window.update_idletasks()
            
            status_label.configure(text="Download complete!")
            update_window.update()
            
            print(f"[DEBUG] Download complete: {filepath}")
            
            # Show success message and offer to open downloads folder or extract
            update_window.destroy()
            
            success_window = ctk.CTkToplevel(_app_instance)
            success_window.title("Download Complete")
            success_window.geometry("450x280")
            success_window.resizable(False, False)
            success_window.transient(_app_instance)
            success_window.grab_set()
            
            # Center the window
            success_window.update_idletasks()
            width = success_window.winfo_width()
            height = success_window.winfo_height()
            x = (success_window.winfo_screenwidth() // 2) - (width // 2)
            y = (success_window.winfo_screenheight() // 2) - (height // 2)
            success_window.geometry(f"{width}x{height}+{x}+{y}")
            
            frame = ctk.CTkFrame(success_window, fg_color=_colors["frame_bg"])
            frame.pack(fill="both", expand=True, padx=15, pady=15)
            
            ctk.CTkLabel(
                frame,
                text="✓ Download Complete!",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color=_colors["accent"]
            ).pack(pady=(10, 5))
            
            ctk.CTkLabel(
                frame,
                text=f"Saved to:\n{filepath}",
                font=ctk.CTkFont(size=11),
                text_color=_colors["text"],
                justify="center"
            ).pack(pady=10)
            
            def extract_and_update():
                """Extract ZIP and update application files"""
                import zipfile
                import shutil
                from pathlib import Path
                
                try:
                    # Update button to show extraction status
                    extract_btn.configure(text="Extracting...", state="disabled")
                    success_window.update()
                    
                    # Get current application directory (root of the app)
                    if getattr(sys, 'frozen', False):
                        # Running as compiled exe - get the directory containing the exe
                        app_dir = os.path.dirname(sys.executable)
                    else:
                        # Running as script - get the directory containing main.py
                        # Go up from core/updater.py to the root
                        current_file = os.path.abspath(__file__)
                        # updater.py is in core/, so parent of parent is root
                        app_dir = os.path.dirname(os.path.dirname(current_file))
                    
                    print(f"[DEBUG] Application root directory: {app_dir}")
                    
                    # Create temporary extraction directory
                    temp_extract_dir = os.path.join(downloads_folder, f"BeamSkin-Studio-temp-{new_version}")
                    
                    # Extract ZIP
                    print(f"[DEBUG] Extracting to: {temp_extract_dir}")
                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                        zip_ref.extractall(temp_extract_dir)
                    
                    # Find the extracted folder (GitHub adds a folder like "BeamSkin-Studio-main")
                    extracted_contents = os.listdir(temp_extract_dir)
                    if len(extracted_contents) == 1 and os.path.isdir(os.path.join(temp_extract_dir, extracted_contents[0])):
                        source_dir = os.path.join(temp_extract_dir, extracted_contents[0])
                    else:
                        source_dir = temp_extract_dir
                    
                    print(f"[DEBUG] Source directory: {source_dir}")
                    print(f"[DEBUG] Target directory: {app_dir}")
                    
                    # Files to preserve (don't overwrite)
                    preserve_relative_paths = {
                        os.path.join('data', 'app_settings.json'),
                        os.path.join('vehicles', 'added_vehicles.json')
                    }
                    
                    # Backup user data before updating
                    backup_data = {}
                    for preserve_path in preserve_relative_paths:
                        full_path = os.path.join(app_dir, preserve_path)
                        if os.path.exists(full_path):
                            try:
                                with open(full_path, 'r', encoding='utf-8') as f:
                                    backup_data[preserve_path] = f.read()
                                print(f"[DEBUG] Backed up: {preserve_path}")
                            except Exception as e:
                                print(f"[DEBUG] Could not backup {preserve_path}: {e}")
                    
                    # Copy new files, overwriting old ones
                    files_updated = 0
                    for root, dirs, files in os.walk(source_dir):
                        # Calculate relative path from source_dir
                        rel_dir = os.path.relpath(root, source_dir)
                        
                        # Determine target directory
                        if rel_dir == '.':
                            target_dir = app_dir
                        else:
                            target_dir = os.path.join(app_dir, rel_dir)
                        
                        # Create directory if it doesn't exist
                        os.makedirs(target_dir, exist_ok=True)
                        
                        # Copy files
                        for file in files:
                            source_file = os.path.join(root, file)
                            
                            # Calculate relative path for this file
                            if rel_dir == '.':
                                rel_file_path = file
                            else:
                                rel_file_path = os.path.join(rel_dir, file)
                            
                            # Normalize path separators
                            rel_file_path_normalized = rel_file_path.replace('/', os.sep).replace('\\', os.sep)
                            
                            # Check if this file should be preserved
                            should_preserve = False
                            for preserve_path in preserve_relative_paths:
                                preserve_normalized = preserve_path.replace('/', os.sep).replace('\\', os.sep)
                                if rel_file_path_normalized == preserve_normalized:
                                    should_preserve = True
                                    break
                            
                            if should_preserve:
                                print(f"[DEBUG] Skipping preserved file: {rel_file_path}")
                                continue
                            
                            target_file = os.path.join(target_dir, file)
                            
                            try:
                                # Copy file and preserve metadata
                                shutil.copy2(source_file, target_file)
                                files_updated += 1
                                if files_updated <= 10:  # Only print first 10 to avoid spam
                                    print(f"[DEBUG] Updated: {rel_file_path}")
                            except Exception as e:
                                print(f"[DEBUG] Could not update {rel_file_path}: {e}")
                    
                    print(f"[DEBUG] Total files updated: {files_updated}")
                    
                    # Restore preserved files
                    for preserve_path, content in backup_data.items():
                        full_path = os.path.join(app_dir, preserve_path)
                        try:
                            # Ensure directory exists
                            os.makedirs(os.path.dirname(full_path), exist_ok=True)
                            with open(full_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            print(f"[DEBUG] Restored: {preserve_path}")
                        except Exception as e:
                            print(f"[DEBUG] Could not restore {preserve_path}: {e}")
                    
                    # Clean up temp directory
                    try:
                        shutil.rmtree(temp_extract_dir)
                        print(f"[DEBUG] Cleaned up temp directory")
                    except Exception as e:
                        print(f"[DEBUG] Could not clean up temp directory: {e}")
                    
                    # Delete the downloaded ZIP file
                    try:
                        os.remove(filepath)
                        print(f"[DEBUG] Deleted downloaded ZIP file: {filepath}")
                    except Exception as e:
                        print(f"[DEBUG] Could not delete ZIP file: {e}")
                    
                    # Show completion message
                    success_window.destroy()
                    
                    completion_window = ctk.CTkToplevel(_app_instance)
                    completion_window.title("Update Complete")
                    completion_window.geometry("450x280")  # INCREASED HEIGHT from 220 to 280
                    completion_window.resizable(False, False)
                    completion_window.transient(_app_instance)
                    completion_window.grab_set()
                    
                    # Center window
                    completion_window.update_idletasks()
                    w = completion_window.winfo_width()
                    h = completion_window.winfo_height()
                    x = (completion_window.winfo_screenwidth() // 2) - (w // 2)
                    y = (completion_window.winfo_screenheight() // 2) - (h // 2)
                    completion_window.geometry(f"{w}x{h}+{x}+{y}")
                    
                    comp_frame = ctk.CTkFrame(completion_window, fg_color=_colors["frame_bg"])
                    comp_frame.pack(fill="both", expand=True, padx=15, pady=15)
                    
                    ctk.CTkLabel(
                        comp_frame,
                        text="✓ Update Complete!",
                        font=ctk.CTkFont(size=18, weight="bold"),
                        text_color=_colors["accent"]
                    ).pack(pady=(10, 5))
                    
                    ctk.CTkLabel(
                        comp_frame,
                        text=f"Updated {files_updated} files to version {new_version}\n\n"
                             "Your settings and custom vehicles have been preserved.\n\n"
                             "Please restart BeamSkin Studio to use the new version.",
                        font=ctk.CTkFont(size=11),
                        text_color=_colors["text"],
                        justify="center"
                    ).pack(pady=10)
                    
                    def restart_app():
                        """Restart the application using the batch launcher if available"""
                        print(f"[DEBUG] Restarting application...")
                        
                        # Get current directory
                        if getattr(sys, 'frozen', False):
                            current_dir = os.path.dirname(sys.executable)
                        else:
                            current_dir = os.path.dirname(os.path.dirname(__file__))
                        
                        # Check for batch file launcher (Windows)
                        bat_launcher = os.path.join(current_dir, "Beamskin studio.bat")
                        
                        if sys.platform == 'win32' and os.path.exists(bat_launcher):
                            # Windows with batch launcher - use it! Shows loading screen ✓
                            print(f"[DEBUG] Restarting using batch launcher: {bat_launcher}")
                            import subprocess
                            
                            # Close current instance
                            completion_window.destroy()
                            _app_instance.destroy()
                            
                            # Start new instance using batch file
                            subprocess.Popen([bat_launcher], cwd=current_dir, shell=True)
                            
                            # Exit current process
                            sys.exit(0)
                        
                        elif getattr(sys, 'frozen', False):
                            # Running as compiled exe (no batch launcher)
                            print(f"[DEBUG] Restarting as compiled exe: {sys.executable}")
                            import subprocess
                            
                            # Close current instance
                            completion_window.destroy()
                            _app_instance.destroy()
                            
                            # Start new instance
                            subprocess.Popen([sys.executable], cwd=current_dir)
                            
                            # Exit current process
                            sys.exit(0)
                        else:
                            # Running as script - check for quick_launcher.py
                            launcher_script = os.path.join(current_dir, "launchers-scripts", "quick_launcher.py")
                            main_script = os.path.join(current_dir, 'main.py')
                            
                            print(f"[DEBUG] Launcher script: {launcher_script}")
                            print(f"[DEBUG] Main script: {main_script}")
                            
                            # Close current instance
                            completion_window.destroy()
                            _app_instance.destroy()
                            
                            import subprocess
                            python = sys.executable
                            
                            # Use launcher if available, otherwise use main.py
                            if os.path.exists(launcher_script):
                                print(f"[DEBUG] Using quick_launcher.py for restart")
                                if sys.platform == 'win32':
                                    subprocess.Popen(["pythonw", launcher_script], cwd=current_dir)
                                else:
                                    subprocess.Popen([python, launcher_script], cwd=current_dir)
                            else:
                                print(f"[DEBUG] Using main.py for restart")
                                subprocess.Popen([python, main_script], cwd=current_dir)
                            
                            # Exit current process
                            sys.exit(0)
                    
                    ctk.CTkButton(
                        comp_frame,
                        text="Restart Now",
                        command=restart_app,
                        fg_color=_colors["accent"],
                        hover_color=_colors["accent_hover"],
                        text_color=_colors["accent_text"],
                        height=35
                    ).pack(pady=(5, 5))
                    
                    ctk.CTkButton(
                        comp_frame,
                        text="Restart Later",
                        command=completion_window.destroy,
                        fg_color=_colors["card_bg"],
                        hover_color=_colors["card_hover"],
                        text_color=_colors["text"],
                        height=35
                    ).pack(pady=(0, 10))
                    
                except Exception as e:
                    print(f"[DEBUG] Extraction/update failed: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    extract_btn.configure(text="Extract & Update", state="normal")
                    
                    # Show error
                    error_label = ctk.CTkLabel(
                        frame,
                        text=f"Update failed: {str(e)}",
                        font=ctk.CTkFont(size=10),
                        text_color="red"
                    )
                    error_label.pack(pady=5)
            
            def open_folder():
                if sys.platform == 'win32':
                    os.startfile(downloads_folder)
                elif sys.platform == 'darwin':
                    os.system(f'open "{downloads_folder}"')
                else:
                    os.system(f'xdg-open "{downloads_folder}"')
                success_window.destroy()
            
            # Button frame with 3 buttons
            button_container = ctk.CTkFrame(frame, fg_color="transparent")
            button_container.pack(pady=(5, 10), fill="x", padx=10)
            
            extract_btn = ctk.CTkButton(
                button_container,
                text="Extract & Update",
                command=extract_and_update,
                fg_color=_colors["accent"],
                hover_color=_colors["accent_hover"],
                text_color=_colors["accent_text"],
                height=35,
                font=ctk.CTkFont(size=12, weight="bold")
            )
            extract_btn.pack(fill="x", pady=(0, 5))
            
            ctk.CTkButton(
                button_container,
                text="Open Downloads Folder",
                command=open_folder,
                fg_color=_colors["card_bg"],
                hover_color=_colors["card_hover"],
                text_color=_colors["text"],
                height=35
            ).pack(fill="x", pady=(0, 5))
            
            ctk.CTkButton(
                button_container,
                text="Close",
                command=success_window.destroy,
                fg_color=_colors["card_bg"],
                hover_color=_colors["card_hover"],
                text_color=_colors["text"],
                height=35
            ).pack(fill="x")
            
        except Exception as e:
            print(f"[DEBUG] Download failed: {e}")
            download_btn.configure(text="Download Update", state="normal")
            
            # Show error and fallback to browser
            error_msg = f"Download failed: {str(e)}\n\nOpening GitHub page instead..."
            ctk.CTkLabel(
                main_frame,
                text=error_msg,
                font=ctk.CTkFont(size=10),
                text_color="red"
            ).pack(pady=5)
            
            update_window.after(2000, lambda: [
                webbrowser.open("https://github.com/johanssonserlanderkevin-sys/BeamSkin-Studio"),
                update_window.destroy()
            ])

    def maybe_later():
        print(f"[DEBUG] maybe_later called")
        """Close update window"""
        print(f"[DEBUG] User chose maybe later")
        update_window.destroy()

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

            if is_newer_version(latest_version, CURRENT_VERSION):
                print(f"[DEBUG] UPDATE AVAILABLE! {CURRENT_VERSION} -> {latest_version}")

                if _app_instance:
                    _app_instance.after(0, lambda: prompt_update(latest_version))
                else:

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