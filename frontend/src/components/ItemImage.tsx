import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useDismiss } from '../utils/hooks'
import { imageUrl, initials, placeholderColor } from '../utils/images'
import { inputClass } from './ui'

/**
 * An item's artwork. Purely decorative: the item's name is always shown as text
 * beside it, so a missing or blocked image falls back to initials on a tinted tile.
 */
export function ItemImage({ name, imageName, className = '', fit = 'contain', fallback }: {
  name: string
  imageName?: string
  className?: string
  fit?: 'contain' | 'cover'
  /** Shown instead of initials when there is no image (e.g. an ability's slot number). */
  fallback?: ReactNode
}) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [imageName])

  if (!imageName || failed) {
    return (
      <span
        aria-hidden
        className={`flex shrink-0 items-center justify-center font-display text-sm font-semibold text-ink/70 ${className}`}
        style={{ background: placeholderColor(name) }}
      >
        {fallback ?? initials(name)}
      </span>
    )
  }
  return (
    <img
      src={imageUrl(imageName)}
      alt=""
      loading="lazy"
      decoding="async"
      draggable={false}
      onError={() => setFailed(true)}
      className={`shrink-0 bg-void/60 ${fit === 'cover' ? 'object-cover' : 'object-contain'} ${className}`}
    />
  )
}

export interface PickerItem {
  key: string
  name: string
  imageName?: string
  /** Second line under the name. */
  detail?: string
  /** Tab the item belongs to. */
  group?: string
}

/** The selected item as a button: artwork, name and a line of stats. Opens a picker. */
export function ItemButton({ name, imageName, detail, placeholder, onClick, label }: {
  name: string
  imageName?: string
  detail?: string
  placeholder: string
  onClick: () => void
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="flex w-full items-center gap-3 border border-seam bg-void p-2 text-left transition-colors hover:border-tenno focus-visible:border-tenno"
    >
      {name
        ? <ItemImage name={name} imageName={imageName} className="size-14" />
        : <span className="flex size-14 shrink-0 items-center justify-center border border-dashed border-seam text-xl text-mute" aria-hidden>+</span>}
      <span className="min-w-0 flex-1">
        <span className="block truncate font-display text-lg font-semibold leading-tight">{name || placeholder}</span>
        {detail && <span className="block truncate text-[13px] text-mute">{detail}</span>}
      </span>
      <span className="shrink-0 pr-1 text-[13px] text-mute">Change</span>
    </button>
  )
}

/** A searchable grid of items with artwork, shown as a dialog. */
export function GridPicker({ title, items, selected, onSelect, onClose, columns = 'wide', allowNone }: {
  title: string
  items: PickerItem[]
  selected: string
  onSelect: (key: string) => void
  onClose: () => void
  columns?: 'wide' | 'narrow'
  /** Adds a first tile that clears the selection. */
  allowNone?: string
}) {
  const [search, setSearch] = useState('')
  const [group, setGroup] = useState('')
  const ref = useDismiss<HTMLDivElement>(true, onClose)

  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previous }
  }, [])

  const groups = useMemo(() => [...new Set(items.map((i) => i.group).filter((g): g is string => !!g))], [items])
  const shown = useMemo(() => {
    const q = search.trim().toLowerCase()
    return items.filter((i) => (!group || i.group === group) && (!q || i.name.toLowerCase().includes(q)))
  }, [items, search, group])

  const tab = (value: string, text: string) => (
    <button
      key={value}
      type="button"
      onClick={() => setGroup(value)}
      aria-pressed={group === value}
      className={`border px-2.5 py-1 text-[13px] font-medium ${
        group === value ? 'border-gold bg-gold/15 text-gold-pale' : 'border-seam bg-plate text-mute hover:text-ink'
      }`}
    >
      {text}
    </button>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-void/80 p-3 pt-[6vh] sm:p-6 sm:pt-[6vh]">
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="flex max-h-[86vh] w-full max-w-5xl flex-col border border-seam-bright bg-hull shadow-2xl shadow-black/60"
      >
        <header className="space-y-3 border-b border-seam p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base">{title}</h2>
            <button type="button" onClick={onClose} className="px-2 text-mute hover:text-ink" aria-label="Close">✕</button>
          </div>
          <input
            autoFocus
            aria-label="Search"
            placeholder="Search by name"
            spellCheck={false}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && shown.length > 0) { onSelect(shown[0].key); onClose() }
              if (e.key === 'Escape') onClose()
            }}
            className={inputClass}
          />
          {groups.length > 1 && (
            <div className="flex flex-wrap gap-1.5">
              {tab('', 'All')}
              {groups.map((g) => tab(g, g))}
            </div>
          )}
        </header>
        <ul className={`grid gap-2 overflow-y-auto p-4 ${
          columns === 'wide'
            ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5'
            : 'grid-cols-2 sm:grid-cols-3'
        }`}>
          {allowNone && !search && (
            <li>
              <button
                type="button"
                onClick={() => { onSelect(''); onClose() }}
                className="flex h-full w-full flex-col items-center justify-center gap-2 border border-dashed border-seam p-3 text-sm text-mute hover:border-tenno hover:text-ink"
              >
                {allowNone}
              </button>
            </li>
          )}
          {shown.map((item) => (
            <li key={item.key}>
              <button
                type="button"
                onClick={() => { onSelect(item.key); onClose() }}
                aria-current={item.key === selected}
                className={`flex h-full w-full flex-col items-center gap-1.5 border p-2 text-center transition-colors hover:border-tenno ${
                  item.key === selected ? 'border-gold bg-gold/10' : 'border-seam bg-plate'
                }`}
              >
                <ItemImage name={item.name} imageName={item.imageName} className="size-20" />
                <span className="font-display text-[15px] font-semibold leading-tight">{item.name}</span>
                {item.detail && <span className="text-[12px] leading-snug text-mute">{item.detail}</span>}
              </button>
            </li>
          ))}
          {shown.length === 0 && <li className="col-span-full p-4 text-sm text-mute">Nothing matches that search.</li>}
        </ul>
      </div>
    </div>
  )
}
