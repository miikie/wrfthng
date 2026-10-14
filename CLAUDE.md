# Warframe Damage Calculator

## What This Is

A game-accurate Warframe damage calculator implementing the full Damage 3.0 pipeline (post-Update 36.0, June 2024). Uses IEEE 754 binary32 (float32) arithmetic to match the game's internal calculations exactly, including damage quantization to nearest 1/32 of modded base damage.

## Project Structure

```
warframe_calc/
├── CLAUDE.md                          # This file
├── portable.md                        # Web app conversion plan (phases 0-6 are built)
├── package.json                       # Root scripts: dev, dev:backend, dev:frontend, build, test
├── backend/
│   ├── main.py                        # FastAPI app; mounts the routers below
│   ├── requirements.txt
│   ├── simulacrum.py                  # OLD CLI, kept as reference only
│   ├── engine/                        # Core calculation engine (Python)
│   │   ├── constants.py               # Game constants, f32() helper, faction modifiers, elemental combos
│   │   ├── damage.py                  # Core damage calculator - 20-step pipeline
│   │   ├── enemies.py                 # Enemy stat scaling with per-faction dual curves + smoothstep
│   │   ├── modding.py                 # Mod resolution, elemental combination engine
│   │   └── weapons.py                 # Weapon data loading and stat properties
│   ├── api/
│   │   ├── deps.py                    # Singleton loaders (weapons, enemies, mods, calculator)
│   │   ├── schemas.py                 # Pydantic models; snake_case in Python, camelCase on the wire
│   │   ├── routes_weapons.py          # GET /api/weapons, /api/weapons/{name}
│   │   ├── routes_enemies.py          # GET /api/enemies, /api/enemies/{key}, /api/enemies/{key}/scaled
│   │   ├── routes_mods.py             # GET /api/mods, /api/mods/{name}?rank=
│   │   └── routes_calculate.py        # POST /api/calculate, /api/compare; element trace for the UI
│   ├── tests/test_api.py              # API + elemental combination tests (npm test)
│   └── data/processed/                # Clean JSON databases (from game exports)
│       ├── weapons.json               # 827 weapons (183 are parts with no damage; hidden from lists)
│       ├── enemies.json               # 1543 enemies, keyed "Name|Faction|VARIANT"
│       ├── core_mods.json             # 108 manually curated damage-relevant mods with per-rank increments
│       └── ...                        # mods, warframes, arcanes, starchart_nodes, summary
├── frontend/                          # React + Vite + TypeScript + Tailwind v4
│   └── src/
│       ├── main.tsx                   # Entry; loads a build from the URL and keeps the URL in sync
│       ├── App.tsx                    # Header (readout, compare toggle, copy link) + build editor(s)
│       ├── api/                       # client.ts (fetch wrappers), queries.ts (TanStack Query hooks)
│       ├── stores/buildStore.ts       # Zustand: two builds, compare mode, presets, recents (localStorage)
│       ├── components/                # WeaponPanel, EnemyPanel, ModRack, ModPicker, Results, PresetMenu, ...
│       ├── types/                     # Mirrors backend/api/schemas.py
│       └── utils/                     # format, damageTypes (colours), url (share links), hooks
├── data/formulas/                     # Reference documentation (pipeline, scaling, type modifiers)
└── scripts/process_export_data.py     # Processes raw exports into backend/data/processed
```

## Running

```
npm run dev     # backend on :8000 and frontend on :5173 (Vite proxies /api)
npm test        # backend tests
npm run build   # type-check and build the frontend
```

All calculation happens in the Python engine. The frontend only displays what the API returns.

## Architecture: The Calculation Engine

The engine is 5 Python modules. ALL calculations use `f32()` (struct pack/unpack to IEEE 754 binary32) to match the game exactly. The user does NOT program — Claude Code is the developer.

