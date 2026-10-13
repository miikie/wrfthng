import { useState } from 'react'
import { useCalculation, useSurvivability } from './api/queries'
import { BUILD_NAMES, BuildEditor } from './components/BuildEditor'
import { DockedPicker } from './components/ModPicker'
import { ResultsPanel } from './components/Results'
import { SurvivabilityEditor, SurvivabilityResults } from './components/Survivability'
import { buttonClass, Toggle } from './components/ui'
import { useBuildStore } from './stores/buildStore'
import type { BuildIndex } from './stores/buildStore'
import { num, seconds } from './utils/format'

/** Always-visible summary so the key numbers stay in view while editing mods. */
function Readout({ index, showName }: { index: BuildIndex; showName: boolean }) {
  const { data } = useCalculation(index)
  if (!data) return null
  return (
    <p className="text-sm text-mute">
      {showName && <span className="mr-2 font-display font-semibold text-gold">{BUILD_NAMES[index]}</span>}
      <span className="font-medium text-ink">{num(data.dps.sustainedDps)}</span> sustained DPS,{' '}
      <span className="font-medium text-ink">{seconds(data.timeToKill)}</span> to kill
    </p>
  )
}

function TakenReadout({ index, showName }: { index: BuildIndex; showName: boolean }) {
  const { data } = useSurvivability(index)
  if (!data) return null
  return (
    <p className="text-sm text-mute">
      {showName && <span className="mr-2 font-display font-semibold text-gold">{BUILD_NAMES[index]}</span>}
      <span className="font-medium text-ink">{data.totalEhp === null ? '∞' : num(data.totalEhp, 0)}</span> effective health,{' '}
      <span className="font-medium text-ink">{(data.totalDr * 100).toFixed(1)}%</span> reduction
    </p>
  )
}

function ViewSwitch() {
  const view = useBuildStore((s) => s.view)
  const setView = useBuildStore((s) => s.setView)
  const tab = (id: 'dealt' | 'taken', label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={view === id}
      onClick={() => setView(id)}
      className={`border px-3 py-1.5 text-sm font-medium transition-colors ${
        view === id
          ? 'border-gold bg-gold/15 text-gold-pale'
          : 'border-seam bg-plate text-mute hover:border-seam-bright hover:text-ink'
      }`}
    >
      {label}
    </button>
  )
  return (
    <div role="tablist" aria-label="Calculator" className="flex">
      {tab('dealt', 'Damage dealt')}
      {tab('taken', 'Damage taken')}
    </div>
  )
}

function ShareButton() {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt('Copy this link to share the build:', window.location.href)
    }
  }
  return (
    <button type="button" className={buttonClass} onClick={copy} title="The address bar always holds a link to the current build.">
      <span role="status">{copied ? 'Link copied' : 'Copy link'}</span>
    </button>
  )
}

export default function App() {
  const compare = useBuildStore((s) => s.compare)
  const sharedEnemy = useBuildStore((s) => s.sharedEnemy)
  const setCompare = useBuildStore((s) => s.setCompare)
  const setSharedEnemy = useBuildStore((s) => s.setSharedEnemy)
  const view = useBuildStore((s) => s.view)

  return (
    <>
      <header className="sticky top-0 z-20 border-b border-seam bg-void/95 backdrop-blur">
        <div className={`mx-auto flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6 ${compare ? 'max-w-[2400px]' : 'max-w-[1900px]'}`}>
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl tracking-wide text-gold-pale">Simulacrum</h1>
            <p className="text-sm text-mute">Warframe damage calculator</p>
            <ViewSwitch />
          </div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
            {view === 'dealt' ? (
              <>
                <Readout index={0} showName={compare} />
                {compare && <Readout index={1} showName />}
              </>
            ) : (
              <>
                <TakenReadout index={0} showName={compare} />
                {compare && <TakenReadout index={1} showName />}
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            {compare && (
              <Toggle
                label="Same enemy"
                checked={sharedEnemy}
                onChange={setSharedEnemy}
                tip="Both builds fight Build A's enemy."
              />
            )}
            <Toggle
              label="Compare two builds"
              checked={compare}
              onChange={setCompare}
              tip="Show a second build beside this one."
            />
            <ShareButton />
          </div>
        </div>
      </header>

      <main className={`mx-auto space-y-6 px-4 py-6 sm:px-6 ${compare ? 'max-w-[2400px]' : 'max-w-[1900px]'}`}>
        {/* Builds on the left, the mod browser docked on the right at desktop width. */}
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className={compare ? 'grid min-w-0 gap-6 2xl:grid-cols-2' : 'min-w-0'}>
            {view === 'dealt' && (compare
              ? <><BuildEditor index={0} compareWith={1} /><BuildEditor index={1} compareWith={0} /></>
              : <BuildEditor index={0} results={false} />)}
            {view === 'taken' && (compare
              ? <><SurvivabilityEditor index={0} compareWith={1} /><SurvivabilityEditor index={1} compareWith={0} /></>
              : <SurvivabilityEditor index={0} results={false} />)}
          </div>
          <DockedPicker />
        </div>
        {/* With one build the results run the full width underneath. */}
        {!compare && (view === 'dealt' ? <ResultsPanel index={0} /> : <SurvivabilityResults index={0} />)}
      </main>
    </>
  )
}
