"""GitHub update checker with custom UI - OS-specific repository support"""
import requests
from tkinter import messagebox
import webbrowser
import customtkinter as ctk
import re
import os
import sys
import platform

def get_github_repo():
    """Get the appropriate GitHub repository URL based on the operating system"""
    if sys.platform == 'win32':
        return "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Beta"
    else:  # Linux and other platforms
        return "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Linux-Beta"

def get_github_raw_url():
    """Get the raw GitHub URL for version.txt based on the operating system"""
    if sys.platform == 'win32':
        return "https://raw.githubusercontent.com/BeamSkin-Studio/BeamSkin-Studio-Beta/main/version.txt"
    else:  # Linux and other platforms
        return "https://raw.githubusercontent.com/BeamSkin-Studio/BeamSkin-Studio-Linux-Beta/main/version.txt"

def get_base_path():
    """Get the base path for resources (works in dev and PyInstaller)"""
    print(f"[DEBUG] get_base_path called")
    print(f"[DEBUG] Platform: {sys.platform}")
    print(f"[DEBUG] Using repo: {get_github_repo()}")
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def read_version():
    """Read version from version.txt and return formatted version string"""
    print(f"[DEBUG] read_version called")
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
    """Set the app instance and colors for update prompts"""
    print(f"[DEBUG] set_app_instance called")
    global _app_instance, _colors
    _app_instance = app
    _colors = colors

def parse_version(version_string):
    """
    Parse version string into comparable tuple.
    Examples:
        "0.3.6.Beta" -> (0, 3, 6, 2)
        "0.4.0.Beta" -> (0, 4, 0, 2)
        "1.0.0.Stable" -> (1, 0, 0, 0)
    """
    print(f"[DEBUG] parse_version called")

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
    """
    Compare two version strings to see if remote is newer.
    Returns True if remote_version is newer than current_version.
    """
    print(f"[DEBUG] is_newer_version called")
    try:
        remote_tuple = parse_version(remote_version)
        current_tuple = parse_version(current_version)

        print(f"[DEBUG] Parsed current: {current_version} -> {current_tuple}")
        print(f"[DEBUG] Parsed remote: {remote_version} -> {remote_tuple}")

        if remote_tuple[:3] != current_tuple[:3]:
            # Different version numbers
            return remote_tuple[:3] > current_tuple[:3]
        else:
            # Same version, check stability (lower = more stable)
            return remote_tuple[3] < current_tuple[3]

    except Exception as e:
        print(f"[DEBUG] Version comparison error: {e}")
        # Fallback: just check if strings differ
        return remote_version != current_version

