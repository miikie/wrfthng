#!/usr/bin/env python3
"""Build backend/data/processed/ability_buffs.json: Warframe abilities and passives
that change weapon damage, plus the survivability effects of abilities that can be
infused through the Helminth.

Each effect is read from a wiki.warframe.com page: it names the page and a pattern
that must match that page's plain text, and its numbers come from the match. A
pattern that stops matching stops the script, so a changed page can't leave a
stale number behind. Values are max rank.

Weapon effect kinds (how the damage engine applies them, from the wiki's notes):
  base_damage_add   added to Serration-style base damage mods (Vex Armor, Amp, Shooting Gallery)
  faction_add       a Faction Damage Bonus, added to Bane mods: twice on DoTs (Roar)
  damage_mult       its own multiplier, once on hits and once on DoTs (Solar Eclipse, Garuda)
  hit_multiplier    multiplies hits on the spot it marks (Sonar): value x Ability Strength
  enemy_vulnerability  Damage Vulnerability on the enemy: once on hits and DoTs (Molecular Prime)
  elemental_add     elemental damage beside the weapon's own, never combining (Nourish, Smite Infusion)
  extra_hit         an Extra Hit worth a share of the hit's damage (Xata's Whisper, Toxic Lash)
  crit_chance_add   added to critical chance mods (Nyx, Zephyr)
  crit_chance_flat  flat points after mods (Covenant)
  fire_rate_add     added to fire rate / attack speed mods (Warcry, Haste Mote)
  armor_strip       enemy armor removed, added to other strips (Terrify)
  slash_dot_mult    multiplies Slash status damage (Ash)
Survivability kinds (infused abilities only; a Warframe's own are in
warframe_survivability.json): dr, armor, strength.

Sources: the ability pages, augment mod pages and `<Frame>/Abilities/Passive`
pages, cached in data/raw/wiki_cache_current. Run before build_helminth_data.py.

Usage: python scripts/build_ability_buffs.py [--refresh]
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_wiki_abilities as wiki  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "data" / "processed" / "ability_buffs.json"

# The last (max rank) value of a "10% / 15% / 25% / 50%" list
MAX = r"(?:\+?[\d.,]+ ?%? ?/ ?)*\+?([\d.,]+) ?%"
MAXX = r"(?:[\d.]+ ?x ?/ ?)*([\d.]+) ?x"
SWORDS = ["SWORDS_STANCE", "DUAL_SWORDS_STANCE", "NIKANAS_STANCE", "RAPIER_STANCE"]
SPEARGUNS = ["Afentis", "Ferrox", "Tenet Ferrox", "Javlok"]   # named on Styanax's passive page

_pages = {}


def text(page: str) -> str:
    if page not in _pages:
        raw = (wiki.fetch_raw(page) or "").replace("{{#tag:tabber|", "")
        raw = raw.replace("{{!-!}}", "\n").replace("{{!}}-{{!}}", "\n").replace("<br>", " ").replace("<br/>", " ")
        _pages[page] = re.sub(r"\s+", " ", wiki.strip_markup(raw))
    return _pages[page]


def read(page: str, pattern: str):
    hit = re.search(pattern, text(page))
    if not hit:
        raise SystemExit(f"{page}: pattern no longer matches the wiki page:\n  {pattern}")
    return [float(g.replace(",", "")) for g in hit.groups()]


def pct(page, pattern):
    return read(page, pattern)[0] / 100


# ----------------------------------------------------------------------------
# Effect builders. Every effect gets the same fields so the engine and UI can
# read any of them the same way.
# ----------------------------------------------------------------------------
def effect(id, label, kind, value, *, ability="", source="", source_kind="ability", target="weapon",
           subsumed="same", subsumed_cap=None, cap=None, scales=True, strength_cap=None, level=None, low=None,
           stacks=None, per_stack=None, weapons="all", weapon_tags=None, element=None, augment="",
           condition="", note="", weak_point=None, per_shields=None, double_for=None, group=""):
    return {
        "id": id, "label": label, "ability": ability or label, "source": source, "sourceKind": source_kind,
        "target": target, "kind": kind, "value": value,
        # value when infused through the Helminth: a number, "same", or None (cannot be infused)
        "subsumed": subsumed, "subsumedCap": subsumed_cap,
        "cap": cap, "scalesWithStrength": scales, "strengthCap": strength_cap,
        "level": level, "low": low, "stacks": stacks, "perStack": per_stack,
        "weapons": weapons, "weaponTags": weapon_tags, "element": element, "augment": augment,
        "condition": condition, "note": note,
        "weakPoint": weak_point,          # {multiplier, cap}: value on a weak point hit (Covenant)
        "perShields": per_shields,        # value per this many shield points (Styanax)
        "doubleFor": double_for,          # weapon names that get double the value (Styanax: spearguns)
        "group": group,                   # effects in one group don't stack: the highest applies
    }


def build():
    out = []
    add = out.append

    # --- Rhino
    roar = pct("Roar", rf"gain {MAX} bonus damage to all weapons and abilities")
    add(effect("Roar", "Roar", "faction_add", roar, source="Rhino",
               subsumed=pct("Roar", rf"Subsumed Roar's damage bonus is reduced to {MAX}"),
               note="A Faction Damage Bonus: added to Bane mods, and counted twice on damage over time."))

    # --- Mirage
    add(effect("Eclipse (Solar)", "Eclipse (Solar)", "damage_mult",
               pct("Eclipse", rf"bathing Mirage in light to gain {MAX} weapon damage"), ability="Eclipse",
               source="Mirage", subsumed=pct("Eclipse", rf"damage bonus is reduced to {MAX}"),
               condition="Hold cast (Solar Eclipse)",
               note="Its own multiplier: applied once to hits and once to status damage."))
    lunar = pct("Eclipse", rf"bathing Mirage in shadows to gain {MAX} Damage Reduction")
    add(effect("Eclipse (Lunar)", "Eclipse (Lunar)", "dr", lunar, ability="Eclipse", source="Mirage",
               target="survivability", cap=pct("Eclipse", r"Damage reduction is capped at (\d+)%"),
               subsumed="same", subsumed_cap=pct("Eclipse", r"Subsumed Eclipse's damage reduction caps at (\d+)%"),
               condition="Tap cast (Lunar Eclipse)", note="Tap cast. The hold cast gives a damage bonus instead."))

    # --- Xaku
    add(effect("Xata's Whisper", "Xata's Whisper", "extra_hit",
               pct("Xata's Whisper", rf"for {MAX} of total weapon damage as Void damage"), source="Xaku",
               element="Void",
               note="An Extra Hit of Void damage worth this share of each hit. Counts faction mods and weak points twice."))

    # --- Chroma
    fury = pct("Vex Armor", rf"Fury increases weapon .*? up to a maximum of {MAX}")
    add(effect("Vex Armor (Fury)", "Vex Armor (Fury)", "base_damage_add", fury, ability="Vex Armor",
               source="Chroma", subsumed=None, low=0.0, level={"label": "Fury built up", "default": 1.0},
               note="Added to base damage mods like Serration. Builds from health damage and ranged kills."))

    # --- Octavia
    amp_min = pct("Amp (Ability)", rf"{MAX} \(min damage buff\)")
    amp_max = pct("Amp (Ability)", rf"{MAX} \(max damage buff\)")
    add(effect("Amp", "Amp", "base_damage_add", amp_max, source="Octavia", subsumed=None, low=amp_min,
               level={"label": "Sound level", "default": 1.0},
               note="Added to base damage mods. Ranges from its minimum to its maximum with the sound level."))

    # --- Saryn
    for weapons, label, pattern in (("ranged", "Toxic Lash (guns)", r"\(added gun damage\)"),
                                    ("melee", "Toxic Lash (melee)", r"\(added melee damage\)")):
        add(effect(label, label, "extra_hit", pct("Toxic Lash", rf"{MAX} {pattern}"), ability="Toxic Lash",
                   source="Saryn", subsumed=None, weapons=weapons, element="Toxin",
                   note="An Extra Hit of Toxin damage that never combines with the weapon's elements. Faction mods "
                        "count again on it. Its guaranteed Toxin status is not part of the numbers."))

    # --- Mesa
    add(effect("Shooting Gallery", "Shooting Gallery", "base_damage_add",
               pct("Shooting Gallery", rf"causing her to gain {MAX} weapon damage"), source="Mesa",
               note="Added to base damage mods. Melee too."))

    # --- Grendel
    add(effect("Nourish", "Nourish", "elemental_add", pct("Nourish", rf"Adds {MAX} Viral damage to all weapons"),
               source="Grendel", element="Viral",
               subsumed=pct("Nourish", rf"Viral weapon bonus damage is reduced to {MAX}"),
               note="Like a Viral mod that never combines with the weapon's other elements."))

    # --- Valkyr
    add(effect("Warcry (attack speed)", "Warcry", "fire_rate_add",
               pct("Warcry", rf"{MAX} \(attack speed buff\)"), ability="Warcry", source="Valkyr", weapons="melee",
               subsumed=pct("Warcry", rf"attack speed bonus is reduced to {MAX}"),
               note="Melee attack speed, added to attack speed mods."))
    add(effect("Warcry", "Warcry", "armor", pct("Warcry", rf"{MAX} \(armor buff\)"), source="Valkyr",
               target="survivability", note="Added to armor mods. Tripled under Hysteria (not modelled)."))

    # --- Oberon, Volt, Gauss: augments that add an element to weapons
    for ability, src, aug, element, page in (("Smite", "Oberon", "Smite Infusion", "Radiation", "Smite Infusion"),
                                             ("Shock", "Volt", "Shock Trooper", "Electricity", "Shock Trooper"),
                                             ("Thermal Sunder", "Gauss", "Thermal Transfer", "Heat", "Thermal Transfer")):
        value = pct(page, r"\| 3 \|\| \+?(\d+)% \|\|")
        add(effect(aug, f"{ability} + {aug}", "elemental_add", value, ability=ability, source=src, element=element,
                   augment=aug,
                   note=f"Needs the {aug} augment. Adds {element} beside the weapon's elements; it never combines."
                        + (" Hold cast gives Heat, tap gives Cold." if aug == "Thermal Transfer" else "")))

    # --- Harrow
    cov_base = pct("Covenant", r"strength = (\d+)% \(base critical chance\)")
    cov_cap = pct("Covenant", r"(\d+)% \(bodyshot critical chance cap\)")
    cov_wp = read("Covenant", r"([\d.]+)x \(weak point multiplier to bonus critical chance\)")[0]
    cov_wp_cap = pct("Covenant", r"(\d+)% \(weak point critical chance cap\)")
    add(effect("Covenant", "Covenant", "crit_chance_flat", cov_cap, source="Harrow", subsumed=None, low=cov_base,
               cap=cov_cap, level={"label": "Damage absorbed (to the cap)", "default": 1.0},
               weak_point={"multiplier": cov_wp, "cap": cov_wp_cap},
               note=f"Flat critical chance after mods: {cov_base:.0%} plus more for damage absorbed, up to "
                    f"{cov_cap:.0%}; x{cov_wp:g} on weak points, up to {cov_wp_cap:.0%}."))

    # --- Banshee
    sonar = read("Sonar", rf"strength = {MAXX}")[0]
    add(effect("Sonar", "Sonar", "hit_multiplier", sonar, source="Banshee", subsumed=None,
               condition="Hitting a Sonar spot",
               note="Hits on a highlighted spot deal this many times the damage (x Ability Strength)."))

    # --- Nova
    add(effect("Molecular Prime", "Molecular Prime", "enemy_vulnerability",
               pct("Molecular Prime", r"receive \+(\d+)% Damage Vulnerability"), source="Nova", subsumed=None,
               scales=False, condition="Enemy is primed",
               note="Damage Vulnerability: applied once to hits and once to damage over time."))

    # --- Equinox, Oraxia, Uriel: Damage Vulnerability
    add(effect("Rage", "Rest & Rage (Rage)", "enemy_vulnerability",
               pct("Rest & Rage", rf"They receive {MAX} Damage Vulnerability"), ability="Rest & Rage", source="Equinox",
               condition="Enemy is enraged", note="Damage Vulnerability on enraged enemies."))
    add(effect("Webbed Embrace", "Webbed Embrace", "enemy_vulnerability",
               pct("Webbed Embrace", rf"{MAX} Damage Vulnerability"), source="Oraxia",
               condition="Enemy is webbed", note="Damage Vulnerability on webbed enemies."))
    add(effect("Demonium", "Demonium", "enemy_vulnerability", pct("Demonium", rf"{MAX} Damage Vulnerability"),
               source="Uriel", subsumed=None, condition="Enemy is hit by Demonium",
               note="Damage Vulnerability on affected enemies."))

    # --- Temple
    wail = pct("Ripper's Wail", rf"{MAX} Heat Damage")
    add(effect("Ripper's Wail", "Ripper's Wail", "elemental_add", wail, source="Temple", subsumed=None,
               element="Heat", per_stack=pct("Ripper's Wail", rf"{MAX} Backbeat Bonus"),
               cap=pct("Ripper's Wail", r"(\d+)% Heat Damage Cap"),
               stacks={"label": "Backbeat bonuses", "max": 135, "default": 0},
               note="Heat beside the weapon's elements, never combining. Each on-beat bonus adds more, up to the cap."))

    # --- Oraxia
    add(effect("Silken Stride", "Silken Stride", "extra_hit", pct("Silken Stride", rf"{MAX} Toxin Weapon Damage"),
               source="Oraxia", subsumed=None, weapons="primary_secondary", element="Toxin", group="Silken Stride",
               note="An Extra Hit of Toxin on primary and secondary weapons."))
    add(effect("Silken Stride (wall latched)", "Silken Stride (wall latched)", "extra_hit",
               pct("Silken Stride", rf"{MAX} Wall Latch Toxin Weapon Damage"), ability="Silken Stride",
               source="Oraxia", subsumed=None, weapons="primary_secondary", element="Toxin", group="Silken Stride",
               condition="Wall latched", note="Double the Toxin while wall latching."))

    # --- Wisp
    melee_speed, fire_rate = read("Reservoirs", r"Haste Mote increases Movement Speed and melee Attack Speed by "
                                                r"(\d+)% and Fire Rate by (\d+)%")
    add(effect("Haste Mote", "Haste Mote", "fire_rate_add", fire_rate / 100, ability="Reservoirs", source="Wisp",
               subsumed=None, weapons="ranged", note="Fire rate, added to fire rate mods."))
    add(effect("Haste Mote (melee)", "Haste Mote", "fire_rate_add", melee_speed / 100, ability="Reservoirs",
               source="Wisp", subsumed=None, weapons="melee", note="Melee attack speed, added to attack speed mods."))

    # --- Armor strip
    add(effect("Terrify", "Terrify", "armor_strip", pct("Terrify", rf"{MAX} \(armor reduction\)"), source="Nekros",
               cap=1.0, note="Strips enemy armor; adds to other armor strip."))
    add(effect("Seeking Shuriken", "Shuriken + Seeking Shuriken", "armor_strip",
               pct("Seeking Shuriken", r"\| 3 \|\| (\d+)% \|\|"), ability="Shuriken", source="Ash", cap=1.0,
               augment="Seeking Shuriken", note="Needs the Seeking Shuriken augment."))
    add(effect("Pillage", "Pillage", "armor_strip", pct("Pillage", rf"{MAX} \(shield/armor drain per enemy\)"),
               source="Hildryn", cap=1.0, note="Per cast. Shields are drained before armor."))
    low, high = read("Fire Blast", r"Armor reduction per cast is capped at (\d+)% - (\d+)%")
    add(effect("Fire Blast", "Fire Blast", "armor_strip", high / 100, source="Ember", low=low / 100,
               level={"label": "Immolation heat", "default": 1.0}, strength_cap=1.0,
               subsumed=pct("Fire Blast", r"Armor reduction per cast is capped at (\d+)%, achievable"),
               note="Reaches its cap at 100% Ability Strength; more strength adds nothing. Ember's own cast strips "
                    "more as Immolation heats up."))

    # --- Passives
    per, cap = read("Garuda/Abilities/Passive", r"gains (\d+)% additional Weapon Damage and Melee Damage for each kill "
                                                r"or assisted kill, up to a maximum of (\d+)%")
    add(effect("Garuda passive", "Death's Gate", "damage_mult", 0, source="Garuda", source_kind="passive",
               subsumed=None, scales=False, per_stack=per / 100, cap=cap / 100,
               stacks={"label": "Recent kills", "max": int(cap // per), "default": 0},
               note=f"{per:g}% per kill up to {cap:g}%. Multiplies with every other bonus."))
    per, cap, n = read("Nyx/Abilities/Passive", r"Critical Chance by (\d+)% per enemy up to a maximum of (\d+)% from "
                                                r"(\d+) enemies")
    add(effect("Nyx passive", "Thrive in Chaos", "crit_chance_add", 0, source="Nyx", source_kind="passive",
               subsumed=None, scales=False, per_stack=per / 100, cap=cap / 100, weapons="primary_secondary",
               stacks={"label": "Confused enemies nearby", "max": int(n), "default": 0},
               note=f"+{per:g}% critical chance per confused enemy, up to {cap:g}%. Added to crit mods."))
    add(effect("Zephyr passive", "Airborne", "crit_chance_add",
               pct("Zephyr/Abilities/Passive", r"weapons gain a (\d+)% Critical Chance bonus that additively stacks"),
               source="Zephyr", source_kind="passive", subsumed=None, scales=False, condition="Airborne",
               note="Added to critical chance mods while airborne."))
    add(effect("Yareli passive", "Critical Flow", "crit_chance_add",
               pct("Yareli/Abilities/Passive", r"increases Critical Chance on her secondary Weapon by (\d+)%"),
               source="Yareli", source_kind="passive", subsumed=None, scales=False, weapons="secondary",
               condition="Moving for at least 1.5 s", note="Added to critical chance mods on secondary weapons."))
    per, shields = read("Styanax/Abilities/Passive", r"Critical Chance bonus increases by (\d+)% per (\d+) Shield points")
    add(effect("Styanax passive", "Hoplite", "crit_chance_add", per / 100, source="Styanax", source_kind="passive",
               subsumed=None, scales=False, per_shields=shields, double_for=SPEARGUNS, low=0.0,
               level={"label": "Shields remaining", "default": 1.0},
               note=f"+{per:g}% critical chance per {shields:g} shields (his modded max shields from the Damage "
                    "taken tab), doubled on spearguns. Added to crit mods."))
    add(effect("Valkyr passive", "Rage", "base_damage_add",
               pct("Valkyr/Abilities/Passive", r"gaining up to (\d+)% additional melee damage bonus"), source="Valkyr",
               source_kind="passive", subsumed=None, scales=False, weapons="melee", low=0.0,
               level={"label": "Rage", "default": 0.0}, note="Melee damage, added to Pressure Point-style mods."))
    speed, damage = read("Excalibur/Abilities/Passive", r"receiving \+(\d+)% Attack Speed and \+(\d+)% damage bonuses")
    add(effect("Excalibur passive", "Swordsmanship", "base_damage_add", damage / 100, source="Excalibur",
               source_kind="passive", subsumed=None, scales=False, weapons="tags", weapon_tags=SWORDS,
               note="Swords, dual swords, nikanas and rapiers. Added to melee damage mods."))
    add(effect("Excalibur passive (speed)", "Swordsmanship", "fire_rate_add", speed / 100, source="Excalibur",
               source_kind="passive", subsumed=None, scales=False, weapons="tags", weapon_tags=SWORDS,
               note="Attack speed with swords, dual swords, nikanas and rapiers."))
    add(effect("Jade passive", "Judgments", "enemy_vulnerability",
               pct("Jade/Abilities/Passive", r"applying (\d+)% Damage Vulnerability"), source="Jade",
               source_kind="passive", subsumed=None, scales=False, condition="Enemy has Judgments",
               note="Damage Vulnerability on enemies with Judgments."))
    add(effect("Ash passive", "Bleed", "slash_dot_mult",
               pct("Ash/Abilities", r"Slash procs inflicted by Ash's weapons and abilities deal (\d+)% more damage"),
               source="Ash", source_kind="passive", subsumed=None, scales=False,
               note="Slash status damage."))

    # --- Survivability effects of infusable abilities that aren't in warframe_survivability.json
    add(effect("Parasitic Armor", "Parasitic Armor", "armor",
               pct("Parasitic Armor", rf"increase Armor value by {MAX} of maximum Shield capacity"),
               source="Helminth", source_kind="helminth", target="survivability",
               note="Turns max shields into flat armor (x Ability Strength); shields are disabled while it lasts."))
    add(effect("Empower", "Empower", "strength",
               pct("Empower", rf"granting it a {MAX} additive Ability Strength bonus"), source="Helminth",
               source_kind="helminth", target="any", scales=False,
               note="Ability Strength for the next ability cast."))
    return out


def main():
    if "--refresh" in sys.argv:
        wiki.REFRESH = True
    effects = build()
    # Parasitic Armor's armor is a share of shields; mark it so the engine knows
    for e in effects:
        if e["id"] == "Parasitic Armor":
            e["mode"] = "shields"
        elif e["kind"] == "armor":
            e["mode"] = "percent"
    ids = [e["id"] for e in effects]
    assert len(ids) == len(set(ids)), "duplicate effect ids"
    data = {
        "_about": "Built by scripts/build_ability_buffs.py from wiki.warframe.com. Values are max rank.",
        "effects": effects,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    by_target = {}
    for e in effects:
        by_target[e["target"]] = by_target.get(e["target"], 0) + 1
    print(f"ability buffs: {len(effects)} effects {by_target}")


if __name__ == "__main__":
    main()
