import { useMemo, useState } from 'react'
import { useCalculation, useEffectiveBuild, useEnemies, useScaledEnemy } from '../api/queries'
import { useBuildStore, usesSharedEnemy } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { EnemySummary, ScaledEnemy } from '../types'
import { num, pct, titleCase } from '../utils/format'
import { Combobox, FilterSelect } from './Combobox'
import { AnimatedNumber, Bar, Counter, DamageChip, Notice, Panel, Tip, Toggle } from './ui'

const MAX_LEVEL = 9999
const SLIDER_STEPS = 1000

// The level slider is logarithmic: most play happens below level 200, but
// endurance runs reach the thousands.
const levelToSlider = (level: number) =>
  Math.round((Math.log(level) / Math.log(MAX_LEVEL)) * SLIDER_STEPS)
const sliderToLevel = (pos: number) =>
  Math.max(1, Math.min(MAX_LEVEL, Math.round(Math.exp((pos / SLIDER_STEPS) * Math.log(MAX_LEVEL)))))

const enemyKey = (e: EnemySummary) => e.key
const enemyText = (e: EnemySummary) => e.name

function EnemyRow(e: EnemySummary) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="truncate font-medium">
        {e.name}
        {e.variantType !== 'STANDARD' && (
          <span className="ml-2 text-[13px] font-normal text-gold">{titleCase(e.variantType)}</span>
        )}
      </span>
      <span className="shrink-0 text-[13px] text-mute">{e.faction}</span>
    </div>
  )
}

export function EnemyPicker({ index }: { index: BuildIndex }) {
  const { data: enemies = [], error } = useEnemies()
  const selectedKey = useBuildStore((s) => s.builds[index].enemyKey)
  const recentKeys = useBuildStore((s) => s.recentEnemies)
  const setEnemy = useBuildStore((s) => s.setEnemy)
  const [faction, setFaction] = useState('')

  const factions = useMemo(() => [...new Set(enemies.map((e) => e.faction))].sort(), [enemies])
  const items = useMemo(
    () => (faction ? enemies.filter((e) => e.faction === faction) : enemies),
    [enemies, faction],
  )
  const recent = useMemo(
    () => recentKeys
      .map((k) => items.find((e) => e.key === k))
      .filter((e): e is EnemySummary => !!e),
    [recentKeys, items],
  )
  const selected = enemies.find((e) => e.key === selectedKey)

  if (error) return <Notice tone="error">{error.message}</Notice>

  return (
    <Combobox
      label="Search enemies"
      items={items}
      getKey={enemyKey}
      getText={enemyText}
      renderItem={EnemyRow}
      selectedText={selected?.name ?? selectedKey.split('|')[0]}
      onSelect={(e) => setEnemy(index, e.key)}
      recent={recent}
      emptyText="No enemy matches that search."
      filter={
        <FilterSelect
          label="Faction"
          value={faction}
          onChange={setFaction}
          options={[
            { value: '', label: 'All factions' },
            ...factions.map((f) => ({ value: f, label: f })),
          ]}
        />
      }
    />
  )
}

export function EnemyConfig({ index }: { index: BuildIndex }) {
  const build = useBuildStore((s) => s.builds[index])
  const update = useBuildStore((s) => s.update)
  const set = (patch: Parameters<typeof update>[1]) => update(index, patch)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <label className="block">
          <span className="mb-1 block text-[13px] text-mute">Level</span>
          <input
            type="number"
            min={1}
            max={MAX_LEVEL}
            value={build.enemyLevel}
            onChange={(e) => {
              const n = Math.round(Number(e.target.value))
              if (Number.isFinite(n)) set({ enemyLevel: Math.min(MAX_LEVEL, Math.max(1, n)) })
            }}
            className="w-20 border border-seam bg-void px-2 py-1.5 text-center font-display text-base font-semibold focus:border-tenno focus:outline-none"
          />
        </label>
        <input
          type="range"
          aria-label="Enemy level"
          min={0}
          max={SLIDER_STEPS}
          value={levelToSlider(build.enemyLevel)}
          onChange={(e) => set({ enemyLevel: sliderToLevel(Number(e.target.value)) })}
          className="mb-2 min-w-32 flex-1"
        />
        <Toggle
          label="Steel Path"
          checked={build.steelPath}
          onChange={(v) => set({ steelPath: v })}
          tip="Adds 100 levels and multiplies shields by 2.5."
        />
        <Toggle
          label="Eximus"
          checked={build.eximus}
          onChange={(v) => set({ eximus: v })}
          tip="Eximus units have more health and shields, and a layer of Overguard."
        />
      </div>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <label className="block min-w-44 flex-1">
          <span className="mb-1 flex justify-between text-[13px] text-mute">
            <Tip text="Share of the enemy's armor removed before you shoot, from abilities or Corrosive and Heat procs.">
              Armor stripped
            </Tip>
            <span className="text-ink">{pct(build.armorStripPct, 0)}</span>
          </span>
          <input
            type="range"
            aria-label="Armor stripped"
            min={0}
            max={100}
            value={Math.round(build.armorStripPct * 100)}
            onChange={(e) => set({ armorStripPct: Number(e.target.value) / 100 })}
            className="w-full"
          />
        </label>
        <Counter
          label="Viral stacks"
          tip="Viral procs on the target. One stack doubles damage to health; ten stacks give +325%."
          value={build.viralStacks}
          min={0}
          max={10}
          onChange={(v) => set({ viralStacks: v })}
        />
        <Counter
          label="Status types"
          tip="Different status effects on the target. Condition Overload and Galvanized mods multiply damage for each one."
          value={build.statusTypes}
          min={0}
          max={10}
          onChange={(v) => set({ statusTypes: v })}
        />
      </div>
    </div>
  )
}

