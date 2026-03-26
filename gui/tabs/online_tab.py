import os
import io
import sys
import json
import time
import zipfile
import shutil
import tempfile
import threading
import platform
import subprocess
import multiprocessing
import requests
from tkinter import filedialog
from typing import Optional, Callable
import customtkinter as ctk
from core.localization import t
from gui.state import state
import utils.connection as connection

# Pillow is optional — only needed for image previews
try:
    from PIL import Image as _PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

print("[DEBUG] Loading class: OnlineTab")

# ── availability gate ─────────────────────────────────────────────────────── #
ONLINE_UNAVAILABLE = True

# ── translation support ───────────────────────────────────────────────────── #
try:
    from deep_translator import GoogleTranslator as _GTranslator
    _TRANSLATE_AVAILABLE = True
    print("[TRANSLATE] deep-translator loaded OK")
except ImportError:
    _TRANSLATE_AVAILABLE = False
    print("[TRANSLATE] deep-translator not found — translation disabled")

_LOCALE_TO_GOOGLE: dict = {
    # Short codes (filename = e.g. "sv.json")
    "en": "en", "fr": "fr", "de": "de", "es": "es",
    "it": "it", "pt": "pt", "nl": "nl", "ru": "ru",
    "pl": "pl", "cs": "cs", "sk": "sk", "hu": "hu",
    "ro": "ro", "tr": "tr", "sv": "sv", "no": "no",
    "da": "da", "fi": "fi", "el": "el", "uk": "uk",
    "zh": "zh-CN", "ja": "ja", "ko": "ko", "ar": "ar",
    "he": "iw", "hi": "hi", "th": "th", "vi": "vi",
    "id": "id", "ms": "ms",
    # Long codes (filename = e.g. "sv_SE.json")
    "en_US": "en", "en_GB": "en",
    "fr_FR": "fr", "de_DE": "de",
    "es_ES": "es", "es_MX": "es",
    "it_IT": "it", "pt_PT": "pt", "pt_BR": "pt",
    "nl_NL": "nl", "ru_RU": "ru", "pl_PL": "pl",
    "cs_CZ": "cs", "sk_SK": "sk", "hu_HU": "hu",
    "ro_RO": "ro", "tr_TR": "tr", "sv_SE": "sv",
    "nb_NO": "no", "da_DK": "da", "fi_FI": "fi",
    "el_GR": "el", "uk_UA": "uk", "zh_CN": "zh-CN",
    "zh_TW": "zh-TW", "ja_JP": "ja", "ko_KR": "ko",
    "ar_SA": "ar", "he_IL": "iw", "hi_IN": "hi",
    "th_TH": "th", "vi_VN": "vi", "id_ID": "id", "ms_MY": "ms",
}

def _get_target_lang() -> str:
    """Return the deep-translator language code for the user's current UI language."""
    try:
        from core.localization import get_current_language
        locale = get_current_language()
        lang = _LOCALE_TO_GOOGLE.get(locale)
        print(f"[TRANSLATE] get_current_language() returned: {locale!r} → mapped to: {lang!r}")
        if lang:
            return lang
        # Fallback: try just the first 2 chars (e.g. "sv" from "sv_SE")
        short = locale[:2].lower()
        print(f"[TRANSLATE] No exact match — trying short code: {short!r}")
        return short
    except Exception as exc:
        print(f"[TRANSLATE] _get_target_lang error: {exc}")
        return "en"

_MAX_BYTES = 10 * 1024 * 1024   # 10 MB

AVAILABLE_TAGS = [
    "Realistic", "Fantasy", "Racing", "Off-Road", "Livery",
    "Police", "Fire", "Military", "Custom", "Fictional",
    "Stock", "JDM", "American", "European", "Retro",
    "Replica", "Formula", "Drift", "Rally", "Vintage",
    "Touring", "GT", "Endurance", "Drag", "Stadium",
    "Emergency", "Car", "Taxi", "Bus", "Truck", "Concept",
]


# ── helpers ───────────────────────────────────────────────────────────────── #

