#!/usr/bin/env python3
"""Turn the research data under data/raw/ into the files the app loads.

Reads data/raw/{operator,amps,companions,companion_mods} (built by
build_operator_companion_data.py) and writes to backend/data/processed/:

  companions.json         companions with stats, precepts and the weapons they can use
  companion_weapons.json  beast claws in the weapons.json schema (category "Claws")
  companion_mods.json     claws mods in the core_mods.json schema (type "CLAWS")
  amps.json               prisms, scaffolds, braces and the amp arcanes the engine models
  buffs.json              catalogue of cross-system buffs (focus, companion, set) with per-rank values

Usage: python scripts/build_app_data.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "backend" / "data" / "processed"

POLARITY = {"Madurai": "Madurai", "Naramon": "Naramon", "Vazarin": "Vazarin", "Penjaga": "Penjaga"}
CLASS_TO_MOD_TYPE = {"Rifle": "PRIMARY", "Sniper Rifle": "PRIMARY", "Sniper": "PRIMARY", "Shotgun": "SHOTGUN",
                     "Pistol": "SECONDARY", "Melee": "MELEE", "Glaive": "MELEE", "Claws (Beast)": "CLAWS"}


def load(rel):
    return json.loads((RAW / rel).read_text(encoding="utf-8"))


def write(name, data):
    with open(OUT / name, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  wrote backend/data/processed/{name}")


def ranks(mods, name, column=0):
    """Per-rank numbers of one varying value in a companion mod's text, as fractions when it is a percentage."""
    stat = mods[name]["stats"][0]
    values = stat.get("all_per_rank_values", [stat["per_rank"]])[column]
    return values


