// Item artwork comes straight from the WFCD community CDN; nothing is stored locally.
const WFCD_CDN = 'https://cdn.warframestat.us/img/'

export function imageUrl(imageName: string): string {
  return `${WFCD_CDN}${encodeURIComponent(imageName)}`
}

/** "Soma Prime" -> "SP", for the placeholder shown when an image is missing or fails to load. */
export function initials(name: string): string {
  const words = name.replace(/[^A-Za-z0-9 ]/g, ' ').split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

/** A stable muted colour per name, so placeholders are told apart at a glance. */
export function placeholderColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) % 360
  return `hsl(${hash} 28% 26%)`
}

export const RARITY_COLORS: Record<string, string> = {
  Common: '#b07a52',
  Uncommon: '#c3ccd6',
  Rare: '#cfa95e',
  Legendary: '#f1f4f7',
}

/** Polarity symbols, drawn as text so they need no image. */
export const POLARITY_GLYPHS: Record<string, string> = {
  Madurai: 'V',
  Vazarin: 'D',
  Naramon: '—',
  Zenurik: '=',
  Unairu: 'R',
  Penjaga: '+',
  Umbra: 'Ω',
}

export function polarityGlyph(polarity: string): string {
  return POLARITY_GLYPHS[polarity] ?? ''
}
