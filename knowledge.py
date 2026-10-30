"""
knowledge.py - RecipeLang INGREDIENT KNOWLEDGE BASE

Gives the compiler domain knowledge about ingredients: their allergen /
diet TAGS, their calories, and a suggested substitute.

The tags work like "type qualifiers": the compiler propagates them through
the program and checks them against the recipe's DIET / AVOID declarations
(similar to taint analysis, where a tainted value must not reach a sink).
"""

# name -> {"tags": set, "kcal": {unit: kcal per 1 unit}, "sub": substitute}
# unit None means "per piece" (e.g. tomato = 3 means 3 pieces).
KB = {
    "rice":    {"tags": set(),            "kcal": {"cups": 200},            "sub": None},
    "oil":     {"tags": set(),            "kcal": {"tbsp": 120},            "sub": None},
    "tomato":  {"tags": set(),            "kcal": {None: 22},               "sub": None},
    "onion":   {"tags": set(),            "kcal": {None: 40},               "sub": None},
    "potato":  {"tags": set(),            "kcal": {None: 160},              "sub": None},
    "salt":    {"tags": set(),            "kcal": {"tsp": 0},               "sub": None},
    "water":   {"tags": set(),            "kcal": {"ml": 0, "cups": 0},     "sub": None},
    "sugar":   {"tags": set(),            "kcal": {"tsp": 16, "tbsp": 48},  "sub": None},
    "lentils": {"tags": set(),            "kcal": {"cups": 230},            "sub": None},
    "egg":     {"tags": {"egg"},          "kcal": {None: 70},               "sub": "tofu"},
    "butter":  {"tags": {"dairy"},        "kcal": {"tbsp": 100},            "sub": "oil"},
    "milk":    {"tags": {"dairy"},        "kcal": {"cups": 150, "ml": 0.6}, "sub": "soy_milk"},
    "paneer":  {"tags": {"dairy"},        "kcal": {"g": 3},                 "sub": "tofu"},
    "cheese":  {"tags": {"dairy"},        "kcal": {"g": 4},                 "sub": "tofu"},
    "chicken": {"tags": {"meat"},         "kcal": {"g": 1.65},              "sub": "tofu"},
    "fish":    {"tags": {"fish"},         "kcal": {"g": 1.2},               "sub": "tofu"},
    "peanut":  {"tags": {"nuts"},         "kcal": {"tbsp": 95},             "sub": "sesame"},
    "almond":  {"tags": {"nuts"},         "kcal": {"tbsp": 50},             "sub": "sesame"},
    "flour":   {"tags": {"gluten"},       "kcal": {"cups": 455},            "sub": "rice_flour"},
    "pasta":   {"tags": {"gluten"},       "kcal": {"cups": 220},            "sub": "rice"},
    "bread":   {"tags": {"gluten"},       "kcal": {None: 80},               "sub": "rice"},
    # safe substitutes used by the auto-repair pass
    "tofu":      {"tags": set(),          "kcal": {"g": 1.45, None: 90},    "sub": None},
    "sesame":    {"tags": set(),          "kcal": {"tbsp": 52},             "sub": None},
    "soy_milk":  {"tags": set(),          "kcal": {"cups": 100, "ml": 0.4}, "sub": None},
    "rice_flour":{"tags": set(),          "kcal": {"cups": 580},            "sub": None},
}

DIETS = {
    "vegetarian": {"meat", "fish"},
    "vegan": {"meat", "fish", "dairy", "egg"},
}

ALLERGENS = {"nuts", "gluten", "dairy", "egg", "fish", "meat"}


def tags_of(name):
    entry = KB.get(name)
    return set(entry["tags"]) if entry else set()


def kcal_of(name, quantity, unit):
    """Calories for this amount, or None if unknown."""
    entry = KB.get(name)
    if not entry or unit not in entry["kcal"]:
        return None
    return entry["kcal"][unit] * quantity


# ---------------------------------------------------------------------------
# Protein (grams per 1 unit) and alternative ingredients - used by contracts.py
# ---------------------------------------------------------------------------
PROTEIN = {
    "rice": {"cups": 4.3}, "oil": {"tbsp": 0}, "tomato": {None: 1}, "onion": {None: 1},
    "potato": {None: 4}, "salt": {"tsp": 0}, "water": {"ml": 0, "cups": 0},
    "sugar": {"tsp": 0, "tbsp": 0}, "lentils": {"cups": 18}, "egg": {None: 6},
    "butter": {"tbsp": 0}, "milk": {"cups": 8, "ml": 0.034}, "paneer": {"g": 0.18},
    "cheese": {"g": 0.25}, "chicken": {"g": 0.27}, "fish": {"g": 0.22},
    "peanut": {"tbsp": 4}, "almond": {"tbsp": 2}, "flour": {"cups": 13},
    "pasta": {"cups": 8}, "bread": {None: 3}, "tofu": {"g": 0.08, None: 9},
    "sesame": {"tbsp": 1.6}, "soy_milk": {"cups": 7, "ml": 0.03},
    "rice_flour": {"cups": 9},
}

# ingredient -> possible swaps the tuner may try (any must be unit-compatible)
ALTS = {
    "rice": ["lentils"], "butter": ["oil"], "cheese": ["paneer", "tofu"],
    "paneer": ["tofu"], "chicken": ["fish", "tofu"], "pasta": ["rice", "lentils"],
    "flour": ["rice_flour"], "milk": ["soy_milk"], "egg": ["tofu"],
    "peanut": ["almond", "sesame"],
}


def protein_of(name, quantity, unit):
    """Protein (g) for this amount, or None if unknown."""
    entry = PROTEIN.get(name)
    if not entry or unit not in entry:
        return None
    return entry[unit] * quantity
