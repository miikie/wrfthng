# Warframe Damage Calculator — Web App Conversion Plan

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| **Backend** | **FastAPI** (Python) | The entire engine is already Python. FastAPI gives us async, auto-generated OpenAPI docs, Pydantic validation, and zero translation effort. |
| **Frontend** | **React + Vite + TypeScript** | Fast dev server, hot reload, strong typing for the complex data shapes. |
| **Styling** | **Tailwind CSS** | Utility-first, no component library lock-in, fast to iterate. Dark theme out of the box. |
| **State** | **Zustand** | Lightweight, no boilerplate, perfect for a single-page calculator. |
| **HTTP Client** | **fetch + SWR or TanStack Query** | Caching, deduplication, loading states for free. |
| **Package Manager** | **npm** | As requested. |
| **Dev Runner** | **concurrently** | Run backend + frontend in one terminal. |

No database needed — all data is static JSON loaded at server startup.

---

## Phase 0: Project Scaffolding

**Goal**: Monorepo structure, both servers start, health check works.

### Steps

1. Create the directory structure:
```
warframe_calc/
├── CLAUDE.md
├── portable.md
├── backend/
│   ├── requirements.txt          # fastapi, uvicorn, pydantic
│   ├── main.py                   # FastAPI app entry point
│   ├── engine/                   # MOVE existing engine/ here
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── damage.py
│   │   ├── enemies.py
│   │   ├── modding.py
│   │   └── weapons.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_weapons.py
│   │   ├── routes_enemies.py
│   │   ├── routes_mods.py
│   │   ├── routes_calculate.py
│   │   └── schemas.py            # Pydantic request/response models
│   └── data/                     # MOVE existing data/processed/ here
│       └── processed/
│           ├── weapons.json
│           ├── enemies.json
│           ├── core_mods.json
│           └── ...
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/                  # API client functions
│   │   ├── components/
│   │   ├── stores/               # Zustand stores
│   │   ├── types/                # TypeScript interfaces
│   │   └── utils/
│   └── public/
├── package.json                  # Root: "dev" script runs both
├── data/                         # Keep formulas for reference
│   └── formulas/
└── scripts/
    └── process_export_data.py
```

2. Initialize:
   - `npm init -y` at root
   - `npm create vite@latest frontend -- --template react-ts` for frontend
   - `cd frontend && npm install && npm install tailwindcss @tailwindcss/vite zustand @tanstack/react-query`
   - Create `backend/requirements.txt`: `fastapi`, `uvicorn[standard]`, `pydantic`
   - `pip install -r backend/requirements.txt --break-system-packages`
   - Install `concurrently` at root: `npm install --save-dev concurrently`

3. Move engine and data:
   - `mv engine/ backend/engine/`
   - `mv data/processed/ backend/data/processed/`
   - Update path references in engine files (the `Path("/home/claude/warframe_calc")` hardcodes need to become relative to `backend/`)

4. Create `backend/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Warframe Damage Calculator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

5. Root `package.json` scripts:
```json
{
  "scripts": {
    "dev": "concurrently \"npm run dev:backend\" \"npm run dev:frontend\"",
    "dev:backend": "cd backend && uvicorn main:app --reload --port 8000",
    "dev:frontend": "cd frontend && npm run dev"
  }
}
```

6. Configure Vite proxy in `frontend/vite.config.ts`:
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

7. Verify: `npm run dev` → both servers start, `curl localhost:8000/api/health` returns OK, frontend loads at localhost:5173.

**Done when**: `npm run dev` starts both servers, health check returns 200, frontend shows a blank React page.

---

## Phase 1: Data API Endpoints

**Goal**: All game data is queryable from the frontend. No calculations yet.

### Backend: Pydantic Schemas (`backend/api/schemas.py`)

Define response models for all data types:
- `WeaponSummary` (name, category, totalDamage, critChance, critMult, statusChance, fireRate) — for list views
- `WeaponDetail` (full stats including damage breakdown, tags, behaviours)
- `EnemySummary` (name, faction, baseLevel, health, armor, shield)
- `EnemyDetail` (full stats + scaled stats at a given level)
- `ModSummary` (name, type, stats at max rank)
- `ModDetail` (full stats, polarity, conditional, note)

### Backend: Routes

**Weapons** (`backend/api/routes_weapons.py`):
- `GET /api/weapons` — List all weapons. Query params: `?search=soma&category=LongGuns`
- `GET /api/weapons/{name}` — Full weapon detail by exact name

**Enemies** (`backend/api/routes_enemies.py`):
- `GET /api/enemies` — List all enemies. Query params: `?search=gunner&faction=Grineer`
- `GET /api/enemies/{key}` — Enemy detail
- `GET /api/enemies/{key}/scaled?level=100&steel_path=true&eximus=true` — Scaled stats at a level

**Mods** (`backend/api/routes_mods.py`):
- `GET /api/mods` — List all core mods. Query params: `?search=serration&type=PRIMARY&stat=DAMAGE`
- `GET /api/mods/{name}` — Mod detail at max rank
- `GET /api/mods/{name}?rank=5` — Mod detail at specific rank

### Backend: Singleton Loaders

In `backend/main.py`, load data once at startup:
```python
from engine.weapons import WeaponLoader
from engine.enemies import EnemyScaler
from engine.modding import ModResolver

