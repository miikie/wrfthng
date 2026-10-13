"""Companion data: stats, precepts and which weapons each companion can use.

A companion's damage comes from a weapon (a Robotic weapon for Sentinels,
MOAs and Hounds, innate claws for beasts) that goes through the normal damage
pipeline with that weapon's own mods.
"""

import json
from pathlib import Path
from typing import Dict, Optional


class CompanionLoader:
    def __init__(self, path: str = "data/processed/companions.json"):
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        with open(p, encoding="utf-8") as f:
            self.companions: Dict[str, dict] = json.load(f)

    def get(self, name: str) -> Optional[dict]:
        return self.companions.get(name)
