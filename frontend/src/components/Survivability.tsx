import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useEnemies, useSurvivability, useWarframes } from '../api/queries'
import { useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { DrLayer, PassiveEffect, StatBlock, SurvivabilityResult, WarframeAbility, WarframeInfo } from '../types'
import { DAMAGE_ORDER } from '../utils/damageTypes'
import { num, pct, seconds } from '../utils/format'
import { BUILD_NAMES } from './BuildEditor'
import { Combobox } from './Combobox'
import { HelminthAbilityBar, useSlotAbilities } from './Helminth'
import type { SlotAbility } from './Helminth'
import { GridPicker, ItemButton, ItemImage } from './ItemImage'
import { ModRack } from './ModRack'
import { PresetMenu } from './PresetMenu'
import { AnimatedNumber, Bar, buttonClass, DamageChip, inputClass, Notice, Panel, Stat, Tip, Toggle } from './ui'

const ARCANE_SLOTS = [0, 1]

function useWarframe(index: BuildIndex): WarframeInfo | undefined {
  const name = useBuildStore((s) => s.builds[index].warframe)
  const { data } = useWarframes()
  return data?.warframes.find((w) => w.name === name)
}

const frameDetail = (w: WarframeInfo) =>
  `${num(w.rank30.health, 0)} health, ${num(w.rank30.shields, 0)} shields, ${num(w.rank30.armor, 0)} armor`

/** What an ability does right now, in words. */
function abilityEffect(a: WarframeAbility, strength: number, stacks: number, level: number): string {
  const scale = a.scalesWithStrength ? strength : 1
  let value: number
  if (a.stacks) value = (a.value + (a.perStack ?? 0) * stacks) * scale
  else if (a.level) value = ((a.low ?? 0) + (a.value - (a.low ?? 0)) * level) * scale
  else value = a.value * scale
  if (a.cap !== null) value = Math.min(value, a.cap)
  if (a.kind === 'dr') return `${pct(Math.min(value, 1))} damage reduction`
  if (a.kind === 'strength') return `+${pct(value)} Ability Strength`
  if (a.kind === 'armor') {
    if (a.mode === 'percent') return `+${pct(value)} armor`
    if (a.mode === 'shields') return `${pct(value)} of max shields as armor`
    return `+${num(value, 0)} armor`
  }
  return 'separate pool'
}

function AbilityRow({ index, ability, strength }: { index: BuildIndex; ability: WarframeAbility; strength: number }) {
  const state = useBuildStore((s) => s.builds[index].survival.abilities[ability.name])
  const setAbility = useBuildStore((s) => s.setAbility)
  const active = state?.active ?? false
  const stacks = state?.stacks ?? ability.stacks?.default ?? 0
  const level = state?.level ?? ability.level?.default ?? 1

  return (
    <li className={`border px-3 py-2 ${active ? 'border-gold/60 bg-gold/5' : 'border-seam'}`}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <span className="flex items-center gap-2">
          <ItemImage name={ability.name} imageName={ability.imageName}
            className={`size-9 rounded-full ${active ? '' : 'opacity-50 grayscale'}`} />
          <Toggle label={ability.name} checked={active} onChange={(on) => setAbility(index, ability.name, { active: on })} />
        </span>
        <span className="text-sm font-medium text-ink">{abilityEffect(ability, strength, stacks, level)}</span>
      </div>
      {ability.note && <p className="mt-1.5 text-[13px] leading-snug text-mute">{ability.note}</p>}
      {active && (ability.stacks || ability.level) && (
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-mute">
          {ability.stacks && (
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap">{ability.stacks.label}: {stacks}</span>
              <input type="range" min={0} max={ability.stacks.max} value={stacks}
                onChange={(e) => setAbility(index, ability.name, { stacks: Number(e.target.value) })} />
            </label>
          )}
          {ability.level && (
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap">{ability.level.label}: {pct(level, 0)}</span>
              <input type="range" min={0} max={100} value={Math.round(level * 100)}
                onChange={(e) => setAbility(index, ability.name, { level: Number(e.target.value) / 100 })} />
            </label>
          )}
        </div>
      )}
    </li>
  )
}

/** A passive effect's current value, in words. */
function passiveEffectText(kind: PassiveEffect['kind'], value: number | null, damageType: string): string {
  if (value === null) return ''
  switch (kind) {
    case 'dr': return `${pct(Math.min(value, 1))} damage reduction`
    case 'resistance': return `${pct(Math.min(value, 1))} ${damageType} resistance`
    case 'armor': return `+${num(value, 0)} armor`
    case 'health': return `+${num(value, 0)} health`
    case 'regen': return `${num(value, 1)} health/s`
    case 'shield_gate': return `${num(value, 1)} s shield gate`
    default: return ''
  }
}

const PASSIVE_TAGS: Partial<Record<PassiveEffect['kind'], string>> = {
  revive: 'Revive', note: 'Not in the numbers', regen: 'Shown only',
}

function PassiveEffectRow({ index, effect, live, damageType }: {
  index: BuildIndex
  effect: PassiveEffect
  live: SurvivabilityResult['passiveEffects'][number] | undefined
  damageType: string
}) {
  const state = useBuildStore((s) => s.builds[index].survival.passive[effect.name])
  const setPassive = useBuildStore((s) => s.setPassive)
  const conditional = effect.condition !== ''
  const on = live?.active ?? !conditional
  const stacks = state?.stacks ?? effect.stacks?.default ?? 0
  const level = state?.level ?? effect.level?.default ?? 1
  const descriptive = effect.kind === 'note' || effect.kind === 'revive'
  const tag = PASSIVE_TAGS[effect.kind]

  return (
    <li className={`border px-3 py-2 ${on && !descriptive ? 'border-gold/60 bg-gold/5' : 'border-seam'}`}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        {conditional ? (
          <Toggle label={effect.name} checked={on} onChange={(v) => setPassive(index, effect.name, { active: v })}
            tip={`Counts only when: ${effect.condition}.`} />
        ) : (
          <span className="text-sm font-medium text-ink">{effect.name}</span>
        )}
        <span className="flex items-center gap-2 text-sm">
          {tag && <span className="border border-seam px-1.5 text-[11px] uppercase tracking-wide text-mute">{tag}</span>}
          {on && <span className="font-medium text-ink">{passiveEffectText(effect.kind, live?.value ?? null, damageType)}</span>}
        </span>
      </div>
      <p className="mt-1 text-[13px] leading-snug text-mute">
        {effect.note}
        {conditional && <> Only when: {effect.condition.charAt(0).toLowerCase() + effect.condition.slice(1)}.</>}
      </p>
      {on && (effect.stacks || effect.level) && (
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-mute">
          {effect.stacks && (
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap">{effect.stacks.label}: {stacks}</span>
              <input type="range" min={0} max={effect.stacks.max} value={stacks}
                onChange={(e) => setPassive(index, effect.name, { stacks: Number(e.target.value) })} />
            </label>
          )}
          {effect.level && (
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap">{effect.level.label}: {pct(level, 0)}</span>
              <input type="range" min={0} max={100} value={Math.round(level * 100)}
                onChange={(e) => setPassive(index, effect.name, { level: Number(e.target.value) / 100 })} />
            </label>
          )}
        </div>
      )}
    </li>
  )
}

/** The Warframe's passive: its in-game text, then each effect it has on damage taken. */
function PassiveSection({ index, warframe, result }: {
  index: BuildIndex
  warframe: WarframeInfo
  result: SurvivabilityResult | undefined
}) {
  const { passive } = warframe
  const damageType = useBuildStore((s) => s.builds[index].survival.type)
  if (!passive.description && passive.effects.length === 0) return null
  return (
    <div>
      <h3 className="mb-1 text-[15px] text-gold">Passive{passive.name && `: ${passive.name}`}</h3>
      {passive.description && (
        <p className="whitespace-pre-line text-[13px] leading-snug text-mute">{passive.description}</p>
      )}
      {passive.effects.length > 0 ? (
        <ul className="mt-2 grid gap-2">
          {passive.effects.map((e) => (
            <PassiveEffectRow key={e.name} index={index} effect={e} damageType={damageType}
              live={result?.passiveEffects.find((x) => x.name === e.name)} />
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-[13px] text-mute">No effect on damage taken.</p>
      )}
    </div>
  )
}

function StatLine({ label, base, modded, color, max }: {
  label: string
  base: number
  modded: number | undefined
  color: string
  max: number
}) {
  const value = modded ?? base
  return (
    <li className="grid grid-cols-[4.5rem_1fr_auto] items-center gap-3 text-sm">
      <span className="text-mute">{label}</span>
      <Bar fraction={value / max} color={color} />
      <span className="min-w-28 text-right font-medium">
        <AnimatedNumber value={value} format={(n) => num(n, 0)} />
        {modded !== undefined && Math.abs(modded - base) > 0.5 && (
          <span className="ml-2 font-normal text-mute">from {num(base, 0)}</span>
        )}
      </span>
    </li>
  )
}

/** An ability's damage-taken effects: its own, or the infused version's when the Helminth put it there. */
function useAbilityEffects(index: BuildIndex, warframe: WarframeInfo | undefined) {
  const { slots } = useSlotAbilities(index)
  return useMemo(() => {
    // an ability can have several effects: "Warding Halo" and "Warding Halo ring", "Eclipse (Lunar)"
    const belongs = (effect: string, ability: string) => effect === ability || effect.startsWith(ability + ' ')
    const replaced = slots.find((x) => x.infused)?.original.name
    const own = (warframe?.abilities ?? []).filter((a) => !(replaced && belongs(a.name, replaced)))
    const slot = slots.find((x) => x.infused)
    // infused effects borrow the infused ability's artwork
    const infused = (slot?.infused?.survivabilityEffects ?? []).map((e) => ({ ...e, imageName: slot!.imageName }))
    const all = [...own, ...infused]
    const effectsOf = (slot: SlotAbility) =>
      slot.infused ? infused : own.filter((a) => belongs(a.name, slot.name))
    return { all, effectsOf, hasSlots: slots.length > 0 }
  }, [slots, warframe])
}

/** The four abilities in slot order. Those that change damage taken toggle; the rest are shown greyed. */
function AbilityBar({ index, warframe }: { index: BuildIndex; warframe: WarframeInfo }) {
  const states = useBuildStore((s) => s.builds[index].survival.abilities)
  const setAbility = useBuildStore((s) => s.setAbility)
  const { effectsOf } = useAbilityEffects(index, warframe)
  return (
    <HelminthAbilityBar
      index={index}
      state={(slot) => {
        const effects = effectsOf(slot)
        const usable = effects.length > 0
        return {
          usable,
          active: usable && effects.every((e) => states[e.name]?.active),
          title: usable ? effects.map((e) => e.note).filter(Boolean).join(' ') || undefined : 'No effect on damage taken',
        }
      }}
      onToggle={(slot) => {
        const effects = effectsOf(slot)
        const on = effects.every((e) => states[e.name]?.active)
        effects.forEach((e) => setAbility(index, e.name, { active: !on }))
      }}
    />
  )
}

/** One of the four ability stats: orange below 100%, green above. */
function AbilityStat({ label, value, tip }: { label: string; value: number; tip: string }) {
  const color = value < 0.995 ? 'text-gold' : value > 1.005 ? 'text-good' : 'text-ink'
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-seam/60 py-1 text-sm">
      <dt className="text-[13px] uppercase tracking-wide text-mute"><Tip text={tip}>{label}</Tip></dt>
      <dd className={`font-medium ${color}`}>{pct(value, 1)}</dd>
    </div>
  )
}

export function WarframePanel({ index }: { index: BuildIndex }) {
  const { data, error } = useWarframes()
  const selected = useBuildStore((s) => s.builds[index].warframe)
  const setWarframe = useBuildStore((s) => s.setWarframe)
  const survival = useBuildStore((s) => s.builds[index].survival)
  const updateSurvival = useBuildStore((s) => s.updateSurvival)
  const warframe = useWarframe(index)
  const effects = useAbilityEffects(index, warframe)
  const { data: result } = useSurvivability(index)
  const modded: StatBlock | undefined = result?.warframe === selected ? result.moddedStats : undefined
  const current = result?.warframe === selected ? result : undefined
  const strength = current?.abilityStrength ?? 1
  const activeNames = useBuildStore((s) => s.builds[index].survival.abilities)
  const max = Math.max(modded?.health ?? 0, modded?.shields ?? 0, modded?.armor ?? 0,
    warframe?.rank30.health ?? 0, warframe?.rank30.shields ?? 0, 1)

  const [pickingFrame, setPickingFrame] = useState(false)
  const closeFramePicker = useCallback(() => setPickingFrame(false), [])
  const [arcaneSlot, setArcaneSlot] = useState<number | null>(null)
  const closeArcanePicker = useCallback(() => setArcaneSlot(null), [])
  const frameItems = useMemo(
    () => (data?.warframes ?? []).map((w) => ({
      key: w.name, name: w.name, imageName: w.imageName, detail: frameDetail(w),
      group: w.name.endsWith(' Prime') ? 'Prime' : 'Base',
    })),
    [data],
  )
  const arcaneItems = useMemo(
    () => (data?.arcanes ?? []).map((a) => ({
      key: a.name, name: a.name, imageName: a.imageName,
      detail: `+${num(a.perRank[a.maxRank], 0)} ${a.stat === 'ARMOR_FLAT' ? 'armor' : 'health'}. ${a.note}`,
    })),
    [data],
  )

  const setArcane = (slot: number, name: string) => {
    const arcanes = [...survival.arcanes]
    if (name) {
      const info = data?.arcanes.find((a) => a.name === name)
      arcanes[slot] = { name, rank: info?.maxRank ?? 0 }
    } else {
      arcanes.splice(slot, 1)
    }
    updateSurvival(index, {
      arcanes: arcanes.filter((a, i) => a && arcanes.findIndex((b) => b?.name === a.name) === i),
    })
  }

  return (
    <Panel title="Warframe">
      <div className="space-y-4">
        {error && <Notice tone="error">{error.message}</Notice>}
        <ItemButton
          name={selected}
          imageName={warframe?.imageName}
          detail={warframe ? frameDetail(warframe) : undefined}
          placeholder="Choose a Warframe"
          label={`Warframe: ${selected}. Change Warframe`}
          onClick={() => setPickingFrame(true)}
        />
        {pickingFrame && (
          <GridPicker title="Choose a Warframe" items={frameItems} selected={selected}
            onSelect={(name) => setWarframe(index, name)} onClose={closeFramePicker} />
        )}
        {arcaneSlot !== null && (
          <GridPicker title={`Arcane for slot ${arcaneSlot + 1}`} items={arcaneItems} columns="narrow"
            selected={survival.arcanes[arcaneSlot]?.name ?? ''} allowNone="Empty slot"
            onSelect={(name) => setArcane(arcaneSlot, name)} onClose={closeArcanePicker} />
        )}
        {warframe && (
          <>
            <div>
              <div className="mb-2 flex items-baseline justify-between">
                <span className="text-[13px] text-mute">Stats at rank 30, with mods and active abilities</span>
              </div>
              <ul className="space-y-1.5">
                <StatLine label="Health" base={warframe.rank30.health} modded={modded?.health} color="var(--color-health)" max={max} />
                <StatLine label="Shields" base={warframe.rank30.shields} modded={modded?.shields} color="var(--color-shield)" max={max} />
                <StatLine label="Armor" base={warframe.rank30.armor} modded={modded?.armor} color="var(--color-armor)" max={max} />
              </ul>
              {current && current.healthRegen > 0 && (
                <p className="mt-2 text-sm text-mute">
                  Health regeneration <span className="font-medium text-ink">{num(current.healthRegen, 1)}/s</span>{' '}
                  <span className="text-[13px]">(from the passive; not part of effective health)</span>
                </p>
              )}
              {warframe.statsNote && <p className="mt-2 text-[13px] text-mute">{warframe.statsNote}</p>}
            </div>

            <dl>
              <AbilityStat label="Duration" value={current?.abilityDuration ?? 1}
                tip="How long abilities last, from your mods. Shown for reference; it doesn't change the numbers here." />
              <AbilityStat label="Efficiency" value={current?.abilityEfficiency ?? 1}
                tip="Energy cost of abilities, from your mods. Capped between 25% and 175%. Shown for reference." />
              <AbilityStat label="Range" value={current?.abilityRange ?? 1}
                tip="Reach of abilities, from your mods. Shown for reference." />
              <AbilityStat label="Strength" value={strength}
                tip="From your mods plus any extra you enter below. It scales most ability damage reduction, armor bonuses and Overguard." />
            </dl>

            <label className="flex flex-wrap items-center gap-3 text-sm text-mute">
              <Tip text="Ability Strength from sources the calculator doesn't model: Archon Shards, squad buffs, Molt Augmented and so on.">
                Extra Ability Strength
              </Tip>
              <input
                type="number" step={5} min={-100} max={1000}
                aria-label="Extra Ability Strength, percent"
                value={Math.round(survival.extraStrength * 100)}
                onChange={(e) => updateSurvival(index, { extraStrength: (Number(e.target.value) || 0) / 100 })}
                className={`${inputClass} !w-24`}
              />
              <span>%</span>
            </label>

            <div>
              <h3 className="mb-2 text-[15px] text-gold">Abilities</h3>
              <AbilityBar index={index} warframe={warframe} />
              {effects.all.length === 0 ? (
                <p className="mt-2 text-sm text-mute">
                  None of this Warframe's abilities reduce damage, add armor or add a pool. Its survivability is
                  health, shields, armor and mods.
                </p>
              ) : (
                <>
                  <p className="mt-2 text-[13px] text-mute">
                    Click an ability to switch its effect on. Greyed abilities don't change damage taken. The
                    flower badge infuses a Helminth ability over that slot.
                  </p>
                  <ul className="mt-2 grid gap-2">
                    {effects.all.filter((a) => activeNames[a.name]?.active).map((a) => (
                      <AbilityRow key={a.name} index={index} ability={a} strength={strength} />
                    ))}
                  </ul>
                </>
              )}
            </div>

            <PassiveSection index={index} warframe={warframe} result={current} />

            <div>
              <h3 className="mb-2 text-[15px] text-gold">Arcanes</h3>
              <div className="grid gap-2">
                {ARCANE_SLOTS.map((slot) => {
                  const current = survival.arcanes[slot]
                  const info = data?.arcanes.find((a) => a.name === current?.name)
                  return (
                    <button
                      key={slot}
                      type="button"
                      onClick={() => setArcaneSlot(slot)}
                      className="flex items-center gap-3 border border-seam bg-void p-2 text-left hover:border-tenno"
                    >
                      <ItemImage name={current?.name ?? `Slot ${slot + 1}`} imageName={info?.imageName}
                        fallback={slot + 1} className="size-12 rounded-full" />
                      <span className="min-w-0">
                        <span className="block truncate font-display font-semibold">{current?.name ?? `Arcane slot ${slot + 1}`}</span>
                        <span className="block text-[13px] leading-snug text-mute">
                          {info
                            ? `Rank ${info.maxRank}: +${num(info.perRank[info.maxRank], 0)} ${info.stat === 'ARMOR_FLAT' ? 'armor' : 'health'}`
                            : 'Empty. Click to choose.'}
                        </span>
                      </span>
                    </button>
                  )
                })}
              </div>
              <p className="mt-2 text-[13px] text-mute">Only arcanes that add armor or health are listed. They count as active.</p>
            </div>
          </>
        )}
      </div>
    </Panel>
  )
}

export function IncomingPanel({ index }: { index: BuildIndex }) {
  const survival = useBuildStore((s) => s.builds[index].survival)
  const updateSurvival = useBuildStore((s) => s.updateSurvival)
  const enemyKey = useBuildStore((s) => s.builds[index].enemyKey)
  const enemyLevel = useBuildStore((s) => s.builds[index].enemyLevel)
  const steelPath = useBuildStore((s) => s.builds[index].steelPath)
  const update = useBuildStore((s) => s.update)
  const setEnemy = useBuildStore((s) => s.setEnemy)
  const { data: enemies = [] } = useEnemies()
  const { data: result } = useSurvivability(index)
  const fromEnemy = survival.source === 'enemy'
  const selectedEnemy = enemies.find((e) => e.key === enemyKey)

  const number = (label: string, value: number, onChange: (n: number) => void, step: number, min: number) => (
    <label className="block">
      <span className="mb-1 block text-[13px] text-mute">{label}</span>
      <input type="number" min={min} step={step} value={value}
        onChange={(e) => onChange(Math.max(min, Number(e.target.value) || 0))} className={inputClass} />
    </label>
  )

  return (
    <Panel title="Incoming damage">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Toggle label="A number I enter" checked={!fromEnemy} onChange={() => updateSurvival(index, { source: 'custom' })} />
          <Toggle label="An enemy, scaled by level" checked={fromEnemy} onChange={() => updateSurvival(index, { source: 'enemy' })}
            tip="Scales a base damage figure by the enemy's level and faction." />
        </div>

        {fromEnemy && (
          <div className="space-y-3">
            <Combobox
              label="Search enemies"
              items={enemies}
              getKey={(e) => e.key}
              getText={(e) => e.name}
              renderItem={(e) => (
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate font-medium">{e.name}</span>
                  <span className="shrink-0 text-[13px] text-mute">{e.faction}, base level {e.baseLevel}</span>
                </div>
              )}
              selectedText={selectedEnemy?.name ?? enemyKey}
              onSelect={(e) => setEnemy(index, e.key)}
              emptyText="No enemy matches that search."
            />
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-28">{number('Enemy level', enemyLevel, (n) => update(index, { enemyLevel: Math.round(n) }), 5, 1)}</div>
              <Toggle label="Steel Path" checked={steelPath} onChange={(on) => update(index, { steelPath: on })}
                tip="Adds 100 levels." />
            </div>
            <p className="text-[13px] leading-snug text-mute">
              The game data has no enemy weapon damage, so enter the enemy's base damage per hit below (what it
              deals at its base level). It is then scaled by level and by its faction's attack multiplier
              {result?.enemyName ? `: ×${num(result.enemyDamageMultiplier, 2)} for ${result.enemyName} here.` : '.'}
            </p>
          </div>
        )}

        <div className="grid grid-cols-3 gap-3">
          {number(fromEnemy ? 'Base damage per hit' : 'Damage per hit', survival.amount, (n) => updateSurvival(index, { amount: n }), 50, 0)}
          <label className="block">
            <span className="mb-1 block text-[13px] text-mute">Damage type</span>
            <select value={survival.type} onChange={(e) => updateSurvival(index, { type: e.target.value })}
              className={inputClass} aria-label="Damage type">
              {DAMAGE_ORDER.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          {number('Hits per second', survival.hitsPerSecond, (n) => updateSurvival(index, { hitsPerSecond: n || 0.1 }), 0.5, 0.1)}
        </div>
        <p className="text-[13px] leading-snug text-mute">
          The damage type matters for Toxin (bypasses shields), elemental resistance mods, and abilities that
          only block some types.
        </p>
      </div>
    </Panel>
  )
}

/** Green for strong layers, gold for middling, red for weak. */
function layerColor(reduction: number): string {
  if (reduction > 0.7) return 'var(--color-good)'
  if (reduction >= 0.3) return 'var(--color-gold)'
  return 'var(--color-bad)'
}

function BreakdownTable({ result: r }: { result: SurvivabilityResult }) {
  const rows: DrLayer[] = r.layers
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[30rem] text-sm">
        <thead>
          <tr className="text-left text-[13px] text-mute">
            <th className="pb-2 font-normal">Layer</th>
            <th className="pb-2 text-right font-normal">Reduces by</th>
            <th className="pb-2 text-right font-normal">Damage after</th>
            <th className="pb-2 text-right font-normal">Total so far</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-seam">
            <td className="py-2">
              <span className="flex items-center gap-2">Incoming hit <DamageChip type={r.damageType} /></span>
            </td>
            <td />
            <td className="py-2 text-right font-medium">{num(r.incomingPerHit)}</td>
            <td />
          </tr>
          {rows.map((l) => (
            <tr key={l.name} className="border-t border-seam align-top">
              <td className="py-2">
                <span className="flex items-center gap-2">
                  <span className="size-2 shrink-0 rotate-45" style={{ background: layerColor(l.reduction) }} aria-hidden />
                  {l.name}
                </span>
                <span className="mt-1 block h-1 bg-plate pl-0" aria-hidden>
                  <span className="block h-full" style={{ width: pct(l.reduction), background: layerColor(l.reduction) }} />
                </span>
                {l.note && <span className="mt-1 block pl-4 text-[13px] leading-snug text-mute">{l.note}</span>}
              </td>
              <td className="py-2 text-right font-medium" style={{ color: layerColor(l.reduction) }}>{pct(l.reduction)}</td>
              <td className="py-2 text-right">{num(l.damageAfter)}</td>
              <td className="py-2 text-right font-display text-base font-semibold text-gold-pale">{pct(l.cumulative, 2)}</td>
            </tr>
          ))}
          <tr className="border-t-2 border-seam-bright">
            <td className="py-2 font-medium">Damage to health per hit</td>
            <td />
            <td className="py-2 text-right font-display text-lg font-semibold text-ink">{num(r.damagePerHit)}</td>
            <td className="py-2 text-right font-display text-lg font-semibold text-gold-pale">{pct(r.totalDr, 2)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function Delta({ mine, theirs }: { mine: number | null; theirs: number | null | undefined }) {
  if (mine === null || theirs === null || theirs === undefined || theirs === 0) return null
  const change = mine / theirs - 1
  if (Math.abs(change) < 0.0005) return null
  return (
    <span className={`block font-sans text-[13px] font-medium ${change > 0 ? 'text-good' : 'text-bad'}`}>
      {change >= 10 ? `${num(mine / theirs)}× the other` : `${change > 0 ? '+' : '−'}${pct(Math.abs(change))}`}
    </span>
  )
}

function Big({ label, tip, children }: { label: string; tip: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[13px] text-mute"><Tip text={tip}>{label}</Tip></dt>
      <dd className="font-display text-[26px] font-semibold leading-tight text-ink">{children}</dd>
    </div>
  )
}

const ehp = (n: number | null) => (n === null ? '∞' : num(n, 0))

export function SurvivabilityResults({ index, compareWith }: { index: BuildIndex; compareWith?: BuildIndex }) {
  const { data: r, error, isPlaceholderData } = useSurvivability(index)
  const otherQuery = useSurvivability(compareWith ?? index)
  const other = compareWith === undefined ? undefined : otherQuery.data

  const parts = useMemo(() => {
    if (!r) return []
    return [
      { label: 'Health', value: r.healthEhp, color: 'var(--color-health)' },
      { label: 'Shields', value: r.shieldEhp, color: 'var(--color-shield)' },
      ...r.pools.map((p) => ({ label: p.name, value: p.ehp, color: 'var(--color-overguard)' })),
    ].filter((p) => p.value === null || p.value > 0)
  }, [r])
  const total = r?.totalEhp ?? null

  return (
    <Panel title="Results">
      {error && <Notice tone="error">{error.message}</Notice>}
      {!error && !r && <div className="h-40 animate-pulse bg-plate" aria-busy="true" aria-label="Calculating" />}
      {!error && r && (
        <div className={`@container space-y-6 transition-opacity ${isPlaceholderData ? 'opacity-70' : ''}`}>
          <dl className="grid grid-cols-2 gap-4 @2xl:grid-cols-4">
            <Big label="Effective health" tip="Raw incoming damage this Warframe can absorb before dying: health behind armor and other reductions, shields at their 50% reduction, and any Overguard or ability pool.">
              {ehp(r.totalEhp)}
              <Delta mine={r.totalEhp} theirs={other?.totalEhp} />
            </Big>
            <Big label="Damage reduction" tip="Share of a hit to health that every layer together removes.">
              {pct(r.totalDr, 2)}
            </Big>
            <Big label="Health lost per hit" tip="Damage one hit does to health after every layer.">
              {num(r.damagePerHit)}
              <Delta mine={other?.damagePerHit ?? null} theirs={r.damagePerHit} />
            </Big>
            <Big label="Time to die" tip="Effective health divided by incoming damage per second. Ignores shield gating, shield recharge and healing, so real survival is longer.">
              {r.timeToKill === null ? '∞' : seconds(r.timeToKill)}
              <Delta mine={r.timeToKill} theirs={other?.timeToKill} />
            </Big>
          </dl>

          <section>
            <h3 className="mb-2 text-[15px] text-gold">Where each hit goes</h3>
            <BreakdownTable result={r} />
            <p className="mt-2 text-[13px] leading-snug text-mute">
              Each layer removes its share of what the layers above let through, so the order doesn't change the
              result. Shields take {pct(r.shieldDr)} less ({num(r.shieldDamagePerHit)} per hit): they ignore armor
              but have a built-in 50% reduction.
            </p>
          </section>

          <section>
            <h3 className="mb-2 text-[15px] text-gold">Effective health by pool</h3>
            <ul className="space-y-1.5">
              {parts.map((p) => (
                <li key={p.label} className="grid grid-cols-[minmax(6rem,12rem)_1fr_auto] items-center gap-3 text-sm">
                  <span className="truncate text-mute">{p.label}</span>
                  <Bar fraction={p.value === null || total === null ? 1 : p.value / total} color={p.color} />
                  <span className="min-w-20 text-right font-medium">{ehp(p.value)}</span>
                </li>
              ))}
            </ul>
            <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
              <Stat label="Health" tip="After mods and arcanes.">{num(r.moddedStats.health, 0)}</Stat>
              <Stat label="Shields">{num(r.moddedStats.shields, 0)}</Stat>
              <Stat label="Armor" tip="Warframe armor reduces health damage by armor ÷ (armor + 300). It has no cap.">
                {num(r.moddedStats.armor, 0)} <span className="text-sm font-normal text-mute">({pct(r.armorDr)})</span>
              </Stat>
              <Stat label="Shield gate" tip="Invulnerability each time full shields break, by maximum shields.">
                {r.shieldGateSeconds > 0 ? `${r.shieldGateSeconds.toFixed(2)} s` : '—'}
              </Stat>
            </dl>
          </section>

          {r.notes.length > 0 && (
            <section>
              <h3 className="mb-2 text-[15px] text-gold">Notes</h3>
              <ul className="space-y-1 text-[13px] leading-snug text-mute">
                {r.notes.map((n) => <li key={n}>{n}</li>)}
              </ul>
            </section>
          )}
        </div>
      )}
    </Panel>
  )
}

/** One Warframe build: the frame and what is hitting it on the left, its mods beside them. */
export function SurvivabilityEditor({ index, compareWith, results = true }: {
  index: BuildIndex
  compareWith?: BuildIndex
  /** False when the page shows the results full width underneath. */
  results?: boolean
}) {
  const copyBuild = useBuildStore((s) => s.copyBuild)
  return (
    <div className="@container space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg text-gold-pale">{compareWith === undefined ? 'Your Warframe' : BUILD_NAMES[index]}</h2>
        <div className="flex gap-2">
          {compareWith !== undefined && (
            <button type="button" className={buttonClass} onClick={() => copyBuild(compareWith, index)}>
              Copy from {BUILD_NAMES[compareWith]}
            </button>
          )}
          <PresetMenu index={index} />
        </div>
      </div>
      <div className="grid items-start gap-4 @5xl:grid-cols-[23rem_minmax(0,1fr)]">
        <WarframePanel index={index} />
        <div className="min-w-0 space-y-4">
          <ModRack index={index} warframe />
          <IncomingPanel index={index} />
        </div>
      </div>
      {results && <SurvivabilityResults index={index} compareWith={compareWith} />}
    </div>
  )
}
