"""Enemy stat scaling engine.

Implements the full enemy level scaling system including:
- Per-faction health/shield/armor scaling with smoothstep interpolation
- Overguard scaling
- Eximus base stat increases
- Steel Path modifiers
- Armor DR calculation
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.constants import (
    ARMOR_DR_COEFFICIENT, ARMOR_DR_REFERENCE, ARMOR_HARD_CAP, ARMOR_INITIAL_MIN,
    FACTION_MODIFIERS, MAX_ENEMY_LEVEL, STEEL_PATH_LEVEL_BONUS,
    STEEL_PATH_SHIELD_MULTIPLIER, f32,
)


# ============================================================================
# SCALING CURVE DEFINITIONS
# ============================================================================

@dataclass(frozen=True)
class ScalingCurve:
    """A single scaling curve: f(x) = 1 + C * (x - base)^E"""
    coefficient: float
    exponent: float


@dataclass(frozen=True)
class DualCurve:
    """Two curves with smoothstep interpolation between them."""
    f1: ScalingCurve
    f2: ScalingCurve
    lower_bound: float  # L - start of transition
    upper_bound: float  # U - end of transition


# --- Health Scaling Curves ---

HEALTH_CURVES: Dict[str, DualCurve] = {
    "Grineer": DualCurve(
        ScalingCurve(0.015, 2.12), ScalingCurve(10.7332, 0.72), 70, 80),
    "Scaldra": DualCurve(
        ScalingCurve(0.015, 2.12), ScalingCurve(10.7332, 0.72), 70, 80),
    "Corpus": DualCurve(
        ScalingCurve(0.015, 2.12), ScalingCurve(13.4165, 0.55), 70, 80),
    "Infested": DualCurve(
        ScalingCurve(0.0225, 2.12), ScalingCurve(16.0998, 0.72), 70, 80),
    "Orokin": DualCurve(
        ScalingCurve(0.015, 2.1), ScalingCurve(10.7332, 0.685), 70, 80),
    "Techrot": DualCurve(
        ScalingCurve(0.02, 2.12), ScalingCurve(15.0998, 0.7), 70, 80),
    # These factions share the same curve
    "The Murmur": DualCurve(
        ScalingCurve(0.015, 2.0), ScalingCurve(10.7332, 0.5), 70, 80),
    "Sentient": DualCurve(
        ScalingCurve(0.015, 2.0), ScalingCurve(10.7332, 0.5), 70, 80),
    "Anarchs": DualCurve(
        ScalingCurve(0.015, 2.0), ScalingCurve(10.7332, 0.5), 70, 80),
    "Unaffiliated": DualCurve(
        ScalingCurve(0.015, 2.0), ScalingCurve(10.7332, 0.5), 70, 80),
}

# Default for factions without specific curves
DEFAULT_HEALTH_CURVE = HEALTH_CURVES["Unaffiliated"]

# --- Shield Scaling Curves ---

SHIELD_CURVES: Dict[str, DualCurve] = {
    "Corpus": DualCurve(
        ScalingCurve(0.02, 1.76), ScalingCurve(2.0, 0.76), 70, 80),
    "Orokin": DualCurve(
        ScalingCurve(0.02, 1.75), ScalingCurve(2.0, 0.75), 70, 80),
    "Grineer": DualCurve(
        ScalingCurve(0.02, 1.75), ScalingCurve(1.6, 0.75), 70, 80),
    "Sentient": DualCurve(
        ScalingCurve(0.02, 1.75), ScalingCurve(1.6, 0.75), 70, 80),
    "Techrot": DualCurve(
        ScalingCurve(0.02, 1.76), ScalingCurve(3.5, 0.76), 70, 80),
}

# Default shield curve (use Corpus as baseline for unknown factions)
DEFAULT_SHIELD_CURVE = SHIELD_CURVES["Corpus"]

# --- Armor Scaling Curve (universal) ---

ARMOR_CURVE = DualCurve(
    ScalingCurve(0.005, 1.75), ScalingCurve(0.4, 0.75), 70, 80)

# --- Overguard Scaling Curve (universal, uses level-1 not level-base) ---

OVERGUARD_CURVE = DualCurve(
    ScalingCurve(0.0015, 4.0), ScalingCurve(260.0, 0.9), 45, 50)


# ============================================================================
# SCALING MATH
# ============================================================================

def _eval_curve(curve: ScalingCurve, q: float) -> float:
    """Evaluate a single scaling curve: 1 + C * q^E (in float32)."""
    if q <= 0:
        return 1.0
    return f32(1.0 + f32(curve.coefficient * f32(q ** curve.exponent)))


def _smoothstep(t: float) -> float:
    """Smoothstep interpolation: 3t^2 - 2t^3 (in float32)."""
    t = f32(t)
    return f32(f32(f32(t * t) * f32(3.0 - f32(2.0 * t))))


def eval_dual_curve(dc: DualCurve, q: float) -> float:
    """Evaluate a dual curve with smoothstep interpolation (float32).

    Uses the exact formula from the wiki to avoid float32 rearrangement errors:
      Multiplier = f1(x) + (f2(x) - f1(x)) * smoothstep(t)
    NOT:
      f1(x) * (1-s) + f2(x) * s  (gives different float32 results)
    """
    v1 = _eval_curve(dc.f1, q)
    v2 = _eval_curve(dc.f2, q)

    if q < dc.lower_bound:
        return v1
    elif q > dc.upper_bound:
        return v2
    else:
        t = f32(f32(q - dc.lower_bound) / f32(dc.upper_bound - dc.lower_bound))
        t = max(0.0, min(1.0, t))
        s = _smoothstep(t)
        return f32(v1 + f32(f32(v2 - v1) * s))


# ============================================================================
# EXIMUS BASE STAT CALCULATION
# ============================================================================

def eximus_base_health(base_hp: float, level: float, has_defenses: bool = True) -> float:
    """Calculate Eximus base health (piecewise function).

    Args:
        base_hp: The enemy's normal base health
        level: Current enemy level
        has_defenses: True if enemy has shields or armor (uses 0.25 multiplier),
                      False if no defenses (uses 0.375 multiplier)
    """
    mult = 0.25 if has_defenses else 0.375

    if level <= 15:
        scaled = mult * (base_hp + 900)
    elif level <= 25:
        scaled = mult * (base_hp + 900) * (1 + 0.025 * (level - 15))
    elif level <= 35:
        scaled = mult * (base_hp + 900) * (1.25 + 0.125 * (level - 25))
    elif level <= 50:
        scaled = mult * (base_hp + 900) * (2.5 + (2 / 15) * (level - 35))
    elif level <= 100:
        scaled = mult * (base_hp + 900) * (4.5 + 0.03 * (level - 50))
    else:
        scaled = mult * (base_hp + 900) * 6

    return max(base_hp * 1.1, scaled)


# ============================================================================
# SCALED ENEMY
# ============================================================================

@dataclass
class ScaledEnemy:
    """An enemy at a specific level with all stats computed."""
    name: str
    faction: str
    base_level: int
    current_level: int

    # Scaled stats
    health: float = 0.0
    shield: float = 0.0
    armor: float = 0.0
    overguard: float = 0.0

    # Armor DR
    armor_dr: float = 0.0      # Damage reduction from armor (0-0.9)
    armor_dm: float = 1.0      # Damage multiplier (1 - DR)

    # Flags
    is_eximus: bool = False
    is_steel_path: bool = False

    # Faction modifiers for incoming damage
    faction_modifiers: Dict[str, float] = field(default_factory=dict)

    # Weak points
    weak_points: List[Dict] = field(default_factory=list)

    @property
    def ehp_vs_neutral(self) -> float:
        """Effective HP against neutral damage (no type modifiers)."""
        if self.armor > 0:
            hp_with_armor = self.health / self.armor_dm
        else:
            hp_with_armor = self.health
        return hp_with_armor + self.shield + self.overguard

    @property
    def effective_armor(self) -> float:
        """Armor value clamped to hard cap."""
        return min(self.armor, ARMOR_HARD_CAP)


class EnemyScaler:
    """Scales enemy stats to arbitrary levels."""

    def __init__(self, enemies_path: str = "data/processed/enemies.json"):
        self.enemies: Dict[str, dict] = {}
        self._load(enemies_path)

    def _load(self, path: str):
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        with open(p) as f:
            self.enemies = json.load(f)

    def list_enemies(self, faction: Optional[str] = None,
                     name_filter: Optional[str] = None) -> List[str]:
        """List available enemies, optionally filtered."""
        results = []
        for key, data in self.enemies.items():
            if faction and data.get("faction", "").lower() != faction.lower():
                continue
            if name_filter and name_filter.lower() not in data.get("name", "").lower():
                continue
            results.append(key)
        return sorted(results)

    def find_enemy(self, name: str) -> Optional[str]:
        """Find an enemy by partial name match. Returns the key or None."""
        name_lower = name.lower()

        # Exact match first
        for key, data in self.enemies.items():
            if data.get("name", "").lower() == name_lower:
                return key

        # Partial match
        matches = []
        for key, data in self.enemies.items():
            if name_lower in data.get("name", "").lower():
                matches.append(key)

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Prefer non-STANDARD variants or shortest name
            return min(matches, key=lambda k: len(self.enemies[k].get("name", "")))
        return None

    def scale_enemy(self, enemy_key: str, level: int,
                    is_eximus: bool = False,
                    is_steel_path: bool = False,
                    armor_strip_pct: float = 0.0,
                    viral_stacks: int = 0) -> ScaledEnemy:
        """Scale an enemy to a given level.

        Args:
            enemy_key: Key from enemies.json
            level: Target level
            is_eximus: Apply Eximus stat bonuses
            is_steel_path: Apply Steel Path modifiers (+100 level, 2.5x shields)
            armor_strip_pct: Percentage of armor stripped (0-1.0)
            viral_stacks: Number of Viral status stacks on target (0-10)

        Returns:
            ScaledEnemy with all stats computed
        """
        data = self.enemies.get(enemy_key)
        if data is None:
            raise ValueError(f"Unknown enemy: {enemy_key}")

        faction = data.get("faction", "Unaffiliated")
        base_level = data.get("baseLevel", 1)
        base_hp = float(data.get("health", 0))
        base_shield = float(data.get("shield", 0))
        base_armor = float(data.get("armor", 0))
        base_og = float(data.get("overguard", 0))

        # Steel Path: +100 to level
        effective_level = level
        if is_steel_path:
            effective_level += STEEL_PATH_LEVEL_BONUS

        effective_level = min(effective_level, MAX_ENEMY_LEVEL)
        q = max(0, effective_level - base_level)

        # --- Health ---
        health_curve = HEALTH_CURVES.get(faction, DEFAULT_HEALTH_CURVE)
        hp_mult = eval_dual_curve(health_curve, q)

        effective_base_hp = base_hp
        if is_eximus:
            has_defenses = (base_shield > 0 or base_armor > 0)
            effective_base_hp = eximus_base_health(base_hp, effective_level, has_defenses)

        health = f32(f32(effective_base_hp) * f32(hp_mult))

        # --- Shields ---
        if base_shield > 0:
            shield_curve = SHIELD_CURVES.get(faction, DEFAULT_SHIELD_CURVE)
            shield_mult = eval_dual_curve(shield_curve, q)

            effective_base_shield = base_shield
            # Eximus shield base increase uses similar piecewise but simpler
            # (same breakpoints, no +900, just multiplier on base shield)
            if is_eximus:
                effective_base_shield = eximus_base_health(
                    base_shield, effective_level, True)

            shield = f32(f32(effective_base_shield) * f32(shield_mult))

            # Steel Path: 2.5x shields
            if is_steel_path:
                shield = f32(shield * STEEL_PATH_SHIELD_MULTIPLIER)
        else:
            shield = 0.0

        # --- Armor ---
        if base_armor > 0:
            armor_mult = eval_dual_curve(ARMOR_CURVE, q)
            armor = f32(f32(base_armor) * f32(armor_mult))

            # Enforce minimum of 200 before strip
            armor = max(armor, ARMOR_INITIAL_MIN)

            # Apply armor strip
            if armor_strip_pct > 0:
                armor = f32(armor * f32(1.0 - min(armor_strip_pct, 1.0)))

            # Hard cap at 2700
            armor = min(armor, ARMOR_HARD_CAP)
        else:
            armor = 0.0

        # --- Overguard ---
        if is_eximus and base_og > 0:
            # Overguard uses level-1, not level-baseLevel
            q_og = max(0, effective_level - 1)
            og_mult = eval_dual_curve(OVERGUARD_CURVE, q_og)
            overguard = f32(f32(base_og) * f32(og_mult))
        elif is_eximus:
            # All Eximus have base overguard of 12
            q_og = max(0, effective_level - 1)
            og_mult = eval_dual_curve(OVERGUARD_CURVE, q_og)
            overguard = f32(f32(12.0) * f32(og_mult))
        else:
            overguard = 0.0

        # --- Armor DR ---
        if armor > 0:
            ar_capped = min(armor, ARMOR_HARD_CAP)
            armor_dm = 1.0 - ARMOR_DR_COEFFICIENT * math.sqrt(ar_capped / ARMOR_DR_REFERENCE)
            armor_dm = max(armor_dm, 0.1)  # 90% DR cap
            armor_dr = 1.0 - armor_dm
        else:
            armor_dm = 1.0
            armor_dr = 0.0

        # --- Faction modifiers ---
        faction_mods = dict(FACTION_MODIFIERS.get(faction, {}))

        return ScaledEnemy(
            name=data.get("name", enemy_key),
            faction=faction,
            base_level=base_level,
            current_level=effective_level,
            health=health,
            shield=shield,
            armor=armor,
            overguard=overguard,
            armor_dr=armor_dr,
            armor_dm=armor_dm,
            is_eximus=is_eximus,
            is_steel_path=is_steel_path,
            faction_modifiers=faction_mods,
            weak_points=data.get("weakPoints", []),
        )

    def armor_dr_at(self, armor: float) -> float:
        """Calculate armor damage reduction at a given armor value."""
        ar = min(armor, ARMOR_HARD_CAP)
        if ar <= 0:
            return 0.0
        dm = 1.0 - ARMOR_DR_COEFFICIENT * math.sqrt(ar / ARMOR_DR_REFERENCE)
        return 1.0 - max(dm, 0.1)
