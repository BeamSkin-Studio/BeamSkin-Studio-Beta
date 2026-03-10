"""
BeamSkin Studio - Changelog
============================
"""

from typing import TypedDict, Literal


# ── Entry type definitions ─────────────────────────────────────────────────── #

EntryType = Literal["title", "subtitle", "item", "note", "separator"]

class Entry(TypedDict):
    type:  EntryType
    text:  str          # empty string for separators


# ── Entry helper functions ─────────────────────────────────────────────────── #

def title(text: str) -> Entry:
    """Large bold section heading (e.g. '🚀 New Features')"""
    return {"type": "title", "text": text}

def subtitle(text: str) -> Entry:
    """Medium bold subheading"""
    return {"type": "subtitle", "text": text}

def item(text: str) -> Entry:
    """Standard bullet-point entry"""
    return {"type": "item", "text": text}

def note(text: str) -> Entry:
    """Small italic footnote / tip"""
    return {"type": "note", "text": text}

def separator() -> Entry:
    """Horizontal divider line — no text needed"""
    return {"type": "separator", "text": ""}


# ── CHANGELOG DATA ─────────────────────────────────────────────────────────── #

CHANGELOGS = [
    {
        "version": "0.7.0.Beta",
        "date": "10-03-2026",
        "entries": [
            title("🚀 New Features"),
            subtitle("Colorable Skins"),
            item("colorable skins are now supported, allowing you to create skins that can be recolored."),
            subtitle("Online Tab"),
            item("a new online tab has been added, where you can report issues, upload and download skins. It will be availbe when I have a dedicated server up and running."),
            subtitle("Language Selection"),
            item("you can now select your preferred language in the settings. download tab and changelog window has a translator button that uses GoogleTranslator that will hopefully translate to your selected language."),
            item("more languages will be added in future updates."),
            separator(),

            title("🐛 Bug Fixes"),
            subtitle("Citybus Texture Fix"),
            item("Fixed so citybus use the newly named textures"),
            separator(),
        ]
    },

    # ════════════════════════════════════════════════════════════════════════ #
    #  TEMPLATE
    # ════════════════════════════════════════════════════════════════════════ #
    # {
    #     "version": "X.Y.Z",
    #     "date": "DD-MM-YYYY",
    #     "entries": [
    #         title("🚀 New Features"),
    #         item("..."),
    #         item("..."),
    #         separator(),
    #         title("⚙️ Improvements"),
    #         subtitle("Optional sub-section label"),
    #         item("..."),
    #         separator(),
    #         title("🐛 Bug Fixes"),
    #         item("..."),
    #         separator(),
    #         note("Optional footnote or thank-you message"),
    #     ]
    # },

]


# ── Public API ─────────────────────────────────────────────────────────────── #

def get_changelog_for_version(version: str) -> dict | None:
    version = version.strip()
    for entry in CHANGELOGS:
        if entry.get("version", "").strip() == version:
            return entry
    return None
