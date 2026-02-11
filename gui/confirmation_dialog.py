"""
Custom themed confirmation dialogs for BeamSkin Studio
"""
import customtkinter as ctk
from typing import Callable, Optional

class ConfirmationDialog:
    """A themed confirmation dialog that matches the main GUI"""

    def __init__(self, parent, title: str, message: str, colors: dict,
                 confirm_text: str = "Yes", cancel_text: str = "No",
                 icon: str = "❓", danger: bool = False):
        """
        Create a confirmation dialog

        Args:
            parent: Parent window
            title: Dialog title
            message: Dialog message
            colors: Theme colors dictionary
            confirm_text: Text for confirm button (default: "Yes")
            cancel_text: Text for cancel button (default: "No")
            icon: Emoji icon to display
            danger: If True, uses error/warning colors for confirm button
        """
        self.result = False
        self.colors = colors

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("600x350")
        self.dialog.resizable(False, False)

        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (300 // 2)
        self.dialog.geometry(f"600x350+{x}+{y}")

        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.attributes('-topmost', True)
        self.dialog.after(100, lambda: self.dialog.attributes('-topmost', False))

        main_frame = ctk.CTkFrame(self.dialog, fg_color=colors["frame_bg"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        icon_label = ctk.CTkLabel(
            main_frame,
            text=icon,
            font=ctk.CTkFont(size=48),
            text_color=colors["text"],
            anchor="center"
        )
        icon_label.pack(fill="x", pady=(15, 10), padx=(67, 0))

        title_label = ctk.CTkLabel(
            main_frame,
            text=title,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=colors["error"] if danger else colors["text"],
            anchor="center"
        )
        title_label.pack(pady=(0, 15), anchor="center")

        message_frame = ctk.CTkFrame(main_frame, fg_color=colors["card_bg"], corner_radius=10)
        message_frame.pack(fill="both", expand=True, padx=10, pady=(0, 15))

        message_label = ctk.CTkLabel(
            message_frame,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color=colors["text"],
            wraplength=540,
            justify="center",
            anchor="center"
        )
        message_label.pack(pady=20, padx=20, expand=True)

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(0, 10))

        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        cancel_btn = ctk.CTkButton(
            button_frame,
            text=cancel_text,
            command=self._on_cancel,
            fg_color=colors["card_bg"],
            hover_color=colors["card_hover"],
            text_color=colors["text"],
            border_width=2,
            border_color=colors["border"],
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14)
        )
        cancel_btn.grid(row=0, column=0, padx=(10, 5), sticky="ew")

        if danger:
            fg_color = colors["error"]
            hover_color = colors["error_hover"]
        else:
            fg_color = colors["accent"]
            hover_color = colors["accent_hover"]

        confirm_btn = ctk.CTkButton(
            button_frame,
            text=confirm_text,
            command=self._on_confirm,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=colors["accent_text"],
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        confirm_btn.grid(row=0, column=1, padx=(5, 10), sticky="ew")

        self.dialog.bind("<Escape>", lambda e: self._on_cancel())

        if not danger:
            confirm_btn.focus_set()
        else:
            cancel_btn.focus_set()

    def _on_confirm(self):
        """Handle confirm button click"""
        self.result = True
        self.dialog.destroy()

    def _on_cancel(self):
        """Handle cancel button click"""
        self.result = False
        self.dialog.destroy()

    def show(self) -> bool:
        """Show the dialog and return the result"""
        self.dialog.wait_window()
        return self.result

class InfoDialog:
    """A themed information dialog (OK button only)"""

    def __init__(self, parent, title: str, message: str, colors: dict,
                 button_text: str = "OK", icon: str = "ℹ️", type: str = "info"):
        """
        Create an information dialog

        Args:
            parent: Parent window
            title: Dialog title
            message: Dialog message
            colors: Theme colors dictionary
            button_text: Text for the button (default: "OK")
            icon: Emoji icon to display
            type: Dialog type ("info", "warning", "error", "success")
        """
        self.colors = colors

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("600x350")
        self.dialog.resizable(False, False)

        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (350 // 2)
        self.dialog.geometry(f"600x350+{x}+{y}")

        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.attributes('-topmost', True)
        self.dialog.after(100, lambda: self.dialog.attributes('-topmost', False))

        main_frame = ctk.CTkFrame(self.dialog, fg_color=colors["frame_bg"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        icon_label = ctk.CTkLabel(
            main_frame,
            text=icon,
            font=ctk.CTkFont(size=48),
            text_color=colors["text"],
            anchor="center"
        )
        icon_label.pack(fill="x", pady=(15, 10), padx=(40, 0))

        if type == "error":
            title_color = colors["error"]
        elif type == "warning":
            title_color = colors["warning"]
        elif type == "success":
            title_color = colors["success"]
        else:
            title_color = colors["text"]

        title_label = ctk.CTkLabel(
            main_frame,
            text=title,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=title_color,
            anchor="center"
        )
        title_label.pack(pady=(0, 15), anchor="center")

        message_frame = ctk.CTkFrame(main_frame, fg_color=colors["card_bg"], corner_radius=10)
        message_frame.pack(fill="both", expand=True, padx=10, pady=(0, 15))

        message_label = ctk.CTkLabel(
            message_frame,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color=colors["text"],
            wraplength=540,
            justify="center",
            anchor="center"
        )
        message_label.pack(pady=20, padx=20, expand=True)

        ok_btn = ctk.CTkButton(
            main_frame,
            text=button_text,
            command=self._on_ok,
            fg_color=colors["accent"],
            hover_color=colors["accent_hover"],
            text_color=colors["accent_text"],
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        ok_btn.pack(pady=(0, 5), padx=40, fill="x")

        self.dialog.bind("<Escape>", lambda e: self._on_ok())
        self.dialog.bind("<Return>", lambda e: self._on_ok())

        ok_btn.focus_set()

    def _on_ok(self):
        """Handle OK button click"""
        self.dialog.destroy()

    def show(self):
        """Show the dialog"""
        self.dialog.wait_window()

def askyesno(parent, title: str, message: str, colors: dict, icon: str = "❓", danger: bool = False) -> bool:
    """
    Show a yes/no confirmation dialog

    Args:
        parent: Parent window
        title: Dialog title
        message: Dialog message
        colors: Theme colors dictionary
        icon: Emoji icon to display
        danger: If True, uses error/warning colors

    Returns:
        True if user clicked Yes, False otherwise
    """
    dialog = ConfirmationDialog(parent, title, message, colors,
                                confirm_text="Yes", cancel_text="No",
                                icon=icon, danger=danger)
    return dialog.show()

def askokcancel(parent, title: str, message: str, colors: dict, icon: str = "❓", danger: bool = False) -> bool:
    """
    Show an OK/Cancel confirmation dialog

    Args:
        parent: Parent window
        title: Dialog title
        message: Dialog message
        colors: Theme colors dictionary
        icon: Emoji icon to display
        danger: If True, uses error/warning colors

    Returns:
        True if user clicked OK, False otherwise
    """
    dialog = ConfirmationDialog(parent, title, message, colors,
                                confirm_text="OK", cancel_text="Cancel",
                                icon=icon, danger=danger)
    return dialog.show()

def showinfo(parent, title: str, message: str, colors: dict, icon: str = "ℹ️"):
    """Show an information dialog"""
    dialog = InfoDialog(parent, title, message, colors, icon=icon, type="info")
    dialog.show()

def showwarning(parent, title: str, message: str, colors: dict, icon: str = "⚠️"):
    """Show a warning dialog"""
    dialog = InfoDialog(parent, title, message, colors, icon=icon, type="warning")
    dialog.show()

def showerror(parent, title: str, message: str, colors: dict, icon: str = "❌"):
    """Show an error dialog"""
    dialog = InfoDialog(parent, title, message, colors, icon=icon, type="error")
    dialog.show()

def showsuccess(parent, title: str, message: str, colors: dict, icon: str = "✅"):
    """Show a success dialog"""
    dialog = InfoDialog(parent, title, message, colors, icon=icon, type="success")
    dialog.show()