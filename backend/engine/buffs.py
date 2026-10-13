"""Cross-system buffs: Focus ways, companion precepts, bond mods and set bonuses.

The catalogue (data/processed/buffs.json) lists each buff with its per-rank
values. `resolve` turns the player's selection into the `Buffs` the damage
pipeline understands, separately for each thing being calculated (the
Warframe's weapon, the companion's weapon, or the amp).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.damage import Buffs

# kind -> Buffs field, for kinds that map one-to-one
DIRECT = {
    "base_damage_add": "base_damage_add",
    "physical_add": "physical_add",
    "crit_chance_flat": "crit_chance_flat",
    "crit_damage_add": "crit_damage_add",
    "crit_mult_flat": "crit_mult_flat",
    "crit_per_combo": "crit_per_combo",
    "fire_rate_add": "fire_rate_add",
    "final_multiplier": "final_multiplier",
}


@dataclass
class AppliedBuff:
    id: str
    name: str
    group: str
    effect: str          # what it did, in words
    verified: bool
    uptime: Optional[float]
    targets: List[str] = field(default_factory=list)


def _pct(v: float) -> str:
    return f"{v * 100:.0f}%"


EFFECT_TEXT = {
    "base_damage_add": lambda v: f"+{_pct(v)} base damage",
    "physical_add": lambda v: f"+{_pct(v)} physical damage",
    "crit_chance_flat": lambda v: f"+{_pct(v)} critical chance (flat points)",
    "crit_chance_floor": lambda v: f"critical chance at least {_pct(v)}",
    "crit_damage_add": lambda v: f"+{_pct(v)} critical damage",
    "crit_mult_flat": lambda v: f"+{v:.1f}x final critical multiplier",
    "crit_per_combo": lambda v: f"+{_pct(v)} critical chance per combo multiplier",
    "fire_rate_add": lambda v: f"+{_pct(v)} fire rate",
    "final_multiplier": lambda v: f"x{1 + v:.2f} damage to the marked enemy",
    "armor_strip": lambda v: f"-{_pct(v)} enemy armor",
}


class BuffCatalogue:
    def __init__(self, path: str = "data/processed/buffs.json"):
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        with open(p, encoding="utf-8") as f:
            self.buffs: Dict[str, dict] = {b["id"]: b for b in json.load(f)["buffs"]}

    def value(self, buff: dict, rank: Optional[int], amount: Optional[float]) -> float:
        max_rank = buff["maxRank"]
        rank = max_rank if rank is None else max(0, min(rank, max_rank))
        value = buff["perRank"][rank]
        spec = buff.get("amount")
        if spec:
            amount = spec["default"] if amount is None else max(spec["min"], min(amount, spec["max"]))
            value *= amount
        return value

    def unmet(self, buff_id: str, companion: Optional[dict], weapon_is_melee: bool) -> Optional[str]:
        """Why a buff cannot apply to this loadout, or None if it can."""
        need = self.buffs[buff_id]["requires"]
        if need["meleeWeapon"] and not weapon_is_melee:
            return "Needs " + need["text"]
        wants_companion = need["anyCompanion"] or need["companions"] or need["companionTypes"]
        if not wants_companion:
            return None
        if companion is None:
            return "Needs " + need["text"]
        if need["anyCompanion"]:
            return None
        if companion["name"] in need["companions"] or companion["type"] in need["companionTypes"]:
            return None
        return "Needs " + need["text"]

    def resolve(
        self, selections: List[Tuple[str, Optional[int], Optional[float]]],
    ) -> Tuple[Dict[str, Buffs], float, List[AppliedBuff]]:
        """Returns ({target: Buffs}, armor strip fraction, what was applied).

        Targets are "weapon", "companion" and "amp". Unknown ids raise KeyError.
        """
        per_target = {"weapon": Buffs(), "companion": Buffs(), "amp": Buffs()}
        armor_strip = 0.0
        applied: List[AppliedBuff] = []

        for buff_id, rank, amount in selections:
            buff = self.buffs[buff_id]
            kind = buff["kind"]
            value = self.value(buff, rank, amount)
            targets = [t for t in buff["appliesTo"] if t in per_target]

            if kind == "armor_strip":
                value = min(1.0, value)
                armor_strip = min(1.0, armor_strip + value)
            for target in targets:
                b = per_target[target]
                if kind == "crit_chance_floor":
                    b.crit_chance_floor = max(b.crit_chance_floor, value)
                elif kind == "physical_add" and target == "amp":
                    # Phoenix Talons is "Operator damage" for amps: one additive damage bonus
                    b.base_damage_add += value
                elif kind in DIRECT:
                    setattr(b, DIRECT[kind], getattr(b, DIRECT[kind]) + value)

            applied.append(AppliedBuff(
                id=buff_id, name=buff["name"], group=buff["group"],
                effect=EFFECT_TEXT[kind](value), verified=buff["verified"],
                uptime=None if kind == "armor_strip" else buff.get("uptime"), targets=buff["appliesTo"],
            ))

        return per_target, armor_strip, applied
