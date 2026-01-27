"""
Dialog Components - Reusable dialog windows and notifications
"""
import customtkinter as ctk
import webbrowser
from gui.state import state
from gui.components.setup_wizard import show_setup_wizard


def show_notification(app, message, type="info", duration=3000):


    print(f"[DEBUG] show_notification called")
    """
    Display a notification at the top of the app.
    
    Args:
        app: The main CTk application window
        message: Notification message
        type: Notification type ('info', 'success', 'warning', 'error')
        duration: How long to show notification in milliseconds (0 = permanent)
    
    Types: 'info', 'success', 'warning', 'error'
    """
    if not app:
        print(f"[WARNING] Could not show notification (no app window): {message}")
        print(f"[{type.upper()}] {message}")
        return
    
    # Ensure notification frame exists
    if not hasattr(app, 'notification_frame'):
        app.notification_frame = ctk.CTkFrame(app, fg_color="transparent")
    
    # Clear existing notifications
    for child in app.notification_frame.winfo_children():
        child.destroy()
    
    icons = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠",
        "info": "ℹ"
    }
    
    colors_map = {
        "success": {"bg": state.colors["success"], "text": state.colors["accent_text"]},
        "error": {"bg": state.colors["error"], "text": "white"},
        "warning": {"bg": state.colors["warning"], "text": state.colors["accent_text"]},
        "info": {"bg": state.colors["accent"], "text": state.colors["accent_text"]}
    }
    
    color_scheme = colors_map.get(type, colors_map["info"])
    icon = icons.get(type, "ℹ")
    
    # Calculate width based on message length
    base_width = 100
    char_width = 9
    calculated_width = base_width + (len(message) * char_width)
    
    min_width = 300
    max_width = 1200
    notification_width = max(min_width, min(calculated_width, max_width))
    
    notification_content = ctk.CTkFrame(
        app.notification_frame,
        fg_color=color_scheme["bg"],
        corner_radius=12,
        width=notification_width,
        height=50
    )
    notification_content.pack(padx=0, pady=10)
    notification_content.pack_propagate(False)
    
    ctk.CTkLabel(
        notification_content,
        text=icon,
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=color_scheme["text"],
        width=40
    ).pack(side="left", padx=(15, 5))
    
    ctk.CTkLabel(
        notification_content,
        text=message,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=color_scheme["text"],
        anchor="w"
    ).pack(side="left", fill="x", expand=True, padx=(5, 15))
    
    app.notification_frame.place(relx=0.5, y=60, anchor="n")
    app.notification_frame.lift()
    
    if duration > 0:
        app.after(duration, lambda: app.notification_frame.place_forget())


def show_confirmation_dialog(parent, title: str, message: str) -> bool:


    print(f"[DEBUG] show_confirmation_dialog called")
    """
    Show a custom confirmation dialog that matches the app theme
    
    Args:
        parent: Parent window
        title: Dialog title
        message: Dialog message
    
    Returns:
        True if user clicked Yes, False if clicked No
    """
    result = {"confirmed": False}
    
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry("500x250")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()
    
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    # Configure colors
    dialog.configure(fg_color=state.colors["frame_bg"])
    
    # Main content frame
    content_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    content_frame.pack(fill="both", expand=True, padx=30, pady=30)
    
    # Warning icon
    ctk.CTkLabel(
        content_frame,
        text="⚠️",
        font=ctk.CTkFont(size=48)
    ).pack(pady=(0, 15))
    
    # Title
    ctk.CTkLabel(
        content_frame,
        text=title,
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=state.colors["text"]
    ).pack(pady=(0, 10))
    
    # Message
    ctk.CTkLabel(
        content_frame,
        text=message,
        font=ctk.CTkFont(size=13),
        text_color=state.colors["text"],
        wraplength=400,
        justify="center"
    ).pack(pady=(0, 25))
    
    # Buttons frame
    button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
    button_frame.pack(fill="x")
    
    def on_yes():
    
        print(f"[DEBUG] on_yes called")
        result["confirmed"] = True
        dialog.destroy()
    
    def on_no():
    
        print(f"[DEBUG] on_no called")
        result["confirmed"] = False
        dialog.destroy()
    
    # Yes button
    yes_btn = ctk.CTkButton(
        button_frame,
        text="Yes, Clear Project",
        command=on_yes,
        width=180,
        height=40,
        fg_color=state.colors["error"],
        hover_color=state.colors["error_hover"],
        text_color="white",
        corner_radius=8,
        font=ctk.CTkFont(size=13, weight="bold")
    )
    yes_btn.pack(side="left", expand=True, padx=(0, 5))
    
    # No button
    no_btn = ctk.CTkButton(
        button_frame,
        text="Cancel",
        command=on_no,
        width=180,
        height=40,
        fg_color=state.colors["card_bg"],
        hover_color=state.colors["card_hover"],
        text_color=state.colors["text"],
        corner_radius=8,
        font=ctk.CTkFont(size=13)
    )
    no_btn.pack(side="right", expand=True, padx=(5, 0))
    
    # Wait for dialog to close
    parent.wait_window(dialog)
    
    return result["confirmed"]


