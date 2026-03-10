"""
Changelog Dialog
=================
"""
import threading
import os
import json
import customtkinter as ctk
from gui.icon_helper import set_window_icon
from gui.state import state
from core.localization import t


# ── Translation support (mirrors online_tab.py) ───────────────────────────── #
try:
    from deep_translator import GoogleTranslator as _GTranslator
    _TRANSLATE_AVAILABLE = True
except ImportError:
    _TRANSLATE_AVAILABLE = False

_LOCALE_TO_GOOGLE: dict = {
    "en": "en", "fr": "fr", "de": "de", "es": "es",
    "it": "it", "pt": "pt", "nl": "nl", "ru": "ru",
    "pl": "pl", "cs": "cs", "sk": "sk", "hu": "hu",
    "ro": "ro", "tr": "tr", "sv": "sv", "no": "no",
    "da": "da", "fi": "fi", "el": "el", "uk": "uk",
    "zh": "zh-CN", "ja": "ja", "ko": "ko", "ar": "ar",
    "he": "iw", "hi": "hi", "th": "th", "vi": "vi",
    "id": "id", "ms": "ms",
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
    try:
        from core.localization import get_current_language
        locale = get_current_language()
        lang = _LOCALE_TO_GOOGLE.get(locale)
        if lang:
            return lang
        return locale[:2].lower()
    except Exception:
        return "en"


def _should_translate() -> bool:
    """Return True if the user's language is not English."""
    return _get_target_lang() not in ("en",)


def _translate_entries(entries: list) -> list:

    if not _TRANSLATE_AVAILABLE or not _should_translate():
        return entries

    target = _get_target_lang()
    translated = []
    for entry in entries:
        if entry["type"] == "separator" or not entry["text"].strip():
            translated.append(entry)
            continue
        try:
            text = _GTranslator(source="en", target=target).translate(entry["text"])
            translated.append({**entry, "text": text or entry["text"]})
        except Exception as e:
            print(f"[CHANGELOG] Translation failed for entry: {e}")
            translated.append(entry)
    return translated


# ── "seen versions" persistence ───────────────────────────────────────────── #

def _seen_versions_path() -> str:
    return os.path.join("data", "seen_changelogs.json")


def _load_seen_versions() -> list:
    path = _seen_versions_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[CHANGELOG] Could not load seen versions: {e}")
    return []


def _mark_version_seen(version: str):
    path = _seen_versions_path()
    seen = _load_seen_versions()
    if version not in seen:
        seen.append(version)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(seen, f)
    except Exception as e:
        print(f"[CHANGELOG] Could not save seen versions: {e}")


def has_seen_changelog(version: str) -> bool:
    return version in _load_seen_versions()


# ── Main dialog ───────────────────────────────────────────────────────────── #

class ChangelogDialog:

    def __init__(self, parent, changelog_data: dict):
        self._parent      = parent
        self._data        = changelog_data
        self._entries     = list(changelog_data.get("entries", []))
        self._version     = changelog_data.get("version", "?")
        self._date        = changelog_data.get("date", "")
        self._translating = False

        self._build_window()
        self._render_entries(self._entries)

    # ── Window skeleton ───────────────────────────────────────────────────── #

    def _build_window(self):
        dlg = ctk.CTkToplevel(self._parent)
        self._dlg = dlg
        set_window_icon(dlg)
        dlg.title(f"What's New — v{self._version}")
        dlg.geometry("640x620")
        dlg.resizable(False, True)
        dlg.configure(fg_color=state.colors["app_bg"])
        dlg.transient(self._parent)
        dlg.grab_set()

        dlg.update_idletasks()
        px = self._parent.winfo_x() + (self._parent.winfo_width()  // 2) - 320
        py = self._parent.winfo_y() + (self._parent.winfo_height() // 2) - 310
        dlg.geometry(f"640x620+{px}+{py}")
        dlg.lift()
        dlg.focus_force()

        # ── Header ────────────────────────────────────────────────────────── #
        header = ctk.CTkFrame(dlg, fg_color=state.colors["card_bg"], corner_radius=0)
        header.pack(fill="x")

        inner_h = ctk.CTkFrame(header, fg_color="transparent")
        inner_h.pack(fill="x", padx=24, pady=18)

        ctk.CTkLabel(
            inner_h,
            text="🎉",
            font=ctk.CTkFont(size=32),
        ).pack(side="left", padx=(0, 12))

        text_col = ctk.CTkFrame(inner_h, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_col,
            text=t("changelog.title", default="What's New"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=state.colors["text"],
            anchor="w",
        ).pack(anchor="w")

        subtitle_text = f"Version {self._version}"
        if self._date:
            subtitle_text += f"  ·  {self._date}"

        ctk.CTkLabel(
            text_col,
            text=subtitle_text,
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text_secondary"],
            anchor="w",
        ).pack(anchor="w")

        # ── Translate button (top-right of header) ────────────────────────── #
        if _TRANSLATE_AVAILABLE and _should_translate():
            self._translate_btn = ctk.CTkButton(
                inner_h,
                text="🌐 " + t("changelog.translate", default="Translate"),
                command=self._on_translate,
                width=120,
                height=32,
                fg_color=state.colors["accent"],
                hover_color=state.colors["accent_hover"],
                text_color=state.colors["accent_text"],
                font=ctk.CTkFont(size=12, weight="bold"),
                corner_radius=8,
            )
            self._translate_btn.pack(side="right")
        else:
            self._translate_btn = None

        # ── Scrollable content area ───────────────────────────────────────── #
        self._scroll = ctk.CTkScrollableFrame(
            dlg,
            fg_color=state.colors["frame_bg"],
            corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True)

        # ── Footer ────────────────────────────────────────────────────────── #
        footer = ctk.CTkFrame(dlg, fg_color=state.colors["card_bg"], corner_radius=0, height=64)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        ctk.CTkButton(
            footer,
            text=t("changelog.close", default="Got it! 🎉"),
            command=self._on_close,
            width=160,
            height=38,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10,
        ).place(relx=0.5, rely=0.5, anchor="center")

        dlg.bind("<Escape>", lambda _: self._on_close())

    # ── Rendering ─────────────────────────────────────────────────────────── #

    def _clear_content(self):
        for widget in self._scroll.winfo_children():
            widget.destroy()

    def _render_entries(self, entries: list):
        self._clear_content()
        pad_x = 24

        for entry in entries:
            etype = entry.get("type", "item")
            text  = entry.get("text", "")

            if etype == "separator":
                sep = ctk.CTkFrame(
                    self._scroll,
                    height=1,
                    fg_color=state.colors["border"],
                )
                sep.pack(fill="x", padx=pad_x, pady=10)

            elif etype == "title":
                ctk.CTkLabel(
                    self._scroll,
                    text=text,
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=state.colors["text"],
                    anchor="w",
                    justify="left",
                    wraplength=570,
                ).pack(fill="x", padx=pad_x, pady=(14, 4))

            elif etype == "subtitle":
                ctk.CTkLabel(
                    self._scroll,
                    text=text,
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=state.colors["text_secondary"],
                    anchor="w",
                    justify="left",
                    wraplength=570,
                ).pack(fill="x", padx=pad_x + 8, pady=(8, 2))

            elif etype == "item":
                row = ctk.CTkFrame(self._scroll, fg_color="transparent")
                row.pack(fill="x", padx=pad_x, pady=2)

                ctk.CTkLabel(
                    row,
                    text="•",
                    font=ctk.CTkFont(size=14),
                    text_color=state.colors["accent"],
                    width=18,
                    anchor="n",
                ).pack(side="left", anchor="n", padx=(8, 0), pady=(3, 0))

                ctk.CTkLabel(
                    row,
                    text=text,
                    font=ctk.CTkFont(size=13),
                    text_color=state.colors["text"],
                    anchor="w",
                    justify="left",
                    wraplength=520,
                ).pack(side="left", fill="x", expand=True, padx=(6, 0))

            elif etype == "note":
                note_frame = ctk.CTkFrame(
                    self._scroll,
                    fg_color=state.colors["card_bg"],
                    corner_radius=8,
                )
                note_frame.pack(fill="x", padx=pad_x, pady=(8, 4))

                ctk.CTkLabel(
                    note_frame,
                    text="💡  " + text,
                    font=ctk.CTkFont(size=12),
                    text_color=state.colors["text_secondary"],
                    anchor="w",
                    justify="left",
                    wraplength=540,
                ).pack(fill="x", padx=14, pady=10)

        # Bottom padding
        ctk.CTkFrame(self._scroll, fg_color="transparent", height=16).pack()

    # ── Translation ───────────────────────────────────────────────────────── #

    def _on_translate(self):
        if self._translating:
            return
        self._translating = True

        if self._translate_btn:
            self._translate_btn.configure(
                text="⏳ " + t("changelog.translating", default="Translating…"),
                state="disabled",
            )

        def _worker():
            translated = _translate_entries(self._entries)
            self._dlg.after(0, lambda: self._apply_translation(translated))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_translation(self, translated_entries: list):
        self._render_entries(translated_entries)
        self._translating = False
        if self._translate_btn:
            self._translate_btn.configure(
                text="✓ " + t("changelog.translated", default="Translated"),
                state="disabled",
            )

    # ── Close ─────────────────────────────────────────────────────────────── #

    def _on_close(self):
        _mark_version_seen(self._version)
        self._dlg.destroy()

    def show(self):
        """Block until the dialog is closed."""
        self._dlg.wait_window()


# ── Public helper ─────────────────────────────────────────────────────────── #

def show_changelog_if_needed(parent, version: str, *, force: bool = False) -> bool:
    from core.changelog import get_changelog_for_version

    if not force and has_seen_changelog(version):
        print(f"[CHANGELOG] Already seen v{version} — skipping")
        return False

    data = get_changelog_for_version(version)
    if data is None:
        print(f"[CHANGELOG] No changelog entry found for v{version} — skipping")
        _mark_version_seen(version)
        return False

    print(f"[CHANGELOG] Showing changelog for v{version}")
    dlg = ChangelogDialog(parent, data)
    dlg.show()
    return True
