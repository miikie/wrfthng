#!/usr/bin/env python3
"""Tag conditional mod stats in backend/data/processed/core_mods.json so the engine can apply them.

build_core_mods.py records conditional bonuses under suffixed stat names
(CRIT_CHANCE_WHILE_AIMING, MULTISHOT_ON_KILL, ...) which the engine ignores.
This rewrites each one as the plain stat plus a condition:

    {"stat": "CRIT_CHANCE", "increment": 0.2, "maxRank": 5, "condition": "while_aiming", "max_stacks": 1}

The engine multiplies a conditional stat by the number of active stacks the
player reports (0 = off). "per_combo" stats scale with the melee combo
multiplier instead. Safe to run repeatedly; run it after build_core_mods.py.

Usage: python scripts/tag_conditional_mods.py
"""

import json
import re
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "backend" / "data" / "processed" / "core_mods.json"

SUFFIXES = {
    "_WHILE_AIMING": "while_aiming",
    "_ON_KILL": "on_kill",
    "_ON_HIT": "on_hit",
    "_ON_HEADSHOT": "on_headshot",
    "_ON_ABILITY": "on_ability",
    "_ON_RELOAD": "on_reload",
    "_ON_EQUIP": "on_equip",
    "_PER_COMBO": "per_combo",
}

# Mods whose game text needs a hand-written reading. Values are per stack at max rank.
OVERRIDES = {
    # "+40% Direct Damage per Status Type ... Stacks up to Nx" (game data, see core_mods_report.txt)
    "Galvanized Aptitude": {"GALV_STATUS_STACKS": dict(increment=0.4, maxRank=0, condition="on_kill", max_stacks=2)},
    "Galvanized Shot": {"GALV_STATUS_STACKS": dict(increment=0.4, maxRank=0, condition="on_kill", max_stacks=3)},
    "Galvanized Savvy": {"GALV_STATUS_STACKS": dict(increment=0.4, maxRank=0, condition="on_kill", max_stacks=2)},
    # "On Melee Kill: +35% Attack Speed for 10s. Stacks up to 2x." at rank 5
    "Berserker Fury": {"FIRE_RATE": dict(increment=round(0.35 / 6, 6), maxRank=5, condition="on_kill", max_stacks=2)},
    # "+40% Critical Chance stacks with Combo Multiplier" / "+40% Status Chance per Combo Multiplier"
    "Blood Rush": {"CRIT_CHANCE": dict(increment=round(0.4 / 6, 6), maxRank=5, condition="per_combo", max_stacks=1)},
    "Weeping Wounds": {"STATUS_CHANCE": dict(increment=round(0.4 / 6, 6), maxRank=5, condition="per_combo", max_stacks=1)},
}
NOTES = {
    "Blood Rush": "Critical chance per combo multiplier above 1x.",
    "Weeping Wounds": "Status chance per combo multiplier above 1x.",
    "Berserker Fury": "On melee kill: attack speed for 10s, stacks up to 2x.",
    "Galvanized Aptitude": "On kill: +40% damage per status type on the target for 20s, stacks up to 2x.",
    "Galvanized Shot": "On kill: +40% damage per status type on the target for 14s, stacks up to 3x.",
    "Galvanized Savvy": "On kill: +40% damage per status type on the target for 20s, stacks up to 2x.",
}


def stacks_from_text(text: str) -> int:
    counts = [int(n) for n in re.findall(r"[Ss]tacks up to (\d+)x", text or "")]
    return max(counts) if counts else 1


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    tagged = []
    for name, mod in data["mods"].items():
        # single-stat entries become a one-item stats list so a condition has somewhere to live
        stats = mod["stats"] if "stats" in mod else None
        single = stats is None and "stat" in mod
        if single:
            stats = [{"stat": mod["stat"], "increment": mod["increment"], "maxRank": mod["maxRank"]}]
        if not stats:
            continue
        changed = False
        for stat in stats:
            override = OVERRIDES.get(name, {}).get(stat["stat"])
            if override:
                if any(stat.get(k) != v for k, v in override.items()):
                    stat.update(override)
                    changed = True
                continue
            for suffix, condition in SUFFIXES.items():
                if stat["stat"].endswith(suffix):
                    stat["stat"] = stat["stat"][:-len(suffix)]
                    stat["condition"] = condition
                    # only "on kill" / "on hit" bonuses stack; aiming bonuses are on or off
                    stat["max_stacks"] = (stacks_from_text(mod.get("conditional", ""))
                                          if condition in ("on_kill", "on_hit") else 1)
                    changed = True
                    break
        if changed:
            if single:
                for key in ("stat", "increment", "maxRank"):
                    mod.pop(key, None)
                data["mods"][name] = {"stats": stats, **mod}
            if name in NOTES:
                data["mods"][name]["conditional"] = NOTES[name]
                data["mods"][name].pop("note", None)
            tagged.append(name)

    data["_conditions"] = {
        "while_aiming": "Active while aiming after the mod's trigger (weak point hit, kill, reload or ability cast). On or off.",
        "on_kill": "Granted on kill, up to max_stacks.",
        "on_hit": "Granted on hit, up to max_stacks.",
        "per_combo": "Scales with the melee combo multiplier above 1x. Applied automatically.",
    }
    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"tagged {len(tagged)} mods this run: {', '.join(tagged)}")
    total = sum(1 for m in data["mods"].values() if any(s.get("condition") for s in m.get("stats", [])))
    print(f"{total} conditional mods in core_mods.json")


if __name__ == "__main__":
    main()
