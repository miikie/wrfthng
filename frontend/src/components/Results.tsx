import type { ReactNode } from 'react'
import { useCalculation, useWeapons } from '../api/queries'
import { useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { CalculationResult, SideResult } from '../types'
import { critTier, damageColor, sortDamage } from '../utils/damageTypes'
import { mult, num, pct, seconds } from '../utils/format'
import { FilterSelect } from './Combobox'
import { AnimatedNumber, DamageChip, Notice, Panel, Stat, Tip, Toggle } from './ui'

/** Percentage difference from the other build, coloured by which is better. */
function Delta({ mine, theirs, lowerIsBetter = false, block = false }: {
  mine: number
  theirs: number | undefined
  lowerIsBetter?: boolean
  block?: boolean
}) {
  const layout = block ? 'block' : 'ml-2'
  if (theirs === undefined || !Number.isFinite(mine) || !Number.isFinite(theirs) || theirs === 0) return null
  const change = mine / theirs - 1
  if (Math.abs(change) < 0.0005) {
    return <span className={`${layout} font-sans text-[13px] font-normal text-mute`}>same as other build</span>
  }
  const better = lowerIsBetter ? change < 0 : change > 0
  return (
    <span className={`${layout} whitespace-nowrap font-sans text-[13px] font-medium ${better ? 'text-good' : 'text-bad'}`}>
      {/* Past +1000% a percentage stops being readable, so show the ratio. */}
      {change >= 10 ? `${num(mine / theirs)}× the other` : `${change > 0 ? '+' : '−'}${pct(Math.abs(change))}`}
    </span>
  )
}

function Section({ title, children, className = '' }: {
  title: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`bg-hull p-4 ${className}`}>
      <h3 className="mb-3 text-[15px] text-gold">{title}</h3>
      {children}
    </section>
  )
}

function Headline({ label, tip, value, format, delta }: {
  label: string
  tip: string
  value: number
  format: (n: number) => string
  delta?: ReactNode
}) {
  return (
    <div>
      <dt className="text-[13px] text-mute"><Tip text={tip}>{label}</Tip></dt>
      <dd className="whitespace-nowrap font-display text-[26px] font-semibold leading-tight text-ink">
        <AnimatedNumber value={value} format={format} />
        {delta}
      </dd>
    </div>
  )
}

interface Shared {
  result: CalculationResult
  other?: CalculationResult
  isMelee: boolean
}

