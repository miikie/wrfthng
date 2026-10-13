#!/usr/bin/env python3
"""Data for the Exilus slot and the weapon arcane slots (display only).

  - Flags every Exilus-compatible mod in backend/data/processed/core_mods.json
    with "exilus": true. Exilus mods that aren't in the file yet are added as
    documented-only entries ("special": true) so they can be slotted; they are
    utility mods and don't change any calculation.
  - Writes backend/data/processed/weapon_arcanes.json: the arcanes that go on
    primary, secondary and melee weapons, with their max-rank text. The engine
    does not apply them.

Source: WFCD warframe-items (data/raw/wfcd_mods.json, wfcd_arcanes.json), where
Exilus-compatible mods carry isUtility / isExilus. Run after build_warframe_data.py.

Usage: python scripts/build_slot_data.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
P = ROOT / "backend" / "data" / "processed"

MOD_TYPES = {"Primary Mod": "PRIMARY", "Secondary Mod": "SECONDARY", "Melee Mod": "MELEE",
             "Shotgun Mod": "SHOTGUN", "Warframe Mod": "WARFRAME"}
ARCANE_TYPES = {"Primary Arcane": "PRIMARY", "Bow Arcane": "PRIMARY", "Shotgun Arcane": "SHOTGUN",
                "Secondary Arcane": "SECONDARY", "Melee Arcane": "MELEE"}


def clean(text: str) -> str:
    text = re.sub(r"<[A-Z_0-9]+>", "", text.replace("\\n", " ").replace("\n", " "))
    return re.sub(r"\s+", " ", text).strip()


def main():
    core = json.loads((P / "core_mods.json").read_text(encoding="utf-8"))
    mods = core["mods"]
    export = json.loads((P / "mods.json").read_text(encoding="utf-8"))
    flagged, added = 0, 0
    seen = set()
    for m in json.loads((RAW / "wfcd_mods.json").read_text(encoding="utf-8")):
        if not (m.get("isUtility") or m.get("isExilus")) or not m.get("levelStats"):
            continue
        if "/PvPMods/" in m["uniqueName"] or m["name"] in seen or m.get("type") not in MOD_TYPES:
            continue
        seen.add(m["name"])
        name = m["name"]
        if name in mods:
            if not mods[name].get("exilus"):
                mods[name]["exilus"] = True
                flagged += 1
            continue
        src = export.get(name)
        if src is None or src.get("isAugment"):
            continue
        text = clean(" / ".join(m["levelStats"][-1]["stats"]))
        mods[name] = {
            "maxRank": len(m["levelStats"]) - 1, "type": MOD_TYPES[m["type"]],
            "polarity": (m.get("polarity") or "").title(), "rarity": m.get("rarity") or "",
            "baseDrain": m.get("baseDrain", 0), "special": True, "exilus": True,
            "note": f"{text} (at max rank). Utility mod: no effect on the calculator.",
        }
        added += 1
    with open(P / "core_mods.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(core, f, indent=2, ensure_ascii=False)
        f.write("\n")
    total = sum(1 for v in mods.values() if v.get("exilus"))
    print(f"exilus mods: {flagged} flagged, {added} added, {total} in core_mods.json")

    arcanes = []
    for a in json.loads((RAW / "wfcd_arcanes.json").read_text(encoding="utf-8")):
        if a.get("type") not in ARCANE_TYPES or not a.get("levelStats"):
            continue
        arcanes.append({
            "name": a["name"], "type": ARCANE_TYPES[a["type"]], "maxRank": len(a["levelStats"]) - 1,
            "text": clean(" / ".join(a["levelStats"][-1]["stats"])), "imageName": a.get("imageName", ""),
        })
    arcanes.sort(key=lambda a: (a["type"], a["name"]))
    with open(P / "weapon_arcanes.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"arcanes": arcanes}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"weapon arcanes: {len(arcanes)}")


if __name__ == "__main__":
    main()
