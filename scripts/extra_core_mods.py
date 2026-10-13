#!/usr/bin/env python3
"""Hand-curated additions and removals for backend/data/processed/core_mods.json.

build_core_mods.py adds every general weapon mod whose game text parses into a
damage stat. This covers what it misses:

  - weapon-specific and set mods with plain stats (Scattered Justice, Amar's Contempt, ...)
  - mods with a condition the generic parser doesn't know (Spectral Serration, Proton Jet, ...)
  - mods whose mechanic can't be written as increment x (rank + 1): stored with
    "special": true and a description, and not applied by the engine
  - entries that are not real mods and must go (REMOVE)

Values are the max-rank card values (WFCD Mods.json, checked against the wiki's
mod data module, October 2026); maxRank comes from mods.json. Safe to re-run.
Run order: build_core_mods.py --write, extra_core_mods.py, tag_conditional_mods.py.

Usage: python scripts/extra_core_mods.py
"""

import json
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "backend" / "data" / "processed"

# Not mods in the game: absent from the game export and from the wiki's mod list.
REMOVE = [
    "Primed Serration", "Primed Hornet Strike", "Primed Point Strike", "Primed Vital Sense",
    "Primed Organ Shatter", "Primed Stormbringer", "Primed Hellfire", "Primed Deep Freeze",
    "Primed Molten Impact", "Primed Shocking Touch",
]

# name: (type override or None, [(stat, max value, condition or None)], note)
PLAIN = {
    "Amar's Contempt": (None, [("DAMAGE", 0.9, None), ("SLASH", 0.3, None)], "Dual daggers only. Amar set."),
    "Boreal's Contempt": (None, [("DAMAGE", 0.9, None), ("STATUS_DAMAGE", 0.6, None)], "Polearms only. Boreal set."),
    "Nira's Contempt": (None, [("DAMAGE", 0.9, None), ("STATUS_CHANCE", 0.6, None)], "Whips only. Nira set."),
    "Bright Purity": (None, [("DAMAGE", 1.0, None)], "Skana only."),
    "Justice Blades": (None, [("DAMAGE", 1.0, None)], "Dual Cleavers only."),
    "Deadly Sequence": (None, [("CRIT_CHANCE", 2.0, None)], "Grinlok only."),
    "Soaring Truth": (None, [("CRIT_CHANCE", 2.0, None)], "Ballistica only."),
    "Gilded Truth": (None, [("FIRE_RATE", 0.8, None)], "Burston Prime only."),
    "Scattered Justice": ("SHOTGUN", [("MULTISHOT", 2.0, None)], "Hek only."),
    "Shattering Justice": ("SHOTGUN", [("STATUS_CHANCE", 0.9, None)], "Sobek only."),
    "Gleaming Blight": (None, [("STATUS_CHANCE", 1.0, None)], "Dark Dagger only."),
    "Toxic Blight": (None, [("TOXIN", 1.0, None)], "Mire only."),
    "Toxic Sequence": (None, [("STATUS_DURATION", 2.0, None)], "Acrid only."),
    "Eroding Blight": (None, [("MAG_SIZE", 2.0, None)], "Embolist only."),
    "Stockpiled Blight": (None, [("MAG_SIZE", 2.0, None)], "Kunai only."),
    "Efficient Beams": (None, [("STATUS_CHANCE", 1.5, None)], "Convectrix only."),
    "Bhisaj-Bal": (None, [("STATUS_CHANCE", 0.9, None)], "Paris Prime only. Also restores 300 health every 3 status effects."),
    "Dizzying Rounds": ("SHOTGUN", [("STATUS_CHANCE", 2.0, None)], "Bronco only. Shots within 8m also stun."),
    "Photon Overcharge": (None, [("CRIT_DAMAGE", 0.9, None)], "Glaxion only."),
    "Amalgam Ripkas True Steel": (None, [("CRIT_CHANCE", 1.87, None)], "Ripkas only. Doubled for heavy attacks (not modelled)."),
    "Amalgam Javlok Magazine Warp": (None, [("MAG_SIZE", 0.45, None)], "Javlok only."),
    "Spectral Serration": (None, [("DAMAGE", 3.3, "while_invisible")], "Damage only while invisible."),
    "Lasting Purity": (None, [("DAMAGE", 0.6, "while_aiming")], "Vulkar only."),
    "Exposing Harpoon": (None, [("CRIT_CHANCE", 3.0, "on_hit")], "Harpak only. For 15s after pulling an enemy."),
    "Proton Jet": (None, [("STATUS_CHANCE", 1.2, "on_wall_latch"), ("CRIT_CHANCE", 1.2, "on_wall_latch")],
                   "During a wall latch."),
    "Proton Snap": (None, [("TOXIN", 1.0, "on_wall_latch"), ("STATUS_CHANCE", 0.5, "on_wall_latch")],
                    "For 20s after holding a wall latch for 2s."),
}

