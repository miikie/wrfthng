"""API smoke tests. Run from backend/: python -m pytest tests"""

import itertools
from urllib.parse import quote

from fastapi.testclient import TestClient

from api.deps import calculator, enemy_scaler, mod_resolver, weapon_loader
from api.routes_calculate import trace_elements
from engine.modding import combine_elements
from main import app

client = TestClient(app)

GUNNER = "Heavy Gunner|Grineer|STANDARD"
SOMA_BUILD = [
    {"name": "Serration", "rank": 10},
    {"name": "Split Chamber", "rank": 5},
    {"name": "Point Strike", "rank": 5},
    {"name": "Vital Sense", "rank": 5},
]


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_data_endpoints():
    assert len(client.get("/api/weapons").json()) > 500
    assert client.get("/api/weapons/Soma Prime").json()["critMult"] == 3.0
    assert client.get("/api/weapons/Soma Primer").status_code == 404
    assert len(client.get("/api/enemies?search=gunner&faction=Grineer").json()) > 0
    key = quote(GUNNER, safe="")
    assert client.get(f"/api/enemies/{key}").json()["name"] == "Heavy Gunner"
    scaled = client.get(f"/api/enemies/{key}/scaled?level=100&steel_path=true&eximus=true").json()
    assert scaled["currentLevel"] == 200 and scaled["overguard"] > 0
    assert len(client.get("/api/mods?type=PRIMARY&stat=DAMAGE").json()) > 0
    assert abs(client.get("/api/mods/Serration?rank=5").json()["stats"][0]["value"] - 0.9) < 1e-9


def test_calculate_matches_engine():
    """The API must return exactly what the engine computes."""
    body = {"weapon": "Soma Prime", "enemy": GUNNER, "enemyLevel": 100, "mods": SOMA_BUILD}
    got = client.post("/api/calculate", json=body).json()

    weapon = weapon_loader.get("Soma Prime")
    enemy = enemy_scaler.scale_enemy(GUNNER, 100)
    mods = [mod_resolver.resolve(m["name"], m["rank"]) for m in SOMA_BUILD]
    want = calculator.calculate(weapon, enemy, mods=mods)

    assert got["dps"]["averageShot"] == want.dps.average_shot
    assert got["dps"]["burstDps"] == want.dps.burst_dps
    assert got["dps"]["sustainedDps"] == want.dps.sustained_dps
    assert got["damage"]["perType"] == want.damage.per_type
    assert got["timeToKill"] == want.time_to_kill
    assert got["arsenalTotalDamage"] == want.arsenal_total_damage


def test_melee_has_no_magazine():
    r = client.post("/api/calculate", json={"weapon": "Nikana Prime", "enemy": GUNNER})
    assert r.status_code == 200
    assert r.json()["dps"]["shotsPerMag"] is None


def test_duplicate_mods_rejected():
    body = {"weapon": "Soma Prime", "enemy": GUNNER,
            "mods": [{"name": "Serration"}, {"name": "serration"}]}
    assert client.post("/api/calculate", json=body).status_code == 422


def test_repeated_elements_stack():
    # Two Heat mods are one Heat entry; nothing is lost.
    assert combine_elements({}, [("Heat", 0.9), ("Heat", 0.6)], 100) == {"Heat": 150.0}
    # Heat + Heat + Cold is all Blast.
    assert combine_elements({}, [("Heat", 0.9), ("Heat", 0.6), ("Cold", 0.9)], 100) == {"Blast": 240.0}
    # A later Toxin joins the Viral it is already part of.
    assert combine_elements({}, [("Cold", 0.9), ("Toxin", 0.9), ("Toxin", 0.6)], 100) == {"Viral": 240.0}
    # Innate Heat combines last.
    assert combine_elements({"Heat": 10}, [("Cold", 0.9), ("Toxin", 0.9)], 100) == {"Viral": 180.0, "Heat": 10}


