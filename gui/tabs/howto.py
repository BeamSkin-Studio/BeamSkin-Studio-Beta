"""
How To Tab - Professional Documentation Interface
"""
import customtkinter as ctk
from typing import Dict, Tuple, List
from gui.state import state
from core.localization import t

class HowToTab(ctk.CTkFrame):
    """Professional documentation tab with comprehensive BeamSkin Studio guide"""

    def __init__(self, parent: ctk.CTk):
        super().__init__(parent, fg_color=state.colors["app_bg"])

        self.content_textbox: ctk.CTkTextbox = None
        self.search_entry: ctk.CTkEntry = None
        self.chapter_buttons: List[Tuple[ctk.CTkButton, str]] = []
        self.current_chapter: str = "all"

        self._setup_ui()
        self.load_all_chapters()  # Load content on startup
        
    def _get_chapters(self):
        """Get chapters with translated titles and content"""
        return {
            "getting_started": {
                "icon": "🚀",
                "title": t("howto.chapter_getting_started"),
                "content": t("howto_content.getting_started_content")
            },
            "skin_creation": {
                "icon": "🎨",
                "title": t("howto.chapter_skin_creation"),
                "content": t("howto_content.skin_creation_content")
            },
            "project": {
                "icon": "⚙️",
                "title": t("howto.chapter_project"),
                "content": t("howto_content.project_content")
            },
            "car_list": {
                "icon": "🚗",
                "title": t("howto.chapter_car_list"),
                "content": t("howto_content.car_list_content")
            },
            "add_vehicle": {
                "icon": "➕",
                "title": t("howto.chapter_add_vehicle"),
                "content": t("howto_content.add_vehicle_content")
            },
            "troubleshooting": {
                "icon": "🔍",
                "title": t("howto.chapter_troubleshooting"),
                "content": t("howto_content.troubleshooting_content")
            },
            "advanced": {
                "icon": "⚡",
                "title": t("howto.chapter_advanced"),
                "content": t("howto_content.advanced_content")
            },
            "faq": {
                "icon": "❓",
                "title": t("howto.chapter_faq"),
                "content": t("howto_content.faq_content")
            }
        }

    def refresh_ui(self):
        """Refresh all UI text with current language"""
        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()
        
        # Recreate UI with new translations
        self._setup_ui()
        self.load_all_chapters()

    def _setup_ui(self):
        """Set up the modern How-To tab UI"""

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        header_frame = ctk.CTkFrame(
            main_container,
            fg_color=state.colors["frame_bg"],
            corner_radius=12,
            height=80
        )
        header_frame.pack(fill="x", pady=(0, 15))
        header_frame.pack_propagate(False)

        title_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_container.pack(side="left", padx=20, pady=15)

        ctk.CTkLabel(
            title_container,
            text=t("howto.page_title"),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_container,
            text=t("howto.page_subtitle"),
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(anchor="w", pady=(5, 0))

        search_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        search_container.pack(side="right", padx=20, pady=15)

        ctk.CTkLabel(
            search_container,
            text="🔍",
            font=ctk.CTkFont(size=18),
            text_color=state.colors["text_secondary"]
        ).pack(side="left", padx=(0, 8))

        self.search_entry = ctk.CTkEntry(
            search_container,
            placeholder_text=t("howto.search_placeholder"),
            width=250,
            height=35,
            font=ctk.CTkFont(size=13),
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"]
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Return>", lambda e: self._search_content())

        nav_frame = ctk.CTkFrame(
            main_container,
            fg_color=state.colors["frame_bg"],
            corner_radius=12
        )
        nav_frame.pack(fill="x", pady=(0, 15))

        self.view_all_btn = ctk.CTkButton(
            nav_frame,
            text=t("howto.view_all"),
            command=self.load_all_chapters,
            width=130,
            height=40,
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent_hover"],
            text_color=state.colors["accent_text"],
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8
        )
        self.view_all_btn.pack(side="left", padx=10, pady=10)

        chapters_container = ctk.CTkFrame(nav_frame, fg_color="transparent")
        chapters_container.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=10)

        chapters = self._get_chapters()
        for chapter_key, chapter_data in chapters.items():
            btn = ctk.CTkButton(
                chapters_container,
                text=f"{chapter_data['icon']} {chapter_data['title']}",
                command=lambda k=chapter_key: self.load_chapter(k),
                width=145,
                height=40,
                fg_color=state.colors["card_bg"],
                hover_color=state.colors["card_hover"],
                text_color=state.colors["text"],
                font=ctk.CTkFont(size=12, weight="bold"),
                corner_radius=8
            )
            btn.pack(side="left", padx=3)
            self.chapter_buttons.append((btn, chapter_key))

        content_frame = ctk.CTkFrame(
            main_container,
            fg_color=state.colors["frame_bg"],
            corner_radius=12
        )
        content_frame.pack(fill="both", expand=True)

        self.content_textbox = ctk.CTkTextbox(
            content_frame,
            font=ctk.CTkFont(size=14),
            fg_color=state.colors["frame_bg"],
            text_color=state.colors["text"],
            wrap="word",
            activate_scrollbars=True
        )
        self.content_textbox.pack(fill="both", expand=True, padx=15, pady=15)

    def _search_content(self):
        """Search through documentation content"""
        search_term = self.search_entry.get().lower().strip()

        if not search_term:
            self.load_all_chapters()
            return

        chapters = self._get_chapters()
        results = []
        for chapter_key, chapter_data in chapters.items():
            content = chapter_data['content'].lower()
            if search_term in content:
                results.append((chapter_key, chapter_data))

        self.content_textbox.configure(state="normal")
        self.content_textbox.delete("0.0", "end")

        if results:
            self.content_textbox.insert("0.0", t("howto.search_results", term=search_term) + "\n")
            self.content_textbox.insert("end", "=" * 60 + "\n\n")

            for chapter_key, chapter_data in results:
                self.content_textbox.insert("end", f"{chapter_data['icon']} {chapter_data['title']}\n")
                self.content_textbox.insert("end", "-" * 60 + "\n")
                self.content_textbox.insert("end", chapter_data['content'])
                self.content_textbox.insert("end", "\n\n")
        else:
            self.content_textbox.insert("0.0", t("howto.no_results", term=search_term) + "\n\n")
            self.content_textbox.insert("end", t("howto.try_different"))

        self.content_textbox.configure(state="disabled")

        self.view_all_btn.configure(
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["tab_unselected_hover"],
            text_color=state.colors["text"]
        )

        self._reset_button_colors()

    def load_chapter(self, chapter_key: str):
        """Load a specific chapter"""
        chapters = self._get_chapters()
        if chapter_key not in chapters:
            return

        chapter_data = chapters[chapter_key]
        self.current_chapter = chapter_key

        self.content_textbox.configure(state="normal")
        self.content_textbox.delete("0.0", "end")

        self.content_textbox.insert("0.0", f"{chapter_data['icon']} {chapter_data['title']}\n")
        self.content_textbox.insert("end", "=" * 60 + "\n\n")

        self.content_textbox.insert("end", chapter_data['content'])

        self.content_textbox.configure(state="disabled")

        self.view_all_btn.configure(
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["tab_unselected_hover"],
            text_color=state.colors["text"]
        )

        for btn, key in self.chapter_buttons:
            if key == chapter_key:
                btn.configure(
                    fg_color=state.colors["accent"],
                    hover_color=state.colors["tab_selected_hover"],
                    text_color=state.colors["accent_text"]
                )
            else:
                btn.configure(
                    fg_color=state.colors["card_bg"],
                    hover_color=state.colors["tab_unselected_hover"],
                    text_color=state.colors["text"]
                )

        print(f"[DEBUG] Loaded chapter: {chapter_data['title']}")

    def load_all_chapters(self):
        """Load all chapters in sequence"""
        self.current_chapter = "all"

        self.content_textbox.configure(state="normal")
        self.content_textbox.delete("0.0", "end")

        intro_text = t("howto.welcome_title") + "\n\n"
        intro_text += t("howto.welcome_intro") + "\n\n"
        intro_text += t("howto.quick_nav_title") + "\n"
        intro_text += t("howto.quick_nav_chapters") + "\n"
        intro_text += t("howto.quick_nav_search") + "\n"
        intro_text += t("howto.quick_nav_walkthrough") + "\n\n"
        intro_text += t("howto.lets_start") + "\n\n"

        self.content_textbox.insert("0.0", intro_text)
        self.content_textbox.insert("end", "=" * 60 + "\n\n")

        chapters = self._get_chapters()
        for chapter_key, chapter_data in chapters.items():
            self.content_textbox.insert("end", f"{chapter_data['icon']} {chapter_data['title']}\n")
            self.content_textbox.insert("end", "-" * 60 + "\n")
            self.content_textbox.insert("end", chapter_data['content'])
            self.content_textbox.insert("end", "\n\n")

        self.content_textbox.configure(state="disabled")

        self.view_all_btn.configure(
            fg_color=state.colors["accent"],
            hover_color=state.colors["tab_selected_hover"],
            text_color=state.colors["accent_text"]
        )

        self._reset_button_colors()

        print("[DEBUG] Loaded all chapters")

    def _reset_button_colors(self):
        """Reset all chapter buttons to default colors"""
        for btn, _ in self.chapter_buttons:
            btn.configure(
                fg_color=state.colors["card_bg"],
                hover_color=state.colors["tab_unselected_hover"],
                text_color=state.colors["text"]
            )