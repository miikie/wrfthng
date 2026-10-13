# Processes warframe-public-export-plus JSON into cleaned databases for the calc engine
import json
import os
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "warframe-public-export-plus"
OUT_DIR = Path(__file__).parent.parent / "backend" / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DAMAGE_TYPE_INDICES = {
    0: "Impact", 1: "Puncture", 2: "Slash",
    3: "Heat", 4: "Cold", 5: "Electricity", 6: "Toxin",
    7: "Blast", 8: "Radiation", 9: "Gas", 10: "Magnetic",
    11: "Viral", 12: "Corrosive", 13: "Void", 14: "Tau",
    15: "Finisher", 16: "ShieldDrain", 17: "HealthDrain",
}

DT_KEY_MAP = {
    "DT_IMPACT": "Impact", "DT_PUNCTURE": "Puncture", "DT_SLASH": "Slash",
    "DT_FIRE": "Heat", "DT_FREEZE": "Cold", "DT_ELECTRICITY": "Electricity",
    "DT_POISON": "Toxin", "DT_EXPLOSION": "Blast", "DT_RADIATION": "Radiation",
    "DT_GAS": "Gas", "DT_MAGNETIC": "Magnetic", "DT_VIRAL": "Viral",
    "DT_CORROSIVE": "Corrosive", "DT_RADIANT": "Void", "DT_SENTIENT": "Tau",
    "DT_FINISHER": "Finisher", "DT_SHIELD_DRAIN": "ShieldDrain",
    "DT_HEALTH_DRAIN": "HealthDrain",
}

FACTION_MAP = {
    "FC_GRINEER": "Grineer", "FC_CORPUS": "Corpus", "FC_INFESTATION": "Infested",
    "FC_OROKIN": "Orokin", "FC_SENTIENT": "Sentient", "FC_NARMER": "Narmer",
    "FC_MITW": "The Murmur", "FC_SCALDRA": "Scaldra", "FC_TECHROT": "Techrot",
    "FC_RED_VEIL": "Stalker", "FC_DUVIRI": "Duviri", "FC_TENNO": "Tenno",
    "Stalker": "Stalker", "Grineer": "Grineer", "Corpus": "Corpus",
    "Infested": "Infested", "Infestation": "Infested", "Orokin": "Orokin",
    "Orokin Empire": "Orokin", "OrokinEmpire": "Orokin",
    "Sentient": "Sentient", "Narmer": "Narmer", "NarmerVeil": "Narmer",
    "Murmur": "The Murmur", "MITW": "The Murmur",
    "Scaldra": "Scaldra", "Techrot": "Techrot",
    "Anarch": "Anarchs", "Red Veil": "Stalker",
    "TENNO": "Tenno", "Tenno": "Tenno",
    "Duviri": "Duviri", "ENEMY": "Unaffiliated",
    "Neutral": "Unaffiliated", "NEUTRAL": "Unaffiliated",
    "Special": "Unaffiliated", "None": "Unaffiliated",
    "Prey": "Unaffiliated", "Dummy": "Unaffiliated",
    "Ash": "Unaffiliated", "Garuda": "Unaffiliated",
}

MISSION_TYPE_MAP = {
    "MT_SURVIVAL": "Survival", "MT_DEFENSE": "Defense", "MT_EXTERMINATION": "Exterminate",
    "MT_SABOTAGE": "Sabotage", "MT_CAPTURE": "Capture", "MT_INTEL": "Spy",
    "MT_MOBILE_DEFENSE": "Mobile Defense", "MT_RESCUE": "Rescue",
    "MT_ASSASSINATION": "Assassination", "MT_EXCAVATION": "Excavation",
    "MT_HIVE": "Hive", "MT_ARTIFACT": "Disruption", "MT_TERRITORY": "Interception",
    "MT_PURSUIT": "Pursuit", "MT_SECTOR": "Dark Sector",
    "MT_RETRIEVAL": "Hijack", "MT_ALCHEMY": "Alchemy",
    "MT_VOID_CASCADE": "Void Cascade", "MT_VOID_FLOOD": "Void Flood",
    "MT_VOID_ARMAGEDDON": "Void Armageddon", "MT_JUNCTION": "Junction",
    "MT_ASSAULT": "Assault", "MT_RELAY": "Relay",
    "MT_LANDSCAPE": "Free Roam", "MT_RAILJACK": "Railjack",
    "MT_ARENA": "Arena", "MT_INFESTED_SALVAGE": "Infested Salvage",
    "MT_DEFECTION": "Defection", "MT_ORPHIX": "Orphix",
    "MT_CORRUPTION": "Void Fissure", "MT_SKIRMISH": "Skirmish",
    "MT_VOLATILE": "Volatile", "MT_ENDLESS_EXTERMINATION": "Mirror Defense",
    "MT_ASCENSION": "Ascension",
}


