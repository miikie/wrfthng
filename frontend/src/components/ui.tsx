import type { ReactNode } from 'react'
import { useAnimatedNumber } from '../utils/hooks'
import { damageColor } from '../utils/damageTypes'

export function Panel({ title, actions, children, className = '' }: {
  title: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`border border-seam bg-hull ${className}`}>
      <header className="flex min-h-11 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-seam px-4 py-2">
        <h2 className="text-base text-ink">{title}</h2>
        {actions}
      </header>
      <div className="p-4">{children}</div>
    </section>
  )
}

/** Explains a stat on hover or keyboard focus. */
export function Tip({ text, children, align = 'left' }: {
  text: string
  children: ReactNode
  align?: 'left' | 'right'
}) {
  return (
    <span className="group/tip relative inline-flex" tabIndex={0}>
      <span className="cursor-help underline decoration-seam-bright decoration-dotted underline-offset-4">
        {children}
      </span>
      <span
        role="tooltip"
        className={`pointer-events-none absolute bottom-full z-40 mb-2 hidden w-60 border border-seam-bright bg-plate px-3 py-2 text-left text-[13px] font-normal leading-snug text-ink shadow-lg shadow-black/40 group-hover/tip:block group-focus-visible/tip:block ${align === 'right' ? 'right-0' : 'left-0'}`}
      >
        {text}
      </span>
    </span>
  )
}

export function Stat({ label, tip, children, className = '' }: {
  label: string
  tip?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <dt className="text-[13px] text-mute">{tip ? <Tip text={tip}>{label}</Tip> : label}</dt>
      <dd className="text-lg font-medium leading-tight text-ink">{children}</dd>
    </div>
  )
}

export function Toggle({ label, checked, onChange, tip, disabled }: {
  label: string
  checked: boolean
  onChange: (next: boolean) => void
  tip?: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      title={tip}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`flex items-center gap-2 border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50 ${
        checked
          ? 'border-gold bg-gold/15 text-gold-pale'
          : 'border-seam bg-plate text-mute hover:border-seam-bright hover:text-ink'
      }`}
    >
      <span className={`size-2 rotate-45 ${checked ? 'bg-gold' : 'border border-mute'}`} aria-hidden />
      {label}
    </button>
  )
}

export function Counter({ label, value, min, max, onChange, tip, disabled }: {
  label: string
  value: number
  min: number
  max: number
  onChange: (next: number) => void
  tip?: string
  disabled?: boolean
}) {
  const step = (d: number) => onChange(Math.min(max, Math.max(min, value + d)))
  const button = 'size-7 border border-seam bg-plate text-ink hover:border-seam-bright disabled:opacity-40'
  return (
    <div>
      <div className="mb-1 text-[13px] text-mute">{tip ? <Tip text={tip}>{label}</Tip> : label}</div>
      <div className="flex items-center gap-1">
        <button type="button" className={button} disabled={disabled || value <= min}
          onClick={() => step(-1)} aria-label={`Decrease ${label}`}>−</button>
        <output className="w-9 text-center text-base font-medium">{value}</output>
        <button type="button" className={button} disabled={disabled || value >= max}
          onClick={() => step(1)} aria-label={`Increase ${label}`}>+</button>
      </div>
    </div>
  )
}

export function AnimatedNumber({ value, format }: {
  value: number
  format: (n: number) => string
}) {
  return <>{format(useAnimatedNumber(value))}</>
}

export function DamageChip({ type, title, strong, className = '' }: {
  type: string
  title?: string
  strong?: boolean
  className?: string
}) {
  const color = damageColor(type)
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap ${strong ? 'border px-2 py-0.5 font-semibold' : ''} ${className}`}
      style={strong ? { borderColor: color, color } : undefined}
    >
      <span className="size-2 shrink-0 rotate-45" style={{ background: color }} aria-hidden />
      {type}
    </span>
  )
}

export function Bar({ fraction, color, className = '' }: {
  fraction: number
  color: string
  className?: string
}) {
  const width = `${Math.min(100, Math.max(0, fraction * 100))}%`
  return (
    <div className={`h-1.5 bg-plate ${className}`}>
      <div className="h-full transition-[width] duration-300" style={{ width, background: color }} />
    </div>
  )
}

export function Notice({ children, tone = 'info' }: {
  children: ReactNode
  tone?: 'info' | 'error'
}) {
  return (
    <p className={`border-l-2 bg-plate px-3 py-2 text-sm ${tone === 'error' ? 'border-bad text-ink' : 'border-tenno text-mute'}`}>
      {children}
    </p>
  )
}

export const buttonClass =
  'border border-seam bg-plate px-3 py-1.5 text-sm font-medium text-ink transition-colors hover:border-seam-bright disabled:opacity-50'

export const inputClass =
  'w-full border border-seam bg-void px-3 py-1.5 text-ink placeholder:text-mute focus:border-tenno focus:outline-none'
