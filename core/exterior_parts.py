
import re

_WORD_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|[^0-9A-Za-z]+")

_EXTERIOR_PART_WORDS = frozenset({
    "arch", "arches",
    "backlite",
    "bonnet",
    "boot", "boots",
    "body", "bodies",
    "bumper", "bumpers",
    "bumperbar", "bumperbars",
    "diffuser", "diffusers",
    "door", "doors",
    "fender", "fenders",
    "flap", "flaps",
    "fog", "foglight", "foglights",
    "glass",
    "grill", "grills", "grille", "grilles",
    "handle", "handles",
    "hatch", "hatches",
    "headlight", "headlights",
    "hood", "hoods",
    "indicator", "indicators",
    "lamp", "lamps",
    "liftgate", "liftgates",
    "liner", "liners",
    "lip", "lips",
    "mirror", "mirrors",
    "moonroof", "moonroofs",
    "marker", "markers",
    "mudflap", "mudflaps",
    "mudguard", "mudguards",
    "pillar", "pillars",
    "quarter", "quarters",
    "rail", "rails",
    "reardoor", "reardoors",
    "rocker", "rockers",
    "roof", "roofs",
    "shield", "shields",
    "skirt", "skirts",
    "splash",
    "splitter", "splitters",
    "sunroof", "sunroofs",
    "tailgate", "tailgates",
    "taillight", "taillights",
    "window", "windows",
    "windshield", "windshields",
    "windscreen", "windscreens",
    "wing", "wings",
    "trunk", "trunks",
    "spoiler", "spoilers",
})

_COMPOUND_PART_WORDS = frozenset({
    "bumpercover", "bumpercovers",
    "brakelight", "brakelights",
    "doorhandle", "doorhandles",
    "fenderliner", "fenderliners",
    "foglamp", "foglamps",
    "markerlamp", "markerlamps",
    "quarterglass",
    "splashguard", "splashguards",
    "wheelarch", "wheelarches",
    "wingmirror", "wingmirrors",
})

_EXCLUDED_PART_WORDS = frozenset({"exhaust", "header", "manifold", "turbo"})


def has_exterior_part_name(name: str) -> bool:
    if not isinstance(name, str) or not name:
        return False
    words = {word.lower() for word in _WORD_SPLIT_RE.split(name) if word}
    if (any("glass" in word for word in words)
            or words & (_EXCLUDED_PART_WORDS | {"light", "lights"})):
        return False
    return bool(words & (_EXTERIOR_PART_WORDS | _COMPOUND_PART_WORDS))