### engine/constants.py
- `f32(x)` — IEEE 754 binary32 conversion function
- `FACTION_MODIFIERS` — 15 factions with Vulnerable (1.5x) / Resistant (0.5x) mappings
- `ELEMENTAL_COMBINATIONS` — Heat+Cold=Blast, Electricity+Toxin=Corrosive, etc.
- `DOT_COEFFICIENTS` — Slash=0.35, Heat/Electricity/Toxin/Gas=0.5
- Armor: hard cap 2700, min 200, DR formula `DM = 1 - 0.9 * sqrt(AR / 2700)`
- Steel Path: +100 level, 2.5x shields (NO armor multiplier)
- Viral: +100% at 1 stack, +25% per additional, max +325% at 10 stacks
- Corrosive: ~26% per stack multiplicative, 80% max strip at 10 stacks
- Heat: 50% max armor strip at 10 stacks

### engine/enemies.py — Enemy Scaling
- `ScalingCurve(coefficient, exponent)` — `f(x) = 1 + C * q^E`
- `DualCurve(f1, f2, lower_bound, upper_bound)` — Two curves with smoothstep interpolation
- Per-faction health curves (Grineer, Corpus, Infested, Orokin, Techrot, Sentient, etc.)
- Per-faction shield curves
- Universal armor curve and overguard curve
- `eval_dual_curve()` — Exact wiki formula: `f1(x) + (f2(x) - f1(x)) * smoothstep(t)` (NOT rearranged — float32 order matters)
- `eximus_base_health()` — Piecewise function, 6 breakpoints (levels 15/25/35/50/100)
- `EnemyScaler.scale_enemy(key, level, is_eximus, is_steel_path, armor_strip_pct, viral_stacks)` → `ScaledEnemy`
- Overguard uses `level - 1` not `level - baseLevel`

### engine/modding.py — Mod Resolution & Elemental Combination
- `ModResolver` loads `core_mods.json`, resolves mods at any rank: `value = increment * (rank + 1)`
- `ModdedStats` aggregates all bonuses (damage, multishot, crit, status, elemental, faction, etc.)
- `build_modded_stats(mods)` — aggregates mod stats, preserves elemental order
- `combine_elements(innate_elements, mod_elements, base_damage)` — Warframe's rules:
  1. Mod elementals calculated as % of total base damage
  2. Elements combine left-to-right in mod slot order
  3. Innate weapon elements combine LAST (rightmost)
  4. Innate combined elements don't re-split

### engine/weapons.py — Weapon Data
- `WeaponData` dataclass with properties: `is_melee`, `is_shotgun`, `mod_type`, `base_damage`, damage distributions
- `WeaponLoader` loads `weapons.json`, provides `find(query)` for partial name match

### engine/damage.py — The 20-Step Damage Pipeline
1. Resolve mods → ModdedStats
2. Modded base damage = base × (1 + damage_bonus + extra)
3. Physical mods applied BEFORE quantization
4. Elemental damage from mods (% of modded base)
5. Quantize to nearest 1/32 of modded base
6. Multishot
7. Crit chance/mult modding
8. Faction damage modifier (from mods like Bane of Grineer)
9. Inflicted damage per type (armor DM × faction type modifier)
10. Viral bonus (multiplicative on health damage)
11. Condition Overload (multiplicative per unique status type)
12. Per-shot damage
13. Headshot (default 2.0x weak point)
14. Average shot (crit average × multishot)
15. Fire rate / effective fire rate (handles charge/burst triggers)
16. Burst DPS
17. Sustained DPS (with reload: `shoot_ratio = shots / (FR × reload + shots)`)
18. Status chance
19. DoTs — NOT quantized, uses f32, ignores elemental/physical bonuses, faction applies TWICE, Slash ignores armor (True damage)
20. Arsenal total + kill estimates (EHP / sustained DPS)

## Data Sources

- **Weapon/enemy/warframe/arcane data**: Processed from `warframe-public-export-plus` (GitHub: calamity-inc/warframe-public-export-plus), a community mirror of DE's public export API
- **Mod per-rank values**: NOT available in any public API. The 108 mods in `core_mods.json` were manually curated with `increment` values. Formula: `value = increment × (rank + 1)`
- **Formulas**: From the Warframe wiki, verified against in-game results

### Data Schema: weapons.json
```json
{
  "Soma Prime": {
    "name": "Soma Prime", "uniqueName": "/Lotus/...", "category": "LongGuns",
    "damage": {"Impact": 1.2, "Puncture": 4.8, "Slash": 6.0},
    "totalDamage": 12.0, "critChance": 0.30, "critMult": 3.0,
    "statusChance": 0.10, "fireRate": 15.0, "magSize": 200,
    "reloadTime": 3.0, "multishot": 1, "trigger": "AUTO",
    "tags": ["LMG", "ASSAULT"], "masteryReq": 7
  }
}
```

