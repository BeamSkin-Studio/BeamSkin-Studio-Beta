"""
Dialog Components - Reusable dialog windows and notifications
"""
import customtkinter as ctk
from gui.icon_helper import set_window_icon
import webbrowser
import threading
from gui.state import state
from gui.components.setup_wizard import show_setup_wizard

try:
    from core.localization import t
except ImportError:
    def t(key, **kwargs): return kwargs.get('default', key)






def run_startup_sequence(app, show_offline_dialog_fn=None, on_complete=None):
    def _step3_offline():
        """Show server offline dialog, then call on_complete."""
        import utils.connection as connection

        def _do():
            if not connection.is_online and show_offline_dialog_fn:
                print("[STARTUP] Server offline — showing offline dialog")
                show_offline_dialog_fn()
            else:
                print("[STARTUP] Server online — skipping offline dialog")
            if on_complete:
                on_complete()

        # Wait until the connection check has finished (poll every 150 ms, up to 10 s)
        _poll_offline(app, connection, _do, attempts=0)

    def _poll_offline(app, connection, callback, attempts):
        if connection.check_complete or attempts >= 67:
            app.after(0, callback)
        else:
            app.after(150, lambda: _poll_offline(app, connection, callback, attempts + 1))

    def _step2_updates():
        """Run update check; when done (dialog closed or no update), go to step 3."""
        print("[STARTUP] Checking for updates…")
        try:
            from core.updater import check_for_updates
            # check_for_updates now accepts on_done so step 3 fires after dialog closes
            threading.Thread(
                target=check_for_updates,
                kwargs={"on_done": lambda: app.after(0, _step3_offline)},
                daemon=True,
            ).start()
        except Exception as e:
            print(f"[STARTUP] Update check error: {e}")
            app.after(0, _step3_offline)

    def _step1b_changelog():
        """Show changelog for this version (once per version), then move to step 2."""
        print("[STARTUP] Checking changelog…")
        try:
            from core.updater import CURRENT_VERSION
            from gui.components.changelog_dialog import show_changelog_if_needed
            show_changelog_if_needed(app, CURRENT_VERSION)  # blocks via wait_window
        except Exception as e:
            print(f"[STARTUP] Changelog error: {e}")
        print("[STARTUP] Changelog step done — proceeding to update check")
        app.after(0, _step2_updates)

    def _step1_wip():
        """Show WIP warning (blocks until closed), then move to step 1b."""
        print("[STARTUP] Showing WIP warning…")
        show_wip_warning(app)          # blocks via wait_window
        print("[STARTUP] WIP warning closed — proceeding to changelog")
        app.after(0, _step1b_changelog)

    # Kick off the chain
    app.after(0, _step1_wip)



def show_notification(app, message, type="info", duration=3000):

    print(f"[DEBUG] show_notification called")
    
    if not app:
        print(f"[WARNING] Could not show notification (no app window): {message}")
        print(f"[{type.upper()}] {message}")
        return

    if not hasattr(app, 'notification_frame'):
        app.notification_frame = ctk.CTkFrame(app, fg_color="transparent")

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

    # Cap width: short messages stay compact, long ones wrap within MAX_WIDTH.
    MAX_WIDTH   = 560   # px — notification never wider than this
    ICON_SPACE  = 60    # px reserved for the icon column + padding
    CHAR_WIDTH  = 8     # rough px per character at font size 13
    TEXT_AREA   = MAX_WIDTH - ICON_SPACE - 30  # usable text width

    # Decide wraplength: only wrap when the text is actually long
    single_line_px = len(message) * CHAR_WIDTH
    if single_line_px <= TEXT_AREA:
        # Fits on one line — no wrapping needed, shrink the box to content
        notification_width = max(300, ICON_SPACE + single_line_px + 30)
        wrap = 0  # 0 = no wrapping
    else:
        # Too long for one line — pin to MAX_WIDTH and let text wrap
        notification_width = MAX_WIDTH
        wrap = TEXT_AREA

    notification_content = ctk.CTkFrame(
        app.notification_frame,
        fg_color=color_scheme["bg"],
        corner_radius=12,
        width=notification_width,
    )
    # Do NOT call pack_propagate(False) — let the frame grow vertically to
    # fit wrapped text instead of clipping it.
    notification_content.pack(padx=0, pady=10)

    ctk.CTkLabel(
        notification_content,
        text=icon,
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=color_scheme["text"],
        width=40
    ).pack(side="left", anchor="n", padx=(15, 5), pady=12)

    ctk.CTkLabel(
        notification_content,
        text=message,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=color_scheme["text"],
        anchor="w",
        justify="left",
        wraplength=wrap if wrap else 0,
    ).pack(side="left", fill="x", expand=True, padx=(5, 15), pady=12)

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
    set_window_icon(dialog)

    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f"{width}x{height}+{x}+{y}")

    dialog.configure(fg_color=state.colors["frame_bg"])

    content_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    content_frame.pack(fill="both", expand=True, padx=30, pady=30)

    ctk.CTkLabel(
        content_frame,
        text="⚠️",
        font=ctk.CTkFont(size=48)
    ).pack(pady=(0, 15))

    ctk.CTkLabel(
        content_frame,
        text=title,
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=state.colors["text"]
    ).pack(pady=(0, 10))

    ctk.CTkLabel(
        content_frame,
        text=message,
        font=ctk.CTkFont(size=13),
        text_color=state.colors["text"],
        wraplength=400,
        justify="center"
    ).pack(pady=(0, 25))

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

    parent.wait_window(dialog)

    return result["confirmed"]