def load_json(filename):
    with open(RAW_DIR / filename) as f:
        return json.load(f)


def load_lang():
    with open(RAW_DIR / "dict.en.json") as f:
        return json.load(f)


def resolve_name(lang, name_path):
    if not name_path:
        return ""
    return lang.get(name_path, name_path.split("/")[-1])


def parse_damage_array(arr):
    if not arr:
        return {}
    result = {}
    for i, val in enumerate(arr):
        if val and i in DAMAGE_TYPE_INDICES:
            result[DAMAGE_TYPE_INDICES[i]] = round(val, 4)
    return result


def parse_dt_dict(d):
    result = {}
    for k, v in d.items():
        if k in DT_KEY_MAP and isinstance(v, (int, float)):
            result[DT_KEY_MAP[k]] = round(v, 4)
    return result


def process_enemies():
    print("Processing enemies...")
    data = load_json("ExportEnemies.json")
    lang = load_lang()

    agents = data["agents"]
    avatars = data["avatars"]
    damage_controllers = data["damageControllers"]
    hit_proxies = data.get("hitProxies", {})

    enemies = {}
    for agent_key, agent in agents.items():
        base_level = agent.get("baseLevel", 1)
        avatar_types = agent.get("avatarTypes", {})

        for variant_type, avatar_key in avatar_types.items():
            avatar = avatars.get(avatar_key)
            if not avatar:
                continue

            name = resolve_name(lang, avatar.get("name", ""))
            if not name or name.startswith("/Lotus/"):
                continue

            faction_raw = avatar.get("faction", "")
            faction = FACTION_MAP.get(faction_raw, faction_raw)

            health = avatar.get("health", 0)
            dc_key = avatar.get("damageController", "")
            dc = damage_controllers.get(dc_key, {})
            armor = dc.get("armor", 0)
            shield = dc.get("shield", 0)

            unhandled_procs = dc.get("unhandledProcTypes", [])
            overguard = dc.get("overguard", 0)

            # Build weak point data from hit proxies
            weak_points = []
            for hp in dc.get("hitProxies", []):
                hp_data = hit_proxies.get(hp.get("type", ""), {})
                if hp_data:
                    weak_points.append({
                        "bone": hp.get("bone", ""),
                        "damageAtten": hp_data.get("damageAtten", 1.0),
                        "critChance": hp_data.get("criticalChance", 0),
                        "critMult": hp_data.get("criticalMultiplier", 1.0),
                    })

            entry_key = f"{name}|{faction}|{variant_type}"
            enemies[entry_key] = {
                "name": name,
                "uniqueName": agent_key,
                "avatarKey": avatar_key,
                "faction": faction,
                "variantType": variant_type,
                "baseLevel": base_level,
                "health": health,
                "armor": armor,
                "shield": shield,
                "overguard": overguard,
                "killXP": avatar.get("killXPReward", 0),
                "isEximus": "Eximus" in name or "eximus" in avatar_key.lower(),
                "excludeFromSimulacrum": avatar.get("excludeFromSimulacrum", False),
                "codexSecret": avatar.get("codexSecret", False),
                "weakPoints": weak_points if weak_points else None,
                "immuneProcs": unhandled_procs if unhandled_procs else None,
            }

    print(f"  {len(enemies)} enemy entries")
    with open(OUT_DIR / "enemies.json", "w") as f:
        json.dump(enemies, f, indent=2)
    return enemies


