// Display colour per damage type. Physical types stay in metal tones so the
// elemental colours carry the signal.
export const DAMAGE_COLORS: Record<string, string> = {
  Impact: '#8b96a5',
  Puncture: '#c3ccd6',
  Slash: '#d8b25a',
  Heat: '#e8553d',
  Cold: '#63d2e6',
  Electricity: '#5b8cf0',
  Toxin: '#5fbf5a',
  Viral: '#2fb5a0',
  Corrosive: '#b4d335',
  Blast: '#f0913a',
  Radiation: '#ecd63c',
  Magnetic: '#a06be0',
  Gas: '#3f8f4d',
  Void: '#f1f4f7',
  Tau: '#e7a6c8',
  True: '#f1f4f7',
  Finisher: '#f1f4f7',
}

export const DAMAGE_ORDER = [
  'Impact', 'Puncture', 'Slash',
  'Heat', 'Cold', 'Electricity', 'Toxin',
  'Blast', 'Corrosive', 'Gas', 'Magnetic', 'Radiation', 'Viral',
  'Void', 'Tau', 'True', 'Finisher',
]

export function damageColor(type: string): string {
  return DAMAGE_COLORS[type] ?? '#8b96a5'
}

export function sortDamage<T>(entries: [string, T][]): [string, T][] {
  const rank = (t: string) => {
    const i = DAMAGE_ORDER.indexOf(t)
    return i === -1 ? DAMAGE_ORDER.length : i
  }
  return [...entries].sort((a, b) => rank(a[0]) - rank(b[0]))
}

/** The element a mod adds, if any (drives the card's colour and the element chain). */
export function modElement(stats: { stat: string }[]): string | null {
  for (const { stat } of stats) {
    if (stat === 'HEAT') return 'Heat'
    if (stat === 'COLD') return 'Cold'
    if (stat === 'ELECTRICITY') return 'Electricity'
    if (stat === 'TOXIN') return 'Toxin'
  }
  return null
}

// Crit tiers as the game colours them: yellow, orange, red.
export const CRIT_TIERS = [
  { name: 'No crit', color: '#c3ccd6' },
  { name: 'Yellow crit', color: '#f2d544' },
  { name: 'Orange crit', color: '#f08c3a' },
  { name: 'Red crit', color: '#e8553d' },
]

export function critTier(tier: number) {
  return CRIT_TIERS[Math.min(Math.max(tier, 0), CRIT_TIERS.length - 1)]
}
