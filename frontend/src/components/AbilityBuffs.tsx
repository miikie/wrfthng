import { useCallback, useMemo, useState } from 'react'
import { useCalculation, useWarframes } from '../api/queries'
import { useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { AbilityEffect } from '../types'
import { num, pct } from '../utils/format'
import { HelminthAbilityBar, HelminthIcon } from './Helminth'
import type { SlotAbility } from './Helminth'
import { GridPicker, ItemButton } from './ItemImage'
import { Notice, Panel, Tip, Toggle } from './ui'

/** On unless switched off: unconditional passives. Everything else starts off. */
const defaultActive = (e: AbilityEffect) => e.variant === 'passive' && e.condition === ''

const VARIANT_TAG: Record<AbilityEffect['variant'], string> = {
  own: '', passive: 'Passive', infused: 'Helminth',
}

function EffectRow({ index, effect: e }: { index: BuildIndex; effect: AbilityEffect }) {
  const state = useBuildStore((s) => s.builds[index].abilityBuffs[e.id])
  const setAbilityBuff = useBuildStore((s) => s.setAbilityBuff)
  const active = state?.active ?? defaultActive(e)
  const on = active && e.applies
  const level = state?.level ?? e.level?.default ?? 1
  const stacks = state?.stacks ?? e.stacks?.default ?? 0
  const tag = VARIANT_TAG[e.variant]

  return (
    <li className={`border px-3 py-2 ${on ? 'border-gold/60 bg-gold/5' : 'border-seam'} ${e.applies ? '' : 'opacity-60'}`}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <span className="flex flex-wrap items-center gap-2">
          <Toggle label={e.label} checked={active} disabled={!e.applies}
            onChange={(v) => setAbilityBuff(index, e.id, { active: v })}
            tip={e.condition ? `Switch on when: ${e.condition}.` : undefined} />
          {tag && (
            <span className="flex items-center gap-1 border border-seam px-1.5 text-[11px] uppercase tracking-wide text-mute">
              {e.variant === 'infused' && <HelminthIcon className="size-3" />}{tag}
            </span>
          )}
          {e.augment && (
            <span className="border border-tenno/50 px-1.5 text-[11px] uppercase tracking-wide text-tenno">
              Needs {e.augment}
            </span>
          )}
        </span>
        <span className={`text-sm font-medium ${on ? 'text-ink' : 'text-mute'}`}>{e.effect}</span>
      </div>
      <p className="mt-1 text-[13px] leading-snug text-mute">
        {!e.applies && <span className="text-bad">{e.reason}. </span>}
        {e.note}
        {e.condition && <> Only when: {e.condition.charAt(0).toLowerCase() + e.condition.slice(1)}.</>}
        {e.scalesWithStrength && ' Scales with Ability Strength.'}
      </p>
      {on && (e.level || e.stacks) && (
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-mute">
          {e.level && (
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap">{e.level.label}: {pct(level, 0)}</span>
              <input type="range" min={0} max={100} value={Math.round(level * 100)}
                onChange={(ev) => setAbilityBuff(index, e.id, { level: Number(ev.target.value) / 100 })} />
            </label>
          )}
          {e.stacks && (
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap">{e.stacks.label}: {stacks}</span>
              <input type="range" min={0} max={e.stacks.max} value={stacks}
                onChange={(ev) => setAbilityBuff(index, e.id, { stacks: Number(ev.target.value) })} />
            </label>
          )}
        </div>
      )}
    </li>
  )
}

/**
 * Damage dealt tab: the Warframe holding the weapon, and the abilities and passive
 * that change weapon damage. The Warframe, its mods (Ability Strength) and its
 * Helminth infusion are shared with the Damage taken tab.
 */
export function AbilityBuffsPanel({ index }: { index: BuildIndex }) {
  const { data: result, error } = useCalculation(index)
  const { data: frames } = useWarframes()
  const warframeName = useBuildStore((s) => s.builds[index].warframe)
  const extraStrength = useBuildStore((s) => s.builds[index].survival.extraStrength)
  const abilityBuffs = useBuildStore((s) => s.builds[index].abilityBuffs)
  const setWarframe = useBuildStore((s) => s.setWarframe)
  const setAbilityBuff = useBuildStore((s) => s.setAbilityBuff)
  const setView = useBuildStore((s) => s.setView)
  const [picking, setPicking] = useState(false)
  const closePicker = useCallback(() => setPicking(false), [])

  const warframe = frames?.warframes.find((w) => w.name === warframeName)
  const frameItems = useMemo(
    () => (frames?.warframes ?? []).map((w) => ({
      key: w.name, name: w.name, imageName: w.imageName,
      group: w.name.endsWith(' Prime') ? 'Prime' : 'Base',
      detail: w.passive.name ? `Passive: ${w.passive.name}` : undefined,
    })),
    [frames],
  )
  const effects = result?.abilityEffects ?? []
  const fromAbilities = effects.filter((e) => e.variant !== 'passive' && e.kind !== 'strength')
  const fromPassive = effects.filter((e) => e.variant === 'passive')
  const empower = effects.find((e) => e.kind === 'strength')
  const strength = result?.abilityStrength ?? null

  // a slot's weapon effects: its own ability's, or the infused ability's
  const effectsOf = (slot: SlotAbility) => effects.filter((e) =>
    e.kind !== 'strength' && (slot.infused ? e.variant === 'infused' : e.variant === 'own' && e.ability === slot.name))
  const isOn = (e: AbilityEffect) => abilityBuffs[e.id]?.active ?? defaultActive(e)

  return (
    <Panel
      title="Warframe abilities"
      actions={strength !== null && (
        <span className="text-sm text-mute">
          <Tip align="right" text="From the Warframe mods on the Damage taken tab, plus any extra Ability Strength entered there. Abilities marked as scaling are multiplied by it.">
            Ability Strength
          </Tip>{' '}
          <span className={`font-medium ${strength > 1.005 ? 'text-good' : strength < 0.995 ? 'text-gold' : 'text-ink'}`}>
            {pct(strength, 0)}
          </span>
        </span>
      )}
    >
      <div className="space-y-4">
        {error && <Notice tone="error">{error.message}</Notice>}
        <div className="grid items-start gap-4 @2xl:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
          <div className="space-y-2">
            <ItemButton
              name={warframeName}
              imageName={warframe?.imageName}
              detail={warframe?.passive.name ? `Passive: ${warframe.passive.name}` : 'The Warframe holding this weapon'}
              placeholder="Choose a Warframe"
              label={`Warframe: ${warframeName}. Change Warframe`}
              onClick={() => setPicking(true)}
            />
            <p className="text-[13px] leading-snug text-mute">
              Same Warframe, mods and Helminth infusion as the Damage taken tab
              {extraStrength ? ` (including +${num(extraStrength * 100, 0)}% extra strength)` : ''}.{' '}
              <button type="button" className="text-tenno underline-offset-4 hover:underline" onClick={() => setView('taken')}>
                Edit its mods
              </button>
            </p>
          </div>
          <div>
            <HelminthAbilityBar
              index={index}
              state={(slot) => {
                const list = effectsOf(slot)
                const usable = list.some((e) => e.applies)
                return {
                  usable,
                  active: usable && list.filter((e) => e.applies).every(isOn),
                  title: list.length === 0 ? 'No effect on weapon damage'
                    : !usable ? list[0].reason : list.map((e) => `${e.label}: ${e.effect}`).join(' · '),
                }
              }}
              onToggle={(slot) => {
                const list = effectsOf(slot).filter((e) => e.applies)
                const on = list.every(isOn)
                list.forEach((e) => setAbilityBuff(index, e.id, { active: !on }))
              }}
            />
            <p className="mt-2 text-[13px] text-mute">
              Click an ability to switch its weapon buff on. The flower badge infuses a Helminth ability over a slot.
            </p>
          </div>
        </div>
        {picking && (
          <GridPicker title="Choose a Warframe" items={frameItems} selected={warframeName}
            onSelect={(name) => setWarframe(index, name)} onClose={closePicker} />
        )}

        {empower && (
          <ul className="grid gap-2"><EffectRow index={index} effect={empower} /></ul>
        )}
        {fromAbilities.length > 0 && (
          <section>
            <h3 className="mb-2 text-[15px] text-gold">Ability buffs</h3>
            <ul className="grid gap-2 @3xl:grid-cols-2">
              {fromAbilities.map((e) => <EffectRow key={e.id} index={index} effect={e} />)}
            </ul>
          </section>
        )}
        {fromPassive.length > 0 && (
          <section>
            <h3 className="mb-2 text-[15px] text-gold">Passive{warframe?.passive.name ? `: ${warframe.passive.name}` : ''}</h3>
            <ul className="grid gap-2 @3xl:grid-cols-2">
              {fromPassive.map((e) => <EffectRow key={e.id} index={index} effect={e} />)}
            </ul>
          </section>
        )}
        {result && effects.length === 0 && (
          <p className="text-sm text-mute">
            None of {warframeName}'s abilities or its passive change weapon damage in this calculator. Infuse one
            with the Helminth badge, such as Roar or Xata's Whisper.
          </p>
        )}
        {fromAbilities.length + fromPassive.length > 0 && (
          <p className="text-[13px] leading-snug text-mute">
            Values are max rank from the wiki, after Ability Strength and caps. Abilities only buff the weapon here;
            effects on allies, companions and abilities are not modelled.
          </p>
        )}
      </div>
    </Panel>
  )
}
