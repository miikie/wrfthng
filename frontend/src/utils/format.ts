/** Compact number: 1,234 below ten thousand, then 12.3K / 4.56M / 7.8B. */
export function num(n: number, decimals = 1): string {
  if (!Number.isFinite(n)) return '∞'
  const abs = Math.abs(n)
  if (abs >= 1e12) return `${(n / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (abs >= 1e4) return `${(n / 1e3).toFixed(1)}K`
  return n.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: abs >= 100 ? Math.min(decimals, 1) : decimals,
  })
}

export function pct(fraction: number, decimals = 1): string {
  return `${(fraction * 100).toFixed(decimals).replace(/\.0+$/, '')}%`
}

export function mult(n: number, decimals = 2): string {
  return `${n.toFixed(decimals).replace(/\.?0+$/, '')}×`
}

export function seconds(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '—'
  if (n < 0.1) return '< 0.1 s'
  if (n < 60) return `${n.toFixed(n < 10 ? 2 : 1)} s`
  if (n < 3600) {
    // round first, so 119.6 s reads "2 min 0 s" and never "1 min 60 s"
    const total = Math.round(n)
    return `${Math.floor(total / 60)} min ${total % 60} s`
  }
  if (n < 86400) return `${(n / 3600).toFixed(1)} h`
  return `${num(n / 86400)} days`
}

const STAT_LABELS: Record<string, string> = {
  DAMAGE: 'Damage',
  MULTISHOT: 'Multishot',
  CRIT_CHANCE: 'Critical chance',
  CRIT_DAMAGE: 'Critical damage',
  STATUS_CHANCE: 'Status chance',
  STATUS_DURATION: 'Status duration',
  FIRE_RATE: 'Fire rate',
  RELOAD_SPEED: 'Reload speed',
  MAG_SIZE: 'Magazine',
  IMPACT: 'Impact',
  PUNCTURE: 'Puncture',
  SLASH: 'Slash',
  HEAT: 'Heat',
  COLD: 'Cold',
  ELECTRICITY: 'Electricity',
  TOXIN: 'Toxin',
  FACTION_GRINEER: 'Damage to Grineer',
  FACTION_CORPUS: 'Damage to Corpus',
  FACTION_INFESTED: 'Damage to Infested',
  FACTION_CORRUPTED: 'Damage to Corrupted',
  FACTION_OROKIN: 'Damage to Orokin',
  FACTION_MURMUR: 'Damage to The Murmur',
  FACTION_SENTIENT: 'Damage to Sentients',
  COMBO_DURATION: 'Combo duration',
  CONDITION_OVERLOAD: 'Damage per status type',
  GALV_STATUS_STACKS: 'Damage per status type',
  ACCURACY: 'Accuracy',
  HEALTH: 'Health',
  SHIELDS: 'Shield capacity',
  ARMOR: 'Armor',
  ARMOR_FLAT: 'Armor',
  DAMAGE_REDUCTION: 'Damage reduction',
  ABILITY_STRENGTH: 'Ability Strength',
  ABILITY_DURATION: 'Ability Duration',
  ABILITY_RANGE: 'Ability Range',
  ABILITY_EFFICIENCY: 'Ability Efficiency',
  RESIST_TOXIN: 'Toxin resistance',
  RESIST_HEAT: 'Heat resistance',
  RESIST_COLD: 'Cold resistance',
  RESIST_ELECTRICITY: 'Electricity resistance',
  RESIST_RADIATION: 'Radiation resistance',
  RESIST_PHYSICAL: 'Physical damage resistance',
  PUNCH_THROUGH: 'Punch through',
}

export function statLabel(stat: string): string {
  return STAT_LABELS[stat] ?? stat.toLowerCase().replace(/_/g, ' ')
}

/** "+165% Damage", "+12s Combo duration" */
export function statText(stat: string, value: number): string {
  const sign = value >= 0 ? '+' : '−'
  const abs = Math.abs(value)
  if (stat === 'COMBO_DURATION') return `${sign}${num(abs)}s ${statLabel(stat)}`
  if (stat === 'PUNCH_THROUGH') return `${sign}${num(abs)}m ${statLabel(stat)}`
  if (stat === 'ARMOR_FLAT') return `${sign}${num(abs, 0)} ${statLabel(stat)}`
  return `${sign}${pct(abs)} ${statLabel(stat)}`
}

const CATEGORY_LABELS: Record<string, string> = {
  LongGuns: 'Primary',
  Pistols: 'Secondary',
  Melee: 'Melee',
  SpaceGuns: 'Archgun',
  SpaceMelee: 'Archmelee',
  SentinelWeapons: 'Companion',
  SpecialItems: 'Exalted',
  DrifterMelee: 'Drifter',
  OperatorAmps: 'Amp',
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category
}

export function titleCase(s: string): string {
  return s.charAt(0) + s.slice(1).toLowerCase()
}
