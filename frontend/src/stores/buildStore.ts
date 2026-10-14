import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  AbilityState, AmpBuild, BuffSelection, CalculateRequest, ModInput, SurvivabilityRequest,
} from '../types'

export const SLOT_COUNT = 8
export type BuildIndex = 0 | 1
/** Which set of mod slots an action touches: the weapon's or the companion weapon's. */
export type Rack = 'mods' | 'exilusMods' | 'companionMods' | 'warframeMods' | 'auraMods' | 'warframeExilusMods'

/** Which mods a slot takes. */
export type SlotKind = 'main' | 'exilus' | 'aura'

/** Slots per rack: eight main slots, one for each special slot. */
export const RACK_SIZE: Record<Rack, number> = {
  mods: SLOT_COUNT, companionMods: SLOT_COUNT, warframeMods: SLOT_COUNT,
  exilusMods: 1, auraMods: 1, warframeExilusMods: 1,
}

export interface Build {
  weapon: string
  enemyKey: string
  enemyLevel: number
  steelPath: boolean
  eximus: boolean
  headshot: boolean
  viralStacks: number
  statusTypes: number
  armorStripPct: number // 0–1
  comboMultiplier: number
  mods: (ModInput | null)[] // always SLOT_COUNT long; order is slot order
  /** Active stacks of each equipped conditional mod, by mod name. Missing = off. */
  conditionalStacks: Record<string, number>
  companion: string // '' = none
  companionWeapon: string // '' = the companion's default weapon
  companionMods: (ModInput | null)[]
  /** Whether the Sentinel has an attack precept equipped; without one it never fires. */
  sentinelAttack: boolean
  buffs: BuffSelection[]
  amp: AmpBuild | null
  // Damage taken
  warframe: string
  warframeMods: (ModInput | null)[]
  survival: SurvivalSettings
  // Special slots: one mod each
  exilusMods: (ModInput | null)[]
  auraMods: (ModInput | null)[]
  warframeExilusMods: (ModInput | null)[]
  /** Weapon arcane slots. Display only: the calculator has no weapon arcanes. */
  weaponArcanes: string[]
  /** The Helminth ability infused into the Warframe and the slot (1-4) it replaces. Both tabs use it. */
  helminth: Infusion | null
  /** Damage dealt tab: the Warframe's ability and passive buffs by effect id. Missing = the effect's default. */
  abilityBuffs: Record<string, Partial<AbilityState>>
}

export interface Infusion {
  ability: string
  slot: number
}

export interface SurvivalSettings {
  abilities: Record<string, AbilityState>
  /** Passive effects by name: toggles for conditional ones, stacks / level for any. */
  passive: Record<string, AbilityState>
  arcanes: ModInput[]
  /** 'custom' = the amount is one hit; 'enemy' = the amount is the build's enemy's base damage per hit. */
  source: 'custom' | 'enemy'
  amount: number
  type: string
  hitsPerSecond: number
  /** Ability Strength from outside the mods, as a fraction (0.3 = +30%). */
  extraStrength: number
}

export const DEFAULT_SURVIVAL: SurvivalSettings = {
  abilities: {}, passive: {}, arcanes: [], source: 'custom', amount: 1000, type: 'Slash', hitsPerSecond: 2, extraStrength: 0,
}

export interface Preset {
  name: string
  build: Build
  builtIn?: boolean
}

const ENEMY_FIELDS = [
  'enemyKey', 'enemyLevel', 'steelPath', 'eximus', 'viralStacks', 'statusTypes', 'armorStripPct',
] as const

function slots(mods: [string, number][]): (ModInput | null)[] {
  const filled: (ModInput | null)[] = mods.map(([name, rank]) => ({ name, rank }))
  while (filled.length < SLOT_COUNT) filled.push(null)
  return filled
}

export const DEFAULT_BUILD: Build = {
  weapon: 'Soma Prime',
  enemyKey: 'Heavy Gunner|Grineer|STANDARD',
  enemyLevel: 100,
  steelPath: false,
  eximus: false,
  headshot: false,
  viralStacks: 0,
  statusTypes: 0,
  armorStripPct: 0,
  comboMultiplier: 1,
  mods: slots([['Serration', 10], ['Split Chamber', 5], ['Point Strike', 5], ['Vital Sense', 5]]),
  conditionalStacks: {},
  companion: '',
  companionWeapon: '',
  companionMods: slots([]),
  sentinelAttack: true,
  buffs: [],
  amp: null,
  warframe: 'Rhino',
  warframeMods: slots([['Vitality', 10], ['Steel Fiber', 10]]),
  survival: DEFAULT_SURVIVAL,
  exilusMods: [null],
  auraMods: [null],
  warframeExilusMods: [null],
  weaponArcanes: [],
  helminth: null,
  abilityBuffs: {},
}

