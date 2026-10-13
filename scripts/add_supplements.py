#!/usr/bin/env python3
"""Add content the game export doesn't carry yet to backend/data/processed/.

The export (warframe-public-export-plus) is still at game version 43.5.4, so
Update 44 items are taken from WFCD warframe-items instead. Re-run this after
process_export_data.py; once the export catches up it adds nothing.

  - weapons.json:   Nunchasa, Steflos Prime, Aksondol, Corufell Prime
  - warframes.json: Narin, Citrine Prime
  - enemies.json:   codex names for enemies the export lists under an internal name

Usage: python scripts/add_supplements.py
"""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
P = ROOT / "backend" / "data" / "processed"
WFCD_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/%s.json"
CURL = shutil.which("curl") or "curl"

WEAPONS = {  # name: (WFCD file, existing weapon to copy tags from)
    "Nunchasa": ("Primary", "Paris Prime"),
    "Steflos Prime": ("Primary", "Steflos"),
    "Aksondol": ("Secondary", "Aklex Prime"),
    "Corufell Prime": ("Arch-Melee", "Corufell"),
}
WARFRAMES = {"Narin": None, "Citrine Prime": "Citrine"}  # name: base frame to take ability costs from
# Codex name -> the name the export uses for the same enemy (matched by avatar key when possible)
ENEMY_NAMES = ["Nemes Ranger", "Nemes Scout", "Nightwatch Bombard", "Tomb Guardian"]


def wfcd(name):
    path = RAW / f"wfcd_{name.lower()}.json"
    if not path.exists():
        subprocess.run([CURL, "-sL", "-o", str(path), WFCD_URL % name], check=True, timeout=180)
    return json.loads(path.read_text(encoding="utf-8"))


def load(name):
    return json.loads((P / name).read_text(encoding="utf-8"))


def save(name, data):
    with open(P / name, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)


def r(x, places=4):
    return round(float(x), places)


def main():
    # ---- weapons
    weapons = load("weapons.json")
    added = []
    for name, (source, like) in WEAPONS.items():
        if name in weapons and weapons[name].get("source") is None:
            continue  # the export has it now
        w = next(x for x in wfcd(source) if x["name"] == name)
        damage = {k.title(): r(v, 3) for k, v in w["damage"].items()
                  if k not in ("total", "true", "cinematic") and v}
        base = weapons.get(like, {})
        weapons[name] = {
            "name": name, "uniqueName": w["uniqueName"], "category": w["productCategory"],
            "slot": w.get("slot"), "damage": damage, "totalDamage": r(sum(damage.values()), 3),
            "critChance": r(w["criticalChance"]), "critMult": r(w["criticalMultiplier"]),
            "statusChance": r(w["procChance"]), "fireRate": r(w["fireRate"]),
            "magSize": w.get("magazineSize", 0), "reloadTime": r(w.get("reloadTime", 0)),
            "multishot": w.get("multishot", 1), "accuracy": r(w.get("accuracy", 0), 2),
            "noise": (w.get("noise") or "").upper(), "trigger": (w.get("trigger") or "").upper(),
            "masteryReq": w.get("masteryReq", 0), "omegaAttenuation": w.get("omegaAttenuation", 1),
            "variantType": "VT_PRIME" if w.get("isPrime") else "VT_NORMAL",
            "tags": base.get("tags", []), "behaviours": [],
            "source": "WFCD warframe-items (Update 44); not yet in the game export",
        }
        added.append(name)
    save("weapons.json", weapons)
    print(f"weapons: added {added or 'nothing'}")

    # ---- warframes
    frames = load("warframes.json")
    all_frames = json.loads((RAW / "wfcd_warframes.json").read_text(encoding="utf-8"))
    added = []
    for name, base in WARFRAMES.items():
        if name in frames and frames[name].get("source") is None:
            continue
        f = next(x for x in all_frames if x["name"] == name)
        scraped = RAW / "wiki_abilities" / (name.lower().replace(" ", "_") + ".json")
        costs = {}
        if base:
            costs = {a["name"]: (a.get("energyCost"), a.get("energyDrain")) for a in frames[base]["abilities"]}
        elif scraped.exists():
            costs = {a["name"]: (a.get("energy_cost"), a.get("energy_drain"))
                     for a in json.loads(scraped.read_text(encoding="utf-8"))["abilities"]}
        frames[name] = {
            "name": name, "uniqueName": f["uniqueName"], "health": f["health"], "shield": f["shield"],
            "armor": f["armor"], "energy": f["power"], "sprintSpeed": f["sprintSpeed"],
            "masteryReq": f.get("masteryReq", 0), "category": "Suits",
            "variantType": "VT_PRIME" if f.get("isPrime") else "VT_NORMAL",
            "abilities": [{"uniqueName": a["uniqueName"], "name": a["name"], "description": a["description"],
                           "energyCost": costs.get(a["name"], (None, None))[0],
                           "energyDrain": costs.get(a["name"], (None, None))[1]} for a in f["abilities"]],
            "source": "WFCD warframe-items (Update 44); not yet in the game export",
        }
        added.append(name)
    save("warframes.json", frames)
    print(f"warframes: added {added or 'nothing'}")

    # ---- enemies: codex names for entries the export has under another name
    enemies = load("enemies.json")
    by_avatar = {}
    for key, e in enemies.items():
        by_avatar.setdefault(e.get("avatarKey"), key)
    codex = {x["name"]: x for x in wfcd("Enemy")}
    report = []
    for name in ENEMY_NAMES:
        if any(e["name"] == name for e in enemies.values()):
            report.append(f"{name}: already present")
            continue
        src = codex.get(name)
        match = by_avatar.get(src["uniqueName"]) if src else None
        if match:
            entry = dict(enemies[match], name=name, aliasOf=match)
            enemies[f"{name}|{entry['faction']}|{entry['variantType']}"] = entry
            report.append(f"{name}: added as another name for {match}")
        elif src:
            faction = src.get("faction") if src.get("faction") not in (None, "Neutral") else src.get("type", "Unaffiliated")
            if name == "Tomb Guardian":
                faction = "Unaffiliated"
            enemies[f"{name}|{faction}|STANDARD"] = {
                "name": name, "uniqueName": src["uniqueName"], "avatarKey": src["uniqueName"],
                "faction": faction, "variantType": "STANDARD", "baseLevel": 1,
                "health": src["health"], "armor": src["armor"], "shield": src["shield"], "overguard": 0,
                "killXP": 0, "isEximus": False, "excludeFromSimulacrum": True, "codexSecret": False,
                "weakPoints": [], "immuneProcs": [],
                "source": "WFCD codex entry; base level and weak points unknown",
            }
            report.append(f"{name}: added from the codex list ({faction}, base level assumed 1)")
        else:
            report.append(f"{name}: not found in any source")
    save("enemies.json", enemies)
    print("enemies:\n  " + "\n  ".join(report))


if __name__ == "__main__":
    main()
