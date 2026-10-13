import { useMemo } from 'react'
import { useAllWeapons, useBuffs, useCompanions } from '../api/queries'
import { useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { BuffInfo, CompanionInfo } from '../types'
import { pct } from '../utils/format'
import { buttonClass, Notice, Panel, Toggle } from './ui'

const KIND_LABELS: Record<string, (v: number) => string> = {
  base_damage_add: (v) => `+${pct(v)} base damage`,
  physical_add: (v) => `+${pct(v)} physical damage`,
  crit_chance_flat: (v) => `+${pct(v)} critical chance (flat)`,
  crit_chance_floor: (v) => `critical chance at least ${pct(v)}`,
  crit_damage_add: (v) => `+${pct(v)} amp critical damage`,
  crit_mult_flat: (v) => `+${v.toFixed(1)}× final critical multiplier`,
  crit_per_combo: (v) => `+${pct(v)} critical chance per combo multiplier`,
  fire_rate_add: (v) => `+${pct(v)} fire rate`,
  final_multiplier: (v) => `×${(1 + v).toFixed(2)} damage`,
  armor_strip: (v) => `−${pct(Math.min(1, v))} enemy armor`,
}

/** What the loadout is missing for this buff to apply, or null when nothing is. */
function missing(buff: BuffInfo, companion: CompanionInfo | undefined, isMelee: boolean): string | null {
  const need = buff.requires
  if (need.meleeWeapon && !isMelee) return need.text
  if (!need.anyCompanion && need.companions.length === 0 && need.companionTypes.length === 0) return null
  if (!companion) return need.text
  if (need.anyCompanion) return null
  return need.companions.includes(companion.name) || need.companionTypes.includes(companion.type)
    ? null
    : need.text
}

function BuffRow({ index, buff, companion, isMelee }: {
  index: BuildIndex
  buff: BuffInfo
  companion: CompanionInfo | undefined
  isMelee: boolean
}) {
  const selection = useBuildStore((s) => s.builds[index].buffs.find((b) => b.id === buff.id))
  const toggleBuff = useBuildStore((s) => s.toggleBuff)
  const updateBuff = useBuildStore((s) => s.updateBuff)
  const setCompanion = useBuildStore((s) => s.setCompanion)

  const active = selection !== undefined
  const rank = selection?.rank ?? buff.maxRank
  const amount = selection?.amount ?? buff.amount?.default ?? 1
  const uptime = selection?.uptime ?? buff.uptime
  const value = buff.perRank[Math.min(rank, buff.maxRank)] * (buff.amount ? amount : 1)
  const unmet = missing(buff, companion, isMelee)
  // A buff tied to one companion can pick that companion for you when none is chosen.
  const autoCompanion = unmet && !companion && buff.requires.companions.length > 0 ? buff.requires.companions[0] : null
  const blocked = unmet !== null && !autoCompanion
  const strips = buff.kind === 'armor_strip'

  const onToggle = () => {
    if (!active && autoCompanion) setCompanion(index, autoCompanion)
    toggleBuff(index, buff.id, buff.maxRank, buff.amount?.default)
  }

  return (
    <li className={`border px-3 py-2 ${active && !unmet ? 'border-gold/60 bg-gold/5' : 'border-seam'}`}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <Toggle
          label={buff.name}
          checked={active}
          onChange={onToggle}
          disabled={blocked && !active}
          tip={unmet ? `Needs ${unmet}.` : undefined}
        />
        <span className={`text-sm font-medium ${unmet ? 'text-mute line-through' : 'text-ink'}`}>
          {KIND_LABELS[buff.kind]?.(value) ?? ''}
        </span>
      </div>
      <p className="mt-1.5 text-[13px] leading-snug text-mute">
        {buff.text}
        {!buff.verified && <span className="text-bad"> How this stacks is not confirmed.</span>}
      </p>
      {unmet && (
        <p className="mt-1 text-[13px] leading-snug text-bad">
          {active ? 'Not applied: needs ' : 'Needs '}{unmet}.
          {autoCompanion && !active && ` Turning this on selects ${autoCompanion}.`}
        </p>
      )}
      {active && !unmet && (
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-mute">
          {buff.maxRank > 0 && (
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap">Rank {rank}/{buff.maxRank}</span>
              <input type="range" min={0} max={buff.maxRank} value={rank}
                onChange={(e) => updateBuff(index, buff.id, { rank: Number(e.target.value) })} />
            </label>
          )}
          {buff.amount && (
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap">{buff.amount.label}: {amount}</span>
              <input type="range" min={buff.amount.min} max={buff.amount.max} value={amount}
                onChange={(e) => updateBuff(index, buff.id, { amount: Number(e.target.value) })} />
            </label>
          )}
          {!strips && (
            <label className="flex items-center gap-2" title={buff.uptimeNote || 'Share of the time this buff is up.'}>
              <span className="whitespace-nowrap">Up {pct(uptime, 0)} of the time</span>
              <input type="range" min={0} max={100} step={1} value={Math.round(uptime * 100)}
                onChange={(e) => updateBuff(index, buff.id, { uptime: Number(e.target.value) / 100 })} />
            </label>
          )}
        </div>
      )}
      {active && !unmet && !strips && buff.uptimeNote && (
        <p className="mt-1 text-[13px] leading-snug text-mute">{buff.uptimeNote}</p>
      )}
      {active && !unmet && strips && (
        <p className="mt-1 text-[13px] leading-snug text-mute">Applied once; the armor stays off.</p>
      )}
    </li>
  )
}

/** Buffs that come from outside the weapon: Focus, the companion, bond mods and mod sets. */
export function BuffsPanel({ index }: { index: BuildIndex }) {
  const { data: buffs = [], error } = useBuffs()
  const { data: companions } = useCompanions()
  const { data: weapons } = useAllWeapons()
  const count = useBuildStore((s) => s.builds[index].buffs.length)
  const companionName = useBuildStore((s) => s.builds[index].companion)
  const weaponName = useBuildStore((s) => s.builds[index].weapon)
  const update = useBuildStore((s) => s.update)

  const companion = companions?.find((c) => c.name === companionName)
  const isMelee = weapons?.find((w) => w.name === weaponName)?.modType === 'MELEE'

  const groups = useMemo(() => {
    const map = new Map<string, BuffInfo[]>()
    for (const b of buffs) map.set(b.group, [...(map.get(b.group) ?? []), b])
    return [...map.entries()]
  }, [buffs])

  return (
    <Panel
      title="Buffs from Focus, companions and sets"
      actions={
        <button type="button" className={buttonClass} disabled={count === 0} onClick={() => update(index, { buffs: [] })}>
          Turn all off
        </button>
      }
    >
      {error && <Notice tone="error">{error.message}</Notice>}
      <p className="mb-3 text-sm text-mute">
        The main results count every buff that is on at full strength. Where a buff is only up part of the
        time, the results also show damage averaged over its uptime, which you can adjust per buff. Focus
        buffs are not checked against a school: turn on the ones you have unlocked.
      </p>
      <div className="@container space-y-4">
        {groups.map(([group, items]) => (
          <section key={group}>
            <h3 className="mb-2 text-[15px] text-gold">{group}</h3>
            <ul className="grid gap-2 @3xl:grid-cols-2 @6xl:grid-cols-3">
              {items.map((b) => (
                <BuffRow key={b.id} index={index} buff={b} companion={companion} isMelee={isMelee} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </Panel>
  )
}