### Data Schema: enemies.json
```json
{
  "heavy_gunner": {
    "name": "Heavy Gunner", "faction": "Grineer", "baseLevel": 1,
    "health": 300, "shield": 0, "armor": 500, "overguard": 0,
    "weakPoints": [{"name": "Head", "multiplier": 2.0}]
  }
}
```

### Data Schema: core_mods.json
```json
{
  "mods": {
    "Serration": {
      "type": "PRIMARY", "stat": "DAMAGE", "increment": 0.15,
      "maxRank": 10, "polarity": "V"
    },
    "Split Chamber": {
      "type": "PRIMARY",
      "stats": [{"stat": "MULTISHOT", "increment": 0.15, "maxRank": 5}],
      "polarity": "V"
    }
  }
}
```

Stats use uppercase keys: `DAMAGE`, `MULTISHOT`, `CRIT_CHANCE`, `CRIT_DAMAGE`, `STATUS_CHANCE`, `STATUS_DURATION`, `FIRE_RATE`, `RELOAD_SPEED`, `MAG_SIZE`, `IMPACT`, `PUNCTURE`, `SLASH`, `HEAT`, `COLD`, `ELECTRICITY`, `TOXIN`, `FACTION_GRINEER`, `CONDITION_OVERLOAD`, etc.

## Critical Implementation Details

### Float32 Arithmetic
The game uses float32 for nearly all calculations. The `f32()` function in constants.py converts float64 to float32 precision. This MUST be used for all intermediate results in scaling curves and damage calculations. The smoothstep formula specifically must NOT be rearranged — `f1 + (f2 - f1) * s` gives different float32 results than `f1 * (1-s) + f2 * s`.

### Quantization
Damage values are quantized to nearest 1/32 of modded base damage. This happens AFTER physical and elemental mods are applied. DoT damage is NOT quantized.

### DoT Special Rules
- DoT damage ignores elemental and physical damage bonuses from mods
- Faction bonus applies TWICE (once in base, once in tick calculation)  
- Slash DoT deals True/Cinematic damage (bypasses armor entirely)
- DoT uses float32 but is NOT quantized

### Elemental Combination Order
Elements combine left-to-right in mod slot order. Innate weapon elements are added LAST (rightmost). Innate combined elements (like a weapon with innate Viral) don't re-split. This order matters enormously for builds.

## Known Gaps / Future Work

- **Warframe abilities**: Only names/energy costs are in the export data. Actual mechanics (damage buffs, armor strip abilities, etc.) would need wiki scraping for 86+ warframes
- **Arcane integration**: Data exists in arcanes.json but not wired into the calculator
- **Mod database expansion**: Only 108 core damage-relevant mods are curated; 1372 total mods exist
- **Riven mods**: Explicitly excluded (too variable, user-specific)
- **Complex weapon mechanics**: Burst alt-fire, area damage falloff, beam weapons, etc.
- **Companion damage**: Not implemented
- **Shield gating**: Not modeled in kill-time estimates

## Companions, Amps and Buffs (in the app)

- `scripts/build_app_data.py` converts the research data into `backend/data/processed/`
  `companions.json`, `companion_weapons.json` (beast claws), `companion_mods.json` (claws mods, type `CLAWS`),
  `amps.json` and `buffs.json`. `api/deps.py` merges the claws weapons and mods into the normal loaders.
- `engine/damage.py` — `Buffs` dataclass, passed to `calculate(buffs=...)`: base damage add, physical add, flat crit
  points, crit floor, flat final crit multiplier, crit per combo, fire rate add, final multiplier (twice on DoTs).
- `engine/buffs.py` — catalogue of 13 selectable buffs (Focus, companion precepts, bond mods, sets) -> `Buffs`
  per target (weapon / companion / amp) plus armor strip.
