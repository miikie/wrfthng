#!/usr/bin/env python3
"""List weapon mods in mods.json that are not in core_mods.json, with their max-rank text.

Usage: python scripts/list_uncurated_mods.py [--damage]   (--damage: only ones whose text mentions a damage stat)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "backend" / "data" / "processed"
DAMAGE = re.compile(r"Damage|Critical|Status|Multishot|Fire Rate|Attack Speed|Combo|Reload|Magazine|"
                    r"Heat|Cold|Toxin|Electric|Slash|Impact|Puncture|FIRE|FREEZE|POISON", re.I)


def main():
    mods = json.loads((P / "mods.json").read_text(encoding="utf-8"))
    core = json.loads((P / "core_mods.json").read_text(encoding="utf-8"))["mods"]
    text = {}
    for m in json.loads((ROOT / "data" / "raw" / "wfcd_mods.json").read_text(encoding="utf-8")):
        if m.get("levelStats") and "/PvPMods/" not in m["uniqueName"]:
            text.setdefault(m["name"], " / ".join(m["levelStats"][-1]["stats"]).replace("\n", " "))
    out = []
    for name, m in sorted(mods.items()):
        if m.get("type") not in ("PRIMARY", "SECONDARY", "MELEE") or name in core or m.get("isAugment"):
            continue
        t = text.get(name, "")
        if "--damage" in sys.argv and not DAMAGE.search(t):
            continue
        out.append(f"{m['type'][:3]} {name} [{m.get('compatName', '')}]: {t}")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(out))
    print(f"\n{len(out)} mods", file=sys.stderr)


if __name__ == "__main__":
    main()