def process_weapons():
    print("Processing weapons...")
    data = load_json("ExportWeapons.json")
    lang = load_lang()

    weapons = {}
    for wep_key, wep in data.items():
        name = resolve_name(lang, wep.get("name", ""))
        if not name or name.startswith("/Lotus/"):
            continue

        damage = parse_damage_array(wep.get("damagePerShot", []))
        total_damage = wep.get("totalDamage", 0)

        behaviours = []
        for b in wep.get("behaviours", []):
            beh = {"stateName": resolve_name(lang, b.get("stateName", ""))}
            beh["fireIterations"] = b.get("fireIterations", 1)

            if "burst" in b:
                beh["burst"] = b["burst"]
            if "chargeTime" in b:
                beh["chargeTime"] = b["chargeTime"]

            if "projectile" in b and "attack" in b["projectile"]:
                beh["projectileDamage"] = parse_dt_dict(b["projectile"]["attack"])
                if "procChance" in b["projectile"]["attack"]:
                    beh["projectileProcChance"] = b["projectile"]["attack"]["procChance"]
            if "projectile" in b and "explosiveAttack" in b["projectile"]:
                beh["explosiveDamage"] = parse_dt_dict(b["projectile"]["explosiveAttack"])

            if "impact" in b:
                beh["impactDamage"] = parse_dt_dict(b["impact"])
                if "procChance" in b["impact"]:
                    beh["impactProcChance"] = b["impact"]["procChance"]

            behaviours.append(beh)

        entry = {
            "name": name,
            "uniqueName": wep_key,
            "category": wep.get("productCategory", ""),
            "slot": wep.get("slot", -1),
            "damage": damage,
            "totalDamage": total_damage,
            "critChance": wep.get("criticalChance", 0),
            "critMult": wep.get("criticalMultiplier", 1),
            "statusChance": wep.get("procChance", 0),
            "fireRate": wep.get("fireRate", 0),
            "magSize": wep.get("magazineSize", 0),
            "reloadTime": wep.get("reloadTime", 0),
            "multishot": wep.get("multishot", 1),
            "accuracy": wep.get("accuracy", 0),
            "noise": wep.get("noise", "ALARMING"),
            "trigger": wep.get("trigger", ""),
            "masteryReq": wep.get("masteryReq", 0),
            "omegaAttenuation": wep.get("omegaAttenuation", 1.0),
            "variantType": wep.get("variantType", "VT_NORMAL"),
            "tags": wep.get("compatibilityTags", []),
            "behaviours": behaviours if behaviours else None,
        }

        if wep.get("parentName"):
            entry["parentWeapon"] = wep["parentName"]

        weapons[name] = entry

    print(f"  {len(weapons)} weapons")
    with open(OUT_DIR / "weapons.json", "w") as f:
        json.dump(weapons, f, indent=2)
    return weapons


def process_warframes():
    print("Processing warframes...")
    data = load_json("ExportWarframes.json")
    lang = load_lang()

    warframes = {}
    for wf_key, wf in data.items():
        name = resolve_name(lang, wf.get("name", ""))
        if not name or name.startswith("/Lotus/"):
            continue

        abilities = []
        for ab in wf.get("abilities", []):
            abilities.append({
                "uniqueName": ab.get("uniqueName", ""),
                "name": resolve_name(lang, ab.get("name", "")),
                "description": resolve_name(lang, ab.get("description", "")),
                "energyCost": ab.get("energyRequiredToActivate", 0),
                "energyDrain": ab.get("energyConsumptionOverTime", None),
            })

        entry = {
            "name": name,
            "uniqueName": wf_key,
            "health": wf.get("health", 0),
            "shield": wf.get("shield", 0),
            "armor": wf.get("armor", 0),
            "energy": wf.get("power", 0),
            "sprintSpeed": wf.get("sprintSpeed", 1.0),
            "masteryReq": wf.get("masteryReq", 0),
            "category": wf.get("productCategory", ""),
            "variantType": wf.get("variantType", "VT_NORMAL"),
            "abilities": abilities,
        }

        if wf.get("parentName"):
            entry["parentFrame"] = wf["parentName"]

        warframes[name] = entry

    print(f"  {len(warframes)} warframes")
    with open(OUT_DIR / "warframes.json", "w") as f:
        json.dump(warframes, f, indent=2)
    return warframes