export const DEFAULT_AMP: AmpBuild = {
  prism: 'Raplak Prism', scaffold: 'Propa Scaffold', brace: 'Certus Brace', arcanes: [],
}

export const BUILT_IN_PRESETS: Preset[] = [
  {
    name: 'Soma Prime, viral crit',
    builtIn: true,
    build: {
      ...DEFAULT_BUILD,
      steelPath: true,
      viralStacks: 10,
      mods: slots([
        ['Serration', 10], ['Split Chamber', 5], ['Point Strike', 5], ['Vital Sense', 5],
        ['Primed Cryo Rounds', 10], ['Infected Clip', 5], ['Malignant Force', 3], ['Rime Rounds', 3],
      ]),
    },
  },
  {
    name: 'Rubico Prime, Eidolon radiation',
    builtIn: true,
    build: {
      ...DEFAULT_BUILD,
      weapon: 'Rubico Prime',
      enemyKey: 'Eidolon Teralyst|Sentient|STANDARD',
      enemyLevel: 50,
      headshot: true,
      mods: slots([
        ['Serration', 10], ['Split Chamber', 5], ['Point Strike', 5], ['Vital Sense', 5],
        ['Hellfire', 5], ['Stormbringer', 5], ['High Voltage', 3], ['Thermite Rounds', 3],
      ]),
    },
  },
  {
    name: 'Nikana Prime, Condition Overload',
    builtIn: true,
    build: {
      ...DEFAULT_BUILD,
      weapon: 'Nikana Prime',
      enemyKey: 'Corrupted Heavy Gunner|Orokin|STANDARD',
      enemyLevel: 120,
      statusTypes: 3,
      viralStacks: 5,
      mods: slots([
        ['Primed Pressure Point', 10], ['Condition Overload', 0], ['Blood Rush', 5],
        ['Organ Shatter', 5], ['Primed Fury', 10], ['Weeping Wounds', 5],
        ['North Wind', 5], ['Fever Strike', 5],
      ]),
    },
  },
  {
    name: 'Lex Prime, corrosive',
    builtIn: true,
    build: {
      ...DEFAULT_BUILD,
      weapon: 'Lex Prime',
      enemyKey: 'Bombard|Grineer|STANDARD',
      enemyLevel: 80,
      mods: slots([
        ['Hornet Strike', 10], ['Barrel Diffusion', 5], ['Lethal Torrent', 5],
        ['Primed Pistol Gambit', 10], ['Primed Target Cracker', 10],
        ['Convulsion', 5], ['Pathogen Rounds', 5],
      ]),
    },
  },
]

const RECENT_LIMIT = 6

function pushRecent(list: string[], item: string): string[] {
  return [item, ...list.filter((x) => x !== item)].slice(0, RECENT_LIMIT)
}

interface BuildState {
  builds: [Build, Build]
  compare: boolean
  sharedEnemy: boolean
  /** Which calculator is showing: damage dealt by a weapon, or damage taken by a Warframe. */
  view: 'dealt' | 'taken'
  presets: Preset[]
  recentWeapons: string[]
  recentEnemies: string[]

