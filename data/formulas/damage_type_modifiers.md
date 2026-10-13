# Damage Type Modifiers (Damage 3.0 - Post Update 36.0)
# Source: https://wiki.warframe.com/w/Damage/Overview_Table
# Source: https://wiki.warframe.com/w/Damage_Type_Modifier

# As of Update 36.0 (2024-06-18), the old per-health-type system
# (Cloned Flesh, Ferrite Armor, Alloy Armor, Proto Shield, etc.)
# was REPLACED with a simplified per-faction system.
#
# Vulnerable (+) = x1.5 incoming damage multiplier
# Resistant (-) = x0.5 incoming damage multiplier
# Neutral (blank) = x1.0

# Format: {faction: {damage_type: multiplier}}
# Only non-1.0 values listed

FACTION_MODIFIERS = {
    "Grineer": {
        "Impact": 1.5,
        "Corrosive": 1.5,
    },
    "Kuva Grineer": {
        "Impact": 1.5,
        "Corrosive": 1.5,
        "Heat": 0.5,
    },
    "Corpus": {
        "Puncture": 1.5,
        "Magnetic": 1.5,
    },
    "Corpus Amalgam": {
        "Electricity": 1.5,
        "Magnetic": 1.5,
        "Blast": 0.5,
    },
    "Infested": {
        "Slash": 1.5,
        "Heat": 1.5,
    },
    "Infested Deimos": {
        "Blast": 1.5,
        "Gas": 1.5,
        "Viral": 0.5,
    },
    "Orokin": {
        "Puncture": 1.5,
        "Viral": 1.5,
        "Radiation": 0.5,
    },
    "Sentient": {
        "Cold": 1.5,
        "Radiation": 1.5,
        "Corrosive": 0.5,
    },
    "Narmer": {
        "Slash": 1.5,
        "Toxin": 1.5,
        "Magnetic": 0.5,
    },
    "The Murmur": {
        "Electricity": 1.5,
        "Radiation": 1.5,
        "Viral": 0.5,
    },
    "Zariman": {
        "Void": 1.5,
    },
    "Scaldra": {
        "Impact": 1.5,
        "Corrosive": 1.5,
        "Gas": 0.5,
    },
    "Techrot": {
        "Gas": 1.5,
        "Magnetic": 1.5,
        "Cold": 0.5,
    },
    "Anarchs": {
        "Impact": 1.5,
        "Electricity": 1.5,
        "Radiation": 0.5,
    },
    "Tenno": {
        # No modifiers
    },
}

# DAMAGE TYPES AND COMBINATIONS
ELEMENTAL_COMBINATIONS = {
    ("Heat", "Cold"): "Blast",
    ("Electricity", "Toxin"): "Corrosive",
    ("Heat", "Toxin"): "Gas",
    ("Cold", "Electricity"): "Magnetic",
    ("Heat", "Electricity"): "Radiation",
    ("Cold", "Toxin"): "Viral",
}

# COMBINATION PRIORITY (mod slot order matters)
# Elements combine left-to-right in mod slot order
# Innate weapon elements combine last (rightmost)
# If weapon has innate combined element, it won't split

# STATUS EFFECT SPECIAL PROPERTIES
STATUS_EFFECTS = {
    "Impact": "Stagger; Increase Parazon Mercy threshold",
    "Puncture": "Enemy Damage Reduced; Amplified Crit Chance",
    "Slash": "Bleed DoT (ignores armor, deals Cinematic/True damage)",
    "Cold": "Slow/Freeze; Amplified Crit Damage",
    "Electricity": "Tesla Chain DoT; Stun",
    "Heat": "Burn DoT; Panic; Reduce Armor (50% strip over 10 stacks)",
    "Toxin": "Poison DoT; Ignores Shields",
    "Blast": "Stack-and-detonate (max 10 stacks, bosses 4); 5m radial on detonation",
    "Corrosive": "Reduce Armor (max 10 stacks, 80% total strip)",
    "Gas": "Gas Cloud AoE DoT",
    "Magnetic": "Amplified Damage to Shields/Overguard/Nullifier Bubbles; Negates Shield Regen",
    "Radiation": "Friendly Fire (confused enemies attack allies)",
    "Viral": "Amplified Damage to Health (100% at 1 stack, +25% per additional, max 325% at 10)",
    "Void": "Bullet Attract",
    "Tau": "Status Vulnerability",
    "True": "No modifier interactions; ignores all defenses",
    "Finisher": "Ignores all defenses",
}

# DAMAGE RESISTANCE STACKING (Post Update 30.5)
# Multiple sources of damage type resistance stack MULTIPLICATIVELY
# on "damage remaining" basis, not additively
# Example: 4x 25% DR = 0.75^4 = 31.5% damage taken (68.5% DR)
# NOT 100% DR as it would be additively
