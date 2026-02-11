"""
Hover Preview Manager - Handles vehicle preview popups on hover
"""
from typing import Optional
import customtkinter as ctk
from PIL import Image
import os
from gui.state import state

class HoverPreviewManager:
    """Manages hover preview windows for vehicle cards"""

    def __init__(self, app: ctk.CTk, preview_overlay: ctk.CTkFrame):
        self.app = app
        self.preview_overlay = preview_overlay
        self.hover_timer: Optional[str] = None
        self.current_hover_carid: Optional[str] = None

    def show_hover_preview(self, carid: str, x: int, y: int) -> None:
        """Show preview image for vehicle INSIDE the main window"""
        print(f"[DEBUG] show_hover_preview called for carid: {carid}")
        print(f"[DEBUG] Current working directory: {os.getcwd()}")

        mouse_x = self.app.winfo_pointerx() - self.app.winfo_rootx()
        mouse_y = self.app.winfo_pointery() - self.app.winfo_rooty()
        print(f"[DEBUG] Mouse position: ({mouse_x}, {mouse_y})")

        for child in self.preview_overlay.winfo_children():
            child.destroy()

        image_path = os.path.join("imagesforgui", "vehicles", carid, "default.jpg")
        print(f"[DEBUG] Looking for image at: {image_path}")
        print(f"[DEBUG] Absolute path: {os.path.abspath(image_path)}")
        print(f"[DEBUG] Image exists: {os.path.exists(image_path)}")

        if not os.path.exists(image_path):
            print(f"[DEBUG] Image not found, trying fallback...")

            if os.path.exists("imagesforgui"):
                print(f"[DEBUG] imagesforgui exists, listing contents:")
                try:
                    print(f"[DEBUG] imagesforgui contents: {os.listdir('imagesforgui')}")
                    if os.path.exists(os.path.join("imagesforgui", "vehicles")):
                        print(f"[DEBUG] vehicles folder contents: {os.listdir(os.path.join('imagesforgui', 'vehicles'))}")
                except Exception as e:
                    print(f"[DEBUG] Error listing directories: {e}")
            else:
                print(f"[DEBUG] imagesforgui folder does NOT exist in current directory")

            fallback_path = os.path.join("imagesforgui", "common", "imagepreview", "MissingTexture.jpg")
            print(f"[DEBUG] Fallback path: {fallback_path}")
            print(f"[DEBUG] Fallback absolute path: {os.path.abspath(fallback_path)}")
            print(f"[DEBUG] Fallback exists: {os.path.exists(fallback_path)}")
            if os.path.exists(fallback_path):
                image_path = fallback_path
            else:
                print(f"[DEBUG] No fallback found, returning early")
                return

        try:
            print(f"[DEBUG] Attempting to load image: {image_path}")
            img = Image.open(image_path)
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            print(f"[DEBUG] Image loaded successfully, size: {img.size}")

            header = ctk.CTkFrame(self.preview_overlay, fg_color=state.colors["accent"], height=30, corner_radius=8)
            header.pack(fill="x", padx=2, pady=2)

            print(f"[DEBUG]   Looking up vehicle name...")
            print(f"[DEBUG]   Checking state.vehicle_ids: {carid in state.vehicle_ids}")
            print(f"[DEBUG]   Checking state.added_vehicles: {carid in state.added_vehicles}")

            vehicle_name = state.vehicle_ids.get(carid)
            if not vehicle_name:
                vehicle_name = state.added_vehicles.get(carid, carid)
                print(f"[DEBUG]   Found in added_vehicles: {vehicle_name}")
            else:
                print(f"[DEBUG]   Found in vehicle_ids: {vehicle_name}")

            header_text = f"Name: {vehicle_name} | ID: {carid}"
            print(f"[DEBUG]   Header text: {header_text}")

            ctk.CTkLabel(header, text=header_text, text_color=state.colors["accent_text"], font=("Segoe UI", 15, "bold")).pack()

            img_label = ctk.CTkLabel(self.preview_overlay, image=photo, text="")
            img_label.pack(padx=10, pady=5)

            self.app.update_idletasks()
            app_w = self.app.winfo_width()
            app_h = self.app.winfo_height()

            self.preview_overlay.update_idletasks()
            p_width = self.preview_overlay.winfo_reqwidth()
            p_height = self.preview_overlay.winfo_reqheight()
            print(f"[DEBUG] Preview dimensions: {p_width}x{p_height}, App dimensions: {app_w}x{app_h}")

            pos_x = mouse_x + 20
            if pos_x + p_width > app_w:
                pos_x = mouse_x - p_width - 20

            pos_y = mouse_y + 10
            if pos_y + p_height > app_h:
                pos_y = mouse_y - p_height - 10

            pos_x = max(10, pos_x)
            pos_y = max(10, pos_y)
            print(f"[DEBUG] Placing preview at: ({pos_x}, {pos_y})")

            self.preview_overlay.place(x=pos_x, y=pos_y)
            self.preview_overlay.lift()
            print(f"[DEBUG] Preview displayed successfully")

        except Exception as e:
            print(f"[DEBUG] Error loading image: {e}")
            import traceback
            traceback.print_exc()

    def hide_hover_preview(self, force: bool = False) -> None:
        """Hide the hover preview overlay"""
        print(f"[DEBUG] hide_hover_preview called (force={force})")
        if self.hover_timer:
            print(f"[DEBUG] Cancelling pending hover timer")
            self.app.after_cancel(self.hover_timer)
            self.hover_timer = None

        self.current_hover_carid = None
        self.preview_overlay.place_forget()
        for child in self.preview_overlay.winfo_children():
            child.destroy()

    def schedule_hover_preview(self, carid: str, widget: ctk.CTkButton) -> None:
        """Schedule a hover preview with a delay"""
        print(f"[DEBUG] schedule_hover_preview called for carid: {carid}")

        if self.hover_timer:
            print(f"[DEBUG] Cancelling previous timer")
            self.app.after_cancel(self.hover_timer)

        self.current_hover_carid = carid

        def show_after_delay():
            print(f"[DEBUG] Timer triggered, checking if still hovering: {self.current_hover_carid == carid}")
            if self.current_hover_carid == carid:
                x = widget.winfo_rootx()
                y = widget.winfo_rooty()
                print(f"[DEBUG] Calling show_hover_preview")
                self.show_hover_preview(carid, x, y)

        print(f"[DEBUG] Setting timer for 500ms")
        self.hover_timer = self.app.after(500, show_after_delay)

    def setup_robust_hover(self, widget, carid: str) -> None:
        """Set up hover events recursively for a widget and ALL its descendants"""

        def on_enter(event):

            self.schedule_hover_preview(carid, widget)

        def on_leave(event):
            self.hide_hover_preview()

        def apply_bindings(target):
            """Recursive helper to bind events to target and all its children"""
            try:

                target.bind("<Enter>", on_enter, add="+")
                target.bind("<Leave>", on_leave, add="+")
            except Exception as e:

                pass

            for child in target.winfo_children():
                apply_bindings(child)

        apply_bindings(widget)
        print(f"[DEBUG] Robust recursive hover setup complete for carid: {carid}")