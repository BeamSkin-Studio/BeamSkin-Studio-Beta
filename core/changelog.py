
from typing import TypedDict, Literal


EntryType = Literal["title", "subtitle", "item", "note", "separator"]

class Entry(TypedDict):
    type:  EntryType
    text:  str


def title(text: str) -> Entry:
    return {"type": "title", "text": text}

def subtitle(text: str) -> Entry:
    return {"type": "subtitle", "text": text}

def item(text: str) -> Entry:
    return {"type": "item", "text": text}

def note(text: str) -> Entry:
    return {"type": "note", "text": text}

def separator() -> Entry:
    return {"type": "separator", "text": ""}


CHANGELOGS = [

    {
        "version": "0.9.1.Beta",
        "date": "10-08-2026",
        "entries": [
            title("🐛 Bug Fixes"),
            subtitle("Generator Tab"),
            item("• Fixed an issue causing the \"edit vehicle info\" to duplicate it's self if you have more then 1 vehicle in the project."),
        ]
    },


    {
        "version": "0.9.0.Beta",
        "date": "09-08-2026",
        "entries": [
            title("🚀 New Features"),
            subtitle("Retroreflectivity:"),
            item("You can now add real retroreflectivity to your skins!"),
            subtitle("Layers:"),
            item("To make decals look like actual decals, I've made it so everything is done in layers, separating the car paint and decals. This was done because of the new orange peel effect, and because I noticed the cars have a paint-like roughness."),
            subtitle("Edit Vehicle Info:"),
            item("You can now edit the info_skinname.json within BeamSkin Studio, available when adding a config."),
            subtitle("Presets:"),
            item("You can now save material values as a preset that you can easily load and reuse."),
            subtitle("Data Folder:"),
            item("Now everything you add or save is saved at a specific location that you pick, you will need to migrate if you are already using BeamSkin Studio before this update."),
            separator(),
            title("⚙️ Improvements"),
            subtitle("Exporting:"),
            item("Now, during an export, the entire project tab will lock its interactivity until it is finished."),
            subtitle("Export Progress:"),
            item("The export progress bar is no longer at the bottom. It will now appear at the bottom right as a little notification."),
            subtitle("Project Browser:"),
            item("The Remove button now deletes the actual project file."),
            subtitle("How To Use Tab:"),
            item("The guide tab now include images for better understanding."),
            separator(),
            title("🐛 Bug Fixes"),
            subtitle("Mod Scanner:"),
            item("• Fixed an issue causing \"mod scanner unavailble\"\n• Fixed an issue causing the user to be unable to add the mod after the scan."),
            separator(),
            title("📝 Notes"),
            note("If you are experiencing any issues, then please make a bug report in the discord server!"),
        ]
    },


    {
        "version": "0.8.4.Beta",
        "date": "03-08-2026",
        "entries": [
            title("🐛 Bug Fixes"),
            subtitle("Wentward DT40L"),
            item("Fixed the material file having the wrong normalmap"),
        ]
    },


    {
        "version": "0.8.3.Beta",
        "date": "01-08-2026",
        "entries": [
            title("🏎️ New Vehicles"),
            subtitle("Cherrier Ardente"),
            item("Added Cherrier Ardente."),
            separator(),
            title("Removed Stuff:"),
            subtitle("Discord"),
            item("Removed the Discord Ban popup"),
        ]
    },


    {
        "version": "0.8.2.Beta",
        "date": "31-05-2026",
        "entries": [
            title("⚙️ Improvements"),
            subtitle("Auto add vehicle mod"),
            item("ZIPs: You can now add multiple mods at the same time"),
            subtitle("Mod scanner"),
            item("I have made some improvements on the mod scanner, less chance that it will fail\n\nNOTE:\nPlease remove all your added vehicles and re add them"),
            separator(),
            title("🐛 Bug Fixes"),
            subtitle("Colorable Skin (at position 1) Issue"),
            item("This issue has hopefully been fully fixed now"),
        ]
    },


    {
        "version": "0.8.0.Beta",
        "date": "15-05-2026",
        "entries": [
            title("🚀 New Features"),
            subtitle("Body variant support"),
            item("You can now do skins for vehicle variants like bus, cargo, box and ambulance"),
            subtitle("Reflective map"),
            item("You can now add reflectivity to your skins, this is useful for police skins and other type of vehicle skins that use reflective decals"),
            subtitle("Unpack toggle"),
            item("You can now export your mod to the unpacked folder as a plain mod folder, no need to extract your mod manually any more"),
            subtitle("Auto add mods"),
            item("BeamSkin Studio can now add you mods for you amd find the correct files, no more finding the correct files manually"),
            separator(),
            title("⚙️ Improvements"),
            subtitle("PySide6 Migration"),
            item("Beamskin Studio now uses PySide6 GUI FrameWork that uses your GPU for the UI rendering, this gives more UI freedom for me the developer and a more stable and smother experience for the users"),
            subtitle("Save and Load Projects"),
            item("I have imporved the save/load feature by giving it a ui window where you can see and select all your saved projects.\n\nnote:\nolder saves done before V.0.8.0.Beta need to be added manually to the load save menu."),
            subtitle("Adding config files is now easier"),
            item("Adding .pc and .jpg files have been improved, now when you press browse on the 2 browse buttons it will open that vehicles folder where your configs are saved for it if the folder exist"),
        ]
    },


    {
        "version": "0.7.20.Beta",
        "date": "18-04-2026",
        "entries": [
            title("⚙️ Improvements"),
            subtitle("PySide6 GUI Framework"),
            item("Switched from customtkinter to PySide6 \n- Expect better and smother experience"),
        ]
    },

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


]


def get_changelog_for_version(version: str) -> dict | None:
    version = version.strip()
    for entry in CHANGELOGS:
        if entry.get("version", "").strip() == version:
            return entry
    return None


def get_latest_changelog() -> dict | None:
    return CHANGELOGS[0] if CHANGELOGS else None


def get_all_versions() -> list[str]:
    return [entry["version"] for entry in CHANGELOGS]