def show_update_dialog(app, new_version):


    print(f"[DEBUG] show_update_dialog called")
    """Show integrated update notification window"""
    print(f"\n[DEBUG] ========== UPDATE PROMPT ==========")
    print(f"[DEBUG] Showing update dialog for version: {new_version}")
    
    from core.updater import CURRENT_VERSION
    
    update_window = ctk.CTkToplevel(app)
    update_window.title("Update Available")
    update_window.geometry("500x350")
    update_window.resizable(False, False)
    update_window.transient(app)
    update_window.grab_set()
    
    update_window.update_idletasks()
    width = update_window.winfo_width()
    height = update_window.winfo_height()
    x = (update_window.winfo_screenwidth() // 2) - (width // 2)
    y = (update_window.winfo_screenheight() // 2) - (height // 2)
    update_window.geometry(f"{width}x{height}+{x}+{y}")
    
    main_frame = ctk.CTkFrame(update_window, fg_color=state.colors["frame_bg"])
    main_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    title_label = ctk.CTkLabel(
        main_frame,
        text="🎉 Update Available!",
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=state.colors["accent"]
    )
    title_label.pack(pady=(5, 15))
    
    info_frame = ctk.CTkFrame(main_frame, fg_color=state.colors["card_bg"], corner_radius=10)
    info_frame.pack(fill="x", padx=10, pady=10)
    
    current_label = ctk.CTkLabel(
        info_frame,
        text=f"Current Version: {CURRENT_VERSION}",
        font=ctk.CTkFont(size=13),
        text_color=state.colors["text"]
    )
    current_label.pack(pady=(10, 5))
    
    arrow_label = ctk.CTkLabel(
        info_frame,
        text="↓",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=state.colors["accent"]
    )
    arrow_label.pack(pady=2)
    
    new_label = ctk.CTkLabel(
        info_frame,
        text=f"New Version: {new_version}",
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=state.colors["accent"]
    )
    new_label.pack(pady=(5, 10))
    
    message_label = ctk.CTkLabel(
        main_frame,
        text="Would you like to open the GitHub page to download it?",
        font=ctk.CTkFont(size=12),
        text_color=state.colors["text"]
    )
    message_label.pack(pady=(10, 15))
    
    button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(fill="x", pady=(5, 10), padx=10)
    
    def download_update():
    
        print(f"[DEBUG] download_update called")
        print(f"[DEBUG] User chose to download update")
        print(f"[DEBUG] Opening GitHub page...")
        webbrowser.open("https://github.com/johanssonserlanderkevin-sys/BeamSkin-Studio")
        print(f"[DEBUG] GitHub page opened")
        update_window.destroy()
    
    def skip_update():
    
        print(f"[DEBUG] skip_update called")
        print(f"[DEBUG] User declined update")
        update_window.destroy()
    
    download_btn = ctk.CTkButton(
        button_frame,
        text="Download Update",
        command=download_update,
        fg_color=state.colors["accent"],
        hover_color=state.colors["accent_hover"],
        text_color=state.colors["accent_text"],
        height=45,
        corner_radius=8,
        font=ctk.CTkFont(size=14, weight="bold")
    )
    download_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))
    
    later_btn = ctk.CTkButton(
        button_frame,
        text="Maybe Later",
        command=skip_update,
        fg_color=state.colors["card_bg"],
        hover_color=state.colors["card_hover"],
        text_color=state.colors["text"],
        height=45,
        corner_radius=8,
        font=ctk.CTkFont(size=14)
    )
    later_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
    print(f"[DEBUG] Update window displayed")
    print(f"[DEBUG] ========== UPDATE PROMPT COMPLETE ==========\n")