export function DPSDisplay({ result: r, other, isMelee }: Shared) {
  const reloading = 1 - r.dps.shootRatio
  const circumference = 2 * Math.PI * 15
  return (
    <Section title="Damage per second">
      <dl className="grid grid-cols-3 gap-4">
        <Headline
          label={isMelee ? 'Average hit' : 'Average shot'}
          tip="Damage of one trigger pull against this enemy, averaged over critical hits and including multishot."
          value={r.dps.averageShot}
          format={num}
          delta={<Delta block mine={r.dps.averageShot} theirs={other?.dps.averageShot} />}
        />
        <Headline
          label="Burst"
          tip="Damage per second while firing, ignoring reloads."
          value={r.dps.burstDps}
          format={num}
          delta={<Delta block mine={r.dps.burstDps} theirs={other?.dps.burstDps} />}
        />
        <Headline
          label="Sustained"
          tip="Damage per second over a long fight, including time spent reloading."
          value={r.dps.sustainedDps}
          format={num}
          delta={<Delta block mine={r.dps.sustainedDps} theirs={other?.dps.sustainedDps} />}
        />
      </dl>

      {r.averaged && (
        <p className="mt-3 border-l-2 border-tenno bg-plate px-3 py-2 text-sm text-mute">
          The figures above have every buff on. Averaged over the time each buff is actually up:{' '}
          <span className="font-medium text-ink">{num(r.averaged.burstDps)}</span> burst,{' '}
          <span className="font-medium text-ink">{num(r.averaged.sustainedDps)}</span> sustained.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-x-5 gap-y-3 border-t border-seam pt-3">
        <dl className="flex flex-wrap gap-x-6 gap-y-2 whitespace-nowrap">
          <Stat label={isMelee ? 'Attack speed' : 'Fire rate'} tip="After mods. Charge and burst triggers are converted to an effective rate.">
            {num(r.dps.effectiveFireRate, 2)}
          </Stat>
          <Stat label="Multishot" tip="Average projectiles per shot after mods.">{num(r.moddedMultishot, 2)}</Stat>
          {!isMelee && (
            <>
              <Stat label="Magazine" tip="Shots per magazine after mods.">{r.dps.shotsPerMag === null ? '—' : r.moddedMagSize}</Stat>
              <Stat label="Reload" tip="Reload time after mods.">{r.moddedReloadTime ? `${num(r.moddedReloadTime, 2)} s` : '—'}</Stat>
            </>
          )}
        </dl>
        {!isMelee && r.dps.shotsPerMag !== null && (
          <div className="flex items-center gap-2" title="Share of time spent firing versus reloading.">
            <svg viewBox="0 0 36 36" className="size-11 -rotate-90" role="img"
              aria-label={`Firing ${pct(r.dps.shootRatio, 0)} of the time`}>
              <circle cx="18" cy="18" r="15" fill="none" stroke="var(--color-seam)" strokeWidth="5" />
              <circle cx="18" cy="18" r="15" fill="none" stroke="var(--color-gold)" strokeWidth="5"
                strokeDasharray={`${r.dps.shootRatio * circumference} ${circumference}`} />
            </svg>
            <p className="text-[13px] leading-tight text-mute">
              <span className="text-ink">{pct(r.dps.shootRatio, 0)}</span> firing<br />
              <span className="text-ink">{pct(reloading, 0)}</span> reloading
            </p>
          </div>
        )}
      </div>
    </Section>
  )
}

export function KillEstimate({ result: r, other, isMelee }: Shared) {
  return (
    <Section title="Time to kill">
      <dl className="space-y-3">
        <Headline
          label={`${r.enemyName}, level ${r.enemyLevel}`}
          tip="Effective health divided by sustained damage per second. Ignores shield gating, damage over time and overkill."
          value={r.timeToKill}
          format={seconds}
          delta={<Delta block mine={r.timeToKill} theirs={other?.timeToKill} lowerIsBetter />}
        />
        <div className="grid grid-cols-2 gap-3">
          <Stat label={isMelee ? 'Hits to kill' : 'Shots to kill'} tip="Effective health divided by average damage per shot.">
            {r.shotsToKill > 0 ? num(Math.ceil(r.shotsToKill), 0) : '—'}
            <Delta block mine={r.shotsToKill} theirs={other?.shotsToKill} lowerIsBetter />
          </Stat>
          <Stat label="Effective health" tip="Enemy health after armor, plus shields and Overguard.">
            {num(r.enemyEhp, 0)}
          </Stat>
        </div>
      </dl>
    </Section>
  )
}

export function CritDisplay({ result: r }: Shared) {
  const c = r.crit
  const guaranteed = critTier(c.guaranteedTier)
  const next = critTier(c.guaranteedTier + 1)
  const top = c.nextTierChance > 1e-9 ? next : guaranteed
  return (
    <Section title="Critical hits">
      <p className="mb-3 font-display text-xl font-semibold" style={{ color: top.color }}>
        {top.name}
        <span className="ml-2 text-base font-medium text-ink">{pct(c.moddedCritChance)} chance</span>
      </p>
      <dl className="grid grid-cols-2 gap-3">
        <Stat label="Crit multiplier" tip="Multiplier of a first-tier critical hit after mods. Each tier above adds this bonus again.">
          {mult(c.moddedCritMult)}
        </Stat>
        <Stat label="Average multiplier" tip="Expected damage multiplier per hit across all crit outcomes. This is what DPS uses.">
          {mult(c.averageMult)}
        </Stat>
        <Stat label={`${guaranteed.name}: ${pct(1 - c.nextTierChance, 0)}`} tip="The tier every hit reaches at minimum, and its damage multiplier.">
          <span style={{ color: guaranteed.color }}>{mult(c.normalShotMult)}</span>
        </Stat>
        <Stat label={`${next.name}: ${pct(c.nextTierChance, 0)}`} tip="Chance to roll one tier higher, and that tier's damage multiplier.">
          <span style={{ color: next.color }}>{mult(c.critShotMult)}</span>
        </Stat>
      </dl>
    </Section>
  )
}

export function DamageBreakdown({ result: r }: Shared) {
  const rows = sortDamage(Object.entries(r.damage.perType)).filter(([, v]) => v !== 0)
  const totalInflicted = r.damage.totalInflicted
  return (
    <Section title="Damage by type">
      {rows.length === 0 ? (
        <Notice>This weapon deals no damage in the game data.</Notice>
      ) : (
        <>
          <div className="mb-3 flex h-3 w-full gap-px" role="img" aria-label="Share of damage dealt to this enemy by type">
            {rows.map(([type]) => (
              <div
                key={type}
                title={`${type}: ${pct((r.damage.perTypeInflicted[type] ?? 0) / totalInflicted)}`}
                className="h-full transition-[flex-grow] duration-300"
                style={{
                  flexGrow: (r.damage.perTypeInflicted[type] ?? 0) / totalInflicted,
                  flexBasis: 0,
                  background: damageColor(type),
                }}
              />
            ))}
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[13px] text-mute">
                <th className="pb-1 font-normal">Type</th>
                <th className="pb-1 text-right font-normal">
                  <Tip align="right" text="Damage of one non-critical hit after mods, before the enemy's defenses.">Modded</Tip>
                </th>
                <th className="pb-1 text-right font-normal">
                  <Tip align="right" text="After this enemy's armor, faction weaknesses and faction mods. Before crits, Viral and multishot.">Dealt</Tip>
                </th>
                <th className="pb-1 text-right font-normal">Share</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([type, value]) => {
                const dealt = r.damage.perTypeInflicted[type] ?? 0
                const modifier = r.enemy.factionModifiers[type]
                return (
                  <tr key={type} className="border-t border-seam">
                    <td className="py-1">
                      <DamageChip type={type} />
                      {modifier && modifier !== 1 && (
                        <span className={`ml-2 text-[13px] ${modifier > 1 ? 'text-good' : 'text-bad'}`}>
                          {modifier > 1 ? 'weak' : 'resists'}
                        </span>
                      )}
                    </td>
                    <td className="py-1 text-right">{num(value, 2)}</td>
                    <td className="py-1 text-right">{num(dealt, 2)}</td>
                    <td className="py-1 text-right text-mute">{pct(dealt / totalInflicted)}</td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr className="border-t border-seam-bright font-semibold">
                <td className="pt-1.5">Total per hit</td>
                <td className="pt-1.5 text-right">{num(r.damage.total, 2)}</td>
                <td className="pt-1.5 text-right">{num(totalInflicted, 2)}</td>
                <td />
              </tr>
            </tfoot>
          </table>
          {(r.viralDamageBonus > 0 || r.conditionOverloadMult > 1) && (
            <p className="mt-3 text-[13px] text-mute">
              {r.viralDamageBonus > 0 && <>Viral adds <span className="text-ink">+{pct(r.viralDamageBonus, 0)}</span> on top. </>}
              {r.conditionOverloadMult > 1 && <>Status-scaling mods multiply by <span className="text-ink">{mult(r.conditionOverloadMult)}</span>.</>}
            </p>
          )}
        </>
      )}
    </Section>
  )
}

export function DoTDisplay({ result: r }: Shared) {
  return (
    <Section title="Damage over time">
      {r.dots.length === 0 ? (
        <p className="text-sm text-mute">
          No damaging status effects. Slash, Heat, Toxin, Electricity and Gas deal damage over time.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[13px] text-mute">
              <th className="pb-1 font-normal">Status</th>
              <th className="pb-1 text-right font-normal">Per tick</th>
              <th className="pb-1 text-right font-normal">Ticks</th>
              <th className="pb-1 text-right font-normal">Lasts</th>
              <th className="pb-1 text-right font-normal">
                <Tip align="right" text="Damage of one proc over its full duration, without critical hits.">Total</Tip>
              </th>
            </tr>
          </thead>
          <tbody>
            {r.dots.map((d) => (
              <tr key={d.dotType} className="border-t border-seam">
                <td className="py-1">
                  <DamageChip type={d.dotType} />
                  {d.ignoresArmor && <span className="ml-2 text-[13px] text-good">ignores armor</span>}
                </td>
                <td className="py-1 text-right">{num(d.damagePerTick)}</td>
                <td className="py-1 text-right text-mute">{d.ticks}</td>
                <td className="py-1 text-right text-mute">{num(d.duration)} s</td>
                <td className="py-1 text-right font-medium">{num(d.totalDamage)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  )
}

export function ArsenalTotal({ result: r, other }: Shared) {
  return (
    <Section title="Arsenal check">
      <dl className="grid grid-cols-3 gap-3">
        <Stat label="Arsenal damage" tip="The total damage figure the in-game Arsenal shows for this build. Compare it to check the mods are entered correctly.">
          <AnimatedNumber value={r.arsenalTotalDamage} format={num} />
          <Delta block mine={r.arsenalTotalDamage} theirs={other?.arsenalTotalDamage} />
        </Stat>
        <Stat label="Status chance" tip="Status chance per projectile after mods.">{pct(r.moddedStatusChance)}</Stat>
        <Stat label="Modded base" tip="Base damage after damage mods such as Serration. Damage types are rounded to 1/32 of this.">
          {num(r.moddedBaseDamage, 2)}
        </Stat>
      </dl>
    </Section>
  )
}

function SideCard({ title, side }: { title: string; side: SideResult }) {
  const damage = sortDamage(Object.entries(side.perTypeInflicted))
  return (
    <Section title={title}>
      <p className="mb-3 text-sm text-mute">{side.weaponName || 'No weapon'}</p>
      <dl className="grid grid-cols-3 gap-4">
        <Headline label="Average hit" tip="Damage of one attack against this enemy, averaged over critical hits." value={side.averageShot} format={num} />
        <Headline label="Burst" tip="Damage per second while attacking." value={side.burstDps} format={num} />
        <Headline label="Sustained" tip="Damage per second including reloads, or energy recharge for amps." value={side.sustainedDps} format={num} />
      </dl>
      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-seam pt-3">
        <Stat label="Crit chance">{pct(side.critChance)}</Stat>
        <Stat label="Crit multiplier">{mult(side.critMult, 1)}</Stat>
        <Stat label="Status chance">{pct(side.statusChance)}</Stat>
        <Stat label="Attacks per second">{num(side.fireRate, 2)}</Stat>
      </dl>
      {damage.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {damage.map(([type, value]) => (
            <li key={type} className="flex items-center gap-2">
              <DamageChip type={type} /> <span className="text-mute">{num(value)}</span>
            </li>
          ))}
        </ul>
      )}
      {side.notes.map((note) => (
        <p key={note} className="mt-2 text-[13px] leading-snug text-mute">{note}</p>
      ))}
    </Section>
  )
}

/** Companion and amp damage, the combined total and the buffs that were applied. */
export function ExtrasDisplay({ result: r }: Shared) {
  if (!r.companion && !r.amp && r.activeBuffs.length === 0 && r.inactiveBuffs.length === 0) return null
  return (
    <>
      {r.companion && (
        <div className="grid @2xl:col-span-2 @6xl:col-span-6">
          <SideCard title={`Companion: ${r.companion.label}`} side={r.companion} />
        </div>
      )}
      {r.companion && (
        <div className="grid @2xl:col-span-2 @6xl:col-span-6">
          <Section title="Weapon and companion together">
            <dl className="grid grid-cols-3 gap-4">
              <Headline label="Weapon" tip="Sustained damage per second of your weapon." value={r.dps.sustainedDps} format={num} />
              <Headline label="Companion" tip="Sustained damage per second of the companion's weapon." value={r.companion.sustainedDps} format={num} />
              <Headline label="Combined" tip="Both attacking the same enemy the whole time. The amp is left out because you can't fire it and your weapon at once." value={r.combinedSustainedDps} format={num} />
            </dl>
            <p className="mt-3 text-[13px] text-mute">
              Kill time with both: {seconds(r.combinedSustainedDps > 0 ? r.enemyEhp / r.combinedSustainedDps : 0)}
            </p>
          </Section>
        </div>
      )}
      {r.amp && (
        <div className="grid @2xl:col-span-2 @6xl:col-span-6">
          <SideCard title="Amp: primary fire" side={r.amp.primary} />
        </div>
      )}
      {r.amp?.alt && (
        <div className="grid @2xl:col-span-2 @6xl:col-span-6">
          <SideCard title="Amp: alternate fire" side={r.amp.alt} />
        </div>
      )}
      {(r.activeBuffs.length > 0 || r.inactiveBuffs.length > 0) && (
        <div className="grid @2xl:col-span-2 @6xl:col-span-12">
          <Section title="Buffs applied">
            <ul className="grid gap-x-8 gap-y-1 text-sm @2xl:grid-cols-2">
              {r.activeBuffs.map((b) => (
                <li key={b.id} className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-medium text-ink">{b.name}</span>
                  <span className="text-mute">{b.effect}</span>
                  {b.uptime !== null && b.uptime < 1 && (
                    <span className="text-[13px] text-mute">up {pct(b.uptime, 0)} of the time</span>
                  )}
                  {!b.verified && <span className="text-[12px] text-bad">unverified</span>}
                </li>
              ))}
              {r.inactiveBuffs.map((b) => (
                <li key={b.id} className="flex flex-wrap items-baseline gap-x-2 text-mute">
                  <span className="font-medium line-through">{b.name}</span>
                  <span>Not applied. {b.reason}.</span>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      )}
    </>
  )
}

const COMBO_OPTIONS = Array.from({ length: 12 }, (_, i) => ({
  value: String(i + 1),
  label: `${i + 1}× combo`,
}))

function CombatContext({ index, isMelee }: { index: BuildIndex; isMelee: boolean }) {
  const headshot = useBuildStore((s) => s.builds[index].headshot)
  const combo = useBuildStore((s) => s.builds[index].comboMultiplier)
  const update = useBuildStore((s) => s.update)
  if (isMelee) {
    return (
      <FilterSelect
        label="Combo multiplier"
        value={String(combo)}
        onChange={(v) => update(index, { comboMultiplier: Number(v) })}
        options={COMBO_OPTIONS}
      />
    )
  }
  return (
    <Toggle
      label="Headshots"
      checked={headshot}
      onChange={(v) => update(index, { headshot: v })}
      tip="Every shot hits a weak point for double damage."
    />
  )
}

export function ResultsPanel({ index, compareWith }: {
  index: BuildIndex
  compareWith?: BuildIndex
}) {
  const weaponName = useBuildStore((s) => s.builds[index].weapon)
  const { data: weapons } = useWeapons()
  const { data: result, error, isPlaceholderData } = useCalculation(index)
  // Always called; only read when a comparison is on.
  const otherQuery = useCalculation(compareWith ?? index)
  const other = compareWith === undefined ? undefined : otherQuery.data

  const isMelee = weapons?.find((w) => w.name === weaponName)?.modType === 'MELEE'
  const shared = result ? { result, other, isMelee } : null

  return (
    <Panel title="Results" actions={<CombatContext index={index} isMelee={isMelee} />}>
      {error && <Notice tone="error">{error.message}</Notice>}
      {!error && !shared && (
        <div className="grid gap-3 sm:grid-cols-3" aria-busy="true" aria-label="Calculating">
          {[0, 1, 2].map((i) => <div key={i} className="h-40 animate-pulse bg-plate" />)}
        </div>
      )}
      {!error && shared && (
        // Sections sit on a seam-coloured grid so the 1px gaps read as dividers.
        <div className="@container -m-4">
          <div
            className={`grid gap-px bg-seam transition-opacity @2xl:grid-cols-2 @6xl:grid-cols-12 ${isPlaceholderData ? 'opacity-70' : ''}`}
          >
            <div className="grid @2xl:col-span-2 @6xl:col-span-5"><DPSDisplay {...shared} /></div>
            <div className="grid @6xl:col-span-3"><KillEstimate {...shared} /></div>
            <div className="grid @6xl:col-span-4"><CritDisplay {...shared} /></div>
            <div className="grid @2xl:col-span-2 @6xl:col-span-7"><DamageBreakdown {...shared} /></div>
            <div className="grid gap-px @2xl:col-span-2 @2xl:grid-cols-2 @6xl:col-span-5 @6xl:grid-cols-1">
              <DoTDisplay {...shared} />
              <ArsenalTotal {...shared} />
            </div>
            <ExtrasDisplay {...shared} />
          </div>
        </div>
      )}
    </Panel>
  )
}
