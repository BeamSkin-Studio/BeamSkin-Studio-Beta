"""
About Tab - Localized version
"""
import customtkinter as ctk
import webbrowser
import threading
import time
import os
import json
from PIL import Image
from gui.state import state
from core.localization import t

print(f"[DEBUG] Loading class: AboutTab")

# ---------------------------------------------------------------------------
# Language file discovery
# ---------------------------------------------------------------------------

# Adjust this path if your locale files live elsewhere (e.g. "languages", "i18n")
_LOCALES_DIR = os.path.join("core", "localization", "languages")


def _scan_translators() -> str:
    """
    Scan every *.json file in the locales directory and collect:
        _meta.contributors  – list of contributor names
        _meta.name          – English/fallback name of the language

    The language name that is actually displayed is resolved in this order:
        1. A "language_names" dict in the *current* locale, keyed by the
           contributor file's _meta.flag  (e.g.  "language_names": {"SE": "Swedish", "DE": "German"})
        2. The _meta.name field from the contributor's own file
        3. The _meta.native_name field as a last resort

    Returns a newline-separated string ready for the label, e.g.:
        Burzt_YT - Swedish
        Joel - German
        Claude - English (US)
    """
    if not os.path.isdir(_LOCALES_DIR):
        print(f"[DEBUG] Locales directory not found: {_LOCALES_DIR}")
        return t("about.translators_list")   # graceful fallback to static key

    # ------------------------------------------------------------------
    # Load the current locale's language_names lookup (optional feature).
    # If a locale file contains  "language_names": {"SE": "Swedish", …}
    # we use those translated names; otherwise we fall back to each
    # file's own _meta.name.
    # ------------------------------------------------------------------
    current_lang_names: dict = {}
    try:
        current_locale_path = _get_current_locale_path()
        if current_locale_path and os.path.isfile(current_locale_path):
            with open(current_locale_path, "r", encoding="utf-8") as f:
                current_data = json.load(f)
            current_lang_names = current_data.get("language_names", {})
    except Exception as e:
        print(f"[DEBUG] Could not load language_names from current locale: {e}")

    # ------------------------------------------------------------------
    # Walk every JSON file and collect (contributor, language_display_name)
    # ------------------------------------------------------------------
    entries: list[str] = []
    seen: set[str] = set()   # avoid duplicate "Contributor - Language" lines

    for filename in sorted(os.listdir(_LOCALES_DIR)):
        if not filename.lower().endswith(".json"):
            continue

        filepath = os.path.join(_LOCALES_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[DEBUG] Skipping {filename}: {e}")
            continue

        meta: dict = data.get("_meta", {})
        contributors: list = meta.get("contributors", [])
        flag: str = meta.get("flag", "")

        # Resolve display name for this language
        if flag and flag in current_lang_names:
            lang_display = current_lang_names[flag]
        elif meta.get("name"):
            lang_display = meta["name"]
        elif meta.get("native_name"):
            lang_display = meta["native_name"]
        else:
            lang_display = filename.replace(".json", "")

        for contributor in contributors:
            line = f"{contributor} - {lang_display}"
            if line not in seen:
                seen.add(line)
                entries.append(line)

    if not entries:
        # Nothing found – fall back to the static translation key
        return t("about.translators_list")

    return "\n".join(entries)


def _get_current_locale_path() -> str | None:
    """
    Try to find the path of the currently active locale file.
    Checks state for a stored path or language code, then searches _LOCALES_DIR.
    """
    # Option A: state stores the path directly
    for attr in ("locale_path", "language_path", "current_locale_path"):
        path = getattr(state, attr, None)
        if path and os.path.isfile(path):
            return path

    # Option B: state stores a language code / flag like "US", "SE", "en_us"
    for attr in ("language", "current_language", "locale", "lang_code"):
        code = getattr(state, attr, None)
        if code:
            # Try exact filename match first, then partial match
            for filename in os.listdir(_LOCALES_DIR):
                if not filename.lower().endswith(".json"):
                    continue
                stem = os.path.splitext(filename)[0].lower()
                if stem == code.lower() or stem.replace("_", "").replace("-", "") == code.lower().replace("_", "").replace("-", ""):
                    return os.path.join(_LOCALES_DIR, filename)

    return None


# ---------------------------------------------------------------------------
# Tab class
# ---------------------------------------------------------------------------

class AboutTab(ctk.CTkFrame):
    """About tab showing app info and credits"""

    def __init__(self, parent):
        print(f"[DEBUG] __init__ called")
        super().__init__(parent, fg_color=state.colors["app_bg"])

        self.socials_frame = None
        self.payment_overlay = None
        self.logo_image = self._load_logo()
        self.paypal_logo = self._load_paypal_logo()
        self.swish_logo = self._load_swish_logo()
        self.patreon_logo = self._load_patreon_logo()
        
        self._setup_ui()

    def _load_logo(self):
        """Load the BeamSkin Studio logo based on current theme"""
        icon_dir = os.path.join("gui", "Icons")

        if state.current_theme == "dark":
            logo_path = os.path.join(icon_dir, "BeamSkin_Studio_White.png")
        else:
            logo_path = os.path.join(icon_dir, "BeamSkin_Studio_Black.png")

        try:
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)
                logo_image = ctk.CTkImage(
                    light_image=pil_image,
                    dark_image=pil_image,
                    size=(200, 200)
                )
                print(f"[DEBUG] Loaded About tab logo from: {logo_path}")
                return logo_image
            else:
                print(f"[DEBUG] Logo not found at: {logo_path}")
                return None
        except Exception as e:
            print(f"[DEBUG] Failed to load About tab logo: {e}")
            return None

    def _load_paypal_logo(self):
        """Load the PayPal logo"""
        logo_path = os.path.join("gui", "Icons", "paypal_P_logo.png")

        try:
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)
                paypal_logo = ctk.CTkImage(
                    light_image=pil_image,
                    dark_image=pil_image,
                    size=(30, 30)
                )
                print(f"[DEBUG] Loaded PayPal logo from: {logo_path}")
                return paypal_logo
            else:
                print(f"[DEBUG] PayPal logo not found at: {logo_path}")
                return None
        except Exception as e:
            print(f"[DEBUG] Failed to load PayPal logo: {e}")
            return None

    def _load_swish_logo(self):
        """Load the Swish logo"""
        logo_path = os.path.join("gui", "Icons", "Swish_logo.png")

        try:
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)
                swish_logo = ctk.CTkImage(
                    light_image=pil_image,
                    dark_image=pil_image,
                    size=(30, 30)
                )
                print(f"[DEBUG] Loaded Swish logo from: {logo_path}")
                return swish_logo
            else:
                print(f"[DEBUG] Swish logo not found at: {logo_path}")
                return None
        except Exception as e:
            print(f"[DEBUG] Failed to load Swish logo: {e}")
            return None

    def _load_patreon_logo(self):
        """Load the Patreon logo"""
        logo_path = os.path.join("gui", "Icons", "Patreon_Logo.png")

        try:
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)
                patreon_logo = ctk.CTkImage(
                    light_image=pil_image,
                    dark_image=pil_image,
                    size=(180, 37)
                )
                print(f"[DEBUG] Loaded Patreon logo from: {logo_path}")
                return patreon_logo
            else:
                print(f"[DEBUG] Patreon logo not found at: {logo_path}")
                return None
        except Exception as e:
            print(f"[DEBUG] Failed to load Patreon logo: {e}")
            return None

    def refresh_ui(self):
        """Refresh all UI text with current language"""
        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()
        
        # Recreate UI with new translations
        self._setup_ui()

    def _setup_ui(self):
        """Set up the About tab UI"""
        about_frame = ctk.CTkFrame(self, fg_color=state.colors["frame_bg"])
        about_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Content frame for top elements
        content_frame = ctk.CTkFrame(about_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True)

        if self.logo_image:
            ctk.CTkLabel(
                content_frame,
                text="",
                image=self.logo_image
            ).pack(pady=(20, 10))
        else:
            # Fallback to text title
            ctk.CTkLabel(
                content_frame,
                text=t("about.title"),
                font=ctk.CTkFont(size=26, weight="bold"),
                text_color=state.colors["text"]
            ).pack(pady=(10, 5))

        ctk.CTkLabel(
            content_frame,
            text=t("about.credits"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=state.colors["text"]
        ).pack(pady=(50, 5))

        ctk.CTkLabel(
            content_frame,
            text=t("about.developer"),
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=state.colors["text"]
        ).pack(pady=(10, 0))

        self.socials_frame = ctk.CTkFrame(content_frame, fg_color="transparent", height=0)
        self.socials_frame.pack_forget()

        ctk.CTkButton(
            content_frame,
            text="@Burzt_YT",
            font=ctk.CTkFont(size=17, weight="bold"),
            command=self._toggle_socials,
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"]
        ).pack(pady=(2, 0))

        ctk.CTkButton(
            self.socials_frame,
            text="Linktree",
            width=120,
            font=ctk.CTkFont(size=15),
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            command=self._open_linktree
        ).pack(pady=5)

        # Translators section — built automatically from all locale files
        ctk.CTkLabel(
            content_frame,
            text=t("about.translators"),
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=state.colors["text"]
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            content_frame,
            text=_scan_translators(),
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=state.colors["text"],
            justify="center"
        ).pack(pady=(0, 10))

        # Version at bottom
        ctk.CTkLabel(
            about_frame,
            text=t("about.version", version=state.current_version),
            font=ctk.CTkFont(size=14),
            text_color=state.colors["text"]
        ).pack(side="bottom", pady=(0, 10))

        # Donate button at bottom
        donate_btn = ctk.CTkButton(
            about_frame,
            text=t("about.donate"),
            width=140,
            height=40,
            font=ctk.CTkFont(size=25, weight="bold"),
            fg_color="#0070BA",
            hover_color="#005EA6",
            text_color="white",
            command=self._show_payment_options
        )
        donate_btn.pack(side="bottom", pady=(10, 10))

    def _show_payment_options(self):
        """Show payment options overlay"""
        if self.payment_overlay is not None:
            return  # Already showing
        
        # Create semi-transparent background overlay
        self.payment_overlay = ctk.CTkFrame(
            self,
            fg_color=("gray80", "gray20"),
            bg_color="transparent"
        )
        self.payment_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Bind click on overlay background to close
        self.payment_overlay.bind("<Button-1>", lambda e: self._close_payment_options())
        
        # Create centered dialog frame
        dialog = ctk.CTkFrame(
            self.payment_overlay,
            fg_color=state.colors["frame_bg"],
            border_width=2,
            border_color=state.colors["accent"]
        )
        dialog.place(relx=0.5, rely=0.5, anchor="center")
        
        # Prevent clicks on dialog from closing overlay
        dialog.bind("<Button-1>", lambda e: "break")
        
        # Title
        ctk.CTkLabel(
            dialog,
            text=t("about.select_payment_method"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=state.colors["text"]
        ).pack(pady=(20, 15), padx=40)
        
        # PayPal button
        ctk.CTkButton(
            dialog,
            text="PayPal",
            width=200,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#0070BA",
            hover_color="#005EA6",
            text_color="white",
            image=self.paypal_logo if self.paypal_logo else None,
            compound="left",
            command=self._open_paypal
        ).pack(pady=8, padx=40)
        
        # Swish button
        ctk.CTkButton(
            dialog,
            text="Swish",
            width=200,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#7BDC3D",
            hover_color="#6BC935",
            text_color="white",
            image=self.swish_logo if self.swish_logo else None,
            compound="left",
            command=self._open_swish
        ).pack(pady=8, padx=40)

        # Divider label for monthly support section
        ctk.CTkLabel(
            dialog,
            text=t("about.monthly"),
            font=ctk.CTkFont(size=12),
            text_color=state.colors["text"]
        ).pack(pady=(10, 4), padx=40)

        # Patreon button
        ctk.CTkButton(
            dialog,
            text="",
            width=200,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#F96854",
            hover_color="#E05A48",
            text_color="white",
            image=self.patreon_logo if self.patreon_logo else None,
            compound="left",
            command=self._open_patreon
        ).pack(pady=(0, 8), padx=40)
        
        # Close button
        ctk.CTkButton(
            dialog,
            text=t("about.cancel") if hasattr(t("about.cancel"), '__call__') else "Cancel",
            width=200,
            height=35,
            font=ctk.CTkFont(size=14),
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"],
            command=self._close_payment_options
        ).pack(pady=(5, 20), padx=40)

    def _close_payment_options(self):
        """Close payment options overlay"""
        if self.payment_overlay is not None:
            self.payment_overlay.destroy()
            self.payment_overlay = None

    def _open_paypal(self):
        """Open PayPal donation URL and close overlay"""
        webbrowser.open("https://www.paypal.com/paypalme/thedriveryt")
        self._close_payment_options()

    def _open_swish(self):
        """Open Swish donation URL and close overlay"""
        webbrowser.open("https://imgur.com/a/lI2y6tj")
        self._close_payment_options()

    def _open_patreon(self):
        """Open Patreon page URL and close overlay"""
        webbrowser.open("https://www.patreon.com/BURZT_YT")
        self._close_payment_options()

    def _toggle_socials(self):
        """Toggle the socials frame with smooth animation"""
        target_height = 45

        if self.socials_frame.winfo_ismapped():
            # Collapse
            def collapse():
                self.socials_frame.pack_propagate(False)
                for i in range(self.socials_frame.winfo_height(), -1, -5):
                    self.socials_frame.configure(height=max(0, i))
                    time.sleep(0.01)
                self.socials_frame.pack_forget()

            threading.Thread(target=collapse, daemon=True).start()
        else:
            # Expand
            self.socials_frame.configure(height=0)
            self.socials_frame.pack(fill="x", pady=(2, 10))
            self.socials_frame.pack_propagate(False)

            def expand():
                for i in range(0, target_height + 2, 5):
                    self.socials_frame.configure(height=i)
                    time.sleep(0.01)
                self.socials_frame.pack_propagate(True)

            threading.Thread(target=expand, daemon=True).start()

    def _open_linktree(self):
        """Open Linktree URL and collapse socials"""
        webbrowser.open("https://linktr.ee/burzt_yt")
        self._toggle_socials()