def build_companions():
    weapons = load("companions/companion_weapons.json")["weapons"]
    scaling = load("companions/companion_base_scaling.json")
    robotic = [w for w in weapons if w["usable_by"] == "Sentinels and MOAs"]
    # Modular companions: stats come from parts. Use one representative build of each.
    moa = load("companions/moas/moa_components.json")
    hound = load("companions/hounds/hound_components.json")

    def pct_of(row, key):
        return float(row[key].replace("%", "").replace("+", "")) / 100

    core = next(c for c in moa["cores"] if c["name"] == "Drex")["gilded_table_row"]
    gyro = next(g for g in moa["gyros"] if g["name"] == "Trux")["gilded_table_row"]
    moa_stats = {stat: round(350 * (1 + pct_of(core, col) + pct_of(gyro, col)), 1)
                 for stat, col in (("health", "Health Bonus"), ("shield", "Shield Bonus"), ("armor", "Armor Bonus"))}
    moa_note = ("Stats are for a gilded MOA with a Drex Core and Trux Gyro. Other cores and gyros shift each "
                "stat by 5-20%; the three always add up to 1,190.")
    hound_core = {"Bhaira Hound": "Adlet", "Dorma Hound": "Garmr", "Hec Hound": "Raiju"}

    def hound_stats(core_name):
        lines = next(c for c in hound["cores"] if c["name"] == core_name)["text"]
        return {key: float(next(l for l in lines if word in l).split()[0])
                for key, word in (("health", "Health"), ("shield", "Shields"), ("armor", "Armor"))}

    companions = {}
    for item in scaling["index"]:
        c = load("companions/" + item["file"])
        kind = c["type"]
        if c["name"].startswith("Venari"):
            continue
        if kind in ("Sentinel", "MOA"):
            usable = [w["name"] for w in robotic]
            if c["name"].startswith("Helios"):
                usable += [w["name"] for w in weapons if w["name"].startswith("Deconstructor")]
        elif kind == "Hound":
            usable = [w["name"] for w in weapons if w["usable_by"] == "Hounds only"]
        else:
            usable = [w["name"] for w in weapons if w.get("comes_with") == c["name"]]
        default = c.get("default_weapon") or (usable[0] if kind not in ("MOA",) and usable else "")
        stats_note = ""
        if kind == "MOA":
            c["base_stats"].update(moa_stats)
            stats_note = moa_note
        elif kind == "Hound":
            core_name = hound_core[c["name"]]
            c["base_stats"].update(hound_stats(core_name))
            stats_note = (f"Stats are for the {core_name} Core before bracket bonuses. Any core fits any model; "
                          "the bracket then shifts each stat by 10-30%.")
        companions[c["name"]] = {
            "name": c["name"], "type": kind, "variant": c["variant"], "description": c["description"],
            "statsNote": stats_note,
            "health": c["base_stats"]["health"] or 0, "shield": c["base_stats"]["shield"] or 0,
            "armor": c["base_stats"]["armor"] or 0,
            "precepts": [{"name": p["name"], "effect": p["effect_at_max_rank"],
                          "damageEffect": re.sub(r"\s*\(pipeline step \d+\)|\s*\(step \d+\)", "", p.get("damage_effect", ""))}
                         for p in c["precepts"]],
            "weapons": sorted(usable), "defaultWeapon": default,
            # Sentinels only fire with an attack precept; the calculator assumes one is equipped.
            "needsAttackPrecept": kind == "Sentinel",
        }
    write("companions.json", companions)

    # Beast claws as weapons. Robotic weapons are already in weapons.json; record their mod class here.
    claws, mod_types = {}, {}
    for w in weapons:
        mod_types[w["name"]] = CLASS_TO_MOD_TYPE.get(w["weapon_class"], "PRIMARY")
        if w["weapon_class"] != "Claws (Beast)":
            continue
        a = w["attacks"][0]
        claws[w["name"]] = {
            "name": w["name"], "uniqueName": w["internal_name"], "category": "Claws",
            "damage": a["damage"], "totalDamage": a["total_damage"],
            "critChance": a["crit_chance"], "critMult": a["crit_multiplier"],
            "statusChance": a["status_chance"], "fireRate": a.get("fire_rate", 1),
            "magSize": 0, "reloadTime": 0, "multishot": 1, "trigger": "", "tags": ["BEAST_WEAPON"], "masteryReq": 0,
        }
    write("companion_weapons.json", {"weapons": claws, "modTypes": mod_types})

    # Claws mods in core_mods format: only the stats the engine understands.
    engine_stats = {"DAMAGE", "CRIT_CHANCE", "CRIT_DAMAGE", "STATUS_CHANCE", "STATUS_DURATION",
                    "HEAT", "COLD", "ELECTRICITY", "TOXIN"}
    notes = {
        "Brute Conditioning": "Also converts all base physical damage to Impact (conversion not modelled).",
        "Disabling Conditioning": "Also converts all base physical damage to Puncture (conversion not modelled).",
        "Precision Conditioning": "Also converts all base physical damage to Slash (conversion not modelled).",
        "Burning Claws": "Also converts the claws' elemental damage to Heat (conversion not modelled).",
        "Chilling Claws": "Also converts the claws' elemental damage to Cold (conversion not modelled).",
        "Sepsis Claws": "Also converts the claws' elemental damage to Toxin (conversion not modelled).",
        "Shocking Claws": "Also converts the claws' elemental damage to Electricity (conversion not modelled).",
    }
    mods = {}
    for m in load("companion_mods/beast_damage_mods.json")["mods"]:
        stats = [{"stat": s["stat"], "increment": s["increment"], "maxRank": s["maxRank"]}
                 for s in m.get("stats", []) if s.get("stat") in engine_stats and s.get("increment")]
        if not stats:
            continue
        mods[m["name"]] = {"type": "CLAWS", "stats": stats, "polarity": m.get("polarity", ""),
                           "rarity": (m.get("rarity") or "").title(), "baseDrain": m.get("base_drain", 0)}
        if m["name"] in notes:
            mods[m["name"]]["note"] = notes[m["name"]]
    write("companion_mods.json", {"mods": mods})
    return companions


