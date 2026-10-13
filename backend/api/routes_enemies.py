from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.deps import enemy_scaler
from api.schemas import EnemyDetail, EnemySummary, ScaledEnemyDetail
from engine.constants import FACTION_MODIFIERS
from engine.enemies import ScaledEnemy

router = APIRouter(prefix="/api/enemies", tags=["enemies"])


def scaled_to_schema(e: ScaledEnemy) -> ScaledEnemyDetail:
    return ScaledEnemyDetail(
        name=e.name,
        faction=e.faction,
        base_level=e.base_level,
        current_level=e.current_level,
        health=e.health,
        shield=e.shield,
        armor=e.armor,
        overguard=e.overguard,
        armor_dr=e.armor_dr,
        armor_dm=e.armor_dm,
        is_eximus=e.is_eximus,
        is_steel_path=e.is_steel_path,
        faction_modifiers=e.faction_modifiers,
        ehp=e.ehp_vs_neutral,
    )


def _summary(key: str, data: dict) -> EnemySummary:
    return EnemySummary(
        key=key,
        name=data.get("name", key),
        faction=data.get("faction", "Unaffiliated"),
        variant_type=data.get("variantType", ""),
        base_level=data.get("baseLevel", 1),
        health=data.get("health", 0),
        armor=data.get("armor", 0),
        shield=data.get("shield", 0),
    )


def _require(key: str) -> dict:
    data = enemy_scaler.enemies.get(key)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Enemy not found: {key}")
    return data


@router.get("", response_model=List[EnemySummary])
def list_enemies(search: Optional[str] = None, faction: Optional[str] = None):
    keys = enemy_scaler.list_enemies(faction=faction, name_filter=search)
    return [_summary(k, enemy_scaler.enemies[k]) for k in keys]


# Enemy keys look like "Heavy Gunner|Grineer|STANDARD" and a few contain
# slashes, so the key is matched as a path. The /scaled route must be
# registered before the plain detail route.
@router.get("/{key:path}/scaled", response_model=ScaledEnemyDetail)
def get_enemy_scaled(
    key: str,
    level: int = Query(100, ge=1, le=9999),
    steel_path: bool = False,
    eximus: bool = False,
    armor_strip_pct: float = Query(0.0, ge=0.0, le=1.0),
):
    _require(key)
    return scaled_to_schema(
        enemy_scaler.scale_enemy(key, level, eximus, steel_path, armor_strip_pct)
    )


@router.get("/{key:path}", response_model=EnemyDetail)
def get_enemy(key: str, level: Optional[int] = Query(None, ge=1, le=9999)):
    data = _require(key)
    base_level = data.get("baseLevel", 1)
    scaled = enemy_scaler.scale_enemy(key, level if level is not None else base_level)
    return EnemyDetail(
        **_summary(key, data).model_dump(),
        overguard=data.get("overguard", 0),
        faction_modifiers=FACTION_MODIFIERS.get(data.get("faction", ""), {}),
        immune_procs=data.get("immuneProcs", []),
        scaled=scaled_to_schema(scaled),
    )
