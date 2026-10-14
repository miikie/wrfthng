"""Warframe abilities, passives and Helminth infusions that change weapon damage.

The catalogue (data/processed/ability_buffs.json) lists each effect with how the
damage pipeline applies it; helminth.json lists what the Helminth can infuse and
the damage-buff placement rule. `resolve` turns a Warframe loadout (the frame,
its infused ability, the player's toggles and its Ability Strength) into the
`Buffs` the damage pipeline understands.

A Warframe's effects are its own abilities' effects (minus the ability an
infusion replaces), its passive's, and the infused ability's at its subsumed
values. Ability Strength multiplies an effect's value when the effect scales.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.damage import Buffs
from engine.weapons import WeaponData


@dataclass
class EffectState:
    active: Optional[bool] = None      # None: the default (unconditional passives on, everything else off)
    stacks: Optional[float] = None
    level: Optional[float] = None


@dataclass
class LoadoutEffect:
    """One effect available to this loadout, with its value right now."""
    effect: dict
    variant: str                       # "own", "passive" or "infused"
    active: bool
    value: float
    applies: bool                      # False when the weapon can't use it
    reason: str = ""
    text: str = ""


def base_of(name: str) -> str:
    return re.sub(r" (Prime|Umbra)$", "", name)


def _pct(v: float) -> str:
    return f"{v * 100:.0f}%" if abs(v * 100 - round(v * 100)) < 0.05 else f"{v * 100:.1f}%"


EFFECT_TEXT = {
    "faction_add": lambda v: f"+{_pct(v)} faction damage",
    "damage_mult": lambda v: f"x{1 + v:.2f} damage",
    "hit_multiplier": lambda v: f"x{v:.2f} damage on the spot",
    "enemy_vulnerability": lambda v: f"+{_pct(v)} damage vulnerability",
    "base_damage_add": lambda v: f"+{_pct(v)} base damage",
    "elemental_add": lambda v: f"+{_pct(v)} elemental damage",
    "extra_hit": lambda v: f"Extra Hit of {_pct(v)} of each hit",
    "crit_chance_add": lambda v: f"+{_pct(v)} critical chance (with mods)",
    "crit_chance_flat": lambda v: f"+{_pct(v)} critical chance (flat)",
    "fire_rate_add": lambda v: f"+{_pct(v)} fire rate / attack speed",
    "armor_strip": lambda v: f"-{_pct(v)} enemy armor",
    "slash_dot_mult": lambda v: f"+{_pct(v)} Slash status damage",
    "strength": lambda v: f"+{_pct(v)} Ability Strength",
}


class AbilityBuffCatalogue:
    def __init__(self, buffs_path: str = "data/processed/ability_buffs.json",
                 helminth_path: str = "data/processed/helminth.json",
                 ability_names: Optional[Dict[str, List[str]]] = None):
        root = Path(__file__).resolve().parent.parent

        def load(path: str) -> dict:
            p = Path(path)
            with open(p if p.is_absolute() else root / p, encoding="utf-8") as f:
                return json.load(f)

        self.effects: Dict[str, dict] = {e["id"]: e for e in load(buffs_path)["effects"]}
        helminth = load(helminth_path)
        self.subsumable: Dict[str, dict] = helminth["subsumable"]
        self.helminth_abilities: Dict[str, dict] = helminth["helminthAbilities"]
        self.restrictions: dict = helminth["restrictions"]
        self.ability_names = ability_names or {}

    # ------------------------------------------------------------------
    def infusable(self, ability: str) -> Optional[dict]:
        return self.subsumable.get(ability) or self.helminth_abilities.get(ability)

    def check_infusion(self, warframe: str, ability: str, slot: int) -> Optional[str]:
        """Why this infusion isn't possible, or None if it is."""
        info = self.infusable(ability)
        if info is None:
            return f"{ability} cannot be infused through the Helminth"
        names = self.ability_names.get(warframe, [])
        if not 1 <= slot <= max(len(names), 4):
            return f"Ability slot must be 1 to 4, not {slot}"
        if ability in names:
            return f"{warframe} already has {ability}"
        base = base_of(warframe)
        only = self.restrictions["onlyReplace"].get(base)
        if ability in self.restrictions["abilities"] and only:
            if names and names[slot - 1] != only:
                return (f"On {base}, {ability} can only replace {only}: the Helminth keeps "
                        f"{', '.join(self.restrictions['abilities'])} from stacking with a Warframe's own damage buff")
        return None

    # ------------------------------------------------------------------
    @staticmethod
    def weapon_reason(effect: dict, weapon: Optional[WeaponData]) -> str:
        """Why the weapon can't use this effect, or ""."""
        if weapon is None or effect["target"] != "weapon":
            return ""
        kind = effect["weapons"]
        if kind == "melee" and not weapon.is_melee:
            return "Melee weapons only"
        if kind == "ranged" and weapon.is_melee:
            return "Guns only"
        if kind == "primary_secondary" and weapon.category not in ("LongGuns", "Pistols"):
            return "Primary and secondary weapons only"
        if kind == "secondary" and weapon.category != "Pistols":
            return "Secondary weapons only"
        if kind == "tags" and not set(effect["weaponTags"] or []) & set(weapon.tags):
            return "Not this weapon class"
        return ""

    def value(self, effect: dict, variant: str, state: EffectState, strength: float,
              shields: float = 0.0, weapon: Optional[WeaponData] = None, headshot: bool = False) -> float:
        base = effect["value"]
        cap = effect["cap"]
        if variant == "infused":
            if effect["subsumed"] not in (None, "same"):
                base = effect["subsumed"]
            if effect["subsumedCap"] is not None:
                cap = effect["subsumedCap"]
        # an infused version with its own value has no meter (subsumed Fire Blast has no Immolation heat)
        fixed = variant == "infused" and effect["subsumed"] not in (None, "same")
        if effect["level"] and not fixed:
            level = effect["level"]["default"] if state.level is None else max(0.0, min(state.level, 1.0))
            low = effect["low"] or 0.0
            value = low + (base - low) * level
        elif effect["stacks"]:
            count = effect["stacks"]["default"] if state.stacks is None else state.stacks
            count = max(0.0, min(count, effect["stacks"]["max"]))
            value = base + (effect["perStack"] or 0.0) * count
        else:
            value = base
        if effect["perShields"]:
            value = value * shields / effect["perShields"]
            names = effect["doubleFor"] or []
            if weapon is not None and any(weapon.name == n or weapon.name.startswith(n + " ") for n in names):
                value *= 2
        if effect["scalesWithStrength"]:
            s = strength if effect["strengthCap"] is None else min(strength, effect["strengthCap"])
            value *= s
        if cap is not None:
            value = min(value, cap)
        wp = effect.get("weakPoint")
        if wp and headshot:
            value = min(value * wp["multiplier"], wp["cap"])
        return value

    # ------------------------------------------------------------------
    def loadout(self, warframe: str, infused: Optional[str], slot: Optional[int]) -> List[Tuple[dict, str]]:
        """(effect, variant) for every effect this loadout has, weapon-side or not."""
        base = base_of(warframe)
        names = self.ability_names.get(warframe) or self.ability_names.get(base) or []
        replaced = names[slot - 1] if infused and slot and 1 <= slot <= len(names) else ""
        out = []
        for e in self.effects.values():
            if e["sourceKind"] == "passive" and e["source"] == base:
                out.append((e, "passive"))
            elif e["sourceKind"] == "ability" and e["source"] == base and e["ability"] in names \
                    and e["ability"] != replaced:
                out.append((e, "own"))
        if infused:
            for e in self.effects.values():
                if e["ability"] == infused and e["subsumed"] is not None:
                    out.append((e, "infused"))
        return out

    def resolve(
        self, warframe: str, *, states: Dict[str, EffectState], strength: float,
        weapon: Optional[WeaponData] = None, headshot: bool = False, shields: float = 0.0,
        infused: Optional[str] = None, slot: Optional[int] = None,
    ) -> Tuple[Buffs, float, float, List[LoadoutEffect]]:
        """Returns (Buffs for the weapon, armor strip, Ability Strength used, every effect of the loadout)."""
        effects = self.loadout(warframe, infused, slot)

        def state_of(e: dict, variant: str) -> EffectState:
            return states.get(e["id"], EffectState())

        def is_active(e: dict, variant: str) -> bool:
            s = state_of(e, variant)
            if s.active is not None:
                return s.active
            return variant == "passive" and not e["condition"]

        # Empower adds Ability Strength to the next cast: counted for every buff here
        strength += sum(e["value"] for e, v in effects if e["kind"] == "strength" and is_active(e, v))

        buffs = Buffs()
        armor_strip = 0.0
        listed: List[LoadoutEffect] = []
        best_in_group: Dict[str, Tuple[float, LoadoutEffect]] = {}
        for e, variant in effects:
            if e["target"] == "survivability":
                continue
            active = is_active(e, variant)
            reason = self.weapon_reason(e, weapon)
            value = self.value(e, variant, state_of(e, variant), strength, shields, weapon, headshot)
            item = LoadoutEffect(effect=e, variant=variant, active=active, value=value, applies=not reason,
                                 reason=reason, text=EFFECT_TEXT[e["kind"]](value))
            listed.append(item)
            if not active or reason or e["kind"] == "strength":
                continue
            if e["group"]:
                held = best_in_group.get(e["group"])
                if held is None or value > held[0]:
                    best_in_group[e["group"]] = (value, item)
                continue
            armor_strip = self._apply(buffs, e, value, armor_strip)
        for value, item in best_in_group.values():
            armor_strip = self._apply(buffs, item.effect, value, armor_strip)
        return buffs, min(1.0, armor_strip), strength, listed

    @staticmethod
    def _apply(buffs: Buffs, e: dict, value: float, armor_strip: float) -> float:
        kind = e["kind"]
        if kind == "faction_add":
            buffs.faction_add += value
        elif kind in ("damage_mult", "enemy_vulnerability"):
            buffs.ability_multiplier *= 1.0 + value
        elif kind == "hit_multiplier":
            buffs.ability_multiplier *= max(value, 1.0)
        elif kind == "base_damage_add":
            buffs.base_damage_add += value
        elif kind == "elemental_add":
            buffs.elemental_add[e["element"]] = buffs.elemental_add.get(e["element"], 0.0) + value
        elif kind == "extra_hit":
            buffs.extra_hits.append((e["element"], value))
        elif kind == "crit_chance_add":
            buffs.crit_chance_add += value
        elif kind == "crit_chance_flat":
            buffs.crit_chance_flat += value
        elif kind == "fire_rate_add":
            buffs.fire_rate_add += value
        elif kind == "slash_dot_mult":
            buffs.slash_dot_mult *= 1.0 + value
        elif kind == "armor_strip":
            armor_strip += value
        return armor_strip


def merge_buffs(a: Buffs, b: Buffs) -> Buffs:
    """Two sets of buffs on one weapon: additive fields add, multipliers multiply."""
    out = Buffs(**{k: v for k, v in vars(a).items()})
    for name, value in vars(b).items():
        if name in ("ability_multiplier", "slash_dot_mult"):
            setattr(out, name, getattr(out, name) * value)
        elif name == "crit_chance_floor":
            out.crit_chance_floor = max(out.crit_chance_floor, value)
        elif name == "elemental_add":
            out.elemental_add = {**a.elemental_add}
            for k, v in value.items():
                out.elemental_add[k] = out.elemental_add.get(k, 0.0) + v
        elif name == "extra_hits":
            out.extra_hits = list(a.extra_hits) + list(value)
        else:
            setattr(out, name, getattr(out, name) + value)
    return out