def build_amps():
    def part(p):
        return {
            "name": p["name"], "series": p.get("series"), "trigger": (p.get("trigger") or "").upper(),
            "energy": p.get("magazine_energy") or 100, "rechargeDelay": p.get("recharge_delay_s") or 2,
            "rechargeRate": p.get("recharge_rate_per_s") or 30,
            "attacks": [{
                "name": a["name"], "damage": a["damage"], "critChance": a.get("crit_chance", 0),
                "critMult": a.get("crit_multiplier", 1), "statusChance": a.get("status_chance", 0),
                "fireRate": a.get("fire_rate", 1), "multishot": a.get("multishot", 1),
                "ammoCost": a.get("ammo_cost", 0), "burstCount": a.get("burst_count", 1),
                "chargeTime": a.get("charge_time", 0),
                # damage is full up to `start` metres and drops to (1 - reduction) at `end`
                "falloff": ({"start": a["falloff"].get("StartRange", 0), "end": a["falloff"].get("EndRange", 0),
                             "reduction": a["falloff"].get("Reduction", 0)} if a.get("falloff") else None),
                "area": a.get("shot_type") == "AoE",
            } for a in p["attacks"]],
        }
    braces = [{"name": b["name"], "series": b["series"], "critChance": b.get("crit_chance", 0),
               "statusChance": b.get("status_chance", 0), "energy": b.get("amp_energy", 0),
               "rechargeDelay": b.get("recharge_delay_s", 0), "rechargeRate": b.get("recharge_rate_per_s", 0)}
              for b in load("amps/braces.json")["braces"]]
    # Arcanes whose effect is a plain stat bonus the pipeline can apply. Values are max rank.
    modelled = {
        "Virtuos Fury": ("DAMAGE", "+30% damage for 4s on status effect (20% chance)"),
        "Eternal Eradicate": ("DAMAGE", "+60% amp damage for 8s after an Operator ability"),
        "Virtuos Shadow": ("CRIT_CHANCE", "+60% critical chance for 12s on headshot (40% chance)"),
        "Eternal Onslaught": ("CRIT_CHANCE", "+180% critical chance for 8s when energy is depleted"),
        "Virtuos Strike": ("CRIT_DAMAGE", "+80% critical damage for 4s on critical hit (20% chance)"),
        "Virtuos Ghost": ("STATUS_CHANCE", "+60% status chance for 12s on headshot (40% chance)"),
        "Virtuos Tempo": ("FIRE_RATE", "+60% fire rate for 8s on kill (60% chance)"),
    }
    arcanes = []
    for a in load("amps/virtuous_arcanes.json")["amp_arcanes"]:
        if a["name"] not in modelled:
            continue
        stat, text = modelled[a["name"]]
        # the bonus is the last varying number, or the last number in the max-rank text
        values = a["per_rank_values"][-1] if a["per_rank_values"] else None
        arcanes.append({"name": a["name"], "stat": stat, "text": text,
                        "perRank": [v / 100 for v in values] if values else [], "maxRank": a["max_rank"]})
    write("amps.json", {
        "prisms": [part(p) for p in load("amps/prisms.json")["prisms"]],
        "scaffolds": [part(p) for p in load("amps/scaffolds.json")["scaffolds"]],
        "braces": braces, "arcanes": arcanes,
    })


