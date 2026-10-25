# BeamSkin Studio live-parts exporter

This BeamNG.drive UI app exports the active vehicle configuration's chosen part slots,
per-part flexbody/prop mesh names, and the complete assembled mesh-name list to:

`settings/beamskin_studio/<carid>/<filename>.json`

Choose an export preset in the exporter app to keep multiple exports for the same
vehicle. Presets cover vehicle styles and body types, racing disciplines, emergency
services, work vehicles, and offroad builds. The preset menu scrolls independently
to keep the app compact. For example, a Police export for the ETK 800 is written to
`settings/beamskin_studio/etk800/police.json`.

## Install

Copy the `lua` and `ui` folders from this directory into the root of an unpacked mod
inside BeamNG.drive's user `mods/unpacked` folder. For example:

`current/mods/unpacked/BeamSkinStudioPartExporter/`

Enable the mod in BeamNG.drive, then add **BeamSkin Studio - Vehicle Parts Exporter**
from the UI Apps selector. The app writes the JSON file in the BeamNG user
folder. In BeamSkin Studio's 3D Preview, choose **Load BeamNG parts…**; the file
picker opens in that vehicle's `settings/beamskin_studio/<carid>` folder so you
can choose among its saved exports.

The preview matches exported DAE node names exactly (case-insensitively); unmatched
meshes remain hidden when an export matches at least one node. Use **Clear** to return
to the regular automatic part selection.
