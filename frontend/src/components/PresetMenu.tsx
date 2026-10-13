import { useCallback, useState } from 'react'
import { BUILT_IN_PRESETS, useBuildStore } from '../stores/buildStore'
import type { BuildIndex, Preset } from '../stores/buildStore'
import { useDismiss } from '../utils/hooks'
import { buttonClass, inputClass } from './ui'

function summary(p: Preset): string {
  const mods = p.build.mods.filter(Boolean).length
  return `${p.build.weapon}, ${mods} ${mods === 1 ? 'mod' : 'mods'}`
}

/** Save the current build under a name, or load a saved or starter build. */
export function PresetMenu({ index }: { index: BuildIndex }) {
  const presets = useBuildStore((s) => s.presets)
  const savePreset = useBuildStore((s) => s.savePreset)
  const deletePreset = useBuildStore((s) => s.deletePreset)
  const replaceBuild = useBuildStore((s) => s.replaceBuild)
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [savedName, setSavedName] = useState('')
  const close = useCallback(() => setOpen(false), [])
  const ref = useDismiss<HTMLDivElement>(open, close)

  const trimmed = name.trim()
  const overwrites = presets.some((p) => p.name === trimmed)

  const save = (e: React.FormEvent) => {
    e.preventDefault()
    if (!trimmed) return
    savePreset(trimmed, index)
    setSavedName(trimmed)
    setName('')
  }

  const load = (p: Preset) => {
    replaceBuild(index, p.build)
    close()
  }

  const row = (p: Preset) => (
    <li key={p.name} className="flex items-stretch border-t border-seam">
      <button type="button" onClick={() => load(p)} className="min-w-0 flex-1 px-3 py-2 text-left hover:bg-tenno/10">
        <span className="block truncate font-medium">{p.name}</span>
        <span className="block truncate text-[13px] text-mute">{summary(p)}</span>
      </button>
      {!p.builtIn && (
        <button type="button" onClick={() => deletePreset(p.name)}
          className="px-3 text-mute hover:text-bad" aria-label={`Delete saved build ${p.name}`}>
          ✕
        </button>
      )}
    </li>
  )

  return (
    <div ref={ref} className="relative">
      <button type="button" className={buttonClass} aria-expanded={open} onClick={() => setOpen(!open)}>
        Saved builds
      </button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 w-80 border border-seam-bright bg-plate shadow-xl shadow-black/50">
          <form onSubmit={save} className="space-y-2 p-3">
            <div className="flex gap-2">
              <input
                aria-label="Name for this build"
                placeholder="Name this build"
                value={name}
                onChange={(e) => { setName(e.target.value); setSavedName('') }}
                className={inputClass}
                maxLength={60}
              />
              <button type="submit" className={`${buttonClass} shrink-0`} disabled={!trimmed}>
                {overwrites ? 'Replace' : 'Save build'}
              </button>
            </div>
            {savedName && <p className="text-[13px] text-good" role="status">Saved “{savedName}” in this browser.</p>}
          </form>

          <h3 className="px-3 pb-1 text-[13px] text-gold">Your builds</h3>
          {presets.length === 0 ? (
            <p className="border-t border-seam px-3 py-2 text-sm text-mute">
              Nothing saved yet. Name the current build above to keep it.
            </p>
          ) : (
            <ul className="max-h-56 overflow-y-auto">{presets.map(row)}</ul>
          )}

          <h3 className="px-3 pb-1 pt-3 text-[13px] text-gold">Starter builds</h3>
          <ul>{BUILT_IN_PRESETS.map(row)}</ul>
        </div>
      )}
    </div>
  )
}
