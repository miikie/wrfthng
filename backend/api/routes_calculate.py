from itertools import product
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException

from api.deps import (
    amp_loader, buff_catalogue, calculator, companion_loader, enemy_scaler,
    mod_resolver, weapon_loader,
)
from api.routes_enemies import scaled_to_schema
from api.schemas import (
    CalculateRequest, CalculateResponse, CompareRequest, CompareResponse,
    ActiveBuff, AmpResult, AveragedDps, CritResponse, InactiveBuff, DamageBreakdownResponse, DoTResponse,
    DPSResponse, ElementGroup, ElementSource, ModInput, SideResult,
)
from engine.constants import (
    BASE_ELEMENTAL_TYPES, COMBINED_ELEMENT_COMPONENTS, ELEMENTAL_COMBINATIONS,
    STAT_TO_ELEMENT,
)
from engine.amps import AmpFireMode
from engine.damage import Buffs
from engine.enemies import ScaledEnemy
from engine.modding import ModdedStats, ResolvedMod
from engine.weapons import WeaponData

router = APIRouter(prefix="/api", tags=["calculate"])


def trace_elements(weapon: WeaponData, mods: List[ResolvedMod]) -> List[ElementGroup]:
    """Explain which mods/innate elements formed each final elemental type.

    Display-only: mirrors the walk in engine.modding.combine_elements (mods in
    slot order, innate base elements last, innate combined elements never
    re-split) but tracks sources instead of damage values.
    """
    queue: List[Tuple[str, str]] = []
    for mod in mods:
        for stat in mod.stats:
            element = STAT_TO_ELEMENT.get(stat.stat.upper())
            if element:
                queue.append((element, mod.name))

    innate: Dict[str, float] = weapon.elemental_damage
    for element in innate:
        if element in BASE_ELEMENTAL_TYPES:
            queue.append((element, "Innate"))

    groups: List[ElementGroup] = []
    for element, source in queue:
        entry = ElementSource(element=element, source=source)
        stacked = next(
            (g for g in groups
             if g.type == element or element in COMBINED_ELEMENT_COMPONENTS.get(g.type, ())),
            None,
        )
        if stacked:
            stacked.sources.append(entry)
            continue
        for group in groups:
            if group.type in BASE_ELEMENTAL_TYPES and (group.type, element) in ELEMENTAL_COMBINATIONS:
                group.type = ELEMENTAL_COMBINATIONS[(group.type, element)]
                group.sources.append(entry)
                break
        else:
            groups.append(ElementGroup(type=element, sources=[entry]))

    for element in innate:
        if element not in BASE_ELEMENTAL_TYPES:
            entry = ElementSource(element=element, source="Innate")
            for group in groups:
                if group.type == element:
                    group.sources.append(entry)
                    break
            else:
                groups.append(ElementGroup(type=element, sources=[entry]))

    return groups


def resolve_mods(inputs: List[ModInput], req: CalculateRequest, combo: float = 1.0) -> List[ResolvedMod]:
    # conditional stats count only for the stacks the player has switched on
    stacks = {name.lower(): n for name, n in req.conditional_stacks.items()}
    seen = set()
    mods: List[ResolvedMod] = []
    for m in inputs:
        try:
            resolved = mod_resolver.resolve(
                m.name, m.rank, stacks=stacks.get(m.name.lower(), 0), combo_multiplier=combo)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        if resolved.name in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate mod: {resolved.name}")
        seen.add(resolved.name)
        mods.append(resolved)
    return mods


def companion_result(req: CalculateRequest, enemy: ScaledEnemy, buffs: Buffs) -> SideResult:
    inp = req.companion
    companion = companion_loader.get(inp.name)
    if companion is None:
        raise HTTPException(status_code=404, detail=f"Companion not found: {inp.name}")
    weapon_name = inp.weapon or companion["defaultWeapon"]
    notes: List[str] = []
    if companion["needsAttackPrecept"]:
        notes.append("Sentinels only fire with an attack precept equipped (Assault Mode or their own).")
    weapon = weapon_loader.get(weapon_name) if weapon_name else None
    if companion["needsAttackPrecept"] and not req.sentinel_attack_precept:
        notes[:] = ["No attack precept equipped, so this Sentinel does not fire."]
        weapon = None
    elif weapon is None:
        notes.append("No weapon equipped, so no weapon damage.")
    if weapon is None:
        return SideResult(
            label=companion["name"], weapon_name="", average_shot=0, burst_dps=0, sustained_dps=0,
            fire_rate=0, crit_chance=0, crit_mult=0, status_chance=0, per_type_inflicted={}, notes=notes,
        )
    if weapon_name not in companion["weapons"]:
        raise HTTPException(status_code=422, detail=f"{companion['name']} cannot use {weapon_name}")
    r = calculator.calculate(
        weapon, enemy, mods=resolve_mods(inp.mods, req),
        viral_stacks=req.viral_stacks,
        status_types_on_target=req.status_types_on_target,
        buffs=buffs,
    )
    return SideResult(
        label=companion["name"], weapon_name=weapon.name,
        average_shot=r.dps.average_shot, burst_dps=r.dps.burst_dps, sustained_dps=r.dps.sustained_dps,
        fire_rate=r.dps.effective_fire_rate, crit_chance=r.modded_crit_chance, crit_mult=r.modded_crit_mult,
        status_chance=r.modded_status_chance, per_type_inflicted=r.damage.per_type_inflicted, notes=notes,
    )