- `engine/amps.py` — prism + scaffold + brace -> fire modes; energy pool recharge stands in for reload.
- `engine/companions.py` — companion catalogue. Companion damage = its weapon through the normal pipeline.
- API: `GET /api/companions`, `/api/amps`, `/api/buffs`; `POST /api/calculate` takes `buffs`, `companion`, `amp`
  and returns `activeBuffs`, `companion`, `amp`, `combinedSustainedDps`.
- Frontend: `CompanionPanel`, `AmpPanel`, `BuffsPanel`; `ModRack` takes `companionWeapon` for the second rack.
- MOAs and Hounds use one representative part set (see `statsNote`). Beast claws are hidden from `GET /api/weapons`
  unless `include_companion=true`.
- Not modelled: choosing MOA/Hound parts, companion survivability mods, focus node trees beyond the listed buffs,
  Focus school membership.

## Survivability (Damage Taken)

The second calculator: a Warframe as the target. Header tabs switch between "Damage dealt" and "Damage taken".

- `engine/survivability.py` — rules, all from wiki.warframe.com:
  - Warframe armor: `DR = armor / (armor + 300)`, health only, no cap. This is NOT the enemy armor formula.
  - Warframe shields take 50% less damage and ignore armor; Toxin bypasses them.
  - Stats: `rank 30 base x (1 + sum of mod %) + flat bonuses`. Umbral mods: x1.25 with two, x1.75 with three.
  - Reductions stack multiplicatively. Ability values scale with Ability Strength up to each ability's cap.
  - Overguard / ability rings are separate pools (Iron Skin: `(1200 + 2.5 x armor) x strength`).
  - Enemy damage: `1 + 0.015 x (level - base)^1.55`; Corpus/Grineer/Techrot use a two-curve version and a 2x
    attack multiplier, Infested 3x. Steel Path adds 100 levels.
- `data/processed/warframe_survivability.json` — rank 0 / rank 30 stats for 122 frames, abilities of kind
  `dr` / `armor` / `pool`, special notes, six arcanes. Built by `scripts/build_warframe_data.py`, which also adds
  60 Warframe and aura mods to `core_mods.json` (types `WARFRAME`, `AURA`).
- API: `GET /api/warframes`, `POST /api/survivability` (`api/routes_survivability.py`).
- Frontend: `components/Survivability.tsx`; `ModRack` with `warframe` for the Warframe's mods. Build fields
  `warframe`, `warframeMods`, `survival`; store field `view`.
- Adaptation and Health Conversion are conditional mods: their stacks slider is on the mod card.
- Enemy weapon damage is not in the game data: with an enemy as the source, the user enters its base damage.

## Artwork and Visual Components

- `scripts/build_image_map.py` -> `data/processed/image_map.json`: image file name per mod, Warframe, ability,
  weapon, arcane, companion and amp part, plus innate slot polarities. Source: WFCD warframe-items JSON
  (`data/raw/wfcd_*.json`). Images load in the browser from `https://cdn.warframestat.us/img/<name>`.
- The API adds `imageName` (and `polarities`, `baseDrain` where relevant) to weapons, mods, Warframes,
  abilities, arcanes, companions and amp parts. Nothing in the calculation reads them.
- Frontend: `utils/images.ts`, `components/ItemImage.tsx` (`ItemImage` with initials fallback, `ItemButton`,
  `GridPicker` dialog), `components/ModCard.tsx`, `components/ModPicker.tsx` (docked browser panel).
- Drag and drop is native HTML5: slot to slot swaps, browser card to slot adds, drag off the rack removes.
- The capacity bar is display only and assumes innate polarities sit on the first slots.

## Slots and Page Layout

- Racks: `mods` (8) + `exilusMods` (1) for the weapon; `warframeMods` (8) + `auraMods` (1) + `warframeExilusMods` (1)
  for the Warframe; `companionMods` (8). `RACK_SIZE`, `slotKindOf`, `rackGroup`, `fitsSlot` in `stores/buildStore.ts`.
  The Exilus mod is appended after the eight main mods in the request, so it never changes element order.
- `scripts/build_slot_data.py` flags Exilus-compatible mods (`"exilus": true`, 106 mods; the utility ones are
  `special`, no stats) and writes `weapon_arcanes.json` (46, display only: `weaponArcanes` on the build is never
  sent to the calculator).
