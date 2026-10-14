#!/usr/bin/env python3
"""Add each Warframe's passive to backend/data/processed/warframe_survivability.json.

Every frame gets `passive`: the in-game passive text plus the effects the
survivability calculator can use. Effects use the same fields as ability
effects (value, cap, stacks, level, low, mode) so the engine reads both the
same way. Kinds:

  dr          damage reduction layer
  armor       bonus armor, "flat" (added after armor mods) or "percent"
  health      bonus health, "flat" or "energy" (a share of max energy)
  resistance  per-damage-type resistance built by hits (doesn't stack with Adaptation)
  regen       health per second (shown, not part of effective health)
  shield_gate replaces the shield gate duration
  revive      self-revive or death prevention (shown as a note)
  note        a defensive effect the numbers can't show

Every number comes from the wiki's `<Frame>/Abilities/Passive` page: each
effect names a pattern that must match that page, and its values are read from
the match. A pattern that stops matching stops the script, so a changed wiki
page can't silently leave a stale number behind.

Sources: wiki.warframe.com Module:Warframes/data (in-game passive text) and the
`<Frame>/Abilities/Passive` pages (details), cached in data/raw/wiki_cache_current.
Run after build_warframe_data.py (which rewrites the file). Safe to re-run.

Usage: python scripts/build_passives.py [--refresh]
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_wiki_abilities as wiki  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "data" / "processed" / "warframe_survivability.json"


def effect(kind, name, pattern, build, condition="", note=""):
    """`build` turns the pattern's numbers into effect fields. `condition` makes it a toggle."""
    return {"kind": kind, "name": name, "pattern": pattern, "build": build, "condition": condition, "note": note}


def flat(value, **extra):
    return {"value": value, "mode": "flat", **extra}