def fire_mode_result(
    label: str, mode: AmpFireMode, arcane_stats: ModdedStats, notes: List[str],
    req: CalculateRequest, enemy: ScaledEnemy, buffs: Buffs,
) -> SideResult:
    mode_buffs = Buffs(**vars(buffs))
    mode_buffs.crit_chance_flat += mode.crit_chance_flat
    mode_buffs.status_chance_flat += mode.status_chance_flat
    results = [
        calculator.calculate(
            attack, enemy, modded_stats=arcane_stats,
            headshot=req.headshot, viral_stacks=req.viral_stacks,
            buffs=mode_buffs, ammo_cost=mode.ammo_cost,
        )
        for attack in mode.attacks
    ]
    first = results[0]
    per_type: Dict[str, float] = {}
    for r in results:
        for dtype, value in r.damage.per_type_inflicted.items():
            per_type[dtype] = per_type.get(dtype, 0.0) + value * r.modded_multishot
    average_shot = sum(r.dps.average_shot for r in results)
    burst = average_shot * first.dps.effective_fire_rate
    extra = list(notes) + list(mode.notes)
    if len(results) > 1:
        extra.append("Each shot's damage instances (" + ", ".join(a.name.split(": ")[1] for a in mode.attacks)
                     + ") are added together.")
    return SideResult(
        label=label, weapon_name=mode.part_name,
        average_shot=average_shot, burst_dps=burst, sustained_dps=burst * first.dps.shoot_ratio,
        fire_rate=first.dps.effective_fire_rate, crit_chance=first.modded_crit_chance,
        crit_mult=first.modded_crit_mult, status_chance=first.modded_status_chance,
        per_type_inflicted=per_type, notes=extra,
    )


def amp_result(req: CalculateRequest, enemy: ScaledEnemy, buffs: Buffs) -> AmpResult:
    inp = req.amp
    prism = amp_loader.prisms.get(inp.prism)
    if prism is None:
        raise HTTPException(status_code=404, detail=f"Amp prism not found: {inp.prism}")
    scaffold = amp_loader.scaffolds.get(inp.scaffold) if inp.scaffold else None
    brace = amp_loader.braces.get(inp.brace) if inp.brace else None
    if inp.scaffold and scaffold is None:
        raise HTTPException(status_code=404, detail=f"Amp scaffold not found: {inp.scaffold}")
    if inp.brace and brace is None:
        raise HTTPException(status_code=404, detail=f"Amp brace not found: {inp.brace}")
    try:
        stats, notes = amp_loader.arcane_stats([(a.name, a.rank) for a in inp.arcanes])
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Amp arcane not found: {e.args[0]}")
    primary = fire_mode_result("Primary fire", amp_loader.fire_mode(prism, brace), stats, notes, req, enemy, buffs)
    alt = None
    if scaffold:
        alt = fire_mode_result("Alternate fire", amp_loader.fire_mode(scaffold, brace), stats, notes, req, enemy, buffs)
    return AmpResult(primary=primary, alt=alt)


