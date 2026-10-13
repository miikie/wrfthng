# TODO

Updated 2026-10-14. Items closed in the last pass are listed at the bottom so the reasoning isn't lost.

## Open

### Needs an in-game check

- Whether Warframe damage auras and squad buffs reach companion weapons.
- Whether Killer's Rush, Temporal Shot and Shade's Ambush are flat points or multipliers (Ambush is in
  the app, marked "not confirmed").
- Whether companions gain stats with rank (data shows one value per companion).
- Quantization on amp and companion-weapon damage (the app quantizes both like any weapon).
- Galvanized Aptitude / Shot / Savvy: the engine applies their per-status bonus as a multiplier raised to
  the number of status types. The game text reads as an additive bonus. Left alone because the engine is
  marked as verified; worth one test.

### Survivability calculator (added 2026-10-14)

- Enemy weapon damage is in no data source, so "an enemy" as the damage source needs a base damage typed in.
- Not checked against the game: the Umbral set multipliers (x1.25 / x1.75), ability armor bonuses being
  additive with armor mods, and whether ability damage reduction applies to Overguard pools.
- Not modelled: shield gating and shield recharge in the time to die, healing, Revenant's Mesmer Skin
  charges, evasion (Baruuk's Elude, Xaku), invisibility, revive passives. They appear as notes.
- Abilities are curated for 30 base frames (51 with Primes). Frames without an entry may still have a minor
  effect that was missed; the scan looked for damage reduction, redirection, armor and Overguard values.
- Valkyr's Warcry tripling under Hysteria and Citrine's Preserving Shell decay are not modelled.
- None of the 13 damage buffs change Warframe survivability, so none are wired in. Unairu's Stone Skin
  (+200 armor) is not in the buff list; use an arcane slot or note it.
- Only 8 Warframe mod slots (no separate aura or exilus slot); auras go in a normal slot.
- Clicking through the new tab is untested; it was checked by screenshot from a share link.

### Visual work: open items (2026-10-14)

- Untested by hand: everything that needs a click or a drag. The layout was checked by screenshot at 1680
  and 820 px from share links; the mod browser as a sheet on narrow screens, the grid pickers, dragging,
  and the rejected-drop flash were not exercised.
- Touch: no pointer-event dragging. Touch users tap a slot (it gets a gold outline and becomes the
  browser's target), then tap a mod. Native drag still works with a mouse.
- Arcane slots open a grid dialog; the docked browser does not switch to arcanes.
- Weapon arcanes are display only (46 listed); the engine has no weapon arcanes.
- Adaptation's stacks slider stays on its mod card (it is a mod, not an ability).
- Dragging between a main slot and the Exilus slot is not supported; special slots fill from the browser.
- Main slots accept Exilus mods (as in the game); only auras are kept out of them.
- No artwork for the 17 beast claws or the Mote Amp. Capacity bar assumes innate polarities are on the
  first slots and ignores Forma.
- Fixed here: Agility Drift's 12% damage reduction was being applied all the time; it is now a
  "while airborne" toggle like Aviator.

### Waiting on the game export

- The export (`warframe-public-export-plus`) is still at 43.5.4. Update 44 weapons and frames come from
  WFCD through `scripts/add_supplements.py`; their `tags` are copied from a similar weapon. Re-run
  `process_export_data.py` and then `add_supplements.py` when the export publishes 44.
- Update 44 enemies: no source lists them.
- The six Update 44 mods (Brood's Oversurge, Cold Front, Gaseous Quake, Gastroparesis, Infernum, Sonic
  Siphon) are warframe augments, so they are not in `core_mods.json`.

### Not modelled

- Mods flagged `"special": true` in `core_mods.json` (35): heavy attacks, slams, finishers, Tennokai,
  initial combo, on-death explosions, flat "final" status chance. Listed in the mod picker with a note.
- Claws mods that convert damage types (the Conditioning and elemental Claws mods): the stat bonus is
  applied, the conversion is not.
- Maiming Strike (flat crit on slide attacks) and weak-point damage mods.
- Choosing MOA / Hound parts. Each uses one representative set; see `statsNote` in `companions.json`.
- Companion survivability mods and link mods.
- Focus school membership: any Focus buff can be turned on.
- Amp burst delay: burst prisms use the engine's default 0.05 s between burst shots.
- Sentient damage adaptation; shield gating; Warframe abilities (data is in `data/raw/wiki_abilities`).

### Data gaps

- Nemes Ranger, Nemes Scout and Tomb Guardian were added from the WFCD codex list with base level
  assumed to be 1 and no weak points. Nightwatch Bombard is the export's "Nightwatch Gunner" under its
  codex name.
- Wildlife (Kuaka, Condroc, Virmink, ...) and Infested hives from the codex list are left out on purpose:
  they are not damage-test targets.
- Not published anywhere found: per-hit multipliers of the Drifter's Duviri melee combos; which focus
  node unlocks which; the gilded Hound stat table.
- 214 uncurated weapon mods remain (run `python scripts/list_uncurated_mods.py`). None of their text
  mentions a damage stat that isn't already covered: ammo, recoil, range, stealth, parkour.
- `build_core_mods.py --write` has not been re-run since conditional tagging; check its report first.

### Not tested

- Clicking through the UI. The visual pass used screenshots of builds loaded from share links at 1024,
  1440 and 1920 px (compare mode): layout, dark theme and console errors. Drag-to-reorder, the mod
  picker dialog, saving and deleting builds, and keyboard navigation were not exercised.

## Closed 2026-10-14

- **Conditional mods:** 31 mods carry `condition` / `max_stacks`; the engine applies them by active stacks.
  Blood Rush and Weeping Wounds now scale with combo instead of adding their full value at 1x.
- **Fake Primed mods:** all ten (Primed Serration, Hornet Strike, Point Strike, Vital Sense, Organ Shatter,
  Stormbringer, Hellfire, Deep Freeze, Molten Impact, Shocking Touch) are absent from both the game
  export and the wiki's mod list. Removed.
- **Cascading Flux:** not a mod. Flux Overdrive (Flux Rifle augment) added as a special entry.
- **Uncurated mods:** 61 added (26 with stats, 35 special).
- **Armor strip in the enemy panel, buff prerequisites, buff uptime averaging, Sentinel attack precept
  toggle, MOA / Hound stats, amp charge trigger and falloff notes, beast claws hidden from weapon search.**
- **Ability data:** all 122 frames re-scraped from wiki.warframe.com (the maintained wiki) instead of the
  stale fandom wiki. No ability is hand-transcribed any more and every augment has per-rank values.
  191 abilities changed value. Necramechs have no passive. See
  `data/raw/ability_verification_report.json` (44 energy-cost differences between export and wiki are
  listed there as notes; the export value stays in `energy_cost`).