def prompt_update(new_version):
    """Show custom update notification window"""
    print(f"[DEBUG] prompt_update called")
    print(f"\n[DEBUG] ========== UPDATE PROMPT ==========")
    print(f"[DEBUG] Showing update dialog for version: {new_version}")

    if _app_instance is None or _colors is None:
        # Fallback to basic messagebox if app instance not set
        response = messagebox.askyesno(
            "Update Available",
            f"A new version is available!\n\n"
            f"Current: {CURRENT_VERSION}\n"
            f"Latest: {new_version}\n\n"
            f"Would you like to download it now?"
        )
        if response:
            webbrowser.open(get_github_repo())
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
        """Download the latest repository ZIP"""
        print(f"[DEBUG] download_update called")
        print(f"[DEBUG] Downloading latest version ZIP from: {get_github_repo()}")
        
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
            # Determine the correct repository name based on OS
            if sys.platform == 'win32':
                repo_name = "BeamSkin-Studio-Beta"
            else:
                repo_name = "BeamSkin-Studio-Linux-Beta"
            
            # GitHub repository ZIP URL
            zip_url = f"https://github.com/BeamSkin-Studio/{repo_name}/archive/refs/heads/main.zip"
            print(f"[DEBUG] Download URL: {zip_url}")
            
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
                            text=f"Downloading {filename}... {progress_mb:.1f}MB / {total_mb:.1f}MB"
                        )
                        update_window.update()
            
            print(f"[DEBUG] Download complete: {filepath}")
            status_label.configure(text="Download complete!")
            update_window.update()
            
            # Show success window
            success_window = ctk.CTkToplevel(update_window)
            success_window.title("Download Complete")
            success_window.geometry("450x300")
            success_window.resizable(False, False)
            success_window.transient(update_window)
            success_window.grab_set()
            
            # Center window
            success_window.update_idletasks()
            width = success_window.winfo_width()
            height = success_window.winfo_height()
            x = (success_window.winfo_screenwidth() // 2) - (width // 2)
            y = (success_window.winfo_screenheight() // 2) - (height // 2)
            success_window.geometry(f"{width}x{height}+{x}+{y}")
            
            frame = ctk.CTkFrame(success_window, fg_color=_colors["frame_bg"])
            frame.pack(fill="both", expand=True, padx=15, pady=15)
            
            # Success icon
            ctk.CTkLabel(
                frame,
                text="✓",
                font=ctk.CTkFont(size=40, weight="bold"),
                text_color=_colors["accent"]
            ).pack(pady=(10, 5))
            
            ctk.CTkLabel(
                frame,
                text="Download Complete!",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=_colors["text"]
            ).pack(pady=(0, 10))
            
            ctk.CTkLabel(
                frame,
                text=f"Update file saved to:\n{filepath}",
                font=ctk.CTkFont(size=11),
                text_color=_colors["text_secondary"],
                justify="center"
            ).pack(pady=10)
            
            def extract_and_update():
                """Extract and apply the update"""
                print(f"[DEBUG] extract_and_update called")
                extract_btn.configure(text="Extracting...", state="disabled")
                
                try:
                    import zipfile
                    import tempfile
                    import shutil
                    
                    # Get current directory
                    if getattr(sys, 'frozen', False):
                        current_dir = os.path.dirname(sys.executable)
                    else:
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                    
                    print(f"[DEBUG] Current directory: {current_dir}")
                    print(f"[DEBUG] Extracting: {filepath}")
                    
                    # Create temp directory for extraction
                    temp_extract_dir = os.path.join(tempfile.gettempdir(), 'beamskin_update')
                    if os.path.exists(temp_extract_dir):
                        shutil.rmtree(temp_extract_dir)
                    os.makedirs(temp_extract_dir)
                    
                    # Extract zip
                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                        zip_ref.extractall(temp_extract_dir)
                    
                    print(f"[DEBUG] Extracted to: {temp_extract_dir}")
                    
                    # Find the extracted folder (GitHub adds repo name to the folder)
                    extracted_items = os.listdir(temp_extract_dir)
                    if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_dir, extracted_items[0])):
                        source_dir = os.path.join(temp_extract_dir, extracted_items[0])
                    else:
                        source_dir = temp_extract_dir
                    
                    print(f"[DEBUG] Source directory: {source_dir}")
                    
                    # Copy files
                    for item in os.listdir(source_dir):
                        source = os.path.join(source_dir, item)
                        dest = os.path.join(current_dir, item)
                        
                        try:
                            if os.path.isdir(source):
                                if os.path.exists(dest):
                                    shutil.rmtree(dest)
                                shutil.copytree(source, dest)
                            else:
                                if os.path.exists(dest):
                                    os.remove(dest)
                                shutil.copy2(source, dest)
                            print(f"[DEBUG] Updated: {item}")
                        except Exception as e:
                            print(f"[DEBUG] Warning - could not update {item}: {e}")
                    
                    # Cleanup
                    shutil.rmtree(temp_extract_dir)
                    
                    print(f"[DEBUG] Update complete!")
                    
                    # Show completion dialog
                    success_window.destroy()
                    update_window.destroy()
                    
                    completion_window = ctk.CTkToplevel(_app_instance)
                    completion_window.title("Update Complete")
                    completion_window.geometry("400x250")
                    completion_window.resizable(False, False)
                    completion_window.transient(_app_instance)
                    completion_window.grab_set()
                    
                    # Center window
                    completion_window.update_idletasks()
                    width = completion_window.winfo_width()
                    height = completion_window.winfo_height()
                    x = (completion_window.winfo_screenwidth() // 2) - (width // 2)
                    y = (completion_window.winfo_screenheight() // 2) - (height // 2)
                    completion_window.geometry(f"{width}x{height}+{x}+{y}")
                    
                    comp_frame = ctk.CTkFrame(completion_window, fg_color=_colors["frame_bg"])
                    comp_frame.pack(fill="both", expand=True, padx=15, pady=15)
                    
                    ctk.CTkLabel(
                        comp_frame,
                        text="✓",
                        font=ctk.CTkFont(size=40, weight="bold"),
                        text_color=_colors["accent"]
                    ).pack(pady=(10, 5))
                    
                    ctk.CTkLabel(
                        comp_frame,
                        text="Update Installed!",
                        font=ctk.CTkFont(size=16, weight="bold"),
                        text_color=_colors["text"]
                    ).pack(pady=(0, 10))
                    
                    ctk.CTkLabel(
                        comp_frame,
                        text="The update has been installed successfully.\nPlease restart the application to use the new version.",
                        font=ctk.CTkFont(size=11),
                        text_color=_colors["text_secondary"],
                        justify="center"
                    ).pack(pady=10)
                    
                    def restart_app():
                        """Restart the application"""
                        print(f"[DEBUG] Restarting application...")
                        
                        if getattr(sys, 'frozen', False):
                            # Running as executable
                            exe_path = sys.executable
                            print(f"[DEBUG] Executable path: {exe_path}")
                            
                            # Close windows
                            completion_window.destroy()
                            _app_instance.destroy()
                            
                            # Start new instance
                            import subprocess
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
                webbrowser.open(get_github_repo()),
                update_window.destroy()
            ])

    def maybe_later():
        """Close update window"""
        print(f"[DEBUG] maybe_later called")
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
    """Check for updates from OS-specific GitHub repository"""
    print(f"[DEBUG] check_for_updates called")
    print(f"\n[DEBUG] ========== UPDATE CHECK STARTED ==========")
    print(f"[DEBUG] Platform detected: {sys.platform}")
    print(f"[DEBUG] Checking repository: {get_github_repo()}")
    print(f"[DEBUG] Current version: {CURRENT_VERSION}")

    url = get_github_raw_url()
    print(f"[DEBUG] Fetching version from: {url}")

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
                    # Fallback to messagebox if no app instance
                    response = messagebox.askyesno(
                        "Update Available",
                        f"Version {latest_version} is available!\nDownload now?"
                    )
                    if response:
                        webbrowser.open(get_github_repo())
            else:
                print(f"[DEBUG] Already on latest version (or newer)")
    except Exception as e:
        print(f"[DEBUG] Update check failed: {e}")

    print(f"[DEBUG] ========== UPDATE CHECK COMPLETE ==========\n")