def show_update_dialog(app, new_version):

    print(f"[DEBUG] show_update_dialog called")
    """Show integrated update notification window"""
    print(f"\n[DEBUG] ========== UPDATE PROMPT ==========")
    print(f"[DEBUG] Showing update dialog for version: {new_version}")

    from core.updater import CURRENT_VERSION

    update_window = ctk.CTkToplevel(app)
    update_window.title(t("dialogs.update_available", default="Update Available"))
    update_window.geometry("500x350")
    update_window.resizable(False, False)
    update_window.transient(app)
    update_window.grab_set()
    set_window_icon(update_window)

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
        text="🎉 " + t("dialogs.update_available", default="Update Available!"),
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=state.colors["accent"]
    )
    title_label.pack(pady=(5, 15))

    info_frame = ctk.CTkFrame(main_frame, fg_color=state.colors["card_bg"], corner_radius=10)
    info_frame.pack(fill="x", padx=10, pady=10)

    current_label = ctk.CTkLabel(
        info_frame,
        text=t("dialogs.current_version", version=CURRENT_VERSION, default=f"Current Version: {CURRENT_VERSION}"),
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
        text=t("dialogs.new_version", version=new_version, default=f"New Version: {new_version}"),
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=state.colors["accent"]
    )
    new_label.pack(pady=(5, 10))

    message_label = ctk.CTkLabel(
        main_frame,
        text=t("dialogs.update_message", default="Would you like to open the GitHub page to download it?"),
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
        text=t("dialogs.download_update", default="Download Update"),
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
        text=t("dialogs.maybe_later", default="Maybe Later"),
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
        dialog.title(t("dialogs.wip_warning_title", default="Welcome to BeamSkin Studio"))
        dialog.geometry("550x700")
        dialog.transient(app)
        dialog.grab_set()
        set_window_icon(dialog)
        print(f"[DEBUG] Dialog created")

        dialog.update_idletasks()
        dialog_x = (dialog.winfo_screenwidth() // 2) - (550 // 2)
        dialog_y = (dialog.winfo_screenheight() // 2) - (700 // 2)
        dialog.geometry(f"550x700+{dialog_x}+{dialog_y}")
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
            text=t("wip.wip_warning_title", default="Work-In-Progress Software"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=state.colors["text"]
        ).pack(pady=(10, 0))

        message_frame = ctk.CTkFrame(main_frame, fg_color=state.colors["card_bg"], corner_radius=12)
        message_frame.pack(fill="both", expand=True, pady=(0, 20))

        ctk.CTkLabel(
            message_frame,
            text=t("wip.wip_warning_message", default=(
                "Welcome to BeamSkin Studio!\n"
                "This application is currently in active development.\n"
                "While I strive to provide a stable experience, some features may not work\n\n"
                "Please note:\n"
                "Some features may be incomplete\n"
                "Occasional bugs or unexpected behavior may occur\n"
                "Updates and improvements are being made\n\n"
                "Your feedback helps me improve the software!\n"
                "If you encounter any issues, please report them on my GitHub page. "
                "Your bug reports and feature suggestions are valuable to making "
                "BeamSkin Studio better!\n\n"
                " I appreciate your understanding and support as I continue "
                "to enhance BeamSkin Studio."
            )),
            font=ctk.CTkFont(size=18),
            text_color=state.colors["text"],
            justify="center",
            wraplength=480
        ).pack(padx=20, pady=20, fill="both", expand=True)

        dont_show_var = ctk.BooleanVar(value=False)
        checkbox = ctk.CTkCheckBox(
            main_frame,
            text=t("wip.wip_dont_show", default="Don't show this message again"),
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
            text=t("wip.wip_understand", default="I Understand"),
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