def test_element_trace_agrees_with_engine():
    """The display trace must name the same final types the engine produces."""
    elemental = ["Hellfire", "Thermite Rounds", "Cryo Rounds", "Rime Rounds",
                 "Stormbringer", "High Voltage", "Infected Clip", "Malignant Force"]
    weapons = [weapon_loader.get(n) for n in ("Soma Prime", "Ignis Wraith", "Kuva Bramma")]
    for weapon in weapons:
        for n in range(0, 5):
            for combo in itertools.permutations(elemental, n):
                mods = [mod_resolver.resolve(m) for m in combo]
                pairs = [(s.stat.capitalize(), s.value) for m in mods for s in m.stats
                         if s.stat in ("HEAT", "COLD", "ELECTRICITY", "TOXIN")]
                engine = combine_elements(weapon.elemental_damage, pairs, weapon.base_damage)
                traced = [g.type for g in trace_elements(weapon, mods)]
                assert traced == list(engine), (weapon.name, combo)


# ----------------------------------------------------------------------------
# Buffs, companions and amps
# ----------------------------------------------------------------------------

BASE = {
    "weapon": "Soma Prime", "enemy": "Heavy Gunner|Grineer|STANDARD", "enemyLevel": 100,
    "mods": [{"name": "Serration", "rank": 10}, {"name": "Point Strike", "rank": 5}],
}


def _calc(extra=None):
    r = client.post("/api/calculate", json={**BASE, **(extra or {})})
    assert r.status_code == 200, r.text
    return r.json()


def test_no_extras_leaves_result_unchanged():
    r = _calc()
    assert r["companion"] is None and r["amp"] is None and r["activeBuffs"] == []
    assert r["combinedSustainedDps"] == r["dps"]["sustainedDps"]


def test_cats_eye_adds_flat_crit_points_after_mods():
    plain = _calc()
    buffed = _calc({"buffs": [{"id": "companion.cats_eye"}], "companion": {"name": "Adarza Kavat"}})
    assert abs(buffed["moddedCritChance"] - (plain["moddedCritChance"] + 0.60)) < 1e-9


def test_buff_without_its_companion_is_left_out():
    plain = _calc()
    r = _calc({"buffs": [{"id": "companion.cats_eye"}], "companion": {"name": "Carrier"}})
    assert r["moddedCritChance"] == plain["moddedCritChance"]
    assert r["activeBuffs"] == [] and r["inactiveBuffs"][0]["id"] == "companion.cats_eye"


def test_uptime_average_sits_between_off_and_on():
    extra = {"buffs": [{"id": "companion.cats_eye", "uptime": 0.25}], "companion": {"name": "Adarza Kavat"}}
    off, on = _calc(), _calc(extra)
    expected = 0.25 * on["dps"]["burstDps"] + 0.75 * off["dps"]["burstDps"]
    assert abs(on["averaged"]["burstDps"] - expected) < 1e-6
    # a buff that is always up needs no average
    always = {**extra, "buffs": [{"id": "companion.cats_eye", "uptime": 1}]}
    assert _calc(always)["averaged"] is None


def test_buff_armor_strip_is_reported_against_the_unstripped_figure():
    # level 1, so the armor is below the 2,700 cap and a 40% strip shows
    r = _calc({"enemyLevel": 1, "buffs": [{"id": "focus.caustic_strike", "rank": 0}]})
    assert abs(r["enemy"]["armor"] - r["armorBeforeBuffs"] * 0.6) < 1e-6


def test_sentinel_without_attack_precept_deals_no_damage():
    r = _calc({"companion": {"name": "Carrier"}, "sentinelAttackPrecept": False})
    assert r["companion"]["sustainedDps"] == 0
    assert r["combinedSustainedDps"] == r["dps"]["sustainedDps"]


def test_claws_are_hidden_from_the_weapon_list():
    names = {w["name"] for w in client.get("/api/weapons").json()}
    everything = {w["name"] for w in client.get("/api/weapons?include_companion=true").json()}
    assert "Adarza Claws" not in names and "Adarza Claws" in everything
    assert "Sweeper" in names


def test_modular_companions_have_stats():
    by_name = {c["name"]: c for c in client.get("/api/companions").json()}
    moa = by_name["Lambeo Moa"]
    assert abs(moa["health"] + moa["shield"] + moa["armor"] - 1190) < 1e-6
    assert by_name["Hec Hound"]["health"] == 450 and by_name["Hec Hound"]["statsNote"]