weapon_loader = WeaponLoader("data/processed/weapons.json")
enemy_scaler = EnemyScaler("data/processed/enemies.json")
mod_resolver = ModResolver("data/processed/core_mods.json")
```

Pass these to route handlers via FastAPI dependency injection or just import them.

### Frontend: API Client (`frontend/src/api/`)

Create typed fetch wrappers:
- `getWeapons(search?, category?)` → `WeaponSummary[]`
- `getWeapon(name)` → `WeaponDetail`
- `getEnemies(search?, faction?)` → `EnemySummary[]`
- `getEnemy(key)` → `EnemyDetail`
- `getEnemyScaled(key, level, steelPath?, eximus?)` → `ScaledEnemyDetail`
- `getMods(search?, type?, stat?)` → `ModSummary[]`
- `getMod(name, rank?)` → `ModDetail`

### Frontend: TypeScript Types (`frontend/src/types/`)

Mirror the Pydantic schemas as TypeScript interfaces. Key types:
```typescript
interface WeaponDetail {
  name: string;
  category: string;
  damage: Record<string, number>;
  totalDamage: number;
  critChance: number;
  critMult: number;
  statusChance: number;
  fireRate: number;
  magSize: number;
  reloadTime: number;
  multishot: number;
  trigger: string;
  tags: string[];
}

