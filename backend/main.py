from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import (
    routes_calculate, routes_enemies, routes_extras, routes_mods, routes_survivability, routes_weapons,
)

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


app.include_router(routes_weapons.router)
app.include_router(routes_enemies.router)
app.include_router(routes_mods.router)
app.include_router(routes_calculate.router)
app.include_router(routes_extras.router)
app.include_router(routes_survivability.router)
