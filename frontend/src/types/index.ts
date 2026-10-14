// Mirrors backend/api/schemas.py (camelCase on the wire).

export interface WeaponSummary {
  name: string
  category: string
  modType: ModType
  imageName: string
  polarities: string[]
  totalDamage: number
  critChance: number
  critMult: number
  statusChance: number
  fireRate: number
}

export interface WeaponDetail extends WeaponSummary {
  uniqueName: string
  damage: Record<string, number>
  magSize: number
  reloadTime: number
  multishot: number
  trigger: string
  tags: string[]
  masteryReq: number
}

export interface EnemySummary {
  key: string
  name: string
  faction: string
  variantType: string
  baseLevel: number
  health: number
  armor: number
  shield: number
}

export interface ScaledEnemy {
  name: string
  faction: string
  baseLevel: number
  currentLevel: number
  health: number
  shield: number
  armor: number
  overguard: number
  armorDr: number
  armorDm: number
  isEximus: boolean
  isSteelPath: boolean
  factionModifiers: Record<string, number>
  ehp: number
}

export interface EnemyDetail extends EnemySummary {
  overguard: number
  factionModifiers: Record<string, number>
  immuneProcs: string[]
  scaled: ScaledEnemy
}

export type ModType = 'PRIMARY' | 'SECONDARY' | 'MELEE' | 'SHOTGUN' | 'CLAWS' | 'WARFRAME' | 'AURA'

export interface ModStatValue {
  stat: string
  /** For conditional stats, the value of one stack. */
  value: number
  condition: string
  maxStacks: number
}

export interface ModDetail {
  name: string
  type: ModType
  rank: number
  maxRank: number
  polarity: string
  rarity: string
  stats: ModStatValue[]
  imageName: string
  /** Fits the Exilus slot. */
  exilus: boolean
  baseDrain: number
  conditional: string
  note: string
  setBonus: string
}

export interface ModInput {
  name: string
  rank: number
}

export interface CalculateRequest {
  weapon: string
  enemy: string
  enemyLevel: number
  mods: ModInput[]
  steelPath: boolean
  eximus: boolean
  headshot: boolean
  viralStacks: number
  statusTypesOnTarget: number
  armorStripPct: number
  comboMultiplier: number
  conditionalStacks: Record<string, number>
  buffs: BuffSelection[]
  companion: { name: string; weapon: string; mods: ModInput[] } | null
  sentinelAttackPrecept: boolean
  amp: AmpBuild | null
  /** The Warframe holding the weapon; its mods set the Ability Strength of its ability buffs. */
  warframe: string
  warframeMods: ModInput[]
  extraAbilityStrength: number
  helminthAbility: string | null
  helminthSlot: number | null
  /** Ability and passive effects by effect id. A missing entry is the effect's default. */
  abilityBuffs: Record<string, Partial<AbilityState>>
}

export interface BuffSelection {
  id: string
  rank: number
  amount?: number
  /** Share of the time the buff is up, 0–1. Missing = the buff's default. */
  uptime?: number
}

export interface AmpBuild {
  prism: string
  scaffold: string
  brace: string
  arcanes: ModInput[]
}

export interface PreceptInfo {
  name: string
  effect: string
  damageEffect: string
}

export interface CompanionInfo {
  name: string
  type: string
  variant: string
  description: string
  health: number
  shield: number
  armor: number
  precepts: PreceptInfo[]
  weapons: string[]
  defaultWeapon: string
  needsAttackPrecept: boolean
  statsNote: string
  imageName: string
}

export interface AmpAttack {
  name: string
  damage: Record<string, number>
  critChance: number
  critMult: number
  statusChance: number
  fireRate: number
  multishot: number
  ammoCost: number
}

export interface AmpPart {
  name: string
  imageName: string
  series: number | null
  trigger: string
  energy: number
  rechargeDelay: number
  rechargeRate: number
  attacks: AmpAttack[]
}

export interface AmpBrace {
  name: string
  imageName: string
  series: number
  critChance: number
  statusChance: number
  energy: number
  rechargeDelay: number
  rechargeRate: number
}

export interface AmpArcane {
  name: string
  imageName: string
  stat: string
  text: string
  perRank: number[]
  maxRank: number
}

export interface AmpCatalogue {
  prisms: AmpPart[]
  scaffolds: AmpPart[]
  braces: AmpBrace[]
  arcanes: AmpArcane[]
}

