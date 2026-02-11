"""Debug utilities"""
import customtkinter as ctk
import sys
import io
from datetime import datetime

debug_mode_enabled = False
debug_window = None
debug_textbox = None

def setup_universal_scroll_handler(app):
    """Sets up intelligent scroll handling"""
    app.unbind_all("<MouseWheel>")
    app.unbind_all("<Button-4>")
    app.unbind_all("<Button-5>")

    def universal_scroll(event):
        x, y = app.winfo_pointerxy()
        widget = app.winfo_containing(x, y)
        if not widget:
            return

        scrollable_frame = None
        current = widget
        while current:
            if isinstance(current, ctk.CTkScrollableFrame):
                scrollable_frame = current
                break
            try:
                current = current.master
            except:
                break

        if scrollable_frame:
            try:
                if event.num == 4 or event.delta > 0:
                    scrollable_frame._parent_canvas.yview_scroll(-25, "units")
                elif event.num == 5 or event.delta < 0:
                    scrollable_frame._parent_canvas.yview_scroll(25, "units")
                return "break"
            except:
                pass

    app.bind_all("<MouseWheel>", universal_scroll, add="+")
    app.bind_all("<Button-4>", universal_scroll, add="+")
    app.bind_all("<Button-5>", universal_scroll, add="+")

class DebugOutput(io.StringIO):
    """Custom output stream for debug window"""
    def __init__(self):
        super().__init__()

        self.terminal = sys.stdout
        self.enabled = True

    def write(self, message):

        if self.terminal is not None:
            try:
                self.terminal.write(message)
            except Exception:
                pass

        if self.enabled and debug_mode_enabled and debug_textbox is not None:
            try:
                if debug_textbox.winfo_exists():
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    debug_textbox.insert("end", f"[{timestamp}] {message}")
                    debug_textbox.see("end")
            except Exception:
                pass

        return len(message)

    def flush(self):
        if self.terminal is not None and hasattr(self.terminal, 'flush'):
            self.terminal.flush()

def create_debug_window(app, colors, on_close_callback=None):
    """Create debug console window"""
    global debug_window, debug_textbox, debug_mode_enabled

    if debug_window is not None and debug_window.winfo_exists():
        debug_window.lift()
        return

    debug_mode_enabled = True
    debug_window = ctk.CTkToplevel(app)
    debug_window.title("Debug Console")
    debug_window.geometry("800x600")
    debug_window.configure(fg_color=colors["app_bg"])

    debug_window.attributes('-topmost', True)
    debug_window.transient(app)
    debug_window.lift()
    debug_window.focus_force()

    header_frame = ctk.CTkFrame(debug_window, corner_radius=12,
                                fg_color=colors["frame_bg"])
    header_frame.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(header_frame, text="Debug Console",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=colors["text"]).pack(side="left", padx=20, pady=10)

    def clear_debug():
        debug_textbox.delete("0.0", "end")
        print("[DEBUG] Console cleared")

    def copy_debug():
        content = debug_textbox.get("0.0", "end-1c")
        app.clipboard_clear()
        app.clipboard_append(content)
        print("[DEBUG] Content copied")

    ctk.CTkButton(header_frame, text="Copy All", width=80, command=copy_debug,
                 fg_color=colors["card_bg"],
                 hover_color=colors["card_hover"]).pack(side="right", padx=5, pady=10)

    ctk.CTkButton(header_frame, text="Clear", width=80, command=clear_debug,
                 fg_color=colors["card_bg"],
                 hover_color=colors["card_hover"]).pack(side="right", padx=5, pady=10)

    text_color = colors["accent"] if colors["app_bg"] == "#0a0a0a" else "#1a1a1a"

    debug_textbox = ctk.CTkTextbox(debug_window, wrap="word",
                                   fg_color=colors["card_bg"],
                                   text_color=text_color,
                                   font=("Consolas", 10))
    debug_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def on_close():
        global debug_mode_enabled
        debug_mode_enabled = False
        debug_window.destroy()

        if on_close_callback and callable(on_close_callback):
            on_close_callback()

    debug_window.protocol("WM_DELETE_WINDOW", on_close)
    print("[DEBUG] Debug console opened")

def toggle_debug_mode(app, colors, on_close=None):
    """Toggle debug mode on/off"""
    global debug_mode_enabled, debug_output
    if debug_mode_enabled:
        if debug_window and debug_window.winfo_exists():
            debug_window.destroy()
        debug_mode_enabled = False

        if hasattr(sys, '_original_stdout'):
            sys.stdout = sys._original_stdout

        if on_close and callable(on_close):
            on_close()
    else:
        create_debug_window(app, colors, on_close_callback=on_close)

        debug_output = DebugOutput()
        if not hasattr(sys, '_original_stdout'):
            sys._original_stdout = sys.stdout
        sys.stdout = debug_output
        print("[DEBUG] Debug console activated - output redirection enabled")