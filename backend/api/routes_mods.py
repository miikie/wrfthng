from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.deps import image_map, mod_resolver
from api.schemas import ModDetail, ModStatValue

router = APIRouter(prefix="/api/mods", tags=["mods"])


def _detail(name: str, rank: Optional[int] = None) -> ModDetail:
    resolved = mod_resolver.resolve(name, rank)
    raw = mod_resolver.mods[resolved.name]
    return ModDetail(
        name=resolved.name,
        type=resolved.mod_type,
        rank=resolved.rank,
        max_rank=resolved.max_rank,
        polarity=resolved.polarity,
        rarity=raw.get("rarity", ""),
        stats=[ModStatValue(stat=s.stat, value=s.value, condition=s.condition, max_stacks=s.max_stacks)
               for s in resolved.stats],
        base_drain=raw.get("baseDrain", 0),
        image_name=image_map["mods"].get(resolved.name, ""),
        exilus=bool(raw.get("exilus")),
        conditional=resolved.conditional,
        note=resolved.note,
        set_bonus=resolved.set_bonus,
    )


# The list returns full details: there are only ~100 mods and the loadout
# builder needs notes/conditionals for every card.
@router.get("", response_model=List[ModDetail])
def list_mods(
    search: Optional[str] = None,
    type: Optional[str] = None,
    stat: Optional[str] = None,
):
    names = mod_resolver.list_mods(mod_type=type, stat_filter=stat)
    if search:
        q = search.lower()
        names = [n for n in names if q in n.lower()]
    return [_detail(n) for n in names]


@router.get("/{name:path}", response_model=ModDetail)
def get_mod(name: str, rank: Optional[int] = Query(None, ge=0)):
    try:
        return _detail(name, rank)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
