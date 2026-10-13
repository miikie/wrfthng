"""Amp assembly: prism (primary fire) + scaffold (alt fire) + brace (stat modifier).

Amp parts are ordinary weapons that take no mods. Each fire mode can have more
than one damage instance per shot (direct hit + explosion), which are
calculated separately and summed. Instead of reloading, an amp spends an
energy pool that recharges after a delay.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.modding import ModdedStats
from engine.weapons import WeaponData

ARCANE_STAT_FIELD = {
    "DAMAGE": "damage_bonus",
    "CRIT_CHANCE": "crit_chance_bonus",
    "CRIT_DAMAGE": "crit_damage_bonus",
    "STATUS_CHANCE": "status_chance_bonus",
    "FIRE_RATE": "fire_rate_bonus",
}


@dataclass
class AmpFireMode:
    part_name: str
    attacks: List[WeaponData]     # one per damage instance of a single shot
    ammo_cost: float
    crit_chance_flat: float       # from the brace
    status_chance_flat: float
    notes: List[str] = field(default_factory=list)


class AmpLoader:
    def __init__(self, path: str = "data/processed/amps.json"):
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        with open(p, encoding="utf-8") as f:
            self.data = json.load(f)
        self.prisms: Dict[str, dict] = {x["name"]: x for x in self.data["prisms"]}
        self.scaffolds: Dict[str, dict] = {x["name"]: x for x in self.data["scaffolds"]}
        self.braces: Dict[str, dict] = {x["name"]: x for x in self.data["braces"]}
        self.arcanes: Dict[str, dict] = {x["name"]: x for x in self.data["arcanes"]}

    def fire_mode(self, part: dict, brace: Optional[dict]) -> AmpFireMode:
        brace = brace or {}
        energy = part["energy"] + brace.get("energy", 0)
        delay = max(0.0, part["rechargeDelay"] + brace.get("rechargeDelay", 0))
        rate = part["rechargeRate"] + brace.get("rechargeRate", 0)
        recharge_time = delay + (energy / rate if rate > 0 else 0.0)
        first = part["attacks"][0]
        notes: List[str] = []
        # Trigger pulls per second. Charge shots wait out the charge first; burst
        # triggers go through the engine's burst formula (three shots per pull).
        fire_rate = first["fireRate"]
        trigger = "AUTO"
        if part["trigger"] == "CHARGE" and first.get("chargeTime"):
            fire_rate = 1.0 / (first["chargeTime"] + 1.0 / first["fireRate"])
            notes.append(f"Charge trigger: {first['chargeTime']:g}s charge before each shot.")
        elif part["trigger"] == "BURST":
            trigger = "BURST"
            notes.append(f"Burst trigger: {int(first.get('burstCount') or 3)} shots per pull.")
        for a in part["attacks"]:
            falloff = a.get("falloff")
            if falloff and falloff["reduction"] > 0:
                kind = "Area damage" if a.get("area") else "Damage"
                near = (f"full within {falloff['start']:g}m, " if falloff["start"] > 0 else "full at the centre, ")
                notes.append(f"{a['name']}: {kind} shown at full strength; {near}"
                             f"{(1 - falloff['reduction']) * 100:.0f}% at {falloff['end']:g}m.")
        attacks = []
        for a in part["attacks"]:
            attacks.append(WeaponData(
                name=f"{part['name']}: {a['name']}", unique_name="", category="OperatorAmps",
                damage=dict(a["damage"]), total_damage=sum(a["damage"].values()),
                crit_chance=a["critChance"], crit_mult=a["critMult"], status_chance=a["statusChance"],
                # every instance of one shot shares the trigger pull's rate
                fire_rate=fire_rate, mag_size=int(energy), reload_time=recharge_time,
                multishot=a.get("multishot", 1) or 1, trigger=trigger,
            ))
        return AmpFireMode(
            part_name=part["name"], attacks=attacks,
            ammo_cost=first.get("ammoCost") or 1,
            crit_chance_flat=brace.get("critChance", 0.0),
            status_chance_flat=brace.get("statusChance", 0.0),
            notes=notes,
        )

    def arcane_stats(self, arcanes: List[Tuple[str, Optional[int]]]) -> Tuple[ModdedStats, List[str]]:
        """Amp arcanes as stat bonuses (all assumed active). Unknown names raise KeyError."""
        stats, texts = ModdedStats(), []
        for name, rank in arcanes:
            arcane = self.arcanes[name]
            max_rank = arcane["maxRank"]
            rank = max_rank if rank is None else max(0, min(rank, max_rank))
            value = arcane["perRank"][rank]
            attr = ARCANE_STAT_FIELD[arcane["stat"]]
            setattr(stats, attr, getattr(stats, attr) + value)
            texts.append(f"{name}: {arcane['text']}")
        return stats, texts
