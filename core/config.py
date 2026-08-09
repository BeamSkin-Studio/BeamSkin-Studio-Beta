
VEHICLE_IDS = {
    "autobello": "Autobello Piccolina",
    "atv": "FPU Wydra",
    "barstow": "Gavril Barstow",
    "bastion": "Bruckell Bastion",
    "bluebuck": "Gavril Bluebuck",
    "bolide": "Civetta Bolide",
    "burnside": "Burnside Special",
    "covet": "Ibishu Covet",
    "citybus": "Wentward DT40L",
    "bx": "Ibishu BX-Series",
    "dryvan": "Dry Van Trailer",
    "dumptruck": "Hirochi HT-55",
    "etk800": "ETK 800 Series",
    "etkc": "ETK K Series",
    "etki": "ETK I Series",
    "fullsize": "Gavril Grand Marshal",
    "hopper": "Ibishu Hopper",
    "lansdale": "Soliad Lansdale",
    "legran": "Bruckell Legran",
    "midsize": "Newer Ibishu Pessima",
    "miramar": "Ibishu Miramar",
    "moonhawk": "Bruckell Moonhawk",
    "md_series": "Gavril MD-Series",
    "midtruck": "Autobello Stambecco",
    "nine": "Bruckell Nine",
    "pessima": "Older Ibishu Pessima",
    "pickup": "Gavril D Series",
    "pigeon": "Ibishu Pigeon",
    "racetruck": "SP Dunekicker",
    "roamer": "Gavril Roamer",
    "rockbouncer": "SP Rockbasher",
    "sbr": "Hirochi SBR4",
    "scintilla": "Civetta Scintilla",
    "sunburst2": "Hirochi Sunburst",
    "us_semi": "Gavril T Series",
    "utv": "Hirochi Aurata",
    "van": "Gavril H Series",
    "vivace": "Cherrier FCV",
    "wendover": "Soliad Wendover",
    "wigeon": "Ibishu Wigeon",
    "wl40": "Hirochi WL-40"
}

SINGLE_LAYER_VARIANTS = {
    "vivace:ardente": True,
}


def is_single_layer_variant(carid: str, variant_suffix: str) -> bool:
    if not variant_suffix:
        return True
    key = f"{carid.lower()}:{variant_suffix.strip().lower()}"
    return SINGLE_LAYER_VARIANTS.get(key, False)


REBADGE_VEHICLES = {
    "vivace:ardente": "Cherrier Ardente",
}


def get_rebadges_for(base_carid: str) -> dict:
    prefix = f"{base_carid.lower()}:"
    return {
        key[len(prefix):]: name
        for key, name in REBADGE_VEHICLES.items()
        if key.startswith(prefix)
    }


def is_rebadge_suffix(base_carid: str, suffix: str) -> bool:
    key = f"{base_carid.lower()}:{suffix.strip().lower()}"
    return key in REBADGE_VEHICLES
