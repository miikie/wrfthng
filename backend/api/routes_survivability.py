"""Warframe survivability: how much damage a Warframe takes."""

import json
import math
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import Field

from api.deps import DATA, ability_buffs, enemy_scaler, image_map, mod_resolver, survivability
from api.schemas import CamelModel, ModInput
from engine.constants import STEEL_PATH_LEVEL_BONUS
from engine.modding import ResolvedMod
from engine.survivability import AbilityState, enemy_damage_multiplier

router = APIRouter(prefix="/api", tags=["survivability"])

# Each Warframe's four ability names in slot order, for the ability bar
with open(DATA / "warframes.json", encoding="utf-8") as _f:
    ability_names = {name: [a["name"] for a in frame.get("abilities", [])]
                     for name, frame in json.load(_f).items()}


class StatBlock(CamelModel):
    health: float
    shields: float
    armor: float
    energy: float = 0


class AbilityInfo(CamelModel):
    kind: str                      # "dr", "armor" or "pool"
    name: str
    value: float
    cap: Optional[float] = None
    scales_with_strength: bool
    stacks: Optional[Dict[str, object]] = None     # {label, max, default}
    per_stack: Optional[float] = None
    level: Optional[Dict[str, object]] = None      # {label, default}
    low: Optional[float] = None
    mode: Optional[str] = None                     # armor: "percent" or "flat"
    armor_multiplier: Optional[float] = None
    note: str = ""
    applies: str = "all"
    image_name: str = ""


class PassiveEffect(AbilityInfo):
    # kinds: dr, armor, health, resistance, regen, shield_gate, revive, note
    value: Optional[float] = None
    scales_with_strength: bool = False
    condition: str = ""            # non-empty: a toggle; empty: always on


class PassiveInfo(CamelModel):
    name: str = ""
    description: str = ""
    effects: List[PassiveEffect] = Field(default_factory=list)


class AbilityIcon(CamelModel):
    name: str
    image_name: str = ""


class WarframeInfo(CamelModel):
    name: str
    # all four abilities, in slot order, whether or not they change damage taken
    all_abilities: List[AbilityIcon] = Field(default_factory=list)
    rank0: StatBlock
    rank30: StatBlock
    stats_note: str
    abilities: List[AbilityInfo]
    passive: PassiveInfo = Field(default_factory=PassiveInfo)
    special: List[str]
    image_name: str = ""
    # innate mod slot polarities and the aura slot's polarity
    polarities: List[str] = Field(default_factory=list)
    aura_polarity: str = ""


class ArcaneInfo(CamelModel):
    name: str
    stat: str
    per_rank: List[float]
    max_rank: int
    note: str
    image_name: str = ""


class WarframeCatalogue(CamelModel):
    warframes: List[WarframeInfo]
    arcanes: List[ArcaneInfo]


class AbilityInput(CamelModel):
    active: bool = True
    stacks: Optional[float] = Field(default=None, ge=0)
    level: Optional[float] = Field(default=None, ge=0, le=1)


class IncomingDamage(CamelModel):
    # "custom": amount is the damage of one hit. "enemy": amount is the enemy's
    # base damage per hit, scaled by its level and faction.
    source: str = "custom"
    amount: float = Field(default=1000, ge=0)
    type: str = "Slash"
    hits_per_second: float = Field(default=1.0, gt=0, le=100)
    enemy: Optional[str] = None
    enemy_level: int = Field(default=100, ge=1, le=9999)
    steel_path: bool = False


class SurvivabilityRequest(CamelModel):
    warframe: str
    mods: List[ModInput] = Field(default_factory=list, max_length=10)
    conditional_stacks: Dict[str, int] = Field(default_factory=dict)
    abilities: Dict[str, AbilityInput] = Field(default_factory=dict)
    # passive effects by name: conditional ones count when active; any effect takes stacks / level
    passive: Dict[str, AbilityInput] = Field(default_factory=dict)
    arcanes: List[ModInput] = Field(default_factory=list, max_length=2)
    incoming: IncomingDamage = Field(default_factory=IncomingDamage)
    # Ability Strength from outside the mods (shards, squad buffs), as a fraction: 0.3 = +30%
    extra_ability_strength: float = Field(default=0.0, ge=-1, le=10)
    # Helminth: the infused ability and the slot (1-4) it replaces
    helminth_ability: Optional[str] = None
    helminth_slot: Optional[int] = Field(default=None, ge=1, le=4)


class HelminthOut(CamelModel):
    ability: str
    slot: int
    replaced: str


class LayerOut(CamelModel):
    name: str
    reduction: float
    damage_after: float
    cumulative: float
    note: str


