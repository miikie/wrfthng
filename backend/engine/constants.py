"""Constants for the Warframe damage calculation engine."""

import struct
from typing import Dict, List, Tuple

# ============================================================================
# DAMAGE TYPES
# ============================================================================

PHYSICAL_TYPES = ("Impact", "Puncture", "Slash")
BASE_ELEMENTAL_TYPES = ("Heat", "Cold", "Electricity", "Toxin")
COMBINED_ELEMENTAL_TYPES = ("Blast", "Viral", "Magnetic", "Radiation", "Corrosive", "Gas")
SPECIAL_TYPES = ("Void", "Tau", "True", "Finisher")

ALL_DAMAGE_TYPES = PHYSICAL_TYPES + BASE_ELEMENTAL_TYPES + COMBINED_ELEMENTAL_TYPES + SPECIAL_TYPES

# Elemental combination rules (order matters: left-to-right in mod slots)
ELEMENTAL_COMBINATIONS: Dict[Tuple[str, str], str] = {
    ("Heat", "Cold"): "Blast",
    ("Cold", "Heat"): "Blast",
    ("Electricity", "Toxin"): "Corrosive",
    ("Toxin", "Electricity"): "Corrosive",
    ("Heat", "Toxin"): "Gas",
    ("Toxin", "Heat"): "Gas",
    ("Cold", "Electricity"): "Magnetic",
    ("Electricity", "Cold"): "Magnetic",
    ("Heat", "Electricity"): "Radiation",
    ("Electricity", "Heat"): "Radiation",
    ("Cold", "Toxin"): "Viral",
    ("Toxin", "Cold"): "Viral",
}

# Which base elements form each combined element
COMBINED_ELEMENT_COMPONENTS: Dict[str, Tuple[str, str]] = {
    "Blast": ("Heat", "Cold"),
    "Corrosive": ("Electricity", "Toxin"),
    "Gas": ("Heat", "Toxin"),
    "Magnetic": ("Cold", "Electricity"),
    "Radiation": ("Heat", "Electricity"),
    "Viral": ("Cold", "Toxin"),
}

# ============================================================================
# DAMAGE TYPE INDICES (damagePerShot array in export data)
# ============================================================================

DAMAGE_TYPE_INDICES = {
    0: "Impact", 1: "Puncture", 2: "Slash",
    3: "Heat", 4: "Cold", 5: "Electricity", 6: "Toxin",
    7: "Blast", 8: "Radiation", 9: "Gas",
    10: "Magnetic", 11: "Viral", 12: "Corrosive",
    13: "Void", 14: "Tau", 15: "Finisher",
    16: "ShieldDrain", 17: "HealthDrain",
}

# ============================================================================
# FACTION DAMAGE MODIFIERS (Damage 3.0 post-Update 36.0)
# ============================================================================
# Vulnerable = 1.5x, Resistant = 0.5x, Neutral = 1.0x

FACTION_MODIFIERS: Dict[str, Dict[str, float]] = {
    "Grineer": {"Impact": 1.5, "Corrosive": 1.5},
    "Kuva Grineer": {"Impact": 1.5, "Corrosive": 1.5, "Heat": 0.5},
    "Corpus": {"Puncture": 1.5, "Magnetic": 1.5},
    "Corpus Amalgam": {"Electricity": 1.5, "Magnetic": 1.5, "Blast": 0.5},
    "Infested": {"Slash": 1.5, "Heat": 1.5},
    "Infested Deimos": {"Blast": 1.5, "Gas": 1.5, "Viral": 0.5},
    "Orokin": {"Puncture": 1.5, "Viral": 1.5, "Radiation": 0.5},
    "Sentient": {"Cold": 1.5, "Radiation": 1.5, "Corrosive": 0.5},
    "Narmer": {"Slash": 1.5, "Toxin": 1.5, "Magnetic": 0.5},
    "The Murmur": {"Electricity": 1.5, "Radiation": 1.5, "Viral": 0.5},
    "Zariman": {"Void": 1.5},
    "Scaldra": {"Impact": 1.5, "Corrosive": 1.5, "Gas": 0.5},
    "Techrot": {"Gas": 1.5, "Magnetic": 1.5, "Cold": 0.5},
    "Anarchs": {"Impact": 1.5, "Electricity": 1.5, "Radiation": 0.5},
    "Tenno": {},
    "Stalker": {},
    "Duviri": {},
    "Unaffiliated": {},
}

# ============================================================================
# DOT COEFFICIENTS
# ============================================================================

DOT_COEFFICIENTS = {
    "Slash": 0.35,
    "Heat": 0.5,
    "Electricity": 0.5,
    "Toxin": 0.5,
    "Gas": 0.5,
}

DOT_TICKS = 6       # Number of ticks for most DoTs
DOT_DURATION = 6.0  # Base duration in seconds for Slash/Toxin/Gas
HEAT_DURATION = 6.0
ELECTRICITY_DURATION = 3.0

# ============================================================================
# ARMOR CONSTANTS
# ============================================================================

ARMOR_HARD_CAP = 2700       # Maximum armor value
ARMOR_INITIAL_MIN = 200     # Minimum initial armor (can be stripped below)
ARMOR_DR_COEFFICIENT = 0.9  # DM = 1 - 0.9 * sqrt(AR / 2700)
ARMOR_DR_REFERENCE = 2700.0 # The reference armor value

# ============================================================================
# STEEL PATH
# ============================================================================

