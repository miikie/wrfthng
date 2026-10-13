import { useCallback, useMemo, useState } from 'react'
import { useAllWeapons, useCalculation, useMod, useMods, useWarframes, useWeaponArcanes } from '../api/queries'
import { fitsSlot, RACK_SIZE, slotKindOf, useBuildStore, usePickerStore } from '../stores/buildStore'
import type { BuildIndex, Rack } from '../stores/buildStore'
import type { ElementGroup, ModDetail, ModInput } from '../types'
import { damageColor, modElement } from '../utils/damageTypes'
import { statText } from '../utils/format'
import { polarityGlyph } from '../utils/images'
import { GridPicker, ItemImage } from './ItemImage'
import { ModCard, RankPips } from './ModCard'
import { NEW_MOD_DRAG_TYPE } from './ModPicker'
import type { DraggedMod } from './ModPicker'
import { Bar, buttonClass, DamageChip, Panel, Tip, Toggle } from './ui'

const DRAG_TYPE = 'application/x-mod-slot'

/** Capacity a mod takes in a slot: half (rounded up) on a matching polarity, +25% on a different one. */
function drainIn(mod: ModDetail | undefined, rank: number, slotPolarity: string): number {
  if (!mod) return 0
  const drain = Math.abs(mod.baseDrain) + rank
  const sign = mod.baseDrain < 0 ? -1 : 1   // auras add capacity
  if (!slotPolarity) return sign * drain
  if (slotPolarity === mod.polarity) return sign * (sign < 0 ? drain * 2 : Math.ceil(drain / 2))
  return sign * (sign < 0 ? Math.floor(drain * 0.8) : Math.ceil(drain * 1.25))
}