class PoolOut(CamelModel):
    name: str
    points: float
    ehp: Optional[float]


class PassiveEffectOut(CamelModel):
    name: str
    kind: str
    active: bool
    value: Optional[float] = None


class SurvivabilityResponse(CamelModel):
    warframe: str
    base_stats: StatBlock
    modded_stats: StatBlock
    ability_strength: float
    # Display only: the other three ability stats from the equipped mods
    ability_duration: float = 1.0
    ability_efficiency: float = 1.0
    ability_range: float = 1.0
    armor_dr: float
    total_dr: float
    shield_dr: float
    layers: List[LayerOut]
    incoming_per_hit: float
    damage_type: str
    damage_per_hit: float
    shield_damage_per_hit: float
    hits_per_second: float
    health_ehp: Optional[float]
    shield_ehp: Optional[float]
    pool_ehp: Optional[float]
    total_ehp: Optional[float]
    pools: List[PoolOut]
    time_to_kill: Optional[float]
    shield_gate_seconds: float
    enemy_damage_multiplier: float
    enemy_name: str = ""
    health_regen: float = 0.0
    passive_effects: List[PassiveEffectOut] = Field(default_factory=list)
    helminth: Optional[HelminthOut] = None
    notes: List[str]


def finite(x: float) -> Optional[float]:
    return None if math.isinf(x) or math.isnan(x) else x


@router.get("/warframes", response_model=WarframeCatalogue)
def list_warframes():
    def ability_image(name: str) -> str:
        # effects are named after their ability, sometimes with a suffix: "Eclipse (Lunar)", "Iron Skin"
        for ability, image in image_map["abilities"].items():
            if name == ability or name.startswith(ability + " "):
                return image
        return ""

    frames = []
    for w in survivability.warframes.values():
        slots = image_map["slotPolarities"]["warframes"].get(w["name"], {})
        frames.append(WarframeInfo(**{
            **w,
            "allAbilities": [{"name": n, "imageName": image_map["abilities"].get(n, "")}
                             for n in ability_names.get(w["name"], [])],
            "abilities": [{**a, "imageName": ability_image(a["name"])} for a in w["abilities"]],
            "imageName": image_map["warframes"].get(w["name"], ""),
            "polarities": slots.get("slots", []), "auraPolarity": slots.get("aura", ""),
        }))
    return WarframeCatalogue(
        warframes=frames,
        arcanes=[ArcaneInfo(**{**a, "imageName": image_map["arcanes"].get(a["name"], "")})
                 for a in survivability.arcanes.values()],
    )


def resolve_warframe_mods(inputs: List[ModInput], conditional_stacks: Dict[str, int]):
    """Warframe and aura mods -> (resolved mods, rank by name, active stacks by name). 404 / 422 on bad input."""
    stacks = {name.lower(): n for name, n in conditional_stacks.items()}
    mods: List[ResolvedMod] = []
    ranks, mod_stacks, seen = {}, {}, set()
    for m in inputs:
        try:
            resolved = mod_resolver.resolve(m.name, m.rank, stacks=stacks.get(m.name.lower(), 0))
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        if resolved.mod_type not in ("WARFRAME", "AURA"):
            raise HTTPException(status_code=422, detail=f"{resolved.name} is not a Warframe mod")
        if resolved.name in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate mod: {resolved.name}")
        seen.add(resolved.name)
        mods.append(resolved)
        ranks[resolved.name] = resolved.rank
        mod_stacks[resolved.name] = stacks.get(m.name.lower(), 0)
    # Adaptation's stat is resolved at 0 stacks when off; keep it visible to the engine
    for m in mods:
        if m.name == "Adaptation" and mod_stacks[m.name] > 0 and not any(s.value > 0 for s in m.stats):
            m.stats[0].value = 0.01
    return mods, ranks, mod_stacks


def infusion(warframe: str, ability: Optional[str], slot: Optional[int]):
    """The infused ability as the survivability engine wants it, or None. 422 if the Helminth can't do it."""
    if not ability:
        return None, None
    if slot is None:
        raise HTTPException(status_code=422, detail="helminthSlot is needed with helminthAbility")
    reason = ability_buffs.check_infusion(warframe, ability, slot)
    if reason:
        raise HTTPException(status_code=422, detail=reason)
    info = ability_buffs.infusable(ability)
    return slot, {"name": ability, "effects": info["survivabilityEffects"]}