export interface BuffInfo {
  id: string
  name: string
  group: string
  kind: string
  perRank: number[]
  maxRank: number
  text: string
  requires: {
    text: string
    companions: string[]
    companionTypes: string[]
    meleeWeapon: boolean
    anyCompanion: boolean
  }
  uptime: number
  uptimeNote: string
  verified: boolean
  amount: { label: string; min: number; max: number; default: number } | null
  appliesTo: string[]
}

export interface ActiveBuff {
  id: string
  name: string
  group: string
  effect: string
  verified: boolean
  uptime: number | null
  targets: string[]
}

export interface SideResult {
  label: string
  weaponName: string
  averageShot: number
  burstDps: number
  sustainedDps: number
  fireRate: number
  critChance: number
  critMult: number
  statusChance: number
  perTypeInflicted: Record<string, number>
  notes: string[]
}

export interface DotResult {
  dotType: string
  damagePerTick: number
  ticks: number
  duration: number
  totalDamage: number
  ignoresArmor: boolean
}

export interface ElementGroup {
  type: string
  sources: { element: string; source: string }[]
}

export interface CalculationResult {
  weaponName: string
  enemyName: string
  enemyLevel: number
  moddedBaseDamage: number
  moddedMultishot: number
  moddedFireRate: number
  moddedCritChance: number
  moddedCritMult: number
  moddedStatusChance: number
  moddedMagSize: number
  moddedReloadTime: number
  damage: {
    perType: Record<string, number>
    total: number
    perTypeInflicted: Record<string, number>
    totalInflicted: number
  }
  crit: {
    moddedCritChance: number
    moddedCritMult: number
    guaranteedTier: number
    nextTierChance: number
    normalShotMult: number
    critShotMult: number
    averageMult: number
  }
  dps: {
    averageShot: number
    effectiveFireRate: number
    burstDps: number
    sustainedDps: number
    shotsPerMag: number | null
    shootRatio: number
  }
  dots: DotResult[]
  enemyEhp: number
  shotsToKill: number
  timeToKill: number
  arsenalTotalDamage: number
  viralDamageBonus: number
  conditionOverloadMult: number
  elements: ElementGroup[]
  enemy: ScaledEnemy
  activeBuffs: ActiveBuff[]
  inactiveBuffs: { id: string; name: string; reason: string }[]
  averaged: { averageShot: number; burstDps: number; sustainedDps: number } | null
  armorBeforeBuffs: number
  companion: SideResult | null
  amp: { primary: SideResult; alt: SideResult | null } | null
  combinedSustainedDps: number
  /** The Warframe's Ability Strength (its mods, extra and Empower); null without a Warframe. */
  abilityStrength: number | null
  /** Every ability and passive effect the Warframe's loadout has, on or off. */
  abilityEffects: AbilityEffect[]
  helminth: HelminthInfusion | null
}

/** A Warframe ability or passive effect on the weapon, as the calculator applied it. */
export interface AbilityEffect {
  id: string
  label: string
  ability: string
  /** The Warframe it comes from, or "Helminth". */
  source: string
  variant: 'own' | 'passive' | 'infused'
  kind: string
  active: boolean
  /** After Ability Strength, caps and stacks. */
  value: number
  /** The value in words. */
  effect: string
  /** False when this weapon can't use it; `reason` says why. */
  applies: boolean
  reason: string
  condition: string
  note: string
  augment: string
  scalesWithStrength: boolean
  level: { label: string; default: number } | null
  stacks: { label: string; max: number; default: number } | null
}

export interface HelminthInfusion {
  ability: string
  slot: number
  /** The ability it replaces. */
  replaced: string
}

/** An ability the Helminth can infuse: a Warframe's subsumable one or the Helminth's own. */
export interface HelminthAbility {
  ability: string
  /** The Warframe it comes from, or "Helminth". */
  warframe: string
  description: string
  roles?: string[]
  augments?: string[]
  notes?: string
  scaling: { strength: boolean; duration: boolean; range: boolean }
  /** Calculator-relevant tags: "Damage buff", "Armor strip", "DR", "Armor", "Strength". */
  tags: string[]
  category: string
  weaponEffects: string[]
  survivabilityEffects: WarframeAbility[]
  imageName: string
}

