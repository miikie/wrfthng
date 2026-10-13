"""Core damage calculation engine.

Implements the complete Warframe damage pipeline:
1. Quantization (1/32 scale)
2. Physical mod application
3. Elemental combination
4. Damage/multishot/crit/status modding
5. Armor DR
6. Faction damage modifiers
7. Critical hit tiers
8. Headshot/weak point bonuses
9. Burst and sustained DPS
10. DoT (Slash, Heat, Toxin, Electricity, Gas)
11. Condition Overload / Galvanized status scaling
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from engine.constants import (
    ALL_DAMAGE_TYPES, ARMOR_DR_COEFFICIENT, ARMOR_DR_REFERENCE, ARMOR_HARD_CAP,
    DOT_COEFFICIENTS, DOT_DURATION, DOT_TICKS, ELECTRICITY_DURATION,
    FACTION_MODIFIERS, HEAT_DURATION, PHYSICAL_TYPES, QUANTIZATION_STEPS,
    VIRAL_BASE_BONUS, VIRAL_MAX_BONUS, VIRAL_MAX_STACKS, VIRAL_STACK_BONUS,
    f32,
)
from engine.enemies import ScaledEnemy
from engine.modding import ModdedStats, ModResolver, ResolvedMod, build_modded_stats, combine_elements
from engine.weapons import WeaponData


# ============================================================================
# QUANTIZATION
# ============================================================================

def quantize_damage(damage_types: Dict[str, float], modded_base: float) -> Dict[str, float]:
    """Quantize damage values to nearest 1/32 of modded base damage.

    Scale = Modded_Base_Damage / 32
    For each type: x = value / modded_base
    Quantized(x) = sign(x) * floor(abs(x) * 32 + 0.5) / 32
    Result = Quantized(x) * modded_base
    """
    if modded_base <= 0:
        return dict(damage_types)

    result = {}
    for dtype, value in damage_types.items():
        if value == 0:
            result[dtype] = 0.0
            continue
        x = value / modded_base
        sign = 1.0 if x >= 0 else -1.0
        quantized_x = sign * math.floor(abs(x) * QUANTIZATION_STEPS + 0.5) / QUANTIZATION_STEPS
        result[dtype] = quantized_x * modded_base

    return result


# ============================================================================
# RESULT DATACLASSES
# ============================================================================

@dataclass
class DamageBreakdown:
    """Detailed damage breakdown per type."""
    per_type: Dict[str, float] = field(default_factory=dict)
    total: float = 0.0

    # After faction/armor modifiers
    per_type_inflicted: Dict[str, float] = field(default_factory=dict)
    total_inflicted: float = 0.0


@dataclass
class CritResult:
    """Critical hit calculation results."""
    modded_crit_chance: float = 0.0
    modded_crit_mult: float = 1.0

    # Guaranteed crit tier (floor of crit chance)
    guaranteed_tier: int = 0
    # Chance of next tier
    next_tier_chance: float = 0.0

    # Damage at guaranteed tier
    normal_shot_mult: float = 1.0
    # Damage at next tier
    crit_shot_mult: float = 1.0
    # Average multiplier
    average_mult: float = 1.0


@dataclass
class DPSResult:
    """DPS calculation results."""
    # Per-shot
    average_shot: float = 0.0

    # Fire rate
    effective_fire_rate: float = 0.0

    # Burst DPS (no reload)
    burst_dps: float = 0.0

    # Sustained DPS (with reload)
    sustained_dps: float = 0.0
    shots_per_mag: float = 0.0
    shoot_ratio: float = 1.0


@dataclass
class DoTResult:
    """Damage over time calculation."""
    dot_type: str = ""
    damage_per_tick: float = 0.0
    ticks: int = 0
    duration: float = 0.0
    total_damage: float = 0.0
    ignores_armor: bool = False


@dataclass
class Buffs:
    """Bonuses from outside the weapon's own mods: Focus ways, companion
    precepts, companion bond mods, set bonuses and amp arcanes."""
    base_damage_add: float = 0.0      # added to the Serration-style bonus (Void Strike)
    physical_add: float = 0.0         # added to each physical bonus (Phoenix Talons)
    crit_chance_flat: float = 0.0     # points added after mods (Cat's Eye)
    crit_chance_floor: float = 0.0    # minimum crit chance (Smeeta Charm)
    crit_damage_add: float = 0.0      # added to the crit damage bonus (Power Transfer)
    crit_mult_flat: float = 0.0       # flat final crit multiplier (Tenacious Bond)
    crit_per_combo: float = 0.0       # crit chance bonus per combo multiplier above 1x (Gladiator set)
    status_chance_flat: float = 0.0   # points added after mods (amp braces)
    fire_rate_add: float = 0.0        # added to the fire rate bonus (Reinforced Bond)
    final_multiplier: float = 0.0     # +150% = 1.5; applies once to hits, twice to DoTs (Mecha Empowered)


@dataclass
class CalculationResult:
    """Complete calculation result."""
    weapon_name: str = ""
    enemy_name: str = ""
    enemy_level: int = 0

    # Modded weapon stats
    modded_base_damage: float = 0.0
    modded_multishot: float = 1.0
    modded_fire_rate: float = 1.0
    modded_crit_chance: float = 0.0
    modded_crit_mult: float = 1.0
    modded_status_chance: float = 0.0
    modded_mag_size: int = 0
    modded_reload_time: float = 0.0

    # Damage breakdown
    damage: DamageBreakdown = field(default_factory=DamageBreakdown)

    # Crit
    crit: CritResult = field(default_factory=CritResult)

    # DPS
    dps: DPSResult = field(default_factory=DPSResult)

    # DoTs per status type
    dots: List[DoTResult] = field(default_factory=list)

    # EHP context
    enemy_ehp: float = 0.0
    shots_to_kill: float = 0.0   # Approximate
    time_to_kill: float = 0.0    # Approximate (sustained)

    # Arsenal display value
    arsenal_total_damage: float = 0.0

    # Status effect context
    viral_damage_bonus: float = 0.0
    condition_overload_mult: float = 1.0


# ============================================================================
# MAIN CALCULATOR
# ============================================================================

class DamageCalculator:
    """The core damage calculation engine."""

    def __init__(self, mod_resolver: Optional[ModResolver] = None):
        self.mod_resolver = mod_resolver or ModResolver()

    def calculate(
        self,
        weapon: WeaponData,
        enemy: ScaledEnemy,
        mods: Optional[List[ResolvedMod]] = None,
        modded_stats: Optional[ModdedStats] = None,
        headshot: bool = False,
        weak_point_bonus: float = 0.0,
        viral_stacks: int = 0,
        status_types_on_target: int = 0,
        combo_multiplier: float = 1.0,
        extra_damage_mult: float = 0.0,   # e.g. from abilities
        extra_elemental: Optional[Dict[str, float]] = None,  # e.g. Xata's Whisper
        buffs: Optional[Buffs] = None,
        ammo_cost: float = 1.0,           # magazine units spent per shot (amps spend energy)
    ) -> CalculationResult:
        """Calculate damage of a weapon against an enemy.

        Args:
            weapon: Weapon data
            enemy: Scaled enemy at target level
            mods: List of resolved mods (or provide modded_stats directly)
            modded_stats: Pre-computed modded stats (skips mod resolution)
            headshot: Whether this is a headshot
            weak_point_bonus: Extra weak point damage bonus (from mods like Primary Acuity)
            viral_stacks: Number of Viral procs on target (0-10)
            status_types_on_target: Unique status types on target (for Condition Overload)
            combo_multiplier: Melee combo multiplier (1.0 for guns)
            extra_damage_mult: Extra damage multiplier from abilities
            extra_elemental: Extra elemental damage from abilities (e.g. {"Void": 0.25})
        """
        result = CalculationResult(
            weapon_name=weapon.name,
            enemy_name=enemy.name,
            enemy_level=enemy.current_level,
        )

        buffs = buffs or Buffs()

        # --- Step 1: Resolve mods ---
        if modded_stats is None:
            if mods:
                modded_stats = build_modded_stats(mods)
            else:
                modded_stats = ModdedStats()

        # --- Step 2: Calculate modded base damage ---
        base_damage = weapon.base_damage
        damage_mult = 1.0 + modded_stats.damage_bonus + extra_damage_mult + buffs.base_damage_add
        modded_base = base_damage * damage_mult
        result.modded_base_damage = modded_base

        # --- Step 3: Apply physical damage bonuses ---
        # Physical mods apply BEFORE quantization to their respective types
        damage_types: Dict[str, float] = {}

        for dtype, base_val in weapon.damage.items():
            if dtype == "Impact":
                damage_types[dtype] = base_val * (1 + modded_stats.impact_bonus + buffs.physical_add) * damage_mult
            elif dtype == "Puncture":
                damage_types[dtype] = base_val * (1 + modded_stats.puncture_bonus + buffs.physical_add) * damage_mult
            elif dtype == "Slash":
                damage_types[dtype] = base_val * (1 + modded_stats.slash_bonus + buffs.physical_add) * damage_mult
            else:
                # Non-physical base damage types scale with damage mult
                damage_types[dtype] = base_val * damage_mult

        # --- Step 4: Add elemental damage from mods ---
        # Elementals calculate from FULL modded base damage
        elemental_additions = list(modded_stats.elemental_mods)

        # Add ability-granted elementals
        if extra_elemental:
            for elem, pct in extra_elemental.items():
                elemental_additions.append((elem, pct))

        # Combine elements using slot order rules
        innate_elemental = weapon.elemental_damage
        combined = combine_elements(innate_elemental, elemental_additions, modded_base)

        # Merge combined elementals into damage_types
        for elem_type, elem_val in combined.items():
            if elem_type in damage_types:
                damage_types[elem_type] += elem_val
            else:
                damage_types[elem_type] = elem_val

        # --- Step 5: Quantize ---
        damage_types = quantize_damage(damage_types, modded_base)

        total_modded = sum(damage_types.values())
        result.damage.per_type = dict(damage_types)
        result.damage.total = total_modded

        # --- Step 6: Multishot ---
        modded_multishot = weapon.multishot * (1 + modded_stats.multishot_bonus)
        result.modded_multishot = modded_multishot

        # --- Step 7: Crit ---
        cc_bonus = modded_stats.crit_chance_bonus
        if weapon.is_melee and combo_multiplier > 1.0:
            cc_bonus += buffs.crit_per_combo * (combo_multiplier - 1.0)
        modded_cc = weapon.crit_chance * (1 + cc_bonus) + buffs.crit_chance_flat
        modded_cc = max(modded_cc, buffs.crit_chance_floor)
        modded_cd = weapon.crit_mult * (1 + modded_stats.crit_damage_bonus + buffs.crit_damage_add)
        # A flat final multiplier turns each tier's (cd - 1) into (cd - 1 + x)
        modded_cd += buffs.crit_mult_flat

        # Melee combo: Blood Rush style (additive to crit chance mult)
        if weapon.is_melee and combo_multiplier > 1.0:
            # Blood Rush: crit_chance_bonus is already in modded_stats
            # but the combo multiplier applies differently
            # Blood Rush value * (combo_mult - 1) is added to crit chance
            # For simplicity, we handle this as the mod's note suggests
            pass

        result.modded_crit_chance = modded_cc
        result.modded_crit_mult = modded_cd

        crit = self._calc_crit(modded_cc, modded_cd)
        result.crit = crit

        # --- Step 8: Faction damage modifier ---
        faction_mult = 1.0 + modded_stats.faction_bonus

        # --- Step 9: Inflicted damage per type (vs enemy) ---
        inflicted = {}
        for dtype, dmg in damage_types.items():
            # Get faction type modifier
            type_mod = enemy.faction_modifiers.get(dtype, 1.0)

            # Armor DR applies to health damage (not shields)
            # For simplicity in average calculation, apply armor DM to all non-shield damage
            if dtype == "Slash" and False:  # Slash DoT ignores armor, but direct Slash doesn't
                pass

            # Apply armor damage multiplier to types that hit health through armor
            armor_mult = enemy.armor_dm if enemy.armor > 0 else 1.0

            # Toxin bypasses shields (we note this but in per-shot it still goes through armor)

            inflicted_dmg = dmg * type_mod * armor_mult * faction_mult
            inflicted[dtype] = inflicted_dmg

        total_inflicted = sum(inflicted.values())
        result.damage.per_type_inflicted = inflicted
        result.damage.total_inflicted = total_inflicted

        # --- Step 10: Viral bonus ---
        viral_mult = 1.0
        if viral_stacks > 0:
            vs = min(viral_stacks, VIRAL_MAX_STACKS)
            viral_mult = 1.0 + VIRAL_BASE_BONUS + VIRAL_STACK_BONUS * (vs - 1)
            viral_mult = min(viral_mult, 1.0 + VIRAL_MAX_BONUS)
        result.viral_damage_bonus = viral_mult - 1.0

        # --- Step 11: Condition Overload ---
        co_mult = 1.0
        if status_types_on_target > 0:
            if modded_stats.condition_overload > 0:
                co_mult *= (1 + modded_stats.condition_overload) ** status_types_on_target
            if modded_stats.galvanized_stacks > 0:
                co_mult *= (1 + modded_stats.galvanized_stacks) ** status_types_on_target
        result.condition_overload_mult = co_mult

        # --- Step 12: Per-shot damage ---
        per_shot = total_inflicted * viral_mult * co_mult * (1.0 + buffs.final_multiplier)

        # --- Step 13: Headshot ---
        if headshot and not weapon.is_melee:
            # Default weak point multiplier is 2.0 for most weapons
            wp_mult = 2.0 + weak_point_bonus
            per_shot *= wp_mult

        # --- Step 14: Average shot (with crit) ---
        average_shot = per_shot * crit.average_mult * modded_multishot

        # Melee combo multiplier
        if weapon.is_melee:
            average_shot *= combo_multiplier

        result.dps.average_shot = average_shot

        # --- Step 15: Fire rate / DPS ---
        modded_fr = weapon.fire_rate * (1 + modded_stats.fire_rate_bonus + buffs.fire_rate_add)
        modded_fr = max(modded_fr, 0.05)  # Sanity floor
        result.modded_fire_rate = modded_fr

        effective_fr = self._effective_fire_rate(weapon, modded_fr)
        result.dps.effective_fire_rate = effective_fr

        # Burst DPS
        burst_dps = average_shot * effective_fr
        result.dps.burst_dps = burst_dps

        # --- Step 16: Sustained DPS ---
        modded_mag = max(1, round(weapon.mag_size * (1 + modded_stats.mag_size_bonus)))
        modded_reload = weapon.reload_time / (1 + modded_stats.reload_speed_bonus) if weapon.reload_time > 0 else 0.0
        result.modded_mag_size = modded_mag
        result.modded_reload_time = modded_reload

        # For melee, sustained = burst (no reload)
        if weapon.is_melee or weapon.mag_size <= 0:
            result.dps.sustained_dps = burst_dps
            result.dps.shots_per_mag = float('inf')
            result.dps.shoot_ratio = 1.0
        else:
            shots_per_mag = modded_mag / ammo_cost if ammo_cost > 0 else float(modded_mag)
            result.dps.shots_per_mag = shots_per_mag

            if modded_reload > 0 and effective_fr > 0:
                shoot_ratio = shots_per_mag / (effective_fr * modded_reload + shots_per_mag)
            else:
                shoot_ratio = 1.0

            result.dps.shoot_ratio = shoot_ratio
            result.dps.sustained_dps = burst_dps * shoot_ratio

        # --- Step 17: Modded status chance ---
        result.modded_status_chance = (
            weapon.status_chance * (1 + modded_stats.status_chance_bonus) + buffs.status_chance_flat
        )

        # --- Step 18: DoTs ---
        result.dots = self._calc_dots(
            weapon, modded_base, modded_multishot, faction_mult,
            modded_stats, enemy,
        )

        if buffs.final_multiplier:
            twice = (1.0 + buffs.final_multiplier) ** 2
            for dot in result.dots:
                dot.damage_per_tick *= twice
                dot.total_damage *= twice

        # --- Step 19: Arsenal total damage ---
        result.arsenal_total_damage = self._arsenal_total(weapon, modded_stats)

        # --- Step 20: Kill estimates ---
        result.enemy_ehp = enemy.ehp_vs_neutral
        if average_shot > 0:
            result.shots_to_kill = result.enemy_ehp / average_shot
            if result.dps.sustained_dps > 0:
                result.time_to_kill = result.enemy_ehp / result.dps.sustained_dps

        return result

    def _calc_crit(self, cc: float, cd: float) -> CritResult:
        """Calculate crit tier multipliers."""
        guaranteed_tier = int(math.floor(cc))
        next_tier_chance = cc - guaranteed_tier

        normal_mult = 1.0 + guaranteed_tier * (cd - 1.0)
        crit_mult = 1.0 + math.ceil(cc) * (cd - 1.0)
        avg_mult = 1.0 + cc * (cd - 1.0)

        return CritResult(
            modded_crit_chance=cc,
            modded_crit_mult=cd,
            guaranteed_tier=guaranteed_tier,
            next_tier_chance=next_tier_chance,
            normal_shot_mult=normal_mult,
            crit_shot_mult=crit_mult,
            average_mult=avg_mult,
        )

    def _effective_fire_rate(self, weapon: WeaponData, modded_fr: float) -> float:
        """Calculate effective fire rate based on trigger type."""
        trigger = weapon.trigger.upper()

        if trigger in ("AUTO", "AUTO-SPOOL", "SEMI", "DUPLEX", "HELD", ""):
            return modded_fr

        if trigger == "CHARGE":
            # FR_Charge = 1 / (charge_time + 1/fire_rate)
            charge_time = 1.0 / modded_fr if modded_fr > 0 else 1.0
            return 1.0 / (charge_time + 1.0 / modded_fr) if modded_fr > 0 else 0.5

        if trigger.startswith("BURST"):
            burst_count = 3  # Default; would need to be from weapon data
            burst_delay = 0.05  # Default
            if modded_fr > 0:
                return burst_count / (1.0 / modded_fr + (burst_count - 1) * burst_delay)
            return modded_fr

        return modded_fr

    def _calc_dots(
        self,
        weapon: WeaponData,
        modded_base: float,
        modded_multishot: float,
        faction_mult: float,
        ms: ModdedStats,
        enemy: ScaledEnemy,
    ) -> List[DoTResult]:
        """Calculate DoT damage for each relevant status type.

        DoT is NOT quantized. Uses float32 arithmetic.
        DoT modded damage IGNORES elemental and physical damage bonuses.
        Faction bonus applies TWICE to DoT.
        """
        dots = []

        # Base for DoT: modded base damage * multishot * faction
        dot_base = f32(modded_base * modded_multishot * faction_mult)

        # Status duration bonus
        duration_mult = 1.0 + ms.status_duration_bonus

        for dot_type, coefficient in DOT_COEFFICIENTS.items():
            # Only calculate if weapon can proc this type
            # (weapon has this element, or mods add it)

            # Determine if weapon can proc this type
            has_type = dot_type in weapon.damage
            if not has_type:
                # Check if mods add this element (as part of a combined element)
                for elem, _ in ms.elemental_mods:
                    if elem == dot_type:
                        has_type = True
                        break

            if not has_type:
                continue

            # Elemental bonus for elemental DoTs
            elem_bonus = 0.0
            if dot_type == "Heat":
                elem_bonus = sum(v for e, v in ms.elemental_mods if e == "Heat")
            elif dot_type == "Electricity":
                elem_bonus = sum(v for e, v in ms.elemental_mods if e == "Electricity")
            elif dot_type == "Toxin":
                elem_bonus = sum(v for e, v in ms.elemental_mods if e == "Toxin")
            elif dot_type == "Gas":
                elem_bonus = sum(v for e, v in ms.elemental_mods if e == "Toxin")  # Gas uses Toxin mods
            # Slash DoT: no elemental/physical bonus

            # Duration and ticks
            if dot_type == "Electricity":
                duration = ELECTRICITY_DURATION * duration_mult
            else:
                duration = DOT_DURATION * duration_mult

            ticks = DOT_TICKS  # Standard tick count

            # Tick damage
            # DoT tick = coefficient * dot_base * (1 + elem_bonus) * faction_mult
            # Note: faction applies twice (once already in dot_base)
            if dot_type == "Slash":
                tick_dmg = f32(coefficient * dot_base * faction_mult)
                # Slash ignores armor (True damage)
                tick_vs_enemy = tick_dmg
            else:
                tick_dmg = f32(coefficient * f32(1.0 + elem_bonus) * dot_base * faction_mult)
                # Other DoTs are affected by armor
                tick_vs_enemy = tick_dmg * enemy.armor_dm if enemy.armor > 0 else tick_dmg

            total = tick_vs_enemy * ticks

            dots.append(DoTResult(
                dot_type=dot_type,
                damage_per_tick=tick_vs_enemy,
                ticks=ticks,
                duration=duration,
                total_damage=total,
                ignores_armor=(dot_type == "Slash"),
            ))

        return dots

    def _arsenal_total(self, weapon: WeaponData, ms: ModdedStats) -> float:
        """Calculate the Arsenal display total damage.

        Arsenal_Total = Base_Damage
            * (1 + Elemental_Bonuses
               + Impact_Dist * Impact_Bonuses
               + Puncture_Dist * Puncture_Bonuses
               + Slash_Dist * Slash_Bonuses)
            * (1 + Damage_Bonuses)
            * (Base_Multishot * (1 + Multishot_Bonuses))
        """
        bd = weapon.base_damage
        if bd <= 0:
            return 0.0

        elem_sum = sum(v for _, v in ms.elemental_mods)

        phys_factor = (
            weapon.impact_distribution * ms.impact_bonus
            + weapon.puncture_distribution * ms.puncture_bonus
            + weapon.slash_distribution * ms.slash_bonus
        )

        total = (
            bd
            * (1 + elem_sum + phys_factor)
            * (1 + ms.damage_bonus)
        )

        if not weapon.is_melee:
            total *= weapon.multishot * (1 + ms.multishot_bonus)

        return total
