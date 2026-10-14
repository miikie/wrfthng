"""Pydantic request/response models.

Python side is snake_case; JSON on the wire is camelCase (alias generator).
Response models read straight from the engine dataclasses (from_attributes).
"""

import math
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ============================================================================
# WEAPONS
# ============================================================================

class WeaponSummary(CamelModel):
    name: str
    category: str
    mod_type: str
    image_name: str = ""
    polarities: List[str] = Field(default_factory=list)
    total_damage: float
    crit_chance: float
    crit_mult: float
    status_chance: float
    fire_rate: float


class WeaponDetail(WeaponSummary):
    unique_name: str
    damage: Dict[str, float]
    mag_size: int
    reload_time: float
    multishot: int
    trigger: str
    tags: List[str]
    mastery_req: int
    behaviours: List[dict]


# ============================================================================
# ENEMIES
# ============================================================================

class EnemySummary(CamelModel):
    key: str
    name: str
    faction: str
    variant_type: str
    base_level: int
    health: float
    armor: float
    shield: float


class ScaledEnemyDetail(CamelModel):
    name: str
    faction: str
    base_level: int
    current_level: int
    health: float
    shield: float
    armor: float
    overguard: float
    armor_dr: float
    armor_dm: float
    is_eximus: bool
    is_steel_path: bool
    faction_modifiers: Dict[str, float]
    ehp: float


class EnemyDetail(EnemySummary):
    overguard: float
    faction_modifiers: Dict[str, float]
    immune_procs: List[str]
    scaled: ScaledEnemyDetail


# ============================================================================
# MODS
# ============================================================================

class ModStatValue(CamelModel):
    stat: str
    # For conditional stats this is the value of one stack
    value: float
    condition: str = ""
    max_stacks: int = 1


class ModSummary(CamelModel):
    name: str
    type: str
    rank: int
    max_rank: int
    polarity: str
    rarity: str
    stats: List[ModStatValue]
    image_name: str = ""
    base_drain: int = 0
    # Fits the Exilus slot (utility mods)
    exilus: bool = False


class ModDetail(ModSummary):
    base_drain: int
    conditional: str
    note: str
    set_bonus: str


# ============================================================================
# CALCULATION
# ============================================================================

class ModInput(CamelModel):
    name: str
    rank: Optional[int] = Field(default=None, ge=0)


class BuffInput(CamelModel):
    id: str
    rank: Optional[int] = Field(default=None, ge=0)
    amount: Optional[float] = Field(default=None, ge=0)
    # Share of the time the buff is up (None = the catalogue's default)
    uptime: Optional[float] = Field(default=None, ge=0, le=1)


class CompanionInput(CamelModel):
    name: str
    weapon: str = ""
    mods: List[ModInput] = Field(default_factory=list, max_length=8)


class ArcaneInput(CamelModel):
    name: str
    rank: Optional[int] = Field(default=None, ge=0)


class AmpInput(CamelModel):
    prism: str
    scaffold: str = ""
    brace: str = ""
    arcanes: List[ArcaneInput] = Field(default_factory=list, max_length=2)


class AbilityEffectInput(CamelModel):
    # None = the default: unconditional passives on, everything else off
    active: Optional[bool] = None
    stacks: Optional[float] = Field(default=None, ge=0)
    level: Optional[float] = Field(default=None, ge=0, le=1)


