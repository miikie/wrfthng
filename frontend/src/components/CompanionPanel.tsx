import { useCallback, useMemo, useState } from 'react'
import { useAllWeapons, useCompanions } from '../api/queries'
import { useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { CompanionInfo } from '../types'
import { num } from '../utils/format'
import { FilterSelect } from './Combobox'
import { GridPicker, ItemButton, ItemImage } from './ItemImage'
import { Notice, Panel, Stat, Toggle } from './ui'

const TYPE_ORDER = ['Sentinel', 'MOA', 'Hound', 'Kubrow', 'Kavat', 'Vulpaphyla', 'Predasite']

function useCompanion(index: BuildIndex): CompanionInfo | undefined {
  const name = useBuildStore((s) => s.builds[index].companion)
  const { data: companions } = useCompanions()
  return companions?.find((c) => c.name === name)
}

/** The weapon the build's companion attacks with, or '' when there is none. */
export function useCompanionWeapon(index: BuildIndex): string {
  const chosen = useBuildStore((s) => s.builds[index].companionWeapon)
  const companion = useCompanion(index)
  if (!companion) return ''
  return companion.weapons.includes(chosen) ? chosen : companion.defaultWeapon
}

export function CompanionPanel({ index }: { index: BuildIndex }) {
  const { data: companions = [], error } = useCompanions()
  const { data: weapons } = useAllWeapons()
  const selected = useBuildStore((s) => s.builds[index].companion)
  const setCompanion = useBuildStore((s) => s.setCompanion)
  const setCompanionWeapon = useBuildStore((s) => s.setCompanionWeapon)
  const sentinelAttack = useBuildStore((s) => s.builds[index].sentinelAttack)
  const update = useBuildStore((s) => s.update)
  const companion = useCompanion(index)
  const weapon = useCompanionWeapon(index)

  const [picking, setPicking] = useState(false)
  const closePicker = useCallback(() => setPicking(false), [])
  const items = useMemo(() => {
    const sorted = [...companions].sort(
      (a, b) => TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type) || a.name.localeCompare(b.name),
    )
    return sorted.map((c) => ({
      key: c.name, name: c.name, imageName: c.imageName, group: c.type,
      detail: `${num(c.health)} health, ${num(c.shield)} shields, ${num(c.armor)} armor`,
    }))
  }, [companions])

  const modTypeOf = (name: string) => weapons?.find((w) => w.name === name)?.modType

  return (
    <Panel title="Companion">
      {error && <Notice tone="error">{error.message}</Notice>}
      <div className="mb-4">
        <ItemButton
          name={selected}
          imageName={companion?.imageName}
          detail={companion?.type}
          placeholder="No companion"
          label={selected ? `Companion: ${selected}. Change companion` : 'Choose a companion'}
          onClick={() => setPicking(true)}
        />
      </div>
      {picking && (
        <GridPicker title="Choose a companion" items={items} selected={selected} allowNone="No companion"
          onSelect={(name) => setCompanion(index, name)} onClose={closePicker} />
      )}
      {!companion && !error && (
        <p className="text-sm text-mute">
          Pick a companion to add its weapon damage and see which of its abilities change your own damage.
        </p>
      )}
      {companion && (
        <div className="space-y-4">
          <dl className="grid grid-cols-3 gap-4">
            <Stat label="Health" tip="Base health before companion mods. Companion stats do not appear to change with rank.">{num(companion.health)}</Stat>
            <Stat label="Shields">{num(companion.shield)}</Stat>
            <Stat label="Armor">{num(companion.armor)}</Stat>
          </dl>
          {companion.statsNote && <p className="text-[13px] leading-snug text-mute">{companion.statsNote}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <span className="text-[13px] text-mute">Weapon</span>
            {weapon && <ItemImage name={weapon} imageName={weapons?.find((w) => w.name === weapon)?.imageName} className="size-9" />}
            {companion.weapons.length > 1 ? (
              <FilterSelect
                label="Companion weapon"
                value={weapon}
                onChange={(next) => setCompanionWeapon(index, next, modTypeOf(next) !== modTypeOf(weapon))}
                options={[
                  ...(companion.defaultWeapon ? [] : [{ value: '', label: 'No weapon' }]),
                  ...companion.weapons.map((w) => ({ value: w, label: w })),
                ]}
              />
            ) : (
              <span className="font-medium">{weapon || 'None'}</span>
            )}
          </div>
          {companion.needsAttackPrecept && (
            <div className="flex flex-wrap items-center gap-3">
              <Toggle
                label="Attack precept equipped"
                checked={sentinelAttack}
                onChange={(on) => update(index, { sentinelAttack: on })}
                tip="Assault Mode, or the Sentinel's own attack precept."
              />
              <span className="text-[13px] text-mute">
                {sentinelAttack ? 'Without one a Sentinel never fires.' : 'This Sentinel will not fire.'}
              </span>
            </div>
          )}

          <div>
            <h3 className="mb-2 text-[15px] text-gold">Abilities</h3>
            <ul className="space-y-2 text-sm">
              {companion.precepts.map((p) => (
                <li key={p.name}>
                  <span className="font-medium text-ink">{p.name}</span>{' '}
                  <span className="text-mute">{p.effect}</span>
                  {p.damageEffect && <p className="text-[13px] text-tenno">Affects damage: {p.damageEffect}</p>}
                </li>
              ))}
              {companion.precepts.length === 0 && (
                <li className="text-mute">Its abilities come from the parts it is built with.</li>
              )}
            </ul>
          </div>
        </div>
      )}
    </Panel>
  )
}