function ModSlot({ index, rack, slot, mod, polarity, label }: {
  index: BuildIndex
  rack: Rack
  slot: number
  mod: ModInput | null
  /** The slot's innate polarity, '' for none. */
  polarity: string
  /** Name of a special slot ("Exilus", "Aura"); main slots are numbered. */
  label?: string
}) {
  const kind = slotKindOf(rack)
  const size = RACK_SIZE[rack]
  const select = usePickerStore((s) => s.select)
  const targeted = usePickerStore((s) =>
    s.target?.index === index && s.target.rack === rack && s.target.slot === slot)
  const onOpen = () => select({ index, rack, slot })
  const [rejected, setRejected] = useState(false)
  const slotName = label ?? `Slot ${slot + 1}`
  const addMod = useBuildStore((s) => s.addMod)
  const removeMod = useBuildStore((s) => s.removeMod)
  const setModRank = useBuildStore((s) => s.setModRank)
  const reorderMods = useBuildStore((s) => s.reorderMods)
  const setStacks = useBuildStore((s) => s.setStacks)
  const stacks = useBuildStore((s) => (mod ? s.builds[index].conditionalStacks[mod.name] ?? 0 : 0))
  const [dropTarget, setDropTarget] = useState(false)
  const { data: detail } = useMod(mod?.name ?? '', mod?.rank ?? 0)

  const dropProps = {
    onDragOver: (e: React.DragEvent) => {
      const types = e.dataTransfer.types
      if (!types.includes(DRAG_TYPE) && !types.includes(NEW_MOD_DRAG_TYPE)) return
      e.preventDefault()
      setDropTarget(true)
    },
    onDragLeave: () => setDropTarget(false),
    onDrop: (e: React.DragEvent) => {
      setDropTarget(false)
      // A card dragged out of the mod browser
      const fresh = e.dataTransfer.getData(NEW_MOD_DRAG_TYPE)
      if (fresh) {
        const data = JSON.parse(fresh) as DraggedMod
        e.preventDefault()
        // An aura in a main slot, or an ordinary mod in the Exilus slot, is refused.
        if (!fitsSlot(kind, data)) {
          setRejected(true)
          window.setTimeout(() => setRejected(false), 700)
          return
        }
        addMod(index, slot, data.name, data.rank, rack)
        return
      }
      // A card moved from another slot of the same rack: the two swap places.
      const [build, fromRack, fromSlot] = e.dataTransfer.getData(DRAG_TYPE).split(':')
      const from = Number(fromSlot)
      if (Number(build) !== index || fromRack !== rack || !Number.isInteger(from)) return
      e.preventDefault()
      reorderMods(index, from, slot, rack)
    },
  }
  const ring = rejected
    ? 'outline outline-2 outline-bad'
    : dropTarget ? 'outline outline-2 outline-tenno' : targeted ? 'outline outline-2 outline-gold' : ''
  const glyph = polarityGlyph(polarity)

  if (!mod) {
    return (
      <li {...dropProps}>
        <button
          type="button"
          onClick={onOpen}
          aria-pressed={targeted}
          className={`flex h-full w-full flex-col items-center justify-center gap-1 border border-dashed bg-void/40 text-mute hover:border-tenno hover:text-ink ${kind === 'main' ? 'min-h-44 border-seam' : 'min-h-24 border-seam-bright'} ${ring}`}
        >
          <span className="font-display text-3xl leading-none opacity-60" aria-hidden>{glyph || '+'}</span>
          <span className={kind === 'main' ? 'text-sm' : 'text-[13px] font-semibold uppercase tracking-wider text-gold'}>
            {slotName}{polarity ? `, ${polarity}` : ''}
          </span>
          <span className="text-[12px]">
            {rejected ? 'That mod does not fit here' : kind === 'aura' ? 'Aura mods only' : kind === 'exilus' ? 'Exilus mods only' : 'Add a mod'}
          </span>
        </button>
      </li>
    )
  }

  const element = detail ? modElement(detail.stats) : null
  const move = (to: number) => reorderMods(index, slot, to, rack)
  // Bonuses that need a trigger (kills, aiming) only count once switched on here.
  const triggered = detail?.stats.filter((s) => s.condition && s.condition !== 'per_combo') ?? []
  const maxStacks = Math.max(0, ...triggered.map((s) => s.maxStacks))
  const smallButton = 'px-1.5 text-mute hover:text-ink disabled:opacity-30'
  const matches = polarity !== '' && detail?.polarity === polarity
  const clashes = polarity !== '' && !!detail && detail.polarity !== polarity

  return (
    <li {...dropProps} className={ring}>
      <ModCard
        name={mod.name}
        imageName={detail?.imageName}
        rarity={detail?.rarity}
        polarity={detail?.polarity}
        rank={mod.rank}
        maxRank={detail?.maxRank}
        badge={maxStacks > 1 ? `${Math.min(stacks, maxStacks)}/${maxStacks} stacks` : maxStacks === 1 ? (stacks > 0 ? 'Active' : 'Off') : undefined}
      >
        <div
          draggable
          onDragStart={(e) => {
            e.dataTransfer.setData(DRAG_TYPE, `${index}:${rack}:${slot}`)
            e.dataTransfer.effectAllowed = 'move'
          }}
          onDragEnd={(e) => {
            // Dropped somewhere that isn't a slot: the mod comes off.
            if (e.dataTransfer.dropEffect === 'none') removeMod(index, slot, rack)
          }}
          className="flex-1 cursor-grab px-2.5 pt-1 active:cursor-grabbing"
          title="Drag onto another slot to swap, or off the rack to remove. Slot order decides how elements combine."
        >
          <button type="button" onClick={onOpen} className="text-left font-display text-[15px] font-semibold leading-tight hover:text-tenno">
            {mod.name}
          </button>
          <ul className="mt-0.5 text-[13px] leading-snug" style={element ? { color: damageColor(element) } : undefined}>
            {detail?.stats.map((s) => (
              <li key={s.stat + s.condition} className={s.condition && s.condition !== 'per_combo' && stacks === 0 ? 'opacity-50' : undefined}>
                {statText(s.stat, s.value)}{conditionText(s.condition, s.maxStacks)}
              </li>
            ))}
          </ul>
          {detail && (detail.conditional || detail.note) && (
            <p className="mt-1 line-clamp-2 text-[12px] leading-snug text-mute" title={detail.conditional || detail.note}>
              {detail.conditional || detail.note}
            </p>
          )}
        </div>

        <div className="px-2.5 pb-1.5 pt-1">
          {maxStacks === 1 && (
            <label className="mb-1 flex items-center gap-2 text-[13px] text-ink">
              <input type="checkbox" checked={stacks > 0}
                onChange={(e) => setStacks(index, mod.name, e.target.checked ? 1 : 0)} />
              Bonus active
            </label>
          )}
          {maxStacks > 1 && (
            <label className="mb-1 flex items-center gap-2 text-[13px] text-ink">
              <span className="whitespace-nowrap">Stacks {stacks}/{maxStacks}</span>
              <input type="range" min={0} max={maxStacks} value={Math.min(stacks, maxStacks)}
                onChange={(e) => setStacks(index, mod.name, Number(e.target.value))}
                className="min-w-0 flex-1" />
            </label>
          )}
          {detail && detail.maxRank > 0 && (
            <>
              <label className="flex items-center gap-2 text-[13px] text-mute">
                <span className="whitespace-nowrap">Rank {mod.rank}/{detail.maxRank}</span>
                <input
                  type="range"
                  min={0}
                  max={detail.maxRank}
                  value={mod.rank}
                  onChange={(e) => setModRank(index, slot, Number(e.target.value), rack)}
                  className="min-w-0 flex-1"
                />
              </label>
              <RankPips rank={mod.rank} maxRank={detail.maxRank} />
            </>
          )}
          <div className="-mx-1.5 mt-0.5 flex items-center justify-between text-sm">
            <span>
              <button type="button" className={smallButton} disabled={slot === 0}
                onClick={() => move(slot - 1)} aria-label={`Move ${mod.name} one slot earlier`}>‹</button>
              <span className="text-[13px] text-mute" title={polarity ? `${polarity} slot` : undefined}>
                {slotName}
                {glyph && <span className={matches ? 'text-good' : clashes ? 'text-bad' : ''}> {glyph}</span>}
              </span>
              <button type="button" className={smallButton} disabled={slot === size - 1}
                onClick={() => move(slot + 1)} aria-label={`Move ${mod.name} one slot later`}>›</button>
            </span>
            <button type="button" className={smallButton}
              onClick={() => removeMod(index, slot, rack)} aria-label={`Remove ${mod.name}`}>✕</button>
          </div>
        </div>
      </ModCard>
    </li>
  )
}

