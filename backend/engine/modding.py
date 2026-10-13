"""Mod resolution and elemental combination engine.

Handles:
- Loading mod databases (curated core_mods + export metadata)
- Resolving mod stats at a given rank
- Combining elemental damage types in correct slot order
- Calculating all modded weapon stats
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.constants import (
    BASE_ELEMENTAL_TYPES, COMBINED_ELEMENT_COMPONENTS,
    ELEMENTAL_COMBINATIONS, STAT_TO_ELEMENT, STAT_TO_PHYSICAL,
)


# ============================================================================
# MOD DATA
# ============================================================================

@dataclass
class ModStat:
    """A single stat provided by a mod at a given rank."""
    stat: str
    value: float
    condition: str = ""   # "" = always on; see core_mods.json _conditions
    max_stacks: int = 1


@dataclass
class ResolvedMod:
    """A mod resolved to specific stats at a given rank."""
    name: str
    rank: int
    max_rank: int
    mod_type: str
    stats: List[ModStat]
    polarity: str = ""
    conditional: str = ""
    note: str = ""
    set_bonus: str = ""


class ModResolver:
    """Resolves mods from the curated database to specific ranks."""

    def __init__(self, core_mods_path: str = "data/processed/core_mods.json"):
        self.mods: Dict[str, dict] = {}
        self._load(core_mods_path)

    def _load(self, path: str):
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        with open(p) as f:
            data = json.load(f)
        self.mods = data.get("mods", data)

    def list_mods(self, mod_type: Optional[str] = None,
                  stat_filter: Optional[str] = None) -> List[str]:
        """List available mods, optionally filtered by type or stat."""
        results = []
        for name, data in self.mods.items():
            if mod_type and data.get("type", "").upper() != mod_type.upper():
                continue
            if stat_filter:
                stats = self._get_stat_names(data)
                if stat_filter.upper() not in [s.upper() for s in stats]:
                    continue
            results.append(name)
        return sorted(results)

    def _get_stat_names(self, data: dict) -> List[str]:
        """Get all stat names from a mod definition."""
        if "stats" in data:
            return [s["stat"] for s in data["stats"]]
        elif "stat" in data:
            return [data["stat"]]
        return []

    def resolve(self, name: str, rank: Optional[int] = None,
                stacks: Optional[int] = None, combo_multiplier: float = 1.0) -> ResolvedMod:
        """Resolve a mod to its stats at a given rank.

        Args:
            name: Mod name (case-insensitive match)
            rank: Desired rank (None = max rank)
            stacks: Active stacks of the mod's conditional stats (0 = inactive).
                None gives the value of one stack, for display.
            combo_multiplier: Melee combo multiplier, for "per_combo" stats

        Returns:
            ResolvedMod with computed stat values

        Raises:
            ValueError: If mod not found
        """
        # Case-insensitive lookup
        mod_data = None
        mod_name = None
        for n, d in self.mods.items():
            if n.lower() == name.lower():
                mod_data = d
                mod_name = n
                break

        if mod_data is None:
            raise ValueError(f"Mod not found: {name}")

        # Determine max rank
        if "stats" in mod_data:
            max_rank = max(s.get("maxRank", 0) for s in mod_data["stats"])
        else:
            max_rank = mod_data.get("maxRank", 0)

        # Default to max rank
        if rank is None:
            rank = max_rank
        rank = min(rank, max_rank)

        # Resolve stats
        stats = []
        if "stats" in mod_data:
            for s in mod_data["stats"]:
                inc = s["increment"]
                s_max_rank = s.get("maxRank", max_rank)
                effective_rank = min(rank, s_max_rank)
                value = inc * (effective_rank + 1)
                condition = s.get("condition", "")
                max_stacks = s.get("max_stacks", 1)
                if condition == "per_combo":
                    if stacks is not None:
                        value *= max(0.0, combo_multiplier - 1.0)
                elif condition and stacks is not None:
                    value *= max(0, min(stacks, max_stacks))
                stats.append(ModStat(stat=s["stat"], value=value, condition=condition, max_stacks=max_stacks))
        elif "stat" in mod_data:
            inc = mod_data["increment"]
            value = inc * (rank + 1)
            stats.append(ModStat(stat=mod_data["stat"], value=value))

        return ResolvedMod(
            name=mod_name,
            rank=rank,
            max_rank=max_rank,
            mod_type=mod_data.get("type", ""),
            stats=stats,
            polarity=mod_data.get("polarity", ""),
            conditional=mod_data.get("conditional", ""),
            note=mod_data.get("note", ""),
            set_bonus=mod_data.get("setBonus", ""),
        )

    def find_mod(self, query: str) -> List[str]:
        """Find mods by partial name match."""
        q = query.lower()
        return [n for n in self.mods if q in n.lower()]


# ============================================================================
# MOD STACK / BUILD
# ============================================================================

@dataclass
class ModdedStats:
    """All modded weapon stats after applying a mod loadout."""
    # Damage multipliers
    damage_bonus: float = 0.0      # +Damage% (Serration etc)
    multishot_bonus: float = 0.0   # +Multishot% (Split Chamber etc)

    # Crit
    crit_chance_bonus: float = 0.0
    crit_damage_bonus: float = 0.0

    # Status
    status_chance_bonus: float = 0.0
    status_duration_bonus: float = 0.0

    # Fire rate / attack speed
    fire_rate_bonus: float = 0.0

    # Reload
    reload_speed_bonus: float = 0.0

    # Magazine
    mag_size_bonus: float = 0.0

    # Physical damage bonuses (applied to their respective base damage type)
    impact_bonus: float = 0.0
    puncture_bonus: float = 0.0
    slash_bonus: float = 0.0

    # Elemental damage bonuses (percentage of base damage, added as elemental)
    # These are stored as ordered list to preserve combination order
    elemental_mods: List[Tuple[str, float]] = field(default_factory=list)

    # Faction damage
    faction_bonus: float = 0.0
    faction_target: str = ""

    # Special
    condition_overload: float = 0.0     # Per-status-type multiplier
    galvanized_stacks: float = 0.0      # Per-status-type (galvanized)

    # Melee combo
    combo_duration_bonus: float = 0.0   # Flat seconds added

    # Accuracy penalty (Heavy Caliber etc)
    accuracy_bonus: float = 0.0


def build_modded_stats(mods: List[ResolvedMod]) -> ModdedStats:
    """Aggregate all mod stats into a single ModdedStats.

    Elemental mod order is preserved for correct combination.
    """
    result = ModdedStats()

    for mod in mods:
        for stat in mod.stats:
            s = stat.stat.upper()
            v = stat.value

            if s == "DAMAGE":
                result.damage_bonus += v
            elif s == "MULTISHOT":
                result.multishot_bonus += v
            elif s == "CRIT_CHANCE":
                result.crit_chance_bonus += v
            elif s == "CRIT_DAMAGE":
                result.crit_damage_bonus += v
            elif s == "STATUS_CHANCE":
                result.status_chance_bonus += v
            elif s == "STATUS_DURATION":
                result.status_duration_bonus += v
            elif s == "FIRE_RATE":
                result.fire_rate_bonus += v
            elif s == "RELOAD_SPEED":
                result.reload_speed_bonus += v
            elif s == "MAG_SIZE":
                result.mag_size_bonus += v
            elif s == "IMPACT":
                result.impact_bonus += v
            elif s == "PUNCTURE":
                result.puncture_bonus += v
            elif s == "SLASH":
                result.slash_bonus += v
            elif s in STAT_TO_ELEMENT:
                element = STAT_TO_ELEMENT[s]
                result.elemental_mods.append((element, v))
            elif s.startswith("FACTION_"):
                result.faction_bonus += v
                result.faction_target = s.replace("FACTION_", "")
            elif s == "CONDITION_OVERLOAD":
                result.condition_overload += v
            elif s == "GALV_STATUS_STACKS":
                result.galvanized_stacks += v
            elif s == "COMBO_DURATION":
                result.combo_duration_bonus += v
            elif s == "ACCURACY":
                result.accuracy_bonus += v

    return result


# ============================================================================
# ELEMENTAL COMBINATION
# ============================================================================

def combine_elements(
    innate_elements: Dict[str, float],
    mod_elements: List[Tuple[str, float]],
    base_damage: float,
) -> Dict[str, float]:
    """Combine elemental damage types following Warframe's rules.

    Rules:
    1. Mod elementals are calculated as percentage of total base damage
    2. Elements combine left-to-right in mod slot order
    3. Innate weapon elements combine LAST (rightmost)
    4. Innate combined elements won't split

    Args:
        innate_elements: Base elemental damage from the weapon {type: value}
        mod_elements: Ordered list of (element_type, bonus_pct) from mods
        base_damage: Total base damage (sum of all base damage types)

    Returns:
        Final elemental damage distribution {type: value}
    """
    # Start with a list of elements in order: mods first, then innate
    # Each entry is (element_type, damage_value)
    element_queue: List[Tuple[str, float]] = []

    # Add mod elementals (calculated from base damage)
    for elem_type, bonus_pct in mod_elements:
        element_queue.append((elem_type, base_damage * bonus_pct))

    # Add innate elements at the end
    for elem_type, dmg_val in innate_elements.items():
        if elem_type in BASE_ELEMENTAL_TYPES:
            element_queue.append((elem_type, dmg_val))
        # Innate combined elements are added separately and don't re-combine

    # Process combination: iterate and combine adjacent compatible pairs
    combined: List[Tuple[str, float]] = []

    for elem_type, dmg_val in element_queue:
        merged = False
        # A repeated element stacks onto its earlier occurrence, keeping that
        # slot position (e.g. Hellfire + Thermite Rounds are one Heat entry,
        # and a second Toxin mod adds to an already-formed Viral).
        for i, (existing_type, existing_val) in enumerate(combined):
            if existing_type == elem_type or elem_type in COMBINED_ELEMENT_COMPONENTS.get(existing_type, ()):
                combined[i] = (existing_type, existing_val + dmg_val)
                merged = True
                break
        if merged:
            continue
        # Try to combine with an existing uncombined base element
        for i, (existing_type, existing_val) in enumerate(combined):
            if existing_type in BASE_ELEMENTAL_TYPES and elem_type in BASE_ELEMENTAL_TYPES:
                combo_key = (existing_type, elem_type)
                if combo_key in ELEMENTAL_COMBINATIONS:
                    new_type = ELEMENTAL_COMBINATIONS[combo_key]
                    combined[i] = (new_type, existing_val + dmg_val)
                    merged = True
                    break
        if not merged:
            combined.append((elem_type, dmg_val))

    # Also add innate combined elements that don't re-split
    for elem_type, dmg_val in innate_elements.items():
        if elem_type not in BASE_ELEMENTAL_TYPES:
            # Check if this type already exists in combined
            found = False
            for i, (t, v) in enumerate(combined):
                if t == elem_type:
                    combined[i] = (t, v + dmg_val)
                    found = True
                    break
            if not found:
                combined.append((elem_type, dmg_val))

    return {t: v for t, v in combined}
