#!/usr/bin/env python3
"""Map every item the app shows to its image on the WFCD CDN.

Reads the WFCD warframe-items data (data/raw/wfcd_*.json, the same JSON the
`warframe-items` npm package ships; missing files are downloaded) and matches
it to the app's processed data by uniqueName, falling back to the display name.

Writes backend/data/processed/image_map.json with image file names per category
(served from https://cdn.warframestat.us/img/<name>) plus mod slot polarities
for weapons and Warframes, which the game export doesn't carry.

Usage: python scripts/build_image_map.py
"""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
P = ROOT / "backend" / "data" / "processed"
URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/%s.json"
CURL = shutil.which("curl") or "curl"
CATEGORIES = ["Mods", "Warframes", "Primary", "Secondary", "Melee", "Arch-Gun", "Arch-Melee",
              "SentinelWeapons", "Sentinels", "Pets", "Arcanes", "Misc"]


def wfcd(name):
    path = RAW / f"wfcd_{name.lower()}.json"
    if not path.exists():
        subprocess.run([CURL, "-sL", "-o", str(path), URL % name], check=True, timeout=300)
    return json.loads(path.read_text(encoding="utf-8"))


def load(name):
    return json.loads((P / name).read_text(encoding="utf-8"))


def main():
    by_unique, by_name, items = {}, {}, {}
    for category in CATEGORIES:
        for item in wfcd(category):
            if not item.get("imageName"):
                continue
            by_unique.setdefault(item.get("uniqueName"), item["imageName"])
            # the obtainable copy of a mod is the one outside the Beginner/Expert/PvP folders
            ranked = ("/PvPMods/" in item.get("uniqueName", ""), "/Beginner/" in item.get("uniqueName", ""))
            if item["name"] not in items or ranked < items[item["name"]][0]:
                items[item["name"]] = (ranked, item)
                by_name[item["name"]] = item["imageName"]

    def find(name, unique=None):
        return by_unique.get(unique) or by_name.get(name) or by_name.get(name.replace(" & ", " And "))

    out = {k: {} for k in ("mods", "warframes", "abilities", "weapons", "arcanes", "companions", "ampParts")}
    polarities = {"weapons": {}, "warframes": {}}
    missing = {k: [] for k in out}

    def put(section, name, image):
        if image:
            out[section][name] = image
        else:
            missing[section].append(name)

    weapons = load("weapons.json")
    weapons.update(load("companion_weapons.json")["weapons"])
    for name, w in weapons.items():
        if not w.get("damage"):
            continue
        put("weapons", name, find(name, w.get("uniqueName")))
        src = items.get(name, (None, {}))[1]
        if src.get("polarities"):
            polarities["weapons"][name] = [p.title() for p in src["polarities"]]

    for name, f in load("warframes.json").items():
        if name.startswith("<ARCHWING>"):
            continue
        put("warframes", name, find(name, f.get("uniqueName")))
        src = items.get(name, (None, {}))[1]
        aura = src.get("aura")  # a few frames list several aura polarities
        polarities["warframes"][name] = {"slots": [p.title() for p in src.get("polarities") or []],
                                         "aura": (aura[0] if isinstance(aura, list) and aura else aura or "").title()}
        for ability in src.get("abilities") or []:
            if ability.get("imageName"):
                out["abilities"][ability["name"]] = ability["imageName"]

    mods = load("core_mods.json")["mods"]
    mods.update(load("companion_mods.json")["mods"])
    lower = {k.lower(): v for k, v in by_name.items()}   # WFCD writes "Bane Of Corpus"
    for name in mods:
        put("mods", name, by_name.get(name) or lower.get(name.lower()))

    for a in load("warframe_survivability.json")["arcanes"] + load("amps.json")["arcanes"]:
        put("arcanes", a["name"], by_name.get(a["name"]))
    for name in load("companions.json"):
        put("companions", name, by_name.get(name))
    amps = load("amps.json")
    for part in amps["prisms"] + amps["scaffolds"] + amps["braces"]:
        put("ampParts", part["name"], by_name.get(part["name"]))

    out["slotPolarities"] = polarities
    with open(P / "image_map.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    for section in missing:
        total = len(out[section]) + len(missing[section])
        print(f"{section}: {len(out[section])}/{total} matched" if section != "abilities"
              else f"abilities: {len(out[section])} icons")
        if missing[section]:
            print("   no image: " + ", ".join(sorted(missing[section])[:40]))


if __name__ == "__main__":
    main()