const CONDITION_TEXT: Record<string, string> = {
  while_aiming: ' while aiming',
  on_kill: ' on kill',
  on_hit: ' on hit',
  on_headshot: ' on weak point hit',
  on_ability: ' on ability cast',
  on_reload: ' on reload',
  on_equip: ' on equip',
  on_damaged: ' per hit taken',
  on_health_orb: ' per Health Orb',
  while_airborne: ' while airborne',
  on_status: ' after a weapon status effect',
  while_invisible: ' while invisible',
  on_wall_latch: ' during a wall latch',
  per_combo: ' per combo multiplier',
}

function conditionText(condition: string, maxStacks: number): string {
  if (!condition) return ''
  return (CONDITION_TEXT[condition] ?? '') + (maxStacks > 1 ? `, up to ${maxStacks}×` : '')
}

const sourceText = (source: string) =>
  source === 'Innate' ? 'From the weapon itself (always combines last)' : `From ${source}`

/** How the build's elemental mods combine, in slot order. */
export function ElementalPreview({ groups }: { groups: ElementGroup[] }) {
  if (groups.length === 0) {
    return (
      <p className="text-sm text-mute">
        No elemental damage yet. Add Heat, Cold, Electricity or Toxin mods. The first two
        elements in slot order combine, then the next two.
      </p>
    )
  }
  return (
    <ul className="flex flex-wrap items-center gap-x-8 gap-y-2 text-sm">
      {groups.map((group) => {
        const combined = group.sources.some((s) => s.element !== group.type)
        return (
          <li key={group.type} className="flex flex-wrap items-center gap-2">
            {combined ? (
              <>
                {group.sources.map((s, i) => (
                  <span key={`${s.source}-${s.element}`} className="flex items-center gap-2">
                    {i > 0 && <span className="text-mute">+</span>}
                    <DamageChip type={s.element} title={sourceText(s.source)} />
                  </span>
                ))}
                <span className="text-mute" aria-label="combine into">→</span>
                <DamageChip
                  key={group.sources.map((s) => s.element).join()}
                  type={group.type}
                  strong
                  className="animate-form"
                />
              </>
            ) : (
              <DamageChip
                type={group.type}
                strong
                title={group.sources.map((s) => sourceText(s.source)).join('; ')}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}

/** Mod capacity used against what the item has. Display only: the calculator ignores it. */
function CapacityBar({ slots }: { slots: { mod: ModInput | null; polarity: string }[] }) {
  const { data: all = [] } = useMods()
  const [doubled, setDoubled] = useState(true)
  const byName = useMemo(() => new Map(all.map((m) => [m.name, m])), [all])
  let used = 0
  let bonus = 0
  for (const { mod, polarity } of slots) {
    if (!mod) continue
    const drain = drainIn(byName.get(mod.name), mod.rank, polarity)
    if (drain < 0) bonus -= drain
    else used += drain
  }
  const capacity = (doubled ? 60 : 30) + bonus
  const over = used > capacity
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div className="min-w-48 flex-1">
        <div className="mb-1 flex items-baseline justify-between text-[13px] text-mute">
          <Tip text="How much mod capacity this loadout uses at rank 30. A mod costs half in a slot of its own polarity and a quarter more in a different one; an aura adds capacity. This assumes the item's built-in polarities sit on the first slots; the game lets you move them.">
            Mod capacity
          </Tip>
          <span className={over ? 'font-medium text-bad' : 'text-ink'}>
            {used} / {capacity}{over ? ' (over capacity)' : ''}
          </span>
        </div>
        <Bar fraction={capacity > 0 ? used / capacity : 1} color={over ? 'var(--color-bad)' : 'var(--color-tenno)'} />
      </div>
      <Toggle label="Orokin Catalyst or Reactor" checked={doubled} onChange={setDoubled}
        tip="Doubles base capacity from 30 to 60." />
    </div>
  )
}

/** Two arcane slots for the weapon. The calculator has no weapon arcanes, so these only record the loadout. */
function WeaponArcaneSlots({ index, modType }: { index: BuildIndex; modType: string }) {
  const { data: arcanes = [] } = useWeaponArcanes()
  const chosen = useBuildStore((s) => s.builds[index].weaponArcanes)
  const update = useBuildStore((s) => s.update)
  const [slot, setSlot] = useState<number | null>(null)
  const close = useCallback(() => setSlot(null), [])
  // shotguns also take primary arcanes
  const fitting = arcanes.filter((a) => a.type === modType || (modType === 'SHOTGUN' && a.type === 'PRIMARY'))
  const items = fitting.map((a) => ({ key: a.name, name: a.name, imageName: a.imageName, detail: a.text }))
  if (fitting.length === 0) return null

  const set = (at: number, name: string) => {
    const next = [...chosen]
    if (name) next[at] = name
    else next.splice(at, 1)
    update(index, { weaponArcanes: next.filter((n, i) => n && next.indexOf(n) === i).slice(0, 2) })
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3">
        <h3 className="text-[13px] font-semibold uppercase tracking-wider text-gold">Arcanes</h3>
        <span className="text-[13px] text-mute">Shown for the loadout only. They do not change the results yet.</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {[0, 1].map((i) => {
          const info = fitting.find((a) => a.name === chosen[i])
          return (
            <button key={i} type="button" onClick={() => setSlot(i)}
              className="flex items-center gap-3 border border-seam bg-void p-2 text-left hover:border-tenno">
              <ItemImage name={info?.name ?? `Slot ${i + 1}`} imageName={info?.imageName} fallback={i + 1}
                className="size-12 rounded-full" />
              <span className="min-w-0">
                <span className="block truncate font-display font-semibold">{info?.name ?? `Arcane slot ${i + 1}`}</span>
                <span className="line-clamp-2 block text-[13px] leading-snug text-mute">
                  {info ? info.text : 'Empty. Click to choose.'}
                </span>
              </span>
              {info && <span className="ml-auto shrink-0 border border-seam px-1.5 text-[11px] text-mute">Not calculated</span>}
            </button>
          )
        })}
      </div>
      {slot !== null && (
        <GridPicker title={`Weapon arcane for slot ${slot + 1} (not calculated)`} items={items} columns="narrow"
          selected={chosen[slot] ?? ''} allowNone="Empty slot" onSelect={(name) => set(slot, name)} onClose={close} />
      )}
    </div>
  )
}

/**
 * A full mod rack: the special slots (Exilus, and Aura for a Warframe) above
 * eight main slots. It belongs to the build's weapon, to its companion's weapon
 * when `companionWeapon` names one, or to the Warframe.
 */
export function ModRack({ index, companionWeapon, warframe = false }: {
  index: BuildIndex
  companionWeapon?: string
  /** The Warframe's own mods, for the damage-taken calculator. */
  warframe?: boolean
}) {
  const rack: Rack = warframe ? 'warframeMods' : companionWeapon === undefined ? 'mods' : 'companionMods'
  const exilusRack: Rack | null = warframe ? 'warframeExilusMods' : companionWeapon === undefined ? 'exilusMods' : null
  const build = useBuildStore((s) => s.builds[index])
  const weaponName = companionWeapon ?? build.weapon
  const mods = build[rack]
  const clearMods = useBuildStore((s) => s.clearMods)
  const show = usePickerStore((s) => s.show)
  const { data: weapons } = useAllWeapons()
  const { data: warframes } = useWarframes()
  const { data: result } = useCalculation(index)

  const weapon = weapons?.find((w) => w.name === weaponName)
  const frame = warframes?.warframes.find((w) => w.name === build.warframe)
  const polarities = (warframe ? frame?.polarities : weapon?.polarities) ?? []
  const special: { rack: Rack; label: string; polarity: string }[] = [
    ...(warframe ? [{ rack: 'auraMods' as Rack, label: 'Aura', polarity: frame?.auraPolarity ?? '' }] : []),
    ...(exilusRack ? [{ rack: exilusRack, label: 'Exilus', polarity: '' }] : []),
  ]
  const all = [
    ...special.map((s) => ({ mod: build[s.rack][0], polarity: s.polarity })),
    ...mods.map((mod, slot) => ({ mod, polarity: polarities[slot] ?? '' })),
  ]
  const filled = all.filter((s) => s.mod).length
  const clearAll = () => {
    clearMods(index, rack)
    special.forEach((s) => clearMods(index, s.rack))
  }

  return (
    <Panel
      title={warframe ? 'Warframe mods' : companionWeapon === undefined ? 'Mods' : `Companion weapon mods: ${companionWeapon}`}
      actions={
        <div className="flex gap-2">
          <button type="button" className={`${buttonClass} xl:hidden`} onClick={() => show({ index, rack, slot: -1 })}>
            Browse mods
          </button>
          <button type="button" className={buttonClass} disabled={filled === 0} onClick={clearAll}>
            Remove all mods
          </button>
        </div>
      }
    >
      <div className="@container space-y-4">
        <CapacityBar slots={all} />
        {special.length > 0 && (
          <ol className="grid grid-cols-2 gap-3 border-b border-seam pb-4 @2xl:grid-cols-4">
            {special.map((s) => (
              <ModSlot key={s.rack} index={index} rack={s.rack} slot={0} mod={build[s.rack][0]}
                polarity={s.polarity} label={s.label} />
            ))}
          </ol>
        )}
        <ol className="grid grid-cols-2 gap-3 @2xl:grid-cols-4">
          {mods.map((mod, slot) => (
            <ModSlot key={slot} index={index} rack={rack} slot={slot} mod={mod} polarity={polarities[slot] ?? ''} />
          ))}
        </ol>
        {rack === 'mods' && <WeaponArcaneSlots index={index} modType={weapon?.modType ?? 'PRIMARY'} />}
        {rack === 'mods' && (
          <div className="border-t border-seam pt-3">
            <ElementalPreview groups={result?.elements ?? []} />
          </div>
        )}
      </div>
    </Panel>
  )
}