def show_wip_warning(app):


    print(f"[DEBUG] show_wip_warning called")
    """Show Work-In-Progress warning dialog on first launch"""
    print(f"\n[DEBUG] ========== WIP WARNING CHECK ==========")
    print(f"[DEBUG] first_launch setting: {state.app_settings.get('first_launch', True)}")
    
    if state.app_settings.get("first_launch", True):
        print(f"[DEBUG] First launch detected - showing WIP warning dialog")
        dialog = ctk.CTkToplevel(app)
        dialog.title("Welcome to BeamSkin Studio")
        dialog.geometry("500x650")
        dialog.transient(app)
        dialog.grab_set()
        print(f"[DEBUG] Dialog created")
        
        dialog.update_idletasks()
        dialog_x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        dialog_y = (dialog.winfo_screenheight() // 2) - (650 // 2)
        dialog.geometry(f"500x650+{dialog_x}+{dialog_y}")
        print(f"[DEBUG] Dialog centered at ({dialog_x}, {dialog_y})")
        
        dialog.configure(fg_color=state.colors["frame_bg"])
        
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        title_frame.pack(pady=(0, 20))
        
        ctk.CTkLabel(
            title_frame,
            text="⚠️",
            font=ctk.CTkFont(size=48),
            text_color=state.colors["text"]
        ).pack()
        
        ctk.CTkLabel(
            title_frame,
            text="Work-In-Progress Software",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=state.colors["text"]
        ).pack(pady=(10, 0))
        
        message_frame = ctk.CTkFrame(main_frame, fg_color=state.colors["card_bg"], corner_radius=12)
        message_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        message_text = (
            "BeamSkin Studio is in active development.\n\n"
            "Please be aware that:\n\n"
            "• Bugs and errors should be expected\n"
            "• Some features may not work as intended\n"
            "• Data loss or unexpected behavior may occur\n"
            "• Regular updates and changes are being made\n\n"
            "Known Limitations:\n\n"
            "• Car variations are NOT supported yet\n"
            "  (e.g., Ambulance, Box Truck, Sedan, Wagon)\n"
            "• Modded cars added via Developer tab\n"
            "  most likely won't work properly\n\n"
            "Thank you for your patience and understanding!"
        )
        
        ctk.CTkLabel(
            message_frame,
            text=message_text,
            font=ctk.CTkFont(size=17),
            text_color=state.colors["text"],
            justify="left"
        ).pack(padx=20, pady=20)
        
        dont_show_var = ctk.BooleanVar(value=False)
        checkbox = ctk.CTkCheckBox(
            main_frame,
            text="Don't show this message again",
            variable=dont_show_var,
            font=ctk.CTkFont(size=12),
            text_color=state.colors["text"]
        )
        checkbox.pack(pady=(0, 10))
        
        def on_ok():
        
            print(f"[DEBUG] on_ok called")
            print(f"[DEBUG] User clicked 'I Understand'")
            print(f"[DEBUG] Don't show again checkbox: {dont_show_var.get()}")
            if dont_show_var.get():
                from core.settings import save_settings
                state.app_settings["first_launch"] = False
                save_settings()
                print("[DEBUG] First launch warning disabled and settings saved")
            dialog.destroy()
            print(f"[DEBUG] Dialog closed")
        
        ctk.CTkButton(
            main_frame,
            text="I Understand",
            command=on_ok,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            width=200
        ).pack()
        
        print(f"[DEBUG] Waiting for user to close dialog...")
        app.wait_window(dialog)
        print(f"[DEBUG] ========== WIP WARNING COMPLETE ==========\n")
    else:
        print(f"[DEBUG] Not first launch - skipping WIP warning")
        print(f"[DEBUG] ========== WIP WARNING SKIPPED ==========\n")