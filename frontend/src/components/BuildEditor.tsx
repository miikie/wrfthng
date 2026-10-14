import { useBuildStore } from '../stores/buildStore'
import { AbilityBuffsPanel } from './AbilityBuffs'
import type { BuildIndex } from '../stores/buildStore'
import { AmpPanel } from './AmpPanel'
import { BuffsPanel } from './BuffsPanel'
import { CompanionPanel, useCompanionWeapon } from './CompanionPanel'
import { EnemyPanel } from './EnemyPanel'
import { ModRack } from './ModRack'
import { PresetMenu } from './PresetMenu'
import { ResultsPanel } from './Results'
import { WeaponPanel } from './WeaponPanel'
import { buttonClass } from './ui'

export const BUILD_NAMES = ['Build A', 'Build B'] as const

/**
 * One complete build. On a wide enough column the weapon and enemy sit in a
 * narrow left column with the mod rack beside them; otherwise everything stacks.
 * `results` is false when the page shows the results full width underneath.
 */
export function BuildEditor({ index, compareWith, results = true }: {
  index: BuildIndex
  compareWith?: BuildIndex
  results?: boolean
}) {
  const copyBuild = useBuildStore((s) => s.copyBuild)
  const companionWeapon = useCompanionWeapon(index)

  return (
    <div className="@container space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg text-gold-pale">
          {compareWith === undefined ? 'Your build' : BUILD_NAMES[index]}
        </h2>
        <div className="flex gap-2">
          {compareWith !== undefined && (
            <button type="button" className={buttonClass} onClick={() => copyBuild(compareWith, index)}>
              Copy from {BUILD_NAMES[compareWith]}
            </button>
          )}
          <PresetMenu index={index} />
        </div>
      </div>
      <div className="grid items-start gap-4 @5xl:grid-cols-[21rem_minmax(0,1fr)]">
        <div className="grid gap-4 @2xl:grid-cols-2 @5xl:grid-cols-1">
          <WeaponPanel index={index} />
          <EnemyPanel index={index} />
        </div>
        <div className="min-w-0 space-y-4">
          <ModRack index={index} />
          <AbilityBuffsPanel index={index} />
          <div className="grid gap-4 @4xl:grid-cols-2">
            <CompanionPanel index={index} />
            <AmpPanel index={index} />
          </div>
          {companionWeapon && <ModRack index={index} companionWeapon={companionWeapon} />}
          <BuffsPanel index={index} />
        </div>
      </div>
      {results && <ResultsPanel index={index} compareWith={compareWith} />}
    </div>
  )
}
