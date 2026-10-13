# Simulacrum: Warframe damage calculator

Two calculators in one web app:

- **Damage dealt**: a weapon with mods against a scaled enemy, with companions, amps and buffs.
- **Damage taken**: a Warframe with mods and abilities against incoming damage, layer by layer.

All maths runs in a Python engine using 32-bit floats to match the game. The React frontend only
displays what the API returns.

## Run it locally

Needs Python 3.11+ and Node 20+.

```
pip install -r backend/requirements.txt
npm install
npm install --prefix frontend
npm run dev
```

Then open http://localhost:5173. The API runs on port 8000.

```
npm test        # backend tests
npm run build   # type-check and build the frontend
```

Item artwork loads from the WFCD CDN (`cdn.warframestat.us`), so images need an internet
connection. Everything else works offline.

## Data

The app reads only `backend/data/processed/`, which is in the repository. Nothing has to be
downloaded to use it.

The scripts in `scripts/` rebuild that data from the game export and the wiki. They download
their inputs into `data/raw/`, which is not in the repository. `CLAUDE.md` lists the scripts in
the order to run them, and documents the engine and the rules it implements.

## Status

`todo.md` lists what is not modelled, not verified against the game, or not tested.
