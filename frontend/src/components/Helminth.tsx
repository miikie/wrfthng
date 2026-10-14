import { useEffect, useMemo, useState } from 'react'
import { useHelminth, useWarframes } from '../api/queries'
import { useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { HelminthAbility, HelminthCatalogue } from '../types'
import { useDismiss } from '../utils/hooks'
import { ItemImage } from './ItemImage'
import { inputClass } from './ui'

/** The Helminth's mark: a bloom of tendrils around a maw. */
export function HelminthIcon({ className = 'size-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3c2 3 2 5 0 7-2-2-2-4 0-7Z" />
      <path d="M20.5 9.2c-1.9 3.1-3.8 3.9-6.5 3.2 1-2.6 2.8-3.7 6.5-3.2Z" />
      <path d="M3.5 9.2c3.7-.5 5.5.6 6.5 3.2-2.7.7-4.6-.1-6.5-3.2Z" />
      <path d="M17.3 20c-3.5-1-4.8-2.6-4.6-5.3 2.8.2 4.2 1.8 4.6 5.3Z" />
      <path d="M6.7 20c.4-3.5 1.8-5.1 4.6-5.3.2 2.7-1.1 4.3-4.6 5.3Z" />
      <circle cx="12" cy="12.6" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  )
}

const baseOf = (name: string) => name.replace(/ (Prime|Umbra)$/, '')

/**
 * Why `ability` can't go in `slot` on this Warframe, or null if it can. The same
 * rules as the server: the Helminth's damage-buff placement rule (wiki), and no
 * second copy of an ability the Warframe already has.
 */
export function infusionBlocked(
  warframe: string, frameAbilities: string[], ability: string, slot: number, catalogue: HelminthCatalogue,
): string | null {
  if (frameAbilities.includes(ability)) return `${warframe} already has ${ability}.`
  const only = catalogue.restrictions.onlyReplace[baseOf(warframe)]
  if (only && catalogue.restrictions.abilities.includes(ability) && frameAbilities[slot - 1] !== only) {
    return `On ${baseOf(warframe)}, ${ability} can only replace ${only}. The Helminth keeps ` +
      `${catalogue.restrictions.abilities.join(', ')} from stacking with a Warframe's own damage buff.`
  }
  return null
}

export interface SlotAbility {
  slot: number
  name: string
  imageName: string
  /** The infused ability in this slot, if any. */
  infused: HelminthAbility | null
  /** The Warframe's own ability for this slot (dimmed when replaced). */
  original: { name: string; imageName: string }
}

/** The Warframe's four abilities with the infusion in place. */
export function useSlotAbilities(index: BuildIndex): { slots: SlotAbility[]; catalogue?: HelminthCatalogue } {
  const name = useBuildStore((s) => s.builds[index].warframe)
  const helminth = useBuildStore((s) => s.builds[index].helminth)
  const { data: frames } = useWarframes()
  const { data: catalogue } = useHelminth()
  return useMemo(() => {
    const frame = frames?.warframes.find((w) => w.name === name)
    const own = frame?.allAbilities ?? []
    const all = catalogue ? [...catalogue.subsumable, ...catalogue.helminthAbilities] : []
    const slots = own.map((a, i) => {
      const infused = helminth && helminth.slot === i + 1 ? all.find((x) => x.ability === helminth.ability) ?? null : null
      return {
        slot: i + 1,
        name: infused?.ability ?? a.name,
        imageName: infused ? infused.imageName : a.imageName,
        infused,
        original: a,
      }
    })
    return { slots, catalogue }
  }, [frames, catalogue, name, helminth])
}

const TAG_STYLE: Record<string, string> = {
  'Damage buff': 'border-gold/60 text-gold',
  'Armor strip': 'border-[var(--color-armor)] text-[var(--color-armor)]',
  DR: 'border-good/60 text-good',
  Armor: 'border-[var(--color-armor)] text-[var(--color-armor)]',
  Strength: 'border-tenno/60 text-tenno',
}

export function AbilityTags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null
  return (
    <span className="flex flex-wrap gap-1">
      {tags.map((t) => (
        <span key={t} className={`border px-1 text-[11px] uppercase tracking-wide ${TAG_STYLE[t] ?? 'border-seam text-mute'}`}>{t}</span>
      ))}
    </span>
  )
}

const CATEGORY_ORDER = ['Damage', 'Armor strip', 'Survivability', 'Helminth', 'Crowd control', 'Utility']

