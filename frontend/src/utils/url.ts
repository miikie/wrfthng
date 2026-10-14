import { DEFAULT_BUILD, normalizeBuild, SLOT_COUNT } from '../stores/buildStore'
import type { Build } from '../stores/buildStore'
import type { ModInput } from '../types'

// A build is shared as plain query params so links stay readable:
//   ?w=Soma Prime&e=Heavy Gunner|Grineer|STANDARD&lv=100&sp=1&m=Serration:10&m=Split Chamber:5
// Build B (compare mode) uses the same keys prefixed with "b.".

function writeBuild(q: URLSearchParams, b: Build, prefix: string) {
  const set = (k: string, v: string | number) => q.set(prefix + k, String(v))
  set('w', b.weapon)
  set('e', b.enemyKey)
  set('lv', b.enemyLevel)
  if (b.steelPath) set('sp', 1)
  if (b.eximus) set('ex', 1)
  if (b.headshot) set('hs', 1)
  if (b.viralStacks) set('vs', b.viralStacks)
  if (b.statusTypes) set('st', b.statusTypes)
  if (b.armorStripPct) set('as', Math.round(b.armorStripPct * 100))
  if (b.comboMultiplier !== 1) set('cm', b.comboMultiplier)

  const writeMods = (key: string, mods: (ModInput | null)[]) => {
    let last = mods.length - 1
    while (last >= 0 && mods[last] === null) last--
    for (let i = 0; i <= last; i++) {
      const m = mods[i]
      q.append(prefix + key, m ? `${m.name}:${m.rank}` : '')
    }
  }
  writeMods('m', b.mods)
  writeMods('xm', b.exilusMods)
  for (const arcane of b.weaponArcanes) q.append(prefix + 'wpa', arcane)

  if (b.companion) {
    set('c', b.companion)
    if (b.companionWeapon) set('cw', b.companionWeapon)
    if (!b.sentinelAttack) set('np', 1)
    writeMods('km', b.companionMods)
  }
  for (const [mod, stacks] of Object.entries(b.conditionalStacks)) {
    const equipped = [
      ...b.mods, ...b.exilusMods, ...b.companionMods, ...b.warframeMods, ...b.auraMods, ...b.warframeExilusMods,
    ].some((m) => m?.name === mod)
    if (stacks > 0 && equipped) q.append(prefix + 'cs', `${mod}:${stacks}`)
  }
  for (const buff of b.buffs) {
    q.append(prefix + 'bf', [
      buff.id, buff.rank, buff.amount ?? '',
      buff.uptime === undefined ? '' : Math.round(buff.uptime * 100),
    ].join(':'))
  }
  set('wf', b.warframe)
  writeMods('wm', b.warframeMods)
  writeMods('wa', b.auraMods)
  writeMods('wx', b.warframeExilusMods)
  set('sv', JSON.stringify(b.survival))
  if (b.helminth) set('hm', `${b.helminth.ability}:${b.helminth.slot}`)
  if (Object.keys(b.abilityBuffs).length > 0) set('ab', JSON.stringify(b.abilityBuffs))
  if (b.amp) {
    set('amp', [b.amp.prism, b.amp.scaffold, b.amp.brace].join('|'))
    for (const a of b.amp.arcanes) q.append(prefix + 'aa', `${a.name}:${a.rank}`)
  }
}

