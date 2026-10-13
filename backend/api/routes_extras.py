"""Catalogues for companions, amp parts and cross-system buffs."""

from typing import List

from fastapi import APIRouter

from api.deps import (
    amp_loader, buff_catalogue, companion_loader, image_map, weapon_arcanes, weapon_loader,
)
from api.schemas import AmpCatalogue, BuffInfo, CompanionInfo

router = APIRouter(prefix="/api", tags=["extras"])


@router.get("/companions", response_model=List[CompanionInfo])
def list_companions():
    out = []
    for c in sorted(companion_loader.companions.values(), key=lambda c: (c["type"], c["name"])):
        # only offer weapons the calculator actually has
        weapons = [w for w in c["weapons"] if w in weapon_loader.weapons]
        default = c["defaultWeapon"] if c["defaultWeapon"] in weapons else ""
        out.append(CompanionInfo(**{**c, "weapons": weapons, "defaultWeapon": default,
                                    "imageName": image_map["companions"].get(c["name"], "")}))
    return out


@router.get("/amps", response_model=AmpCatalogue)
def amp_parts():
    def with_image(items, section):
        return [{**item, "imageName": image_map[section].get(item["name"], "")} for item in items]

    data = amp_loader.data
    return AmpCatalogue(
        prisms=with_image(data["prisms"], "ampParts"), scaffolds=with_image(data["scaffolds"], "ampParts"),
        braces=with_image(data["braces"], "ampParts"), arcanes=with_image(data["arcanes"], "arcanes"),
    )


@router.get("/weapon-arcanes")
def list_weapon_arcanes():
    """Arcanes for weapon arcane slots. Shown in the loadout only; not part of any calculation."""
    return weapon_arcanes


@router.get("/buffs", response_model=List[BuffInfo])
def list_buffs():
    return [BuffInfo(**b) for b in buff_catalogue.buffs.values()]
