#!/usr/bin/env python3
"""Complete and verify core_mods.json from per-rank game data.

Per-rank mod values are published in the WFCD warframe-items dataset
(https://github.com/WFCD/warframe-items, data/json/Mods.json), which carries
the game's own `levelStats` text for every rank of every mod.

Usage:
    python scripts/build_core_mods.py            # report only
    python scripts/build_core_mods.py --write    # also update core_mods.json

The script never rewrites an existing entry's values on its own; mismatches
against game data are reported and fixed through the FIXES table below.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "backend" / "data" / "processed"
CACHE = ROOT / "data" / "raw" / "wfcd_mods.json"
SOURCE_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/Mods.json"

# Which loadout class a mod belongs to, by the weapon family it fits.
# Mods for a single weapon, stances, claws, tomes etc. are out of scope.
COMPAT_TO_TYPE = {
    "Rifle": "PRIMARY", "Assault Rifle": "PRIMARY", "Sniper": "PRIMARY",
    "Bow": "PRIMARY", "PRIMARY": "PRIMARY",
    "Shotgun": "SHOTGUN", "Pistol": "SECONDARY", "Melee": "MELEE",
}
RESTRICTED_COMPAT = {"Assault Rifle": "Assault rifles only", "Sniper": "Sniper rifles only", "Bow": "Bows only"}

ELEMENTS = {
    "FIRE": "HEAT", "FREEZE": "COLD", "ELECTRICITY": "ELECTRICITY", "POISON": "TOXIN",
    "RADIATION": "RADIATION", "MAGNETIC": "MAGNETIC", "VIRAL": "VIRAL",
    "IMPACT": "IMPACT", "PUNCTURE": "PUNCTURE", "SLASH": "SLASH",
}

# "+N% <label>" lines, in the game's wording.
PERCENT_STATS = {
    "Damage": "DAMAGE", "Melee Damage": "DAMAGE",
    "Multishot": "MULTISHOT",
    "Critical Chance": "CRIT_CHANCE", "Critical Damage": "CRIT_DAMAGE",
    "Status Chance": "STATUS_CHANCE", "Status Duration": "STATUS_DURATION",
    "Status Damage": "STATUS_DAMAGE",
    "Fire Rate": "FIRE_RATE", "Attack Speed": "FIRE_RATE",
    "Reload Speed": "RELOAD_SPEED", "Magazine Capacity": "MAG_SIZE",
    "Accuracy": "ACCURACY",
    "Weak Point Damage": "WEAK_POINT_DAMAGE", "to Headshot Multiplier": "WEAK_POINT_DAMAGE",
    "Headshot Damage": "WEAK_POINT_DAMAGE",
    "Heavy Attack Efficiency": "COMBO_EFFICIENCY",
    "Damage on first shot in Magazine": "DAMAGE_FIRST_SHOT",
    "Melee Damage per Status Type affecting the target": "CONDITION_OVERLOAD",
    "Direct Damage per Status Type affecting the target": "GALV_STATUS_STACKS",
    "Critical Chance stacks with Combo Multiplier": "CRIT_CHANCE_PER_COMBO",
    "Status Chance per Combo Multiplier": "STATUS_CHANCE_PER_COMBO",
    "Critical Chance for Slide Attack": "CRIT_CHANCE_SLIDE",
    "chance to apply <DT_SLASH_COLOR> on Critical": "SLASH_ON_CRIT",
}

FACTIONS = {"Grineer": "GRINEER", "Corpus": "CORPUS", "Infested": "INFESTED",
            "Orokin": "OROKIN", "Murmur": "MURMUR", "Sentients": "SENTIENT"}

# Stats the damage pipeline cares about (directly or once conditions are modelled).
# A mod is added only if it carries at least one of these.
RELEVANT = {
    "DAMAGE", "MULTISHOT", "CRIT_CHANCE", "CRIT_DAMAGE", "STATUS_CHANCE", "STATUS_DAMAGE",
    "STATUS_DURATION", "FIRE_RATE", "RELOAD_SPEED", "MAG_SIZE", "IMPACT", "PUNCTURE", "SLASH", "HEAT", "COLD", "ELECTRICITY", "TOXIN",
    "RADIATION", "MAGNETIC", "VIRAL", "WEAK_POINT_DAMAGE", "CONDITION_OVERLOAD",
    "GALV_STATUS_STACKS", "DAMAGE_FIRST_SHOT", "CRIT_CHANCE_PER_COMBO",
    "STATUS_CHANCE_PER_COMBO", "CRIT_CHANCE_SLIDE", "SLASH_ON_CRIT",
}

# Trigger text -> suffix for conditional stats ("On Kill:\n+30% Multishot ..." -> MULTISHOT_ON_KILL).
TRIGGERS = [
    (r"when Aiming", "WHILE_AIMING"),
    (r"^On (Melee |Weak Point )?Kill", "ON_KILL"),
    (r"^On Ability Cast", "ON_ABILITY"),
    (r"^On Reload", "ON_RELOAD"),
    (r"^On Weak Point Hit|^On Headshot", "ON_HEADSHOT"),
    (r"^On Hit|^On \d+ Hits", "ON_HIT"),
    (r"^On Equip", "ON_EQUIP"),
]

# Added even though none of their stats feed the damage pipeline: the rest of
# their family is in the database, or they change which status effects occur.
ALWAYS_INCLUDE = {"Galvanized Acceleration", "Galvanized Reflex", "Internal Bleeding", "Hemorrhage"}

# No per-rank text exists for these in the dataset; values are the in-game card values.
MANUAL = {}
for _faction, _key in [("Grineer", "GRINEER"), ("Corpus", "CORPUS"), ("Infested", "INFESTED"),
                       ("Orokin", "OROKIN"), ("The Murmur", "MURMUR")]:
    MANUAL[f"Bane of {_faction}"] = (f"FACTION_{_key}", 0.05, 5)          # x1.30 at rank 5
    MANUAL[f"Primed Bane of {_faction}"] = (f"FACTION_{_key}", 0.05, 10)  # x1.55 at rank 10

# Existing entries whose stat keys encode how the engine models the mod
# (combo scaling, full-stack values). Their keys are kept; only plain stats
# the game lists and the file lacks are appended.
KEEP_MODEL = {
    "Blood Rush", "Weeping Wounds", "Berserker Fury",
    "Galvanized Aptitude", "Galvanized Shot", "Galvanized Savvy",
}

# Existing keys that are the same mod under an outdated or malformed name.
RENAMES = {
    "Primed Faction Grineer (Bane of Grineer)": "Primed Bane of Grineer",
    "Bane of Corrupted": "Bane of Orokin",
}

NEW_STAT_TYPES = {
    "STATUS_DAMAGE": "Damage of status effects / DoT ticks (Elementalist mods). Not applied by the engine yet",
    "WEAK_POINT_DAMAGE": "Weak point (headshot) damage bonus. Not applied automatically; engine takes weak_point_bonus",
    "DAMAGE_FIRST_SHOT": "Damage on the first shot of a magazine (Charged Chamber family). Not applied by the engine",
    "RADIATION": "Radiation elemental damage from a mod. Not applied by the engine yet",
    "MAGNETIC": "Magnetic elemental damage from a mod. Not applied by the engine yet",
    "VIRAL": "Viral elemental damage from a mod. Not applied by the engine yet",
    "FACTION_OROKIN": "Faction damage vs Orokin (formerly Corrupted)",
    "FACTION_MURMUR": "Faction damage vs The Murmur",
    "FACTION_SENTIENT": "Faction damage vs Sentients",
    "CRIT_CHANCE_PER_COMBO": "Critical chance per melee combo multiplier (Blood Rush family)",
    "STATUS_CHANCE_PER_COMBO": "Status chance per melee combo multiplier (Weeping Wounds family)",
    "CRIT_CHANCE_SLIDE": "Critical chance on slide attacks (Maiming Strike)",
    "SLASH_ON_CRIT": "Chance for a critical hit to apply a Slash proc (Hunter Munitions)",
    "*_WHILE_AIMING": "Conditional: applies while aiming after the mod's trigger. Ignored by the engine",
    "*_ON_KILL": "Conditional: granted on kill, usually stacking. Ignored by the engine",
    "*_ON_ABILITY": "Conditional: granted on ability cast. Ignored by the engine",
    "*_ON_RELOAD": "Conditional: granted on reload. Ignored by the engine",
    "*_ON_HEADSHOT": "Conditional: granted on weak point hit. Ignored by the engine",
    "*_ON_HIT": "Conditional: granted on hit. Ignored by the engine",
    "*_ON_EQUIP": "Conditional: granted briefly on equip. Ignored by the engine",
}


def load_source():
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {SOURCE_URL}")
        urllib.request.urlretrieve(SOURCE_URL, CACHE)
    with open(CACHE, encoding="utf-8") as f:
        return json.load(f)


def clean(text: str) -> str:
    text = text.replace("\\n", "\n").replace("<LINE_SEPARATOR>", "").replace("<LOWER_IS_BETTER>", "")
    return re.sub(r"<DT_(\w+?)(_COLOR)?>", "", text).strip()


def parse_line(line: str):
    """One stat line -> (stat, value) or None. Percentages become fractions."""
    line = line.strip()
    m = re.match(r"^([+-])([\d.]+)% <DT_(\w+?)_COLOR>\w+$", line)
    if m and m.group(3) in ELEMENTS:
        return ELEMENTS[m.group(3)], sign(m.group(1)) * float(m.group(2)) / 100
    m = re.match(r"^x([\d.]+) Damage to (\w+)$", line)
    if m and m.group(2) in FACTIONS:
        return f"FACTION_{FACTIONS[m.group(2)]}", float(m.group(1)) - 1
    m = re.match(r"^([+-])([\d.]+) Punch Through$", line)
    if m:
        return "PUNCH_THROUGH", sign(m.group(1)) * float(m.group(2))
    m = re.match(r"^([+-])([\d.]+)s Combo Duration$", line)
    if m:
        return "COMBO_DURATION", sign(m.group(1)) * float(m.group(2))
    m = re.match(r"^([+-])([\d.]+)% (.+?)(?: \(x[\d.]+ for (?:Bows|Heavy Attacks)\))?$", line)
    if m and m.group(3) in PERCENT_STATS:
        return PERCENT_STATS[m.group(3)], sign(m.group(1)) * float(m.group(2)) / 100
    return None


def sign(s: str) -> float:
    return -1.0 if s == "-" else 1.0


def parse_entry(text: str):
    """One levelStats string -> ([(stat, value)], unparsed description or None).

    A string is either a plain stat line or a conditional block such as
    "On Kill:\\n+30% Multishot for 20s. Stacks up to 5x."
    """
    raw = text.replace("\\n", "\n")
    plain = parse_line(raw)
    if plain:
        return [plain], None

    suffix = next((s for pattern, s in TRIGGERS if re.search(pattern, raw, re.M)), None)
    if suffix:
        found = []
        for m in re.finditer(r"([+-])([\d.]+)% ((?:<DT_\w+>)?[A-Za-z ]+?)(?= when Aiming| for [\d.]+s|\n|$| and )", raw):
            base = parse_line(f"{m.group(1)}{m.group(2)}% {m.group(3).strip()}")
            if base:
                found.append((f"{base[0]}_{suffix}", base[1]))
        if found:
            # A block with two triggers repeats the stat ("On Weak Point Hit: ...
            # On Weak Point Kill: ... Stacks"); the second one is the on-kill stack.
            seen, unique = set(), []
            for stat, value in found:
                if stat in seen:
                    stat = re.sub(r"_(WHILE_AIMING|ON_[A-Z]+)$", "", stat) + "_ON_KILL"
                seen.add(stat)
                unique.append((stat, value))
            return unique, clean(text)
    return [], clean(text)


def resolve(mod: dict):
    """Game data for one mod -> {'stats': [...], 'maxRank', 'conditional', 'note', 'issues'}."""
    levels = mod["levelStats"]
    max_rank = len(levels) - 1
    per_rank = []
    descriptions = []
    for level in levels:
        row = []
        for text in level["stats"]:
            stats, description = parse_entry(text)
            row.extend(stats)
            if description and level is levels[-1]:
                descriptions.append((description, bool(stats)))
        per_rank.append(row)

    issues = []
    top = per_rank[-1]
    stats = []
    for i, (stat, value) in enumerate(top):
        increment = value / (max_rank + 1)
        # value = increment * (rank + 1) must hold at every rank (within display rounding).
        for rank, row in enumerate(per_rank):
            if i >= len(row) or row[i][0] != stat:
                issues.append(f"{stat}: missing at rank {rank}")
                break
            tolerance = 0.011 if abs(value) < 5 else 0.11
            if abs(row[i][1] - increment * (rank + 1)) > tolerance:
                issues.append(f"{stat}: not linear (rank {rank} is {row[i][1]:g}, expected {increment * (rank + 1):g})")
                break
        stats.append({"stat": stat, "increment": round(increment, 6), "maxRank": max_rank})

    return {
        "stats": stats,
        "maxRank": max_rank,
        "conditional": " ".join(d.replace("\n", " ") for d, parsed in descriptions if parsed),
        "note": " ".join(d.replace("\n", " ") for d, parsed in descriptions if not parsed),
        "issues": issues,
    }


def to_entry(resolved: dict, mod_type: str, source: dict, compat: str) -> dict:
    stats = resolved["stats"]
    entry = {}
    if len(stats) == 1:
        entry.update(stats[0])
    elif stats:
        entry["stats"] = stats
    else:
        entry["maxRank"] = resolved["maxRank"]
    entry["type"] = mod_type
    entry["polarity"] = (source.get("polarity") or "").capitalize()
    entry["rarity"] = (source.get("rarity") or "").capitalize()
    entry["baseDrain"] = abs(source.get("baseDrain", 0))
    if resolved["conditional"]:
        entry["conditional"] = resolved["conditional"]
    note = " ".join(x for x in (RESTRICTED_COMPAT.get(compat), resolved["note"]) if x)
    if note:
        entry["note"] = note
    return entry


def flat_stats(entry: dict):
    if "stats" in entry:
        return {s["stat"]: (s["increment"], s.get("maxRank", 0)) for s in entry["stats"]}
    if "stat" in entry:
        return {entry["stat"]: (entry["increment"], entry.get("maxRank", 0))}
    return {}


def dump(data: dict) -> str:
    """Write in the file's existing style: one compact block per mod."""
    out = ["{"]
    out.append(f'  "_comment": {json.dumps(data["_comment"])},')
    out.append('  "_statTypes": {')
    types = list(data["_statTypes"].items())
    for i, (k, v) in enumerate(types):
        out.append(f"    {json.dumps(k)}: {json.dumps(v)}{',' if i < len(types) - 1 else ''}")
    out.append("  },")
    out.append('  "mods": {')
    mods = list(data["mods"].items())
    for i, (name, entry) in enumerate(mods):
        out.append(f"    {json.dumps(name, ensure_ascii=False)}: {{")
        lines = []
        head = {k: entry[k] for k in ("stat", "increment", "maxRank") if k in entry}
        if head:
            lines.append(", ".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in head.items()))
        if "stats" in entry:
            inner = ",\n".join(f"        {json.dumps(s)}" for s in entry["stats"])
            lines.append(f'"stats": [\n{inner}\n      ]')
        meta = {k: entry[k] for k in ("type", "polarity", "rarity", "baseDrain") if k in entry}
        lines.append(", ".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in meta.items()))
        for k, v in entry.items():
            if k not in head and k not in meta and k != "stats":
                lines.append(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}")
        out.append(",\n".join(f"      {line}" for line in lines))
        out.append(f"    }}{',' if i < len(mods) - 1 else ''}")
    out.append("  }")
    out.append("}")
    return "\n".join(out) + "\n"