export interface HelminthCatalogue {
  subsumable: HelminthAbility[]
  helminthAbilities: HelminthAbility[]
  restrictions: {
    /** These can only replace the named ability on the Warframes in `onlyReplace`. */
    abilities: string[]
    onlyReplace: Record<string, string>
  }
}

// ---- Survivability (damage taken) ----

export interface StatBlock {
  health: number
  shields: number
  armor: number
  energy: number
}

export interface WarframeAbility {
  kind: 'dr' | 'armor' | 'pool' | 'strength'
  name: string
  value: number
  cap: number | null
  scalesWithStrength: boolean
  stacks: { label: string; max: number; default: number } | null
  perStack: number | null
  level: { label: string; default: number } | null
  low: number | null
  mode: 'percent' | 'flat' | 'shields' | null
  armorMultiplier: number | null
  note: string
  applies: string
  imageName: string
}

/** One effect of a Warframe's passive. Same value fields as an ability effect. */
export interface PassiveEffect {
  kind: 'dr' | 'armor' | 'health' | 'resistance' | 'regen' | 'shield_gate' | 'revive' | 'note'
  name: string
  value: number | null
  cap: number | null
  stacks: { label: string; max: number; default: number } | null
  perStack: number | null
  level: { label: string; default: number } | null
  low: number | null
  mode: 'percent' | 'flat' | 'energy' | null
  /** Non-empty: the effect is a toggle that counts only when this holds. Empty: always on. */
  condition: string
  note: string
}

export interface WarframePassive {
  /** The passive's name where the wiki gives one; often empty. */
  name: string
  /** The in-game passive text. */
  description: string
  effects: PassiveEffect[]
}

export interface WarframeInfo {
  name: string
  rank0: StatBlock
  rank30: StatBlock
  statsNote: string
  abilities: WarframeAbility[]
  /** All four abilities in slot order, including ones with no effect on damage taken. */
  allAbilities: { name: string; imageName: string }[]
  passive: WarframePassive
  special: string[]
  imageName: string
  polarities: string[]
  auraPolarity: string
}

export interface WarframeArcane {
  name: string
  imageName: string
  stat: string
  perRank: number[]
  maxRank: number
  note: string
}

export interface WarframeCatalogue {
  warframes: WarframeInfo[]
  arcanes: WarframeArcane[]
}

export interface AbilityState {
  active: boolean
  stacks?: number
  level?: number
}

export interface SurvivabilityRequest {
  warframe: string
  mods: ModInput[]
  conditionalStacks: Record<string, number>
  abilities: Record<string, AbilityState>
  passive: Record<string, AbilityState>
  arcanes: ModInput[]
  incoming: {
    source: 'custom' | 'enemy'
    amount: number
    type: string
    hitsPerSecond: number
    enemy: string
    enemyLevel: number
    steelPath: boolean
  }
  extraAbilityStrength: number
  helminthAbility: string | null
  helminthSlot: number | null
}

export interface DrLayer {
  name: string
  reduction: number
  damageAfter: number
  cumulative: number
  note: string
}

export interface SurvivabilityResult {
  warframe: string
  baseStats: StatBlock
  moddedStats: StatBlock
  abilityStrength: number
  abilityDuration: number
  abilityEfficiency: number
  abilityRange: number
  armorDr: number
  totalDr: number
  shieldDr: number
  layers: DrLayer[]
  incomingPerHit: number
  damageType: string
  damagePerHit: number
  shieldDamagePerHit: number
  hitsPerSecond: number
  healthEhp: number | null
  shieldEhp: number | null
  poolEhp: number | null
  totalEhp: number | null
  pools: { name: string; points: number; ehp: number | null }[]
  timeToKill: number | null
  shieldGateSeconds: number
  enemyDamageMultiplier: number
  enemyName: string
  /** Health per second from the passive. Shown only; not part of effective health. */
  healthRegen: number
  /** Each passive effect: whether it counts, and its value (DR fraction, armor, health, health/s or seconds). */
  passiveEffects: { name: string; kind: PassiveEffect['kind']; active: boolean; value: number | null }[]
  helminth: HelminthInfusion | null
  notes: string[]
}

/** An arcane for a weapon arcane slot. Shown in the loadout only; not calculated. */
export interface WeaponArcane {
  name: string
  type: ModType
  maxRank: number
  text: string
  imageName: string
}