/** Choose a Helminth ability for one slot. Abilities the rules forbid there are greyed with the reason. */
export function HelminthPicker({ index, slot, onClose }: { index: BuildIndex; slot: number; onClose: () => void }) {
  const warframe = useBuildStore((s) => s.builds[index].warframe)
  const current = useBuildStore((s) => s.builds[index].helminth)
  const setHelminth = useBuildStore((s) => s.setHelminth)
  const { slots, catalogue } = useSlotAbilities(index)
  const [search, setSearch] = useState('')
  const [group, setGroup] = useState('')
  const ref = useDismiss<HTMLDivElement>(true, onClose)

  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previous }
  }, [])

  const ownKey = slots.map((s) => s.original.name).join('|')
  const items = useMemo(() => {
    if (!catalogue) return []
    const own = ownKey.split('|')
    const q = search.trim().toLowerCase()
    return [...catalogue.subsumable, ...catalogue.helminthAbilities]
      .filter((a) => !group || a.category === group)
      .filter((a) => !q || a.ability.toLowerCase().includes(q) || a.warframe.toLowerCase().includes(q))
      .map((a) => ({ ability: a, blocked: infusionBlocked(warframe, own, a.ability, slot, catalogue) }))
      .sort((x, y) => CATEGORY_ORDER.indexOf(x.ability.category) - CATEGORY_ORDER.indexOf(y.ability.category)
        || Number(!!x.blocked) - Number(!!y.blocked) || x.ability.ability.localeCompare(y.ability.ability))
  }, [catalogue, search, group, warframe, slot, ownKey])

  const groups = catalogue
    ? CATEGORY_ORDER.filter((g) => [...catalogue.subsumable, ...catalogue.helminthAbilities].some((a) => a.category === g))
    : []
  const replacing = slots[slot - 1]?.original.name ?? `ability ${slot}`
  const infusedHere = current?.slot === slot ? current.ability : ''
  const choose = (ability: string) => { setHelminth(index, { ability, slot }); onClose() }

  const tab = (value: string, text: string) => (
    <button key={value} type="button" onClick={() => setGroup(value)} aria-pressed={group === value}
      className={`border px-2.5 py-1 text-[13px] font-medium ${
        group === value ? 'border-gold bg-gold/15 text-gold-pale' : 'border-seam bg-plate text-mute hover:text-ink'
      }`}>
      {text}
    </button>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-void/80 p-3 pt-[6vh] sm:p-6 sm:pt-[6vh]">
      <div ref={ref} role="dialog" aria-modal="true" aria-label={`Helminth ability for slot ${slot}`}
        className="flex max-h-[86vh] w-full max-w-5xl flex-col border border-seam-bright bg-hull shadow-2xl shadow-black/60">
        <header className="space-y-3 border-b border-seam p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-base">
              <HelminthIcon className="size-5 text-gold" />
              Infuse over {replacing}
            </h2>
            <div className="flex items-center gap-2">
              {current && (
                <button type="button" onClick={() => { setHelminth(index, null); onClose() }}
                  className="border border-seam px-2.5 py-1 text-[13px] text-mute hover:border-bad hover:text-ink">
                  Remove {current.ability}
                </button>
              )}
              <button type="button" onClick={onClose} className="px-2 text-mute hover:text-ink" aria-label="Close">✕</button>
            </div>
          </div>
          <p className="text-[13px] leading-snug text-mute">
            One infusion per Warframe: choosing an ability here replaces {replacing}
            {current && current.slot !== slot ? ` and removes ${current.ability} from slot ${current.slot}` : ''}.
            Tags show what the calculator models; infused values are the Helminth versions from the wiki.
          </p>
          <input autoFocus aria-label="Search abilities" placeholder="Search by ability or Warframe" spellCheck={false}
            value={search} onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              const first = items.find((x) => !x.blocked)
              if (e.key === 'Enter' && first) choose(first.ability.ability)
              if (e.key === 'Escape') onClose()
            }}
            className={inputClass} />
          <div className="flex flex-wrap gap-1.5">
            {tab('', 'All')}
            {groups.map((g) => tab(g, g))}
          </div>
        </header>
        <ul className="grid gap-2 overflow-y-auto p-4 sm:grid-cols-2 lg:grid-cols-3">
          {!catalogue && <li className="col-span-full h-32 animate-pulse bg-plate" aria-busy="true" />}
          {items.map(({ ability: a, blocked }) => (
            <li key={a.ability}>
              <button type="button" disabled={!!blocked} onClick={() => choose(a.ability)}
                title={blocked ?? undefined}
                aria-current={a.ability === infusedHere}
                className={`flex h-full w-full items-start gap-3 border p-2.5 text-left transition-colors ${
                  blocked ? 'cursor-not-allowed border-seam/60 opacity-45'
                    : a.ability === infusedHere ? 'border-gold bg-gold/10' : 'border-seam bg-plate hover:border-tenno'
                }`}>
                <ItemImage name={a.ability} imageName={a.imageName}
                  fallback={a.warframe === 'Helminth' ? <HelminthIcon className="size-6" /> : undefined}
                  className="size-11 shrink-0 rounded-full" />
                <span className="min-w-0 space-y-1">
                  <span className="block font-display text-[15px] font-semibold leading-tight">{a.ability}</span>
                  <span className="block text-[12px] text-mute">{a.warframe === 'Helminth' ? 'Helminth' : `from ${a.warframe}`}</span>
                  <span className="line-clamp-2 block text-[12px] leading-snug text-mute">{a.description}</span>
                  <AbilityTags tags={a.tags} />
                  {blocked && <span className="block text-[12px] leading-snug text-bad">{blocked}</span>}
                </span>
              </button>
            </li>
          ))}
          {catalogue && items.length === 0 && <li className="col-span-full p-4 text-sm text-mute">Nothing matches that search.</li>}
        </ul>
      </div>
    </div>
  )
}