# name: (type override or None, mechanic). Documented only; the engine does not apply these.
SPECIAL = {
    "Flux Overdrive": (None, "Flux Rifle only. Status chance swings between +150% and +250% over 5s while the beam fires."),
    "Killing Blow": (None, "+120% melee damage on heavy attacks and +60% wind-up speed. Heavy attacks are not modelled."),
    "Corrupt Charge": (None, "+30 initial combo, -50% combo duration."),
    "True Punishment": (None, "+100% additional combo count chance, -50% combo duration."),
    "Covert Lethality": (None, "Daggers only. +16 initial combo, +100% finisher damage."),
    "Gladiator Rush": (None, "+6s combo duration. Gladiator set."),
    "Relentless Combination": (None, "Slash status damage ticks have a 100% chance to add to the melee combo counter."),
    "Meticulous Aim": (None, "Vulkar only. +105% headshot damage, -45% bodyshot damage."),
    "Hata-Satya": (None, "Soma Prime only. Each hit adds 1.2% critical chance until reload or holster."),
    "Entropy Burst": (None, "Supra only. +20 final status chance (flat points, not a multiplier)."),
    "Napalm Grenades": (None, "Penta only. +30 final status chance (flat points, not a multiplier)."),
    "Synth Charge": (None, "+200% damage on the final shot of a magazine of 6 or more. Synth set."),
    "Clip Delegation": ("SHOTGUN", "Sobek only. Next magazine gains 15% status chance and multishot per shot landed, up to 15 stacks."),
    "Motus Setup": ("SHOTGUN", "100% critical and status chance for 4s after landing from a double or bullet jump. Motus set."),
    "Deadly Maneuvers": (None, "Magnus only. After a dodge, +400% headshot critical chance for the next 2 shots."),
    "Wild Frenzy": (None, "Grakata only. Secondary fire shoots at +400% fire rate until the magazine is empty."),
    "Power Throw": (None, "Thrown melee only. +1.3 punch through; consecutive throws gain +66.7% throw damage, up to 3 stacks."),
    "Energy Channel": (None, "Converts 550% of energy spent into up to 550 bonus damage on the next melee attack."),
    "Seismic Wave": (None, "+200% slam attack damage. Slam attacks are not modelled."),
    "Finishing Touch": (None, "+165% finisher damage. Finishers are not modelled."),
    "Shattering Impact": (None, "Each hit with Impact damage removes 6 armor from the enemy."),
    "Strain Infection": (None, "+20% melee critical damage per Helminth cyst. Strain set."),
    "Enduring Affliction": (None, "+100% status chance against Lifted enemies."),
    "Master's Edge": (None, "Enables Tennokai; +60% Tennokai damage. Tennokai is not modelled."),
    "Dreamer's Wrath": (None, "Enables Tennokai; +50% opportunity chance and +32% critical damage on Tennokai attacks."),
    "Condition's Perfection": (None, "Enables Tennokai; +100% status chance on Tennokai attacks."),
    "Truth's Flame": (None, "Enables Tennokai; Tennokai kills extend the opportunity by 4s and add 120% Tennokai damage."),
    "Combustion Beam": (None, "Beam weapons. Enemies killed explode for 600 damage."),
    "Shivering Contagion": (None, "Cold status effects spread to enemies within 6m."),
    "Magnetic Welt": ("SHOTGUN", "Impact status effects have a 35% chance to also apply Magnetic (doubled below 2.5 fire rate)."),
    "Acid Shells": ("SHOTGUN", "Sobek only. Enemies explode on death for 450 Corrosive plus 45% of their max health."),
    "Thermagnetic Shells": (None, "Detron only. Enemies explode on death for 80 Magnetic plus 40% of their max health."),
    "Vulcan Blitz": (None, "Jat Kittag only. Enemies explode on death for 300 Blast plus 60% of their max health."),
    "Static Discharge": (None, "Prova only. Heavy attacks shock nearby enemies for 80% of weapon damage."),
    "Nightwatch Napalm": (None, "Ogris only. Rockets leave napalm dealing 30% damage over 6s."),
}

POLARITY = {"AP_ATTACK": "Madurai", "AP_DEFENSE": "Vazarin", "AP_TACTIC": "Naramon", "AP_POWER": "Zenurik",
            "AP_WARD": "Unairu", "AP_PRECEPT": "Penjaga", "AP_UMBRA": "Umbra"}


def main():
    core = json.loads((P / "core_mods.json").read_text(encoding="utf-8"))
    export = json.loads((P / "mods.json").read_text(encoding="utf-8"))
    mods = core["mods"]

    removed = [n for n in REMOVE if mods.pop(n, None) is not None]

    def base(name, type_override):
        src = export.get(name)
        if src is None:
            raise SystemExit(f"{name} is not in mods.json")
        return src, {
            "type": type_override or src["type"],
            "polarity": POLARITY.get(src.get("polarity"), src.get("polarity", "")),
            "rarity": (src.get("rarity") or "").title(),
            "baseDrain": src.get("baseDrain", 0),
        }

    added = []
    for name, (type_override, stats, note) in PLAIN.items():
        src, entry = base(name, type_override)
        max_rank = src.get("fusionLimit", 0)
        entry_stats = []
        for stat, value, condition in stats:
            s = {"stat": stat, "increment": round(value / (max_rank + 1), 6), "maxRank": max_rank}
            if condition:
                s["condition"], s["max_stacks"] = condition, 1
            entry_stats.append(s)
        new = {"stats": entry_stats, **entry, "note": note}
        if mods.get(name) != new:
            mods[name] = new
            added.append(name)
    for name, (type_override, mechanic) in SPECIAL.items():
        src, entry = base(name, type_override)
        new = {"maxRank": src.get("fusionLimit", 0), **entry, "special": True, "mechanic": mechanic,
               "note": mechanic + " Not applied by the calculator."}
        if mods.get(name) != new:
            mods[name] = new
            added.append(name)

    core["mods"] = mods
    with open(P / "core_mods.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(core, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"removed {len(removed)}: {', '.join(removed)}")
    print(f"added or updated {len(added)} ({len(PLAIN)} with stats, {len(SPECIAL)} special); {len(mods)} mods total")


if __name__ == "__main__":
    main()