STEEL_PATH_LEVEL_BONUS = 100
STEEL_PATH_SHIELD_MULTIPLIER = 2.5

# ============================================================================
# ENEMY LEVEL
# ============================================================================

MAX_ENEMY_LEVEL = 9999

# ============================================================================
# QUANTIZATION
# ============================================================================

QUANTIZATION_STEPS = 32  # Damage is quantized to nearest 1/32

# ============================================================================
# VIRAL STATUS BONUSES
# ============================================================================

VIRAL_BASE_BONUS = 1.0        # +100% at 1 stack
VIRAL_STACK_BONUS = 0.25      # +25% per additional stack
VIRAL_MAX_STACKS = 10
VIRAL_MAX_BONUS = 3.25        # 100% + 9*25% = 325%

# ============================================================================
# CORROSIVE ARMOR STRIP
# ============================================================================

CORROSIVE_STRIP_PER_STACK = 0.26  # ~26% per stack (multiplicative remaining)
CORROSIVE_MAX_STACKS = 10
CORROSIVE_MAX_STRIP = 0.80        # 80% total at 10 stacks

# ============================================================================
# HEAT ARMOR STRIP
# ============================================================================

HEAT_MAX_STACKS = 10          # For armor strip purpose
HEAT_MAX_STRIP = 0.50         # 50% at 10 stacks

# ============================================================================
# STAT TYPE ENUM (for mod resolution)
# ============================================================================

STAT_TYPES = {
    "DAMAGE", "MULTISHOT", "CRIT_CHANCE", "CRIT_DAMAGE",
    "STATUS_CHANCE", "STATUS_DURATION", "FIRE_RATE", "RELOAD_SPEED",
    "MAG_SIZE", "IMPACT", "PUNCTURE", "SLASH",
    "HEAT", "COLD", "ELECTRICITY", "TOXIN",
    "FACTION_GRINEER", "FACTION_CORPUS", "FACTION_INFESTED", "FACTION_CORRUPTED",
    "COMBO_DURATION", "COMBO_EFFICIENCY", "CHANNELING_DAMAGE",
    "CONDITION_OVERLOAD", "GALV_STATUS_STACKS",
    "ACCURACY", "PUNCH_THROUGH", "SPRINT_SPEED",
    # Added with the mod database expansion. Recorded on mods but not yet
    # applied by the damage pipeline (build_modded_stats ignores them).
    "FACTION_OROKIN", "FACTION_MURMUR", "FACTION_SENTIENT",
    "RADIATION", "MAGNETIC", "VIRAL",
    "STATUS_DAMAGE", "WEAK_POINT_DAMAGE", "DAMAGE_FIRST_SHOT",
    "CRIT_CHANCE_PER_COMBO", "STATUS_CHANCE_PER_COMBO", "CRIT_CHANCE_SLIDE", "SLASH_ON_CRIT",
    # Conditional bonuses: base stat + trigger suffix.
    "CRIT_CHANCE_WHILE_AIMING", "CRIT_DAMAGE_WHILE_AIMING", "STATUS_CHANCE_WHILE_AIMING",
    "FIRE_RATE_WHILE_AIMING", "CRIT_CHANCE_ON_KILL", "CRIT_DAMAGE_ON_KILL",
    "STATUS_CHANCE_ON_KILL", "MULTISHOT_ON_KILL", "FIRE_RATE_ON_KILL", "RELOAD_SPEED_ON_KILL",
    "MULTISHOT_ON_HIT", "ACCURACY_ON_HIT", "DAMAGE_ON_HIT", "FIRE_RATE_ON_HIT",
    # Warframe mods (survivability calculator)
    "HEALTH", "SHIELDS", "ARMOR", "ARMOR_FLAT", "DAMAGE_REDUCTION",
    "ABILITY_STRENGTH", "ABILITY_RANGE", "ABILITY_DURATION", "ABILITY_EFFICIENCY",
    "RESIST_TOXIN", "RESIST_HEAT", "RESIST_COLD", "RESIST_ELECTRICITY", "RESIST_RADIATION", "RESIST_PHYSICAL",
}

# Stat to damage type mapping for elementals
STAT_TO_ELEMENT = {
    "HEAT": "Heat",
    "COLD": "Cold",
    "ELECTRICITY": "Electricity",
    "TOXIN": "Toxin",
}

# Stat to physical type mapping
STAT_TO_PHYSICAL = {
    "IMPACT": "Impact",
    "PUNCTURE": "Puncture",
    "SLASH": "Slash",
}

# ============================================================================
# WEAPON CATEGORIES
# ============================================================================

PRIMARY_CATEGORIES = {"LongGuns"}
SECONDARY_CATEGORIES = {"Pistols"}
MELEE_CATEGORIES = {"Melee"}
SHOTGUN_TAGS = {"SHOTGUN", "SECONDARYSHOTGUN"}

# Mod type to weapon category compatibility
MOD_TYPE_COMPAT = {
    "PRIMARY": {"LongGuns"},
    "SECONDARY": {"Pistols"},
    "MELEE": {"Melee"},
    "SHOTGUN": {"LongGuns", "Pistols"},  # Shotguns can be primary or secondary
}

# ============================================================================
# FLOAT32 HELPER
# ============================================================================

def f32(x: float) -> float:
    """Convert a float64 to float32 precision (IEEE 754 binary32).

    The game uses float32 for most calculations. This ensures our
    intermediate results match the game's rounding behavior.
    """
    return struct.unpack('f', struct.pack('f', x))[0]