function readBuild(q: URLSearchParams, prefix: string): Build | null {
  const get = (k: string) => q.get(prefix + k)
  const weapon = get('w')
  if (!weapon) return null

  const int = (k: string, fallback: number, min: number, max: number) => {
    const n = Number(get(k))
    return get(k) !== null && Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback
  }

  const readMods = (key: string): (ModInput | null)[] => {
    const seen = new Set<string>()
    return q.getAll(prefix + key).slice(0, SLOT_COUNT).map((raw) => {
      const cut = raw.lastIndexOf(':')
      const name = cut === -1 ? raw : raw.slice(0, cut)
      const rank = cut === -1 ? 0 : Math.max(0, Math.floor(Number(raw.slice(cut + 1))) || 0)
      if (!name || seen.has(name)) return null
      seen.add(name)
      return { name, rank }
    })
  }
  const mods = readMods('m')

  const buffs = q.getAll(prefix + 'bf').map((raw) => {
    const [id, rank, amount, uptime] = raw.split(':')
    return {
      id,
      rank: Math.max(0, Math.floor(Number(rank)) || 0),
      ...(amount ? { amount: Number(amount) || 0 } : {}),
      ...(uptime ? { uptime: Math.min(100, Math.max(0, Number(uptime) || 0)) / 100 } : {}),
    }
  }).filter((x) => x.id)

  const conditionalStacks = Object.fromEntries(
    readMods('cs').filter((m): m is ModInput => m !== null).map((m) => [m.name, m.rank]),
  )

  let survival: Partial<Build['survival']> | undefined
  try {
    const raw = get('sv')
    if (raw) survival = JSON.parse(raw)
  } catch {
    survival = undefined
  }

  let abilityBuffs: Build['abilityBuffs'] | undefined
  try {
    const raw = get('ab')
    if (raw) abilityBuffs = JSON.parse(raw)
  } catch {
    abilityBuffs = undefined
  }
  const infusion = get('hm')
  const cut = infusion ? infusion.lastIndexOf(':') : -1
  const slot = cut > 0 ? Math.floor(Number(infusion!.slice(cut + 1))) : NaN
  const helminth = cut > 0 && slot >= 1 && slot <= 4 ? { ability: infusion!.slice(0, cut), slot } : null

  const ampParts = get('amp')?.split('|')
  const amp = ampParts && ampParts[0]
    ? {
        prism: ampParts[0],
        scaffold: ampParts[1] ?? '',
        brace: ampParts[2] ?? '',
        arcanes: readMods('aa').filter((a): a is ModInput => a !== null).slice(0, 2),
      }
    : null

  return normalizeBuild({
    weapon,
    enemyKey: get('e') ?? DEFAULT_BUILD.enemyKey,
    enemyLevel: Math.round(int('lv', DEFAULT_BUILD.enemyLevel, 1, 9999)),
    steelPath: get('sp') === '1',
    eximus: get('ex') === '1',
    headshot: get('hs') === '1',
    viralStacks: Math.round(int('vs', 0, 0, 10)),
    statusTypes: Math.round(int('st', 0, 0, 10)),
    armorStripPct: int('as', 0, 0, 100) / 100,
    comboMultiplier: int('cm', 1, 1, 13),
    mods,
    companion: get('c') ?? '',
    companionWeapon: get('cw') ?? '',
    companionMods: readMods('km'),
    sentinelAttack: get('np') !== '1',
    conditionalStacks,
    buffs,
    amp,
    warframe: get('wf') ?? DEFAULT_BUILD.warframe,
    warframeMods: q.has(prefix + 'wf') ? readMods('wm') : undefined,
    exilusMods: readMods('xm'),
    auraMods: readMods('wa'),
    warframeExilusMods: readMods('wx'),
    weaponArcanes: q.getAll(prefix + 'wpa').slice(0, 2),
    survival: survival as Build['survival'] | undefined,
    helminth,
    abilityBuffs,
  })
}

export interface SharedState {
  builds: [Build, Build]
  compare: boolean
  sharedEnemy: boolean
  view: 'dealt' | 'taken'
}

export function encodeState(s: SharedState): string {
  const q = new URLSearchParams()
  if (s.view === 'taken') q.set('view', 'taken')
  writeBuild(q, s.builds[0], '')
  if (s.compare) {
    q.set('cmp', s.sharedEnemy ? 'shared' : 'split')
    writeBuild(q, s.builds[1], 'b.')
  }
  return q.toString()
}

/** Reads a shared link. Without compare params only Build A is returned. */
export function decodeState(
  search: string,
): { a: Build; b: Build | null; sharedEnemy: boolean; view: 'dealt' | 'taken' } | null {
  const q = new URLSearchParams(search)
  const a = readBuild(q, '')
  if (!a) return null
  const b = readBuild(q, 'b.')
  const cmp = q.get('cmp')
  return {
    a, b: cmp ? b : null, sharedEnemy: cmp !== 'split',
    view: q.get('view') === 'taken' ? 'taken' : 'dealt',
  }
}