def main():
    write = "--write" in sys.argv
    source = load_source()
    with open(PROCESSED / "mods.json", encoding="utf-8") as f:
        export = json.load(f)
    with open(PROCESSED / "core_mods.json", encoding="utf-8") as f:
        core = json.load(f)
    mods = core["mods"]

    # Many mods exist as Beginner (flawed), Intermediate and Expert (unreleased
    # higher-rank) copies under the same display name. The obtainable mod is
    # the one outside those folders; real Primed mods live in Expert under
    # their own "Primed ..." name and have no competing copy.
    def preference(m):
        variant = re.search(r"/(Beginner|Intermediate|Expert)/", m["uniqueName"]) is not None
        return (variant, len(m["uniqueName"]))

    by_name = {}
    for m in source:
        if not m.get("levelStats") or "/PvPMods/" in m["uniqueName"]:
            continue
        best = by_name.get(m["name"])
        if best is None or preference(m) < preference(best):
            by_name[m["name"]] = m

    # --- Renames ---
    renamed = []
    for old, new in RENAMES.items():
        if old in mods and new not in mods:
            mods = {new if k == old else k: v for k, v in mods.items()}
            renamed.append((old, new))
    for old, new in RENAMES.items():
        # Stat key follows the faction's current name.
        if new in mods and mods[new].get("stat") == "FACTION_CORRUPTED":
            mods[new]["stat"] = "FACTION_OROKIN"

    # --- Verify existing entries against game data ---
    mismatches, not_in_game, fixed = [], [], []
    for name, entry in mods.items():
        game = by_name.get(name)
        if name not in export and not game and name not in MANUAL:
            not_in_game.append(name)
            continue
        if not game:
            continue
        resolved = resolve(game)
        want = {s["stat"]: (s["increment"], s["maxRank"]) for s in resolved["stats"]}
        have = flat_stats(entry)
        diffs = []
        for stat, (inc, rank) in have.items():
            if stat not in want:
                diffs.append(f"{stat} {inc}x{rank + 1} not in game data")
            elif abs(want[stat][0] * (want[stat][1] + 1) - inc * (rank + 1)) > 0.011:
                diffs.append(f"{stat}: file max {inc * (rank + 1):g} (rank {rank}), "
                             f"game max {want[stat][0] * (want[stat][1] + 1):g} (rank {want[stat][1]})")
        missing = [s for s in want if s not in have]
        if not (diffs or missing):
            continue
        mismatches.append((name, diffs, missing, game["levelStats"][-1]["stats"]))
        if resolved["issues"]:
            continue
        if name in KEEP_MODEL:
            extra = [s for s in resolved["stats"]
                     if s["stat"] not in have and not re.search(r"_(WHILE_AIMING|ON_[A-Z]+|PER_COMBO)$", s["stat"])]
            if extra:
                current = entry.pop("stats", None) or [
                    {"stat": entry.pop("stat"), "increment": entry.pop("increment"), "maxRank": entry.pop("maxRank")}]
                entry["stats"] = extra + current
                fixed.append(name)
            continue
        # The engine currently applies every FACTION_* stat against every
        # enemy, so a faction bonus the entry did not have before is recorded
        # as a note rather than a stat (it would inflate existing builds).
        new_stats = []
        for s in resolved["stats"]:
            if s["stat"].startswith("FACTION_") and s["stat"] not in have:
                faction = s["stat"].removeprefix("FACTION_").capitalize()
                entry["note"] = f"Also x{1 + s['increment'] * (s['maxRank'] + 1):.2f} damage to {faction} at max rank (not applied)."
            else:
                new_stats.append(s)
        for key in ("stat", "increment", "maxRank", "stats"):
            entry.pop(key, None)
        if len(new_stats) == 1:
            entry.update(new_stats[0])
        else:
            entry["stats"] = new_stats
        if resolved["conditional"]:
            entry["conditional"] = resolved["conditional"]
        fixed.append(name)

    # --- Add missing damage-relevant mods ---
    added, skipped_nonlinear = {}, []
    for name, info in export.items():
        if name in mods or info.get("isAugment") or "/PvPMods/" in info["uniqueName"]:
            continue
        mod_type = COMPAT_TO_TYPE.get(info["compatName"]) if info["type"] in ("PRIMARY", "SECONDARY", "MELEE") else None
        if not mod_type:
            continue
        if name in MANUAL:
            stat, increment, max_rank = MANUAL[name]
            added[name] = {
                "stat": stat, "increment": increment, "maxRank": max_rank,
                "type": mod_type,
                "polarity": {"AP_ATTACK": "Madurai", "AP_TACTIC": "Naramon", "AP_DEFENSE": "Vazarin"}.get(info["polarity"], ""),
                "rarity": info["rarity"].capitalize(), "baseDrain": info["baseDrain"],
            }
            continue
        game = by_name.get(name)
        if not game:
            continue
        resolved = resolve(game)
        bases = {re.sub(r"_(WHILE_AIMING|ON_[A-Z]+)$", "", s["stat"]) for s in resolved["stats"]}
        relevant = bases & RELEVANT or any(b.startswith("FACTION_") for b in bases)
        if not relevant and name not in ALWAYS_INCLUDE:
            continue
        if resolved["issues"]:
            skipped_nonlinear.append((name, resolved["issues"]))
            continue
        added[name] = to_entry(resolved, mod_type, game, info["compatName"])

    mods.update(added)
    core["mods"] = mods
    core["_statTypes"].update(NEW_STAT_TYPES)
    core["_statTypes"].pop("FACTION_CORRUPTED", None)

    # --- Report ---
    print(f"\nExisting entries: {len(mods) - len(added)}   added: {len(added)}   total: {len(mods)}")
    for old, new in renamed:
        print(f"renamed: {old!r} -> {new!r}")
    print(f"\nIn core_mods.json but not a mod in the game data ({len(not_in_game)}):")
    for name in not_in_game:
        print(f"  {name}")
    print(f"\nExisting entries that disagree with game data ({len(mismatches)}):")
    for name, diffs, missing, text in mismatches:
        print(f"  {name}")
        for d in diffs:
            print(f"      {d}")
        if missing:
            print(f"      game also lists: {', '.join(missing)}")
        print(f"      game text at max rank: {[clean(t) for t in text]}")
    print(f"\nCorrected to game values ({len(fixed)}): {', '.join(fixed)}")
    for name in not_in_game:
        mods[name].setdefault("note", "Not a mod in the current game data; kept from the original list.")
    print(f"\nSkipped, values do not follow increment*(rank+1) ({len(skipped_nonlinear)}):")
    for name, issues in skipped_nonlinear:
        print(f"  {name}: {issues[0]}")
    for mod_type in ("PRIMARY", "SHOTGUN", "SECONDARY", "MELEE"):
        names = sorted(n for n, e in added.items() if e["type"] == mod_type)
        print(f"\nAdded {mod_type} ({len(names)}): {', '.join(names)}")

    if write:
        with open(PROCESSED / "core_mods.json", "w", encoding="utf-8", newline="\n") as f:
            f.write(dump(core))
        print(f"\nWrote {PROCESSED / 'core_mods.json'}")


if __name__ == "__main__":
    main()
