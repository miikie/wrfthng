# Engine and UI changes for Operators, Amps and Companions

Written 2026-10-14 from the data under `data/raw/operator`, `amps`, `companions`, `companion_mods`
and `data/raw/interactivity_map.json`. Nothing here is implemented yet.

Step numbers refer to the 20-step pipeline in `CLAUDE.md`.

## The short version

- **Amps and robotic weapons are ordinary weapons.** They can go through the existing pipeline once
  they are loaded as `WeaponData`. No second pipeline is needed.
- **Most cross-system effects are one of five kinds of external buff.** The engine needs one new
  input (a list of buffs) rather than a special case per ability.
- **Three things are genuinely new math:** flat crit-chance points added after mods (Cat's Eye),
  a flat final crit multiplier (Tenacious Bond), and energy-pool "reloads" for amps.

## New concept: external buffs

Add a `Buff` record and let `DamageCalculator.calculate()` take `buffs: list[Buff]`.

| Buff kind | Applied at | Examples |
|---|---|---|
| `base_damage_add` | step 2, summed with Serration-type bonuses | Void Strike, Ambush, Deadly Decrees |
| `physical_add` / `elemental_add` | steps 3 / 4 | Phoenix Talons, Anabolic Pollination, Zid-An Uskos |
| `crit_chance_flat` | step 7, added after `base x (1 + mods)` | Cat's Eye (+0.60), Arcane Avenger-style |
| `crit_chance_floor` | step 7, `max(cc, floor)` | Smeeta Charm (2.0) |
| `crit_mult_final_flat` | step 7 / 14, `1 + tier x (cm - 1 + x)` | Tenacious Bond (1.2) |
| `crit_per_combo` | step 7, summed with Blood Rush | Gladiator set (0.10 per piece) |
| `fire_rate_add` | step 15 | Reinforced Bond |
| `status_chance_add` | step 18 | Zid-An Asheir |
| `final_multiplier` | step 12, and again on DoTs (step 19) | Mecha Empowered (x2.5; x6.25 on DoTs) |
| `armor_strip_pct` / `shield_strip` | enemy scaling, before step 9 | Caustic Strike, Sharpened Claws, Vicious Bond, Magnetic Flare |
| `status_on_target` | steps 10 / 11 | Viral Quills, Coolant Leak |

Each buff carries `source`, `value`, `uptime` (0-1) and `conditions`, so results can show both
"buff active" and time-averaged DPS. Cat's Eye uptime is 10 / (10 + 20).

## New modules

### `engine/operator.py`
- Load `data/raw/operator/focus_*.json`; ignore nodes with `status: "legacy"`.
- `FocusLoadout(school, {node: rank}, unbound_waybounds)` -> list of `Buff` using each node's
  `per_rank_values` and `damage_effect`.
- Operator stats: `health = 350 x (1 + enduring_tides) + magus_vigor`,
  `armor = 75 x (1 + enduring_tides) + magus_husk + stone_skin`, `DR = armor / (armor + 300)`.
- Void Strike: `bonus = per_rank_pct x energy_fraction_consumed x 100`.

### `engine/amps.py`
- Load `data/raw/amps/prisms.json`, `scaffolds.json`, `braces.json`.
- `assemble(prism, scaffold, brace)` -> two `WeaponData` objects (primary fire, alt fire).
  Brace crit/status are **flat additions** to base chance; energy and recharge changes alter the pool.
- No mod slots. Two arcane slots from `virtuous_arcanes.json`, turned into `Buff`s.
- Operator damage bonuses (Void Strike, Phoenix Talons, Unairu Wisp, Virtuos Fury, Eternal
  Eradicate, Amp Spike, Lethal Levitation) are **one additive group** at step 2.
- Contamination Wave is a separate enemy-side multiplier.
- Sustained DPS: `shots = pool / ammo_cost`, then `recharge_delay + pool / recharge_rate` in place
  of reload time (step 17).

### `engine/companions.py`
- Load `data/raw/companions/**`.
- Stats: `base x (1 + flat mod)` or `base + link x warframe_stat` (never both for one stat).
  MOA: 350 base per stat, adjusted by core and gyro percentages.
- Weapon damage: build `WeaponData` from `companion_weapons.json` (robotic weapon or beast claws)
  and call the existing calculator with that weapon's mods.
- Sentinels deal weapon damage only if an attack precept is equipped.
- Precepts -> `Buff`s for the owner (Cat's Eye, Charm, Viral Quills, Sharpened Claws, ...).
- Hunter Synergy / Mecha Overdrive need the primary weapon's *modded* crit / status chance, so the
  companion calculation runs after the primary weapon's step 7 / 18.

## Changes to existing modules

### `engine/damage.py`
- Accept `buffs` and apply them at the steps in the table above.
- Step 7: `cc = base x (1 + mods + per_combo x (combo - 1)) + flat_points`, then apply floor.
- Step 14: crit-tier averaging must accept a flat final multiplier and the Vigilante
  "raise one tier" chance.
- Step 12 / 19: `final_multiplier` buffs apply once to hits and twice to DoTs (same pattern the
  faction bonus already follows).
- Return companion DPS and amp DPS as separate lines plus a combined total.

### `engine/constants.py`
- Void: neutral to all factions; x1.5 against Overguard and Zariman void manifestations.
- New stat keys for companion mods: `HEALTH`, `SHIELD`, `ARMOR`, `LINK_HEALTH`, `LINK_SHIELD`,
  `LINK_ARMOR`. Claws mods reuse `DAMAGE`, `CRIT_CHANCE`, `CRIT_DAMAGE`, elementals.
- `MOD_TYPES`: add `CLAWS`, `COMPANION`, `ROBOTIC`, `BEAST`, plus per-companion precept classes.
- Weapon class map for robotic weapons: Rifle/Sniper -> PRIMARY, Shotgun -> SHOTGUN,
  Pistol -> SECONDARY, Melee/Glaive -> MELEE.

### `engine/modding.py`
- Companion mods are a **separate pool** (`companion_mods/*.json`); robotic weapon mods are **not**,
  they use `core_mods.json`.
- Set bonuses: count pieces across Warframe, weapons, companion and companion weapon, then emit a
  `Buff` from `companion_mods/set_mods.json`.
- The elemental-combination rule needs one exception: Momentous Bond's element does not combine
  with the weapon's elements.

### `engine/enemies.py`
- Sentient damage adaptation (and its reset by Void damage) is not modelled at all today. Add it
  only if Sentient targets matter; it is a per-damage-type resistance that grows as damage is dealt.
- Accept `shield_strip` alongside the existing `armor_strip_pct`.

### `backend/data/processed/weapons.json`
- 17 beast claws entries are missing (see `companion_weapons.json` -> `missing_from_app`).
- Amp parts are in the game export with zero stats; real stats are only in `data/raw/amps/`.

## Web app UI (not built)

- **Companion selector:** type -> companion. No level control (stats do not appear to scale with rank).
- **Companion weapon:** weapon picker limited by companion type, then the existing mod rack filtered
  to that weapon's class.
- **Companion mod loadout:** precepts in priority order (order matters), link/flat stat mods, bond mods.
- **MOA / Hound builder:** model, core, gyro/stabilizer, bracket.
- **Focus selector:** school -> nodes with rank sliders -> waybounds unbound from other schools.
- **Amp builder:** prism + scaffold + brace, two arcane slots, shown as primary and alt fire.
- **Results:** separate rows for weapon, companion and amp DPS, plus a combined total.
- **Active buffs panel:** every `Buff` with source, value, uptime and a toggle, since most are conditional.

## Before building: things to test in game

These are marked `unverified` in `interactivity_map.json`.

1. Whether Warframe damage auras and squad buffs reach companion weapons.
2. Whether Killer's Rush, Temporal Shot and Ambush are flat points or multipliers.
3. Whether companions gain stats with rank.
4. Quantization on amp and companion-weapon damage.