/**
 * The Warframe's four abilities in slot order, with the infusion in place. Each slot
 * has a Helminth badge that opens the picker. What a click on the ability itself
 * does is up to the tab: `state(slot)` says whether it can be toggled and whether it is on.
 */
export function HelminthAbilityBar({ index, state, onToggle }: {
  index: BuildIndex
  state: (slot: SlotAbility) => { usable: boolean; active: boolean; title?: string }
  onToggle: (slot: SlotAbility) => void
}) {
  const { slots } = useSlotAbilities(index)
  const [picking, setPicking] = useState<number | null>(null)

  return (
    <>
      <ul className="grid grid-cols-4 gap-2">
        {slots.map((s) => {
          const { usable, active, title } = state(s)
          return (
            <li key={s.slot} className="relative">
              <button type="button" disabled={!usable} aria-pressed={usable ? active : undefined}
                title={title}
                onClick={() => onToggle(s)}
                className={`flex w-full flex-col items-center gap-1 border p-1.5 pt-2 text-center transition-colors ${
                  active ? 'border-gold bg-gold/10' : usable ? 'border-seam hover:border-tenno' : 'border-transparent'
                } ${s.infused ? 'ring-1 ring-inset ring-gold/40' : ''}`}>
                <span className="relative">
                  <ItemImage name={s.name} imageName={s.imageName}
                    fallback={s.infused?.warframe === 'Helminth' ? <HelminthIcon className="size-6" /> : s.slot}
                    className={`size-12 rounded-full ${active ? '' : usable ? 'opacity-70' : 'opacity-30 grayscale'}`} />
                  {s.infused && (
                    // the replaced ability, dimmed, tucked behind the infused one
                    <ItemImage name={s.original.name} imageName={s.original.imageName} fallback={s.slot}
                      className="absolute -bottom-1 -left-2 size-5 rounded-full opacity-50 grayscale ring-1 ring-void" />
                  )}
                </span>
                <span className={`text-[12px] leading-tight ${usable ? 'text-ink' : 'text-mute'}`}>{s.name}</span>
                {s.infused && (
                  <span className="text-[11px] leading-tight text-mute line-through decoration-mute/60">{s.original.name}</span>
                )}
              </button>
              <button type="button" onClick={() => setPicking(s.slot)}
                aria-label={s.infused ? `Change the Helminth ability in slot ${s.slot}` : `Infuse a Helminth ability over ${s.original.name}`}
                title={s.infused ? `Infused: ${s.infused.ability} (replaces ${s.original.name}). Click to change.` : `Infuse a Helminth ability over ${s.original.name}`}
                className={`absolute -right-1 -top-1 flex size-6 items-center justify-center rounded-full border bg-void transition-colors ${
                  s.infused ? 'border-gold text-gold' : 'border-seam text-mute hover:border-tenno hover:text-ink'
                }`}>
                <HelminthIcon className="size-3.5" />
              </button>
            </li>
          )
        })}
      </ul>
      {picking !== null && <HelminthPicker index={index} slot={picking} onClose={() => setPicking(null)} />}
    </>
  )
}
