import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import type { ReactNode, Ref } from 'react'
import { useDismiss } from '../utils/hooks'
import { inputClass } from './ui'

const VISIBLE_LIMIT = 60

interface Props<T> {
  label: string
  items: T[]
  getKey: (item: T) => string
  /** Text the search matches against. */
  getText: (item: T) => string
  renderItem: (item: T) => ReactNode
  selectedText: string
  onSelect: (item: T) => void
  /** Shown first while the search box is empty. */
  recent?: T[]
  /** Extra filter control rendered beside the search box. */
  filter?: ReactNode
  emptyText?: string
  inputRef?: Ref<HTMLInputElement>
}

/** Search-as-you-type picker over a list that is already in memory. */
export function Combobox<T>({
  label, items, getKey, getText, renderItem, selectedText, onSelect,
  recent = [], filter, emptyText = 'Nothing matches that search.', inputRef,
}: Props<T>) {
  const listId = useId()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const close = useCallback(() => { setOpen(false); setQuery('') }, [])
  const rootRef = useDismiss<HTMLDivElement>(open, close)
  const listRef = useRef<HTMLUListElement>(null)

  const { shown, hidden, recentCount } = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) {
      const recentKeys = new Set(recent.map(getKey))
      const rest = items.filter((it) => !recentKeys.has(getKey(it)))
      const all = [...recent, ...rest]
      return {
        shown: all.slice(0, VISIBLE_LIMIT),
        hidden: Math.max(0, all.length - VISIBLE_LIMIT),
        recentCount: recent.length,
      }
    }
    // Names that start with the query rank above names that merely contain it.
    const starts: T[] = []
    const contains: T[] = []
    for (const it of items) {
      const text = getText(it).toLowerCase()
      if (text.startsWith(q)) starts.push(it)
      else if (text.includes(q)) contains.push(it)
    }
    const all = [...starts, ...contains]
    return {
      shown: all.slice(0, VISIBLE_LIMIT),
      hidden: Math.max(0, all.length - VISIBLE_LIMIT),
      recentCount: 0,
    }
  }, [items, recent, query, getKey, getText])

  useEffect(() => setActive(0), [query, items])

  useEffect(() => {
    listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' })
  }, [active])

  const choose = (item: T) => {
    onSelect(item)
    close()
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((a) => Math.min(shown.length - 1, a + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(0, a - 1))
    } else if (e.key === 'Enter' && open && shown[active]) {
      e.preventDefault()
      choose(shown[active])
      e.currentTarget.blur()
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <div className="flex gap-2">
        <input
          ref={inputRef}
          role="combobox"
          aria-label={label}
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open && shown[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          spellCheck={false}
          className={`${inputClass} font-display text-base font-semibold`}
          value={open ? query : selectedText}
          placeholder={open ? selectedText || label : label}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
          onKeyDown={onKeyDown}
        />
        {filter}
      </div>

      {open && (
        <div className="absolute inset-x-0 top-full z-30 mt-1 border border-seam-bright bg-plate shadow-xl shadow-black/50">
          <ul ref={listRef} id={listId} role="listbox" aria-label={label} className="max-h-80 overflow-y-auto">
            {shown.map((item, i) => (
              <li
                key={getKey(item)}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                className={`px-3 py-1.5 ${i === active ? 'bg-tenno/15' : ''} ${i === recentCount && recentCount > 0 ? 'border-t border-seam' : ''}`}
                onPointerMove={() => setActive(i)}
                onClick={() => choose(item)}
              >
                {renderItem(item)}
              </li>
            ))}
          </ul>
          {shown.length === 0 && <p className="px-3 py-3 text-sm text-mute">{emptyText}</p>}
          {hidden > 0 && (
            <p className="border-t border-seam px-3 py-1.5 text-[13px] text-mute">
              {hidden} more. Keep typing to narrow the list.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function FilterSelect({ label, value, onChange, options }: {
  label: string
  value: string
  onChange: (next: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="shrink-0 border border-seam bg-void px-2 py-1.5 text-sm text-ink focus:border-tenno focus:outline-none"
    >
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}
