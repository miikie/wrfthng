import { useCallback, useState } from 'react'
import { useAmpParts } from '../api/queries'
import { DEFAULT_AMP, useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { AmpBrace, AmpBuild, AmpPart } from '../types'
import { num, pct } from '../utils/format'
import { FilterSelect } from './Combobox'
import { GridPicker, ItemImage } from './ItemImage'
import { DamageChip, Notice, Panel, Toggle } from './ui'

const ARCANE_SLOTS = [0, 1]

function PartSummary({ label, part }: { label: string; part: AmpPart | undefined }) {
  if (!part) return null
  return (
    <div>
      <h3 className="mb-1 flex items-center gap-2 text-[15px] text-gold">
        <ItemImage name={part.name} imageName={part.imageName} className="size-9" />
        {label}: {part.name}
      </h3>
      <ul className="space-y-1 text-sm">
        {part.attacks.map((a) => (
          <li key={a.name} className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="text-mute">{a.name}</span>
            {Object.entries(a.damage).map(([type, value]) => (
              <span key={type} className="flex items-center gap-1.5">
                <DamageChip type={type} /> {num(value)}
              </span>
            ))}
            <span className="text-mute">
              {pct(a.critChance)} crit, {num(a.critMult, 1)}×, {pct(a.statusChance)} status
              {a.multishot > 1 ? `, ${a.multishot} projectiles` : ''}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function AmpPanel({ index }: { index: BuildIndex }) {
  const { data: parts, error } = useAmpParts()
  const amp = useBuildStore((s) => s.builds[index].amp)
  const update = useBuildStore((s) => s.update)
  const set = (patch: Partial<AmpBuild>) => amp && update(index, { amp: { ...amp, ...patch } })

  const [picking, setPicking] = useState<'prism' | 'scaffold' | 'brace' | null>(null)
  const closePicker = useCallback(() => setPicking(null), [])
  const stats = (p: AmpPart) => {
    const a = p.attacks[0]
    const damage = Object.values(a.damage).reduce((sum, v) => sum + v, 0)
    return `${num(damage)} damage, ${pct(a.critChance, 0)} crit, ${pct(a.statusChance, 0)} status`
  }
  const braceText = (b: AmpBrace) => [
    b.critChance ? `+${pct(b.critChance, 0)} crit chance` : '',
    b.statusChance ? `+${pct(b.statusChance, 0)} status chance` : '',
    b.energy ? `${b.energy > 0 ? '+' : ''}${b.energy} energy` : '',
    b.rechargeDelay ? `${b.rechargeDelay > 0 ? '+' : ''}${b.rechargeDelay}s recharge delay` : '',
    b.rechargeRate ? `+${b.rechargeRate}/s recharge` : '',
  ].filter(Boolean).join(', ')
  const series = (n: number | null | undefined) => (n ? String(n) : 'x')

  const setArcane = (slot: number, name: string) => {
    if (!amp || !parts) return
    const arcanes = [...amp.arcanes]
    if (name) {
      const info = parts.arcanes.find((a) => a.name === name)
      arcanes[slot] = { name, rank: info?.maxRank ?? 0 }
    } else {
      arcanes.splice(slot, 1)
    }
    // An arcane can only be equipped once.
    set({ arcanes: arcanes.filter((a, i) => a && arcanes.findIndex((b) => b?.name === a.name) === i) })
  }

  return (
    <Panel
      title="Operator amp"
      actions={
        <Toggle
          label="Include amp"
          checked={amp !== null}
          onChange={(on) => update(index, { amp: on ? DEFAULT_AMP : null })}
          tip="Calculate your Operator's amp against the same enemy."
        />
      }
    >
      {error && <Notice tone="error">{error.message}</Notice>}
      {!amp && !error && (
        <p className="text-sm text-mute">
          Turn this on to build an amp from a prism, scaffold and brace and see its damage against this enemy.
        </p>
      )}
      {amp && parts && (
        <div className="space-y-4">
          <p className="text-sm text-mute">
            Amp{' '}
            <span className="font-display text-base font-semibold text-gold-pale">
              {series(parts.prisms.find((p) => p.name === amp.prism)?.series)}
              {series(parts.scaffolds.find((p) => p.name === amp.scaffold)?.series)}
              {series(parts.braces.find((p) => p.name === amp.brace)?.series)}
            </span>
            : prism, scaffold and brace by their series number.
          </p>
          <div className="grid grid-cols-3 gap-2">
            {([
              ['prism', 'Prism', amp.prism, parts.prisms.find((p) => p.name === amp.prism)?.imageName],
              ['scaffold', 'Scaffold', amp.scaffold, parts.scaffolds.find((p) => p.name === amp.scaffold)?.imageName],
              ['brace', 'Brace', amp.brace, parts.braces.find((p) => p.name === amp.brace)?.imageName],
            ] as const).map(([key, label, name, image]) => (
              <button key={key} type="button" onClick={() => setPicking(key)}
                aria-label={`${label}: ${name || 'none'}. Change ${label.toLowerCase()}`}
                className="flex flex-col items-center gap-1 border border-seam bg-void p-2 text-center hover:border-tenno">
                <ItemImage name={name || label} imageName={image} className="size-14" />
                <span className="text-[11px] uppercase tracking-wide text-mute">{label}</span>
                <span className="font-display text-[14px] font-semibold leading-tight">{name ? name.replace(/ (Prism|Scaffold|Brace)$/, '') : 'None'}</span>
              </button>
            ))}
          </div>
          {picking === 'prism' && (
            <GridPicker title="Prism (primary fire)" columns="narrow" selected={amp.prism} onClose={closePicker}
              items={parts.prisms.map((p) => ({ key: p.name, name: p.name, imageName: p.imageName, detail: stats(p) }))}
              onSelect={(v) => v && set({ prism: v })} />
          )}
          {picking === 'scaffold' && (
            <GridPicker title="Scaffold (alternate fire)" columns="narrow" selected={amp.scaffold} onClose={closePicker}
              allowNone="No scaffold"
              items={parts.scaffolds.map((p) => ({ key: p.name, name: p.name, imageName: p.imageName, detail: stats(p) }))}
              onSelect={(v) => set({ scaffold: v })} />
          )}
          {picking === 'brace' && (
            <GridPicker title="Brace" columns="narrow" selected={amp.brace} onClose={closePicker} allowNone="No brace"
              items={parts.braces.map((b) => ({ key: b.name, name: b.name, imageName: b.imageName, detail: braceText(b) }))}
              onSelect={(v) => set({ brace: v })} />
          )}

          <PartSummary label="Prism" part={parts.prisms.find((p) => p.name === amp.prism)} />
          <PartSummary label="Scaffold" part={parts.scaffolds.find((p) => p.name === amp.scaffold)} />

          <div>
            <h3 className="mb-2 text-[15px] text-gold">Arcanes</h3>
            <div className="space-y-2">
              {ARCANE_SLOTS.map((slot) => {
                const current = amp.arcanes[slot]
                const info = parts.arcanes.find((a) => a.name === current?.name)
                return (
                  <div key={slot} className="flex flex-wrap items-center gap-3">
                    <ItemImage name={current?.name ?? `Slot ${slot + 1}`} imageName={info?.imageName}
                      fallback={slot + 1} className="size-9 rounded-full" />
                    <FilterSelect
                      label={`Arcane slot ${slot + 1}`}
                      value={current?.name ?? ''}
                      onChange={(v) => setArcane(slot, v)}
                      options={[
                        { value: '', label: `Arcane slot ${slot + 1}: empty` },
                        ...parts.arcanes.map((a) => ({ value: a.name, label: a.name })),
                      ]}
                    />
                    {info && <span className="text-[13px] text-mute">{info.text}</span>}
                  </div>
                )
              })}
            </div>
            <p className="mt-2 text-[13px] text-mute">
              Arcane bonuses are counted as always active. Only arcanes that change damage stats are listed.
            </p>
          </div>
        </div>
      )}
    </Panel>
  )
}