  update: (i: BuildIndex, patch: Partial<Build>) => void
  setWeapon: (i: BuildIndex, name: string, clearMods: boolean) => void
  setEnemy: (i: BuildIndex, key: string) => void
  addMod: (i: BuildIndex, slot: number, name: string, rank: number, rack?: Rack) => void
  removeMod: (i: BuildIndex, slot: number, rack?: Rack) => void
  setModRank: (i: BuildIndex, slot: number, rank: number, rack?: Rack) => void
  reorderMods: (i: BuildIndex, from: number, to: number, rack?: Rack) => void
  clearMods: (i: BuildIndex, rack?: Rack) => void
  setStacks: (i: BuildIndex, mod: string, stacks: number) => void
  setCompanion: (i: BuildIndex, name: string) => void
  setCompanionWeapon: (i: BuildIndex, weapon: string, clearMods: boolean) => void
  toggleBuff: (i: BuildIndex, id: string, rank: number, amount?: number) => void
  updateBuff: (i: BuildIndex, id: string, patch: Partial<BuffSelection>) => void
  replaceBuild: (i: BuildIndex, build: Build) => void
  copyBuild: (from: BuildIndex, to: BuildIndex) => void
  setCompare: (on: boolean) => void
  setView: (view: 'dealt' | 'taken') => void
  setWarframe: (i: BuildIndex, name: string) => void
  updateSurvival: (i: BuildIndex, patch: Partial<SurvivalSettings>) => void
  setAbility: (i: BuildIndex, name: string, patch: Partial<AbilityState>) => void
  setPassive: (i: BuildIndex, name: string, patch: Partial<AbilityState>) => void
  setHelminth: (i: BuildIndex, infusion: Infusion | null) => void
  setAbilityBuff: (i: BuildIndex, id: string, patch: Partial<AbilityState>) => void
  setSharedEnemy: (on: boolean) => void
  savePreset: (name: string, i: BuildIndex) => void
  deletePreset: (name: string) => void
}

export const useBuildStore = create<BuildState>()(
  persist(
    (set) => {
      const patchBuild = (i: BuildIndex, fn: (b: Build) => Partial<Build>) =>
        set((s) => {
          const builds = [...s.builds] as [Build, Build]
          builds[i] = { ...builds[i], ...fn(builds[i]) }
          return { builds }
        })

      const patchMods = (i: BuildIndex, rack: Rack, fn: (mods: (ModInput | null)[]) => void) =>
        patchBuild(i, (b) => {
          const mods = [...b[rack]]
          fn(mods)
          return { [rack]: mods }
        })

      return {
        builds: [DEFAULT_BUILD, DEFAULT_BUILD],
        compare: false,
        sharedEnemy: true,
        view: 'dealt',
        presets: [],
        recentWeapons: [],
        recentEnemies: [],

        update: (i, patch) => patchBuild(i, () => patch),

        setWeapon: (i, name, clearMods) => {
          patchBuild(i, (b) => ({
            weapon: name,
            comboMultiplier: 1,
            mods: clearMods ? slots([]) : b.mods,
            exilusMods: clearMods ? [null] : b.exilusMods,
            weaponArcanes: clearMods ? [] : b.weaponArcanes,
          }))
          set((s) => ({ recentWeapons: pushRecent(s.recentWeapons, name) }))
        },

        setEnemy: (i, key) => {
          patchBuild(i, () => ({ enemyKey: key }))
          set((s) => ({ recentEnemies: pushRecent(s.recentEnemies, key) }))
        },

        addMod: (i, slot, name, rank, rack = 'mods') =>
          patchBuild(i, (b) => {
            // one copy per item: not in another slot or in the item's other racks
            const elsewhere = rackGroup(rack).some((r) =>
              b[r].some((m, idx) => m?.name === name && !(r === rack && idx === slot)))
            if (elsewhere) return {}
            const mods = [...b[rack]]
            mods[slot] = { name, rank }
            return { [rack]: mods }
          }),

        removeMod: (i, slot, rack = 'mods') => patchMods(i, rack, (mods) => { mods[slot] = null }),

        setModRank: (i, slot, rank, rack = 'mods') =>
          patchMods(i, rack, (mods) => {
            const mod = mods[slot]
            if (mod) mods[slot] = { ...mod, rank }
          }),

        // Dropping onto another slot swaps the two, so empty slots stay where they are.
        reorderMods: (i, from, to, rack = 'mods') =>
          patchMods(i, rack, (mods) => {
            if (from === to) return
            ;[mods[from], mods[to]] = [mods[to], mods[from]]
          }),

        clearMods: (i, rack = 'mods') => patchBuild(i, (b) => ({ [rack]: b[rack].map(() => null) })),

        setStacks: (i, mod, stacks) =>
          patchBuild(i, (b) => ({ conditionalStacks: { ...b.conditionalStacks, [mod]: stacks } })),

        // A different companion has different weapons, so its weapon and mods reset.
        setCompanion: (i, name) =>
          patchBuild(i, () => ({ companion: name, companionWeapon: '', companionMods: slots([]) })),

        setCompanionWeapon: (i, weapon, clearMods) =>
          patchBuild(i, (b) => ({
            companionWeapon: weapon,
            companionMods: clearMods ? slots([]) : b.companionMods,
          })),

        toggleBuff: (i, id, rank, amount) =>
          patchBuild(i, (b) => ({
            buffs: b.buffs.some((x) => x.id === id)
              ? b.buffs.filter((x) => x.id !== id)
              : [...b.buffs, { id, rank, ...(amount === undefined ? {} : { amount }) }],
          })),

        updateBuff: (i, id, patch) =>
          patchBuild(i, (b) => ({
            buffs: b.buffs.map((x) => (x.id === id ? { ...x, ...patch } : x)),
          })),

        replaceBuild: (i, build) => patchBuild(i, () => normalizeBuild(build)),

        copyBuild: (from, to) =>
          set((s) => {
            const builds = [...s.builds] as [Build, Build]
            builds[to] = normalizeBuild(structuredClone(builds[from]))
            return { builds }
          }),

        setCompare: (on) => set({ compare: on }),
        setView: (view) => set({ view }),

        // Abilities, the passive and the infusion belong to one Warframe, so they reset with it.
        setWarframe: (i, name) =>
          patchBuild(i, (b) => ({
            warframe: name, helminth: null, abilityBuffs: {},
            survival: { ...b.survival, abilities: {}, passive: {} },
          })),

        setHelminth: (i, infusion) => patchBuild(i, () => ({ helminth: infusion })),

        setAbilityBuff: (i, id, patch) =>
          patchBuild(i, (b) => ({ abilityBuffs: { ...b.abilityBuffs, [id]: { ...b.abilityBuffs[id], ...patch } } })),

        updateSurvival: (i, patch) =>
          patchBuild(i, (b) => ({ survival: { ...b.survival, ...patch } })),

        setAbility: (i, name, patch) =>
          patchBuild(i, (b) => ({
            survival: {
              ...b.survival,
              abilities: {
                ...b.survival.abilities,
                [name]: { ...(b.survival.abilities[name] ?? { active: false }), ...patch },
              },
            },
          })),
        setPassive: (i, name, patch) =>
          patchBuild(i, (b) => ({
            survival: {
              ...b.survival,
              passive: {
                ...b.survival.passive,
                [name]: { ...(b.survival.passive[name] ?? { active: false }), ...patch },
              },
            },
          })),
        setSharedEnemy: (on) => set({ sharedEnemy: on }),

        savePreset: (name, i) =>
          set((s) => ({
            presets: [
              ...s.presets.filter((p) => p.name !== name),
              { name, build: s.builds[i] },
            ],
          })),

        deletePreset: (name) =>
          set((s) => ({ presets: s.presets.filter((p) => p.name !== name) })),
      }
    },
    {
      name: 'simulacrum',
      version: 5,
      // Version 1 builds predate companions, amps and buffs.
      migrate: (persisted) => {
        const s = persisted as Partial<BuildState>
        return {
          ...s,
          builds: (s.builds ?? [DEFAULT_BUILD, DEFAULT_BUILD]).map(normalizeBuild) as [Build, Build],
          presets: (s.presets ?? []).map((p) => ({ ...p, build: normalizeBuild(p.build) })),
        }
      },
    },
  ),
)