class CalculateRequest(CamelModel):
    weapon: str
    enemy: str
    enemy_level: int = Field(default=100, ge=1, le=9999)
    mods: List[ModInput] = Field(default_factory=list, max_length=9)
    steel_path: bool = False
    eximus: bool = False
    headshot: bool = False
    viral_stacks: int = Field(default=0, ge=0, le=10)
    status_types_on_target: int = Field(default=0, ge=0, le=10)
    armor_strip_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    combo_multiplier: float = Field(default=1.0, ge=1.0, le=13.0)
    # Active stacks per equipped conditional mod (0 or missing = inactive)
    conditional_stacks: Dict[str, int] = Field(default_factory=dict)
    buffs: List[BuffInput] = Field(default_factory=list, max_length=32)
    companion: Optional[CompanionInput] = None
    # Sentinels only fire with an attack precept (Assault Mode or their own) equipped
    sentinel_attack_precept: bool = True
    amp: Optional[AmpInput] = None
    # The Warframe holding the weapon. Its mods set the Ability Strength of its ability buffs.
    warframe: Optional[str] = None
    warframe_mods: List[ModInput] = Field(default_factory=list, max_length=10)
    extra_ability_strength: float = Field(default=0.0, ge=-1, le=10)
    # Helminth: the infused ability and the slot (1-4) it replaces
    helminth_ability: Optional[str] = None
    helminth_slot: Optional[int] = Field(default=None, ge=1, le=4)
    # Ability and passive effects by effect id (see GET /api/ability-buffs)
    ability_buffs: Dict[str, AbilityEffectInput] = Field(default_factory=dict)


class DamageBreakdownResponse(CamelModel):
    per_type: Dict[str, float]
    total: float
    per_type_inflicted: Dict[str, float]
    total_inflicted: float


class CritResponse(CamelModel):
    modded_crit_chance: float
    modded_crit_mult: float
    guaranteed_tier: int
    next_tier_chance: float
    normal_shot_mult: float
    crit_shot_mult: float
    average_mult: float


class DPSResponse(CamelModel):
    average_shot: float
    effective_fire_rate: float
    burst_dps: float
    sustained_dps: float
    # None when the weapon never reloads (melee / no magazine)
    shots_per_mag: Optional[float]
    shoot_ratio: float

    @field_validator("shots_per_mag", mode="before")
    @classmethod
    def _inf_to_none(cls, v):
        return None if v is not None and math.isinf(v) else v


class DoTResponse(CamelModel):
    dot_type: str
    damage_per_tick: float
    ticks: int
    duration: float
    total_damage: float
    ignores_armor: bool


class ElementSource(CamelModel):
    element: str
    # Mod name, or "Innate" for the weapon's own damage
    source: str


class ElementGroup(CamelModel):
    """One final elemental type and the ordered inputs that formed it."""
    type: str
    sources: List[ElementSource]


class ActiveBuff(CamelModel):
    id: str
    name: str
    group: str
    effect: str
    verified: bool
    uptime: Optional[float]
    targets: List[str]


class InactiveBuff(CamelModel):
    id: str
    name: str
    reason: str


class AveragedDps(CamelModel):
    """Weapon damage averaged over the time each buff is actually up."""
    average_shot: float
    burst_dps: float
    sustained_dps: float


class SideResult(CamelModel):
    """Damage of something other than the main weapon: the companion or one amp fire mode."""
    label: str
    weapon_name: str
    average_shot: float
    burst_dps: float
    sustained_dps: float
    fire_rate: float
    crit_chance: float
    crit_mult: float
    status_chance: float
    per_type_inflicted: Dict[str, float]
    notes: List[str]


class AmpResult(CamelModel):
    primary: SideResult
    alt: Optional[SideResult]


class AbilityEffectOut(CamelModel):
    id: str
    label: str
    ability: str
    source: str                 # the Warframe it comes from, or "Helminth"
    variant: str                # "own", "passive" or "infused"
    kind: str
    active: bool
    value: float                # after Ability Strength, caps and stacks
    effect: str                 # the value in words
    applies: bool               # False: the weapon can't use it (reason says why)
    reason: str = ""
    condition: str = ""
    note: str = ""
    augment: str = ""
    scales_with_strength: bool
    level: Optional[Dict[str, object]] = None
    stacks: Optional[Dict[str, object]] = None


class HelminthInfo(CamelModel):
    ability: str
    slot: int
    replaced: str


