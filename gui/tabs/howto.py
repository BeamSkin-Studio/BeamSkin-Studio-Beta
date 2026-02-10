"""
How To Tab - Professional Documentation Interface
"""
import customtkinter as ctk
from typing import Dict, Tuple, List
from gui.state import state


class HowToTab(ctk.CTkFrame):
    """Professional documentation tab with comprehensive BeamSkin Studio guide"""
    
    def __init__(self, parent: ctk.CTk):
        super().__init__(parent, fg_color=state.colors["app_bg"])
        
        # UI references
        self.content_textbox: ctk.CTkTextbox = None
        self.search_entry: ctk.CTkEntry = None
        self.chapter_buttons: List[Tuple[ctk.CTkButton, str]] = []
        self.current_chapter: str = "all"
        
        # Enhanced chapter structure with icons and better organization
        self.chapters = {
            "getting_started": {
                "icon": "🚀",
                "title": "Getting Started",
                "content": self._chapter_getting_started()
            },
            "skin_creation": {
                "icon": "🎨",
                "title": "Creating Skins",
                "content": self._chapter_skin_creation()
            },
            "project": {
                "icon": "⚙️",
                "title": "Project Tab",
                "content": self._chapter_project()
            },
            "car_list": {
                "icon": "🚗",
                "title": "Car List",
                "content": self._chapter_car_list()
            },
            "add_vehicle": {
                "icon": "➕",
                "title": "Add Vehicle",
                "content": self._chapter_add_vehicle()
            },
            "troubleshooting": {
                "icon": "🔍",
                "title": "Troubleshooting",
                "content": self._chapter_troubleshooting()
            },
            "advanced": {
                "icon": "⚡",
                "title": "Advanced Topics",
                "content": self._chapter_advanced()
            },
            "faq": {
                "icon": "❓",
                "title": "FAQ",
                "content": self._chapter_faq()
            }
        }
        
        self._setup_ui()
        self.load_all_chapters()  # Load all chapters by default
    
    def _setup_ui(self):
        """Set up the modern How-To tab UI"""
        # Main container
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header section
        header_frame = ctk.CTkFrame(
            main_container,
            fg_color=state.colors["frame_bg"],
            corner_radius=12,
            height=80
        )
        header_frame.pack(fill="x", pady=(0, 15))
        header_frame.pack_propagate(False)
        
        # Title and description
        title_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_container.pack(side="left", padx=20, pady=15)
        
        ctk.CTkLabel(
            title_container,
            text="📚 How to Use BeamSkin Studio",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=state.colors["text"],
            anchor="w"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            title_container,
            text="Complete guide to creating and managing vehicle skins for BeamNG.drive",
            font=ctk.CTkFont(size=13),
            text_color=state.colors["text_secondary"],
            anchor="w"
        ).pack(anchor="w", pady=(5, 0))
        
        # Search box in header
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
            placeholder_text="Search documentation...",
            width=250,
            height=35,
            font=ctk.CTkFont(size=13),
            fg_color=state.colors["card_bg"],
            border_color=state.colors["border"]
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Return>", lambda e: self._search_content())
        
        # Navigation frame with chapter buttons
        nav_frame = ctk.CTkFrame(
            main_container,
            fg_color=state.colors["frame_bg"],
            corner_radius=12
        )
        nav_frame.pack(fill="x", pady=(0, 15))
        
        # "View All" button
        self.view_all_btn = ctk.CTkButton(
            nav_frame,
            text="📖 View All",
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
        
        # Chapter navigation buttons
        chapters_container = ctk.CTkFrame(nav_frame, fg_color="transparent")
        chapters_container.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=10)
        
        for chapter_key, chapter_data in self.chapters.items():
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
        
        # Content area with scrollable textbox
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
        
        # Search through all chapters
        results = []
        for chapter_key, chapter_data in self.chapters.items():
            content = chapter_data['content'].lower()
            if search_term in content:
                results.append((chapter_key, chapter_data))
        
        # Display results
        self.content_textbox.configure(state="normal")
        self.content_textbox.delete("0.0", "end")
        
        if results:
            self.content_textbox.insert("0.0", f"🔍 Search Results for '{search_term}'\n")
            self.content_textbox.insert("end", "=" * 60 + "\n\n")
            
            for chapter_key, chapter_data in results:
                self.content_textbox.insert("end", f"{chapter_data['icon']} {chapter_data['title']}\n")
                self.content_textbox.insert("end", "-" * 60 + "\n")
                self.content_textbox.insert("end", chapter_data['content'])
                self.content_textbox.insert("end", "\n\n")
        else:
            self.content_textbox.insert("0.0", f"❌ No results found for '{search_term}'\n\n")
            self.content_textbox.insert("end", "Try different keywords or browse chapters above.")
        
        self.content_textbox.configure(state="disabled")
        
        # Reset View All button when showing search results
        self.view_all_btn.configure(
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"]
        )
        
        # Reset all chapter buttons
        self._reset_button_colors()
    
    def load_chapter(self, chapter_key: str):
        """Load a specific chapter"""
        if chapter_key not in self.chapters:
            return
        
        chapter_data = self.chapters[chapter_key]
        self.current_chapter = chapter_key
        
        # Update content
        self.content_textbox.configure(state="normal")
        self.content_textbox.delete("0.0", "end")
        
        # Chapter header
        self.content_textbox.insert("0.0", f"{chapter_data['icon']} {chapter_data['title']}\n")
        self.content_textbox.insert("end", "=" * 60 + "\n\n")
        
        # Chapter content
        self.content_textbox.insert("end", chapter_data['content'])
        
        self.content_textbox.configure(state="disabled")
        
        # Reset View All button since we're viewing a specific chapter
        self.view_all_btn.configure(
            fg_color=state.colors["card_bg"],
            hover_color=state.colors["card_hover"],
            text_color=state.colors["text"]
        )
        
        # Update button states
        for btn, key in self.chapter_buttons:
            if key == chapter_key:
                # Selected button: accent color with no hover effect
                btn.configure(
                    fg_color=state.colors["accent"],
                    hover_color=state.colors["accent"],  # Same as fg_color to disable hover
                    text_color=state.colors["accent_text"]
                )
            else:
                # Unselected buttons: normal state with hover
                btn.configure(
                    fg_color=state.colors["card_bg"],
                    hover_color=state.colors["card_hover"],
                    text_color=state.colors["text"]
                )
        
        print(f"[DEBUG] Loaded chapter: {chapter_data['title']}")
    
    def load_all_chapters(self):
        """Load all chapters in sequence"""
        self.current_chapter = "all"
        
        self.content_textbox.configure(state="normal")
        self.content_textbox.delete("0.0", "end")
        
        # Introduction
        intro_text = """Welcome to BeamSkin Studio Documentation

This comprehensive guide will help you create, manage, and export custom vehicle skins for BeamNG.drive.

Whether you're a beginner or an experienced modder, this guide covers everything from basic skin creation to advanced custom vehicle integration.

📋 Quick Navigation:
• Use the chapter buttons above to jump to specific topics
• Search for keywords using the search box
• Follow chapters in order for a complete walkthrough

Let's get started!

"""
        self.content_textbox.insert("0.0", intro_text)
        self.content_textbox.insert("end", "=" * 60 + "\n\n")
        
        # Add all chapters in order
        for chapter_key, chapter_data in self.chapters.items():
            self.content_textbox.insert("end", f"{chapter_data['icon']} {chapter_data['title']}\n")
            self.content_textbox.insert("end", "-" * 60 + "\n")
            self.content_textbox.insert("end", chapter_data['content'])
            self.content_textbox.insert("end", "\n\n")
        
        self.content_textbox.configure(state="disabled")
        
        # Set View All button to selected state (green, no hover)
        self.view_all_btn.configure(
            fg_color=state.colors["accent"],
            hover_color=state.colors["accent"],  # Same as fg_color to disable hover
            text_color=state.colors["accent_text"]
        )
        
        # Reset all chapter buttons to unselected state
        self._reset_button_colors()
        
        print("[DEBUG] Loaded all chapters")
    
    def _reset_button_colors(self):
        """Reset all chapter buttons to default colors"""
        for btn, _ in self.chapter_buttons:
            btn.configure(
                fg_color=state.colors["card_bg"],
                hover_color=state.colors["card_hover"],
                text_color=state.colors["text"]
            )
    
    # ============================================================================
    # CHAPTER CONTENT METHODS
    # ============================================================================
    
    def _chapter_getting_started(self) -> str:
        """Getting Started chapter content"""
        return """Welcome to BeamSkin Studio!

BeamSkin Studio is a professional tool for creating and managing vehicle skins for BeamNG.drive. This chapter will help you get started quickly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 What You'll Need
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. BeamNG.drive installed on your computer
2. Image editing software that supports DDS format:
   • Paint.NET (Free) - Recommended for beginners
   • GIMP (Free) with DDS plugin
   • Adobe Photoshop (Paid) with DDS plugin
   • Substance Painter (Paid) - Professional option

3. Your custom texture ready to save as DDS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Quick Start Guide
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Create Your Texture
• Design your skin in your image editor
• Match the vehicle's UV map dimensions
• Save as DDS format (BC3/DXT5 compression recommended)

Step 2: Name Your File Correctly
• Format: carid_skin_YourSkinName.dds
• Example: etk800_skin_RacingBlue.dds
• Use the Car List tab to find the correct carid

Step 3: Add to Project
• Go to the Project Tab
• Add your vehicle to the project
• Add your skin file to the vehicle
• Fill in mod information

Step 4: Generate Mod
• Choose your output location
• Click "Generate Mod"
• Launch BeamNG.drive and activate your mod

That's it! Your skin is now ready to use in-game.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Pro Tips
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Always save your project files (.bsproject) to avoid losing work
✓ Keep original PSD/XCF files separate from DDS exports
✓ Test skins in-game before sharing with others
✓ Use descriptive names for easy organization
✓ Back up your work regularly

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Common First-Time Mistakes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ Using PNG or JPG instead of DDS format
✗ Incorrect file naming (missing "skin" or wrong carid)
✗ Forgetting to activate mod in BeamNG.drive
✗ Using spaces in file names
✗ Not restarting BeamNG after adding mod

Continue to the next chapters for detailed instructions on each feature.
"""
    
    def _chapter_skin_creation(self) -> str:
        """Skin Creation chapter content"""
        return """Creating Professional Vehicle Skins

This chapter covers the technical requirements and best practices for creating high-quality vehicle skins.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 DDS File Requirements
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Required Format: DDS (DirectDraw Surface)

Compression Settings:
• BC3 (DXT5) - Best for color + alpha
• BC1 (DXT1) - For solid colors without transparency
• BC7 - Highest quality 

Recommended Resolutions:
1:1 Aspect Ratio:
• Performance Quality: 4096 x 4096
• Standard Quality: 8192 x 8192
• High Quality: 16384 x 16384

2:1 Aspect Ratio:
• Performance Quality: 4096 x 2048
• Standard Quality: 8192 x 4096
• High Quality: 16384 x 8192

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 File Naming Convention
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Format: [carid]_skin_[SkinName].dds

Components:
1. carid - Vehicle identifier (find in Car List tab)
   • Must be exact match
   • Case-sensitive
   • No spaces allowed

2. skin - Literal text "skin"
   • Must be lowercase
   • Required separator

3. SkinName - Your skin's unique name
   • One word (no spaces)
   • Letters and numbers only
   • CamelCase recommended for readability

✓ CORRECT Examples:
• etk800_skin_RacingStripes.dds
• pickup_skin_Muddy.dds
• sunburst2_skin_Police.dds

✗ INCORRECT Examples:
• etk 800_skin_Racing.dds (space in carid)
• etk800_Racing.dds (missing "skin")
• etk800_skin_Racing Stripes.dds (space in name)
• etk800_paint_Racing.dds (wrong separator)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 Obtaining UV Maps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UV maps show you where different parts of the car are located on the texture.

Method 1: Using BeamSkin Studio (Recommended)
1. Go to Car List tab
2. Find your vehicle
3. Click "Get UV Map" button
4. Save the extracted template
5. Open in your image editor as a guide layer

Method 2: Manual Extraction
1. Navigate to BeamNG installation:
   C:\\Program Files (x86)\\Steam\\steamapps\\common\\BeamNG.drive\\content\\vehicles\\
2. Find vehicle folder (e.g., "etk800")
3. Open the DDS texture in your editor
4. Save as template/reference

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖌️ Design Best Practices
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Layer Organization:
• Keep UV map as bottom reference layer
• Organize designs in folders/groups
• Use adjustment layers for easy color changes
• Maintain non-destructive workflow

Detail Considerations:
• Higher resolution areas = visible details (hood, doors)
• Lower resolution areas = less important (undercarriage)
• Add weathering and wear for realism
• Consider how light will affect the paint

Color Management:
• Use sRGB color space
• Avoid pure black (use dark gray instead)
• Test colors in different lighting conditions
• Consider color-blind accessibility

Performance:
• Don't use unnecessarily high resolutions
• Compress textures appropriately
• Test in-game performance
• Balance quality vs. file size

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💾 Saving Your Work
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Workflow:
1. Save master file (.psd, .xcf, .kra)
   • Keep all layers
   • Easy to modify later
   • High quality source

2. Export to DDS
   • Flatten layers
   • Apply compression
   • Save with correct naming

3. Keep organized backups
   • Separate folders for each vehicle
   • Version numbers for iterations
   • Archive completed projects

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Quality Checklist
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before exporting:
☐ UV alignment is correct
☐ No visible seams or stretching
☐ Resolution is appropriate
☐ Colors look good in neutral lighting
☐ Details are sharp and clear
☐ File name follows convention
☐ DDS compression is optimal
☐ Mip maps are generated
☐ Master file is saved
☐ Ready for testing in-game
"""
    
    def _chapter_project(self) -> str:
        """Project Tab chapter content"""
        return """Using the Project Tab

The Project Tab is your main workspace for creating skin mods. It uses a project-based system that allows you to manage multiple vehicles and skins in one place.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗂️ Project System Overview
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BeamSkin Studio uses a multi-car, multi-skin project system:

• One project = One mod ZIP file
• Each project can contain multiple vehicles
• Each vehicle can have multiple skins
• Projects can be saved and loaded
• All skins export together into a single mod

Benefits:
✓ Organize related skins together
✓ Manage large skin collections easily
✓ Save work in progress
✓ Reuse projects for updates

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Project Information
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mod Name (ZIP Name):
• Becomes the filename of your mod
• One word only, no spaces
• No special characters
• Example: MyCoolSkins, RacingPack, PoliceCollection
• This name appears in your mods folder

Author Name:
• Your name or username
• Appears in all skin metadata
• Spaces and special characters allowed
• Shows in BeamNG.drive skin selector

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚗 Adding Vehicles to Project
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step-by-Step Process:

1. Click "Select Vehicle"
   • Opens the vehicle selector dialog
   • Shows all available vehicles

2. Find Your Vehicle
   • Search by name or ID
   • Use filters if available
   • Hover for preview images

3. Select the Vehicle
   • Click on the vehicle card
   • Verify it's the correct one
   • Check the carid matches your DDS file

4. Add to Project
   • Click "Add Car to Project"
   • Vehicle appears in "Vehicles in Project" section
   • Ready to receive skins

Multiple Instances:
• You can add the same vehicle multiple times
• Useful for organizing different skin themes
• Example: "ETK 800 - Racing" and "ETK 800 - Casual"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 Adding Skins to Vehicles
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Process:

1. Select Target Vehicle
   • Click on a vehicle card in your project
   • Card highlights to show it's selected
   • Only one vehicle can be selected at a time

2. Enter Skin Name
   • This is the display name shown in-game
   • Spaces and special characters allowed
   • Should be descriptive and unique
   • Example: "Racing Stripes Red", "Police Livery"

3. Browse for DDS File
   • Click "Browse" button
   • Navigate to your skin file
   • Select the correctly named DDS file
   • File path shows in the field

4. Add the Skin
   • Click "Add Skin to Selected Car"
   • Skin appears under the vehicle
   • Can add more skins to the same vehicle
   • Repeat for all your skins

Skin Management:
• View all skins under each vehicle
• Remove individual skins if needed
• Reorder skins (if supported)
• Preview which skins are included

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💾 Project Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Save Project:
• Saves current state to .bsproject file
• Choose location and filename
• Includes all vehicles and skins
• Preserves all settings
• Allows continuing work later

Load Project:
• Opens a saved .bsproject file
• Restores all vehicles and skins
• Checks if DDS files still exist
• Warns about missing files
• Continue where you left off

Clear Project:
• Removes all vehicles and skins
• Starts fresh
• Prompts for confirmation
• Cannot be undone
• Project info is preserved

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 Output Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Steam Workshop Location (Default):
• Automatic path detection
• Windows: C:\\Users\\[username]\\AppData\\Local\\BeamNG.drive\\current\\mods
• Linux: ~/.local/share/BeamNG.drive/current/mods
• macOS: ~/Library/Application Support/BeamNG.drive/current/mods
• Mod activates automatically in-game

Custom Location:
• Choose any folder you want
• Useful for manual management
• Good for testing before sharing
• Organize mods by category
• Browse to select folder

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Generating Your Mod
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before Generating:
☐ All vehicles have at least one skin
☐ All DDS files are correctly named
☐ Mod name is unique and valid
☐ Author name is filled in
☐ Output location is correct

Generate Process:
1. Click "Generate Mod"
2. Tool processes all files
3. Creates folder structure
4. Copies all skin files
5. Generates metadata
6. Creates ZIP file
7. Moves to output location

Success Indicators:
✓ Success message appears
✓ ZIP file created in output folder
✓ No error messages
✓ File size seems reasonable
✓ Ready to test in-game

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Testing Your Mod
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

In BeamNG.drive:
1. Launch the game
2. Go to Content Manager > Mods
3. Find your mod in the list
4. Ensure it's activated (checkbox)
5. Restart game if needed
6. Spawn a vehicle
7. Check paint menu for your skins
8. Test each skin to verify appearance

Troubleshooting:
• If skins don't appear, check file names
• Ensure mod is activated in Content Manager
• Restart BeamNG.drive completely
• Check mods folder for ZIP file
• Verify carid matches vehicle

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Workflow Tips
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Efficient Organization:
• One project per theme/collection
• Group related skins together
• Use descriptive mod names
• Save projects frequently
• Keep DDS files organized in folders

Version Control:
• Increment version numbers
• Save different project versions
• Keep notes of changes
• Archive old versions
• Document updates for users

Quality Assurance:
• Test each skin before adding more
• Verify file names are correct
• Check in different lighting
• Get feedback from others
• Iterate and improve
"""
    
    def _chapter_car_list(self) -> str:
        """Car List chapter content"""
        return """Using the Car List Tab

The Car List tab provides a searchable database of all available vehicles, their IDs, and tools for working with them.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Finding Vehicles
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Search Functionality:
• Search by vehicle name (e.g., "Moonhawk")
• Search by car ID (e.g., "moonhawk")
• Case-insensitive searching
• Real-time results as you type
• Partial matches supported

Browse Mode:
• Scroll through complete vehicle list
• Organized alphabetically
• Visual card layout
• Hover for preview images
• Quick overview of all vehicles

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏷️ Understanding Car IDs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

What is a Car ID?
• Unique identifier for each vehicle
• Used in file names and mod structure
• Usually lowercase
• May contain underscores
• Never contains spaces

Common ID Patterns:
• Manufacturer_Model: "gavril_roamer"
• Series: "etk800", "etkc"
• Generation: "pickup" (D-Series), "midsize" (Pessima)
• Specialty: "racetruck", "rockbouncer"

Finding the Right ID:
1. Search for vehicle name in Car List
2. Vehicle card shows both name and ID
3. Use "Copy ID" button for accuracy
4. ID appears in carid field
5. Use this exact ID in your DDS file name

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Vehicle Information Cards
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each vehicle card displays:
• Vehicle Name - Full display name
• Car ID - Technical identifier
• Preview Image - Vehicle thumbnail (on hover)
• Action Buttons - Copy ID, Get UV Map

Card Features:
• Click to view details
• Hover for enlarged preview
• Quick copy ID to clipboard
• Direct UV map extraction
• Add to project button (in context)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 Getting UV Maps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

What are UV Maps?
UV maps show how the 2D texture wraps around the 3D vehicle model. They're essential templates for creating accurate skins.

Using "Get UV Map":
1. Find your vehicle in Car List
2. Click "Get UV Map" button
3. Tool extracts original texture
4. Save to your working directory
5. Open in image editor as reference layer

UV Map Best Practices:
• Use as non-printing guide layer
• Lock the layer to prevent edits
• Set layer opacity to 30-50%
• Design your skin on layers above
• Keep UV map for future reference

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Copy ID Feature
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Why Copy ID?
• Ensures exact ID accuracy
• Prevents typing errors
• Speeds up workflow
• Critical for file naming
• One-click convenience

Using Copy ID:
1. Click "Copy ID" button
2. ID copied to clipboard
3. Paste into file name
4. Or paste into notes/docs
5. Prevents manual transcription errors

Example Usage:
Vehicle: Gavril Roamer
Copy ID → "roamer"
Create file: roamer_skin_OffRoad.dds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 Preview Images
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hover Preview System:
• Hover over any vehicle card
• Preview appears after 0.5 seconds
• Shows vehicle render
• Displays vehicle name and ID
• Helps verify correct vehicle

Preview Features:
• High-quality vehicle renders
• Default vehicle configuration
• Standard paint scheme
• Clear identification
• Quick visual reference

Missing Previews:
• Some vehicles may not have previews
• Shows placeholder image
• Doesn't affect functionality
• ID and name still accurate
• Can still create skins normally

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔤 Vehicle Name vs. Car ID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Understanding the Difference:

Vehicle Name (Display Name):
• How vehicle appears in-game
• Human-readable format
• May contain spaces
• Example: "Gavril Grand Marshal"
• Used for communication

Car ID (Technical Name):
• Internal game identifier
• Machine-readable format
• No spaces, lowercase
• Example: "fullsize"
• Used in file naming

Critical Rule:
Always use Car ID in file names, never the display name!

✓ CORRECT: fullsize_skin_Police.dds
✗ WRONG: Gavril Grand Marshal_skin_Police.dds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Common Vehicles Reference
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Popular Vehicles and Their IDs:

Gavril:
• D-Series → pickup
• Roamer → roamer
• Grand Marshal → fullsize
• T-Series → us_semi
• H-Series → van
• Barstow → barstow
• Bluebuck → bluebuck

Ibishu:
• Covet → covet
• Pessima (Old) → pessima
• Pessima (New) → midsize
• Pigeon → pigeon
• Wigeon → wigeon
• Miramar → miramar
• Hopper → hopper

Bruckell:
• Moonhawk → moonhawk
• LeGran → legran
• Bastion → bastion

Hirochi:
• Sunburst → sunburst2
• SBR4 → sbr

ETK:
• 800-Series → etk800
• K-Series → etkc
• I-Series → etki

Others:
• Bolide → bolide
• Scintilla → scintilla
• Vivace → vivace
• Wendover → wendover

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Tips and Tricks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Workflow Efficiency:
• Use search to quickly find vehicles
• Copy ID immediately when starting work
• Extract UV map before designing
• Bookmark frequently used vehicles
• Keep a reference list of common IDs

Accuracy Checks:
• Always verify ID before naming files
• Double-check spelling
• Use Copy ID to avoid typos
• Test with simple skin first
• Confirm vehicle loads correctly

Organization:
• Create folders per vehicle
• Name folders with both name and ID
• Example: "Moonhawk_moonhawk"
• Keeps work organized
• Easy to find files later
"""
    
    def _chapter_add_vehicle(self) -> str:
        """Add Vehicle tab chapter content"""
        return """Using the Add Vehicle Tab

The Add Vehicle tab allows you to add custom, modded, or newly released vehicles to BeamSkin Studio. This is essential for creating skins for vehicles not in the default list.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL: Getting the Car ID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Car ID is THE MOST IMPORTANT piece of information. If it's wrong, nothing will work.

Required Method - BeamNG Console:

1. Launch BeamNG.drive
2. Load into any map (Free Roam works best)
3. Spawn the vehicle you want to add
   • ESC > Vehicles menu
   • Select your custom/modded vehicle

4. Open the Console
   • Press ~ (tilde) key

5. Find the Exact Car ID
   • Look for: "Vehicle replaced: [carid]"
   • The text after "replaced:" is your Car ID
   • Example: "Vehicle replaced: gavril_barstow"
   • Copy or write this down EXACTLY

6. Verify the ID
   • Must be exactly as shown
   • Usually lowercase
   • May contain underscores
   • No spaces
   • Case-sensitive!

Console Message Examples:
"Vehicle replaced: civetta_scintilla" → Use: civetta_scintilla
"Vehicle replaced: etk800" → Use: etk800  
"Vehicle replaced: custom_mod_car" → Use: custom_mod_car
"Vehicle replaced: rally_car_2024" → Use: rally_car_2024

⚠️ NEVER guess the Car ID!
⚠️ NEVER use the vehicle's display name!
⚠️ ALWAYS use exactly what the console shows!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Locating Required Files
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You need TWO files from the mod folder:
1. JSON file (material definitions)
2. JBEAM file (skin configuration)

Where to Find Them:

For Installed Mods:
1. Navigate to your BeamNG mods folder:
   Windows: C:\\Users\\[username]\\AppData\\Local\\BeamNG.drive\\current\\mods
   Linux: ~/.local/share/BeamNG.drive/current/mods
   macOS: ~/Library/Application Support/BeamNG.drive/current/mods

2. Find your mod's .zip file
3. Extract the ZIP to a temporary folder
4. Navigate into the extracted folder:
   [ModName] → vehicles → [vehiclename]

5. Look for these files in the vehicle folder:
   • skin.materials.json (or materials.json)
   • main.jbeam (or [vehiclename].jbeam)

For Vanilla Game Vehicles (Default Install):
Windows:
C:\\Program Files (x86)\\Steam\\steamapps\\common\\BeamNG.drive\\content\\vehicles\\

Linux:
~/.steam/steam/steamapps/common/BeamNG.drive/content/vehicles/

macOS:
~/Library/Application Support/Steam/steamapps/common/BeamNG.drive/content/vehicles/

Then: [vehiclename] folder

Typical File Structure:
```
[ModName].zip
├── vehicles/
│   └── [vehiclename]/
│       ├── skin.materials.json  ← You need this
│       ├── main.jbeam          ← You need this
│       ├── other files...
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Required JSON File
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Common Names:
• skin.materials.json (most common)
• materials.json
• [vehiclename]_materials.json
• skin_materials.json

What to Look For:
✓ File is in the vehicle's main folder
✓ Contains "materials" in the name
✓ Is a .json file
✓ Usually 1-50 KB in size
✓ Contains material definitions for skins

How to Verify Correct File:
1. Open in text editor (Notepad, VS Code)
2. Should contain entries like:
   • "paint1"
   • "paint2"  
   • "skin"
   • Material properties
3. Contains color/texture definitions

Example JSON Contents:
```json
{
  "paint1": {
    "mapTo": "paint",
    "color": [1, 1, 1, 1]
  }
}
```

⚠️ Common Mistakes:
✗ Selecting vehicle.json instead
✗ Selecting info.json
✗ Files from wrong folder
✗ Missing "materials" in filename

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Required JBEAM File
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Common Names:
• main.jbeam (most common)
• [vehiclename].jbeam
• [vehiclename]_main.jbeam
• skin.jbeam

What to Look For:
✓ File is in the vehicle's main folder
✓ Usually named "main.jbeam"
✓ Is a .jbeam file
✓ Usually larger than JSON (5-500+ KB)
✓ Contains vehicle configuration

How to Verify Correct File:
1. Open in text editor
2. Should contain "jbeam" references
3. Contains vehicle part definitions
4. May have skin-related entries
5. JSON-like structure with vehicle data

Example JBEAM Structure:
```json
{
  "main": {
    "information": {
      "name": "Vehicle Name"
    }
  }
}
```

⚠️ Important Notes:
• Some mods have multiple .jbeam files
• If unsure, "main.jbeam" is usually correct
• File should be in vehicle's root folder
• Not in subfolders like "parts" or "slots"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
➕ Adding a Vehicle - Step by Step
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Complete Process:

Step 1: Get Car ID from BeamNG Console
• Launch BeamNG.drive
• Spawn the vehicle
• Open console (~)
• Find "Vehicle replaced: [carid]"
• Copy the exact ID

Step 2: Locate Mod Files
• Navigate to mods folder
• Extract mod ZIP (if needed)
• Find: vehicles → [vehiclename]
• Identify skin.materials.json
• Identify main.jbeam

Step 3: Open Add Vehicle Tab
• Go to Add Vehicle tab in BeamSkin Studio
• Form will be empty and ready

Step 4: Enter Car ID
• Paste the EXACT Car ID from console
• No modifications
• Case-sensitive
• Example: "custom_rally_car"

Step 5: Enter Display Name
• This is what you'll see in menus
• Can be anything you want
• Spaces allowed
• Example: "Custom Rally Car 2024"

Step 6: Select JSON File
• Click "Browse" next to JSON field
• Navigate to vehicle folder
• Select skin.materials.json
• Verify correct file

Step 7: Select JBEAM File
• Click "Browse" next to JBEAM field
• Same folder as JSON
• Select main.jbeam
• Verify correct file

Step 8: Add Preview Image (Optional)
• Click "Browse" next to Image field
• Select a .jpg or .jpeg image
• 400x400+ pixels recommended
• Shows in vehicle cards
• Not required but nice to have

Step 9: Add the Vehicle
• Review all information
• Click "Add Vehicle" button
• Wait for processing
• Check for success message

Success Indicators:
✓ "Vehicle added successfully" message
✓ Vehicle appears in Car List
✓ Available in Project Tab
✓ Preview image shows (if added)
✓ Ready to create skins for it

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ What Happens Automatically
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BeamSkin Studio processes your files:

JSON Processing:
• Identifies skin material entries
• Removes color palette systems
• Updates material paths
• Standardizes material names
• Preserves important properties
• Creates clean skin template

JBEAM Processing:
• Finds main skin configuration
• Updates skin entry names
• Sets placeholder values
• Preserves vehicle structure
• Ensures compatibility

File Management:
• Creates vehicle folder structure
• Copies processed files
• Generates metadata
• Adds to vehicle database
• Links preview image
• Saves permanently

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Verification Steps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

After Adding Vehicle:

1. Check Car List Tab
   • Your vehicle should appear
   • Search for it by name
   • Verify Car ID is correct
   • Preview image shows (if added)

2. Test in Project Tab
   • Click "Select Vehicle"
   • Find your new vehicle
   • Add it to a project
   • Verify it appears correctly

3. Create Test Skin
   • Make simple color test skin
   • Name file: [carid]_skin_Test.dds
   • Add to project
   • Generate mod
   • Test in BeamNG.drive

If Test Succeeds:
✓ Car ID is correct
✓ Files processed properly
✓ Ready for production skins
✓ Can create full skin sets

If Test Fails:
• Check Car ID matches console exactly
• Verify JSON/JBEAM were correct files
• Enable Debug Mode to see processing
• Try re-adding with correct files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Pro Tips
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

File Organization:
• Extract mod ZIPs to organized folders
• Keep structure: [ModName] → vehicles
• Label folders clearly
• Easy to find files later

Preview Images:
• Screenshot vehicle in-game
• Crop to square aspect ratio
• Save as high-quality JPEG
• Makes vehicle easy to identify
• Professional appearance

Testing Strategy:
1. Add vehicle
2. Create simple test skin (solid color)
3. Generate small mod
4. Test in BeamNG.drive
5. If working, proceed with detailed skins
6. If not, check Car ID and files

Documentation:
• Keep notes on custom vehicles
• Record Car ID for reference
• Note mod source
• Document any special requirements
• Helpful for future updates

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Common Issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Skins don't work after adding vehicle":
→ Car ID must be EXACT from console
→ Verify you spawned correct vehicle
→ Check for typos or case differences
→ Re-check console message

"Can't find JSON or JBEAM files":
→ Must be in vehicle's main folder
→ Not in subfolders
→ Extract mod ZIP completely
→ Look for common file names

"Processing errors":
→ Enable Debug Mode in Settings
→ Watch console for error details
→ Verify files aren't corrupted
→ Try different files if available

"Vehicle appears but skins won't show":
→ Car ID verification critical
→ Test with simple solid color skin
→ Check BeamNG console for errors
→ Ensure mod is activated in-game

Remember: The Car ID must be EXACTLY as shown in the BeamNG.drive console. This cannot be emphasized enough - it's the #1 cause of issues!
"""
    
    def _chapter_developer_mode(self) -> str:
        """Developer Mode chapter content"""
        return """Developer Mode - Advanced Vehicle Integration

Developer Mode allows you to add custom, modded, or new vehicles that aren't in the default vehicle list. This is an advanced feature requiring technical knowledge.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL: Finding the Correct Car ID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Car ID is the MOST IMPORTANT piece of information. If incorrect, skins will not work at all.

Required Method - Using BeamNG Console:

1. Launch BeamNG.drive
2. Load into any map (Free Roam recommended)
3. Spawn the vehicle you want to add
   • Use ESC > Vehicles menu
   • Select your custom/modded vehicle

4. Open the Console
   • Press ~ (tilde) key
   • Console appears at bottom of screen
   • Shows game system messages

5. Find the Car ID
   • Look for: "Vehicle replaced: [carid]"
   • The text after "replaced:" is your exact Car ID
   • Example: "Vehicle replaced: gavril_barstow"
   • Write this down EXACTLY as shown

6. Verify the ID
   • Should be lowercase
   • May contain underscores
   • No spaces
   • Case-sensitive!

Example Console Messages:
"Vehicle replaced: civetta_scintilla" → Use: civetta_scintilla
"Vehicle replaced: etk800" → Use: etk800
"Vehicle replaced: custom_vehicle_2024" → Use: custom_vehicle_2024

⚠️ Do NOT guess the Car ID!
⚠️ Do NOT make up a Car ID!
⚠️ Use ONLY what the console shows!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Enabling Developer Mode
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Steps:
1. Go to Settings tab
2. Find "Developer Mode" toggle
3. Enable it
4. New "Developer" tab appears in main navigation
5. Access advanced vehicle management

Requirements:
• Understanding of BeamNG.drive file structure
• Ability to navigate game installation
• Knowledge of JSON and JBEAM formats
• Patience and attention to detail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Locating Vehicle Files
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Standard BeamNG Installation:
Windows:
C:\\Program Files (x86)\\Steam\\steamapps\\common\\BeamNG.drive\\content\\vehicles\\

Linux:
~/.steam/steam/steamapps/common/BeamNG.drive/content/vehicles/

macOS:
~/Library/Application Support/Steam/steamapps/common/BeamNG.drive/content/vehicles/

Modded Vehicles:
Check your mods folder:
Windows: C:\\Users\\[username]\\AppData\\Local\\BeamNG.drive\\current\\mods\\

Navigate to mod ZIP, extract, then look in:
vehicles/[vehicle_folder]/

Required Files Location:
1. Find vehicle folder (matches car ID usually)
2. Open "skin" subfolder
3. Locate these files:
   • materials.json (or similar .json)
   • [vehicleid]_skin.jbeam (or similar .jbeam)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
➕ Adding a Custom Vehicle
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step-by-Step Process:

1. Get the Exact Car ID (see above)
   • Use BeamNG console method
   • Write it down exactly
   • Case-sensitive!

2. Enter Car ID
   • Paste or type EXACTLY as shown in console
   • No modifications
   • Must match perfectly

3. Enter Car Name
   • This is the display name (shown in menus)
   • Can be anything you want
   • Spaces allowed
   • Example: "Custom Rally Car 2024"

4. Select JSON File
   • Click "Browse" next to JSON field
   • Navigate to vehicle's skin folder
   • Select materials.json (or skin.json, materials_skin.json)
   • Verify it's the correct file

5. Select JBEAM File
   • Click "Browse" next to JBEAM field
   • Same folder as JSON
   • Select [vehicleid]_skin.jbeam
   • Should contain skin definitions

6. Select Preview Image (Optional)
   • JPEG format only (.jpg or .jpeg)
   • Recommended: 400x400 pixels or larger
   • Shows in vehicle cards and previews
   • Not required but recommended

7. Click "Add Vehicle"
   • Tool processes files automatically
   • Shows progress/status
   • Completes in a few seconds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ What the Tool Does Automatically
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JSON Processing:
✓ Identifies canonical skin variant
✓ Removes alternative skin variants
✓ Removes color palette systems
✓ Removes colorPaletteMap entries
✓ Updates material paths
✓ Standardizes material names
✓ Preserves other properties

JBEAM Processing:
✓ Finds primary skin entry
✓ Removes duplicate skin entries
✓ Updates skin placeholder names
✓ Sets author information
✓ Preserves slotType and value
✓ Maintains compatibility

File Management:
✓ Creates vehicle folder structure
✓ Copies and processes files
✓ Generates required metadata
✓ Adds to vehicle database
✓ Creates preview image reference
✓ Saves configuration permanently

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗂️ Managing Custom Vehicles
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View Added Vehicles:
• Developer tab shows all custom vehicles
• Search by name or ID
• View processing status
• Access vehicle details

Delete Vehicles:
• Select vehicle in Developer tab
• Click "Delete" button
• Confirms before removing
• Permanently removes from system
• Cannot be undone

Edit Vehicles:
• Current version: Delete and re-add
• Future versions may support editing
• Keep backup of original files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 Debug Mode
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Enable Debug Mode (in Settings):
• Shows detailed processing logs
• Displays every step
• Helps troubleshoot issues
• Shows which variants were found
• Indicates canonical skin selection
• Reports any errors

Debug Output Shows:
• File paths being processed
• JSON variant detection
• JBEAM entry processing
• Material path updates
• Success/failure states
• Detailed error messages

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Common Issues and Solutions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Skin not working after adding vehicle":
→ Verify Car ID matches console exactly
→ Check that you selected correct JSON/JBEAM files
→ Enable Debug Mode to see processing details
→ Ensure files came from "skin" subfolder

"Cannot find JSON or JBEAM files":
→ Check in vehicle's "skin" folder specifically
→ Some mods use different folder structures
→ Extract mod ZIP if needed
→ Look for files with "material" or "skin" in name

"Preview image not showing":
→ Ensure image is JPEG format (.jpg or .jpeg)
→ Check file isn't corrupted
→ Try different image
→ Preview is optional, doesn't affect functionality

"Vehicle appears multiple times":
→ Canonical skin processing may have created duplicates
→ Normal behavior in some cases
→ Use the one that works
→ Or delete and re-add

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Best Practices
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

File Organization:
• Keep original mod files separate
• Create working folder for each vehicle
• Copy files before adding to tool
• Back up processed vehicle folders
• Document Car IDs in a reference file

Testing Workflow:
1. Add vehicle to BeamSkin Studio
2. Create simple test skin
3. Generate mod with test skin
4. Load in BeamNG and verify
5. If working, proceed with full skins
6. If not, check Car ID and file selection

Documentation:
• Keep notes on each custom vehicle
• Record where you got the files
• Document the Car ID source
• Note any special requirements
• Save screenshots for reference

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎓 Advanced Tips
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Understanding Variants:
• Some vehicles have multiple skin variants
• Tool keeps first variant found
• Others are automatically removed
• This prevents conflicts
• Ensures custom skins work consistently

Color Palette Systems:
• BeamNG supports dynamic color palettes
• These can interfere with custom skins
• Tool removes palette logic automatically
• Your custom colors will be preserved
• No palette blending or overrides

Material Names:
• Tool standardizes material paths
• Ensures compatibility across versions
• Updates references automatically
• Maintains visual quality
• No manual editing required

The Developer Mode is powerful but requires careful attention to detail. Always verify your Car ID and test thoroughly!
"""
    
    def _chapter_troubleshooting(self) -> str:
        """Troubleshooting chapter content"""
        return """Troubleshooting Common Issues

This chapter addresses the most common problems and their solutions. Read carefully to resolve issues quickly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ Skin Not Appearing In-Game
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Check List:
☐ DDS file name uses correct Car ID
☐ File name format: carid_skin_skinname.dds
☐ Mod is activated in BeamNG Content Manager
☐ BeamNG.drive was restarted after adding mod
☐ Mod ZIP is in correct mods folder
☐ Vehicle in project matches skin's carid
☐ No typos in file name

Step-by-Step Fix:
1. Verify Car ID
   • Check Car List tab for correct ID
   • Compare with your DDS file name
   • Must match EXACTLY (case-sensitive)

2. Check File Name Format
   ✓ Correct: etk800_skin_Racing.dds
   ✗ Wrong: etk800_Racing.dds
   ✗ Wrong: etk 800_skin_Racing.dds
   ✗ Wrong: ETK800_skin_Racing.dds

3. Verify Mod Activation
   • Launch BeamNG.drive
   • ESC > Content Manager > Mods
   • Find your mod in the list
   • Checkbox should be checked
   • If not, click to activate

4. Restart BeamNG
   • Close game completely
   • Wait 5 seconds
   • Launch again
   • Mods refresh on restart

5. Check Mods Folder
   • Navigate to output location
   • Verify ZIP file exists
   • File size should be reasonable (not 0 KB)
   • Try extracting to verify contents

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖼️ DDS File Issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"File won't open in BeamNG":
→ Must be DDS format (not PNG, JPG, BMP)
→ Save in image editor with "Save As DDS"
→ Verify file extension is .dds

"Compression errors":
→ Use BC3 (DXT5) compression
→ Or BC1 (DXT1) for solid colors
→ BC7 if your editor supports it
→ Check editor's DDS export settings

"Resolution problems":
→ Must be power of 2 (512, 1024, 2048, 4096)
 1:1 Aspect Ratio:
 • Performance Quality: 4096 x 4096
 • Standard Quality: 8192 x 8192
 • High Quality: 16384 x 16384

 2:1 Aspect Ratio:
 • Performance Quality: 4096 x 2048
 • Standard Quality: 8192 x 4096
 • High Quality: 16384 x 8192

"Texture appears corrupt in-game":
→ Re-export from source file
→ Check original isn't corrupted
→ Try different DDS compression
→ Generate mip-maps
→ Use different image editor

"Black or white texture":
→ Check UV mapping alignment
→ Verify colors aren't pure black/white
→ Test with bright colors first
→ Check alpha channel
→ Try BC3 compression

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Custom Vehicle Not Working
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Most Critical: Car ID Verification

1. Console Method (Required)
   • Load BeamNG.drive
   • Spawn the exact vehicle
   • Open console (~)
   • Look for: "Vehicle replaced: [carid]"
   • Use EXACTLY what appears

2. Common Car ID Mistakes
   ✗ Guessing the ID
   ✗ Using vehicle display name
   ✗ Wrong capitalization
   ✗ Adding or removing underscores
   ✗ Using spaces

3. File Selection Issues
   • JSON must be from "skin" folder
   • JBEAM must be from "skin" folder
   • Not from main vehicle folder
   • Not from other subfolders
   • Verify correct files

4. Enable Debug Mode
   • Settings > Debug Mode
   • Watch processing output
   • Check canonical skin detection
   • Verify JSON/JBEAM processing
   • Look for error messages

5. File Structure
   • Ensure files are from correct vehicle
   • Check mod compatibility
   • Verify game version match
   • Test with vanilla vehicles first

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 ZIP File Already Exists Error
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue: "A mod with this name already exists"

Solutions:
1. Choose Different Name
   • Change mod name in project
   • Use unique identifier
   • Example: MyCoolSkins_v2

2. Delete Existing Mod
   • Navigate to mods folder
   • Find old ZIP file
   • Delete or rename it
   • Generate new mod

3. Rename Old Mod
   • Keep both versions
   • Add "_old" suffix to old file
   • Useful for backups
   • Prevents conflicts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖼️ Preview Images Not Showing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Troubleshooting:
• Hover for 0.5-1 second (not instant)
• Check image is JPEG format (.jpg/.jpeg)
• Minimum 400x400 pixels recommended
• Image should be in correct folder
• Some vehicles may use placeholder

Solutions:
1. Re-add preview image
2. Use different image file
3. Check file isn't corrupted
4. Verify correct JPEG format
5. Preview is cosmetic only (doesn't affect skins)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💾 Project File Issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Cannot load project":
→ Verify .bsproject file isn't corrupted
→ Check file path hasn't changed
→ Ensure DDS files still exist in original locations
→ Try opening in text editor to check format
→ Re-create project if necessary

"Missing skin files":
→ Tool checks if DDS files exist
→ Move files back to original location
→ Or re-browse to new location
→ Update file paths in project
→ Save project after fixing

"Project won't save":
→ Check folder write permissions
→ Ensure sufficient disk space
→ Verify folder path is valid
→ Try different save location
→ Check antivirus isn't blocking

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ Generation Failures
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Mod generation failed":

Check:
☐ All DDS files exist and are accessible
☐ File names follow correct format
☐ No special characters in mod name
☐ Output folder exists and is writable
☐ Sufficient disk space
☐ No files are locked by other programs
☐ At least one vehicle has one skin

Common Causes:
• Missing DDS files (moved or deleted)
• File name errors
• Permission issues
• Disk space
• Files open in other programs
• Invalid mod name

Solutions:
1. Verify all files exist
2. Check file permissions
3. Close other programs
4. Free up disk space
5. Choose different output folder
6. Restart BeamSkin Studio

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎮 BeamNG.drive Integration Issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Mods folder not detected":
→ Set custom output location
→ Browse to mods folder manually
→ Check BeamNG installation path
→ Verify game is installed correctly

Path Examples:
Windows: C:\\Users\\[username]\\AppData\\Local\\BeamNG.drive\\current\\mods
Linux: ~/.local/share/BeamNG.drive/current/mods
macOS: ~/Library/Application Support/BeamNG.drive/current/mods

"Mod appears but skins don't load":
→ Verify mod is activated
→ Restart BeamNG completely
→ Check car ID matches
→ Test with different vehicle
→ Check BeamNG console for errors

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Application Errors
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Application won't start":
→ Check Python installation
→ Verify all dependencies installed
→ Run install.bat again (Windows)
→ Check for error messages
→ Try clearing cache (clear_cache.bat)

"Application crashes":
→ Enable Debug Mode first
→ Check console output
→ Update to latest version
→ Report bug with debug logs
→ Try fresh installation

"Slow performance":
→ Close unused tabs
→ Clear debug console regularly
→ Work with smaller projects
→ Close preview windows
→ Restart application periodically

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 File Path Issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Windows Path Problems:
• Avoid special characters: !@#$%^&*()
• No spaces in folder names (use underscores)
• Keep paths reasonably short
• Use forward / or double backslash \\
• Avoid network drives if possible

Cross-Platform:
• Linux/Mac: Case-sensitive file systems
• Windows: Not case-sensitive
• Use consistent naming
• Avoid special characters everywhere

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🆘 Getting Help
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before Asking:
1. Enable Debug Mode
2. Try to reproduce the issue
3. Note exact error messages
4. Check this troubleshooting guide
5. Verify you followed instructions

When Reporting Issues:
• Describe what you were trying to do
• Explain what happened instead
• Include debug console output
• Specify operating system
• Note BeamNG.drive version
• Share project file if relevant
• Include screenshots if helpful

Where to Get Help:
• BeamNG Forums: forum.beamng.com
• BeamNG Discord servers
• GitHub Issues (if available)
• BeamNG modding community

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Prevention Tips
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Avoid Problems:
✓ Save projects frequently
✓ Back up DDS files
✓ Test skins incrementally
✓ Verify file names before generating
✓ Use Car List to copy IDs
✓ Keep organized folder structure
✓ Document your workflow
✓ Update software regularly
✓ Read error messages carefully
✓ Enable Debug Mode when learning

Quality Workflow:
1. Create skin in image editor
2. Save as DDS with correct name
3. Verify file name format
4. Add to small test project
5. Generate and test in-game
6. If working, add to main project
7. Save project file
8. Generate final mod
9. Test thoroughly
10. Share with confidence"""
    
    def _chapter_advanced(self) -> str:
        """Advanced Topics chapter content"""
        return """Advanced Topics

This chapter covers advanced techniques and best practices for professional skin creation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 Advanced Texture Techniques
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Multi-Layer Workflow:
• Base color layer
• Detail/decal layers
• Weathering/dirt layers
• Scratch/damage layers
• Gloss/reflection consideration

Layer Organization:
1. Background (UV reference - locked, 30% opacity)
2. Base paint color
3. Main design elements
4. Secondary details
5. Text/logos
6. Weathering effects
7. Final color adjustments

Smart Workflow Techniques:
• Use smart objects for reusable logos
• Maintains quality when resizing
• Easy updates across multiple skins
• Non-destructive editing

Color Management:
• Use adjustment layers for global changes
• Non-destructive color grading
• Easy to create color variations
• Maintain consistent color schemes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 UV Mapping Optimization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Understanding UV Density:
• Hood/doors: High detail (large UV space)
• Roof/trunk: Medium detail
• Undercarriage: Low detail (small UV space)
• Mirrors/trim: Minimal detail

Detail Distribution:
• Focus detail where most visible
• Simplify less visible areas
• Balance file size vs. quality
• Consider common viewing angles

Seam Management:
• Identify UV seams on template
• Avoid placing important details across seams
• Use clone stamp to blend seams
• Test in-game to verify seamless appearance

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Technical Optimization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

File Size Management:
• Use appropriate DDS compression
• Don't over-size textures unnecessarily
• Generate proper mip-map chains
• Balance visual quality vs. performance
• Test on various hardware

Performance Considerations:
• Standard quality (2048²) for most users
• High quality (4096²) for enthusiasts
• Consider multiplayer impact
• Optimize for VR if applicable

Quality Assurance Checklist:
☐ Test on multiple graphics settings
☐ Verify in different lighting conditions
☐ Check at various viewing distances
☐ Test in rain and night conditions
☐ Validate on different monitor types
☐ Ensure readability of text/numbers

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Professional Tips
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Creating Skin Collections:
• Develop unified themes
• Maintain consistent design language
• Use common color palettes
• Standardize detail level
• Professional naming conventions

Version Control:
• Semantic versioning (1.0, 1.1, 2.0)
• Maintain change logs
• Archive old versions
• Document updates clearly

Community Best Practices:
• High-quality preview images
• Clear installation instructions
• Credits for used resources
• Respond to user feedback
• Regular updates and bug fixes
"""
    
    def _chapter_faq(self) -> str:
        """FAQ chapter content"""
        return """Frequently Asked Questions

Quick answers to the most commonly asked questions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 Skin Creation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: What software do I need?
A: Any image editor supporting DDS (Paint.NET free, GIMP free, Photoshop paid).

Q: Can I use PNG or JPG?
A: No, must be DDS format for BeamNG.drive.

Q: What resolution should I use?
A1: for 1:1 aspect ratio 8192x8192 (standard) or 16384x16384 (high quality).
A2: for 2:1 aspect ratio 8192x4096 (standard) or 16384x8192 (high quality).
Note: Resolutions must be power of 2 (512, 1024, 2048, etc).

Q: Do I need the UV map?
A: Helpful but not required. Use "Get UV Map" in Car List for templates.

Q: Can I use the same skin on multiple vehicles?
A: No, each vehicle has unique UV mapping. Create separate skins per vehicle.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Tool Usage
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: Can I add multiple skins to one vehicle?
A: Yes! Add vehicle once, then add unlimited skins to it.

Q: Can one mod contain multiple vehicles?
A: Yes! That's the main feature - one mod for all your skins.

Q: How do I update an existing mod?
A: Change mod name or delete old mod, then regenerate.

Q: Do project files work on different computers?
A: Yes, but DDS paths must be accessible or re-browsed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Files and Naming
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: What is a Car ID?
A: Technical vehicle identifier (e.g., "etk800"). Find in Car List tab.

Q: Is Car ID case-sensitive?
A: Yes! Must match exactly. Use Copy ID button for accuracy.

Q: Can file names have spaces?
A: No! Format: carid_skin_SkinName.dds (no spaces anywhere).

Q: What if I misspell the Car ID?
A: Skin won't work. Always copy from Car List tab.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎮 BeamNG Integration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: Where is my mod installed?
A: Default Steam mods folder or custom location you chose.

Q: Do I activate my mod?
A: Yes! Content Manager > Mods > Enable checkbox.

Q: Why don't I see my skins?
A: Check mod activated, BeamNG restarted, Car ID correct.

Q: Do mods work in BeamMP?
A: No, custom mods are single-player only.
"""