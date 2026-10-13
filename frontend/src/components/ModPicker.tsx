import { useEffect, useMemo, useState } from 'react'
import { useAllWeapons, useCompanions, useMods } from '../api/queries'
import {
  fitsSlot, rackGroup, slotKindOf, useBuildStore, usePickerStore,
} from '../stores/buildStore'
import type { PickerTarget, Rack, SlotKind } from '../stores/buildStore'
import type { ModDetail, ModType } from '../types'
import { damageColor, modElement } from '../utils/damageTypes'
import { statLabel, statText } from '../utils/format'
import { POLARITY_GLYPHS } from '../utils/images'
import { FilterSelect } from './Combobox'
import { ModCard } from './ModCard'
import { inputClass, Notice } from './ui'

export { RARITY_COLORS } from '../utils/images'

const TYPE_LABELS: Record<ModType, string> = {
  PRIMARY: 'Rifle',
  SHOTGUN: 'Shotgun',
  SECONDARY: 'Pistol',
  MELEE: 'Melee',
  CLAWS: 'Claws',
  WARFRAME: 'Warframe',
  AURA: 'Aura',
}

const WEAPON_TYPES: ModType[] = ['PRIMARY', 'SHOTGUN', 'SECONDARY', 'MELEE', 'CLAWS']
const RARITIES = ['Common', 'Uncommon', 'Rare', 'Legendary']
const RACK_NAMES: Record<Rack, string> = {
  mods: 'weapon', exilusMods: 'weapon Exilus slot', companionMods: 'companion weapon',
  warframeMods: 'Warframe', auraMods: 'Aura slot', warframeExilusMods: 'Warframe Exilus slot',
}
const KIND_HINT: Record<SlotKind, string> = {
  main: '',
  exilus: 'Only Exilus (utility) mods fit this slot.',
  aura: 'Only aura mods fit this slot.',
}

/** What a dragged browser card carries: the mod and what kind of slot it fits. */
export const NEW_MOD_DRAG_TYPE = 'application/x-mod-new'

export interface DraggedMod {
  name: string
  rank: number
  type: string
  exilus: boolean
}

/** Which mod class a rack takes, from the item it belongs to. */
function useRackModType(target: PickerTarget): ModType {
  const build = useBuildStore((s) => s.builds[target.index])
  const { data: weapons } = useAllWeapons()
  const { data: companions } = useCompanions()
  if (target.rack === 'auraMods') return 'AURA'
  if (target.rack === 'warframeMods' || target.rack === 'warframeExilusMods') return 'WARFRAME'
  let weaponName = build.weapon
  if (target.rack === 'companionMods') {
    const companion = companions?.find((c) => c.name === build.companion)
    weaponName = companion?.weapons.includes(build.companionWeapon)
      ? build.companionWeapon
      : companion?.defaultWeapon ?? ''
  }
  return weapons?.find((w) => w.name === weaponName)?.modType ?? 'PRIMARY'
}

/**
 * The mod browser. On wide screens it is a column that is always visible beside
 * the build; on narrow ones it is a full-screen sheet opened from a slot or the
 * "Browse mods" button. It always fills one target slot: the one last clicked,
 * or the first free slot of the main rack.
 */
