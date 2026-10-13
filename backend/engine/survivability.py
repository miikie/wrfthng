"""How much damage a Warframe takes.

Rules (wiki.warframe.com, October 2026):
  - Warframe armor reduces damage to health only: DR = armor / (armor + 300).
    This is not the enemy armor formula and has no cap.
  - Warframe shields take 50% less damage and ignore armor. Toxin bypasses them.
  - Damage reduction sources stack multiplicatively: each one reduces what the
    previous ones let through.
  - Health, shield and armor mods add up and multiply the rank 30 base stat.
  - Overguard and ability rings are separate pools that are hit before shields.
  - Enemy damage scales with level: 1 + 0.015 x (level - base)^1.55, with a
    modified two-curve version for Corpus, Grineer and Techrot.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from engine.constants import f32
from engine.enemies import DualCurve, ScalingCurve, eval_dual_curve
from engine.modding import ResolvedMod

TENNO_ARMOR_CONSTANT = 300.0
SHIELD_DAMAGE_REDUCTION = 0.5
PHYSICAL = {"Impact", "Puncture", "Slash"}
KINETIC = PHYSICAL | {"Heat", "Cold", "Blast"}      # what Gauss's Kinetic Plating covers
UMBRAL_SET_MULTIPLIER = {1: 1.0, 2: 1.25, 3: 1.75}

# Enemy damage scaling
STANDARD_DAMAGE_CURVE = ScalingCurve(0.015, 1.55)
MODIFIED_DAMAGE_CURVE = DualCurve(ScalingCurve(0.015, 1.75), ScalingCurve(0.0075, 1.55), 1, 25)
MODIFIED_DAMAGE_FACTIONS = {"Corpus", "Grineer", "Techrot"}
FACTION_ATTACK_MULTIPLIER = {"Corpus": 2.0, "Grineer": 2.0, "Techrot": 2.0, "Infested": 3.0}


def enemy_damage_multiplier(faction: str, base_level: int, level: int) -> float:
    """Multiplier on an enemy's base damage at a given level (level scaling x faction attack multiplier)."""
    gained = max(0, level - base_level)
    if faction in MODIFIED_DAMAGE_FACTIONS:
        scaling = eval_dual_curve(MODIFIED_DAMAGE_CURVE, gained)
    else:
        scaling = f32(1.0 + f32(STANDARD_DAMAGE_CURVE.coefficient * f32(gained ** STANDARD_DAMAGE_CURVE.exponent)))
    return f32(scaling * FACTION_ATTACK_MULTIPLIER.get(faction, 1.0))


def armor_damage_reduction(armor: float) -> float:
    armor = max(0.0, armor)
    return f32(armor / f32(armor + TENNO_ARMOR_CONSTANT))


def stack_reductions(reductions: List[float]) -> float:
    """Total damage reduction of sources that each cut what the others let through."""
    remaining = 1.0
    for r in reductions:
        remaining = f32(remaining * f32(1.0 - r))
    return f32(1.0 - remaining)


def shield_gate_seconds(shields: float) -> float:
    """Invulnerability after shields break, by max shields (wiki approximation)."""
    if shields <= 0:
        return 0.0
    if shields < 53:
        return shields / 180 + 1 / 3
    if shields <= 1150:
        return (shields / 350) ** 0.65 + 1 / 3
    return 2.5


@dataclass
class AbilityState:
    active: bool = True
    stacks: Optional[float] = None     # daggers, particles, kills...
    level: Optional[float] = None      # 0-1 meter


@dataclass
class Layer:
    name: str
    reduction: float
    damage_after: float
    cumulative: float
    note: str = ""


@dataclass
class SurvivabilityResult:
    warframe: str
    base_stats: Dict[str, float] = field(default_factory=dict)
    modded_stats: Dict[str, float] = field(default_factory=dict)
    ability_strength: float = 1.0
    armor_dr: float = 0.0
    total_dr: float = 0.0                 # against damage to health
    shield_dr: float = 0.0                # against damage to shields
    layers: List[Layer] = field(default_factory=list)
    incoming_per_hit: float = 0.0
    damage_type: str = ""
    damage_per_hit: float = 0.0           # to health, after every layer
    shield_damage_per_hit: float = 0.0
    hits_per_second: float = 1.0
    health_ehp: float = 0.0
    shield_ehp: float = 0.0
    pool_ehp: float = 0.0
    total_ehp: float = 0.0
    pools: List[Dict[str, float]] = field(default_factory=list)
    time_to_kill: float = 0.0             # seconds, ignoring shield gating and regeneration
    shield_gate_seconds: float = 0.0
    enemy_damage_multiplier: float = 1.0
    notes: List[str] = field(default_factory=list)