- `usePickerStore` holds the slot the mod browser is filling. `DockedPicker` (`components/ModPicker.tsx`) is one
  browser for the whole page: a sticky right column at `xl` and wider, a full-screen sheet below that. It filters
  by slot kind; a dragged mod that doesn't fit a slot is refused.
- Page: `[builds | mod browser]`, results full width underneath (in compare mode each build keeps its own results).
  Inside a build: item panels in a left column, rack and the rest in the centre (container queries, `@5xl`).
- `POST /api/survivability` also returns `abilityDuration`, `abilityEfficiency` (25%-175%), `abilityRange`
  for display. `GET /api/warframes` returns `allAbilities` (four names + icons) for the ability bar.

## Data Build Order

Each step is safe to re-run. Later steps patch what earlier ones write.

```
python scripts/process_export_data.py          # game export -> weapons, enemies, warframes, mods, arcanes
python scripts/add_supplements.py              # Update 44 items + codex enemy names the export lacks
python scripts/build_core_mods.py --write      # general weapon mods with damage stats -> core_mods.json
python scripts/extra_core_mods.py              # weapon-specific / special mods; removes entries that aren't real mods
python scripts/tag_conditional_mods.py         # suffix stats -> {"condition": ..., "max_stacks": ...}
python scripts/build_warframe_data.py          # Warframe/aura mods + warframe_survivability.json
python scripts/build_passives.py               # passives -> warframe_survivability.json (after build_warframe_data)
python scripts/build_slot_data.py              # Exilus flags + weapon_arcanes.json (after build_warframe_data)
python scripts/build_operator_companion_data.py  # wiki -> data/raw/{operator,amps,companions,companion_mods}
python scripts/build_app_data.py               # data/raw -> companions, amps, buffs for the app
python scripts/build_image_map.py              # artwork names + slot polarities (run last of the app data)
python scripts/build_ability_buffs.py          # ability / passive weapon buffs -> ability_buffs.json
python scripts/build_helminth_data.py          # Helminth table + rules -> helminth.json (after the two above)
python scripts/scrape_wiki_abilities.py        # wiki.warframe.com -> data/raw/wiki_abilities (slow; cached)
```

The backend reads its JSON once at startup: restart `npm run dev` after rebuilding data.

`build_core_mods.py --write` has not been re-run since the conditional tagging was added. It compares existing
entries against game text and may rewrite tagged stats: run it without `--write` first and read the report.

## Conditional Mods

- A stat in `core_mods.json` may carry `"condition"` (`while_aiming`, `on_kill`, `on_hit`, `per_combo`, ...) and
  `"max_stacks"`. `ModResolver.resolve(name, rank, stacks, combo_multiplier)` multiplies a conditional stat by its
  active stacks (clamped to `max_stacks`); `per_combo` stats scale with `combo_multiplier - 1` instead.
- `POST /api/calculate` takes `conditionalStacks: {modName: n}`; a conditional mod with no entry is inactive.
- Mods with `"special": true` have no stats and are documented only (`mechanic`).

## Buff Rules

- Each buff has `requires` (companion names / types, melee weapon). Buffs whose requirement the loadout doesn't
  meet are skipped and returned in `inactiveBuffs`.
- Each buff has an `uptime` (overridable per request). When any active buff is up less than all the time, the
  response adds `averaged`: weapon DPS averaged over every on/off combination, weighted by uptime.
- Armor-strip buffs raise the armor strip; `armorBeforeBuffs` is the enemy's armor without them.

## Raw Research Data

Everything under `data/raw/` is source material. The app reads only what `build_app_data.py` converts.

