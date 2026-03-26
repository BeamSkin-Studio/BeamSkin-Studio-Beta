import customtkinter as ctk
from gui.icon_helper import set_window_icon
from gui.state import state
from core.localization import t


def show_connection_dialog(parent, on_retry, on_offline):
    
    dialog = ctk.CTkToplevel(parent)
    set_window_icon(dialog)
    dialog.title("Connection Failed")
    dialog.geometry("460x260")
    dialog.resizable(False, False)
    dialog.configure(fg_color=state.colors["app_bg"])
    dialog.grab_set()
    dialog.lift()
    dialog.focus_force()

    # centre over parent
    dialog.update_idletasks()
    px = parent.winfo_x() + (parent.winfo_width()  // 2) - 230
    py = parent.winfo_y() + (parent.winfo_height() // 2) - 130
    dialog.geometry(f"460x280+{px}+{py}")

    # ── card ──────────────────────────────────────────────────────────────── #
    card = ctk.CTkFrame(dialog, fg_color=state.colors["card_bg"], corner_radius=16)
    card.pack(fill="both", expand=True, padx=20, pady=20)

    # icon + title row
    title_row = ctk.CTkFrame(card, fg_color="transparent")
    title_row.pack(fill="x", padx=24, pady=(22, 6))

    ctk.CTkLabel(
        title_row,
        text="⚠️",
        font=ctk.CTkFont(size=28),
    ).pack(side="left", padx=(0, 10))

    ctk.CTkLabel(
        title_row,
        text=t("Offline.title"),
        font=ctk.CTkFont(size=17, weight="bold"),
        text_color=state.colors["text"],
        anchor="w"
    ).pack(side="left", fill="x", expand=True)

    # body text
    ctk.CTkLabel(
        card,
        text=t("Offline.subtitle"),
        font=ctk.CTkFont(size=15),
        text_color=state.colors["text_secondary"],
        justify="left",
        wraplength=390,
        anchor="w"
    ).pack(fill="x", padx=24, pady=(0, 20))

    sep = ctk.CTkFrame(card, height=1, fg_color=state.colors["border"])
    sep.pack(fill="x", padx=24, pady=(0, 16))

    # buttons
    btn_row = ctk.CTkFrame(card, fg_color="transparent")
    btn_row.pack(fill="x", padx=24, pady=(0, 20))
    btn_row.columnconfigure(0, weight=1)
    btn_row.columnconfigure(1, weight=1)

    def _retry():
        dialog.destroy()
        on_retry()

    def _offline():
        dialog.destroy()
        on_offline()

    ctk.CTkButton(
        btn_row,
        text=t("Offline.retry"),
        height=40,
        fg_color=state.colors["accent"],
        hover_color=state.colors["accent_hover"],
        text_color=state.colors["accent_text"],
        corner_radius=10,
        font=ctk.CTkFont(size=13, weight="bold"),
        command=_retry
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

    ctk.CTkButton(
        btn_row,
        text=t("Offline.stay_offline"),
        height=40,
        fg_color=state.colors["frame_bg"],
        hover_color=state.colors["card_hover"],
        border_width=1,
        border_color=state.colors["border"],
        text_color=state.colors["text"],
        corner_radius=10,
        font=ctk.CTkFont(size=13, weight="bold"),
        command=_offline
    ).grid(row=0, column=1, sticky="ew", padx=(6, 0))