class CalculateResponse(CamelModel):
    weapon_name: str
    enemy_name: str
    enemy_level: int

    modded_base_damage: float
    modded_multishot: float
    modded_fire_rate: float
    modded_crit_chance: float
    modded_crit_mult: float
    modded_status_chance: float
    modded_mag_size: int
    modded_reload_time: float

    damage: DamageBreakdownResponse
    crit: CritResponse
    dps: DPSResponse
    dots: List[DoTResponse]

    enemy_ehp: float
    shots_to_kill: float
    time_to_kill: float
    arsenal_total_damage: float
    viral_damage_bonus: float
    condition_overload_mult: float

    elements: List[ElementGroup]
    enemy: ScaledEnemyDetail

    active_buffs: List[ActiveBuff] = Field(default_factory=list)
    # Selected buffs that were left out because the loadout doesn't meet their requirement
    inactive_buffs: List[InactiveBuff] = Field(default_factory=list)
    # None when every active buff is up all the time
    averaged: Optional[AveragedDps] = None
    # Enemy armor before buff armor strip (the enemy block shows it after)
    armor_before_buffs: float = 0.0
    companion: Optional[SideResult] = None
    amp: Optional[AmpResult] = None
    # weapon + companion; the amp is excluded because it can't fire at the same time
    combined_sustained_dps: float = 0.0
    # The Warframe's Ability Strength (mods + extra + Empower) and every ability / passive effect
    # its loadout has, active or not. Empty without a warframe.
    ability_strength: Optional[float] = None
    ability_effects: List[AbilityEffectOut] = Field(default_factory=list)
    helminth: Optional[HelminthInfo] = None


class CompareRequest(CamelModel):
    builds: List[CalculateRequest] = Field(min_length=1, max_length=4)


class CompareResponse(CamelModel):
    results: List[CalculateResponse]


# ============================================================================
# COMPANIONS, AMPS, BUFFS (catalogues)
# ============================================================================

class PreceptInfo(CamelModel):
    name: str
    effect: str
    damage_effect: str = ""


class CompanionInfo(CamelModel):
    name: str
    type: str
    variant: str
    description: str
    health: float
    shield: float
    armor: float
    precepts: List[PreceptInfo]
    weapons: List[str]
    default_weapon: str
    needs_attack_precept: bool
    stats_note: str = ""
    image_name: str = ""


class AmpAttack(CamelModel):
    name: str
    damage: Dict[str, float]
    crit_chance: float
    crit_mult: float
    status_chance: float
    fire_rate: float
    multishot: float
    ammo_cost: float
    burst_count: float = 1
    charge_time: float = 0
    falloff: Optional[Dict[str, float]] = None
    area: bool = False


class AmpPart(CamelModel):
    name: str
    image_name: str = ""
    series: Optional[int]
    trigger: str
    energy: float
    recharge_delay: float
    recharge_rate: float
    attacks: List[AmpAttack]


class AmpBrace(CamelModel):
    name: str
    image_name: str = ""
    series: int
    crit_chance: float
    status_chance: float
    energy: float
    recharge_delay: float
    recharge_rate: float


class AmpArcane(CamelModel):
    name: str
    image_name: str = ""
    stat: str
    text: str
    per_rank: List[float]
    max_rank: int


class AmpCatalogue(CamelModel):
    prisms: List[AmpPart]
    scaffolds: List[AmpPart]
    braces: List[AmpBrace]
    arcanes: List[AmpArcane]


class BuffAmount(CamelModel):
    label: str
    min: float
    max: float
    default: float


class BuffRequires(CamelModel):
    text: str
    companions: List[str]
    companion_types: List[str]
    melee_weapon: bool
    any_companion: bool


class BuffInfo(CamelModel):
    id: str
    name: str
    group: str
    kind: str
    per_rank: List[float]
    max_rank: int
    text: str
    requires: BuffRequires
    uptime: float
    uptime_note: str
    verified: bool
    amount: Optional[BuffAmount]
    applies_to: List[str]
