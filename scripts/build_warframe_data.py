#!/usr/bin/env python3
"""Build the data the survivability calculator needs.

  - Adds Warframe and aura mods that change health, shields, armor, ability
    stats or damage taken to backend/data/processed/core_mods.json
    (type "WARFRAME" / "AURA"), parsed from the game's per-rank mod text.
  - Writes backend/data/processed/warframe_survivability.json: rank 30 stats for
    every Warframe, the abilities that reduce damage taken, add armor or add a
    separate pool, and the arcanes that add armor or health.

Sources: WFCD Mods.json / Arcanes.json (per-rank text), wiki.warframe.com
Module:Warframes/data (rank 0 and rank 30 stats), and the ability values in
data/raw/wiki_abilities (scraped from wiki.warframe.com, October 2026).
Run after extra_core_mods.py. Safe to re-run.

Usage: python scripts/build_warframe_data.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_operator_companion_data as wiki  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
P = ROOT / "backend" / "data" / "processed"

POLARITY = {"AP_ATTACK": "Madurai", "AP_DEFENSE": "Vazarin", "AP_TACTIC": "Naramon", "AP_POWER": "Zenurik",
            "AP_WARD": "Unairu", "AP_PRECEPT": "Penjaga", "AP_UMBRA": "Umbra"}

# "+N% <label>" lines -> stat
PERCENT = [
    (r"^([+-][\d.]+)% Health$", "HEALTH"),
    (r"^Squad gains ([+-][\d.]+)% Maximum Health$", "HEALTH"),
    (r"^([+-][\d.]+)% Shield Capacity$", "SHIELDS"),
    (r"^([+-][\d.]+)% Armor$", "ARMOR"),
    (r"^Squad receives ([+-][\d.]+)% Armor$", "ARMOR"),
    (r"^([+-][\d.]+)% Ability Strength$", "ABILITY_STRENGTH"),
    (r"^([+-][\d.]+)% Ability Duration$", "ABILITY_DURATION"),
    (r"^([+-][\d.]+)% Ability Range$", "ABILITY_RANGE"),
    (r"^([+-][\d.]+)% Ability Efficiency$", "ABILITY_EFFICIENCY"),
    (r"^([+-][\d.]+)% Toxin Resistance$", "RESIST_TOXIN"),
    (r"^([+-][\d.]+)% Heat Resistance$", "RESIST_HEAT"),
    (r"^([+-][\d.]+)% Cold Resistance$", "RESIST_COLD"),
    (r"^([+-][\d.]+)% Electricity Resistance$", "RESIST_ELECTRICITY"),
    (r"^([+-][\d.]+)% Radiation Resistance$", "RESIST_RADIATION"),
    (r"^([+-][\d.]+)% Physical Damage Resistance$", "RESIST_PHYSICAL"),
    (r"^Reduced damage by ([\d.]+)% while airborne$", "DAMAGE_REDUCTION"),
]
# Lines that need a condition. name: (stat, max value, maxRank or None for the mod's, condition, max_stacks, note)
SPECIAL_STATS = {
    "Adaptation": ("DAMAGE_REDUCTION", 0.10, None, "on_damaged", 9,
                   "Each hit of a damage type adds resistance to that type (5% per hit at rank 0, 10% at rank 10), up to 90%."),
    "Health Conversion": ("ARMOR_FLAT", 450, None, "on_health_orb", 3,
                          "Each Health Orb adds a stack of flat armor; taking damage uses one up after 3s."),
    "Aviator": ("DAMAGE_REDUCTION", 0.40, None, "while_airborne", 1, "Only while airborne."),
    "Agility Drift": ("DAMAGE_REDUCTION", 0.12, None, "while_airborne", 1, "Only while airborne."),
}
NOTES = {
    "Catalyzing Shields": "Cuts max shields to 20% and fixes the full shield gate at 1.33s (at rank 3).",
    "Rolling Guard": "On dodge: invulnerable for 3s at max rank, 7s cooldown. Not part of the numbers.",
    "Quick Thinking": "Lethal damage drains energy instead of health at 80% efficiency (max rank). Not part of the numbers.",
    "Brief Respite": "Aura: 150% of energy spent becomes shields while overshields are inactive. Not part of the numbers.",
    "Growing Power": "Aura: +25% Ability Strength for 6s after a weapon status effect. Use the conditional toggle.",
    "Energy Conversion": "Energy Orbs give +50% Ability Strength to the next cast. Not part of the numbers.",
    "Mecha Pulse": "Killing a marked enemy gives +60% armor per enemy within 30m for 20s. Not part of the numbers.",
    "Arcane Guardian": "",
}
ALWAYS = {"Catalyzing Shields", "Rolling Guard", "Quick Thinking", "Brief Respite", "Energy Conversion", "Mecha Pulse"}
EXTRA_CONDITIONAL = {"Growing Power": ("ABILITY_STRENGTH", 0.25, "on_status", 1)}


def clean(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[A-Z_0-9]+>", "", line)).strip()


def build_mods():
    export = json.loads((P / "mods.json").read_text(encoding="utf-8"))
    core = json.loads((P / "core_mods.json").read_text(encoding="utf-8"))
    mods = core["mods"]
    by_name = {}
    for m in json.loads((RAW / "wfcd_mods.json").read_text(encoding="utf-8")):
        if m.get("type") == "Warframe Mod" and m.get("levelStats") and "/PvPMods/" not in m["uniqueName"]:
            by_name.setdefault(m["name"], m)

    added = []
    for name, m in sorted(by_name.items()):
        src = export.get(name)
        if not src or src.get("isAugment") or src.get("type") not in ("WARFRAME", "AURA"):
            continue
        levels = m["levelStats"]
        max_rank = len(levels) - 1
        stats = []
        for line in [clean(x) for raw in levels[-1]["stats"] for x in raw.replace("\\n", "\n").split("\n")]:
            for pattern, stat in PERCENT:
                hit = re.match(pattern, line)
                if hit:
                    entry = {"stat": stat, "increment": round(float(hit.group(1)) / 100 / (max_rank + 1), 6),
                             "maxRank": max_rank}
                    if stat == "DAMAGE_REDUCTION" and name in SPECIAL_STATS:
                        break
                    stats.append(entry)
                    break
        if name in SPECIAL_STATS:
            stat, value, _, condition, stacks, note = SPECIAL_STATS[name]
            stats = [{"stat": stat, "increment": round(value / (max_rank + 1), 6), "maxRank": max_rank,
                      "condition": condition, "max_stacks": stacks}]
        if name in EXTRA_CONDITIONAL:
            stat, value, condition, stacks = EXTRA_CONDITIONAL[name]
            stats = [{"stat": stat, "increment": round(value / (max_rank + 1), 6), "maxRank": max_rank,
                      "condition": condition, "max_stacks": stacks}]
        if not stats and name not in ALWAYS:
            continue
        entry = {
            "type": src["type"], "polarity": POLARITY.get(src.get("polarity"), src.get("polarity", "")),
            "rarity": (src.get("rarity") or "").title(), "baseDrain": src.get("baseDrain", 0),
        }
        if stats:
            entry = {"stats": stats, **entry}
        else:
            entry = {"maxRank": max_rank, **entry, "special": True}
        note = NOTES.get(name) or (SPECIAL_STATS[name][5] if name in SPECIAL_STATS else "")
        if name.startswith("Umbral "):
            note = "Umbral set: each other Umbral mod equipped raises this mod's value (x1.25 with two, x1.75 with three)."
        if note:
            entry["note"] = note
        if mods.get(name) != entry:
            mods[name] = entry
            added.append(name)
    with open(P / "core_mods.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(core, f, indent=2, ensure_ascii=False)
        f.write("\n")
    total = sum(1 for v in mods.values() if v.get("type") in ("WARFRAME", "AURA"))
    print(f"warframe mods: {len(added)} added or updated, {total} in core_mods.json")


# ----------------------------------------------------------------------------
# Abilities that change damage taken. Values are max rank, from data/raw/wiki_abilities.
#   kind "dr":     damage reduction (or redirection away from the Warframe)
#   kind "armor":  bonus armor, "percent" of base or "flat" points
#   kind "pool":   a separate pool that is hit before shields and health
#   scales: True  = value multiplied by Ability Strength
#   level:  a 0-1 slider (meter, battery); stacks: a count
# ----------------------------------------------------------------------------
def dr(name, value, cap=None, scales=True, stacks=None, per_stack=None, level=None, low=None, note="", applies="all"):
    return {"kind": "dr", "name": name, "value": value, "cap": cap, "scalesWithStrength": scales,
            "stacks": stacks, "perStack": per_stack, "level": level, "low": low, "note": note, "applies": applies}


def armor(name, value, mode, cap=None, scales=True, stacks=None, per_stack=None, level=None, note=""):
    return {"kind": "armor", "name": name, "value": value, "mode": mode, "cap": cap, "scalesWithStrength": scales,
            "stacks": stacks, "perStack": per_stack, "level": level, "low": None, "note": note, "applies": "all"}


def pool(name, base, armor_multiplier=0.0, cap=None, scales=True, note=""):
    return {"kind": "pool", "name": name, "value": base, "armorMultiplier": armor_multiplier, "cap": cap,
            "scalesWithStrength": scales, "stacks": None, "perStack": None, "level": None, "low": None,
            "note": note, "applies": "all"}


ABILITIES = {
    "Baruuk": [
        dr("Desolate Hands", 0.0, cap=0.90, scales=False, stacks={"label": "Daggers", "max": 9, "default": 8},
           per_stack=0.10, note="10% per dagger in the ring. 8 daggers at base; Ability Strength adds daggers, not strength per dagger."),
        dr("Serene Storm", 0.25, cap=0.40, note="While Serene Storm is active."),
    ],
    "Citrine": [dr("Preserving Shell", 0.40, cap=0.90, stacks={"label": "Kills since cast", "max": 30, "default": 0},
                   per_stack=0.03, note="Starts at 40% and decays toward 25%; each kill adds 3%. Shown without decay.")],
    "Ember": [dr("Immolation", 0.85, cap=0.90, low=0.40, level={"label": "Heat meter", "default": 1.0},
                 note="40% on cast rising to 85% at full heat, before Ability Strength.")],
    "Follie": [dr("Self Portrait", 0.50, cap=0.90, low=0.10, level={"label": "Effigy growth", "default": 1.0},
                  note="Starts at 10% and grows to its maximum as the effigy grows.")],
    "Gara": [dr("Splinter Storm", 0.70, cap=0.90, note="The 90% cap is the wiki's stated limit for Splinter Storm.")],
    "Gauss": [dr("Kinetic Plating", 1.00, cap=1.00, low=0.20, level={"label": "Battery", "default": 0.8},
                 note="20% at empty battery to 100% at full, capped at 50% when empty. Only against Impact, Puncture, "
                      "Slash, Heat, Cold and Blast.", applies="kinetic")],
    "Jade": [dr("Glory on High", 0.35, cap=0.50, note="While airborne in Glory on High.")],
    "Kullervo": [dr("Collective Curse", 0.50, cap=None, note="Share of damage redirected to cursed enemies while any are alive.")],
    "Mesa": [dr("Shatter Shield", 0.80, cap=0.95, note="Only against enemy gunfire, not melee or area damage.", applies="ranged")],
    "Mirage": [dr("Eclipse (Lunar)", 0.75, cap=0.90, note="Tap cast. The hold cast gives a damage bonus instead.")],
    "Nezha": [
        dr("Warding Halo", 0.90, cap=0.90, scales=False, note="90% of damage is redirected to the halo while it lasts."),
        pool("Warding Halo ring", 1000, armor_multiplier=2.5,
             note="Ring health = (1,000 + 250% of armor) x Ability Strength. Damage absorbed during the 3s cast adds more."),
    ],
    "Nidus": [dr("Parasitic Link", 0.50, cap=None, note="Share of damage redirected to the linked enemy.")],
    "Nova": [dr("Null Star", 0.0, cap=0.90, stacks={"label": "Particles", "max": 18, "default": 12}, per_stack=0.05,
                note="5% per orbiting particle (scaled by Ability Strength), 12 particles at base.")],
    "Sirius & Orion": [dr("Light's Sanctuary", 0.45, cap=0.75, low=0.15, level={"label": "Charge", "default": 1.0})],
    "Orion & Sirius": [dr("Light's Sanctuary", 0.45, cap=0.75, low=0.15, level={"label": "Charge", "default": 1.0})],
    "Trinity": [
        dr("Blessing", 0.50, cap=0.75),
        dr("Link", 0.75, cap=0.75, scales=False, note="Share of damage redirected to linked enemies."),
    ],
    "Yareli": [dr("Merulina", 0.90, cap=0.90, scales=False, note="90% of damage is redirected to Merulina while riding.")],
    "Chroma": [
        armor("Elemental Ward (Cold)", 1.45, "percent", note="Cold energy colour only."),
        armor("Vex Armor (Scorn)", 3.50, "percent", level={"label": "Scorn built up", "default": 1.0},
              note="Builds as shields are hit or on melee kills, up to 350% x Ability Strength."),
    ],
    "Inaros": [armor("Scarab Shell", 350, "flat", level={"label": "Shell charge", "default": 1.0})],
    "Octavia": [armor("Metronome (Nocturne)", 0.35, "percent")],
    "Oberon": [armor("Reckoning", 5, "flat", cap=1000, stacks={"label": "Radiation procs", "max": 200, "default": 50},
                     per_stack=5, note="5 armor per Radiation status applied, capped at 1,000.")],
    "Hydroid": [armor("Plunder", 40, "flat", stacks={"label": "Corrosive statuses", "max": 50, "default": 10}, per_stack=40)],
    "Valkyr": [armor("Warcry", 0.50, "percent", note="Tripled while Hysteria is active (not modelled).")],
    "Wukong": [armor("Defy", 1500, "flat", cap=1500, scales=False, level={"label": "Damage absorbed", "default": 1.0},
                     note="100 to 1,500 armor depending on damage taken during the 2s stance.")],
    "Vauban": [armor("Bastille", 1500, "flat", cap=1500, scales=False, level={"label": "Armor stolen", "default": 1.0},
                     note="Armor taken from enemies held in Bastille, up to 1,500.")],
    "Rhino": [pool("Iron Skin", 1200, armor_multiplier=2.5,
                   note="Overguard = (1,200 + 250% of armor) x Ability Strength. Damage absorbed in the 3s after casting adds more.")],
    "Dante": [pool("Light Verse Overguard", 15000, scales=True, note="Overguard cap; each cast adds 350 x Ability Strength.")],
    "Kullervo ": [],
    "Narin": [pool("Naraemagi Overguard", 15000, scales=True, note="Overguard cap; built by absorbing Cold statuses at full shields.")],
    "Nyx": [pool("Psychic Bolts Overguard", 7500, scales=True, note="Overguard stolen from enemies, up to the cap.")],
}
ABILITIES["Kullervo"].append(pool("Recompense Overguard", 10000, scales=True, note="Overguard cap; 350 per dagger hit."))
del ABILITIES["Kullervo "]

# Passives are added by build_passives.py, so they are not listed here.
SPECIAL = {
    "Revenant": ["Mesmer Skin: 6 charges at base (x Ability Strength, rounded up). Each charge blocks one hit completely, so damage reduction doesn't describe it."],
    "Harrow": ["Covenant: 6s of invulnerability for the squad (x Ability Duration)."],
    "Baruuk": ["Elude: 100% dodge chance against projectiles and melee within a 180° arc in front, only while not attacking. It is evasion, not damage reduction."],
    "Octavia": ["Metronome's Nocturne grants invisibility, which stops most damage at the source."],
    "Protea": ["Temporal Anchor rewinds health, shields and energy. Shield Satellites restore shields."],
    "Xaku": ["The Vast Untime: 75% dodge chance and area damage reduction while active."],
    "Garuda": ["Dread Mirror blocks frontal damage while held."],
    "Frost": ["Snow Globe blocks ranged fire from outside; it protects an area, not Frost's own health pool."],
    "Mesa": ["Shatter Shield does nothing against melee or area damage."],
    "Rhino": ["While Iron Skin's Overguard holds, health and shields are untouched and status effects are blocked."],
}

ARCANES = {  # name: (stat, note)
    "Arcane Guardian": ("ARMOR_FLAT", "15% chance when damaged, for 20s."),
    "Arcane Tanker": ("ARMOR_FLAT", "On Archgun equip, for 60s."),
    "Arcane Ultimatum": ("ARMOR_FLAT", "On finisher kill, for 45s."),
    "Arcane Reaper": ("ARMOR_FLAT", "On melee kill, for 10s."),
    "Arcane Blessing": ("HEALTH_FLAT", "+24 max health per Health pickup, up to 50 stacks. Shown at full stacks."),
    "Arcane Intention": ("HEALTH_FLAT", "+250 max health per active channelled ability. Shown for one."),
}


def base_of(name: str) -> str:
    return re.sub(r" (Prime|Umbra)$", "", name)


def build_survivability():
    frames = json.loads((P / "warframes.json").read_text(encoding="utf-8"))
    module = wiki.module("Module:Warframes/data")
    module = module.get("Warframes", module)
    out = {}
    for name, f in sorted(frames.items()):
        if name.startswith("<ARCHWING>"):
            continue
        w = module.get(name)
        if w:
            rank0 = {"health": w["Health"], "shields": w["Shield"], "armor": w["Armor"], "energy": w.get("Energy", 0)}
            rank30 = {"health": w.get("HealthRank30", w["Health"] + 100),
                      "shields": w.get("ShieldRank30", w["Shield"] + 100 if w["Shield"] else 0),
                      "armor": w.get("ArmorRank30", w["Armor"]),
                      "energy": w.get("EnergyRank30", w.get("Energy", 0) + 50)}
            stats_note = ""
        else:
            rank0 = {"health": f["health"], "shields": f["shield"], "armor": f["armor"], "energy": f.get("energy", 0)}
            rank30 = dict(rank0)
            stats_note = "Rank 30 stats are not on the wiki for this unit; the game export's base values are used."
        base = base_of(name)
        out[name] = {
            "name": name, "rank0": rank0, "rank30": rank30, "statsNote": stats_note,
            "abilities": ABILITIES.get(name, ABILITIES.get(base, [])),
            "special": SPECIAL.get(name, SPECIAL.get(base, [])),
        }

    arcanes = []
    for a in json.loads((RAW / "wfcd_arcanes.json").read_text(encoding="utf-8")):
        if a["name"] not in ARCANES or not a.get("levelStats"):
            continue
        stat, note = ARCANES[a["name"]]
        per_rank = []
        for level in a["levelStats"]:
            text = " ".join(level["stats"])
            pattern = r"\+([\d,]+) Armor" if stat == "ARMOR_FLAT" else r"\+([\d,]+) Max Health"
            n = re.search(pattern, text)
            value = float(n.group(1).replace(",", "")) if n else 0.0
            if a["name"] == "Arcane Blessing":
                value *= 50
            per_rank.append(value)
        arcanes.append({"name": a["name"], "stat": stat, "perRank": per_rank, "maxRank": len(per_rank) - 1, "note": note})

    data = {
        "_about": "Built by scripts/build_warframe_data.py. Ability values are max rank, from the wiki ability pages.",
        "warframes": out, "arcanes": sorted(arcanes, key=lambda a: a["name"]),
    }
    with open(P / "warframe_survivability.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with_abilities = sum(1 for v in out.values() if v["abilities"])
    print(f"survivability: {len(out)} warframes ({with_abilities} with abilities), {len(arcanes)} arcanes")
    missing = [n for n in out if out[n]["statsNote"]]
    print(f"  no wiki rank 30 stats for: {missing}")


if __name__ == "__main__":
    build_mods()
    build_survivability()
