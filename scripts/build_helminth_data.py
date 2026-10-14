#!/usr/bin/env python3
"""Build backend/data/processed/helminth.json: what the Helminth can infuse.

  subsumable         every Warframe's subsumable ability (the wiki's Subsumable Ability
                     Checklist), keyed by ability name
  helminthAbilities  the Helminth's own abilities (Helminth/Unique Abilities)
  restrictions       the damage-buff rule: Eclipse, Roar and Xata's Whisper can only
                     replace one named ability on certain Warframes

Each ability carries its wiki description, what Ability Strength / Duration / Range
change (the wiki's Power Scaling table), tags for the picker, the ids of its weapon
effects in ability_buffs.json, and its survivability effects in the same format as
warframe_survivability.json (with the values the subsumed version has).

Sources: wiki.warframe.com Helminth, Helminth/Unique Abilities and the ability pages,
cached in data/raw/wiki_cache_current; the slot of each ability from the game export
(backend/data/processed/warframes.json). Run after build_ability_buffs.py and
build_passives.py. Safe to re-run.

Usage: python scripts/build_helminth_data.py [--refresh]
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_wiki_abilities as wiki  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "backend" / "data" / "processed"

WEAPON_KINDS = {
    "faction_add", "damage_mult", "base_damage_add", "elemental_add", "extra_hit", "crit_chance_add",
    "crit_chance_flat", "fire_rate_add", "enemy_vulnerability", "hit_multiplier", "slash_dot_mult",
}


def plain(wikitext: str) -> str:
    return re.sub(r"\s+", " ", wiki.strip_markup(wikitext.replace("<br />", "\n").replace("<br/>", "\n"))).strip()


def cell_list(wikitext: str):
    """A <br />-separated table cell -> list of plain items."""
    items = [plain(x) for x in re.split(r"<br\s*/?>", wikitext)]
    return [x for x in items if x and x not in ("—", "-")]


def section(page: str, heading: str) -> str:
    m = re.search(r"^=+\s*%s\s*=+\s*$(.*?)(?=^=+[^=])" % re.escape(heading), page, re.M | re.S)
    if not m:
        raise SystemExit(f"Helminth page: section '{heading}' not found")
    return m.group(1)


def template_field(page: str, key: str) -> str:
    m = re.search(r"^\s*\|\s*%s\s*=(.*?)(?=^\s*\|\s*\w+\s*=|^\}\})" % key, page, re.M | re.S)
    return m.group(1).strip() if m else ""


def parse_checklist(page: str):
    table = section(page, "Subsumable Ability Checklist")
    rows = {}
    for block in re.split(r"^\|- data-rowid=", table, flags=re.M)[1:]:
        cells = []
        for line in block.split("\n")[1:]:
            line = line.strip()
            if not line.startswith("|") or line.startswith("|-") or line.startswith("|}"):
                continue
            for cell in line[1:].split("||"):
                # drop sort keys: `data-sort-value="Ash" | {{WF|Ash}}`
                cell = re.sub(r'^(?:\s*data-sort-value="[^"]*")+\s*\|', "", cell)
                cells.append(cell.strip())
        if len(cells) < 6:
            continue
        frame = plain(cells[0])
        abilities = re.findall(r"\{\{A\|([^}|]+)", cells[1])
        notes = plain(cells[5]).replace("File:HelminthChrysalis.png", "").strip(" —")
        if "Cannot be used to swap" in notes or len(abilities) != 1:
            continue
        augments = re.findall(r"\{\{M\|([^}|]+)", cells[2])
        rows[abilities[0]] = {
            "warframe": frame, "augments": augments, "roles": cell_list(cells[3]),
            "damageTypes": [plain(x) for x in re.findall(r"\{\{D\|([^}|]+)", cells[4])],
            "notes": "" if notes in ("", "—") else notes,
        }
    return rows


def parse_scaling(page: str):
    """(ability, augment) -> {strength, duration, range} from the Power Scaling table rows."""
    out = {}
    for row in re.findall(r"\{\{Table row/Helminth scaling\|([^}]*)\}\}", page):
        parts = row.split("|")
        named = dict(p.split("=", 1) for p in parts if "=" in p)
        positional = [p for p in parts if "=" not in p]
        augment = named.get("augment") or (positional[2] if len(positional) > 2 else "")
        out[(positional[1], augment)] = {
            "strength": named.get("STR") == "TRUE", "duration": named.get("DUR") == "TRUE",
            "range": named.get("RNG") == "TRUE",
        }
    return out


def parse_restrictions(page: str):
    text = section(page, "Damage buff restrictions")
    head, _, tail = text.partition("... can only replace")
    abilities = re.findall(r"\{\{A\|([^}|]+)\}\}", head)
    only = {}
    for frame, ability in re.findall(r"^\*\{\{WF\|([^}|]+)\}\}'s \{\{A\|([^}|]+)\}\}", tail, re.M):
        only[frame] = ability
    if not abilities or not only:
        raise SystemExit("Helminth page: damage buff restrictions not understood")
    return {"abilities": abilities, "onlyReplace": only}


def helminth_ability_names() -> list:
    page = wiki.fetch_raw("Helminth/Unique Abilities") or ""
    return re.findall(r"\{\{:([^}]+)\}\}", page)


def module_scaling(page: str):
    """{name: {strength, duration, range}} from an {{AbilityModBenefits}} block."""
    out = {}
    for n, name in re.findall(r"\|\s*ability(\d+)\s*=\s*([^\n|]+)", page):
        get = lambda k: bool(re.search(r"\|\s*ability%s%s[ \t]*=[ \t]*[^\s|]" % (n, k), page))  # noqa: E731
        out[name.strip()] = {"strength": get("strength"), "duration": get("duration"), "range": get("range")}
    return out


def description(ability: str) -> str:
    page = wiki.fetch_raw(ability) or ""
    # Helminth ability pages append the Metamorphosis tier and infusion costs to the description
    return plain(template_field(page, "description")).split(" Metamorphosis:")[0].strip()


def subsumed_cap(ability: str):
    """A cap the wiki gives for the infused version ("Subsumed Defy's armor bonus is capped at 750"), or None."""
    page = wiki.fetch_raw(ability) or ""
    helminth = template_field(page, "helminth")
    m = re.search(r"Subsumed [^.\n]*?\bcap(?:s|ped)? at [^\d]*([\d,]+)(%?)", helminth)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    return value / 100 if m.group(2) else value


def tags_for(effects_weapon, effects_surv, roles):
    tags = []
    kinds = {e["kind"] for e in effects_weapon}
    if kinds & WEAPON_KINDS:
        tags.append("Damage buff")
    if "armor_strip" in kinds:
        tags.append("Armor strip")
    if any(e["kind"] == "dr" for e in effects_surv):
        tags.append("DR")
    if any(e["kind"] == "armor" for e in effects_surv):
        tags.append("Armor")
    if any(e["kind"] == "strength" for e in effects_surv):
        tags.append("Strength")
    return tags


def category(roles, tags):
    """One picker group per ability, from the calculator's tags first, then the wiki's roles."""
    if "Damage buff" in tags:
        return "Damage"
    if "Armor strip" in tags:
        return "Armor strip"
    if {"DR", "Armor"} & set(tags):
        return "Survivability"
    joined = " ".join(roles).lower()
    if "damage" in joined and "debuff" not in joined:
        return "Damage"
    if any(w in joined for w in ("heal", "shield", "armor", "survivab", "invulnerab", "damage reduction")):
        return "Survivability"
    if "crowd control" in joined:
        return "Crowd control"
    return "Utility"


def main():
    if "--refresh" in sys.argv:
        wiki.REFRESH = True
    page = wiki.fetch_raw("Helminth") or ""
    checklist = parse_checklist(page)
    scaling = parse_scaling(page)
    restrictions = parse_restrictions(page)

    frames = json.loads((P / "warframes.json").read_text(encoding="utf-8"))
    surv = json.loads((P / "warframe_survivability.json").read_text(encoding="utf-8"))["warframes"]
    buffs = json.loads((P / "ability_buffs.json").read_text(encoding="utf-8"))["effects"]
    weapon_fx = [e for e in buffs if e["target"] in ("weapon",)]
    surv_fx = [e for e in buffs if e["target"] in ("survivability", "any")]

    def belongs(effect_name, ability):
        return effect_name == ability or effect_name.startswith(ability + " ")

    def survivability_effects(ability, donor):
        """The donor's own survivability entries for this ability, with subsumed values applied."""
        out = [dict(a) for a in surv.get(donor, {}).get("abilities", []) if belongs(a["name"], ability)]
        for e in surv_fx:
            if e["ability"] != ability:
                continue
            existing = next((a for a in out if a["name"] == e["id"]), None)
            if existing is None and e["subsumed"] is not None:
                value = e["value"] if e["subsumed"] == "same" else e["subsumed"]
                existing = {"kind": e["kind"], "name": e["id"], "value": value, "cap": e["cap"],
                            "scalesWithStrength": e["scalesWithStrength"], "stacks": e["stacks"],
                            "perStack": e["perStack"], "level": e["level"], "low": e["low"],
                            "mode": e.get("mode"), "note": e["note"], "applies": "all"}
                out.append(existing)
            if existing is not None and e["subsumedCap"] is not None:
                existing["cap"] = e["subsumedCap"]
                existing["note"] = (existing.get("note", "") + f" Infused: capped at {e['subsumedCap']:.0%}.").strip()
        return out


    subsumable = {}
    for ability, row in sorted(checklist.items()):
        donor = row["warframe"]
        names = [a["name"] for a in frames.get(donor, {}).get("abilities", [])]
        if ability not in names:
            raise SystemExit(f"{ability}: not one of {donor}'s abilities in the game export ({names})")
        weapon = [e for e in weapon_fx if e["ability"] == ability and e["subsumed"] is not None]
        survival = survivability_effects(ability, donor)
        cap = subsumed_cap(ability)
        for e in survival:
            if cap is not None and e["kind"] in ("dr", "armor") and "Infused: capped" not in e.get("note", ""):
                e["cap"] = cap
                shown = f"{cap:.0%}" if e["kind"] == "dr" else f"{cap:,.0f}"
                e["note"] = (e.get("note", "") + f" Infused: capped at {shown}.").strip()
        tags = tags_for(weapon, survival, row["roles"])
        subsumable[ability] = {
            "ability": ability, "warframe": donor, "slot": names.index(ability) + 1,
            "description": description(ability),
            "augments": row["augments"], "roles": row["roles"], "damageTypes": row["damageTypes"],
            "notes": row["notes"],
            "scaling": scaling.get((ability, "")) or {"strength": False, "duration": False, "range": False},
            "augmentScaling": {aug: s for (a, aug), s in scaling.items() if a == ability and aug},
            "tags": tags, "category": category(row["roles"], tags),
            "weaponEffects": [e["id"] for e in weapon],
            "survivabilityEffects": survival,
        }
    # every infusable weapon effect must belong to a subsumable ability
    for e in weapon_fx:
        if e["subsumed"] is not None and e["ability"] not in subsumable and e["sourceKind"] == "ability":
            raise SystemExit(f"{e['id']}: marked infusable but {e['ability']} is not on the Helminth checklist")

    unique_page = wiki.fetch_raw("Helminth/Unique Abilities") or ""
    unique_scaling = module_scaling(unique_page)
    helminth = {}
    for name in helminth_ability_names():
        ability_page = wiki.fetch_raw(name) or ""
        fields = {k: plain(template_field(ability_page, k)) for k in ("strength", "duration", "range", "misc")}
        survival = survivability_effects(name, "")
        tags = tags_for([], survival, [])
        helminth[name] = {
            "ability": name, "warframe": "Helminth",
            "description": description(name),
            "values": {k: v for k, v in fields.items() if v},
            "scaling": unique_scaling.get(name) or unique_scaling.get(name.replace("'", "")) or
                       {"strength": False, "duration": False, "range": False},
            "tags": tags, "category": "Helminth",
            "weaponEffects": [], "survivabilityEffects": survival,
        }

    data = {
        "_about": "Built by scripts/build_helminth_data.py from wiki.warframe.com (Helminth page). "
                  "Survivability effects carry the values of the infused version.",
        "subsumable": subsumable, "helminthAbilities": helminth, "restrictions": restrictions,
    }
    with open(P / "helminth.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tagged = {a: v["tags"] for a, v in {**subsumable, **helminth}.items() if v["tags"]}
    print(f"helminth: {len(subsumable)} subsumable abilities, {len(helminth)} Helminth abilities, "
          f"restricted: {restrictions['abilities']} on {len(restrictions['onlyReplace'])} frames")
    print(f"  with calculator effects: {tagged}")


if __name__ == "__main__":
    main()