def build_buffs():
    cmods = {m["name"]: m for m in load("companion_mods/companion_mod_list.json")["mods"]}
    focus = {}
    for school in ("madurai", "vazarin", "naramon", "zenurik", "unairu"):
        for n in load(f"operator/focus_{school}.json")["nodes"]:
            if n["status"] == "current":
                focus[n["name"]] = (school.title(), n)

    def frac(values):
        return [round(v / 100, 6) for v in values]

    buffs = []

    beasts = ["Kubrow", "Kavat", "Vulpaphyla", "Predasite"]

    def need(text="", companions=(), types=(), melee=False, any_companion=False):
        return {"text": text, "companions": list(companions), "companionTypes": list(types),
                "meleeWeapon": melee, "anyCompanion": any_companion}

    def add(id, name, group, kind, per_rank, text, requires=None, uptime=1.0, uptime_note="", verified=True,
            amount=None, applies_to=("weapon",)):
        buffs.append({"id": id, "name": name, "group": group, "kind": kind, "perRank": per_rank,
                      "maxRank": len(per_rank) - 1, "text": text, "requires": requires or need(),
                      "uptime": uptime, "uptimeNote": uptime_note,
                      "verified": verified, "amount": amount, "appliesTo": list(applies_to)})

    pt = focus["Phoenix Talons"][1]["per_rank_values"][0]
    add("focus.phoenix_talons", "Phoenix Talons", "Focus: Madurai", "physical_add", frac(pt),
        "Physical damage (Impact, Puncture, Slash) of Warframe weapons. For amps it is Operator damage.",
        applies_to=("weapon", "amp"))
    vs = focus["Void Strike"][1]["per_rank_values"]
    add("focus.void_strike", "Void Strike", "Focus: Madurai", "base_damage_add", frac(vs[1]),
        "Damage per 1% of Operator energy consumed, added to base damage bonuses like Serration.",
        uptime=8 / 48, uptime_note="8s of buff, then a 40s cooldown, at rank 3.",
        amount={"label": "Energy consumed (%)", "min": 1, "max": 100, "default": 100},
        applies_to=("weapon", "amp"))
    cs = focus["Caustic Strike"][1]["per_rank_values"][-1]
    add("focus.caustic_strike", "Caustic Strike", "Focus: Unairu", "armor_strip", frac(cs),
        "Strips this share of the enemy's armor.", applies_to=("enemy",))
    pw = focus["Power Transfer"][1]["per_rank_values"][0]
    add("focus.power_transfer", "Power Transfer", "Focus: Madurai", "crit_damage_add", frac(pw),
        "Amp critical damage after switching to Operator.", applies_to=("amp",))

    add("companion.cats_eye", "Cat's Eye", "Companion", "crit_chance_flat", frac(ranks(cmods, "Cat's Eye", 0)),
        "Flat critical chance points added after mods, for the whole squad.", requires=need("Adarza Kavat", companions=["Adarza Kavat"]),
        uptime=10 / 30, uptime_note="10s of buff, then a 20s cooldown.", applies_to=("weapon", "companion", "amp"))
    add("companion.charm", "Charm (critical buff)", "Companion", "crit_chance_floor", [2.0],
        "Sets a minimum critical chance of 200% while the buff lasts. Rolled at random among six Charm buffs.",
        requires=need("Smeeta Kavat", companions=["Smeeta Kavat"]), uptime=0.1,
        uptime_note="Charm triggers 40% of the time every 27s and picks one of six buffs. 10% is a rough figure.",
        applies_to=("weapon",))
    sc = ranks(cmods, "Sharpened Claws", 1)
    add("companion.sharpened_claws", "Sharpened Claws", "Companion", "armor_strip", [min(1.0, v / 100) for v in sc],
        "Kavat or Vulpaphyla attack that removes armor from one enemy.", requires=need("a Kavat or Vulpaphyla", types=["Kavat", "Vulpaphyla"]),
        applies_to=("enemy",))
    add("companion.ambush", "Ambush", "Companion", "base_damage_add", frac(ranks(cmods, "Ambush", 0)),
        "Weapon damage for 3s when Shade's cloak breaks.", requires=need("Shade", companions=["Shade", "Shade Prime", "Prisma Shade"]),
        uptime_note="Lasts 3s each time the cloak breaks. Set the uptime to match how you play.", verified=False)
    tb = ranks(cmods, "Tenacious Bond", 1)
    add("bond.tenacious", "Tenacious Bond", "Companion mod", "crit_mult_flat", list(tb),
        "Flat final critical multiplier while the companion's critical chance is 50% or more.",
        requires=need("a companion whose critical chance is 50% or more", any_companion=True))
    rb = [s for s in cmods["Reinforced Bond"]["stats"]][0]
    rb_values = rb.get("all_per_rank_values", [rb["per_rank"]])
    fire = next((v for v in rb_values if v[-1] == 60), rb_values[-1])
    add("bond.reinforced", "Reinforced Bond", "Companion mod", "fire_rate_add", frac(fire),
        "Fire rate while the companion has more than 1200 shields.", requires=need("a companion with more than 1,200 shields", any_companion=True))
    add("bond.vicious", "Vicious Bond", "Companion mod", "armor_strip", [0.15],
        "Each companion melee hit removes 15% of the enemy's armor.", requires=need("a companion that attacks in melee (a beast or Hound)", types=beasts + ["Hound"]),
        amount={"label": "Companion hits", "min": 1, "max": 7, "default": 3}, applies_to=("enemy",))
    add("aura.mecha_empowered", "Mecha Empowered", "Set: Mecha", "final_multiplier",
        [0.25, 0.5, 0.75, 1.0, 1.25, 1.5],
        "Extra damage against the enemy your Kubrow or Predasite has marked. Counts twice on damage-over-time.",
        requires=need("a Kubrow or Predasite carrying a Mecha set mod", types=["Kubrow", "Predasite"]))
    add("set.gladiator", "Gladiator set", "Set: Gladiator", "crit_per_combo", [0.10],
        "Melee critical chance per combo multiplier, per set piece. Pieces on the companion count.",
        amount={"label": "Set pieces", "min": 1, "max": 6, "default": 6}, requires=need("a melee weapon", melee=True))
    write("buffs.json", {"buffs": buffs})


def main():
    print("App data")
    build_companions()
    build_amps()
    build_buffs()


if __name__ == "__main__":
    main()