interface ScaledEnemy {
  name: string;
  faction: string;
  currentLevel: number;
  health: number;
  shield: number;
  armor: number;
  overguard: number;
  armorDr: number;
  ehp: number;
}
```

**Done when**: You can hit all API endpoints from the browser/curl and get correct JSON. Frontend can fetch and console.log weapon/enemy/mod data.

---

## Phase 2: Calculation API

**Goal**: Full damage calculation available as an API endpoint.

### Backend: Calculation Route (`backend/api/routes_calculate.py`)

**`POST /api/calculate`**:
```json
{
  "weapon": "Soma Prime",
  "enemy": "heavy_gunner",
  "enemyLevel": 100,
  "mods": [
    {"name": "Serration", "rank": 10},
    {"name": "Split Chamber", "rank": 5},
    {"name": "Point Strike", "rank": 5},
    {"name": "Vital Sense", "rank": 5}
  ],
  "steelPath": false,
  "eximus": false,
  "headshot": false,
  "viralStacks": 0,
  "statusTypesOnTarget": 0,
  "armorStripPct": 0.0
}
```

Response: Full `CalculationResult` — modded stats, damage breakdown (per-type raw and inflicted), crit tiers, burst/sustained DPS, DoTs, kill estimates.

**`POST /api/compare`** (stretch):
Same but accepts an array of builds, returns results side-by-side.

### Backend: Pydantic Models for Calculation

- `CalculateRequest` — weapon name, enemy key, level, mod list, combat params
- `ModInput` — name + optional rank
- `CalculateResponse` — mirrors `CalculationResult` dataclass but as Pydantic
  - `DamageBreakdownResponse` with per_type dicts
  - `CritResponse` with tier info
  - `DPSResponse` with burst/sustained
  - `DoTResponse` list
  - Kill estimate fields

### Implementation

The route handler:
1. Look up weapon by name → `WeaponData`
2. Scale enemy → `ScaledEnemy`
3. Resolve each mod → `List[ResolvedMod]`
4. Call `DamageCalculator.calculate()` with all params
5. Serialize `CalculationResult` → JSON response

**Done when**: `POST /api/calculate` with a weapon, enemy, and mod list returns a full damage breakdown matching what the CLI produced.

---

## Phase 3: Frontend — Weapon & Enemy Selection

**Goal**: Users can select a weapon and enemy, see their base stats.

### Components

1. **`WeaponPicker`** — Searchable dropdown/combobox
   - Search-as-you-type against `/api/weapons?search=...`
   - Show category tags (Primary/Secondary/Melee/Shotgun)
   - On select: show stat card with base damage breakdown, crit, status, fire rate

2. **`EnemyPicker`** — Searchable dropdown
   - Filter by faction
   - On select: show base stats

3. **`EnemyConfig`** — Controls beside enemy picker
   - Level slider/input (1–9999)
   - Steel Path toggle
   - Eximus toggle
   - Shows scaled stats live (health/shield/armor/overguard/EHP)
   - Armor strip % slider (0–100%)
   - Viral stacks counter (0–10)

4. **`WeaponStatCard`** — Shows weapon stats in a clean layout
   - Damage per type with colored bars (physical = grey tones, elemental = colored)
   - Crit chance (highlight if >100% = orange tier)
   - Status chance
   - Fire rate, mag, reload

5. **`EnemyStatCard`** — Shows scaled enemy stats
   - Health bar, Shield bar, Armor bar
   - Armor DR percentage
   - Faction icon/name
   - EHP display

### Zustand Store (`frontend/src/stores/buildStore.ts`)

```typescript
interface BuildState {
  weapon: WeaponDetail | null;
  enemy: ScaledEnemy | null;
  enemyKey: string;
  enemyLevel: number;
  steelPath: boolean;
  eximus: boolean;
  viralStacks: number;
  armorStripPct: number;
  headshot: boolean;
  mods: ModInput[];    // Phase 4
  // ... actions
}
```

### Layout

Top-level layout:
```
┌─────────────────────────────────────────────┐
│  Warframe Simulacrum                        │
├──────────────────┬──────────────────────────┤
│  WEAPON          │  ENEMY                   │
│  [Search...]     │  [Search...]             │
│                  │  Level: [___] SP☐ EX☐    │
│  Stat Card       │  Stat Card               │
├──────────────────┴──────────────────────────┤
│  MODS (Phase 4)                             │
│  [8 mod slots]                              │
├─────────────────────────────────────────────┤
│  RESULTS (Phase 5)                          │
│  Damage breakdown, DPS, etc.                │
└─────────────────────────────────────────────┘
```

**Done when**: User can search and select a weapon and enemy, see their stats, adjust enemy level/SP/Eximus and watch stats update live.

---

## Phase 4: Frontend — Mod Loadout Builder

**Goal**: Users can build a mod loadout with 8 slots, see elemental combinations preview.

### Components

1. **`ModSlotGrid`** — 8 mod slots (or 9 for Exilus)
   - Each slot is a `ModSlot` component
   - Drag to reorder (elemental order matters!)
   - Visual: polarities, mod capacity (stretch goal)

2. **`ModSlot`** — Individual slot
   - Click to open `ModPicker`
   - Shows mod name, rank, key stats
   - Rank slider (0 to maxRank)
   - X button to remove

3. **`ModPicker`** — Modal/popover for selecting a mod
   - Search by name
   - Filter by type (PRIMARY/SECONDARY/MELEE/SHOTGUN)
   - Filter by stat (DAMAGE, CRIT_CHANCE, etc.)
   - Shows stat preview at max rank
   - Only shows mods compatible with selected weapon's mod_type
   - Prevents duplicate mods

4. **`ElementalPreview`** — Shows what elements the build produces
   - Display mod elements in slot order → combined result
   - Show innate weapon elements at the end
   - Color-coded element icons
   - e.g., "Cold + Toxin → Viral" with arrow animation

### Store Update

Add to buildStore:
```typescript
mods: { name: string; rank: number }[];  // Max 8
addMod(slot: number, name: string): void;
removeMod(slot: number): void;
setModRank(slot: number, rank: number): void;
reorderMods(from: number, to: number): void;
```

**Done when**: User can add/remove/reorder mods in 8 slots, adjust ranks, see elemental combination preview. Duplicate mods are blocked.

---

## Phase 5: Frontend — Results Display

**Goal**: Full damage calculation results displayed clearly.

### Components

1. **`ResultsPanel`** — Main results container
   - Triggers calculation via `POST /api/calculate` whenever weapon, enemy, or mods change
   - Debounce 300ms to avoid spam during slider drags
   - Loading skeleton while calculating

2. **`DamageBreakdown`** — Per-type damage display
   - Horizontal stacked bar: each damage type as a colored segment
   - Table below: Type | Raw Damage | After Armor/Faction | % of Total
   - Color coding: Impact=grey, Puncture=silver, Slash=gold, Heat=red, Cold=cyan, Electricity=blue, Toxin=green, Viral=teal, Corrosive=lime, Blast=orange, Radiation=yellow, Magnetic=purple, Gas=darkgreen, Void=white

3. **`CritDisplay`** — Crit tier breakdown
   - Show modded CC and CD
   - Tier indicator: "Yellow Crit" / "Orange Crit (132% CC)" / "Red Crit"
   - Guaranteed tier multiplier
   - Next tier chance
   - Average multiplier

4. **`DPSDisplay`** — DPS numbers
   - Average shot damage (big number)
   - Burst DPS
   - Sustained DPS
   - Fire rate, mag size, reload time (modded)
   - Shoot ratio (visual: pie chart of shooting vs reloading)

5. **`DoTDisplay`** — Status effect damage
   - Per DoT type: damage/tick, ticks, duration, total
   - Flag for "ignores armor" on Slash

6. **`KillEstimate`** — How fast does this kill
   - Enemy EHP
   - Shots to kill
   - Time to kill (seconds)
   - Visual: health bar depleting animation (stretch)

7. **`ArsenalTotal`** — The "Arsenal" damage number
   - Matches in-game Arsenal display for verification

### Combat Context Controls

Add to the results area or enemy config:
- Headshot toggle
- Status types on target (0-10 counter, for Condition Overload)
- Viral stacks (0-10 counter) — could also auto-estimate from status chance

**Done when**: Full damage pipeline results display on screen. Changing any input (weapon, enemy, level, mods, combat params) triggers recalculation and updates results.

---

## Phase 6: Polish & Compare Mode

**Goal**: Side-by-side build comparison, visual polish, QoL.

### Compare Mode

1. **`CompareView`** — Two builds side by side
   - Each side has its own weapon/mod/enemy config
   - Results displayed in parallel columns
   - Differences highlighted (green = better, red = worse)
   - Shared enemy option (same enemy for both, or different)

2. **Build Presets**
   - Save/load builds to localStorage
   - Name a build, save weapon + mods + enemy config
   - Quick-swap between saved builds

### Visual Polish

- Dark theme (Warframe aesthetic: dark background, gold/blue accents)
- Responsive layout (works on tablet+, not phone — too data-dense)
- Tooltips on hover for every stat explaining what it means
- Warframe-style fonts if available (or similar: Rajdhani, Exo 2)
- Damage type icons (optional — colored circles work fine)
- Smooth transitions on number changes (count-up animation)

### QoL Features

- URL state: share a build via URL query params
- Keyboard shortcuts: Ctrl+K to search weapons
- Recent weapons/enemies list
- "Popular builds" presets (Soma Prime viral crit, Rubico Eidolon, etc.)

**Done when**: Two builds can be compared side by side. Dark theme applied. Builds saveable to localStorage.

---

## Phase 7: Stretch Goals (Future)

These are NOT part of the initial conversion. Listed for reference.

- **Armor strip calculator**: Interactive slider showing armor → DR curve
- **Scaling graph**: Plot enemy EHP / your DPS across level range
- **Warframe ability integration**: Damage buffs (Roar, Eclipse, etc.)
- **Arcane integration**: Wire arcanes into calculator
- **Expand mod database**: Beyond core 108 mods
- **Deployment**: Docker compose, or static frontend + serverless backend
- **Status effect simulation**: Monte Carlo proc simulation over time
- **Build optimizer**: Given a weapon and enemy, suggest optimal mods

---

## Development Notes

### Running the project
```bash
npm run dev          # Starts both backend (8000) and frontend (5173)
npm run dev:backend  # Backend only
npm run dev:frontend # Frontend only
```

### Key invariants
- ALL calculation happens on the backend in Python. The frontend is a pure display layer.
- The engine modules (`engine/*.py`) should NOT be modified unless fixing a calculation bug. They are verified against the game.
- Data files in `data/processed/` are static and read-only at runtime.
- The `f32()` function MUST be used for all intermediate calculations that match the game. This is not optional — results will be wrong without it.

### Path references
When moving `engine/` to `backend/engine/`, update the hardcoded `/home/claude/warframe_calc` paths in the loader classes to use `Path(__file__).parent.parent / "data/processed"` or similar relative path.

### API conventions
- All endpoints under `/api/`
- Snake_case in Python/API, camelCase in TypeScript
- Use Pydantic's `model_config = ConfigDict(alias_generator=to_camel)` for automatic conversion
- Error responses: `{"detail": "Weapon not found: Soma Primer"}` with appropriate HTTP status

### Testing calculations
The CLI `simulacrum.py` has working calculation examples. Use these as reference to verify the API returns identical results:
- Soma Prime + Serration/Split Chamber/Point Strike/Vital Sense vs Heavy Gunner level 100
- Any weapon vs Steel Path Eximus enemies at high levels