class SurvivabilityCalculator:
    def __init__(self, path: str = "data/processed/warframe_survivability.json"):
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        self.warframes: Dict[str, dict] = data["warframes"]
        self.arcanes: Dict[str, dict] = {a["name"]: a for a in data["arcanes"]}

    # ------------------------------------------------------------------
    def ability_value(self, ability: dict, state: AbilityState, strength: float) -> float:
        """Current value of an ability effect (a DR fraction, an armor bonus, or pool points)."""
        scale = strength if ability["scalesWithStrength"] else 1.0
        if ability.get("stacks"):
            count = ability["stacks"]["default"] if state.stacks is None else state.stacks
            count = max(0.0, min(count, ability["stacks"]["max"]))
            value = f32(f32(ability["value"] + f32(ability["perStack"] * count)) * scale) \
                if ability["value"] else f32(f32(ability["perStack"] * count) * scale)
        elif ability.get("level"):
            level = ability["level"]["default"] if state.level is None else state.level
            level = max(0.0, min(level, 1.0))
            low = ability["low"] if ability.get("low") is not None else 0.0
            value = f32(f32(low + f32((ability["value"] - low) * level)) * scale)
        else:
            value = f32(ability["value"] * scale)
        if ability.get("cap") is not None:
            value = min(value, ability["cap"])
        return value

    @staticmethod
    def applies(ability: dict, damage_type: str) -> bool:
        if ability["applies"] == "kinetic":
            return damage_type in KINETIC
        return True

    # ------------------------------------------------------------------
    def calculate(
        self,
        warframe: str,
        mods: Optional[List[ResolvedMod]] = None,
        abilities: Optional[Dict[str, AbilityState]] = None,
        arcanes: Optional[List[tuple]] = None,          # [(name, rank or None)]
        incoming: float = 1000.0,
        damage_type: str = "Slash",
        hits_per_second: float = 1.0,
        strength_bonus: float = 0.0,                    # extra Ability Strength from outside the mods
        mod_ranks: Optional[Dict[str, int]] = None,
        mod_stacks: Optional[Dict[str, int]] = None,
        extra_armor: float = 0.0,
        enemy_multiplier: float = 1.0,
    ) -> SurvivabilityResult:
        frame = self.warframes[warframe]
        mods = mods or []
        abilities = abilities or {}
        base = frame["rank30"]
        result = SurvivabilityResult(warframe=warframe, base_stats=dict(base), damage_type=damage_type,
                                     hits_per_second=hits_per_second, enemy_damage_multiplier=enemy_multiplier)
        notes = result.notes
        if frame["statsNote"]:
            notes.append(frame["statsNote"])

        # --- Mods: add up each stat. Umbral mods strengthen each other.
        umbral = sum(1 for m in mods if m.name.startswith("Umbral "))
        umbral_mult = UMBRAL_SET_MULTIPLIER.get(min(umbral, 3), 1.0)
        totals: Dict[str, float] = {}
        flat_dr: List[tuple] = []
        catalyzing = None
        for m in mods:
            if m.name == "Catalyzing Shields":
                catalyzing = m
            for s in m.stats:
                value = s.value
                if m.name.startswith("Umbral ") and not s.stat.startswith("RESIST"):
                    value = f32(value * umbral_mult)
                if s.stat == "DAMAGE_REDUCTION":
                    if value > 0:
                        flat_dr.append((m.name, value))
                else:
                    totals[s.stat] = totals.get(s.stat, 0.0) + value
        if umbral >= 2:
            notes.append(f"Umbral set: {umbral} Umbral mods equipped, each worth x{umbral_mult:g}.")

        strength = max(0.0, f32(1.0 + totals.get("ABILITY_STRENGTH", 0.0) + strength_bonus))
        result.ability_strength = strength

        # --- Arcanes
        flat_armor = totals.get("ARMOR_FLAT", 0.0) + extra_armor
        flat_health = 0.0
        for name, rank in arcanes or []:
            arcane = self.arcanes[name]
            rank = arcane["maxRank"] if rank is None else max(0, min(rank, arcane["maxRank"]))
            if arcane["stat"] == "ARMOR_FLAT":
                flat_armor += arcane["perRank"][rank]
            else:
                flat_health += arcane["perRank"][rank]
            notes.append(f"{name}: {arcane['note']} Counted as active.")

        # --- Abilities: armor bonuses first, then reductions and pools
        armor_pct = totals.get("ARMOR", 0.0)
        active = [(a, abilities.get(a["name"], AbilityState(active=False))) for a in frame["abilities"]]
        active = [(a, s) for a, s in active if s.active]
        for a, state in active:
            if a["kind"] != "armor":
                continue
            value = self.ability_value(a, state, strength)
            if a["mode"] == "percent":
                armor_pct += value
            else:
                flat_armor += value

        health = f32(f32(base["health"] * f32(1.0 + totals.get("HEALTH", 0.0))) + flat_health)
        shields = f32(base["shields"] * f32(1.0 + totals.get("SHIELDS", 0.0)))
        if catalyzing is not None:
            # x0.80 / 0.60 / 0.40 / 0.20 max shields by rank
            shields = f32(shields * f32(1.0 - 0.2 * (catalyzing.rank + 1)))
            notes.append("Catalyzing Shields: max shields cut, full shield gate fixed at "
                         f"{[0.33, 0.67, 1.0, 1.33][min(catalyzing.rank, 3)]:.2f}s.")
        armor = max(0.0, f32(f32(base["armor"] * f32(1.0 + armor_pct)) + flat_armor))
        result.modded_stats = {"health": health, "shields": shields, "armor": armor,
                               "energy": base.get("energy", 0)}

        # --- Damage reduction layers
        incoming = f32(incoming * enemy_multiplier)
        result.incoming_per_hit = incoming
        result.armor_dr = armor_damage_reduction(armor)

        shared: List[tuple] = []   # (name, reduction, note): apply to shields and health alike
        for a, state in active:
            if a["kind"] != "dr":
                continue
            if not self.applies(a, damage_type):
                notes.append(f"{a['name']} does not reduce {damage_type} damage.")
                continue
            value = self.ability_value(a, state, strength)
            if value > 0:
                shared.append((a["name"], min(value, 1.0), a["note"]))
            if a["applies"] == "ranged":
                notes.append(f"{a['name']}: {a['note']}")
        for name, value in flat_dr:
            if name == "Adaptation":
                # 5% per hit at rank 0 up to 10% at rank 10, to a 90% cap
                rank = (mod_ranks or {}).get(name, 10)
                stacks = (mod_stacks or {}).get(name, 0)
                value = min(0.9, f32((0.05 + 0.005 * rank) * stacks))
                if value <= 0:
                    continue
                shared.append((f"Adaptation ({damage_type})", value,
                               f"{stacks} hit(s) of {damage_type} taken. Other damage types build their own stacks."))
            else:
                shared.append((name, min(value, 1.0), ""))
        resist_keys = ["RESIST_" + damage_type.upper()] + (["RESIST_PHYSICAL"] if damage_type in PHYSICAL else [])
        for key in resist_keys:
            if totals.get(key, 0) > 0:
                shared.append((f"{damage_type} resistance mods", min(totals[key], 1.0), ""))

        layers: List[Layer] = []
        remaining = incoming
        health_reductions = [result.armor_dr] + [r for _, r, _ in shared]
        for name, reduction, note in [(f"Armor ({armor:,.0f})", result.armor_dr,
                                       "Applies to health only, not shields.")] + shared:
            remaining = f32(remaining * f32(1.0 - reduction))
            done = [l.reduction for l in layers] + [reduction]
            layers.append(Layer(name=name, reduction=reduction, damage_after=remaining,
                                cumulative=stack_reductions(done), note=note))
        result.layers = layers
        result.total_dr = stack_reductions(health_reductions)
        result.damage_per_hit = remaining

        shield_reductions = [SHIELD_DAMAGE_REDUCTION] + [r for _, r, _ in shared]
        result.shield_dr = stack_reductions(shield_reductions)
        result.shield_damage_per_hit = f32(incoming * f32(1.0 - result.shield_dr))
        ability_only = stack_reductions([r for _, r, _ in shared])

        # --- Effective health: raw damage each pool can absorb
        result.health_ehp = health / (1.0 - result.total_dr) if result.total_dr < 1 else float("inf")
        bypass_shields = damage_type == "Toxin"
        if bypass_shields:
            result.shield_ehp = 0.0
            if shields > 0:
                notes.append("Toxin bypasses shields, so they add nothing against this damage.")
        else:
            result.shield_ehp = shields / (1.0 - result.shield_dr) if result.shield_dr < 1 else float("inf")
        for a, state in active:
            if a["kind"] != "pool":
                continue
            points = f32(f32(a["value"] + f32(a.get("armorMultiplier", 0.0) * armor)) * (strength if a["scalesWithStrength"] else 1.0))
            # pools ignore armor; other reductions still apply to what reaches them
            ehp = points / (1.0 - ability_only) if ability_only < 1 else float("inf")
            result.pools.append({"name": a["name"], "points": points, "ehp": ehp})
            result.pool_ehp += ehp
            notes.append(f"{a['name']}: {a['note']}")
        result.total_ehp = result.health_ehp + result.shield_ehp + result.pool_ehp

        dps = incoming * hits_per_second
        result.time_to_kill = result.total_ehp / dps if dps > 0 else float("inf")
        result.shield_gate_seconds = shield_gate_seconds(shields)
        if shields > 0 and not bypass_shields:
            notes.append(f"Shield gate: about {result.shield_gate_seconds:.2f}s of invulnerability each time full shields "
                         "break. Not included in the time to kill.")
        notes.extend(frame["special"])
        if any(a["kind"] == "armor" for a, _ in active):
            notes.append("Ability armor bonuses are added to armor mods before multiplying base armor.")
        return result