/** Fill in anything missing from a build that came from a URL or old save. */
export function normalizeBuild(partial: Partial<Build>): Build {
  const pad = (list: (ModInput | null)[] | undefined, size = SLOT_COUNT) => {
    const mods = (list ?? []).slice(0, size)
    while (mods.length < size) mods.push(null)
    return mods
  }
  return {
    ...DEFAULT_BUILD,
    ...partial,
    mods: pad(partial.mods),
    companionMods: pad(partial.companionMods),
    warframeMods: partial.warframeMods ? pad(partial.warframeMods) : DEFAULT_BUILD.warframeMods,
    survival: { ...DEFAULT_SURVIVAL, ...partial.survival },
    exilusMods: pad(partial.exilusMods, 1),
    auraMods: pad(partial.auraMods, 1),
    warframeExilusMods: pad(partial.warframeExilusMods, 1),
    weaponArcanes: partial.weaponArcanes ?? [],
    conditionalStacks: partial.conditionalStacks ?? {},
    buffs: partial.buffs ?? [],
    amp: partial.amp ?? null,
    helminth: partial.helminth ?? null,
    abilityBuffs: partial.abilityBuffs ?? {},
  }
}

const warframeRack = (b: Build) =>
  [...b.warframeMods, ...b.auraMods, ...b.warframeExilusMods].filter((m): m is ModInput => m !== null)

