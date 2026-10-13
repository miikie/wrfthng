import { useCallback, useEffect, useMemo, useState } from 'react'
import { useWeapon, useWeapons } from '../api/queries'
import { useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import type { WeaponDetail } from '../types'
import { critTier, damageColor, sortDamage } from '../utils/damageTypes'
import { categoryLabel, mult, num, pct, titleCase } from '../utils/format'
import { GridPicker, ItemButton } from './ItemImage'
import { Bar, DamageChip, Notice, Panel, Stat } from './ui'

export function WeaponPicker({ index }: { index: BuildIndex }) {
  const { data: weapons = [], error } = useWeapons()
  const selected = useBuildStore((s) => s.builds[index].weapon)
  const setWeapon = useBuildStore((s) => s.setWeapon)
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])

  // Ctrl+K opens the weapon picker of the first build.
  useEffect(() => {
    if (index !== 0) return
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [index])

  const items = useMemo(
    () => weapons.map((w) => ({
      key: w.name,
      name: w.name,
      imageName: w.imageName,
      group: categoryLabel(w.category),
      detail: `${num(w.totalDamage)} damage, ${pct(w.critChance, 0)} crit, ${pct(w.statusChance, 0)} status`,
    })),
    [weapons],
  )
  const current = weapons.find((w) => w.name === selected)

  const onSelect = (name: string) => {
    const next = weapons.find((w) => w.name === name)
    if (!next) return
    // Mods for one weapon class don't fit another, so the rack empties.
    setWeapon(index, next.name, !!current && current.modType !== next.modType)
  }

  if (error) return <Notice tone="error">{error.message}</Notice>

  return (
    <>
      <ItemButton
        name={selected}
        imageName={current?.imageName}
        detail={current ? `${categoryLabel(current.category)}${index === 0 ? ' · Ctrl+K to change' : ''}` : undefined}
        placeholder="Choose a weapon"
        label={`Weapon: ${selected}. Change weapon`}
        onClick={() => setOpen(true)}
      />
      {open && (
        <GridPicker title="Choose a weapon" items={items} selected={selected} onSelect={onSelect} onClose={close} />
      )}
    </>
  )
}

export function WeaponStatCard({ weapon }: { weapon: WeaponDetail }) {
  const damage = sortDamage(Object.entries(weapon.damage))
  const total = damage.reduce((sum, [, v]) => sum + v, 0)
  const tier = critTier(Math.ceil(weapon.critChance - 1e-9))
  const isMelee = weapon.modType === 'MELEE'

  return (
    <div className="grid gap-5 @lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <div>
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-[13px] text-mute">Base damage per hit</span>
          <span className="font-display text-xl font-semibold text-gold-pale">{num(total)}</span>
        </div>
        {damage.length === 0 && <Notice>The game export has no damage data for this weapon.</Notice>}
        <ul className="space-y-1.5">
          {damage.map(([type, value]) => (
            <li key={type} className="grid grid-cols-[6.5rem_1fr_3.5rem] items-center gap-2 text-sm">
              <DamageChip type={type} />
              <Bar fraction={value / total} color={damageColor(type)} />
              <span className="text-right">{num(value)}</span>
            </li>
          ))}
        </ul>
      </div>

      <dl className="grid grid-cols-3 gap-x-4 gap-y-3">
        <Stat label="Crit chance" tip="Chance for a hit to be critical. Above 100% every hit crits and the remainder is the chance of the next tier.">
          <span style={{ color: weapon.critChance >= 1 ? tier.color : undefined }}>
            {pct(weapon.critChance)}
          </span>
        </Stat>
        <Stat label="Crit multiplier" tip="Damage multiplier of a first-tier (yellow) critical hit.">
          {mult(weapon.critMult, 1)}
        </Stat>
        <Stat label="Status chance" tip="Chance per hit to apply a status effect, weighted by damage type.">
          {pct(weapon.statusChance)}
        </Stat>
        <Stat label={isMelee ? 'Attack speed' : 'Fire rate'} tip={isMelee ? 'Attack speed multiplier.' : 'Shots per second while the trigger is held.'}>
          {num(weapon.fireRate, 2)}
        </Stat>
        {!isMelee && (
          <>
            <Stat label="Magazine" tip="Shots before a reload.">{weapon.magSize || '—'}</Stat>
            <Stat label="Reload" tip="Seconds to reload an empty magazine.">
              {weapon.reloadTime ? `${num(weapon.reloadTime, 2)} s` : '—'}
            </Stat>
            <Stat label="Multishot" tip="Projectiles per shot before mods. Each one rolls crit and status separately.">
              {weapon.multishot}
            </Stat>
            <Stat label="Trigger" tip="How the weapon fires. Charge and burst triggers change the effective fire rate.">
              {weapon.trigger ? titleCase(weapon.trigger) : '—'}
            </Stat>
          </>
        )}
        <Stat label="Mastery" tip="Mastery rank needed to use this weapon.">{weapon.masteryReq}</Stat>
      </dl>
    </div>
  )
}

export function WeaponPanel({ index }: { index: BuildIndex }) {
  const name = useBuildStore((s) => s.builds[index].weapon)
  const { data: weapon, error } = useWeapon(name)

  return (
    <Panel title="Weapon">
      <div className="@container space-y-4">
        <WeaponPicker index={index} />
        {error && <Notice tone="error">{error.message}</Notice>}
        {weapon && <WeaponStatCard weapon={weapon} />}
        {!weapon && !error && <div className="h-28 animate-pulse bg-plate" />}
      </div>
    </Panel>
  )
}
