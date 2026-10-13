import type { ReactNode } from 'react'
import { polarityGlyph, RARITY_COLORS } from '../utils/images'
import { ItemImage } from './ItemImage'

/**
 * The face of a mod card: artwork, rarity border, polarity, rank and name.
 * `children` renders below the name (stats, sliders), inside the same frame.
 */
export function ModCard({ name, imageName, rarity, polarity, rank, maxRank, size = 'rack', badge, dim, children }: {
  name: string
  imageName?: string
  rarity?: string
  polarity?: string
  rank?: number
  maxRank?: number
  size?: 'rack' | 'picker'
  /** Small label over the artwork, e.g. "3/5 stacks" or "In slot 2". */
  badge?: ReactNode
  dim?: boolean
  children?: ReactNode
}) {
  const color = RARITY_COLORS[rarity ?? ''] ?? '#8a99ad'
  const glyph = polarityGlyph(polarity ?? '')
  return (
    <div
      className={`flex h-full flex-col overflow-hidden border-2 bg-plate ${dim ? 'opacity-45' : ''}`}
      style={{ borderColor: color }}
    >
      <div className={`relative ${size === 'rack' ? 'h-24' : 'h-20'}`}>
        <ItemImage name={name} imageName={imageName} fit="cover" className="absolute inset-0 size-full" />
        <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-plate to-transparent" aria-hidden />
        {glyph && (
          <span
            className="absolute right-1 top-1 flex size-5 items-center justify-center bg-void/80 text-[12px] font-semibold text-ink"
            title={`${polarity} polarity`}
          >
            {glyph}
          </span>
        )}
        {maxRank !== undefined && maxRank > 0 && rank !== undefined && (
          <span className="absolute left-1 top-1 bg-void/80 px-1 text-[12px] font-semibold text-ink" title={`Rank ${rank} of ${maxRank}`}>
            R{rank}
          </span>
        )}
        {badge && (
          <span className="absolute bottom-1 right-1 bg-void/85 px-1 text-[11px] font-medium text-gold-pale">{badge}</span>
        )}
      </div>
      {children}
    </div>
  )
}

/** Rank shown as the game does: one pip per rank, filled up to the current one. */
export function RankPips({ rank, maxRank }: { rank: number; maxRank: number }) {
  if (maxRank <= 0) return null
  return (
    <span className="flex gap-[2px]" aria-hidden>
      {Array.from({ length: maxRank }, (_, i) => (
        <span key={i} className={`h-1 flex-1 ${i < rank ? 'bg-tenno' : 'bg-seam'}`} />
      ))}
    </span>
  )
}
