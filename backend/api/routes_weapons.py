from typing import List, Optional

from fastapi import APIRouter, HTTPException

from api.deps import weapon_loader
from api.schemas import WeaponDetail, WeaponSummary

router = APIRouter(prefix="/api/weapons", tags=["weapons"])


@router.get("", response_model=List[WeaponSummary])
def list_weapons(
    search: Optional[str] = None,
    category: Optional[str] = None,
    include_empty: bool = False,
    include_companion: bool = False,
):
    """List weapons. Entries with no damage data (kitgun/zaw/amp parts) are
    hidden unless include_empty is set."""
    q = search.lower() if search else None
    results = []
    for name in sorted(weapon_loader.weapons):
        w = weapon_loader.weapons[name]
        if q and q not in name.lower():
            continue
        if category and w.category.lower() != category.lower():
            continue
        # beast claws are companion-only weapons
        if not include_companion and w.category == "Claws":
            continue
        if not include_empty and w.base_damage <= 0:
            continue
        results.append(w)
    return results


@router.get("/{name:path}", response_model=WeaponDetail)
def get_weapon(name: str):
    w = weapon_loader.get(name)
    if w is None:
        raise HTTPException(status_code=404, detail=f"Weapon not found: {name}")
    return w