export function DockedPicker() {
  const view = useBuildStore((s) => s.view)
  const stored = usePickerStore((s) => s.target)
  const open = usePickerStore((s) => s.open)
  const close = usePickerStore((s) => s.close)
  const addMod = useBuildStore((s) => s.addMod)

  // A target from the other tab doesn't apply: fall back to this tab's main rack.
  const warframeRacks: Rack[] = ['warframeMods', 'auraMods', 'warframeExilusMods']
  const usable = stored && (view === 'taken') === warframeRacks.includes(stored.rack)
  const base: PickerTarget = usable ? stored : { index: 0, rack: view === 'taken' ? 'warframeMods' : 'mods', slot: -1 }
  const build = useBuildStore((s) => s.builds[base.index])
  const rackMods = build[base.rack]
  const firstEmpty = rackMods.findIndex((m) => m === null)
  // the clicked slot while it is free, otherwise the next free one
  const slot = base.slot >= 0 && rackMods[base.slot] === null ? base.slot : firstEmpty === -1 ? null : firstEmpty
  const kind = slotKindOf(base.rack)
  const modType = useRackModType(base)
  const equipped = useMemo(
    () => new Set(rackGroup(base.rack).flatMap((r) => build[r]).filter(Boolean).map((m) => m!.name)),
    [build, base.rack],
  )

  const { data: mods = [], error } = useMods()
  const [search, setSearch] = useState('')
  const [type, setType] = useState<ModType>(modType)
  const [stat, setStat] = useState('')
  const [rarity, setRarity] = useState('')
  const [polarity, setPolarity] = useState('')
  const [sort, setSort] = useState('name')
  const isWarframe = modType === 'WARFRAME' || modType === 'AURA'
  const types: ModType[] = isWarframe ? [modType] : WEAPON_TYPES

  useEffect(() => { setType(modType); setStat('') }, [modType])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, close])

  const candidates = useMemo(
    () => mods.filter((m) => m.type === type && fitsSlot(kind, m)),
    [mods, type, kind],
  )
  const stats = useMemo(
    () => [...new Set(candidates.flatMap((m) => m.stats.map((s) => s.stat)))]
      .sort((a, b) => statLabel(a).localeCompare(statLabel(b))),
    [candidates],
  )
  const shown = useMemo(() => {
    const q = search.trim().toLowerCase()
    const list = candidates.filter((m) =>
      (!q || m.name.toLowerCase().includes(q)) &&
      (!stat || m.stats.some((s) => s.stat === stat)) &&
      (!rarity || m.rarity === rarity) &&
      (!polarity || m.polarity === polarity))
    if (sort === 'drain') list.sort((a, b) => (a.baseDrain + a.maxRank) - (b.baseDrain + b.maxRank) || a.name.localeCompare(b.name))
    else if (sort === 'rarity') list.sort((a, b) => RARITIES.indexOf(b.rarity) - RARITIES.indexOf(a.rarity) || a.name.localeCompare(b.name))
    else list.sort((a, b) => a.name.localeCompare(b.name))
    return list
  }, [candidates, search, stat, rarity, polarity, sort])

  const pick = (mod: ModDetail) => {
    if (slot === null) return
    addMod(base.index, slot, mod.name, mod.maxRank, base.rack)
  }
  const where = slot === null
    ? `Every ${RACK_NAMES[base.rack]} slot is full`
    : kind === 'main' ? `${RACK_NAMES[base.rack]} slot ${slot + 1}` : RACK_NAMES[base.rack]

  return (
    <aside
      aria-label="Mod browser"
      className={`${open ? 'flex' : 'hidden'} fixed inset-0 z-40 flex-col border-seam bg-hull xl:sticky xl:inset-auto xl:top-[4.75rem] xl:z-auto xl:flex xl:h-[calc(100vh-6rem)] xl:border`}
    >
      <header className="space-y-2.5 border-b border-seam p-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base">Mods</h2>
          <button type="button" onClick={close} className="px-2 text-mute hover:text-ink xl:hidden" aria-label="Close mod browser">
            ✕
          </button>
        </div>
        <p className="text-[13px] leading-snug text-mute" role="status">
          Filling: <span className="font-medium text-gold-pale">{where}</span>.
          {' '}{KIND_HINT[kind] || 'Click a slot to aim somewhere else.'}
        </p>
        <input
          aria-label="Search mods"
          placeholder="Search mods"
          spellCheck={false}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={inputClass}
        />
        <div className="flex flex-wrap gap-1.5">
          {types.length > 1 && (
            <FilterSelect
              label="Mod class"
              value={type}
              onChange={(v) => { setType(v as ModType); setStat('') }}
              options={types.map((t) => ({ value: t, label: `${TYPE_LABELS[t]} mods` }))}
            />
          )}
          <FilterSelect
            label="Stat"
            value={stat}
            onChange={setStat}
            options={[{ value: '', label: 'Any stat' }, ...stats.map((s) => ({ value: s, label: statLabel(s) }))]}
          />
          <FilterSelect
            label="Rarity"
            value={rarity}
            onChange={setRarity}
            options={[{ value: '', label: 'Any rarity' }, ...RARITIES.map((r) => ({ value: r, label: r }))]}
          />
          <FilterSelect
            label="Polarity"
            value={polarity}
            onChange={setPolarity}
            options={[
              { value: '', label: 'Any polarity' },
              ...Object.entries(POLARITY_GLYPHS).map(([p, g]) => ({ value: p, label: `${g} ${p}` })),
            ]}
          />
          <FilterSelect
            label="Sort"
            value={sort}
            onChange={setSort}
            options={[
              { value: 'name', label: 'By name' },
              { value: 'drain', label: 'By drain' },
              { value: 'rarity', label: 'By rarity' },
            ]}
          />
        </div>
        {!isWarframe && type !== modType && (
          <p className="text-[13px] leading-snug text-mute">
            This weapon is listed as taking {TYPE_LABELS[modType].toLowerCase()} mods. Other classes are here
            in case the game data has it wrong.
          </p>
        )}
      </header>

      <ul className="grid flex-1 auto-rows-min grid-cols-2 gap-2 overflow-y-auto p-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-2">
        {error && <li className="col-span-full"><Notice tone="error">{error.message}</Notice></li>}
        {!error && shown.length === 0 && (
          <li className="col-span-full text-sm text-mute">No mod matches. Clear the search or loosen a filter.</li>
        )}
        {shown.map((mod) => {
          const taken = equipped.has(mod.name)
          const element = modElement(mod.stats)
          const dragged: DraggedMod = { name: mod.name, rank: mod.maxRank, type: mod.type, exilus: mod.exilus }
          return (
            <li key={mod.name}>
              <button
                type="button"
                disabled={taken || slot === null}
                draggable={!taken}
                onDragStart={(e) => {
                  e.dataTransfer.setData(NEW_MOD_DRAG_TYPE, JSON.stringify(dragged))
                  e.dataTransfer.effectAllowed = 'copy'
                }}
                onClick={() => pick(mod)}
                title={mod.conditional || mod.note || undefined}
                className="h-full w-full text-left transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:hover:translate-y-0"
              >
                <ModCard
                  name={mod.name}
                  imageName={mod.imageName}
                  rarity={mod.rarity}
                  polarity={mod.polarity}
                  rank={mod.maxRank}
                  maxRank={mod.maxRank}
                  size="picker"
                  dim={taken}
                  badge={taken ? 'Equipped' : `${Math.abs(mod.baseDrain) + mod.maxRank} drain`}
                >
                  <span className="block px-2 pb-2 pt-1">
                    <span className="block font-display text-[14px] font-semibold leading-tight">{mod.name}</span>
                    <span className="mt-0.5 line-clamp-3 block text-[12px] leading-snug" style={element ? { color: damageColor(element) } : undefined}>
                      {mod.stats.length > 0
                        ? mod.stats.map((s) => statText(s.stat, s.value)).join(', ')
                        : <span className="text-mute">{mod.note}</span>}
                    </span>
                    <span className="mt-1 block text-[11px] uppercase tracking-wide text-mute">
                      {TYPE_LABELS[mod.type]}{mod.exilus ? ' · Exilus' : ''}
                    </span>
                  </span>
                </ModCard>
              </button>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}