def run_calculation(req: CalculateRequest) -> CalculateResponse:
    weapon = weapon_loader.get(req.weapon)
    if weapon is None:
        raise HTTPException(status_code=404, detail=f"Weapon not found: {req.weapon}")

    if req.enemy not in enemy_scaler.enemies:
        raise HTTPException(status_code=404, detail=f"Enemy not found: {req.enemy}")

    mods = resolve_mods(req.mods, req, req.combo_multiplier)

    # Buffs whose requirement the loadout doesn't meet are left out and reported back.
    companion_info = companion_loader.get(req.companion.name) if req.companion else None
    selected, inactive = [], []
    for b in req.buffs:
        if b.id not in buff_catalogue.buffs:
            raise HTTPException(status_code=404, detail=f"Buff not found: {b.id}")
        reason = buff_catalogue.unmet(b.id, companion_info, weapon.is_melee)
        if reason:
            inactive.append(InactiveBuff(id=b.id, name=buff_catalogue.buffs[b.id]["name"], reason=reason))
        else:
            selected.append(b)

    def as_selection(items):
        return [(b.id, b.rank, b.amount) for b in items]

    def uptime_of(b) -> float:
        info = buff_catalogue.buffs[b.id]
        if info["kind"] == "armor_strip":   # applied once and it stays
            return 1.0
        return info["uptime"] if b.uptime is None else b.uptime

    buffs, buff_strip, applied = buff_catalogue.resolve(as_selection(selected))
    for item, b in zip(applied, selected):
        if item.uptime is not None:
            item.uptime = uptime_of(b)
    armor_strip = min(1.0, req.armor_strip_pct + buff_strip)

    enemy = enemy_scaler.scale_enemy(
        req.enemy, req.enemy_level,
        is_eximus=req.eximus,
        is_steel_path=req.steel_path,
        armor_strip_pct=armor_strip,
        viral_stacks=req.viral_stacks,
    )

    r = calculator.calculate(
        weapon, enemy, mods=mods,
        headshot=req.headshot,
        viral_stacks=req.viral_stacks,
        status_types_on_target=req.status_types_on_target,
        combo_multiplier=req.combo_multiplier,
        buffs=buffs["weapon"],
    )

    # Average over buff uptime: weigh every on/off combination of the part-time
    # buffs by how likely it is, treating the buffs as independent.
    averaged = None
    part_time = [b for b in selected if uptime_of(b) < 1.0][:6]
    if part_time:
        always = [b for b in selected if b not in part_time]
        totals = [0.0, 0.0, 0.0]
        for states in product((True, False), repeat=len(part_time)):
            weight = 1.0
            for b, on in zip(part_time, states):
                weight *= uptime_of(b) if on else 1.0 - uptime_of(b)
            if weight == 0:
                continue
            active = always + [b for b, on in zip(part_time, states) if on]
            combo_buffs = buff_catalogue.resolve(as_selection(active))[0]["weapon"]
            rr = calculator.calculate(
                weapon, enemy, mods=mods, headshot=req.headshot, viral_stacks=req.viral_stacks,
                status_types_on_target=req.status_types_on_target,
                combo_multiplier=req.combo_multiplier, buffs=combo_buffs,
            )
            for i, v in enumerate((rr.dps.average_shot, rr.dps.burst_dps, rr.dps.sustained_dps)):
                totals[i] += weight * v
        averaged = AveragedDps(average_shot=totals[0], burst_dps=totals[1], sustained_dps=totals[2])

    companion = companion_result(req, enemy, buffs["companion"]) if req.companion else None
    amp = amp_result(req, enemy, buffs["amp"]) if req.amp else None

    return CalculateResponse(
        weapon_name=r.weapon_name,
        enemy_name=r.enemy_name,
        enemy_level=r.enemy_level,
        modded_base_damage=r.modded_base_damage,
        modded_multishot=r.modded_multishot,
        modded_fire_rate=r.modded_fire_rate,
        modded_crit_chance=r.modded_crit_chance,
        modded_crit_mult=r.modded_crit_mult,
        modded_status_chance=r.modded_status_chance,
        modded_mag_size=r.modded_mag_size,
        modded_reload_time=r.modded_reload_time,
        damage=DamageBreakdownResponse.model_validate(r.damage),
        crit=CritResponse.model_validate(r.crit),
        dps=DPSResponse.model_validate(r.dps),
        dots=[DoTResponse.model_validate(d) for d in r.dots],
        enemy_ehp=r.enemy_ehp,
        shots_to_kill=r.shots_to_kill,
        time_to_kill=r.time_to_kill,
        arsenal_total_damage=r.arsenal_total_damage,
        viral_damage_bonus=r.viral_damage_bonus,
        condition_overload_mult=r.condition_overload_mult,
        elements=trace_elements(weapon, mods),
        enemy=scaled_to_schema(enemy),
        active_buffs=[ActiveBuff(**vars(a)) for a in applied],
        inactive_buffs=inactive,
        averaged=averaged,
        armor_before_buffs=enemy_scaler.scale_enemy(
            req.enemy, req.enemy_level, is_eximus=req.eximus, is_steel_path=req.steel_path,
            armor_strip_pct=req.armor_strip_pct, viral_stacks=req.viral_stacks,
        ).armor,
        companion=companion,
        amp=amp,
        combined_sustained_dps=r.dps.sustained_dps + (companion.sustained_dps if companion else 0.0),
    )


@router.post("/calculate", response_model=CalculateResponse)
def calculate(req: CalculateRequest):
    return run_calculation(req)


@router.post("/compare", response_model=CompareResponse)
def compare(req: CompareRequest):
    return CompareResponse(results=[run_calculation(b) for b in req.builds])
