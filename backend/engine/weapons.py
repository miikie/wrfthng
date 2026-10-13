"""Weapon data loading and stat resolution."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.constants import PHYSICAL_TYPES, BASE_ELEMENTAL_TYPES


@dataclass
class WeaponData:
    """Parsed weapon stats from the database."""
    name: str
    unique_name: str
    category: str       # LongGuns, Pistols, Melee, etc.

    # Base damage per type
    damage: Dict[str, float] = field(default_factory=dict)
    total_damage: float = 0.0

    # Crit
    crit_chance: float = 0.0
    crit_mult: float = 1.0

    # Status
    status_chance: float = 0.0

    # Fire rate / attack speed
    fire_rate: float = 1.0

    # Magazine
    mag_size: int = 0
    reload_time: float = 0.0

    # Multishot
    multishot: int = 1

    # Trigger type
    trigger: str = ""

    # Tags
    tags: List[str] = field(default_factory=list)

    # Mastery
    mastery_req: int = 0

    # Behaviours (for complex weapons)
    behaviours: List[dict] = field(default_factory=list)

    # Set for companion weapons, whose category doesn't say which mods they take
    mod_type_override: str = ""

    # Display only: artwork file on the WFCD CDN and the weapon's innate slot polarities
    image_name: str = ""
    polarities: List[str] = field(default_factory=list)

    @property
    def is_melee(self) -> bool:
        return self.category in ("Melee", "Claws") or self.mod_type_override == "MELEE"

    @property
    def is_shotgun(self) -> bool:
        return any(t in self.tags for t in ("SHOTGUN", "SECONDARYSHOTGUN"))

    @property
    def is_primary(self) -> bool:
        return self.category == "LongGuns"

    @property
    def is_secondary(self) -> bool:
        return self.category == "Pistols"

    @property
    def physical_damage(self) -> Dict[str, float]:
        """Just the physical damage components."""
        return {k: v for k, v in self.damage.items() if k in PHYSICAL_TYPES}

    @property
    def elemental_damage(self) -> Dict[str, float]:
        """Just the elemental damage components (innate)."""
        return {k: v for k, v in self.damage.items() if k not in PHYSICAL_TYPES}

    @property
    def mod_type(self) -> str:
        """Determine which mod type applies to this weapon."""
        if self.mod_type_override:
            return self.mod_type_override
        if self.is_melee:
            return "MELEE"
        elif self.is_shotgun:
            return "SHOTGUN"
        elif self.is_secondary:
            return "SECONDARY"
        else:
            return "PRIMARY"

    @property
    def base_damage(self) -> float:
        """Total base damage (sum of all types)."""
        return sum(self.damage.values())

    @property
    def impact_distribution(self) -> float:
        """Fraction of base damage that is Impact."""
        bd = self.base_damage
        return self.damage.get("Impact", 0) / bd if bd > 0 else 0.0

    @property
    def puncture_distribution(self) -> float:
        """Fraction of base damage that is Puncture."""
        bd = self.base_damage
        return self.damage.get("Puncture", 0) / bd if bd > 0 else 0.0

    @property
    def slash_distribution(self) -> float:
        """Fraction of base damage that is Slash."""
        bd = self.base_damage
        return self.damage.get("Slash", 0) / bd if bd > 0 else 0.0


class WeaponLoader:
    """Loads and queries the weapon database."""

    def __init__(self, weapons_path: str = "data/processed/weapons.json"):
        self.weapons: Dict[str, WeaponData] = {}
        self._load(weapons_path)

    def _load(self, path: str):
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        self.add(raw)

    def add(self, raw: Dict[str, dict]):
        """Add weapons from a weapons.json-shaped dict."""
        for name, data in raw.items():
            self.weapons[name] = WeaponData(
                name=data.get("name", name),
                unique_name=data.get("uniqueName", ""),
                category=data.get("category", ""),
                damage=data.get("damage", {}),
                total_damage=data.get("totalDamage", 0),
                crit_chance=data.get("critChance", 0),
                crit_mult=data.get("critMult", 1),
                status_chance=data.get("statusChance", 0),
                fire_rate=data.get("fireRate", 1),
                mag_size=data.get("magSize", 0),
                reload_time=data.get("reloadTime", 0),
                multishot=data.get("multishot", 1),
                trigger=data.get("trigger", ""),
                tags=data.get("tags", []),
                mastery_req=data.get("masteryReq", 0),
                behaviours=data.get("behaviours", []),
            )

    def get(self, name: str) -> Optional[WeaponData]:
        """Get a weapon by exact name."""
        return self.weapons.get(name)

    def find(self, query: str) -> List[str]:
        """Find weapons by partial name match."""
        q = query.lower()
        return sorted(n for n in self.weapons if q in n.lower())

    def list_by_category(self, category: str) -> List[str]:
        """List weapons in a category (LongGuns, Pistols, Melee, etc.)."""
        return sorted(
            n for n, w in self.weapons.items()
            if w.category.lower() == category.lower()
        )