@router.post("/survivability", response_model=SurvivabilityResponse)
def calculate_survivability(req: SurvivabilityRequest):
    if req.warframe not in survivability.warframes:
        raise HTTPException(status_code=404, detail=f"Warframe not found: {req.warframe}")
    mods, ranks, mod_stacks = resolve_warframe_mods(req.mods, req.conditional_stacks)
    slot, infused = infusion(req.warframe, req.helminth_ability, req.helminth_slot)

    for name in req.arcanes:
        if name.name not in survivability.arcanes:
            raise HTTPException(status_code=404, detail=f"Arcane not found: {name.name}")

    multiplier, enemy_name = 1.0, ""
    inc = req.incoming
    if inc.source == "enemy":
        enemy = enemy_scaler.enemies.get(inc.enemy or "")
        if enemy is None:
            raise HTTPException(status_code=404, detail=f"Enemy not found: {inc.enemy}")
        level = inc.enemy_level + (STEEL_PATH_LEVEL_BONUS if inc.steel_path else 0)
        base_level = enemy.get("baseLevel", 1)
        multiplier = enemy_damage_multiplier(enemy.get("faction", ""), base_level, max(level, base_level))
        enemy_name = enemy.get("name", "")

    r = survivability.calculate(
        req.warframe, mods=mods,
        abilities={k: AbilityState(active=v.active, stacks=v.stacks, level=v.level) for k, v in req.abilities.items()},
        passive={k: AbilityState(active=v.active, stacks=v.stacks, level=v.level) for k, v in req.passive.items()},
        arcanes=[(a.name, a.rank) for a in req.arcanes],
        incoming=inc.amount, damage_type=inc.type, hits_per_second=inc.hits_per_second,
        strength_bonus=req.extra_ability_strength, mod_ranks=ranks, mod_stacks=mod_stacks,
        enemy_multiplier=multiplier, replaced_slot=slot, infused=infused,
    )
    if inc.source == "enemy":
        r.notes.insert(0, f"{enemy_name} at level {inc.enemy_level}{' on the Steel Path' if inc.steel_path else ''}: "
                          f"base damage x{multiplier:,.2f} (level scaling and its faction's attack multiplier).")
    # The other ability stats, for the stat panel. Efficiency runs from 25% to 175%;
    # Duration and Range have floors of 12.5% and 34%.
    def stat_total(key: str) -> float:
        return 1.0 + sum(s.value for m in mods for s in m.stats if s.stat == key)

    return SurvivabilityResponse(
        ability_duration=max(0.125, stat_total("ABILITY_DURATION")),
        ability_efficiency=min(1.75, max(0.25, stat_total("ABILITY_EFFICIENCY"))),
        ability_range=max(0.34, stat_total("ABILITY_RANGE")),
        warframe=r.warframe, base_stats=StatBlock(**r.base_stats), modded_stats=StatBlock(**r.modded_stats),
        ability_strength=r.ability_strength, armor_dr=r.armor_dr, total_dr=r.total_dr, shield_dr=r.shield_dr,
        layers=[LayerOut(**vars(l)) for l in r.layers],
        incoming_per_hit=r.incoming_per_hit, damage_type=r.damage_type, damage_per_hit=r.damage_per_hit,
        shield_damage_per_hit=r.shield_damage_per_hit, hits_per_second=r.hits_per_second,
        health_ehp=finite(r.health_ehp), shield_ehp=finite(r.shield_ehp), pool_ehp=finite(r.pool_ehp),
        total_ehp=finite(r.total_ehp),
        pools=[PoolOut(name=p["name"], points=p["points"], ehp=finite(p["ehp"])) for p in r.pools],
        time_to_kill=finite(r.time_to_kill), shield_gate_seconds=r.shield_gate_seconds,
        enemy_damage_multiplier=r.enemy_damage_multiplier, enemy_name=enemy_name, notes=r.notes,
        health_regen=r.health_regen, passive_effects=[PassiveEffectOut(**e) for e in r.passive_effects],
        helminth=HelminthOut(**r.helminth) if r.helminth else None,
    )


@router.get("/helminth")
def helminth_catalogue():
    """What the Helminth can infuse: every subsumable ability, the Helminth's own, and the
    damage-buff placement rule. Survivability effects carry the infused version's values."""
    def with_image(entries: Dict[str, dict]) -> List[dict]:
        return [{**v, "imageName": image_map["abilities"].get(name, "")} for name, v in entries.items()]

    return {
        "subsumable": with_image(ability_buffs.subsumable),
        "helminthAbilities": with_image(ability_buffs.helminth_abilities),
        "restrictions": ability_buffs.restrictions,
    }


@router.get("/ability-buffs")
def ability_buff_catalogue():
    """Every ability and passive effect the calculator models, with its wiki values (max rank)."""
    return list(ability_buffs.effects.values())