def process_regions():
    print("Processing star chart nodes...")
    data = load_json("ExportRegions.json")
    lang = load_lang()

    nodes = {}
    for node_key, node in data.items():
        name = resolve_name(lang, node.get("name", ""))
        system_name = resolve_name(lang, node.get("systemName", ""))
        mission_type_raw = node.get("missionType", "")
        mission_type = MISSION_TYPE_MAP.get(mission_type_raw, mission_type_raw)
        faction_raw = node.get("faction", "")
        faction = FACTION_MAP.get(faction_raw, faction_raw)

        entry = {
            "name": name,
            "nodeKey": node_key,
            "planet": system_name,
            "missionType": mission_type,
            "faction": faction,
            "minLevel": node.get("minEnemyLevel", 0),
            "maxLevel": node.get("maxEnemyLevel", 0),
            "masteryReq": node.get("masteryReq", 0),
            "enemySpec": node.get("enemySpec", ""),
        }

        nodes[f"{name} ({system_name})"] = entry

    print(f"  {len(nodes)} star chart nodes")
    with open(OUT_DIR / "starchart_nodes.json", "w") as f:
        json.dump(nodes, f, indent=2)
    return nodes


def process_mods():
    print("Processing mods...")
    data = load_json("ExportUpgrades.json")
    lang = load_lang()

    mods = {}
    for mod_key, mod in data.items():
        name = resolve_name(lang, mod.get("name", ""))
        if not name:
            continue

        entry = {
            "name": name,
            "uniqueName": mod_key,
            "polarity": mod.get("polarity", ""),
            "rarity": mod.get("rarity", ""),
            "baseDrain": mod.get("baseDrain", 0),
            "fusionLimit": mod.get("fusionLimit", 0),
            "type": mod.get("type", ""),
            "compatName": mod.get("compatName", ""),
            "compat": mod.get("compat", ""),
            "isAugment": "Augment" in mod_key or mod.get("isAugment", False),
            "tradable": mod.get("tradable", False),
        }

        if "levelStats" in mod:
            entry["levelStats"] = mod["levelStats"]
        if "upgradeEntries" in mod:
            entry["upgradeEntries"] = mod["upgradeEntries"]

        mods[name] = entry

    print(f"  {len(mods)} mods")
    with open(OUT_DIR / "mods.json", "w") as f:
        json.dump(mods, f, indent=2)
    return mods


def process_arcanes():
    print("Processing arcanes...")
    data = load_json("ExportArcanes.json")
    lang = load_lang()

    arcanes = {}
    for arc_key, arc in data.items():
        name = resolve_name(lang, arc.get("name", ""))
        if not name:
            continue

        entry = {
            "name": name,
            "uniqueName": arc_key,
            "rarity": arc.get("rarity", ""),
            "fusionLimit": arc.get("fusionLimit", 0),
        }

        if "levelStats" in arc:
            entry["levelStats"] = arc["levelStats"]

        arcanes[name] = entry

    print(f"  {len(arcanes)} arcanes")
    with open(OUT_DIR / "arcanes.json", "w") as f:
        json.dump(arcanes, f, indent=2)
    return arcanes


def generate_summary(enemies, weapons, warframes, nodes, mods, arcanes):
    print("\nGenerating summary...")
    factions_in_enemies = {}
    for e in enemies.values():
        f = e["faction"]
        factions_in_enemies[f] = factions_in_enemies.get(f, 0) + 1

    planets = {}
    for n in nodes.values():
        p = n["planet"]
        planets[p] = planets.get(p, 0) + 1

    categories = {}
    for w in weapons.values():
        c = w["category"]
        categories[c] = categories.get(c, 0) + 1

    summary = {
        "totalEnemies": len(enemies),
        "totalWeapons": len(weapons),
        "totalWarframes": len(warframes),
        "totalNodes": len(nodes),
        "totalMods": len(mods),
        "totalArcanes": len(arcanes),
        "enemiesByFaction": dict(sorted(factions_in_enemies.items(), key=lambda x: -x[1])),
        "nodesByPlanet": dict(sorted(planets.items(), key=lambda x: -x[1])),
        "weaponsByCategory": dict(sorted(categories.items(), key=lambda x: -x[1])),
    }

    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    enemies = process_enemies()
    weapons = process_weapons()
    warframes = process_warframes()
    nodes = process_regions()
    mods = process_mods()
    arcanes = process_arcanes()
    summary = generate_summary(enemies, weapons, warframes, nodes, mods, arcanes)

    print(f"\n=== EXPORT SUMMARY ===")
    for k, v in summary.items():
        if isinstance(v, dict):
            print(f"\n{k}:")
            for sk, sv in v.items():
                print(f"  {sk}: {sv}")
        else:
            print(f"{k}: {v}")