# frame: (passive name where the wiki gives one, [effects]). Patterns run on the page's plain text.
SPECS = {
    "Atlas": ("Rubble", [
        effect("armor", "Rubble armor",
               r"restores (\d+) health or provides \d+ armor.*?Armor bonus is capped at ([\d,]+) points"
               r".*?decays at a rate of (\d+) armor points per second",
               lambda per, cap, decay: flat(0, perStack=per, cap=cap,
                                            stacks={"label": "Rubble picked up at full health", "max": int(cap // per),
                                                    "default": 10}),
               condition="Rubble picked up while at full health",
               note="{0:g} armor per piece of Rubble picked up at full health, up to {1:,.0f}. Decays at {2:g} armor/s. "
                    "Counted as flat armor added after armor mods."),
        effect("note", "Immovable", r"immune to Knockdown while in contact with the ground", lambda: {},
               note="Immune to knockdown while on the ground."),
    ]),
    "Baruuk": ("Restraint", [
        effect("dr", "Restraint", r"provides up to (\d+)% Damage Reduction when the meter is completely depleted",
               lambda pct: {"value": pct / 100, "low": 0.0, "level": {"label": "Restraint eroded", "default": 0.0}},
               note="Up to {0:g}% as the Restraint meter is eroded by Elude, Lull and Desolate Hands. Not affected by "
                    "Ability Strength."),
    ]),
    "Caliban": ("Adaptive Armor", [
        effect("resistance", "Adaptive Armor", r"stacking (\d+)% per hit up to a cap of (\d+)%",
               lambda per, cap: {"value": 0, "perStack": per / 100, "cap": cap / 100,
                                 "stacks": {"label": "Hits of this damage type", "max": int(cap // per), "default": 10}},
               condition="Recently hit by this damage type",
               note="{0:g}% resistance per hit of a damage type, up to {1:g}%. Does not stack with Adaptation: the higher "
                    "of the two applies."),
    ]),
    "Citrine": ("Geoluminesence", [
        effect("regen", "Geoluminesence",
               r"recover a base (\d+) Health points per second.*?increased by ([\d.]+) points, up to a maximum heal "
               r"rate of (\d+) points per second after collecting (\d+) Health Orbs",
               lambda base, per, cap, orbs: {"value": base, "perStack": per, "cap": cap,
                                             "stacks": {"label": "Health Orbs collected", "max": int(orbs), "default": 0}},
               note="{0:g} health/s, plus {1:g} per Health Orb collected, up to {2:g}/s."),
    ]),
    "Dagath": ("Abundant Abyss", [
        effect("note", "Abundant Abyss", r"granting her a (\d+)% chance .*? increase their effective yield by \+(\d+)%",
               lambda chance, bonus: {}, note="{0:g}% chance for Health and Energy Orbs to give {1:g}% more."),
    ]),
    "Frost": ("Fortifying Freeze", [
        effect("armor", "Fortifying Freeze", r"increases his Armor by (\d+) per enemy afflicted by a Cold status effect",
               lambda per: flat(0, perStack=per,
                                stacks={"label": "Enemies with Cold status nearby", "max": 40, "default": 0}),
               note="{0:g} armor per enemy with a Cold status within Affinity Range."),
    ]),
    "Gauss": ("", [
        effect("note", "Battery", r"maximum of (\d+)% for recharge rate and (\d+)% for recharge delay reduction",
               lambda rate, delay: {},
               note="Shields recharge up to {0:g}% faster with up to {1:g}% shorter delay, by battery level. "
                    "Shield recharge is not part of the numbers."),
    ]),
    "Grendel": ("", [
        effect("armor", "Swallowed enemies", r"passively grants him (\d+) Armor, to a maximum of ([\d,]+) bonus armor at the "
                                    r"(\d+) enemy cap",
               lambda per, cap, n: flat(0, perStack=per, cap=cap,
                                        stacks={"label": "Enemies in his belly", "max": int(n), "default": 0}),
               note="{0:g} armor per enemy swallowed by Feast, up to {2:g} enemies. Added after armor mods."),
    ]),
    "Harrow": ("", [
        effect("note", "Overshield capacity", r"possesses (\d+)% Overshields capacity, granting him a maximum of ([\d,]+) "
                                      r"Overshields", lambda pct, cap: {},
               note="Overshield cap {1:,.0f} ({0:g}% of normal). Overshields are not part of the numbers."),
    ]),
    "Hildryn": ("Advanced Shielding", [
        effect("shield_gate", "Advanced Shielding", r"Shield Gating grace period is ([\d.]+) seconds when fully charged",
               lambda s: {"value": s},
               note="Full shield gate lasts {0:g}s. Overshields also protect her health from Toxin."),
    ]),
    "Inaros": ("Undying", [
        effect("revive", "Sarcophagus", r"On fatal injury and entering Bleedout, Inaros entombs himself", lambda: {},
               note="On lethal damage Inaros enters a sarcophagus and revives himself with melee attacks."),
        effect("note", "Melee Finisher Heal", r"Killing enemies with melee Finishers restores (\d+)% of Inaros's "
                                              r"maximum Health", lambda pct: {},
               note="Finisher kills restore {0:g}% of max health."),
    ]),
    "Lavos": ("Valence Block", [
        effect("note", "Valence Block", r"gains status immunity for (\d+) seconds upon collecting an Energy or "
                                        r"Universal Orb", lambda s: {},
               note="Energy and Universal Orbs cleanse status effects and give {0:g}s of status immunity."),
    ]),
    "Mesa": ("", [
        effect("health", "No melee weapon", r"\+(\d+) health when no melee weapon is equipped",
               lambda hp: flat(hp), condition="No melee weapon equipped", note="+{0:g} health without a melee weapon."),
    ]),
    "Nekros": ("", [
        effect("regen", "Health from nearby deaths", r"regenerates (\d+) Health when an enemy dies within (\d+) meters",
               lambda hp, m: {"value": 0, "perStack": hp,
                              "stacks": {"label": "Enemy deaths within 10 m per second", "max": 10, "default": 0}},
               note="{0:g} health for each enemy that dies within {1:g} m."),
    ]),
    "Nidus": ("Undying", [
        effect("revive", "Undying", r"at least (\d+) stacks of Mutation, Nidus will consume the \d+ stacks to avoid "
                                    r"bleedout while receiving (\d+) seconds of invulnerability and restoring (\d+)%",
               lambda n, s, hp: {},
               note="Lethal damage with {0:g}+ Mutation stacks consumes {0:g} for {1:g}s of invulnerability and "
                    "{2:g}% health."),
    ]),
    "Nokko": ("Vital Decay", [
        effect("revive", "Vital Decay", r"Nokko will revive if he can reach one of his active mushrooms within (\d+) "
                                        r"seconds", lambda s: {},
               note="With a mushroom placed, lethal damage turns Nokko into a Sprodling that revives by reaching it "
                    "within {0:g}s."),
    ]),
    "Oberon": ("Righteous Negation", [
        effect("note", "Righteous Negation", r"Righteous Negation for up to (\d+) charges", lambda n: {},
               note="Health Orbs give charges (up to {0:g}) that each block one instance of damage."),
    ]),
    "Oraxia": ("Predator's Lurk", [
        effect("note", "Predator's Lurk", r"Invisible for (\d+) seconds", lambda s: {},
               note="Wall latching makes Oraxia invisible for {0:g}s."),
    ]),
    "Sevagoth": ("Tombstone", [
        effect("revive", "Tombstone", r"collect the souls of (\d+) enemies", lambda n: {},
               note="On death his Shadow revives him by collecting {0:g} souls."),
    ]),
    "Titania": ("Upsurge", [
        effect("regen", "Upsurge", r"regenerates (\d+) Health points per second for (\d+) seconds",
               lambda hp, s: {"value": hp}, condition="Within 20 s of casting an ability",
               note="{0:g} health/s for {1:g}s after each ability cast."),
    ]),
    "Trinity": ("Lifegiver", [
        effect("health", "Lifegiver", r"increases their Health equal to (\d+)% \(\d+% in Conclave\) of Trinity's "
                                      r"total Energy pool",
               lambda pct: {"value": pct / 100, "mode": "energy"},
               note="+{0:g}% of max energy as health. Uses rank 30 energy; energy mods are not counted."),
    ]),
    "Valkyr": ("Rage", [
        effect("revive", "Rage", r"at or above (\d+)% Rage, all of it is consumed to prevent death, grant her (\d+) "
                                 r"seconds of invulnerability and regenerate (\d+)% health",
               lambda rage, s, hp: {},
               note="Fatal damage at {0:g}%+ Rage is prevented: {1:g}s of invulnerability and {2:g}% health."),
    ]),
    "Wisp": ("", [
        effect("note", "Airborne invisibility", r"invisible to enemies indefinitely until she lands or fires a weapon", lambda: {},
               note="Invisible while airborne until she fires a weapon."),
    ]),
    "Wukong": ("", [
        effect("revive", "Survival techniques", r"randomly allowed (\d+) of these techniques per mission.*?Invulnerable for "
                                          r"(\d+) seconds, restore (\d+)% health",
               lambda n, s, hp: {},
               note="Survives fatal damage {0:g} times per mission: {1:g}s of invulnerability and {2:g}% health, plus "
                    "a random buff."),
    ]),
    "Xaku": ("", [
        effect("dr", "Area damage reduction", r"protected by a (\d+)% Damage Reduction against area of effect damage\. "
                                              r"Passive dodge chance and area damage reduction both raise to (\d+)%",
               lambda pct, untime: {"value": pct / 100},
               condition="The hit is area-of-effect damage (an explosion)",
               note="{0:g}% against explosions, {1:g}% while The Vast Untime is active."),
        effect("note", "Dodge", r"has a (\d+)% Dodge chance to harmlessly phase through incoming enemy weapon attacks",
               lambda pct: {}, note="{0:g}% chance to dodge enemy weapon attacks. Evasion is not part of the numbers."),
    ]),
}

FIELDS = ("value", "cap", "stacks", "perStack", "level", "low", "mode")


def base_of(name: str) -> str:
    return re.sub(r" (Prime|Umbra)$", "", name)


def clean_text(text: str) -> str:
    """In-game passive text: drop colour tags, keep paragraphs."""
    text = re.sub(r"<[A-Z_0-9]+>", "", text or "")
    return re.sub(r"\n{2,}", "\n", text).strip()


def build_passive(frame: str, ingame: str) -> dict:
    name, specs = SPECS.get(frame, ("", []))
    page = wiki.fetch_raw(f"{frame}/Abilities/Passive") or ""
    # Tabbed pages wrap everything in {{#tag:tabber|...}}; unwrap it so the tabs read as plain text
    page = page.replace("{{#tag:tabber|", "").replace("{{!-!}}", "\n").replace("{{!}}-{{!}}", "\n")
    text = re.sub(r"\s+", " ", wiki.strip_markup(page))
    effects = []
    for spec in specs:
        hit = re.search(spec["pattern"], text)
        if not hit:
            raise SystemExit(f"{frame} / {spec['name']}: pattern no longer matches the wiki passive page:\n  "
                             f"{spec['pattern']}")
        numbers = [float(g.replace(",", "")) for g in hit.groups()]
        fields = spec["build"](*numbers)
        out = {"kind": spec["kind"], "name": spec["name"]}
        for key in FIELDS:
            out[key] = fields.get(key)
        out.update({
            "scalesWithStrength": False,
            "condition": spec["condition"],
            "note": spec["note"].format(*numbers),
            "applies": "all",
        })
        effects.append(out)
    return {"name": name, "description": clean_text(ingame), "effects": effects}


def main():
    if "--refresh" in sys.argv:
        wiki.REFRESH = True
    module = wiki.load_passives()
    data = json.loads(OUT.read_text(encoding="utf-8"))
    built = {}
    for name, frame in data["warframes"].items():
        base = base_of(name)
        if base not in built:
            built[base] = build_passive(base, module.get(base) or module.get(name) or "")
        frame["passive"] = built[base]
        # passive notes now live in `passive`
        frame["special"] = [s for s in frame["special"] if not s.startswith("Passive:")]
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with_effects = sorted(b for b, p in built.items() if p["effects"])
    missing = sorted(set(SPECS) - set(built))
    print(f"passives: {len(data['warframes'])} warframes, {len(with_effects)} base frames with survivability effects")
    print(f"  {', '.join(with_effects)}")
    if missing:
        print(f"  specs for frames not in the data: {missing}")


if __name__ == "__main__":
    main()
