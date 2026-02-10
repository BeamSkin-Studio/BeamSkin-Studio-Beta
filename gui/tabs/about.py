"""
About Tab
"""
import customtkinter as ctk
import webbrowser
import threading
import time
import os
from PIL import Image
from gui.state import state


print(f"[DEBUG] Loading class: AboutTab")


class AboutTab(ctk.CTkFrame):
    """About tab showing app info and credits"""
    
    def __init__(self, parent):
    
        print(f"[DEBUG] __init__ called")
        super().__init__(parent, fg_color=state.colors["app_bg"])
        
        # Socials frame reference
        self.socials_frame = None
        
        # Load logo
        self.logo_image = self._load_logo()
        
        # Load PayPal logo
        self.paypal_logo = self._load_paypal_logo()
        
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
                # Larger logo for About page
                logo_image = ctk.CTkImage(
                    light_image=pil_image,
                    dark_image=pil_image,
                    size=(200, 200)  # Bigger than topbar logo
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
        logo_path = os.path.join("gui", "Icons", "paypal_logo.png")
        
        try:
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)
                paypal_logo = ctk.CTkImage(
                    light_image=pil_image,
                    dark_image=pil_image,
                    size=(100, 30)  # Logo size to replace button text
                )
                print(f"[DEBUG] Loaded PayPal logo from: {logo_path}")
                return paypal_logo
            else:
                print(f"[DEBUG] PayPal logo not found at: {logo_path}")
                return None
        except Exception as e:
            print(f"[DEBUG] Failed to load PayPal logo: {e}")
            return None
    
    def _setup_ui(self):
        """Set up the About tab UI"""
        # Main about frame
        about_frame = ctk.CTkFrame(self, fg_color=state.colors["frame_bg"])
        about_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Logo (replacing text title)
        if self.logo_image:
            ctk.CTkLabel(
                about_frame,
                text="",
                image=self.logo_image
            ).pack(pady=(20, 10))
        else:
            # Fallback to text if logo not found
            ctk.CTkLabel(
                about_frame,
                text="BeamSkin Studio",
                font=ctk.CTkFont(size=26, weight="bold"),
                text_color=state.colors["text"]
            ).pack(pady=(10, 5))
        
        # Credits section
        ctk.CTkLabel(
            about_frame,
            text="Credits:",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=state.colors["text"]
        ).pack(pady=(50, 5))
        
        # Developer label
        ctk.CTkLabel(
            about_frame,
            text="Developer:",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=state.colors["text"]
        ).pack(pady=(10, 0))
        
        # Socials expandable frame
        self.socials_frame = ctk.CTkFrame(about_frame, fg_color="transparent", height=0)
        self.socials_frame.pack_forget()
        
        # Developer button with toggle
        ctk.CTkButton(
            about_frame,
            text="@Burzt_YT",
            font=ctk.CTkFont(size=17, weight="bold"),
            command=self._toggle_socials,
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"]
        ).pack(pady=(2, 0))
        
        # Linktree button (inside socials frame)
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
        
        # PayPal donate button - Always visible, separate from socials
        paypal_btn = ctk.CTkButton(
            about_frame,
            text="" if self.paypal_logo else "Donate via PayPal",
            width=140,
            height=40,
            font=ctk.CTkFont(size=15),
            fg_color="#0070BA",  # PayPal blue
            hover_color="#005EA6",
            text_color="white",
            command=self._open_paypal,
            image=self.paypal_logo if self.paypal_logo else None
        )
        paypal_btn.pack(pady=(20, 10))
        
        # Version label at bottom - NOW WITH "Version:" PREFIX
        ctk.CTkLabel(
            about_frame,
            text=f"Version: {state.current_version}",
            font=ctk.CTkFont(size=14),
            text_color=state.colors["text"]
        ).pack(side="bottom", pady=(0, 10))
    
    def _toggle_socials(self):
        """Toggle the socials frame with smooth animation"""
        target_height = 45
        
        if self.socials_frame.winfo_ismapped():
            # Collapse animation
            def collapse():
                print(f"[DEBUG] collapse called")
                self.socials_frame.pack_propagate(False)
                for i in range(self.socials_frame.winfo_height(), -1, -5):
                    self.socials_frame.configure(height=max(0, i))
                    time.sleep(0.01)
                self.socials_frame.pack_forget()
            
            threading.Thread(target=collapse, daemon=True).start()
        else:
            # Expand animation
            self.socials_frame.configure(height=0)
            self.socials_frame.pack(fill="x", pady=(2, 10))
            self.socials_frame.pack_propagate(False)
            
            def expand():
            
                print(f"[DEBUG] expand called")
                for i in range(0, target_height + 2, 5):
                    self.socials_frame.configure(height=i)
                    time.sleep(0.01)
                self.socials_frame.pack_propagate(True)
            
            threading.Thread(target=expand, daemon=True).start()
    
    def _open_linktree(self):
        """Open Linktree URL and collapse socials"""
        webbrowser.open("https://linktr.ee/burzt_yt")
        self._toggle_socials()
    
    def _open_paypal(self):
        """Open PayPal donation URL"""
        webbrowser.open("https://www.paypal.com/paypalme/thedriveryt")