def test_amp_charge_trigger_and_falloff_note():
    amp = {"prism": "Raplak Prism", "scaffold": "Pencha Scaffold", "brace": ""}
    alt = _calc({"amp": amp})["amp"]["alt"]
    assert abs(alt["fireRate"] - 1 / (0.8 + 1 / 2)) < 1e-9
    shraksun = _calc({"amp": {**amp, "scaffold": "Shraksun Scaffold"}})["amp"]["alt"]
    assert any("60% at 5m" in n for n in shraksun["notes"])


def test_void_strike_adds_to_base_damage_bonus():
    plain = _calc()
    # rank 3 is 10% per 1% energy; 50% energy = +500%, added to Serration's +165%
    buffed = _calc({"buffs": [{"id": "focus.void_strike", "amount": 50}]})
    assert abs(buffed["moddedBaseDamage"] / plain["moddedBaseDamage"] - (1 + 1.65 + 5.0) / (1 + 1.65)) < 1e-6


def test_caustic_strike_strips_armor():
    assert _calc({"buffs": [{"id": "focus.caustic_strike"}]})["enemy"]["armor"] == 0


def test_companion_claws_take_claws_mods():
    bare = _calc({"companion": {"name": "Adarza Kavat"}})["companion"]
    modded = _calc({"companion": {"name": "Adarza Kavat", "mods": [{"name": "Maul"}]}})["companion"]
    assert bare["weaponName"] == "Adarza Claws"
    assert abs(modded["averageShot"] / bare["averageShot"] - 4.3) < 1e-6   # Maul: +330%


def test_sentinel_weapon_uses_its_weapon_class_mods():
    r = client.get("/api/weapons/Sweeper").json()
    assert r["modType"] == "SHOTGUN"
    assert _calc({"companion": {"name": "Carrier"}})["companion"]["weaponName"] == "Sweeper"


def test_amp_brace_adds_flat_crit_chance():
    amp = {"prism": "Raplak Prism", "scaffold": "", "brace": ""}
    plain = _calc({"amp": amp})["amp"]["primary"]
    braced = _calc({"amp": {**amp, "brace": "Certus Brace"}})["amp"]["primary"]
    assert abs(plain["critChance"] - 0.38) < 1e-9
    assert abs(braced["critChance"] - 0.58) < 1e-9


def test_unknown_buff_and_companion_are_404():
    assert client.post("/api/calculate", json={**BASE, "buffs": [{"id": "nope"}]}).status_code == 404
    assert client.post("/api/calculate", json={**BASE, "companion": {"name": "nope"}}).status_code == 404


# ----------------------------------------------------------------------------
# Conditional mods
# ----------------------------------------------------------------------------

