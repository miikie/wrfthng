import type {
  AmpCatalogue, BuffInfo, CalculateRequest, CalculationResult, CompanionInfo, EnemyDetail,
  EnemySummary, ModDetail, ScaledEnemy, SurvivabilityRequest, SurvivabilityResult, WarframeCatalogue,
  WeaponArcane, WeaponDetail, WeaponSummary,
} from '../types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Params = Record<string, string | number | boolean | undefined>

function query(params: Params): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') q.set(k, String(v))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError(0, 'Can’t reach the calculation server. Start it with “npm run dev”.')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${res.status})`
    throw new ApiError(res.status, detail)
  }
  return res.json()
}

const enc = encodeURIComponent

export const getWeapons = (search?: string, category?: string) =>
  request<WeaponSummary[]>(`/weapons${query({ search, category })}`)

export const getWeapon = (name: string) =>
  request<WeaponDetail>(`/weapons/${enc(name)}`)

export const getEnemies = (search?: string, faction?: string) =>
  request<EnemySummary[]>(`/enemies${query({ search, faction })}`)

export const getEnemy = (key: string) =>
  request<EnemyDetail>(`/enemies/${enc(key)}`)

export const getEnemyScaled = (
  key: string, level: number, steelPath = false, eximus = false, armorStripPct = 0,
) =>
  request<ScaledEnemy>(
    `/enemies/${enc(key)}/scaled${query({
      level, steel_path: steelPath, eximus, armor_strip_pct: armorStripPct,
    })}`,
  )

export const getMods = (search?: string, type?: string, stat?: string) =>
  request<ModDetail[]>(`/mods${query({ search, type, stat })}`)

export const getMod = (name: string, rank?: number) =>
  request<ModDetail>(`/mods/${enc(name)}${query({ rank })}`)

/** Every weapon, including the beast claws only companions can use. */
export const getAllWeapons = () =>
  request<WeaponSummary[]>('/weapons?include_companion=true')

export const getCompanions = () => request<CompanionInfo[]>('/companions')

export const getAmpParts = () => request<AmpCatalogue>('/amps')

export const getBuffs = () => request<BuffInfo[]>('/buffs')

export const getWeaponArcanes = () => request<WeaponArcane[]>('/weapon-arcanes')

export const getWarframes = () => request<WarframeCatalogue>('/warframes')

export const survivability = (body: SurvivabilityRequest) =>
  request<SurvivabilityResult>('/survivability', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const calculate = (body: CalculateRequest) =>
  request<CalculationResult>('/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