def _find_7zip() -> Optional[str]:
    """Return the 7-Zip executable path, or None if not found."""
    sys_name = platform.system()
    if sys_name == "Windows":
        for candidate in [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]:
            if os.path.exists(candidate):
                return candidate
        # Try PATH
        try:
            r = subprocess.run(["7z", "--help"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return "7z"
        except Exception:
            pass
    else:
        for cmd in ["7z", "7za", "7zz"]:
            try:
                r = subprocess.run([cmd, "--help"], capture_output=True, timeout=5)
                if r.returncode == 0:
                    return cmd
            except Exception:
                pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  ONLINE TAB  (container)
# ══════════════════════════════════════════════════════════════════════════════

class OnlineTab(ctk.CTkFrame):

    def __init__(self, parent, notification_callback: Optional[Callable] = None):
        super().__init__(parent, fg_color=state.colors["app_bg"], corner_radius=0)
        self.notification_callback = notification_callback
        self._build_ui()
        print("[DEBUG] OnlineTab created")

    # ── layout ──────────────────────────────────────────────────────────── #

    def _build_ui(self):
        # ── tab bar ──────────────────────────────────────────────────────── #
        tab_bar = ctk.CTkFrame(
            self, fg_color=state.colors["frame_bg"], height=56, corner_radius=0
        )
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        btn_row = ctk.CTkFrame(tab_bar, fg_color="transparent")
        btn_row.pack(side="left", padx=20, pady=10)

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        self._tab_frames: dict[str, ctk.CTkFrame] = {}

        TAB_DEFS = [
            ("report",   f"🚨  {t('online.tab_report', default='Report')}"),
            ("upload",   f"📤  {t('online.tab_upload', default='Upload')}"),
            ("download", f"📥  {t('online.tab_download', default='Download')}"),
        ]
        for key, label in TAB_DEFS:
            btn = ctk.CTkButton(
                btn_row, text=label, width=140, height=36, corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=state.colors["card_bg"],
                hover_color=state.colors["card_hover"],
                text_color=state.colors["text"],
                command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(side="left", padx=(0, 8))
            self._tab_btns[key] = btn

        # ── content area ─────────────────────────────────────────────────── #
        content = ctk.CTkFrame(self, fg_color=state.colors["app_bg"], corner_radius=0)
        content.pack(fill="both", expand=True)

        self._report_tab   = _ReportSubTab(content,   self.notification_callback)
        self._upload_tab   = _UploadSubTab(content,   self.notification_callback)
        self._download_tab = _DownloadSubTab(content, self.notification_callback)

        self._tab_frames = {
            "report":   self._report_tab,
            "upload":   self._upload_tab,
            "download": self._download_tab,
        }

        # Wire all retry buttons to the shared retry so one click connects all tabs
        self._report_tab.retry_btn.configure(command=self._shared_retry)
        self._upload_tab.retry_btn.configure(command=self._shared_retry)
        self._download_tab.retry_btn.configure(command=self._shared_retry)

        # Any individual tab that gets connected on its own notifies all others
        self._report_tab.on_connected   = self._on_shared_success
        self._upload_tab.on_connected   = self._on_shared_success
        self._download_tab.on_connected = self._on_shared_success

        # Rebuild UI immediately if a ban 403 is received mid-session
        self._report_tab.on_ban_detected = self.refresh_ui
        self._upload_tab.on_ban_detected = self.refresh_ui

        # Show the Report tab by default
        self._switch_tab("report")

        # ── availability overlay (disable by setting ONLINE_UNAVAILABLE=False) #
        if ONLINE_UNAVAILABLE:
            self._build_unavailable_overlay()

    # ── unavailability overlay ───────────────────────────────────────────── #

    def _build_unavailable_overlay(self):
        """
        Cover the entire Online tab with a translucent overlay that explains
        the feature is not yet live.  Toggle visibility by changing
        ONLINE_UNAVAILABLE at the top of this file.
        """
        overlay = ctk.CTkFrame(
            self,
            fg_color=state.colors["app_bg"],
            corner_radius=0,
        )
        # Sit on top of everything via place, filling the whole widget
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Semi-transparent backing card
        card = ctk.CTkFrame(
            overlay,
            fg_color=state.colors["frame_bg"],
            corner_radius=16,
            border_width=1,
            border_color=state.colors["border"],
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            card,
            text="🚧",
            font=ctk.CTkFont(size=52),
        ).pack(padx=48, pady=(36, 8))

        ctk.CTkLabel(
            card,
            text=t("online.unavailable"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=state.colors["text"],
        ).pack(padx=48, pady=(0, 6))

        ctk.CTkLabel(
            card,
            text=t("online.online_server"),
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text_secondary"],
            justify="center",
        ).pack(padx=48, pady=(0, 28))

    # ── tab switching ────────────────────────────────────────────────────── #

    def _switch_tab(self, key: str):
        for k, frame in self._tab_frames.items():
            frame.pack_forget()
            self._tab_btns[k].configure(
                fg_color=state.colors["card_bg"],
                hover_color=state.colors["card_hover"],
                text_color=state.colors["text"],
            )
        self._tab_frames[key].pack(fill="both", expand=True)
        self._tab_btns[key].configure(
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
        )
        if key == "download":
            self._download_tab.load_skins(from_tab_switch=True)

    # ── shared retry ─────────────────────────────────────────────────────── #

    def _shared_retry(self):
        """Retry connection and refresh ALL sub-tabs on success or failure."""
        for tab in (self._report_tab, self._upload_tab, self._download_tab):
            tab.status_label.configure(
                text="Retrying...", text_color=state.colors["text_secondary"])
            tab.retry_btn.pack_forget()

        connection.check_connection(
            on_success=lambda: self.after(0, self._on_shared_success),
            on_failure=lambda: self.after(0, self._on_shared_failure),
        )

    def _on_shared_success(self):
        for tab in (self._report_tab, self._upload_tab):
            tab._refresh_username_lock()
            tab._refresh_status_badge()
        if connection.is_banned:
            self._report_tab._apply_ban_mode()
            self._upload_tab._show_ban_overlay()
        self._report_tab._update_cooldown_ui()
        self._upload_tab._tick_upload_cooldown()
        self._download_tab._refresh_status_badge()

    def _on_shared_failure(self):
        for tab in (self._report_tab, self._upload_tab):
            tab._refresh_status_badge()
        self._download_tab._refresh_status_badge()

    # ── public API ───────────────────────────────────────────────────────── #

    def refresh_connection_state(self):
        """Call after connection check completes so the Report tab syncs."""
        self._report_tab._poll_connection()
        self._upload_tab._poll_connection()

    def refresh_ui(self):
        """Rebuild the entire tab after a language change."""
        # Remember which sub-tab was active
        active = next(
            (k for k, f in self._tab_frames.items() if f.winfo_ismapped()), "report"
        )
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
        self._switch_tab(active)


# ══════════════════════════════════════════════════════════════════════════════
#  REPORT SUB-TAB  (mirrors original report.py logic)
# ══════════════════════════════════════════════════════════════════════════════

class _ReportSubTab(ctk.CTkFrame):
    def __init__(self, parent, notification_callback):
        super().__init__(parent, fg_color=state.colors["app_bg"], corner_radius=0)
        self.notification_callback  = notification_callback
        self.on_connected    = None
        self.on_ban_detected = None   # set by OnlineTab — called when a ban 403 is received
        self._attachment_path: Optional[str] = None
        self._project_path:    Optional[str] = None
        self._last_cooldown:   float = 15 * 60
        self._cooldown_job             = None
        self._poll_attempts:   int   = 0
        self._build_ui()

    # ── UI build ─────────────────────────────────────────────────────────── #

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=state.colors["app_bg"])
        scroll.pack(fill="both", expand=True)

        card = ctk.CTkFrame(scroll, fg_color=state.colors["card_bg"], corner_radius=16)
        card.pack(fill="both", expand=True, padx=60, pady=40)

        # heading
        self._heading_lbl = ctk.CTkLabel(
            card, text=t("report.title"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=state.colors["text"], anchor="w",
        )
        self._heading_lbl.pack(fill="x", padx=30, pady=(28, 4))

        self._subtitle_lbl = ctk.CTkLabel(
            card,
            text=t("report.title_description"),
            font=ctk.CTkFont(size=13), text_color=state.colors["text_secondary"],
            anchor="w", wraplength=700, justify="left",
        )
        self._subtitle_lbl.pack(fill="x", padx=30, pady=(0, 10))

        # connection status row
        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=30, pady=(0, 14))
        self.status_label = ctk.CTkLabel(
            status_row, text="", font=ctk.CTkFont(size=12), anchor="w"
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self.retry_btn = ctk.CTkButton(
            status_row, text="🔄 Retry", width=100, height=30,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8,
            font=ctk.CTkFont(size=12), command=self._retry_connection,
        )
        self._refresh_status_badge()

        ctk.CTkFrame(card, height=2, fg_color=state.colors["border"]).pack(
            fill="x", padx=30, pady=(0, 22)
        )

        # ── Report type selector ─────────────────────────────────────────── #
        self._lbl(card, t("report.type")),
        type_row = ctk.CTkFrame(card, fg_color="transparent")
        type_row.pack(fill="x", padx=30, pady=(0, 18))

        self._report_type = ctk.StringVar(value="bug")
        TYPE_DEFS = [
            ("bug",      t("report.tabname")),
            ("suggest",  t("suggestion.tabname")),
            ("username", t("username.tabname")),
            ("appeal",   t("ban_appeal.tabname")),
        ]
        self._type_btns: dict[str, ctk.CTkButton] = {}
        for key, label in TYPE_DEFS:
            btn = ctk.CTkButton(
                type_row, text=label, width=160, height=36, corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=state.colors["card_bg"],
                hover_color=state.colors["card_hover"],
                text_color=state.colors["text"],
                command=lambda k=key: self._switch_report_type(k),
            )
            if not (key == "appeal" and not connection.is_banned):
                btn.pack(side="left", padx=(0, 8))
            self._type_btns[key] = btn

        # If banned, force appeal mode and hide other type buttons
        if connection.is_banned:
            self._switch_report_type("appeal", init=True)
            for k, b in self._type_btns.items():
                if k != "appeal":
                    b.pack_forget()
        else:
            self._switch_report_type("bug", init=True)

        # username
        self._lbl(card, t("common.username"))
        user_row = ctk.CTkFrame(card, fg_color="transparent")
        user_row.pack(fill="x", padx=30, pady=(0, 18))
        self.username_var = ctk.StringVar(value=connection.server_username)
        self.username_entry = ctk.CTkEntry(
            user_row, textvariable=self.username_var, height=40,
            fg_color=state.colors["frame_bg"], border_color=state.colors["border"],
            text_color=state.colors["text"], font=ctk.CTkFont(size=14),
            placeholder_text=t("common.username_placeholder"),
            state="disabled" if connection.username_locked else "normal",
        )
        self.username_entry.pack(side="left", fill="x", expand=True)
        self.lock_label = ctk.CTkLabel(
            user_row,
            text=t("common.username_locked") if connection.username_locked else "",
            font=ctk.CTkFont(size=12), text_color=state.colors["text_secondary"],
        )
        self.lock_label.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            card,
            text=t("common.username_warning"),
            font=ctk.CTkFont(size=13), text_color=state.colors["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=30, pady=(0, 18))

        # title  (hidden for username change type)
        self._title_lbl = self._lbl(card, t("report.report_title"), pack=False)
        self.title_var  = ctk.StringVar()
        self._title_entry = ctk.CTkEntry(
            card, textvariable=self.title_var, height=40,
            fg_color=state.colors["frame_bg"], border_color=state.colors["border"],
            text_color=state.colors["text"], font=ctk.CTkFont(size=14),
            placeholder_text="Short summary…",
        )

        # description / reason
        self._desc_lbl = self._lbl(card, t("report.report_description"), pack=False)
        self.desc_box  = ctk.CTkTextbox(
            card, height=160,
            fg_color=state.colors["frame_bg"], border_color=state.colors["border"],
            border_width=2, text_color=state.colors["text"],
            font=ctk.CTkFont(size=13), corner_radius=8, wrap="word",
        )

        # new username field (only shown for username change type)
        self._new_username_lbl   = self._lbl(card, t("username.new_username"), pack=False)
        self.new_username_var    = ctk.StringVar()
        self._new_username_entry = ctk.CTkEntry(
            card, textvariable=self.new_username_var, height=40,
            fg_color=state.colors["frame_bg"], border_color=state.colors["border"],
            text_color=state.colors["text"], font=ctk.CTkFont(size=14),
            placeholder_text="The username you'd like to switch to…",
        )

        # attachment (only for bug reports)
        self._attach_lbl = self._lbl(card, t("report.attachment"), pack=False)
        attach_row = ctk.CTkFrame(card, fg_color="transparent")
        self.attach_label = ctk.CTkLabel(
            attach_row, text=t("common.nofile_selected"),
            font=ctk.CTkFont(size=12), text_color=state.colors["text_secondary"], anchor="w",
        )
        self.attach_label.pack(side="left", fill="x", expand=True)
        self.clear_media_btn = ctk.CTkButton(
            attach_row, text=t("common.clear"), width=70, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color="#e57373", corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._clear_media,
        )
        ctk.CTkButton(
            attach_row, text=t("common.browse"), width=120, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._browse_attachment,
        ).pack(side="right")
        self._attach_row = attach_row

        # project file (only for bug reports)
        self._proj_lbl = self._lbl(card, t("report.bs_project"), pack=False)
        proj_row = ctk.CTkFrame(card, fg_color="transparent")
        self.project_label = ctk.CTkLabel(
            proj_row, text=t("common.nofile_selected"),
            font=ctk.CTkFont(size=12), text_color=state.colors["text_secondary"], anchor="w",
        )
        self.project_label.pack(side="left", fill="x", expand=True)
        self.clear_project_btn = ctk.CTkButton(
            proj_row, text=t("common.clear"), width=70, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color="#e57373", corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._clear_project,
        )
        ctk.CTkButton(
            proj_row, text=t("common.browse"), width=120, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._browse_project,
        ).pack(side="right")
        self._proj_row = proj_row

        self.size_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=11),
            text_color=state.colors["text_secondary"], anchor="w",
        )
        self._size_lbl_widget = self.size_label

        # Store card ref for packing dynamic widgets into it
        self._card = card

        self.cooldown_label = ctk.CTkLabel(card, text="",
            font=ctk.CTkFont(size=12), text_color="#e57373")
        self.cooldown_label.pack(pady=(0, 6))

        self.submit_btn = ctk.CTkButton(
            card, text="🚀  Send Report", height=46,
            fg_color=state.colors["accent"], hover_color=state.colors["accent_hover"],
            text_color=state.colors["text"], corner_radius=10,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._submit,
        )
        self.submit_btn.pack(padx=30, pady=(0, 30))

        # Now actually lay out the dynamic widgets for the initial type
        self._layout_type_widgets()
        self._tick_cooldown()
        self.after(200, self._poll_connection)

    def _switch_report_type(self, key: str, init: bool = False):
        self._report_type.set(key)
        for k, btn in self._type_btns.items():
            if k == key:
                btn.configure(fg_color=state.colors["accent"],
                              hover_color=state.colors["accent_hover"],
                              text_color=state.colors["accent_text"])
            else:
                btn.configure(fg_color=state.colors["card_bg"],
                              hover_color=state.colors["card_hover"],
                              text_color=state.colors["text"])

        if not init:
            # Update UI labels and submit button text
            self._layout_type_widgets()

    def _layout_type_widgets(self):
        """Show/hide dynamic widgets based on the current report type."""
        rtype = self._report_type.get()

        # Unpack everything that's dynamic first
        for w in [
            self._title_lbl, self._title_entry,
            self._desc_lbl, self.desc_box,
            self._new_username_lbl, self._new_username_entry,
            self._attach_lbl, self._attach_row,
            self._proj_lbl, self._proj_row,
            self._size_lbl_widget,
        ]:
            w.pack_forget()

        SUBMIT_LABELS = {
            "bug":      t("report.send_report"),
            "suggest":  t("suggestion.send_suggestion"),
            "username": t("username.send_request"),
            "appeal":   t("ban_appeal.send_appeal"),
        }
        self.submit_btn.configure(text=SUBMIT_LABELS[rtype])

        HEADING_LABELS = {
            "bug":      t("report.title"),
            "suggest":  t("suggestion.title"),
            "username": t("username.title"),
            "appeal":   t("ban_appeal.title"),
        }
        self._heading_lbl.configure(text=HEADING_LABELS.get(rtype, t("report.title")))

        SUBTITLE_LABELS = {
            "bug":      t("report.title_description"),
            "suggest":  t("suggestion.title_description"),
            "username": t("username.title_description"),
            "appeal":   t("ban_appeal.title_description"),
        }
        self._subtitle_lbl.configure(text=SUBTITLE_LABELS.get(rtype, t("report.title_description")))

        if rtype == "bug":
            self._title_lbl.configure(text=t("report.report_title"))
            self._title_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self._title_entry.pack(fill="x", padx=30, pady=(0, 18))
            self._desc_lbl.configure(text=t("report.report_description"))
            self._desc_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self.desc_box.pack(fill="x", padx=30, pady=(0, 18))
            self._attach_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self._attach_row.pack(fill="x", padx=30, pady=(0, 10))
            self._proj_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self._proj_row.pack(fill="x", padx=30, pady=(0, 10))
            self._size_lbl_widget.pack(fill="x", padx=30, pady=(2, 16))

        elif rtype == "suggest":
            self._title_lbl.configure(text=t("suggestion.title"))
            self._title_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self._title_entry.pack(fill="x", padx=30, pady=(0, 18))
            self._desc_lbl.configure(text=t("suggestion.suggestion_description"))
            self._desc_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self.desc_box.pack(fill="x", padx=30, pady=(0, 18))

        elif rtype == "username":
            self._new_username_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self._new_username_entry.pack(fill="x", padx=30, pady=(0, 18))
            self._desc_lbl.configure(text=t("username.reason_for_change"))
            self._desc_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self.desc_box.pack(fill="x", padx=30, pady=(0, 18))

        elif rtype == "appeal":
            ban_r = connection.ban_reason or "No reason provided."
            self._desc_lbl.configure(text=f"Your Appeal  (Ban reason: {ban_r})")
            self._desc_lbl.pack(fill="x", padx=30, pady=(0, 6))
            self.desc_box.pack(fill="x", padx=30, pady=(0, 18))

        # Re-pack cooldown + submit (they sit at the bottom)
        self.cooldown_label.pack_forget()
        self.submit_btn.pack_forget()
        self.cooldown_label.pack(pady=(0, 6))
        self.submit_btn.pack(padx=30, pady=(0, 30))

    def _lbl(self, parent, text: str, pack: bool = True):
        lbl = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text"], anchor="w",
        )
        if pack:
            lbl.pack(fill="x", padx=30, pady=(0, 6))
        return lbl

    # ── connection ───────────────────────────────────────────────────────── #

    def _poll_connection(self):
        if connection.check_complete:
            self._refresh_username_lock()
            self._refresh_status_badge()
            self._update_cooldown_ui()
            if connection.is_banned:
                self._apply_ban_mode()
        else:
            self._poll_attempts += 1
            if self._poll_attempts < 40:
                self.after(200, self._poll_connection)

    def _retry_connection(self):
        self.status_label.configure(text=t("common.retrying"),
            text_color=state.colors["text_secondary"])
        self.retry_btn.pack_forget()
        connection.check_connection(
            on_success=lambda: self.after(0, self._on_retry_success),
            on_failure=lambda: self.after(0, self._refresh_status_badge),
        )

    def _on_retry_success(self):
        self._refresh_username_lock()
        self._refresh_status_badge()
        self._update_cooldown_ui()
        if connection.is_banned:
            self._apply_ban_mode()
        if self.on_connected:
            self.on_connected()

    def _apply_ban_mode(self):
        """Force the UI into appeal-only mode when the user is banned."""
        for k, btn in self._type_btns.items():
            if k != "appeal":
                btn.pack_forget()
            else:
                btn.pack(side="left", padx=(0, 8))
        if self._report_type.get() != "appeal":
            self._switch_report_type("appeal")
        if connection.is_online and hasattr(self, "submit_btn"):
            self.submit_btn.configure(state="normal")

    def _refresh_status_badge(self):
        has_btn = hasattr(self, "submit_btn")
        rtype   = getattr(self, "_report_type", None)
        is_appeal = rtype and rtype.get() == "appeal"
        if connection.is_banned and not is_appeal:
            # Banned — only allow appeal tab to submit
            self.status_label.configure(
                text=t("ban_appeal.ban_appeal_status"), text_color=state.colors["error"])
            self.retry_btn.pack_forget()
            if has_btn:
                self.submit_btn.configure(state="disabled")
            return
        if connection.is_online:
            self.status_label.configure(
                text=t("common.server_status_online"), text_color=state.colors["success"])
            self.retry_btn.pack_forget()
            if has_btn and connection.cooldown_remaining <= 0:
                self.submit_btn.configure(state="normal")
        else:
            self.status_label.configure(
                text=t("report.server_status_offline"), text_color=state.colors["error"])
            self.retry_btn.pack(side="right")
            if has_btn:
                self.submit_btn.configure(state="disabled")

    def _refresh_username_lock(self):
        if connection.username_locked:
            self.username_var.set(connection.server_username)
            self.username_entry.configure(state="disabled")
            self.lock_label.configure(text=t("common.username_locked"))
        else:
            self.username_entry.configure(state="normal")
            self.lock_label.configure(text="")

    # ── cooldown ticker ──────────────────────────────────────────────────── #

    def _tick_cooldown(self):
        if self._cooldown_job:
            self.after_cancel(self._cooldown_job)
            self._cooldown_job = None
        remaining = connection.cooldown_remaining
        if remaining > 0:
            connection.cooldown_remaining = max(0.0, remaining - 1)
            m, s = int(connection.cooldown_remaining // 60), int(connection.cooldown_remaining % 60)
            self.cooldown_label.configure(
                text=f"⏳ You can submit another report in {m}m {s}s")
            self.submit_btn.configure(state="disabled")
            self._cooldown_job = self.after(1000, self._tick_cooldown)
        else:
            self.cooldown_label.configure(text="")
            if connection.is_online:
                self.submit_btn.configure(state="normal")

    def _update_cooldown_ui(self):
        self._tick_cooldown()

    # ── file helpers ─────────────────────────────────────────────────────── #

    def _combined_size(self) -> int:
        t = 0
        if self._attachment_path and os.path.exists(self._attachment_path):
            t += os.path.getsize(self._attachment_path)
        if self._project_path and os.path.exists(self._project_path):
            t += os.path.getsize(self._project_path)
        return t

    def _update_size_label(self):
        total = self._combined_size()
        if total == 0:
            self.size_label.configure(text="")
            return
        mb    = total / 1024 / 1024
        color = "#e57373" if total > _MAX_BYTES else state.colors["text_secondary"]
        self.size_label.configure(
            text=f"Combined size: {mb:.2f} MB / 10.00 MB", text_color=color)

    def _browse_attachment(self):
        path = filedialog.askopenfilename(title="Select image or video", filetypes=[
            ("Images & Videos", "*.png *.jpg *.jpeg *.gif *.webp *.mp4 *.mov *.avi *.mkv"),
        ])
        if not path:
            return
        self._attachment_path = path
        if self._combined_size() > _MAX_BYTES:
            self._attachment_path = None
            self._notify(t("upload.error.combined_file_size"), "error")
            return
        size = os.path.getsize(path)
        self.attach_label.configure(
            text=f"{os.path.basename(path)}  ({size/1024/1024:.2f} MB)",
            text_color=state.colors["text"])
        self.clear_media_btn.pack(side="right", padx=(4, 0))
        self._update_size_label()

    def _clear_media(self):
        self._attachment_path = None
        self.attach_label.configure(text=t("common.nofile_selected"),
            text_color=state.colors["text_secondary"])
        self.clear_media_btn.pack_forget()
        self._update_size_label()

    def _browse_project(self):
        path = filedialog.askopenfilename(title="Select .bsproject file", filetypes=[
            ("BeamSkin Project", "*.bsproject"),
        ])
        if not path:
            return
        self._project_path = path
        if self._combined_size() > _MAX_BYTES:
            self._project_path = None
            self._notify(t("upload.error.combined_file_size"), "error")
            return
        size = os.path.getsize(path)
        self.project_label.configure(
            text=f"{os.path.basename(path)}  ({size/1024/1024:.2f} MB)",
            text_color=state.colors["text"])
        self.clear_project_btn.pack(side="right", padx=(4, 0))
        self._update_size_label()

    def _clear_project(self):
        self._project_path = None
        self.project_label.configure(text=t("common.nofile_selected"),
            text_color=state.colors["text_secondary"])
        self.clear_project_btn.pack_forget()
        self._update_size_label()

    # ── submit ───────────────────────────────────────────────────────────── #

    def _submit(self):
        if not connection.is_online:
            self._notify(t("common.offline_submit"), "error")
            return

        rtype    = self._report_type.get()
        username = self.username_var.get().strip()
        desc     = self.desc_box.get("1.0", "end").strip()

        if not username:
            self._notify(t("common.please_enter_username"), "error"); return

        if rtype == "bug":
            title = self.title_var.get().strip()
            if not title: self._notify(t("common.please_enter_title"), "error"); return
            if not desc:  self._notify(t("common.please_enter_description"), "error"); return
            if not connection.username_locked:
                available, _ = connection.check_username_available(username)
                if not available:
                    self._notify(t("common.username_taken", username=username), "error"); return
            self.submit_btn.configure(state="disabled", text=t("common.sending"))
            threading.Thread(target=self._send_bug_report, args=(username, title, desc), daemon=True).start()

        elif rtype == "suggest":
            title = self.title_var.get().strip()
            if not title: self._notify(t("common.please_enter_suggestion_title"), "error"); return
            if not desc:  self._notify(t("common.please_enter_suggestion_description"), "error"); return
            self.submit_btn.configure(state="disabled", text=t("common.sending"))
            threading.Thread(target=self._send_suggestion, args=(username, title, desc), daemon=True).start()

        elif rtype == "username":
            new_username = self.new_username_var.get().strip()
            if not new_username: self._notify(t("common.please_enter_new_username"), "error"); return
            if not desc:         self._notify(t("common.please_enter_reason_for_change"), "error"); return
            self.submit_btn.configure(state="disabled", text=t("common.sending"))
            threading.Thread(target=self._send_username_change, args=(username, new_username, desc), daemon=True).start()

        elif rtype == "appeal":
            desc = self.desc_box.get("1.0", "end").strip()
            if not desc: self._notify(t("common.please_enter_appeal_reason"), "error"); return
            self.submit_btn.configure(state="disabled", text=t("common.sending"),)
            threading.Thread(target=self._send_appeal, args=(username, desc), daemon=True).start()

    def _send_appeal(self, username, reason):
        ok, msg = connection.submit_appeal(username=username, reason=reason)
        if ok:
            self.after(0, self._on_appeal_success)
        else:
            self.after(0, lambda: self._on_generic_error(msg, "🔓  Submit Appeal"))

    def _send_bug_report(self, username, title, desc):
        ok, msg, cooldown = connection.submit_report(
            username=username, title=title, description=desc,
            attachment_path=self._attachment_path, project_path=self._project_path,
        )
        self._last_cooldown = cooldown
        if ok:
            connection.refresh_user_state(on_done=lambda: self.after(0, self._on_bug_success))
        elif connection.is_banned:
            self.after(0, self._on_banned_detected)
        else:
            connection.refresh_user_state(on_done=lambda: self.after(0, lambda: self._on_bug_error(msg)))

    def _on_banned_detected(self):
        self.submit_btn.configure(state="normal", text="🚀  Send Bug Report")
        if self.on_ban_detected:
            self.on_ban_detected()

    def _send_suggestion(self, username, title, desc):
        ok, msg = connection.submit_suggestion(username=username, title=title, description=desc)
        if ok:
            connection.refresh_user_state(on_done=lambda: self.after(0, self._on_suggestion_success))
        elif connection.is_banned:
            self.after(0, self._on_banned_detected)
        else:
            self.after(0, lambda: self._on_generic_error(msg, "💡  Send Suggestion"))

    def _send_username_change(self, username, new_username, reason):
        ok, msg = connection.submit_username_change(
            username=username, new_username=new_username, reason=reason
        )
        if ok:
            connection.refresh_user_state(on_done=lambda: self.after(0, self._on_username_change_success))
        elif connection.is_banned:
            self.after(0, self._on_banned_detected)
        else:
            self.after(0, lambda: self._on_generic_error(msg, "🔄  Send Username Change Request"))

    def _on_bug_success(self):
        self._notify(t("common.bug_report_sent"), "success")
        self.title_var.set("")
        self.desc_box.delete("1.0", "end")
        self._clear_media()
        self._clear_project()
        self.submit_btn.configure(state="normal", text=t("report.send_report"))
        self._refresh_username_lock()
        self._tick_cooldown()

    def _on_suggestion_success(self):
        self._notify(t("common.suggestion_sent"), "success")
        self.title_var.set("")
        self.desc_box.delete("1.0", "end")
        self.submit_btn.configure(state="normal", text=t("suggestion.send_suggestion"))
        self._refresh_username_lock()

    def _on_username_change_success(self):
        self._notify(t("common.username_changed"), "success")
        self.new_username_var.set("")
        self.desc_box.delete("1.0", "end")
        self.submit_btn.configure(state="normal", text=t("username.send_request"))
        self._refresh_username_lock()

    def _on_appeal_success(self):
        self._notify(t("common.appeal_submitted"), "success")
        self.desc_box.delete("1.0", "end")
        self.submit_btn.configure(state="normal", text=t("ban_appeal.send_appeal"))

    def _on_bug_error(self, msg):
        WARN_PREFIXES = (
            "Title is too", "Description is too", "Please don't",
            "Report contains", "Report appears", "This report is identical",
            "Links are not allowed", "Only 1 YouTube",
        )
        if "minute cooldown" in msg:
            self._notify(f"🚫 {msg}", "error")
            self._tick_cooldown()
        elif "Warning 1/2" in msg:
            self._notify(f"⚠️ {msg}", "warning")
            self.submit_btn.configure(state="normal", text=t("report.send_report"))
        elif any(msg.startswith(p) for p in WARN_PREFIXES):
            self._notify(f"⚠️ {msg}", "warning")
            self.submit_btn.configure(state="normal", text=t("report.send_report"))
        else:
            self._notify(f"{t('common.failed_to_send_report')} {msg}", "error")
            self.submit_btn.configure(state="normal", text=t("report.send_report"))

    def _on_generic_error(self, msg, btn_label):
        self._notify(f"{t('common.failed_to_send')} {msg}", "error")
        self.submit_btn.configure(state="normal", text=btn_label)

    # kept for backwards compat (OnlineTab references this via _send_report path)
    def _send_report(self, username, title, desc):
        self._send_bug_report(username, title, desc)

    def _on_success(self):
        self._on_bug_success()

    def _on_error(self, msg):
        self._on_bug_error(msg)

    def _notify(self, message, type="info"):
        if self.notification_callback:
            self.notification_callback(message, type)
        else:
            print(f"[REPORT] {type.upper()}: {message}")


# ══════════════════════════════════════════════════════════════════════════════
#  UPLOAD SUB-TAB
# ══════════════════════════════════════════════════════════════════════════════

class _UploadSubTab(ctk.CTkFrame):

    ALLOWED_EXT = {".dds", ".png", ".json", ".jbeam", ".jpg", ".jpeg", ".pc"}

    def __init__(self, parent, notification_callback):
        super().__init__(parent, fg_color=state.colors["app_bg"], corner_radius=0)
        self.notification_callback = notification_callback
        self.on_connected    = None
        self.on_ban_detected = None   # set by OnlineTab — called when a ban 403 is received
        self._image_paths:    list[str]  = []
        self._thumbnail_index: int       = 0   # index of the image chosen as embed thumbnail
        self._zip_path:       Optional[str] = None
        self._selected_tags:  set[str]      = set()
        self._poll_attempts:  int           = 0
        self._cooldown_job    = None
        self._build_ui()

    # ── UI build ─────────────────────────────────────────────────────────── #

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=state.colors["app_bg"])
        scroll.pack(fill="both", expand=True)

        card = ctk.CTkFrame(scroll, fg_color=state.colors["card_bg"], corner_radius=16)
        card.pack(fill="both", expand=True, padx=60, pady=40)

        # ── header ───────────────────────────────────────────────────────── #
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=30, pady=(28, 4))

        ctk.CTkLabel(hdr, text=t("upload.title"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=state.colors["text"], anchor="w",
        ).pack(side="left")

        # 7-Zip status badge
        self._sevenz_status = ctk.CTkLabel(hdr, text="",
            font=ctk.CTkFont(size=12), text_color=state.colors["text_secondary"])
        self._sevenz_status.pack(side="right", padx=(0, 8))

        self._install_btn = ctk.CTkButton(hdr, text=t("upload.install7zip"),
            width=130, height=30,
            fg_color="#c07000", hover_color="#985800",
            text_color="white", corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._install_7zip)
        self._refresh_7zip_ui()

        ctk.CTkLabel(card,
            text=t("upload.description"),
            font=ctk.CTkFont(size=13), text_color=state.colors["text_secondary"],
            anchor="w", wraplength=700, justify="left",
        ).pack(fill="x", padx=30, pady=(0, 10))

        # ── connection status row ─────────────────────────────────────────── #
        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=30, pady=(0, 10))
        self.status_label = ctk.CTkLabel(
            status_row, text="", font=ctk.CTkFont(size=12), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)
        self.retry_btn = ctk.CTkButton(
            status_row, text=t("common.retry"), width=100, height=30,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8,
            font=ctk.CTkFont(size=12), command=self._retry_connection,
        )
        self._refresh_status_badge()

        ctk.CTkFrame(card, height=2, fg_color=state.colors["border"]).pack(
            fill="x", padx=30, pady=(0, 22))

        # ── username ──────────────────────────────────────────────────────── #
        self._lbl(card, t("common.username"))
        user_row = ctk.CTkFrame(card, fg_color="transparent")
        user_row.pack(fill="x", padx=30, pady=(0, 18))
        self.username_var = ctk.StringVar(value=connection.server_username)
        self.username_entry = ctk.CTkEntry(
            user_row, textvariable=self.username_var, height=40,
            fg_color=state.colors["frame_bg"], border_color=state.colors["border"],
            text_color=state.colors["text"], font=ctk.CTkFont(size=14),
            placeholder_text="Enter your username...",
            state="disabled" if connection.username_locked else "normal",
        )
        self.username_entry.pack(side="left", fill="x", expand=True)
        self.lock_label = ctk.CTkLabel(
            user_row,
            text=t("common.username_locked") if connection.username_locked else "",
            font=ctk.CTkFont(size=12), text_color=state.colors["text_secondary"],
        )
        self.lock_label.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            card,
            text=t("common.username_warning"),
            font=ctk.CTkFont(size=13), text_color=state.colors["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=30, pady=(0, 18))

        # ── title ────────────────────────────────────────────────────────── #
        self._lbl(card, t("upload.skin_title"))
        self.title_var = ctk.StringVar()
        ctk.CTkEntry(card, textvariable=self.title_var, height=40,
            fg_color=state.colors["frame_bg"], border_color=state.colors["border"],
            text_color=state.colors["text"], font=ctk.CTkFont(size=14),
            placeholder_text="e.g. 2024 WEC Hypercar Livery Pack…",
        ).pack(fill="x", padx=30, pady=(0, 18))

        # ── description ───────────────────────────────────────────────────── #
        self._lbl(card, t("upload.skin_description"))
        self.desc_box = ctk.CTkTextbox(card, height=120,
            fg_color=state.colors["frame_bg"], border_color=state.colors["border"],
            border_width=2, text_color=state.colors["text"],
            font=ctk.CTkFont(size=13), corner_radius=8, wrap="word")
        self.desc_box.pack(fill="x", padx=30, pady=(0, 18))

        # ── tags ─────────────────────────────────────────────────────────── #
        self._lbl(card, t("upload.tags"))
        tags_card = ctk.CTkFrame(card, fg_color=state.colors["frame_bg"], corner_radius=8)
        tags_card.pack(fill="x", padx=30, pady=(0, 18))
        self._tag_btns: dict[str, ctk.CTkButton] = {}
        # Build rows of 5 tags each, each row fills full width
        COLS = 5
        rows_needed = (len(AVAILABLE_TAGS) + COLS - 1) // COLS
        for row_idx in range(rows_needed):
            row_frame = ctk.CTkFrame(tags_card, fg_color="transparent")
            row_frame.pack(fill="x", padx=10, pady=(5, 0) if row_idx < rows_needed - 1 else (5, 10))
            row_tags = AVAILABLE_TAGS[row_idx * COLS : (row_idx + 1) * COLS]
            for col_idx, tag in enumerate(row_tags):
                row_frame.columnconfigure(col_idx, weight=1)
            for col_idx, tag in enumerate(row_tags):
                btn = ctk.CTkButton(
                    row_frame, text=tag, height=30,
                    corner_radius=15, font=ctk.CTkFont(size=12),
                    fg_color=state.colors["card_bg"],
                    hover_color=state.colors["accent"],
                    border_width=1, border_color=state.colors["border"],
                    text_color=state.colors["text"],
                    command=lambda t=tag: self._toggle_tag(t),
                )
                btn.grid(row=0, column=col_idx, padx=4, sticky="ew")
                self._tag_btns[tag] = btn

        # ── preview images ─────────────────────────────────────────────────── #
        self._lbl(card, t("upload.preview_image"))
        img_row = ctk.CTkFrame(card, fg_color="transparent")
        img_row.pack(fill="x", padx=30, pady=(0, 6))
        self._img_label = ctk.CTkLabel(img_row, text=t("common.image_file"),
            font=ctk.CTkFont(size=12), text_color=state.colors["text_secondary"], anchor="w")
        self._img_label.pack(side="left", fill="x", expand=True)
        self._clear_img_btn = ctk.CTkButton(img_row, text=t("common.clear_all"), width=80, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color="#e57373", corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._clear_image)
        ctk.CTkButton(img_row, text="🖼️  Browse…", width=120, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._browse_image,
        ).pack(side="right")

        # image thumbnails row
        self._img_preview_frame = ctk.CTkFrame(
            card, fg_color=state.colors["frame_bg"], corner_radius=8)
        self._img_preview_row = ctk.CTkFrame(self._img_preview_frame, fg_color="transparent")
        self._img_preview_row.pack(pady=10, padx=10, fill="x")

        # ── mod zip ───────────────────────────────────────────────────────── #
        self._lbl(card,
            t("upload.zip"))
        zip_row = ctk.CTkFrame(card, fg_color="transparent")
        zip_row.pack(fill="x", padx=30, pady=(0, 6))
        self._zip_label = ctk.CTkLabel(zip_row, text=t("common.nofile_selected"),
            font=ctk.CTkFont(size=12), text_color=state.colors["text_secondary"], anchor="w")
        self._zip_label.pack(side="left", fill="x", expand=True)
        self._clear_zip_btn = ctk.CTkButton(zip_row, text=t("common.clear"), width=70, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color="#e57373", corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._clear_zip)
        ctk.CTkButton(zip_row, text="📦  Browse…", width=120, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._browse_zip,
        ).pack(side="right")

        # ── progress ─────────────────────────────────────────────────────── #
        self._progress_lbl = ctk.CTkLabel(card, text="",
            font=ctk.CTkFont(size=12), text_color=state.colors["text_secondary"])
        self._progress_lbl.pack(pady=(14, 2))
        self._progress_bar = ctk.CTkProgressBar(
            card, mode="indeterminate",
            fg_color=state.colors["frame_bg"], progress_color=state.colors["accent"])
        # packed only while submitting

        # ── upload cooldown label ─────────────────────────────────────────── #
        self.cooldown_label = ctk.CTkLabel(card, text="",
            font=ctk.CTkFont(size=12), text_color="#e57373")
        self.cooldown_label.pack(pady=(0, 4))

        # ── submit button ─────────────────────────────────────────────────── #
        self.submit_btn = ctk.CTkButton(
            card, text=t("upload.upload_button"), height=46,
            fg_color=state.colors["accent"], hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"], corner_radius=10,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._submit)
        self.submit_btn.pack(padx=30, pady=(0, 30))

        # Poll until the connection check completes so the status badge and
        # submit button are updated correctly once submit_btn actually exists.
        self.after(200, self._poll_connection)

    def _lbl(self, parent, text: str):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text"], anchor="w",
        ).pack(fill="x", padx=30, pady=(0, 6))

    # ── connection ───────────────────────────────────────────────────────── #

    def _poll_connection(self):
        if connection.check_complete:
            self._refresh_username_lock()
            self._refresh_status_badge()
            self._tick_upload_cooldown()
            if connection.is_banned:
                self._show_ban_overlay()
        else:
            self._poll_attempts += 1
            if self._poll_attempts < 40:
                self.after(200, self._poll_connection)

    def _show_ban_overlay(self):
        """Replace the upload card with a banned notice."""
        if getattr(self, "_ban_overlay_shown", False):
            return
        self._ban_overlay_shown = True
        for child in self.winfo_children():
            child.pack_forget()
        ban_card = ctk.CTkFrame(self, fg_color=state.colors["card_bg"], corner_radius=16)
        ban_card.pack(fill="both", expand=True, padx=60, pady=40)
        ctk.CTkLabel(ban_card, text="🚫", font=ctk.CTkFont(size=48)).pack(pady=(40, 8))
        ctk.CTkLabel(ban_card, text=t("upload.your_ban"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=state.colors["error"]).pack(pady=(0, 8))
        reason = connection.ban_reason or "No reason provided."
        ctk.CTkLabel(ban_card, text=(f"{t('upload.reason_banned')}{reason}"),
            font=ctk.CTkFont(size=14), text_color=state.colors["text_secondary"],
            wraplength=500).pack(pady=(0, 16))
        ctk.CTkLabel(ban_card,
            text=t("upload.banned"),
            font=ctk.CTkFont(size=13), text_color=state.colors["text_secondary"],
            wraplength=500, justify="center").pack(pady=(0, 24))

        status_lbl = ctk.CTkLabel(ban_card, text="", font=ctk.CTkFont(size=12),
            text_color=state.colors["text_secondary"])
        status_lbl.pack(pady=(0, 4))

        UNBAN_COOLDOWN = 3600  # 1 hour
        ban_card._last_unban_check = 0.0

        def _fmt(secs):
            m, s = divmod(int(secs), 60)
            h, m = divmod(m, 60)
            return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

        def _tick():
            if not check_btn.winfo_exists():
                return
            remaining = UNBAN_COOLDOWN - (time.time() - ban_card._last_unban_check)
            if remaining > 0:
                check_btn.configure(state="disabled", text=(f"{t('upload.check_again')} {_fmt(remaining)}"))
                ban_card.after(1000, _tick)
            else:
                check_btn.configure(state="normal", text=t("upload.check_ban_status"))

        def _check_unban():
            ban_card._last_unban_check = time.time()
            check_btn.configure(state="disabled", text=t("upload.checking_ban_status"))
            status_lbl.configure(text="")
            def _done():
                if not connection.is_banned:
                    if self.on_ban_detected:
                        self.after(0, self.on_ban_detected)
                else:
                    status_lbl.configure(text=t("upload.still_banned"), text_color=state.colors["error"])
                    _tick()
            connection.refresh_user_state(on_done=lambda: self.after(0, _done))

        check_btn = ctk.CTkButton(ban_card, text=t("upload.check_ban_status"),
            width=220, height=38,
            fg_color=state.colors["frame_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=_check_unban)
        check_btn.pack(pady=(0, 40))

    def _retry_connection(self):
        self.status_label.configure(
            text=t("common.server_retry"), text_color=state.colors["text_secondary"])
        self.retry_btn.pack_forget()
        connection.check_connection(
            on_success=lambda: self.after(0, self._on_retry_success),
            on_failure=lambda: self.after(0, self._refresh_status_badge),
        )

    def _on_retry_success(self):
        self._refresh_username_lock()
        self._refresh_status_badge()
        self._tick_upload_cooldown()
        if connection.is_banned:
            self._show_ban_overlay()
        if self.on_connected:
            self.on_connected()

    def _refresh_status_badge(self):
        has_btn = hasattr(self, "submit_btn")
        if connection.is_banned:
            self.status_label.configure(
                text=t("upload.you_are_banned"), text_color=state.colors["error"])
            self.retry_btn.pack_forget()
            if has_btn:
                self.submit_btn.configure(state="disabled")
            return
        if connection.is_online:
            self.status_label.configure(
                text=t("common.server_status_online"), text_color=state.colors["success"])
            self.retry_btn.pack_forget()
            if has_btn and connection.upload_cooldown_remaining <= 0:
                self.submit_btn.configure(state="normal")
        else:
            self.status_label.configure(
                text=t("upload.offline"), text_color=state.colors["error"])
            self.retry_btn.pack(side="right")
            if has_btn:
                self.submit_btn.configure(state="disabled")

    def _refresh_username_lock(self):
        if connection.username_locked:
            self.username_var.set(connection.server_username)
            self.username_entry.configure(state="disabled")
            self.lock_label.configure(text=t("common.username_locked"))
        else:
            self.username_entry.configure(state="normal")
            self.lock_label.configure(text="")

    # ── upload cooldown ticker (mirrors _ReportSubTab._tick_cooldown exactly) ─ #

    def _tick_upload_cooldown(self):
        if self._cooldown_job:
            self.after_cancel(self._cooldown_job)
            self._cooldown_job = None
        remaining = connection.upload_cooldown_remaining
        if remaining > 0:
            connection.upload_cooldown_remaining = max(0.0, remaining - 1)
            m, s = int(connection.upload_cooldown_remaining // 60), int(connection.upload_cooldown_remaining % 60)
            self.cooldown_label.configure(
                text=f"⏳ You can upload another skin in {m}m {s}s")
            self.submit_btn.configure(state="disabled")
            self._cooldown_job = self.after(1000, self._tick_upload_cooldown)
        else:
            self.cooldown_label.configure(text="")
            if connection.is_online:
                self.submit_btn.configure(state="normal")

    def _update_upload_cooldown_ui(self):
        self._tick_upload_cooldown()


    def _refresh_7zip_ui(self):
        if _find_7zip():
            self._sevenz_status.configure(
                text=t("upload.7zip_found"), text_color=state.colors["success"])
            self._install_btn.pack_forget()
        else:
            self._sevenz_status.configure(
                text=t("upload.7zip_not_found"), text_color=state.colors["error"])
            self._install_btn.pack(side="right", padx=(0, 8))

    def _install_7zip(self):
        self._install_btn.configure(state="disabled", text=t("upload.7zip_installing"))
        threading.Thread(
            target=self._do_install_7zip, args=(platform.system(),), daemon=True
        ).start()

    def _do_install_7zip(self, sys_name: str):
        try:
            import urllib.request
            if sys_name == "Windows":
                url = "https://www.7-zip.org/a/7z2409-x64.exe"
                tmp = os.path.join(tempfile.gettempdir(), "7z_setup.exe")
                self._set_prog(t("upload.7zip_installing"))
                urllib.request.urlretrieve(url, tmp)
                self._set_prog("Running installer (silent)…")
                subprocess.run([tmp, "/S"], check=True)
                os.remove(tmp)
            elif sys_name == "Linux":
                self._set_prog("Installing p7zip-full via apt…")
                subprocess.run(
                    ["sudo", "apt-get", "install", "-y", "p7zip-full"], check=True)
            elif sys_name == "Darwin":
                self._set_prog("Installing via Homebrew…")
                subprocess.run(["brew", "install", "p7zip"], check=True)
            self.after(0, self._after_install)
        except Exception as exc:
            self.after(0, lambda: (
                self._notify(f"{t('upload.7zip_install_failed')}: {exc}", "error"),
                self._install_btn.configure(state="normal", text=t("upload.7zip_install_button")),
                self._set_prog(""),
            ))

    def _after_install(self):
        self._set_prog("")
        self._refresh_7zip_ui()
        self._notify(t("upload.7zip_install_success"))

    # ── tag toggles ───────────────────────────────────────────────────────── #

    def _toggle_tag(self, tag: str):
        btn = self._tag_btns[tag]
        if tag in self._selected_tags:
            self._selected_tags.discard(tag)
            btn.configure(fg_color=state.colors["card_bg"],
                text_color=state.colors["text"], border_color=state.colors["border"])
        else:
            self._selected_tags.add(tag)
            btn.configure(fg_color=state.colors["accent"],
                text_color=state.colors["accent_text"], border_color=state.colors["accent"])

    # ── file pickers ──────────────────────────────────────────────────────── #

    def _browse_image(self):
        paths = filedialog.askopenfilenames(title="Select preview images (up to 5)", filetypes=[
            ("Images", "*.png *.jpg *.jpeg")])
        if not paths:
            return
        paths = list(paths)[:5]  # cap at 5

        # Reject images over 8 MB — anything larger is unreasonable for a preview.
        # Resolution is not checked here; oversized images are downscaled by _compress_images.
        MAX_FILE_MB = 8
        valid_paths = []
        rejected = []
        for path in paths:
            size_mb = os.path.getsize(path) / 1024 / 1024
            if size_mb > MAX_FILE_MB:
                rejected.append(f"{os.path.basename(path)} ({size_mb:.1f} MB)")
            else:
                valid_paths.append(path)

        if rejected:
            self._notify(
                f"Rejected {len(rejected)} image(s) exceeding 8 MB: {', '.join(rejected)}",
                "error")

        if not valid_paths:
            return

        paths = valid_paths
        self._image_paths = paths
        self._thumbnail_index = 0   # reset; first image is thumbnail by default
        names = ", ".join(os.path.basename(p) for p in paths)
        total_mb = sum(os.path.getsize(p) for p in paths) / 1024 / 1024
        self._img_label.configure(
            text=f"{len(paths)} image(s): {names}  ({total_mb:.2f} MB total)",
            text_color=state.colors["text"])
        self._clear_img_btn.pack(side="right", padx=(4, 0))

        # Show thumbnail previews with selector
        self._rebuild_image_previews()

    def _rebuild_image_previews(self):
        """Rebuild the preview thumbnail strip, highlighting the current thumbnail selection."""
        for w in self._img_preview_row.winfo_children():
            w.destroy()

        if not self._image_paths:
            self._img_preview_frame.pack_forget()
            return

        self._img_preview_frame.pack(fill="x", padx=30, pady=(0, 18))

        if not _PIL_AVAILABLE:
            return

        # Instruction label
        if len(self._image_paths) > 1:
            hint_lbl = ctk.CTkLabel(
                self._img_preview_row,
                text="Click an image to set it as the thumbnail:",
                font=ctk.CTkFont(size=11),
                text_color=state.colors["text_secondary"],
            )
            hint_lbl.pack(anchor="w", pady=(0, 4))

        thumb_row = ctk.CTkFrame(self._img_preview_row, fg_color="transparent")
        thumb_row.pack(anchor="w")

        for idx, path in enumerate(self._image_paths):
            try:
                img = _PILImage.open(path)
                img.thumbnail((160, 100))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)

                is_thumb = (idx == self._thumbnail_index)
                # Outer frame — colored border when selected
                border_color = state.colors["accent"] if is_thumb else state.colors["border"]
                outer = ctk.CTkFrame(
                    thumb_row,
                    fg_color=border_color,
                    corner_radius=8,
                )
                outer.pack(side="left", padx=(0, 8), pady=2)

                lbl = ctk.CTkLabel(outer, image=ctk_img, text="")
                lbl.image = ctk_img  # keep reference
                lbl.pack(padx=2, pady=2)

                # Thumbnail badge / label below image
                badge_text = "⭐ Thumbnail" if is_thumb else "Click to set"
                badge_color = state.colors["accent"] if is_thumb else state.colors["text_secondary"]
                badge = ctk.CTkLabel(
                    outer,
                    text=badge_text,
                    font=ctk.CTkFont(size=10, weight="bold" if is_thumb else "normal"),
                    text_color=badge_color,
                )
                badge.pack(pady=(0, 3))

                # Click to set this as thumbnail
                def _set_thumb(i=idx):
                    self._thumbnail_index = i
                    self._rebuild_image_previews()

                lbl.configure(cursor="hand2")
                lbl.bind("<Button-1>", lambda e, i=idx: _set_thumb(i))
                outer.bind("<Button-1>", lambda e, i=idx: _set_thumb(i))

            except Exception:
                pass


    def _clear_image(self):
        self._image_paths = []
        self._thumbnail_index = 0
        self._img_label.configure(text="No images selected",
            text_color=state.colors["text_secondary"])
        self._clear_img_btn.pack_forget()
        self._img_preview_frame.pack_forget()
        for w in self._img_preview_row.winfo_children():
            w.destroy()

    def _browse_zip(self):
        path = filedialog.askopenfilename(title="Select mod ZIP", filetypes=[
            ("ZIP archives", "*.zip")])
        if not path:
            return
        self._zip_path = path
        size = os.path.getsize(path)
        self._zip_label.configure(
            text=f"{os.path.basename(path)}  ({size/1024/1024:.2f} MB)",
            text_color=state.colors["text"])
        self._clear_zip_btn.pack(side="right", padx=(4, 0))

    def _clear_zip(self):
        self._zip_path = None
        self._zip_label.configure(text=t("common.nofile_selected"),
            text_color=state.colors["text_secondary"])
        self._clear_zip_btn.pack_forget()

    # ── submit pipeline ───────────────────────────────────────────────────── #

    def _submit(self):
        if not connection.is_online:
            self._notify(t("upload.offline"),)
            return

        username = self.username_var.get().strip()
        if not username:
            self._notify(t("common.please_enter_username"), "error")
            return

        title = self.title_var.get().strip()
        desc  = self.desc_box.get("1.0", "end").strip()
        tags  = list(self._selected_tags)

        if not title:           self._notify(t("common.please_enter_skin_title"), "error");       return
        if not desc:            self._notify(t("common.please_enter_skin_description"), "error");      return
        if not tags:            self._notify(t("common.please_select_tag"), "error");  return
        if not self._image_paths:
            self._notify(t("common.please_select_preview_image"), "error"); return
        if not self._zip_path:
            self._notify(t("common.please_select_zip_file"), "error"); return
        if not _find_7zip():
            self._notify(t("common.7zip_required"), "error"); return

        # Only check availability if the username isn't already locked to this user
        if not connection.username_locked:
            available, err = connection.check_username_available(username)
            if not available:
                self._notify(t("common.username_taken", username=username), "error")
                return

        self.submit_btn.configure(state="disabled", text=t("common.processing"))
        self._progress_bar.pack(padx=30, fill="x", pady=(0, 8))
        self._progress_bar.start()
        threading.Thread(
            target=self._pipeline, args=(username, title, desc, tags, self._thumbnail_index), daemon=True
        ).start()

    def _set_prog(self, text: str):
        self.after(0, lambda: self._progress_lbl.configure(text=text))

    def _pipeline(self, username: str, title: str, desc: str, tags: list[str], thumbnail_index: int = 0):
        tmp = tempfile.mkdtemp(prefix="bs_upload_")
        try:
            # 1. Extract zip
            self._set_prog(t("common.exrtracting_zip"))
            ex_dir = os.path.join(tmp, "extracted")
            os.makedirs(ex_dir)
            with zipfile.ZipFile(self._zip_path, "r") as zf:
                zf.extractall(ex_dir)

            # 2. Validate
            self._set_prog(t("common.validating_files"))
            ok, err, vehicles_dir = self._validate(ex_dir)
            if not ok:
                self.after(0, lambda: self._fail(err))
                return

            # 3. Compress with 7-Zip (ultra LZMA2)
            self._set_prog(t("common.compressing"))
            base_name  = os.path.splitext(os.path.basename(self._zip_path))[0]
            out_7z     = os.path.join(tmp, f"{base_name}.7z")
            ok, err    = self._compress(vehicles_dir, out_7z)
            if not ok:
                self.after(0, lambda: self._fail(f"Compression failed: {err}"))
                return

            # 4. Size check
            self._set_prog(t("common.checking_compression_size"))
            sz = os.path.getsize(out_7z)
            if sz > _MAX_BYTES:
                mb = sz / 1024 / 1024
                self.after(0, lambda: self._fail(
                    f"{t('common.file_too_large', mb=mb)}"))
                return

            # 5. Compress preview images
            self._set_prog(t("common.compressing_preview_images"))
            compressed_images = self._compress_images(self._image_paths, tmp)

            # 6. Upload to server
            self._set_prog(t("common.uploading_to_server"))
            ok, err, is_warn = self._post(username, title, desc, tags, out_7z, base_name, compressed_images, thumbnail_index)
            if ok:
                self.after(0, self._succeed)
            elif is_warn:
                self.after(0, lambda e=err: self._on_warning(e))
            else:
                self.after(0, lambda e=err: self._fail(e))

        except Exception as exc:
            self.after(0, lambda e=str(exc): self._fail(f"{t('common.Unexpected_error')} {e}"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _validate(self, root_dir: str):
        """Returns (valid, error_msg, vehicles_folder_path)."""
        vehicles = None
        container = None

        top_items = os.listdir(root_dir)

        # Accept either: root has 'vehicles/' directly, or root has one folder that contains 'vehicles/'
        for item in top_items:
            p = os.path.join(root_dir, item)
            if item.lower() == "vehicles" and os.path.isdir(p):
                vehicles = p
                break
            if os.path.isdir(p):
                sub = os.path.join(p, "vehicles")
                if os.path.exists(sub) and os.path.isdir(sub):
                    vehicles = sub
                    container = p
                    break

        if vehicles is None:
            return False, (
                t("common.vehicles_folder_root_only"),
            ), None

        # Check nothing unexpected sits alongside the vehicles folder
        check_dir = container if container else root_dir
        for item in os.listdir(check_dir):
            p = os.path.join(check_dir, item)
            if os.path.isdir(p) and item.lower() != "vehicles":
                return False, (
                    f"{t('common.vehicles_folder_only', item=item)}"
                ), None
            if os.path.isfile(p):
                ext = os.path.splitext(item)[1].lower()
                if ext not in self.ALLOWED_EXT:
                    return False, (
                        f"{t('common.only_allowed_files', item=item)}"
                    ), None

        # Validate every file inside vehicles/
        for dirpath, _, files in os.walk(vehicles):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in self.ALLOWED_EXT:
                    return False, (
                        f"{t('common.file_extension_not_allowed', ext=ext, fname=fname)}"
                    ), None

        return True, "", vehicles

    def _compress(self, source: str, output: str):
        """Compress source folder to output .7z with the requested ultra settings."""
        exe = _find_7zip()
        if not exe:
            return False, "7-Zip executable not found"
        cpus = multiprocessing.cpu_count()
        cmd  = [
            exe, "a",
            "-t7z",             # format
            "-mx=9",            # level: ultra
            "-m0=lzma2",        # method
            "-md=1024m",        # dictionary 1 GB
            "-mfb=256",         # word size 256
            "-ms=on",           # solid archive
            f"-mmt={cpus}",     # all CPU threads
            output,
            source,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                return False, result.stderr or result.stdout
            return True, ""
        except subprocess.TimeoutExpired:
            return False, "Compression timed out (>10 min)"
        except Exception as exc:
            return False, str(exc)

    def _compress_images(self, image_paths: list, tmp_dir: str) -> list:

        if not _PIL_AVAILABLE:
            return list(image_paths)

        out_paths = []
        for idx, path in enumerate(image_paths):
            try:
                img = _PILImage.open(path).convert("RGB")

                # Downscale if larger than 1920×1080 (preserves aspect ratio)
                max_w, max_h = 1920, 1080
                if img.width > max_w or img.height > max_h:
                    img.thumbnail((max_w, max_h), _PILImage.LANCZOS)

                out_name = f"preview_{idx}.jpg"
                out_path = os.path.join(tmp_dir, out_name)
                img.save(out_path, format="JPEG", quality=85, optimize=True)

                orig_kb = os.path.getsize(path) / 1024
                comp_kb = os.path.getsize(out_path) / 1024
                print(f"[UPLOAD] Image {idx+1}: {orig_kb:.0f} KB → {comp_kb:.0f} KB  "
                      f"({100*comp_kb/max(orig_kb,1):.0f} %)")
                out_paths.append(out_path)

            except Exception as exc:
                print (f"{t('common.image_compression_failed', path=path, exc=exc)}")
                out_paths.append(path)

        return out_paths

    def _post(self, username, title, desc, tags, archive, base_name, image_paths=None, thumbnail_index: int = 0):
        try:
            data = {
                "hwid":            connection.hwid(),
                "username":        username,
                "title":           title,
                "description":     desc,
                "tags":            ",".join(tags),
                "file_name":       f"{base_name}.7z",
                "thumbnail_index": str(thumbnail_index),
            }
            files: dict = {
                "archive": (
                    f"{base_name}.7z",
                    open(archive, "rb"),
                    "application/octet-stream",
                )
            }
            paths_to_send = list(image_paths) if image_paths is not None else list(getattr(self, "_image_paths", []))
            # Reorder so the chosen thumbnail is always the first image sent
            if paths_to_send and 0 <= thumbnail_index < len(paths_to_send):
                thumb = paths_to_send.pop(thumbnail_index)
                paths_to_send.insert(0, thumb)
            for idx, img_path in enumerate(paths_to_send):
                if os.path.exists(img_path):
                    field = "image" if idx == 0 else f"image_{idx}"
                    files[field] = (
                        os.path.basename(img_path),
                        open(img_path, "rb"),
                    )
            resp = requests.post(
                f"{connection.SERVER_URL}/upload",
                data=data, files=files, timeout=90,
                headers={"ngrok-skip-browser-warning": "true"},
            )
            if resp.status_code == 200:
                return True, "ok", False
            try:
                body     = resp.json()
                err      = body.get("error", f"HTTP {resp.status_code}")
                if resp.status_code == 403 and err == "banned":
                    connection.is_banned  = True
                    connection.ban_reason = body.get("ban_reason", "")
                    print("[UPLOAD] Ban detected via /upload response")
                is_warn  = "Warning" in err
                return False, err, is_warn
            except Exception:
                return False, f"HTTP {resp.status_code}", False
        except Exception as exc:
            return False, str(exc), False

    def _succeed(self):
        self._progress_bar.stop()
        self._progress_bar.pack_forget()
        self._progress_lbl.configure(text="")
        self.submit_btn.configure(state="normal", text=t("upload.upload_button"))
        self.title_var.set("")
        self.desc_box.delete("1.0", "end")
        self._clear_image()
        self._clear_zip()
        for tag in list(self._selected_tags):
            self._toggle_tag(tag)
        self._notify(t("upload.uploaded"), "success")
        # Refresh server state (picks up new upload cooldown + username lock) then start ticker
        connection.refresh_user_state(
            on_done=lambda: self.after(0, self._on_upload_state_refreshed)
        )

    def _on_upload_state_refreshed(self):
        self._refresh_username_lock()
        self._tick_upload_cooldown()

    def _on_warning(self, msg: str):
        """Server returned a content warning — re-enable submit without clearing the form."""
        self._progress_bar.stop()
        self._progress_bar.pack_forget()
        self._progress_lbl.configure(text="")
        self.submit_btn.configure(state="normal", text=t("upload.upload_button"))
        self._notify(f"⚠️ {msg}", "warning")

    def _fail(self, msg: str, cooldown: float = 0.0):
        self._progress_bar.stop()
        self._progress_bar.pack_forget()
        self._progress_lbl.configure(text="")
        self.submit_btn.configure(state="normal", text=t("upload.upload_button"))
        if connection.is_banned:
            if self.on_ban_detected:
                self.on_ban_detected()
        elif "upload_cooldown" in msg or "minute cooldown" in msg.lower() or cooldown > 0:
            self._notify(f"🚫 {msg}", "error")
            connection.refresh_user_state(
                on_done=lambda: self.after(0, self._tick_upload_cooldown)
            )
        else:
            self._notify(msg, "error")

    def _notify(self, message, type="info"):
        if self.notification_callback:
            self.notification_callback(message, type)
        else:
            print(f"[UPLOAD] {type.upper()}: {message}")



# ══════════════════════════════════════════════════════════════════════════════
#  DOWNLOAD SUB-TAB
# ══════════════════════════════════════════════════════════════════════════════

# Users must wait this long after downloading before they can rate a skin
_RATING_COOLDOWN_SECS: int = 5 * 60   # 5 minutes

# Where we persist download timestamps between sessions
_DOWNLOAD_TIMES_PATH: str = os.path.join(
    os.path.expanduser("~"), ".beamskin", "download_times.json"
)

class _DownloadSubTab(ctk.CTkFrame):
    """
    Browse community skin mods from the Discord uploads channel.
    • 3-column card grid  • 12 per page  • search  • tag filter
    """

    PAGE_SIZE = 10
    COLS      = 5

    def __init__(self, parent, notification_callback):
        super().__init__(parent, fg_color=state.colors["app_bg"], corner_radius=0)
        self.notification_callback = notification_callback
        self._poll_attempts: int = 0
        self._all_skins:   list  = []
        self._shown_skins: list  = []
        self._total_skins: int   = 0
        self._page:        int   = 0
        self._active_tags: set   = set()
        self._sort_var:    str   = "newest"   # newest | downloads | rating
        self._detail_skin: dict  = None
        self._detail_img_index: int = 0
        self._detail_img_refs: list = []
        # {str(message_id): unix_timestamp} — persisted across sessions
        self._download_times: dict = self._load_download_times()
        self.on_connected = None   # injected by OnlineTab — called on any successful retry
        self._build_ui()

    # ── download-time persistence ────────────────────────────────────────── #

    @staticmethod
    def _load_download_times() -> dict:
        """Load {str(message_id): float timestamp} from disk."""
        try:
            if os.path.exists(_DOWNLOAD_TIMES_PATH):
                with open(_DOWNLOAD_TIMES_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_download_times(self) -> None:
        """Persist download times to disk so cooldown survives restarts."""
        try:
            os.makedirs(os.path.dirname(_DOWNLOAD_TIMES_PATH), exist_ok=True)
            with open(_DOWNLOAD_TIMES_PATH, "w", encoding="utf-8") as f:
                json.dump(self._download_times, f)
        except Exception as exc:
            print(f"[DOWNLOAD] Could not save download times: {exc}")

    def _record_download(self, message_id) -> None:
        """Mark that this machine just downloaded a skin."""
        self._download_times[str(message_id)] = time.time()
        self._save_download_times()

    def _can_rate(self, message_id) -> tuple:
        """
        Returns (can_rate: bool, seconds_remaining: float).
        can_rate is True only if user has downloaded AND ≥5 min have passed.
        """
        ts = self._download_times.get(str(message_id))
        if ts is None:
            return False, 0.0
        elapsed = time.time() - ts
        if elapsed >= _RATING_COOLDOWN_SECS:
            return True, 0.0
        return False, _RATING_COOLDOWN_SECS - elapsed


    # ── layout ──────────────────────────────────────────────────────────── #

    def _build_ui(self):
        # header bar
        hdr = ctk.CTkFrame(self, fg_color=state.colors["frame_bg"], height=60, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text=t("download.header"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=state.colors["text"],
        ).pack(side="left", padx=24, pady=16)

        self._refresh_btn = ctk.CTkButton(hdr, text=t("download.refresh"), width=110, height=34,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self.load_skins)
        self._refresh_btn.pack(side="right", padx=16, pady=13)

        # connection status bar
        status_bar = ctk.CTkFrame(self, fg_color=state.colors["card_bg"], height=40, corner_radius=0)
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)

        status_inner = ctk.CTkFrame(status_bar, fg_color="transparent")
        status_inner.pack(fill="both", expand=True, padx=20)

        self.status_label = ctk.CTkLabel(
            status_inner, text="", font=ctk.CTkFont(size=12), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, pady=10)

        self.retry_btn = ctk.CTkButton(
            status_inner, text=t("common.retry"), width=100, height=28,
            fg_color=state.colors["frame_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._retry_connection,
        )
        self._refresh_status_badge()

        # search + filter bar
        filter_bar = ctk.CTkFrame(self, fg_color=state.colors["frame_bg"], height=52, corner_radius=0)
        filter_bar.pack(fill="x")
        filter_bar.pack_propagate(False)

        filter_inner = ctk.CTkFrame(filter_bar, fg_color="transparent")
        filter_inner.pack(fill="both", expand=True, padx=16, pady=8)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filters())
        ctk.CTkEntry(filter_inner,
            textvariable=self._search_var,
            placeholder_text="🔍  Search skins by title, author or description…",
            height=36, corner_radius=8,
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=13),
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))

        self._filter_btn = ctk.CTkButton(filter_inner, text=t("download.tags.label"), width=130, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._toggle_tag_filter)
        self._filter_btn.pack(side="left")

        # ── sort dropdown ─────────────────────────────────────────────────── #
        self._sort_option = ctk.CTkOptionMenu(
            filter_inner,
            values=[t("download.tags.newest"), t("download.tags.most_downloaded"), t("download.tags.rated")],
            width=160, height=36, corner_radius=8,
            fg_color=state.colors["card_bg"],
            button_color=state.colors["card_bg"],
            button_hover_color=state.colors["card_hover"],
            dropdown_fg_color=state.colors["frame_bg"],
            dropdown_hover_color=state.colors["card_hover"],
            dropdown_text_color=state.colors["text"],
            text_color=state.colors["text"],
            font=ctk.CTkFont(size=12),
            command=self._on_sort_changed,
        )
        self._sort_option.pack(side="left", padx=(8, 0))

        ctk.CTkButton(filter_inner, text=t("download.clear_filters"), width=70, height=36,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color="#e57373", corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._clear_filters).pack(side="left", padx=(8, 0))

        # ── inline tag filter panel (hidden by default) ─────────────────── #
        self._tag_panel = ctk.CTkFrame(self, fg_color=state.colors["card_bg"], corner_radius=0)
        # Not packed initially — toggled by _toggle_tag_filter
        self._tag_panel_visible = False
        self._tag_vars: dict = {}
        self._build_tag_panel()

        # ── main body: list view + detail view stack ─────────────────────── #
        self._body = ctk.CTkFrame(self, fg_color=state.colors["app_bg"], corner_radius=0)
        self._body.pack(fill="both", expand=True)

        # list view
        self._list_frame = ctk.CTkFrame(self._body, fg_color=state.colors["app_bg"], corner_radius=0)
        self._list_frame.pack(fill="both", expand=True)

        # scrollable grid
        self._scroll = ctk.CTkScrollableFrame(self._list_frame, fg_color=state.colors["app_bg"])
        self._scroll.pack(fill="both", expand=True)

        for c in range(self.COLS):
            self._scroll.columnconfigure(c, weight=1, uniform="col")

        # pagination bar (pinned to bottom of list frame)
        page_bar = ctk.CTkFrame(self._list_frame, fg_color=state.colors["frame_bg"], height=50, corner_radius=0)
        page_bar.pack(fill="x", side="bottom")
        page_bar.pack_propagate(False)

        self._prev_btn = ctk.CTkButton(page_bar, text="◀  Prev", width=100, height=32,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._prev_page)
        self._prev_btn.pack(side="left", padx=16, pady=9)

        self._page_lbl = ctk.CTkLabel(page_bar, text="",
            font=ctk.CTkFont(size=13), text_color=state.colors["text_secondary"])
        self._page_lbl.pack(side="left", expand=True)

        self._next_btn = ctk.CTkButton(page_bar, text="Next  ▶", width=100, height=32,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._next_page)
        self._next_btn.pack(side="right", padx=16, pady=9)

        # detail view (hidden by default)
        self._detail_frame = ctk.CTkFrame(self._body, fg_color=state.colors["app_bg"], corner_radius=0)

        self.after(200, self._poll_connection)

    def _build_tag_panel(self):
        """Build inline tag filter checkboxes inside self._tag_panel."""
        for w in self._tag_panel.winfo_children():
            w.destroy()
        self._tag_vars.clear()

        header_row = ctk.CTkFrame(self._tag_panel, fg_color="transparent")
        header_row.pack(fill="x", padx=16, pady=(10, 6))
        ctk.CTkLabel(header_row, text="Filter by tags:", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text"]).pack(side="left")

        btn_row = ctk.CTkFrame(header_row, fg_color="transparent")
        btn_row.pack(side="right")
        ctk.CTkButton(btn_row, text="Clear All", width=90, height=28,
            fg_color=state.colors["frame_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=6, font=ctk.CTkFont(size=11),
            command=self._clear_tag_filter_vars).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Apply", width=80, height=28,
            fg_color=state.colors["accent"], hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"], corner_radius=6, font=ctk.CTkFont(size=11),
            command=self._apply_tag_filter).pack(side="left")

        all_tags = sorted({tg for s in self._all_skins for tg in s.get("tags", [])} or AVAILABLE_TAGS)

        tags_frame = ctk.CTkFrame(self._tag_panel, fg_color="transparent")
        tags_frame.pack(fill="x", padx=16, pady=(0, 10))

        TCOLS = 6
        for i, tag in enumerate(all_tags):
            v = ctk.BooleanVar(value=(tag in self._active_tags))
            self._tag_vars[tag] = v
            ctk.CTkCheckBox(tags_frame, text=tag, variable=v,
                font=ctk.CTkFont(size=12),
                text_color=state.colors["text"],
                fg_color=state.colors["accent"],
                hover_color=state.colors["accent_hover"],
                width=120,
            ).grid(row=i // TCOLS, column=i % TCOLS, padx=6, pady=3, sticky="w")

    def _toggle_tag_filter(self):
        if self._tag_panel_visible:
            self._tag_panel.pack_forget()
            self._tag_panel_visible = False
        else:
            # Rebuild tags (in case skins loaded after initial build)
            self._build_tag_panel()
            self._tag_panel.pack(fill="x", after=self._tag_panel.master.winfo_children()[2])
            self._tag_panel_visible = True

    def _clear_tag_filter_vars(self):
        for v in self._tag_vars.values():
            v.set(False)

    def _apply_tag_filter(self):
        self._active_tags = {tag for tag, v in self._tag_vars.items() if v.get()}
        self._apply_filters()
        # Hide panel after apply
        self._tag_panel.pack_forget()
        self._tag_panel_visible = False

    # ── connection ───────────────────────────────────────────────────────── #

    def _poll_connection(self):
        if connection.check_complete:
            self._refresh_status_badge()
        else:
            self._poll_attempts += 1
            if self._poll_attempts < 40:
                self.after(200, self._poll_connection)

    def _retry_connection(self):
        self.status_label.configure(text=t("common.retrying"), text_color=state.colors["text_secondary"])
        self.retry_btn.pack_forget()
        connection.check_connection(
            on_success=lambda: self.after(0, self._on_retry_success),
            on_failure=lambda: self.after(0, self._refresh_status_badge),
        )

    def _on_retry_success(self):
        self._refresh_status_badge()
        if self.on_connected:
            self.on_connected()

    def _refresh_status_badge(self):
        if connection.is_online:
            self.status_label.configure(text=t("common.server_status_online"), text_color=state.colors["success"])
            self.retry_btn.pack_forget()
        else:
            self.status_label.configure(text=t("download.offline"), text_color=state.colors["error"])
            self.retry_btn.pack(side="right", pady=6)

    # ── search / filter ──────────────────────────────────────────────────── #

    def _open_tag_filter(self):
        """Legacy stub — now handled by _toggle_tag_filter."""
        self._toggle_tag_filter()

    def _clear_filters(self):
        self._search_var.set("")
        self._active_tags.clear()
        # Reset tag checkboxes
        for v in self._tag_vars.values():
            v.set(False)
        self._filter_btn.configure(text="🏷️  Filter Tags",
            fg_color=state.colors["card_bg"], text_color=state.colors["text"])
        # Reset sort
        self._sort_var = "newest"
        self._sort_option.set("🕒  Newest")
        self._apply_filters()

    def _on_sort_changed(self, value: str):
        """Called when the sort dropdown changes. Re-fetch page 0 with new sort."""
        label_to_key = {
            "🕒  Newest":          "newest",
            "⬇  Most Downloaded":  "downloads",
            "⭐  Top Rated":        "rating",
        }
        self._sort_var = label_to_key.get(value, "newest")
        # Reset and re-fetch from the server with the new sort
        self._all_skins   = []
        self._shown_skins = []
        self._total_skins = 0
        self._page        = 0
        self._fetch_page(0)

    def _apply_filters(self):
        query = self._search_var.get().lower().strip()
        result = []
        for s in self._all_skins:
            if self._active_tags and not self._active_tags.issubset(set(s.get("tags", []))):
                continue
            if query:
                haystack = (s.get("title","") + " " + s.get("username","") + " " + s.get("description","")).lower()
                if query not in haystack:
                    continue
            result.append(s)
        # Apply local sort to filtered results
        if self._sort_var == "downloads":
            result.sort(key=lambda s: s.get("downloads", 0), reverse=True)
        elif self._sort_var == "rating":
            result.sort(key=lambda s: (s.get("avg_rating", 0.0), s.get("rating_count", 0)), reverse=True)
        self._shown_skins = result
        self._page = 0
        self._render_page()
        # Update filter button label
        if self._active_tags:
            self._filter_btn.configure(text=f"🏷️  Tags ({len(self._active_tags)})",
                fg_color=state.colors["accent"], text_color=state.colors["accent_text"])
        else:
            self._filter_btn.configure(text="🏷️  Filter Tags",
                fg_color=state.colors["card_bg"], text_color=state.colors["text"])

    # ── detail view ─────────────────────────────────────────────────────── #

    def _open_detail(self, skin: dict):
        """Show the detail view for a given skin."""
        self._detail_skin = skin
        self._detail_img_index = 0
        self._detail_img_refs = []

        # Determine image urls (support images_urls list or single image_url)
        self._detail_images = skin.get("images_urls") or skin.get("image_urls") or []
        if not self._detail_images and skin.get("image_url"):
            self._detail_images = [skin["image_url"]]

        # Switch views
        self._list_frame.pack_forget()
        for w in self._detail_frame.winfo_children():
            w.destroy()
        self._detail_frame.pack(fill="both", expand=True)

        self._build_detail_view(skin)

    def _build_detail_view(self, skin: dict):
        df = self._detail_frame

        # ── back button bar ── #
        back_bar = ctk.CTkFrame(df, fg_color=state.colors["frame_bg"], height=48, corner_radius=0)
        back_bar.pack(fill="x")
        back_bar.pack_propagate(False)
        ctk.CTkButton(back_bar, text="◀  Back to list", width=140, height=32,
            fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
            border_width=1, border_color=state.colors["border"],
            text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._close_detail).pack(side="left", padx=16, pady=8)

        # ── translate toggle (only if googletrans is available) ── #
        self._translate_active = False
        self._translate_btn    = None
        if _TRANSLATE_AVAILABLE:
            self._translate_btn = ctk.CTkButton(
                back_bar, text=t("download.translate"), width=130, height=32,
                fg_color=state.colors["card_bg"], hover_color=state.colors["card_hover"],
                border_width=1, border_color=state.colors["border"],
                text_color=state.colors["text"], corner_radius=8, font=ctk.CTkFont(size=12),
                command=self._toggle_translate,
            )
            self._translate_btn.pack(side="right", padx=16, pady=8)

        # ── scrollable content ── #
        scroll = ctk.CTkScrollableFrame(df, fg_color=state.colors["app_bg"])
        scroll.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(scroll, fg_color=state.colors["card_bg"], corner_radius=14)
        inner.pack(fill="both", expand=True, padx=40, pady=30)

        content = ctk.CTkFrame(inner, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=24)

        # Posted by
        ctk.CTkLabel(content,
            text=f"{t('download.postedby')} {skin.get('username', 'Unknown')}",
            font=ctk.CTkFont(size=13), text_color=state.colors["text_secondary"], anchor="w",
        ).pack(fill="x", pady=(0, 6))

        # Title
        self._detail_title_lbl = ctk.CTkLabel(content,
            text=skin.get("title", "Untitled"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=state.colors["text"], anchor="w", wraplength=700,
        )
        self._detail_title_lbl.pack(fill="x", pady=(0, 16))

        # ── image viewer ── #
        if self._detail_images and _PIL_AVAILABLE:
            img_section = ctk.CTkFrame(content, fg_color="transparent")
            img_section.pack(fill="x", pady=(0, 12))

            nav_row = ctk.CTkFrame(img_section, fg_color="transparent")
            nav_row.pack(fill="x")

            # left arrow — packed first so it anchors to the far left
            self._detail_left_btn = ctk.CTkButton(
                nav_row, text="◀", width=40, height=300,
                fg_color=state.colors["frame_bg"], hover_color=state.colors["card_hover"],
                text_color=state.colors["text"], corner_radius=6, font=ctk.CTkFont(size=18),
                command=self._detail_prev_img,
            )
            self._detail_left_btn.pack(side="left", padx=(0, 4))

            # right arrow — packed second so it anchors to the far right
            self._detail_right_btn = ctk.CTkButton(
                nav_row, text="▶", width=40, height=300,
                fg_color=state.colors["frame_bg"], hover_color=state.colors["card_hover"],
                text_color=state.colors["text"], corner_radius=6, font=ctk.CTkFont(size=18),
                command=self._detail_next_img,
            )
            self._detail_right_btn.pack(side="right", padx=(4, 0))

            # main image label — packed last, fills space between arrows; click to fullscreen
            self._detail_img_lbl = ctk.CTkLabel(nav_row, text="🖼️  Loading…",
                font=ctk.CTkFont(size=13), text_color=state.colors["text_secondary"],
                fg_color=state.colors["frame_bg"], corner_radius=8,
                width=600, height=300, cursor="hand2")
            self._detail_img_lbl.pack(side="left", expand=True, fill="x")
            self._detail_img_lbl.bind("<Button-1>", lambda e: self._open_fullscreen(self._detail_img_index))

            # thumbnails row (only if > 1 image)
            if len(self._detail_images) > 1:
                self._detail_thumb_frame = ctk.CTkFrame(img_section, fg_color="transparent")
                self._detail_thumb_frame.pack(fill="x", pady=(8, 0))
            else:
                self._detail_thumb_frame = None

            self._detail_update_arrows()
            threading.Thread(
                target=self._load_detail_images, args=(list(self._detail_images),), daemon=True
            ).start()

        # ── description ── #
        desc = skin.get("description", "")
        self._detail_desc_lbl = None
        if desc:
            ctk.CTkLabel(content, text=t("download.download_description"),
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=state.colors["text"], anchor="w",
            ).pack(fill="x", pady=(4, 4))
            self._detail_desc_lbl = ctk.CTkLabel(content, text=desc,
                font=ctk.CTkFont(size=13), text_color=state.colors["text"],
                wraplength=700, justify="left", anchor="nw",
            )
            self._detail_desc_lbl.pack(fill="x", pady=(0, 14))

        # ── tags ── #
        tags = skin.get("tags", [])
        if tags:
            ctk.CTkLabel(content, text=t("download.download_tags"),
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=state.colors["text"], anchor="w",
            ).pack(fill="x", pady=(0, 4))
            tag_bar = ctk.CTkFrame(content, fg_color="transparent")
            tag_bar.pack(fill="x", pady=(0, 14))
            for tg in tags:
                ctk.CTkLabel(tag_bar, text=f" {tg} ",
                    font=ctk.CTkFont(size=12),
                    fg_color=state.colors["accent"],
                    text_color=state.colors["accent_text"],
                    corner_radius=8,
                ).pack(side="left", padx=(0, 4), pady=2)

        # ── download button ── #
        size_txt = ""
        if skin.get("file_size"):
            size_txt = f"  {skin['file_size'] / 1024 / 1024:.2f} MB"
        ctk.CTkButton(content, text=f"{t('download.download_button')}{size_txt}", height=46,
            fg_color="#2d7a2d", hover_color="#1a5c1a",
            text_color="white", corner_radius=10, font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self._start_download(skin),
        ).pack(fill="x", pady=(6, 0))

        # ── ratings + download count ── #
        self._build_star_rating(content, skin, size=20).pack(pady=(12, 0))

    def _detail_update_arrows(self):
        """Enable/disable arrows based on current image index. Buttons are always visible."""
        n = len(self._detail_images)
        if n <= 1:
            self._detail_left_btn.pack_forget()
            self._detail_right_btn.pack_forget()
            return
        self._detail_left_btn.configure(state="normal" if self._detail_img_index > 0 else "disabled")
        self._detail_right_btn.configure(state="normal" if self._detail_img_index < n - 1 else "disabled")

    def _detail_prev_img(self):
        if self._detail_img_index > 0:
            self._detail_img_index -= 1
            self._detail_show_image(self._detail_img_index)
            self._detail_update_arrows()
            self._detail_update_thumbs()

    def _detail_next_img(self):
        if self._detail_img_index < len(self._detail_images) - 1:
            self._detail_img_index += 1
            self._detail_show_image(self._detail_img_index)
            self._detail_update_arrows()
            self._detail_update_thumbs()

    def _detail_show_image(self, idx: int):
        if idx < len(self._detail_img_refs):
            ref = self._detail_img_refs[idx]
            if ref is not None:
                self._detail_img_lbl.configure(image=ref, text="")
            else:
                self._detail_img_lbl.configure(image=None, text="❌ Failed to load")

    def _detail_update_thumbs(self):
        if not self._detail_thumb_frame:
            return
        for w in self._detail_thumb_frame.winfo_children():
            w.destroy()
        thumb_refs = getattr(self, "_detail_thumb_refs", {})
        for i in range(len(self._detail_images)):
            ref = thumb_refs.get(i)
            if ref is None:
                continue
            border_color = state.colors["accent"] if i == self._detail_img_index else state.colors["border"]
            thumb_frame = ctk.CTkFrame(self._detail_thumb_frame,
                fg_color=border_color, corner_radius=6, width=72, height=52)
            thumb_frame.pack(side="left", padx=4)
            thumb_frame.pack_propagate(False)
            lbl = ctk.CTkLabel(thumb_frame, text="", image=ref)
            lbl.pack(expand=True, padx=2, pady=2)
            idx_cap = i
            thumb_frame.bind("<Button-1>", lambda e, ix=idx_cap: self._detail_jump(ix))
            lbl.bind("<Button-1>", lambda e, ix=idx_cap: self._detail_jump(ix))

    def _detail_jump(self, idx: int):
        self._detail_img_index = idx
        self._detail_show_image(idx)
        self._detail_update_arrows()
        self._detail_update_thumbs()

    def _load_detail_images(self, urls: list):
        """Load all images for the detail view in a background thread."""
        self._detail_img_refs = [None] * len(urls)
        if not hasattr(self, "_detail_pil_imgs"):
            self._detail_pil_imgs = {}
        for i, url in enumerate(urls):
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    img = _PILImage.open(io.BytesIO(resp.content)).convert("RGBA")
                    # Store the full-resolution PIL image for fullscreen zoom
                    self._detail_pil_imgs[i] = img
                    # Main display: fit in ~600x340
                    display = img.copy()
                    display.thumbnail((600, 340))
                    ctk_main = ctk.CTkImage(light_image=display, dark_image=display, size=display.size)
                    # Thumbnail: fit in 68x48
                    thumb = img.copy()
                    thumb.thumbnail((68, 48))
                    ctk_thumb = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
                    self._detail_img_refs[i] = ctk_main
                    if not hasattr(self, "_detail_thumb_refs"):
                        self._detail_thumb_refs = {}
                    self._detail_thumb_refs[i] = ctk_thumb
            except Exception:
                self._detail_img_refs[i] = None
            idx_cap = i
            self.after(0, lambda ix=idx_cap: self._on_detail_img_loaded(ix))

    def _on_detail_img_loaded(self, idx: int):
        # Show first image automatically
        if idx == 0:
            self._detail_show_image(0)
        # Update thumb strip using thumb refs
        if self._detail_thumb_frame and hasattr(self, "_detail_thumb_refs"):
            self._rebuild_thumb_strip()

    def _rebuild_thumb_strip(self):
        if not self._detail_thumb_frame:
            return
        for w in self._detail_thumb_frame.winfo_children():
            w.destroy()
        thumb_refs = getattr(self, "_detail_thumb_refs", {})
        for i in range(len(self._detail_images)):
            ref = thumb_refs.get(i)
            if ref is None:
                continue
            border_color = state.colors["accent"] if i == self._detail_img_index else state.colors["border"]
            thumb_frame = ctk.CTkFrame(self._detail_thumb_frame,
                fg_color=border_color, corner_radius=6, width=72, height=52)
            thumb_frame.pack(side="left", padx=4)
            thumb_frame.pack_propagate(False)
            lbl = ctk.CTkLabel(thumb_frame, text="", image=ref)
            lbl.pack(expand=True, padx=2, pady=2)
            thumb_frame.bind("<Button-1>", lambda e, ix=i: self._detail_jump(ix))
            lbl.bind("<Button-1>", lambda e, ix=i: self._detail_jump(ix))

    def _toggle_translate(self):
        """Toggle translation of the currently open skin's title and description."""
        if self._translate_active:
            # Restore originals
            skin = self._detail_skin
            if skin and self._detail_title_lbl and self._detail_title_lbl.winfo_exists():
                self._detail_title_lbl.configure(text=skin.get("title", ""))
            if skin and self._detail_desc_lbl and self._detail_desc_lbl.winfo_exists():
                self._detail_desc_lbl.configure(text=skin.get("description", ""))
            self._translate_active = False
            if self._translate_btn and self._translate_btn.winfo_exists():
                self._translate_btn.configure(
                    text=t("download.translate"),
                    fg_color=state.colors["card_bg"],
                    text_color=state.colors["text"],
                )
        else:
            # Start translation
            if self._translate_btn and self._translate_btn.winfo_exists():
                self._translate_btn.configure(text=t("download.translating"), state="disabled")
            threading.Thread(target=self._do_translate, daemon=True).start()

    def _do_translate(self):
        """Run translation in background thread and update labels."""
        skin = self._detail_skin
        if not skin:
            return
        try:
            target_lang = _get_target_lang()
            print(f"[TRANSLATE] Translating to: {target_lang}")

            title = skin.get("title", "").strip()
            desc  = skin.get("description", "").strip()

            if not title and not desc:
                print("[TRANSLATE] Nothing to translate")
                self.after(0, lambda: self._translate_btn.configure(text=t("download.translate"), state="normal") if self._translate_btn else None)
                return

            def _translate_chunk(text: str) -> str:
                """Translate text, splitting into 500-char chunks if needed."""
                if not text:
                    return text
                if len(text) <= 500:
                    return _GTranslator(source="auto", target=target_lang).translate(text)
                # Split long text into chunks
                chunks = [text[i:i+500] for i in range(0, len(text), 500)]
                translated_chunks = [
                    _GTranslator(source="auto", target=target_lang).translate(chunk)
                    for chunk in chunks
                ]
                return " ".join(translated_chunks)

            translated_title = _translate_chunk(title)
            translated_desc  = _translate_chunk(desc)

            print(f"[TRANSLATE] Title: {title!r} → {translated_title!r}")
            print(f"[TRANSLATE] Desc snippet: {desc[:60]!r} → {translated_desc[:60]!r}")

            def _apply():
                if self._detail_title_lbl and self._detail_title_lbl.winfo_exists():
                    self._detail_title_lbl.configure(text=translated_title)
                if self._detail_desc_lbl and self._detail_desc_lbl.winfo_exists():
                    self._detail_desc_lbl.configure(text=translated_desc)
                self._translate_active = True
                if self._translate_btn and self._translate_btn.winfo_exists():
                    self._translate_btn.configure(
                        text=t("download.show_original"),
                        state="normal",
                        fg_color=state.colors["accent"],
                        text_color=state.colors["accent_text"],
                    )

            self.after(0, _apply)

        except Exception as exc:
            print(f"[TRANSLATE] ERROR: {exc}")
            def _err():
                self._notify(f"Translation failed: {exc}", "error")
                if self._translate_btn and self._translate_btn.winfo_exists():
                    self._translate_btn.configure(text=t("download.translate"), state="normal")
            self.after(0, _err)

    def _open_fullscreen(self, idx: int):
        """Open a fullscreen image viewer with zoom and pan support."""
        pil_imgs = getattr(self, "_detail_pil_imgs", {})
        pil_img  = pil_imgs.get(idx)
        if pil_img is None:
            return

        import tkinter as tk
        from PIL import ImageTk

        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Image Viewer")
        win.configure(bg="#0f0f0f")
        win.attributes("-fullscreen", True)
        win.focus_force()

        # ── state ──────────────────────────────────────────────────────────── #
        zoom       = [1.0]
        offset     = [0, 0]      # canvas pan offset in pixels
        drag_start = [0, 0]
        img_ref    = [None]      # keep PhotoImage alive (prevent GC)
        canvas_img = [None]      # canvas item ID — moved instead of redrawn when panning
        last_scale = [None]      # (canvas_w, canvas_h, zoom) at last resize — detect real changes
        _resize_job = [None]     # debounce handle for window resize

        canvas = tk.Canvas(win, bg="#0f0f0f", highlightthickness=0, cursor="crosshair")
        canvas.pack(fill="both", expand=True)

        # hint label
        hint = tk.Label(win, text="Scroll to zoom  •  Drag to pan  •  ESC or click × to close",
            bg="#0f0f0f", fg="#888888", font=("Segoe UI", 11))
        hint.place(relx=0.5, rely=0.97, anchor="s")

        # close button
        close_btn = tk.Button(win, text="✕", bg="#222", fg="white",
            font=("Segoe UI", 14, "bold"), bd=0, padx=10, pady=4,
            activebackground="#444", activeforeground="white",
            command=win.destroy, cursor="hand2")
        close_btn.place(relx=1.0, x=-10, y=10, anchor="ne")

        def _resize_image():
            """Resize + re-render the image. Only called when zoom or canvas size actually changes."""
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 2 or h < 2:
                win.after(50, _resize_image)
                return

            img_w, img_h = pil_img.size
            base_scale   = min(w / img_w, h / img_h)
            scale        = base_scale * zoom[0]
            new_w        = max(1, int(img_w * scale))
            new_h        = max(1, int(img_h * scale))

            # BILINEAR is fast and perfectly adequate for interactive zooming
            resized      = pil_img.resize((new_w, new_h), _PILImage.BILINEAR)
            photo        = ImageTk.PhotoImage(resized)
            img_ref[0]   = photo
            last_scale[0] = (w, h, zoom[0])

            cx = w // 2 + offset[0]
            cy = h // 2 + offset[1]

            if canvas_img[0] is None:
                canvas_img[0] = canvas.create_image(cx, cy, image=photo, anchor="center")
            else:
                canvas.itemconfigure(canvas_img[0], image=photo)
                canvas.coords(canvas_img[0], cx, cy)

        def _pan_only():
            """Just move the existing canvas image — no PIL resize, virtually zero cost."""
            if canvas_img[0] is None:
                return
            w  = canvas.winfo_width()
            h  = canvas.winfo_height()
            cx = w // 2 + offset[0]
            cy = h // 2 + offset[1]
            canvas.coords(canvas_img[0], cx, cy)

        def _on_resize(e):
            # Debounce: only resize once the window stops changing for 80 ms
            if _resize_job[0]:
                win.after_cancel(_resize_job[0])
            _resize_job[0] = win.after(80, _resize_image)

        def _on_scroll(e):
            factor = 1.15 if (e.delta > 0 or e.num == 4) else (1 / 1.15)
            zoom[0] = max(0.1, min(zoom[0] * factor, 20.0))
            _resize_image()   # zoom changed → must resize

        def _on_drag_start(e):
            drag_start[0] = e.x
            drag_start[1] = e.y

        def _on_drag(e):
            offset[0] += e.x - drag_start[0]
            offset[1] += e.y - drag_start[1]
            drag_start[0] = e.x
            drag_start[1] = e.y
            _pan_only()   # ← just move the image, no resize at all

        def _reset_pan(e=None):
            offset[0] = 0
            offset[1] = 0
            zoom[0]   = 1.0
            _resize_image()

        canvas.bind("<Configure>",      _on_resize)
        canvas.bind("<MouseWheel>",     _on_scroll)    # Windows / macOS
        canvas.bind("<Button-4>",       _on_scroll)    # Linux scroll up
        canvas.bind("<Button-5>",       _on_scroll)    # Linux scroll down
        canvas.bind("<ButtonPress-1>",  _on_drag_start)
        canvas.bind("<B1-Motion>",      _on_drag)
        canvas.bind("<Double-Button-1>", _reset_pan)
        win.bind("<Escape>",            lambda e: win.destroy())

        win.after(50, _resize_image)

    def _close_detail(self):
        self._detail_frame.pack_forget()
        self._list_frame.pack(fill="both", expand=True)
        self._detail_skin = None
        self._detail_img_refs = []
        if hasattr(self, "_detail_thumb_refs"):
            self._detail_thumb_refs = {}
        if hasattr(self, "_detail_pil_imgs"):
            self._detail_pil_imgs = {}


    # ── pagination ───────────────────────────────────────────────────────── #

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._fetch_page(self._page)

    def _next_page(self):
        total_pages = max(1, (self._total_skins + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self._page < total_pages - 1:
            self._page += 1
            self._fetch_page(self._page)

    def _fetch_page(self, page: int):
        """Show loading state and fetch the given page from server."""
        for w in self._scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._scroll, text="⏳ Loading…",
            font=ctk.CTkFont(size=14), text_color=state.colors["text_secondary"],
        ).grid(row=0, column=0, columnspan=5, pady=60)
        self._prev_btn.configure(state="disabled")
        self._next_btn.configure(state="disabled")
        threading.Thread(target=self._fetch, args=(page,), daemon=True).start()

    def _render_page(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        skins = self._shown_skins
        # Use server-side total if available (no active filters), else use local count
        if self._active_tags or self._search_var.get().strip():
            total_items = len(skins)
        else:
            total_items = max(len(skins), self._total_skins)
        total_pages = max(1, (total_items + self.PAGE_SIZE - 1) // self.PAGE_SIZE)

        if not skins:
            msg = ("No results match your search or filters."
                   if (self._search_var.get() or self._active_tags)
                   else "No skin mods uploaded yet — be the first!")
            ctk.CTkLabel(self._scroll, text=msg,
                font=ctk.CTkFont(size=14), text_color=state.colors["text_secondary"],
            ).grid(row=0, column=0, columnspan=5, pady=60)
            self._page_lbl.configure(text="")
            self._prev_btn.configure(state="disabled")
            self._next_btn.configure(state="disabled")
            return

        # For client-side filtered views, slice locally; otherwise show the full fetched page.
        if self._active_tags or self._search_var.get().strip():
            page_skins = skins[self._page * self.PAGE_SIZE : (self._page + 1) * self.PAGE_SIZE]
        else:
            page_skins = skins  # server already returned the right page

        for i, skin in enumerate(page_skins):
            row, col = divmod(i, self.COLS)
            self._card(skin, row, col)

        self._page_lbl.configure(
            text=f"Page {self._page + 1} of {total_pages}  ({total_items} skin{'s' if total_items != 1 else ''})")
        self._prev_btn.configure(state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(state="normal" if self._page < total_pages - 1 else "disabled")

    # ── load ─────────────────────────────────────────────────────────────── #

    def load_skins(self, force: bool = False, from_tab_switch: bool = False):

        REFRESH_COOLDOWN = 300  # 5 minutes

        if from_tab_switch:
            # Don't re-fetch if we already have data — just re-render the page.
            if self._total_skins > 0:
                self._render_page()
                return
            # First visit — fetch without updating the cooldown timestamp so the
            # button cooldown is not consumed by a tab switch.
        else:
            # Button-triggered: enforce the 5-minute cooldown.
            last = getattr(self, "_last_refresh", 0)
            if not force and last > 0:
                remaining = int(REFRESH_COOLDOWN - (time.time() - last))
                if remaining > 0:
                    m, s = divmod(remaining, 60)
                    self._refresh_btn.configure(
                        state="disabled", text=f"{t('download.refresh')} ({m}m {s}s)")
                    return
            # Record the timestamp so the button cooldown starts now.
            self._last_refresh = time.time()
            self._tick_refresh_cooldown()

        # Reset client-side state and show a loading indicator.
        self._all_skins   = []
        self._shown_skins = []
        self._total_skins = 0
        self._page        = 0
        for w in self._scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._scroll, text="⏳ Loading skin mods…",
            font=ctk.CTkFont(size=14), text_color=state.colors["text_secondary"],
        ).grid(row=0, column=0, columnspan=5, pady=60)
        self._refresh_btn.configure(state="disabled", text=t("download.refresh"))
        if from_tab_switch:
            self._last_refresh = time.time()
            self._tick_refresh_cooldown()
        threading.Thread(target=self._fetch, args=(0,), daemon=True).start()

    def _tick_refresh_cooldown(self):
        if not self._refresh_btn.winfo_exists():
            return
        remaining = int(300 - (time.time() - getattr(self, "_last_refresh", 0)))
        if remaining > 0:
            m, s = divmod(remaining, 60)
            self._refresh_btn.configure(state="disabled", text=f"{t('download.refresh')} ({m}m {s}s)")
            self.after(1000, self._tick_refresh_cooldown)
        else:
            self._refresh_btn.configure(state="normal", text=t("download.refresh"))

    def _fetch(self, page: int):
        """Fetch a single page of skins from the server."""
        try:
            resp = requests.get(
                f"{connection.SERVER_URL}/downloads",
                params={
                    "hwid":      connection.hwid(),
                    "page":      page,
                    "page_size": self.PAGE_SIZE,
                    "sort_by":   self._sort_var,
                },
                timeout=15,
                headers={"ngrok-skip-browser-warning": "true"},
            )
            if resp.status_code == 200:
                data  = resp.json()
                skins = data.get("skins", [])
                total = data.get("total", len(skins))
                connection.is_online = True
                self.after(0, lambda: self._on_loaded(skins, page, total))
                if self.on_connected:
                    self.after(0, self.on_connected)
            else:
                self.after(0, lambda: self._show_err(t("download.errors.server_offline")))
        except Exception as exc:
            self.after(0, lambda: self._show_err(f"Could not reach server: {exc}"))

    def _on_loaded(self, skins: list, page: int, total: int):
        self._all_skins   = skins
        self._shown_skins = skins[:]
        self._total_skins = total
        self._page        = page
        self._render_page()

    def _show_err(self, msg: str):
        for w in self._scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._scroll, text=f"❌ {msg}",
            font=ctk.CTkFont(size=13), text_color=state.colors["error"],
        ).grid(row=0, column=0, columnspan=5, pady=60)

    # ── individual skin card (grid cell) ─────────────────────────────────── #

    def _card(self, skin: dict, row: int, col: int):
        card = ctk.CTkFrame(self._scroll, fg_color=state.colors["card_bg"], corner_radius=14)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=14)

        # image preview
        img_url = skin.get("image_url") or (skin.get("images_urls") or skin.get("image_urls") or [None])[0]
        if img_url and _PIL_AVAILABLE:
            preview_frame = ctk.CTkFrame(inner,
                fg_color=state.colors["frame_bg"],
                corner_radius=10, height=140)
            preview_frame.pack(fill="x", pady=(0, 10))
            preview_frame.pack_propagate(False)
            ph = ctk.CTkLabel(preview_frame, text="🖼️  Loading…",
                font=ctk.CTkFont(size=11), text_color=state.colors["text_secondary"])
            ph.pack(expand=True)
            threading.Thread(target=self._load_img, args=(img_url, ph, 300, 140, 10), daemon=True).start()

        # title
        ctk.CTkLabel(inner, text=skin.get("title", "Untitled"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=state.colors["text"], anchor="w", wraplength=260,
        ).pack(fill="x", pady=(0, 2))

        # by
        ctk.CTkLabel(inner, text=f"By {skin.get('username', 'Unknown')}",
            font=ctk.CTkFont(size=11), text_color=state.colors["text_secondary"], anchor="w",
        ).pack(fill="x", pady=(0, 6))

        # tags (cap at 3 for smaller cards)
        tags = skin.get("tags", [])
        if tags:
            tag_bar = ctk.CTkFrame(inner, fg_color="transparent")
            tag_bar.pack(fill="x", pady=(0, 6))
            for tg in tags[:3]:
                ctk.CTkLabel(tag_bar, text=f" {tg} ",
                    font=ctk.CTkFont(size=10),
                    fg_color=state.colors["accent"],
                    text_color=state.colors["accent_text"],
                    corner_radius=8,
                ).pack(side="left", padx=(0, 3))
            if len(tags) > 3:
                ctk.CTkLabel(tag_bar, text=f"+{len(tags)-3}",
                    font=ctk.CTkFont(size=10), text_color=state.colors["text_secondary"],
                ).pack(side="left")

        # description (truncated)
        desc = skin.get("description", "")
        if len(desc) > 80:
            desc = desc[:77] + "…"
        ctk.CTkLabel(inner, text=desc,
            font=ctk.CTkFont(size=11), text_color=state.colors["text"],
            wraplength=260, justify="left", anchor="nw",
        ).pack(fill="x", pady=(0, 8))

        # download button
        size_txt = ""
        if skin.get("file_size"):
            size_txt = f"  {skin['file_size'] / 1024 / 1024:.2f} MB"

        ctk.CTkButton(inner, text=f"{t('download.download_button')}{size_txt}", height=34,
            fg_color="#2d7a2d", hover_color="#1a5c1a",
            text_color="white", corner_radius=8, font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda s=skin: self._start_download(s),
        ).pack(fill="x", pady=(0, 4))

        # ratings + download count
        self._build_star_rating(inner, skin, size=14).pack(fill="x", pady=(2, 0))

        # ── hover + click to open detail ── #
        def _on_enter(e, c=card):
            c.configure(fg_color=state.colors["card_hover"])
        def _on_leave(e, c=card):
            c.configure(fg_color=state.colors["card_bg"])
        def _on_click(e, s=skin):
            self._open_detail(s)

        for widget in (card, inner):
            widget.bind("<Enter>", _on_enter)
            widget.bind("<Leave>", _on_leave)
            widget.bind("<Button-1>", _on_click)
        # Bind children too (labels etc.) but not the download button
        for child in inner.winfo_children():
            child_type = type(child).__name__
            if "Button" not in child_type:
                child.bind("<Enter>", _on_enter)
                child.bind("<Leave>", _on_leave)
                child.bind("<Button-1>", _on_click)


    def _load_img(self, url: str, label: ctk.CTkLabel, w: int, h: int, radius: int = 0):
        try:
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                img = _PILImage.open(io.BytesIO(resp.content)).convert("RGBA")
                img.thumbnail((w, h))
                if radius > 0:
                    # Build a rounded-rectangle mask and apply it
                    mask = _PILImage.new("L", img.size, 0)
                    from PIL import ImageDraw
                    draw = ImageDraw.Draw(mask)
                    draw.rounded_rectangle((0, 0, img.width, img.height), radius=radius, fill=255)
                    result = _PILImage.new("RGBA", img.size, (0, 0, 0, 0))
                    result.paste(img, mask=mask)
                    img = result
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.after(0, lambda i=ctk_img: label.configure(image=i, text=""))
        except Exception:
            pass

    # ── download pipeline ─────────────────────────────────────────────────── #

    def _start_download(self, skin: dict):
        message_id = skin.get("message_id")
        if not message_id:
            self._notify("No download ID available for this skin.", "error")
            return

        try:
            from core.settings import get_mods_folder_path
            mods_folder = get_mods_folder_path()
        except Exception:
            mods_folder = None

        if not mods_folder or not os.path.exists(mods_folder):
            self._notify("Please set your BeamNG mods folder in Settings first.", "error")
            return

        self._notify(f"⏳ Downloading '{skin.get('title', 'skin')}' — please wait…", "info")
        threading.Thread(target=self._do_download, args=(skin, message_id, mods_folder), daemon=True).start()

    def _do_download(self, skin: dict, message_id: int, mods_folder: str):
        tmp = tempfile.mkdtemp(prefix="bs_dl_")
        try:
            resp = requests.get(
                f"{connection.SERVER_URL}/download/{message_id}",
                params={"hwid": connection.hwid()},
                timeout=120,
                stream=True,
                headers={"ngrok-skip-browser-warning": "true"},
            )

            if resp.status_code == 422:
                try:
                    body  = resp.json()
                    title = body.get("title", skin.get("title", "Unknown"))
                    bad   = ", ".join(body.get("bad_files", []))
                    self.after(0, lambda t=title, b=bad: self._notify(
                        f"⛔ Skin mod \"{t}\" was removed — disallowed files detected ({b}).", "error"))
                except Exception:
                    self.after(0, lambda: self._notify(
                        "This skin was removed — it contained disallowed files.", "error"))
                self.after(500, lambda: self.load_skins(force=True))
                return

            if resp.status_code != 200:
                try:
                    err = resp.json().get("error", f"HTTP {resp.status_code}")
                except Exception:
                    err = f"HTTP {resp.status_code}"
                self.after(0, lambda e=err: self._notify(f"Download failed: {e}", "error"))
                return

            title    = skin.get("title", "skin_mod")
            base     = "".join(c for c in title if c.isalnum() or c in " _-").strip() or "skin_mod"
            zip_path = os.path.join(tmp, f"{base}.zip")
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(65536):
                    f.write(chunk)

            dest = os.path.join(mods_folder, f"{base}.zip")
            shutil.move(zip_path, dest)

            # Mark skin as downloaded in local skin dict so rating UI appears immediately
            skin["has_downloaded"] = True
            self._record_download(message_id)
            self.after(0, lambda: self._notify(
                f"✅ '{title}' installed! You can rate it in 5 minutes.", "success"
            ))

        except Exception as exc:
            self.after(0, lambda e=str(exc): self._notify(f"Download error: {e}", "error"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ── star rating ───────────────────────────────────────────────────────── #

    def _build_star_rating(self, parent, skin: dict, size: int = 18):
        """
        Build the rating UI block.

        Layout (two separate rows):
          Row 1 — Public stats:   ⬇ 42   ★★★★☆  3.8  (12 ratings)
          Row 2 — User action:    one of:
            • "⬇ Download to rate this skin"          (never downloaded)
            • "⏳ You can rate in M:SS"                (downloaded, cooldown active)
            • Interactive ★ stars + "Rate this skin"   (cooldown passed)
        """
        message_id   = skin.get("message_id")
        avg_rating   = skin.get("avg_rating", 0.0)
        rating_count = skin.get("rating_count", 0)
        downloads    = skin.get("downloads", 0)
        your_rating  = skin.get("your_rating", 0)

        # Has the user ever downloaded this skin (this session OR a previous one)?
        has_downloaded = (
            skin.get("has_downloaded", False)
            or (message_id is not None and str(message_id) in self._download_times)
        )

        # Users cannot rate their own uploads
        skin_author  = (skin.get("username") or "").strip().lower()
        current_user = (connection.server_username or "").strip().lower()
        is_own_skin  = bool(skin_author and current_user and skin_author == current_user)

        can_rate, remaining = self._can_rate(message_id)

        wrapper = ctk.CTkFrame(parent, fg_color="transparent")

        # ── Row 1: Public stats ─────────────────────────────────────────── #
        stats_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, 3))

        ctk.CTkLabel(
            stats_row,
            text=f"⬇ {downloads}",
            font=ctk.CTkFont(size=size - 4),
            text_color=state.colors["text_secondary"],
        ).pack(side="left", padx=(0, 10))

        # Separator dot
        ctk.CTkLabel(
            stats_row, text="·",
            font=ctk.CTkFont(size=size - 4),
            text_color=state.colors["text_secondary"],
        ).pack(side="left", padx=(0, 10))

        if rating_count > 0:
            avg_filled = round(avg_rating)
            star_str   = "★" * avg_filled + "☆" * (5 - avg_filled)
            ctk.CTkLabel(
                stats_row,
                text=f"{star_str}  {avg_rating:.1f}  ({rating_count} rating{'s' if rating_count != 1 else ''})",
                font=ctk.CTkFont(size=size - 4),
                text_color="#f5a623",
            ).pack(side="left")
        else:
            ctk.CTkLabel(
                stats_row,
                text=t("download.no_ratings"),
                font=ctk.CTkFont(size=size - 4),
                text_color=state.colors["text_secondary"],
            ).pack(side="left")

        # ── Row 2: User rating action ───────────────────────────────────── #
        action_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        action_row.pack(fill="x")

        if is_own_skin:
            # Author cannot rate their own skin
            ctk.CTkLabel(
                action_row,
                text=t("download.cant_rate_own_mod"),
                font=ctk.CTkFont(size=size - 5),
                text_color=state.colors["text_secondary"],
                cursor="arrow",
            ).pack(side="left")

        elif not has_downloaded:
            # Never downloaded — prompt them
            ctk.CTkLabel(
                action_row,
                text="⬇  Download this skin to leave a rating",
                font=ctk.CTkFont(size=size - 5),
                text_color=state.colors["text_secondary"],
                cursor="arrow",
            ).pack(side="left")

        elif not can_rate:
            # Downloaded but cooldown not yet passed
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            ctk.CTkLabel(
                action_row,
                text=f"⏳  You can rate this skin in {mins}:{secs:02d}",
                font=ctk.CTkFont(size=size - 5),
                text_color=state.colors["text_secondary"],
                cursor="arrow",
            ).pack(side="left")

        else:
            # Ready to rate — interactive stars
            stars_frame = ctk.CTkFrame(action_row, fg_color="transparent")
            stars_frame.pack(side="left")

            star_labels    = []
            current_stars  = [your_rating or 0]

            def _set_stars(n, permanent=False):
                for i, lbl in enumerate(star_labels):
                    lbl.configure(
                        text="★" if i < n else "☆",
                        text_color="#f5a623" if i < n else state.colors["text_secondary"],
                    )
                if permanent and message_id and connection.is_online:
                    threading.Thread(
                        target=self._submit_rating,
                        args=(skin, message_id, n, star_labels),
                        daemon=True,
                    ).start()

            for i in range(1, 6):
                filled = i <= (your_rating or 0)
                lbl = ctk.CTkLabel(
                    stars_frame,
                    text="★" if filled else "☆",
                    font=ctk.CTkFont(size=size),
                    text_color="#f5a623" if filled else state.colors["text_secondary"],
                    cursor="hand2",
                )
                lbl.pack(side="left", padx=1)
                star_labels.append(lbl)

                lbl.bind("<Enter>",    lambda e, n=i: _set_stars(n))
                lbl.bind("<Leave>",    lambda e: _set_stars(current_stars[0]))
                lbl.bind("<Button-1>", lambda e, n=i: (
                    current_stars.__setitem__(0, n), _set_stars(n, permanent=True)
                ))

            action_lbl_text = "  Change your rating" if your_rating else "  Rate this skin"
            ctk.CTkLabel(
                action_row,
                text=action_lbl_text,
                font=ctk.CTkFont(size=size - 5),
                text_color=state.colors["text_secondary"],
            ).pack(side="left", padx=(4, 0))

        return wrapper

    def _submit_rating(self, skin: dict, message_id: int, rating: int, star_labels: list):
        ok, data, err = connection.submit_rating(message_id, rating)
        if ok:
            skin["avg_rating"]   = data.get("avg_rating", rating)
            skin["rating_count"] = data.get("rating_count", 1)
            skin["your_rating"]  = rating
            self.after(0, lambda: self._notify(f"⭐ Rating submitted!", "success"))
        else:
            self.after(0, lambda e=err: self._notify(f"Rating failed: {e}", "error"))

    def _notify(self, message, type="info"):
        if self.notification_callback:
            self.notification_callback(message, type)
        else:
            print(f"[DOWNLOAD] {type.upper()}: {message}")