/** Build B borrows Build A's enemy while comparing against a shared enemy. */
export function effectiveBuild(
  s: Pick<BuildState, 'builds' | 'compare' | 'sharedEnemy'>, i: BuildIndex,
): Build {
  const build = s.builds[i]
  if (i === 0 || !s.compare || !s.sharedEnemy) return build
  const shared = Object.fromEntries(ENEMY_FIELDS.map((f) => [f, s.builds[0][f]]))
  return { ...build, ...shared }
}

export function usesSharedEnemy(
  s: Pick<BuildState, 'compare' | 'sharedEnemy'>, i: BuildIndex,
): boolean {
  return i === 1 && s.compare && s.sharedEnemy
}

export function toRequest(b: Build): CalculateRequest {
  return {
    weapon: b.weapon,
    enemy: b.enemyKey,
    enemyLevel: b.enemyLevel,
    // the Exilus mod goes last so it never changes how elements combine
    mods: [...b.mods, ...b.exilusMods].filter((m): m is ModInput => m !== null),
    steelPath: b.steelPath,
    eximus: b.eximus,
    headshot: b.headshot,
    viralStacks: b.viralStacks,
    statusTypesOnTarget: b.statusTypes,
    armorStripPct: b.armorStripPct,
    comboMultiplier: b.comboMultiplier,
    conditionalStacks: b.conditionalStacks,
    buffs: b.buffs,
    companion: b.companion
      ? {
          name: b.companion,
          weapon: b.companionWeapon,
          mods: b.companionMods.filter((m): m is ModInput => m !== null),
        }
      : null,
    sentinelAttackPrecept: b.sentinelAttack,
    amp: b.amp,
    // the Damage taken tab's Warframe: its mods set the strength of its ability buffs
    warframe: b.warframe,
    warframeMods: warframeRack(b),
    extraAbilityStrength: b.survival.extraStrength,
    helminthAbility: b.helminth?.ability ?? null,
    helminthSlot: b.helminth?.slot ?? null,
    abilityBuffs: b.abilityBuffs,
  }
}

export function toSurvivabilityRequest(b: Build): SurvivabilityRequest {
  return {
    warframe: b.warframe,
    mods: warframeRack(b),
    conditionalStacks: b.conditionalStacks,
    abilities: b.survival.abilities,
    passive: b.survival.passive,
    arcanes: b.survival.arcanes,
    incoming: {
      source: b.survival.source,
      amount: b.survival.amount,
      type: b.survival.type,
      hitsPerSecond: b.survival.hitsPerSecond,
      enemy: b.enemyKey,
      enemyLevel: b.enemyLevel,
      steelPath: b.steelPath,
    },
    extraAbilityStrength: b.survival.extraStrength,
    helminthAbility: b.helminth?.ability ?? null,
    helminthSlot: b.helminth?.slot ?? null,
  }
}

/** The slot the mod browser is filling. Not saved: it is where the user is working right now. */
export interface PickerTarget {
  index: BuildIndex
  rack: Rack
  slot: number
}

interface PickerState {
  target: PickerTarget | null
  /** On narrow screens the browser is a sheet that opens and closes; on wide ones it is always docked. */
  open: boolean
  select: (target: PickerTarget) => void
  show: (target?: PickerTarget) => void
  close: () => void
}

export const usePickerStore = create<PickerState>()((set) => ({
  target: null,
  open: false,
  select: (target) => set({ target, open: true }),
  show: (target) => set((s) => ({ target: target ?? s.target, open: true })),
  close: () => set({ open: false }),
}))

export const slotKindOf = (rack: Rack): SlotKind =>
  rack === 'auraMods' ? 'aura' : rack === 'exilusMods' || rack === 'warframeExilusMods' ? 'exilus' : 'main'

/** Racks that share one item, so a mod can only be equipped in one of them. */
export const rackGroup = (rack: Rack): Rack[] =>
  rack === 'companionMods'
    ? ['companionMods']
    : rack === 'mods' || rack === 'exilusMods'
      ? ['mods', 'exilusMods']
      : ['warframeMods', 'auraMods', 'warframeExilusMods']

/** Whether a mod may go in a slot of this kind. */
export function fitsSlot(kind: SlotKind, mod: { type: string; exilus: boolean }): boolean {
  if (kind === 'aura') return mod.type === 'AURA'
  if (kind === 'exilus') return mod.exilus
  return mod.type !== 'AURA'
}