- `wiki_abilities/` — one file per warframe (122) with ability values. Built by `scripts/scrape_wiki_abilities.py`.
- `operator/` — five `focus_*.json` (15 current nodes each, older Focus 2.0 nodes marked `legacy`), Operator and Drifter stats.
- `amps/` — prisms, scaffolds, braces, amp/operator arcanes, `amp_mechanics.json`.
- `companions/` — one file per companion (41), MOA and Hound parts, `companion_weapons.json`, `companion_base_scaling.json`.
- `companion_mods/` — 173 companion mods with per-rank values, precepts, link mods, set bonuses.
- `interactivity_map.json` — every cross-system damage interaction, with pipeline step and a confidence label.
- `engine_changes.md` — what the engine and UI need in order to use the above.
- The last five are built by `scripts/build_operator_companion_data.py` (uses `scripts/lua_data.py` to read the
  wiki's Lua data modules). Source is wiki.warframe.com, cached in `data/raw/wiki_cache_current/`.
- `todo.md` (repo root) lists work that is on hold.

## Web App Status

Phases 0-6 of `portable.md` are built. Phase 7 (stretch goals) is not started.

Known data limitation: no primary weapon in weapons.json carries a SHOTGUN tag, so `WeaponData.mod_type`
reports primary shotguns (Tigris, Hek) as PRIMARY and secondary shotguns (Bronco) as SHOTGUN. The mod picker
defaults to that type but lets the user switch mod class.

## Passives, Helminth and Ability Buffs

- Every number comes from a wiki page via a regex in the build script; a pattern that stops matching stops the
  script (no silent stale values). Pages are cached in `data/raw/wiki_cache_current/`.
- `scripts/build_passives.py` adds `passive: {name, description, effects}` to each frame in
  `warframe_survivability.json`. Effect kinds: `dr`, `armor` (flat after mods), `health` (`flat` / `energy`),
  `resistance` (Caliban; the higher of it and Adaptation applies), `regen` (shown, not EHP), `shield_gate`,
  `revive` / `note` (text). An effect with a `condition` is a toggle; the rest are always on. Meters and stacks
  default to the mission-start state (Restraint 0%, Garuda 0 kills).
- `scripts/build_ability_buffs.py` -> `ability_buffs.json`: 42 effects (own abilities, passives, Helminth) with
  `value`, `subsumed` (number, "same" or null = not infusable), `subsumedCap`. Weapon kinds and where they apply:
  `base_damage_add` (with Serration), `faction_add` (with Bane; twice on DoTs: Roar), `damage_mult` /
  `enemy_vulnerability` / `hit_multiplier` (one product, once on hits and DoTs), `elemental_add` (beside the
  weapon's elements, never combining), `extra_hit` (share of the hit incl. faction, faction again, weak points
  twice), `crit_chance_add`, `crit_chance_flat`, `fire_rate_add`, `armor_strip`, `slash_dot_mult`.
- `scripts/build_helminth_data.py` -> `helminth.json`: 65 subsumable abilities (keyed by ability), 13 Helminth
  abilities, `restrictions` (Eclipse / Roar / Xata's Whisper can only replace the named ability on 9 frames).
  Survivability effects of infused abilities are copied from the donor with the wiki's subsumed caps.
- `engine/ability_buffs.py`: `AbilityBuffCatalogue.loadout()` = own ability effects (minus the replaced slot) +
  passive + infused (subsumed values); `resolve()` -> `Buffs`, armor strip, strength (incl. Empower).
  `check_infusion()` enforces the placement rule and blocks a second copy of an ability the frame has.
- `engine/survivability.py`: `calculate(passive=..., replaced_slot=..., infused=...)`; Parasitic Armor (armor
  mode `shields`) turns max shields into armor and disables shields.
- API: `GET /api/helminth`, `GET /api/ability-buffs`. `POST /api/calculate` takes `warframe`, `warframeMods`,
  `extraAbilityStrength`, `helminthAbility`, `helminthSlot`, `abilityBuffs` and returns `abilityStrength`,
  `abilityEffects` (every effect of the loadout, on or off, with `applies` / `reason`), `helminth`.
  `POST /api/survivability` takes `passive`, `helminthAbility`, `helminthSlot`.
- Cross-tab: the build's `warframe`, Warframe mods, `survival.extraStrength` and `helminth` are shared. The damage
  route runs the survivability engine on the Warframe's mods to get Ability Strength (and shields for Styanax).
- Frontend: `components/Helminth.tsx` (`HelminthAbilityBar` with a badge per slot, `HelminthPicker`,
  `infusionBlocked` mirrors the server rule), `components/AbilityBuffs.tsx` (Damage dealt panel). Build fields
  `helminth`, `abilityBuffs` (share link keys `hm`, `ab`); passive state in `survival.passive`.

