"""Singleton data loaders shared by all routes. Loaded once at import time."""

import json
from pathlib import Path

from engine.ability_buffs import AbilityBuffCatalogue
from engine.amps import AmpLoader
from engine.buffs import BuffCatalogue
from engine.companions import CompanionLoader
from engine.damage import DamageCalculator
from engine.enemies import EnemyScaler
from engine.modding import ModResolver
from engine.survivability import SurvivabilityCalculator
from engine.weapons import WeaponLoader

DATA = Path(__file__).resolve().parent.parent / "data" / "processed"

weapon_loader = WeaponLoader("data/processed/weapons.json")
enemy_scaler = EnemyScaler("data/processed/enemies.json")
mod_resolver = ModResolver("data/processed/core_mods.json")
calculator = DamageCalculator(mod_resolver)

# Companion weapons: beast claws are extra weapons; Robotic weapons are already
# loaded and only need to be told which class of mods they take.
with open(DATA / "companion_weapons.json", encoding="utf-8") as f:
    _companion_weapons = json.load(f)
weapon_loader.add(_companion_weapons["weapons"])
for _name, _mod_type in _companion_weapons["modTypes"].items():
    if _name in weapon_loader.weapons:
        weapon_loader.weapons[_name].mod_type_override = _mod_type

with open(DATA / "companion_mods.json", encoding="utf-8") as f:
    mod_resolver.mods.update(json.load(f)["mods"])

# Artwork file names and slot polarities (display only; built by scripts/build_image_map.py)
with open(DATA / "image_map.json", encoding="utf-8") as f:
    image_map = json.load(f)
for _name, _weapon in weapon_loader.weapons.items():
    _weapon.image_name = image_map["weapons"].get(_name, "")
    _weapon.polarities = image_map["slotPolarities"]["weapons"].get(_name, [])

# Display only: arcanes for the weapon arcane slots (the engine does not apply them)
with open(DATA / "weapon_arcanes.json", encoding="utf-8") as f:
    weapon_arcanes = json.load(f)["arcanes"]

companion_loader = CompanionLoader("data/processed/companions.json")
amp_loader = AmpLoader("data/processed/amps.json")
buff_catalogue = BuffCatalogue("data/processed/buffs.json")
survivability = SurvivabilityCalculator("data/processed/warframe_survivability.json")
# Warframe ability / passive buffs and Helminth infusions (scripts/build_ability_buffs.py, build_helminth_data.py)
ability_buffs = AbilityBuffCatalogue("data/processed/ability_buffs.json", "data/processed/helminth.json",
                                     ability_names=survivability.ability_names)