function DefenseRow({ label, value, fraction, color, note, tip }: {
  label: string
  value: number
  fraction: number
  color: string
  note?: string
  tip: string
}) {
  return (
    <li className="grid grid-cols-[5.5rem_1fr_auto] items-center gap-3 text-sm">
      <span className="text-mute"><Tip text={tip}>{label}</Tip></span>
      <Bar fraction={fraction} color={color} />
      <span className="min-w-20 text-right font-medium">
        <AnimatedNumber value={value} format={(n) => num(n, 0)} />
        {note && <span className="ml-2 font-normal text-mute">{note}</span>}
      </span>
    </li>
  )
}

export function EnemyStatCard({ enemy, afterBuffs }: {
  enemy: ScaledEnemy
  /** The same enemy once armor-stripping buffs have been applied, when that differs. */
  afterBuffs?: ScaledEnemy
}) {
  const pool = Math.max(enemy.health, enemy.shield, enemy.overguard, 1)
  const weak = Object.entries(enemy.factionModifiers).filter(([, m]) => m > 1)
  const resist = Object.entries(enemy.factionModifiers).filter(([, m]) => m < 1)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-sm text-mute">
          <span className="font-medium text-ink">{enemy.faction}</span>, level {enemy.currentLevel}
          {enemy.isSteelPath && ' with Steel Path'}
        </p>
        <p className="text-sm text-mute">
          <Tip align="right" text="Effective health: how much neutral damage it takes to kill, counting armor, shields and Overguard.">
            Effective health
          </Tip>
          <span className="ml-2 font-display text-xl font-semibold text-gold-pale">
            <AnimatedNumber value={enemy.ehp} format={(n) => num(n, 0)} />
          </span>
        </p>
      </div>

      <ul className="space-y-1.5">
        <DefenseRow label="Health" value={enemy.health} fraction={enemy.health / pool}
          color="var(--color-health)" tip="Health at this level. Armor reduces damage dealt to it." />
        {enemy.shield > 0 && (
          <DefenseRow label="Shield" value={enemy.shield} fraction={enemy.shield / pool}
            color="var(--color-shield)" tip="Shields absorb damage before health and ignore armor. Toxin bypasses them." />
        )}
        {enemy.overguard > 0 && (
          <DefenseRow label="Overguard" value={enemy.overguard} fraction={enemy.overguard / pool}
            color="var(--color-overguard)" tip="Overguard sits on top of shields and health on Eximus units." />
        )}
        <DefenseRow label="Armor" value={enemy.armor} fraction={enemy.armor / 2700}
          color="var(--color-armor)" note={`${pct(enemy.armorDr)} reduction`}
          tip="Armor reduces damage to health. It caps at 2,700, which is 90% reduction." />
        {afterBuffs && (
          <DefenseRow label="After buffs" value={afterBuffs.armor} fraction={afterBuffs.armor / 2700}
            color="var(--color-armor)" note={`${pct(afterBuffs.armorDr)} reduction`}
            tip="Armor left once your armor-stripping buffs (Caustic Strike, Sharpened Claws, Vicious Bond) have been applied. Results use this figure." />
        )}
      </ul>

      {(weak.length > 0 || resist.length > 0) && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          {weak.length > 0 && (
            <p className="flex flex-wrap items-center gap-x-3">
              <span className="text-mute">Weak to (+50%)</span>
              {weak.map(([t]) => <DamageChip key={t} type={t} />)}
            </p>
          )}
          {resist.length > 0 && (
            <p className="flex flex-wrap items-center gap-x-3">
              <span className="text-mute">Resists (−50%)</span>
              {resist.map(([t]) => <DamageChip key={t} type={t} />)}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function EnemyPanel({ index }: { index: BuildIndex }) {
  const shared = useBuildStore((s) => usesSharedEnemy(s, index))
  const { enemyKey: key } = useEffectiveBuild(index)
  const { data: enemy, error } = useScaledEnemy(index)
  // The calculation's enemy has buff armor strip applied; this panel's own figure does not.
  const { data: result } = useCalculation(index)
  const afterBuffs = result && enemy && result.enemy.name === enemy.name
    && result.enemy.currentLevel === enemy.currentLevel
    && result.enemy.armor < result.armorBeforeBuffs - 0.5
    ? result.enemy
    : undefined

  return (
    <Panel title="Enemy">
      <div className="space-y-4">
        {shared ? (
          <Notice>
            Fighting the same enemy as Build A. Turn off “Same enemy” in the header to set a different one.
          </Notice>
        ) : (
          <>
            <EnemyPicker index={index} />
            <EnemyConfig index={index} />
          </>
        )}
        {error && <Notice tone="error">{error.message}</Notice>}
        {enemy && !error && <EnemyStatCard key={key} enemy={enemy} afterBuffs={afterBuffs} />}
        {!enemy && !error && <div className="h-28 animate-pulse bg-plate" />}
      </div>
    </Panel>
  )
}
