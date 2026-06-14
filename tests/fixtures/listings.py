"""
Reusable sample listings for the new scoring-module tests.

Each fixture is a plain dict with the fields the scoring modules read
(title, description, price, brands, category). No DB rows required.
"""

# A clean, well-described espresso machine with strong comps.
GOOD_ESPRESSO = {
    "title": "Breville Barista Express BES870XL Espresso Machine",
    "description": "Like new, barely used. Includes portafilter and tamper.",
    "price": 280.0,
    "brands": ["Breville", "Gaggia", "Rancilio", "De'Longhi"],
    "category": "Espresso Machines",
}

# Under-described: misspelled brand + urgency + weak description.
MISSPELLED_ESPRESSO = {
    "title": "Breveille expresso maker - must go moving sale",
    "description": "works",
    "price": 90.0,
    "brands": ["Breville", "Gaggia", "Rancilio"],
    "category": "Espresso Machines",
}

# Generic one-word title hiding a possibly valuable item.
GENERIC_TITLE = {
    "title": "coffee machine",
    "description": "old, untested, need gone",
    "price": 40.0,
    "brands": ["Breville", "Gaggia"],
    "category": "Espresso Machines",
}

# A GameCube bundle worth breaking apart.
GAMECUBE_BUNDLE = {
    "title": "Nintendo GameCube console bundle with 2 controllers and 8 games",
    "description": "Includes Mario Kart Double Dash, Super Smash Bros Melee, "
                   "Luigi's Mansion, memory card, all cables. Everything pictured.",
    "price": 180.0,
    "brands": ["Nintendo"],
    "category": "gamecube",
}

# A Sonos speaker lot.
SONOS_LOT = {
    "title": "Sonos speaker lot - 2 Sonos One and a Sonos Beam",
    "description": "Moving, must sell. All work great.",
    "price": 300.0,
    "brands": ["Sonos"],
    "category": "Sonos Speakers",
}

# A tool lot bundle.
TOOL_LOT = {
    "title": "Milwaukee M18 tool lot - drill, impact driver, 3 batteries and charger",
    "description": "Garage cleanout. Cases included.",
    "price": 220.0,
    "brands": ["Milwaukee", "DeWalt", "Makita"],
    "category": "tools",
}

# A patio furniture set.
PATIO_SET = {
    "title": "Outdoor patio furniture set - table, 4 chairs, umbrella, cushions",
    "description": "Downsizing, pickup today.",
    "price": 150.0,
    "brands": [],
    "category": "Outdoor Furniture",
}