def _lex(mods, stacks=None):
    body = {"weapon": "Lex Prime", "enemy": "Bombard|Grineer|STANDARD", "enemyLevel": 80,
            "mods": [{"name": m} for m in mods], "conditionalStacks": stacks or {}}
    r = client.post("/api/calculate", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_conditional_mod_is_off_without_stacks():
    assert _lex(["Galvanized Crosshairs"])["moddedCritChance"] == _lex([])["moddedCritChance"]


def test_galvanized_crosshairs_stacks_scale_crit_chance():
    base = _lex([])["moddedCritChance"]
    one = _lex(["Galvanized Crosshairs"], {"Galvanized Crosshairs": 1})["moddedCritChance"]
    five = _lex(["Galvanized Crosshairs"], {"Galvanized Crosshairs": 5})["moddedCritChance"]
    # one stack: +120% while aiming and +40% on kill; five stacks: +120% and 5 x 40%
    assert abs(one / base - (1 + 1.2 + 0.4)) < 1e-4
    assert abs(five / base - (1 + 1.2 + 2.0)) < 1e-4
    # stacks above the mod's maximum are clamped
    assert _lex(["Galvanized Crosshairs"], {"Galvanized Crosshairs": 99})["moddedCritChance"] == five


def test_argon_scope_toggle():
    off = _calc({"mods": [{"name": "Argon Scope"}]})
    on = _calc({"mods": [{"name": "Argon Scope"}], "conditionalStacks": {"Argon Scope": 1}})
    assert abs(on["moddedCritChance"] / off["moddedCritChance"] - 2.35) < 1e-4
    assert on["dps"]["sustainedDps"] > off["dps"]["sustainedDps"]


def test_unconditional_mods_ignore_stacks():
    plain = _calc()
    with_stacks = _calc({"conditionalStacks": {"Serration": 5, "Point Strike": 0}})
    assert plain["dps"] == with_stacks["dps"]


def test_blood_rush_scales_with_combo():
    def crit(combo):
        body = {"weapon": "Nikana Prime", "enemy": "Bombard|Grineer|STANDARD", "enemyLevel": 80,
                "mods": [{"name": "Blood Rush"}], "comboMultiplier": combo}
        return client.post("/api/calculate", json=body).json()["moddedCritChance"]
    assert abs(crit(5) / crit(1) - (1 + 0.4 * 4)) < 1e-4


def test_update_44_weapons_and_enemy_names_load():
    names = {w["name"] for w in client.get("/api/weapons").json()}
    assert {"Nunchasa", "Steflos Prime", "Aksondol", "Corufell Prime"} <= names
    r = client.post("/api/calculate", json={"weapon": "Steflos Prime", "enemy": "Nightwatch Bombard|Grineer|STANDARD"})
    assert r.status_code == 200 and r.json()["dps"]["sustainedDps"] > 0


def test_removed_and_special_mods():
    names = {m["name"]: m for m in client.get("/api/mods").json()}
    assert "Primed Serration" not in names
    assert names["Killing Blow"]["stats"] == [] and "Not applied" in names["Killing Blow"]["note"]
    assert names["Scattered Justice"]["type"] == "SHOTGUN"


# ----------------------------------------------------------------------------
# Survivability
# ----------------------------------------------------------------------------

def _surv(body):
    r = client.post("/api/survivability", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_tenno_armor_formula_and_rank_30_stats():
    r = _surv({"warframe": "Rhino", "incoming": {"amount": 1000, "type": "Slash"}})
    assert r["baseStats"] == {"health": 370, "shields": 555, "armor": 240, "energy": 150}
    assert abs(r["armorDr"] - 240 / 540) < 1e-6
    assert abs(r["damagePerHit"] - 1000 * 300 / 540) < 1e-2
    # shields: 50% damage reduction, no armor
    assert abs(r["shieldEhp"] - 555 / 0.5) < 1e-3


def test_health_and_armor_mods_scale_rank_30_base():
    r = _surv({"warframe": "Rhino", "mods": [{"name": "Vitality"}, {"name": "Steel Fiber"}]})
    assert abs(r["moddedStats"]["health"] - 740) < 0.01
    assert abs(r["moddedStats"]["armor"] - 480) < 0.01


def test_reductions_stack_multiplicatively():
    body = {"warframe": "Baruuk", "mods": [{"name": "Adaptation"}], "conditionalStacks": {"Adaptation": 9},
            "abilities": {"Desolate Hands": {"active": True, "stacks": 9}},
            "incoming": {"amount": 10000, "type": "Slash"}}
    r = _surv(body)
    armor_dr = 185 / 485
    assert [round(l["reduction"], 4) for l in r["layers"]] == [round(armor_dr, 4), 0.9, 0.9]
    assert abs(r["damagePerHit"] - 10000 * (1 - armor_dr) * 0.1 * 0.1) < 0.05
    assert abs(r["totalDr"] - (1 - (1 - armor_dr) * 0.01)) < 1e-5
    # without stacks Adaptation does nothing
    off = _surv({**body, "conditionalStacks": {}})
    assert len(off["layers"]) == 2


def test_ability_strength_scales_and_caps_reduction():
    def blessing(mods):
        r = _surv({"warframe": "Trinity", "mods": mods, "abilities": {"Blessing": {"active": True}}})
        return next(l for l in r["layers"] if l["name"] == "Blessing")["reduction"]
    assert abs(blessing([]) - 0.5) < 1e-6
    assert abs(blessing([{"name": "Intensify"}]) - 0.65) < 1e-6
    assert abs(blessing([{"name": "Blind Rage"}, {"name": "Intensify"}]) - 0.75) < 1e-6   # capped


def test_iron_skin_pool_uses_armor_and_strength():
    r = _surv({"warframe": "Rhino", "mods": [{"name": "Steel Fiber"}, {"name": "Intensify"}],
               "abilities": {"Iron Skin": {"active": True}}})
    assert abs(r["pools"][0]["points"] - (1200 + 2.5 * 480) * 1.3) < 0.5
    assert r["totalEhp"] > r["healthEhp"] + r["shieldEhp"]


def test_umbral_set_and_toxin_bypass():
    r = _surv({"warframe": "Rhino", "mods": [{"name": "Umbral Vitality"}, {"name": "Umbral Fiber"}],
               "incoming": {"amount": 100, "type": "Toxin"}})
    assert abs(r["moddedStats"]["health"] - 370 * 2.25) < 0.05
    assert r["shieldEhp"] == 0


def test_enemy_damage_scaling():
    from engine.survivability import enemy_damage_multiplier
    assert abs(enemy_damage_multiplier("Orokin", 1, 101) - (1 + 0.015 * 100 ** 1.55)) < 0.01
    # Grineer: upper curve past the transition, then the 2x attack multiplier
    assert abs(enemy_damage_multiplier("Grineer", 1, 101) - 2 * (1 + 0.0075 * 100 ** 1.55)) < 0.01
    r = _surv({"warframe": "Rhino", "incoming": {"source": "enemy", "amount": 10, "type": "Slash",
                                                 "enemy": "Heavy Gunner|Grineer|STANDARD", "enemyLevel": 100}})
    assert r["enemyDamageMultiplier"] > 1 and r["incomingPerHit"] > 10


def test_warframe_catalogue_and_mod_type_check():
    cat = client.get("/api/warframes").json()
    assert len(cat["warframes"]) == 122 and len(cat["arcanes"]) == 6
    r = client.post("/api/survivability", json={"warframe": "Rhino", "mods": [{"name": "Serration"}]})
    assert r.status_code == 422


# --- Passives -------------------------------------------------------------

def _layer(r, name):
    return next((l for l in r["layers"] if l["name"] == name), None)


def test_every_frame_has_a_passive_and_restraint_scales_with_erosion():
    cat = client.get("/api/warframes").json()["warframes"]
    assert all("passive" in w for w in cat)
    assert next(w for w in cat if w["name"] == "Baruuk Prime")["passive"]["name"] == "Restraint"
    half = _surv({"warframe": "Baruuk", "passive": {"Restraint": {"active": True, "level": 0.5}}})
    assert abs(_layer(half, "Restraint (passive)")["reduction"] - 0.25) < 1e-6
    # unconditional, but Restraint starts each mission full: no reduction until it is eroded
    assert _layer(_surv({"warframe": "Baruuk"}), "Restraint (passive)") is None
    full = _surv({"warframe": "Baruuk", "passive": {"Restraint": {"level": 1}}})
    assert abs(_layer(full, "Restraint (passive)")["reduction"] - 0.5) < 1e-6


def test_passive_flat_armor_and_health_from_energy():
    grendel = _surv({"warframe": "Grendel", "passive": {"Swallowed enemies": {"stacks": 2}}})
    assert abs(grendel["moddedStats"]["armor"] - (370 + 2 * 250)) < 0.01   # added after armor mods
    trinity = _surv({"warframe": "Trinity"})
    assert abs(trinity["moddedStats"]["health"] - (370 + 0.5 * 225)) < 0.01


def test_conditional_passive_is_off_until_switched_on():
    off = _surv({"warframe": "Mesa"})
    on = _surv({"warframe": "Mesa", "passive": {"No melee weapon": {"active": True}}})
    assert on["moddedStats"]["health"] - off["moddedStats"]["health"] == 50
    xaku = _surv({"warframe": "Xaku", "passive": {"Area damage reduction": {"active": True}}})
    assert abs(_layer(xaku, "Area damage reduction (passive)")["reduction"] - 0.25) < 1e-6


def test_adaptive_armor_and_adaptation_take_the_higher():
    body = {"warframe": "Caliban", "passive": {"Adaptive Armor": {"active": True, "stacks": 10}},
            "mods": [{"name": "Adaptation", "rank": 10}], "conditionalStacks": {"Adaptation": 2}}
    r = _surv(body)
    names = [l["name"] for l in r["layers"]]
    assert "Adaptive Armor (passive, Slash)" in names and "Adaptation (Slash)" not in names
    r = _surv({**body, "conditionalStacks": {"Adaptation": 9}})
    assert [l["name"] for l in r["layers"]][-1] == "Adaptation (Slash)"


def test_hildryn_shield_gate_and_regen_is_reported_not_counted():
    assert _surv({"warframe": "Hildryn"})["shieldGateSeconds"] == 3.5
    citrine = _surv({"warframe": "Citrine", "passive": {"Geoluminesence": {"stacks": 300}}})
    assert citrine["healthRegen"] == 25          # 5 + 0.1 x orbs, capped at 25
    plain = _surv({"warframe": "Citrine"})
    assert citrine["totalEhp"] == plain["totalEhp"]


# --- Helminth and ability buffs ---------------------------------------------

def _frame_calc(**body):
    r = client.post("/api/calculate", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _tick(r, kind):
    return next(d for d in r["dots"] if d["dotType"] == kind)["damagePerTick"]


BANE = dict(weapon="Soma Prime", enemy=GUNNER,
            mods=[{"name": "Serration", "rank": 10}, {"name": "Bane of Grineer", "rank": 5}])
INTENSIFY = [{"name": "Intensify", "rank": 5}]


def test_helminth_catalogue_and_restrictions():
    cat = client.get("/api/helminth").json()
    names = {a["ability"] for a in cat["subsumable"]}
    assert {"Roar", "Eclipse", "Xata's Whisper", "Terrify", "Shuriken"} <= names
    assert "Jade Stars" not in names          # Sirius & Orion can't be subsumed
    assert len(cat["helminthAbilities"]) == 13
    assert cat["restrictions"]["onlyReplace"]["Chroma"] == "Vex Armor"
    bad = client.post("/api/calculate", json={**BANE, "warframe": "Chroma", "helminthAbility": "Roar",
                                              "helminthSlot": 1})
    assert bad.status_code == 422 and "Vex Armor" in bad.json()["detail"]
    dup = client.post("/api/survivability", json={"warframe": "Mag", "helminthAbility": "Pull", "helminthSlot": 2})
    assert dup.status_code == 422


def test_roar_is_a_faction_bonus_counted_twice_on_dots():
    # wiki: (1 + 0.5 x 1.3 + 0.3) on hits with Intensify and Bane, squared on Slash ticks
    off = _frame_calc(**BANE)
    on = _frame_calc(**BANE, warframe="Rhino", warframeMods=INTENSIFY, abilityBuffs={"Roar": {"active": True}})
    ratio = (1 + 0.5 * 1.3 + 0.3) / 1.3
    assert abs(on["dps"]["averageShot"] / off["dps"]["averageShot"] - ratio) < 1e-5
    assert abs(_tick(on, "Slash") / _tick(off, "Slash") - ratio ** 2) < 1e-5
    assert abs(on["abilityStrength"] - 1.3) < 1e-6


def test_subsumed_roar_uses_its_reduced_value_and_replaces_the_slot():
    off = _frame_calc(**BANE)
    on = _frame_calc(**BANE, warframe="Chroma", warframeMods=INTENSIFY, helminthAbility="Roar", helminthSlot=3,
               abilityBuffs={"Roar": {"active": True}})
    assert abs(on["dps"]["averageShot"] / off["dps"]["averageShot"] - (1 + 0.3 * 1.3 + 0.3) / 1.3) < 1e-5
    ids = {e["id"]: e["variant"] for e in on["abilityEffects"]}
    assert ids == {"Roar": "infused"}         # Vex Armor (slot 3) is gone
    assert on["helminth"] == {"ability": "Roar", "slot": 3, "replaced": "Vex Armor"}


def test_solar_eclipse_is_its_own_multiplier_once_on_dots():
    off = _frame_calc(**BANE)
    on = _frame_calc(**BANE, warframe="Mirage", warframeMods=INTENSIFY, abilityBuffs={"Eclipse (Solar)": {"active": True}})
    assert abs(on["dps"]["averageShot"] / off["dps"]["averageShot"] - (1 + 2 * 1.3)) < 1e-5
    assert abs(_tick(on, "Slash") / _tick(off, "Slash") - (1 + 2 * 1.3)) < 1e-5


def test_xatas_whisper_adds_a_void_extra_hit_that_double_dips_weak_points():
    off, off_head = _frame_calc(**BANE), _frame_calc(**BANE, headshot=True)
    on = _frame_calc(**BANE, warframe="Xaku", abilityBuffs={"Xata's Whisper": {"active": True}})
    on_head = _frame_calc(**BANE, headshot=True, warframe="Xaku", abilityBuffs={"Xata's Whisper": {"active": True}})
    void = on["damage"]["perTypeInflicted"]["Void"]
    assert void > 0
    main = off["damage"]["totalInflicted"]
    assert abs(on["dps"]["averageShot"] / off["dps"]["averageShot"] - (main + void) / main) < 1e-6
    assert abs(on_head["dps"]["averageShot"] / off_head["dps"]["averageShot"] - (main + 2 * void) / main) < 1e-6


def test_parallel_elements_and_effects_the_weapon_cannot_use():
    r = _frame_calc(**BANE, warframe="Grendel", abilityBuffs={"Nourish": {"active": True}})
    assert abs(r["damage"]["perType"]["Viral"] - r["moddedBaseDamage"] * 0.75) < 1e-6
    melee_only = _frame_calc(**BANE, warframe="Valkyr", abilityBuffs={"Valkyr passive": {"active": True}})
    rage = next(e for e in melee_only["abilityEffects"] if e["id"] == "Valkyr passive")
    assert not rage["applies"] and rage["reason"] == "Melee weapons only"
    assert melee_only["dps"]["averageShot"] == _frame_calc(**BANE)["dps"]["averageShot"]


def test_unconditional_passive_buffs_default_on_and_ability_strip_adds_up():
    # on by default, but kill stacks start at zero
    assert _frame_calc(**BANE, warframe="Garuda")["dps"]["averageShot"] == _frame_calc(**BANE)["dps"]["averageShot"]
    garuda = _frame_calc(**BANE, warframe="Garuda", abilityBuffs={"Garuda passive": {"stacks": 20}})
    assert abs(garuda["dps"]["averageShot"] / _frame_calc(**BANE)["dps"]["averageShot"] - 2.0) < 1e-6
    r = _frame_calc(**BANE, warframe="Nekros", warframeMods=INTENSIFY, armorStripPct=0.2,
              abilityBuffs={"Terrify": {"active": True}})
    stripped = _frame_calc(**BANE, armorStripPct=min(1.0, 0.2 + 0.6 * 1.3))
    assert abs(r["enemy"]["armor"] - stripped["enemy"]["armor"]) < 1e-3


def test_infused_survivability_effects_use_subsumed_caps():
    r = _surv({"warframe": "Excalibur", "mods": INTENSIFY, "helminthAbility": "Eclipse", "helminthSlot": 2,
               "abilities": {"Eclipse (Lunar)": {"active": True}}})
    assert abs(_layer(r, "Eclipse (Lunar)")["reduction"] - 0.75) < 1e-6     # 0.75 x 1.3 capped at 75%
    own = _surv({"warframe": "Mirage", "mods": INTENSIFY, "abilities": {"Eclipse (Lunar)": {"active": True}}})
    assert abs(_layer(own, "Eclipse (Lunar)")["reduction"] - 0.9) < 1e-6
    para = _surv({"warframe": "Rhino", "helminthAbility": "Parasitic Armor", "helminthSlot": 1,
                  "abilities": {"Parasitic Armor": {"active": True}}})
    assert para["moddedStats"]["armor"] == 240 + 555 and para["moddedStats"]["shields"] == 0
    # Defy in Eclipse's slot: Mirage loses Lunar Eclipse
    defy = _surv({"warframe": "Mirage", "helminthAbility": "Defy", "helminthSlot": 3,
                  "abilities": {"Eclipse (Lunar)": {"active": True}, "Defy": {"active": True}}})
    assert _layer(defy, "Eclipse (Lunar)") is None and defy["moddedStats"]["armor"] == 105 + 750
