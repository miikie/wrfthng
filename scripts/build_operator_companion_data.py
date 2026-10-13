#!/usr/bin/env python3
"""Build the Operator / Amp / Companion raw data sets under data/raw/.

Sources (all cached under data/raw/wiki_cache_current/ and data/raw/wfcd_*.json):
  - wiki.warframe.com data modules (Lua tables): Focus, Companions, Weapons (companion, modular),
    Mods, Arcane. These are the current, maintained wiki's structured data.
  - wiki.warframe.com article wikitext for prose-only facts (focus node notes, amp braces,
    MOA / Hound parts, set bonuses, Drifter intrinsics).
  - WFCD warframe-items Mods.json / Arcanes.json for per-rank text of mods and arcanes.

Hand-written facts (stat formulas, pipeline notes) live in MECHANICS below, each with its source.

Usage: python scripts/build_operator_companion_data.py [--refresh]
"""

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lua_data  # noqa: E402
from scrape_wiki_abilities import strip_markup, bullets  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CACHE = RAW / "wiki_cache_current"
WIKI = "https://wiki.warframe.com/w/"
UA = "warframe-calc-data/1.0 (personal damage calculator; one-off data pull)"
CURL = shutil.which("curl") or "curl"
REFRESH = "--refresh" in sys.argv
WFCD_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/%s.json"

SCHOOLS = {
    "AP_ATTACK": "Madurai", "AP_DEFENSE": "Vazarin", "AP_DEFENCE": "Vazarin",
    "AP_TACTIC": "Naramon", "AP_POWER": "Zenurik", "AP_WARD": "Unairu",
}


# ============================================================================
# FETCHING
# ============================================================================

def fetch(title: str) -> str:
    """Raw wikitext of a wiki.warframe.com page, following redirects. '' if missing."""
    for _ in range(4):
        cache = CACHE / (re.sub(r"[/:()]", "_", title.replace(" ", "_")) + ".wiki")
        if cache.exists() and not REFRESH:
            text = cache.read_text(encoding="utf-8")
        else:
            url = WIKI + urllib.parse.quote(title.replace(" ", "_"), safe="/:") + "?action=raw"
            code, body = "", ""
            for attempt in range(4):
                try:
                    result = subprocess.run([CURL, "-sL", "-A", UA, "-w", "\n%{http_code}", url],
                                            capture_output=True, timeout=90)
                except subprocess.TimeoutExpired:
                    time.sleep(10)
                    continue
                body, _, code = result.stdout.decode("utf-8", errors="replace").rpartition("\n")
                if code in ("200", "404"):
                    break
                time.sleep(20 * (attempt + 1))
            text = body if code == "200" else ""
            cache.write_text(text, encoding="utf-8", newline="\n")
            time.sleep(1.0)
        redirect = re.match(r"\s*#REDIRECT\s*\[\[:?([^\]#|]+)", text, re.I)
        if not redirect:
            return text
        title = redirect.group(1).strip()
    return ""


def module(title: str):
    return lua_data.parse(fetch(title))


def mods_module():
    text = fetch("Module:Mods/data")
    start = text.index("local modData = {") + len("local modData = ")
    return lua_data.parse("return " + text[start:text.rindex("return modData")])


def wfcd(name: str):
    path = RAW / f"wfcd_{name.lower()}.json"
    if not path.exists() or REFRESH:
        subprocess.run([CURL, "-sL", "-o", str(path), WFCD_URL % name], check=True, timeout=180)
    return json.loads(path.read_text(encoding="utf-8"))


def write(rel: str, data):
    path = RAW / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  wrote {rel}")


# ============================================================================
# TEXT HELPERS
# ============================================================================

NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def clean(text) -> str:
    text = re.sub(r"<DT_(\w+?)(?:_COLOR)?>", "", text or "")
    text = re.sub(r"<[A-Z_0-9]+>", "", text)
    return re.sub(r"\s*\r?\n\s*", "; ", strip_markup(text)).strip()


def rank_values(texts):
    """Numbers that vary across a list of per-rank strings -> list of per-rank lists."""
    rows = [[float(n.replace(",", "")) for n in NUMBER.findall(t)] for t in texts]
    if not rows or len({len(r) for r in rows}) != 1:
        return []
    out = []
    for column in zip(*rows):
        values = [int(v) if v == int(v) else v for v in column]
        if len(set(values)) > 1:
            out.append(values)
    return out


def sections(text: str):
    """{heading: body} for every ==...== heading (any depth); last one wins on duplicates."""
    parts = re.split(r"^=+\s*([^=\n]+?)\s*=+\s*$", text, flags=re.M)
    return {strip_markup(h): b for h, b in zip(parts[1::2], parts[2::2])}


def gallery_items(body: str):
    """Entries of a <gallery>: 'File.png|'''[[X#Name|Name]]'''<br/>line<br/>line' -> (name, [lines])."""
    items = []
    for block in re.findall(r"<gallery[^>]*>(.*?)</gallery>", body, re.S):
        for line in block.strip().split("\n"):
            if "|" not in line:
                continue
            fields = [strip_markup(p) for p in re.split(r"<br\s*/?>", line.split("|", 1)[1], flags=re.I)]
            fields = [f for f in fields if f]
            if fields:
                items.append((fields[0], fields[1:]))
    return items


def wikitable(body: str):
    """First wikitable in body -> list of dict rows keyed by header."""
    m = re.search(r"\{\|.*?\n\|\}", body, re.S)
    if not m:
        return []
    table = re.sub(r"<!--.*?-->", "", m.group(0), flags=re.S)
    table = re.sub(r"\n\|\+[^\n]*", "", table)
    headers, rows = [], []
    for chunk in re.split(r"\n\|-[^\n]*", table):
        cells = [c for c in re.split(r"\n[!|]|\|\||!!", "\n" + chunk.strip()) if c.strip()]
        cells = [strip_markup(re.sub(r'^[^|\[{]*="[^"]*"\s*\|', "", c)) for c in cells]
        cells = [c for c in cells if c and not c.startswith("{|")]
        if not cells:
            continue
        if "\n!" in "\n" + chunk.strip() and not headers:
            headers = cells
        elif headers:
            rows.append(dict(zip(headers, cells)))
    return rows


def pct(text: str):
    m = re.search(r"([+-]?\d+\.?\d*)\s*%", text)
    return float(m.group(1)) / 100 if m else None


# ============================================================================
# SYSTEM 1: OPERATOR / DRIFTER / FOCUS
# ============================================================================

# Focus ways that touch the weapon/warframe damage pipeline. Steps refer to CLAUDE.md's 20-step list.
# "effect" is written from the in-game description plus the wiki's node notes.
FOCUS_DAMAGE_EFFECTS = {
    "Phoenix Talons": {"pipeline_step": 3, "type": "additive with physical damage mods",
                       "target": "Warframe weapon Impact/Puncture/Slash damage; all Operator damage",
                       "note": "NOT a Heat bonus. In-game text: 'Physical Damage and Operator Damage increased by X%'."},
    "Phoenix Spirit": {"pipeline_step": 4, "type": "additive with elemental damage mods",
                       "target": "Warframe weapon elemental damage",
                       "note": "Game data text is 'Elemental Damage increased by |PERCENT|%' with no per-rank numbers; confirm in game before wiring."},
    "Void Strike": {"pipeline_step": 2, "type": "additive with base damage mods (Serration, Condition Overload)",
                    "target": "Warframe weapons and Operator/Amp damage",
                    "note": "Bonus = per-rank % x percentage of Operator energy consumed (100% energy at rank 3 = +1000%). For amps it is additive with other Operator damage bonuses."},
    "Void Fuel": {"pipeline_step": None, "type": "ammo efficiency", "target": "Warframe and Operator weapons",
                  "note": "Sustained DPS only (fewer reloads); does not change per-shot damage."},
    "Power Transfer": {"pipeline_step": 7, "type": "additive crit damage (amp)", "target": "Amp critical damage",
                       "note": "Amp only; the Warframe half is casting speed."},
    "Contamination Wave": {"pipeline_step": 9, "type": "damage vulnerability", "target": "Operator damage only",
                           "note": "Enemy-side multiplier for Operator/Amp damage; Distilled Contamination adds stacks."},
    "Distilled Contamination": {"pipeline_step": 9, "type": "damage vulnerability", "target": "Operator damage only", "note": ""},
    "Sling Strength": {"pipeline_step": None, "type": "ability strength", "target": "Warframe abilities",
                       "note": "Indirect: raises strength-scaling weapon buffs (Roar, Eclipse, Vex Armor)."},
    "Overwhelming Power": {"pipeline_step": None, "type": "ability strength", "target": "Warframe abilities", "note": "Tauron Strike way."},
    "Power Spike": {"pipeline_step": 7, "type": "combo counter retention", "target": "Melee combo multiplier",
                    "note": "Feeds Blood Rush / Weeping Wounds / heavy attack multiplier by keeping combo up; no direct stat."},
    "Opening Slam": {"pipeline_step": 7, "type": "combo gain x2", "target": "Melee combo multiplier", "note": ""},
    "Void Stalker": {"pipeline_step": 7, "type": "additive melee crit chance", "target": "Warframe melee critical chance",
                     "note": "Ramps up in Void Mode, decays over 20s after leaving it."},
    "Killer's Rush": {"pipeline_step": 7, "type": "additive melee crit chance", "target": "Warframe melee critical chance", "note": ""},
    "Sling Stun": {"pipeline_step": None, "type": "finisher damage vulnerability", "target": "Finisher damage", "note": ""},
    "Executing Dash": {"pipeline_step": None, "type": "finisher damage vulnerability", "target": "Finisher damage", "note": ""},
    "Amp Spike": {"pipeline_step": 2, "type": "amp damage bonus", "target": "Amp damage", "note": "Requires 8x melee combo on transfer."},
    "Lethal Levitation": {"pipeline_step": 2, "type": "operator damage bonus, stacking", "target": "Operator damage", "note": ""},
    "Vexoric Tauron Strike": {"pipeline_step": 7, "type": "combo gain", "target": "Melee combo multiplier", "note": ""},
    "Caustic Strike": {"pipeline_step": 9, "type": "armor strip (percent of armor)", "target": "Enemy armor",
                       "note": "Maps directly onto EnemyScaler.scale_enemy(armor_strip_pct=...). 100% at max rank."},
    "Sundering Dash": {"pipeline_step": 9, "type": "armor strip (percent of armor)", "target": "Enemy armor", "note": "Per Void Sling pass."},
    "Magnetic Flare": {"pipeline_step": 9, "type": "shield removal", "target": "Enemy shields", "note": "Disables shields inside the field."},
    "Unairu Wisp": {"pipeline_step": 2, "type": "operator damage bonus", "target": "Operator damage", "note": ""},
    "Vengeance": {"pipeline_step": 2, "type": "operator damage bonus", "target": "Operator damage", "note": "Only during Last Gasp."},
    "Stone Skin": {"pipeline_step": None, "type": "flat armor", "target": "Warframe and Operator armor", "note": "Survivability only."},
    "Tempered Benison": {"pipeline_step": None, "type": "flat armor", "target": "Warframe armor", "note": "Survivability only."},
    "Eroding Rapids": {"pipeline_step": 18, "type": "status vulnerability", "target": "Status application on enemies in the vortex", "note": ""},
    "Rift Waters": {"pipeline_step": 9, "type": "overguard strip", "target": "Enemy overguard", "note": ""},
    "Inner Might": {"pipeline_step": None, "type": "free ability cast", "target": "Warframe energy", "note": "Indirect."},
    "Hardened Wellspring": {"pipeline_step": None, "type": "ability strength", "target": "Warframe abilities",
                            "note": "Grants Ability Strength (not armor) to those inside the Wellspring."},
    "Spectral Pages": {"pipeline_step": None, "type": "ability strength/duration/cast speed", "target": "Warframe abilities", "note": ""},
    "Boundless Energy": {"pipeline_step": None, "type": "ability strength/duration/cast speed", "target": "Warframe abilities", "note": ""},
    "Temporal Shot": {"pipeline_step": 13, "type": "headshot damage bonus", "target": "Weak point damage on slowed enemies", "note": ""},
    "Temporal Drag": {"pipeline_step": None, "type": "enemy slow", "target": "Enemies", "note": "Enables Temporal Shot."},
}


def focus_nodes_from_page(school: str):
    """{{FocusNode|name=..|desc=..|warframe=y|operator=y|info=...}} blocks on the school page."""
    text = fetch(f"Focus/{school}")
    nodes = {}
    for start in [m.start() for m in re.finditer(r"\{\{FocusNode", text)]:
        depth, i = 0, start
        while i < len(text) - 1:
            if text[i:i + 2] == "{{":
                depth, i = depth + 1, i + 2
            elif text[i:i + 2] == "}}":
                depth, i = depth - 1, i + 2
                if depth == 0:
                    break
            else:
                i += 1
        body = text[start + len("{{FocusNode"):i - 2]
        parts = re.split(r"\|\s*(name|distance|icon|desc|warframe|operator|info|TauronResource|TauronCost)\s*=", body)
        params = {k: v.strip() for k, v in zip(parts[1::2], parts[2::2])}
        if not params.get("name"):
            continue
        nodes[strip_markup(params["name"])] = {
            "affects_warframe": params.get("warframe", "").startswith("y"),
            "affects_operator": params.get("operator", "").startswith("y"),
            "wiki_notes": bullets(params.get("info", "")),
            "tauron_cost": ({"resource": params["TauronResource"], "per_rank": params.get("TauronCost")}
                            if params.get("TauronResource") else None),
        }
    return nodes


def build_focus():
    data = module("Module:Focus/data")
    costs = sections(fetch("Focus")).get("Costs", "")
    cost_notes = bullets(costs)
    tier_costs = {
        0: {"unlock": 25000, "rank_ups": [50000, 105000, 200000], "total": 380000},
        1: {"unlock": 60000, "rank_ups": [105000, 215000, 400000], "total": 780000},
        2: {"unlock": 95000, "rank_ups": [160000, 325000, 600000], "total": 1180000},
    }
    by_school = {}
    for name, way in data["Ways"].items():
        by_school.setdefault(SCHOOLS[way["Polarity"]], []).append((name, way))

    for school, ways in by_school.items():
        page = focus_nodes_from_page(school)
        nodes = []
        for name, way in sorted(ways, key=lambda kv: (kv[1].get("NodeDistance", 9), kv[0])):
            texts = [clean(level["Stats"]) for level in way.get("LevelStats", [])]
            extra = page.get(name, {})
            tauron = "Tauron" in name or bool(extra.get("tauron_cost"))
            node = {
                "name": name,
                "kind": "waybound passive" if way.get("IsWayBound") else "passive" if way.get("IsPassive") else "active",
                "tree_distance": way.get("NodeDistance"),
                "max_rank": way.get("MaxRank"),
                "capacity_cost": way.get("BaseDrain"),
                "description": clean(way.get("Description")),
                "per_rank_text": texts,
                "per_rank_values": rank_values(texts),
                "affects_warframe": extra.get("affects_warframe"),
                "affects_operator": extra.get("affects_operator"),
                "wiki_notes": extra.get("wiki_notes", []),
                "internal_name": way.get("InternalName"),
            }
            if name not in page:
                node["status"] = "legacy"
                node["_notes"] = ["Not on the current school page: a Focus 2.0 way kept in the wiki data. Not obtainable in the current game."]
            else:
                node["status"] = "current"
            if tauron:
                node["tauron_way"] = True
                if extra.get("tauron_cost"):
                    node["tauron_cost"] = extra["tauron_cost"]
            energy = re.search(r"[Cc]osts?(?: an additional)? (\d+) [Ee]nergy(/s)?", node["description"])
            if energy:
                node["energy_cost"] = {"value": int(energy.group(1)), "per_second": bool(energy.group(2))}
            if not tauron and way.get("NodeDistance") in tier_costs and not way.get("IsWayBound"):
                node["focus_point_cost"] = tier_costs[way["NodeDistance"]]
            effect = FOCUS_DAMAGE_EFFECTS.get(name)
            node["affects_damage_calc"] = bool(effect) and name in page
            if effect:
                node["damage_effect"] = effect
            nodes.append(node)
        write(f"operator/focus_{school.lower()}.json", {
            "school": school,
            "description": clean(data["Schools"][school]["Description"]),
            "wiki_url": WIKI + f"Focus/{school}",
            "source": "wiki.warframe.com Module:Focus/data (per-rank text) + Focus/%s (applicability, notes)" % school,
            "tree_structure": "tree_distance is the node's distance from the central root way (0 = root). The data does not "
                              "record which specific node unlocks which; a node needs an unlocked neighbour closer to the root.",
            "cost_rules": cost_notes,
            "current_node_count": sum(1 for n in nodes if n["status"] == "current"),
            "nodes": sorted(nodes, key=lambda n: (n["status"] != "current", n["tree_distance"], n["name"])),
        })
    return data


def build_operator_stats():
    intrinsics = {}
    for tree in ("Combat", "Riding", "Opportunity", "Endurance"):
        rows = []
        text = fetch(f"Drifter/Intrinsics/{tree}")
        for chunk in re.split(r"\n\|-[^\n]*", text)[1:]:
            cells = [c.strip() for c in re.split(r"\n\|", "\n" + chunk.strip()) if c.strip()]
            if len(cells) >= 3 and re.match(r"'*\d+'*$", cells[0]):
                rows.append({"rank": int(cells[0].strip("'")), "name": strip_markup(cells[1]),
                             "description": strip_markup(cells[2]),
                             "notes": bullets(cells[3]) if len(cells) > 3 else []})
        intrinsics[tree] = rows
    drifter_weapons = {}
    weapons = json.loads((ROOT / "backend" / "data" / "processed" / "weapons.json").read_text(encoding="utf-8"))
    for name, w in weapons.items():
        if w.get("category") in ("DrifterMelee", "OperatorAmps"):
            drifter_weapons[name] = {k: w.get(k) for k in ("category", "damage", "totalDamage", "critChance", "critMult", "statusChance", "fireRate")}

    write("operator/operator_base_stats.json", {
        "source": "wiki.warframe.com Operator/Gameplay (Stats, Health/Armor Calculation), Void Sling, Void Mode, Damage/Void Damage",
        "base_stats": {
            "health": {"base": 100, "after_quills_initiation": 350, "note": "350 once the Operator has an Amp from The Quills"},
            "armor": 75, "shields": 350, "shield_gating": True, "energy": 100,
            "energy_regen": "accelerating, 5 energy per second squared",
        },
        "rank_scaling": "None. Operators have no level; stats change only through Focus ways and Magus arcanes.",
        "formulas": {
            "health": "HP = BaseHP x (1 + Enduring Tides) + Magus Vigor   (350 x 3 + 600 = 1650 max)",
            "armor": "Armor = Base x (1 + Enduring Tides) + Magus Husk + Stone Skin   (75 x 3 + 300 + 200 = 725 max)",
            "damage_reduction": "Armor / (Armor + 300)",
            "effective_health": "HP x (Armor + 300) / 300",
        },
        "modifiers": {
            "Enduring Tides (Vazarin waybound)": "+200% Operator health and armor at max rank",
            "Basilisk Scales (Unairu waybound)": "+200% Operator armor at max rank",
            "Stone Skin (Unairu)": "+200 armor to Warframe and Operator at max rank",
            "Magus Vigor": "+600 health at max rank", "Magus Husk": "+300 armor at max rank",
            "Rejuvenating Tides (Vazarin waybound)": "+6 health/s as Operator, doubled while in the Warframe",
        },
        "void_powers": {
            "Void Beam": {"damage_type": "Void", "damage_per_second": 2000, "crit_multiplier": 1.5, "range_m": 20,
                          "note": "Unarmed attack; replaced by the Amp's prism/scaffold once an Amp is equipped. Removes Sentient adaptation."},
            "Void Sling": {"energy_cost": 25, "distance_m": [12, 32], "energy_restored_per_enemy_hit": 10},
            "Void Mode": {"energy_cost_per_second": 5, "effect": "invisible and immune to damage and status"},
            "Void Blast": {"note": "Melee-key radial knockback; several Focus ways modify it (Flame Blast, Rising Blast, Voltaic Blast)."},
        },
        "transference": {
            "warframe_state": "Left where it stood, normally invulnerable; with certain channelled abilities active it is vulnerable but gets 90% damage reduction.",
            "operator_death": "No bleedout: control returns to the Warframe, its shields are emptied and it gains Transference Static.",
            "transference_static_warframe_max_health": {"1": 0.8, "2": 0.5, "3": 0.2, "4": 0.0},
            "companions": "Sentinels stay with the Warframe; beasts, MOAs and Hounds follow the Operator. Both keep attacking.",
            "mods": "Warframe and weapon mods do not affect the Operator.",
        },
        "void_damage": {
            "vs_health_types": "Neutral to every faction; bonus against Overguard and Zariman void manifestations.",
            "status": "Bullet Attractor: 2.5 m field for 3 s that pulls shots onto the target.",
            "sentients": "Resets damage adaptation and stuns drone-type Sentients; bypasses Eidolon invulnerabilities.",
            "not_physical_or_elemental": "Gets nothing from Phoenix Talons' physical bonus and ignores sortie physical/elemental resist modifiers.",
        },
        "tektolyst_artifacts": "After The Old Peace each school has a Tektolyst Artifact: a third Operator ability (Tauron Strike), "
                               "5 Operator mod slots and 1 arcane slot. The Tauron ways are in the focus_*.json files.",
    })
    write("operator/drifter_base_stats.json", {
        "source": "wiki.warframe.com Drifter/Gameplay, Drifter/Intrinsics/*",
        "base_stats": {"health": 250, "shields": 0, "note": "Duviri values. Abilities run on cooldowns, not energy."},
        "outside_duviri": "The Drifter is interchangeable with the Operator: same Focus school, Void powers and Amp mechanics. "
                          "An Amp equipped on the Drifter always looks like the Sirocco but behaves as the equipped Amp. "
                          "Operator and Drifter can carry different Amps and arcanes.",
        "duviri_abilities": ["Summon Kaithe", "Guiding Hand", "Restorative", "Smoke Screen",
                             "Transference Surge (Combat rank 3): summon the Warframe for 10 s, 15 s at Combat rank 8"],
        "kaithe_abilities": ["Hoof Stomp (Riding rank 3)", "Steadfast Dismount (Riding rank 6)"],
        "melee": {
            "moves": ["target lock", "parry / projectile reflect", "Power Strike (block + heavy, on cooldown)", "quick-shot with the Sirocco"],
            "power_strikes": {
                "Sun & Moon": "two arcs of explosive energy, Electricity damage, guaranteed status",
                "Syam": "two spinning slashes, inflicts Lifted",
                "Azothane": "five energy blades in a cone, Cold damage, guaranteed status",
                "Edun": "dust cloud, Knockdown, opens to ground finisher",
                "Sampotes": "shockwave in a line, Heat damage, guaranteed status",
                "Argo & Vel": "charged swing, inflicts Slash; a perfect parry resets the cooldown",
            },
            "combo_damage_values": "Not published on the wiki as per-hit multipliers. Weapon base stats below come from the game export.",
        },
        "weapons_from_game_export": drifter_weapons,
        "intrinsics": intrinsics,
        "intrinsics_and_damage": "Combat rank 1 (Deadly Decrees): +10% damage per active Decree, additive with base damage mods "
                                 "(pipeline step 2). Only rank 9 of each tree has an effect outside Duviri.",
    })


# ============================================================================
# SYSTEM 2: AMPS
# ============================================================================

BRACES = {  # wiki.warframe.com Amp, "Components and Names" table
    "Clapkra Brace": {"series": 1, "vendor": "The Quills", "amp_energy": 40},
    "Juttni Brace": {"series": 2, "vendor": "The Quills", "recharge_delay_s": -1},
    "Lohrin Brace": {"series": 3, "vendor": "The Quills", "crit_chance": 0.12, "status_chance": 0.12},
    "Anspatha Brace": {"series": 4, "vendor": "The Quills", "amp_energy": 20, "recharge_rate_per_s": 15},
    "Suo Brace": {"series": 5, "vendor": "Vox Solaris", "amp_energy": 100, "recharge_delay_s": 2},
    "Plaga Brace": {"series": 6, "vendor": "Vox Solaris", "amp_energy": -20, "recharge_delay_s": -1.5},
    "Certus Brace": {"series": 7, "vendor": "Vox Solaris", "crit_chance": 0.20},
}
SERIES = {"Raplak": 1, "Pencha": 1, "Shwaak": 2, "Shraksun": 2, "Granmu": 3, "Klebrik": 3, "Rahn": 4, "Phahd": 4,
          "Cantic": 5, "Exard": 5, "Lega": 6, "Dissic": 6, "Klamora": 7, "Propa": 7}


def amp_part(name, entry):
    attacks = []
    for a in entry.get("Attacks", []):
        attacks.append({
            "name": a.get("AttackName"), "damage": a.get("Damage"),
            "total_damage": round(sum((a.get("Damage") or {}).values()), 4),
            "crit_chance": a.get("CritChance"), "crit_multiplier": a.get("CritMultiplier"),
            "status_chance": a.get("StatusChance"), "fire_rate": a.get("FireRate"),
            "multishot": a.get("Multishot"), "ammo_cost": a.get("AmmoCost"),
            "shot_type": a.get("ShotType"), "range": a.get("Range"), "falloff": a.get("Falloff"),
            "punch_through": a.get("PunchThrough"), "charge_time": a.get("ChargeTime"),
            "burst_count": a.get("BurstCount"), "explosion_radius": (a.get("Falloff") or {}).get("EndRange") if a.get("ShotType") == "AoE" else None,
        })
        attacks[-1] = {k: v for k, v in attacks[-1].items() if v is not None}
    return {
        "name": name, "series": SERIES.get(name.split()[0]),
        "trigger": entry.get("Trigger"), "magazine_energy": entry.get("Magazine"),
        "recharge_delay_s": entry.get("ReloadDelay"), "recharge_rate_per_s": entry.get("ReloadRate"),
        "full_recharge_s": entry.get("Reload"), "accuracy": entry.get("Accuracy"),
        "attacks": attacks, "introduced": entry.get("Introduced"), "internal_name": entry.get("InternalName"),
    }


def arcane_ranks(arcanes_wfcd, name):
    for a in arcanes_wfcd:
        if a["name"] == name:
            return [clean("; ".join(level["stats"]).replace("\\n", "; ")) for level in a.get("levelStats", [])]
    return []


def build_amps():
    modular = module("Module:Weapons/data/modular")
    amps = {n: e for n, e in modular.items() if e.get("Class") == "Amp"}
    write("amps/prisms.json", {
        "source": "wiki.warframe.com Module:Weapons/data/modular",
        "note": "A prism is the Amp's primary fire. Mote Amp and Sirocco are complete amps listed here for their primary fire.",
        "prisms": [amp_part(n, e) for n, e in sorted(amps.items()) if "Prism" in n or n in ("Mote Amp", "Sirocco")],
    })
    write("amps/scaffolds.json", {
        "source": "wiki.warframe.com Module:Weapons/data/modular",
        "note": "A scaffold is the Amp's alternate fire.",
        "scaffolds": [amp_part(n, e) for n, e in sorted(amps.items()) if "Scaffold" in n],
    })
    write("amps/braces.json", {
        "source": "wiki.warframe.com Amp page, component table",
        "note": "Braces modify both the prism and the scaffold. Crit/status values are added to the part's base chance. "
                "The base Amp energy pool is 100 with a 2 s recharge delay and 30/s recharge (see prisms.json).",
        "braces": [{"name": n, **v} for n, v in BRACES.items()],
    })

    arcane_mod = module("Module:Arcane/data")["Arcanes"]
    arc_wfcd = wfcd("Arcanes")
    groups = {"Amp": [], "Operator": [], "Tektolyst Artifacts": []}
    for name, a in sorted(arcane_mod.items()):
        if a.get("Type") not in groups:
            continue
        texts = arcane_ranks(arc_wfcd, name)
        groups[a["Type"]].append({
            "name": name, "max_rank": a.get("MaxRank"), "rarity": a.get("Rarity"),
            "effect_at_max_rank": clean(a.get("Description")),
            "per_rank_text": texts, "per_rank_values": rank_values(texts),
            "upgrade_types": a.get("UpgradeTypes"),
        })
    write("amps/virtuous_arcanes.json", {
        "source": "wiki.warframe.com Module:Arcane/data + WFCD Arcanes.json (per-rank text)",
        "note": "The in-game spelling is 'Virtuos'. Amps have two arcane slots (the second needs an Amp Arcane Adapter). "
                "Magus/Emergence arcanes go on the Operator, Zid-An arcanes on Tektolyst Artifacts.",
        "amp_arcanes": groups["Amp"], "operator_arcanes": groups["Operator"],
        "tektolyst_arcanes": groups["Tektolyst Artifacts"],
    })
    write("amps/amp_mechanics.json", {
        "source": "wiki.warframe.com Amp, Damage/Void Damage, Focus/Madurai; weapon data module",
        "assembly": "Prism (primary fire) + Scaffold (alt fire) + Brace (stat modifier). 7 of each, 343 combinations. "
                    "Community shorthand is three series digits, e.g. 777 = Klamora / Propa / Certus.",
        "pipeline": {
            "same_as_weapons": "Yes for the core: base damage x multishot, crit tiers from crit chance, status chance per pellet, "
                               "fire rate, and the same armor / faction-type math. Amp parts are ordinary weapon entries in the game data.",
            "mods": "Amps take no mods. Steps 1-4 of the pipeline only see arcanes, Focus ways and the brace.",
            "quantization": "No mods means modded base = base, so step 5 quantization leaves values unchanged. "
                            "Whether damage bonuses from arcanes are quantized is unverified.",
            "multishot": "Exists per part (e.g. Shwaak, Granmu fire several projectiles); nothing increases it.",
            "ammo": "Amps spend a 100-point Amp energy pool that recharges (30/s after a 2 s delay) instead of reloading. "
                    "Sustained DPS should use magazine_energy / ammo_cost shots, then recharge_delay + pool / recharge_rate.",
            "crit_status": "Brace crit/status bonuses are flat additions to the part's base chance, not multipliers.",
        },
        "void_damage": {
            "faction_modifiers": "Void is neutral against every health type; +50% only against Overguard and Zariman void manifestations. "
                                 "FACTION_MODIFIERS in engine/constants.py needs no Void rows other than those.",
            "armor": "Void is reduced by armor like any non-True damage type.",
            "conversion": "Virtuos Forge / Spike / Surge / Trojan convert 98% of Void to Heat / Puncture / Electricity / Viral at max rank; "
                          "converted damage then uses that type's faction modifiers.",
        },
        "damage_bonuses": {
            "additive_group": "Void Strike, Phoenix Talons (Operator damage), Unairu Wisp, Virtuos Fury, Eternal Eradicate, Amp Spike "
                              "and Lethal Levitation add together as one Operator damage bonus.",
            "void_strike": "Rank 3: +10% damage per 1% of Operator energy consumed, for 8 s, 40 s cooldown. Full energy = +1000%.",
            "vulnerability": "Contamination Wave (+50%, plus 25% per Distilled Contamination stack up to 4) multiplies Operator damage taken by the enemy.",
            "crit": "Certus/Lohrin brace (flat), Virtuos Shadow (+60% CC), Eternal Onslaught (+180% CC), Virtuos Strike (+80% CD), "
                    "Power Transfer (+100% CD), Zid-An Osbok (+3.0x CD).",
        },
        "unverified": ["Stacking order between arcane crit chance bonuses and brace bonuses",
                       "Whether Eternal Onslaught's 180% is additive or multiplicative with base crit chance"],
    })
    return amps


# ============================================================================
# SYSTEM 3 + 4: COMPANIONS AND THEIR WEAPONS
# ============================================================================

TYPE_DIR = {"Sentinel": "sentinels", "Kubrow": "kubrows", "Kavat": "kavats", "Vulpaphyla": "kavats",
            "Predasite": "predasites", "MOA": "moas", "Hound": "hounds"}
MOD_CLASSES = {  # which mod "Type" values each companion kind can equip
    "Sentinel": ["Companion", "Robotic", "Sentinel"],
    "MOA": ["Companion", "Robotic", "MOA"],
    "Hound": ["Companion", "Robotic", "Hound"],
    "Kubrow": ["Companion", "Beast", "Kubrow"],
    "Kavat": ["Companion", "Beast", "Kavat"],
    "Vulpaphyla": ["Companion", "Beast", "Vulpaphyla"],
    "Predasite": ["Companion", "Beast", "Predasite"],
}
# Abilities that change the owner's or squad's damage. Values are max rank, from the mod text.
COMPANION_DAMAGE_PRECEPTS = {
    "Cat's Eye": "Squad critical chance +60% for 10 s every 20 s (pipeline step 7).",
    "Charm": "40% chance every 27 s for a random buff; the damage-relevant one is guaranteed orange/red critical hits for a short time.",
    "Viral Quills": "Applies Viral status (40% status chance per quill, 6 quills): feeds the Viral health-damage bonus (step 10) and Condition Overload (step 11).",
    "Sharpened Claws": "Kavat attack that strips armor (text: 'sunders armor by 120%').",
    "Anabolic Pollination": "+100% Toxin damage for 15 s to allies in the cloud (step 4).",
    "Acidic Spittle": "Corrosive damage and status on a target: armor strip via Corrosive stacks.",
    "Ambush": "+240% weapon damage for 3 s when Ghost's cloak breaks (step 2).",
    "Fired Up": "Sentinel weapon gains 5% Heat per hit up to 100%.",
    "Vaporize": "600 damage every 10 s, scaled by the sentinel weapon's mods.",
    "Detect Vulnerability": "Reveals weak points on researched enemies (enables step 13 weak point hits).",
    "Cordon": "Groups enemies: no stat change, raises practical AoE DPS.",
    "Energy Generator": "Energy Orb after 10 assists: indirect.",
    "Shield Charger": "+60% Warframe max shields and regen for 10 s: survivability only.",
    "Null Audit": "Hound copies an Eximus aura and strips 50% of its Overguard.",
    "Infectious Bite": "+200% finisher damage attack that seeds exploding pustules.",
    "Hunt": "Kubrow charge dealing 120% damage; scales with claw mods.",
    "Savagery": "Sunika knockdown rush: opens enemies to finishers.",
    "Unleashed": "+300% damage against Overguard for the Sunika.",
    "Ferocity": "Sahasa finisher with +300% crit chance.",
    "Draining Bite": "Vasca applies 5 Slash stacks at 150% of its melee damage: counts for Condition Overload.",
    "Trample": "Helminth Charger gains +10% melee damage, health and armor per enemy hit.",
    "Strain Fever": "Helminth Charger +40% damage per Cyst.",
    "Coolant Leak": "Adds 3 Cold stacks in 10 m: counts for Condition Overload / Galvanized status stacks.",
    "Arc Coil": "100 Electricity damage to 7 enemies, 10% status chance.",
}


def weapon_entry(name, w):
    attacks = []
    for a in w.get("Attacks", []):
        attacks.append({k: v for k, v in {
            "name": a.get("AttackName"), "damage": a.get("Damage"),
            "total_damage": round(sum((a.get("Damage") or {}).values()), 4),
            "crit_chance": a.get("CritChance"), "crit_multiplier": a.get("CritMultiplier"),
            "status_chance": a.get("StatusChance"), "fire_rate": a.get("FireRate"),
            "multishot": a.get("Multishot"), "shot_type": a.get("ShotType"),
            "range": a.get("Range"), "falloff": a.get("Falloff"), "punch_through": a.get("PunchThrough"),
            "charge_time": a.get("ChargeTime"), "burst_count": a.get("BurstCount"),
        }.items() if v is not None})
    return {
        "name": name, "weapon_class": w.get("Class"), "slot": w.get("Slot"), "trigger": w.get("Trigger"),
        "magazine": w.get("Magazine"), "reload": w.get("Reload"), "disposition": w.get("Disposition"),
        "polarities": w.get("Polarities"), "compatibility_tags": w.get("CompatibilityTags"),
        "attacks": attacks, "internal_name": w.get("InternalName"),
    }


def build_companions(mods_data):
    comp = module("Module:Companions/data")["Companions"]
    cweapons = module("Module:Weapons/data/companion")
    all_mods = mods_data["Mods"]
    processed = json.loads((ROOT / "backend" / "data" / "processed" / "weapons.json").read_text(encoding="utf-8"))

    precepts = {}
    for name, mod in all_mods.items():
        precepts.setdefault(mod.get("Type"), []).append(name)

    # which robotic weapon ships with which sentinel (from the item descriptions / internal names)
    default_weapon = {
        "Carrier": "Sweeper", "Carrier Prime": "Sweeper Prime", "Dethcube": "Deth Machine Rifle",
        "Dethcube Prime": "Deth Machine Rifle Prime", "Diriga": "Vulklok", "Djinn": "Stinger",
        "Helios": "Deconstructor", "Helios Prime": "Deconstructor Prime", "Nautilus": "Verglas",
        "Nautilus Prime": "Verglas Prime", "Oxylus": "Multron", "Shade": "Burst Laser",
        "Prisma Shade": "Prisma Burst Laser", "Shade Prime": "Burst Laser Prime", "Taxon": "Artax",
        "Wyrm": "Laser Rifle", "Wyrm Prime": "Prime Laser Rifle",
        "Bhaira Hound": "Lacerten", "Dorma Hound": "Batoten", "Hec Hound": "Akaten",
    }
    index = []
    for name, c in sorted(comp.items()):
        kind = c.get("Type")
        base = name.replace(" Prime", "").replace("Prisma ", "")
        own_precepts = sorted(set(precepts.get(name, []) + precepts.get(base, [])))
        claws = [a for a in c.get("Attacks", [])]
        entry = {
            "name": name, "type": kind, "variant": "prime" if "Prime" in name else "prisma" if "Prisma" in name else "base",
            "wiki_url": WIKI + urllib.parse.quote(name.replace(" ", "_")),
            "description": clean(c.get("Description")),
            "base_stats": {"health": c.get("Health"), "shield": c.get("Shield"), "armor": c.get("Armor"), "energy": c.get("Energy")},
            "polarities": c.get("Polarities"),
            "mod_classes": MOD_CLASSES.get(kind, []) + ([base] if own_precepts else []),
            "precepts": [],
            "internal_name": c.get("InternalName"), "introduced": c.get("Introduced"),
        }
        for p in own_precepts:
            mod = all_mods[p]
            entry["precepts"].append({
                "name": p, "max_rank": mod.get("MaxRank"), "effect_at_max_rank": clean(mod.get("Description")),
                "damage_relevant": p in COMPANION_DAMAGE_PRECEPTS,
                **({"damage_effect": COMPANION_DAMAGE_PRECEPTS[p]} if p in COMPANION_DAMAGE_PRECEPTS else {}),
            })
        if claws:
            entry["innate_attacks"] = [{
                "name": a.get("AttackName"), "damage": a.get("Damage"), "total_damage": a.get("TotalDamage"),
                "crit_chance": a.get("CritChance"), "crit_multiplier": a.get("CritMultiplier"),
                "status_chance": a.get("StatusChance"),
            } for a in claws]
        if name in default_weapon:
            entry["default_weapon"] = default_weapon[name]
        if kind == "Sentinel":
            entry["attacks_only_with"] = "an attack precept (Assault Mode or the sentinel's own, e.g. Striker, Swift Deth, Warrior)"
        if name.startswith("Venari"):
            entry["_notes"] = ["Khora's exalted companion, not an equippable companion; modded through Khora's ability menu."]
        folder = TYPE_DIR.get(kind, "other")
        write(f"companions/{folder}/{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}.json", entry)
        index.append({"name": name, "type": kind, "file": f"{folder}/{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}.json"})

    # MOA parts
    moa_text = fetch("MOA (Companion)")
    moa_sections = sections(moa_text)
    moa = {"source": "wiki.warframe.com MOA (Companion)",
           "base_stats": {"health": 350, "shield": 350, "armor": 350},
           "rules": ["Core and Gyro percentages are applied to the 350 base; the three stats always sum to 1190.",
                     "The Model picks the two bundled precepts; any MOA may equip any two MOA-specific precepts.",
                     "Bracket is the fourth part; see 'brackets' for what the page lists.",
                     "MOAs use Robotic weapons (not Hound weapons or the Deconstructor) and attack without Assault Mode.",
                     "Gallery bonuses on the wiki are for an ungilded MOA; the tables give the gilded (doubled) values."],
           "models": [], "cores": [], "gyros": [], "brackets": []}
    for key, heading in (("models", "Model"), ("cores", "Core"), ("gyros", "Gyro"), ("brackets", "Bracket")):
        body = moa_sections.get(heading, "")
        table = {re.sub(r"\s+(Model|Core|Gyro|Bracket)$", "", r.get(heading, list(r.values())[0])): r for r in wikitable(body)}
        for name, lines in gallery_items(body):
            item = {"name": name, "text": lines}
            for line in lines:
                for stat in ("Health", "Shields", "Armor"):
                    if stat in line and pct(line) is not None:
                        item.setdefault("ungilded_bonus", {})[stat.lower().rstrip("s")] = pct(line)
            if key == "models":
                item["precepts"] = re.findall(r"\{\{M\|([^}|]+)", next((b for b in body.split("\n") if name in b), ""))
            row = table.get(name)
            if row:
                item["gilded_table_row"] = row
            moa[key].append(item)
    write("companions/moas/moa_components.json", moa)

    hound_text = fetch("Hound (Companion)")
    hs = sections(hound_text)
    hound = {"source": "wiki.warframe.com Hound (Companion)",
             "rules": ["A Hound is Model + Core + Bracket + Stabilizer. The Model fixes the weapon and one precept; "
                       "Bracket and Stabilizer each add one precept; the Core sets base stats.",
                       "Hound weapons (Akaten, Batoten, Lacerten) are melee Robotic weapons usable only by Hounds."],
             "gilded_stats_text": clean(hs.get("Gilded Stats", ""))}
    for key, heading in (("models", "Model"), ("cores", "Core"), ("brackets", "Bracket"), ("stabilizers", "Stabilizer")):
        body = hs.get(heading, "")
        hound[key] = [{"name": n, "text": lines,
                       "precepts": [p for p in all_mods if any(p in line for line in lines) and all_mods[p].get("Type") == "Hound"]}
                      for n, lines in gallery_items(body)]
        if not hound[key]:
            hound[key] = [{"text": clean(body)[:1500]}]
    write("companions/hounds/hound_components.json", hound)

    write("companions/companion_base_scaling.json", {
        "source": "wiki.warframe.com Module:Companions/data, Sentinel (stat comparison), MOA (Companion); Link mod text",
        "rank_scaling": "The current game data lists one set of stats per companion and the wiki's 'max' tables are exactly "
                        "base x 3.5, i.e. base with the +250% Enhanced Vitality / Calculated Redirection / Metal Fiber mods. "
                        "No per-rank stat growth is documented, so treat base stats as rank-independent. UNVERIFIED in game.",
        "mods": {
            "Enhanced Vitality": "+250% health at rank 10 (increment 22.7273% per rank + 1)",
            "Calculated Redirection": "+250% shields at rank 10",
            "Metal Fiber": "+250% armor at rank 10",
            "Link Vitality": "+125% of the Warframe's max health at rank 10",
            "Link Redirection": "+125% of the Warframe's max shields at rank 10",
            "Link Fiber": "+125% of the Warframe's armor at rank 10",
            "exclusivity": "The flat-% mod and the Link mod for the same stat cannot be equipped together. Sentinels cannot use Link mods.",
        },
        "formulas": {
            "health": "Base x (1 + Enhanced Vitality)   or   Base + Link Vitality x Warframe max health",
            "shield": "Base x (1 + Calculated Redirection)   or   Base + Link Redirection x Warframe max shields",
            "armor": "Base x (1 + Metal Fiber)   or   Base + Link Fiber x Warframe armor",
            "effective_health": "Health x (Armor + 300) / 300",
        },
        "incapacitation": "Companions do not die: they are downed and return after a recovery timer (reduced by Regen, Medi-Pet Kit, bond mods).",
        "enemy_level_scaling": "Companions do not scale with enemy level.",
        "companions": [{"name": n, "type": c.get("Type"), "health": c.get("Health"), "shield": c.get("Shield"),
                        "armor": c.get("Armor")} for n, c in sorted(comp.items())],
        "index": index,
    })

    # companion weapons
    in_app = {v.get("uniqueName"): k for k, v in processed.items()}
    owner = {w: s for s, w in default_weapon.items()}
    weapons = []
    for name, w in sorted(cweapons.items()):
        e = weapon_entry(name, w)
        e["in_weapons_json_as"] = in_app.get(w.get("InternalName"))
        e["comes_with"] = owner.get(name) or next((c for c in comp if name.startswith(c.split()[0]) and "Claws" in name), None)
        e["usable_by"] = ("Hounds only" if name in ("Akaten", "Batoten", "Lacerten")
                          else "Helios / Helios Prime only" if name.startswith("Deconstructor")
                          else "innate to its beast; modded with Claws mods" if "Claws" in name
                          else "Sentinels and MOAs")
        weapons.append(e)
    write("companions/companion_weapons.json", {
        "source": "wiki.warframe.com Module:Weapons/data/companion; backend/data/processed/weapons.json for the app cross-reference",
        "pipeline": {
            "same_as_weapons": "Yes. Robotic weapons are ordinary weapons with a class (Rifle, Shotgun, Pistol, Sniper, Melee) and take "
                               "that class's normal mods: base damage, multishot, crit, status, elemental, fire rate, magazine, reload, faction.",
            "shared_mods": "The same mod copy can sit on the player's weapon and the companion's weapon at once.",
            "set_mods": "Set mods on a companion weapon count toward the player's set bonus.",
            "not_available": "No Exilus slot, no arcanes; ammo-maximum mods do nothing (unlimited reserves).",
            "quantization": "Nothing in the sources suggests companion weapons skip quantization; treat as identical (unverified in game).",
            "beast_claws": "Beast attacks use the claws entry (innate_attacks) and Claws mods (Bite, Maul, elemental claws) through the same math.",
        },
        "weapon_class_map": {"Rifle": "PRIMARY mods", "Sniper": "PRIMARY mods", "Shotgun": "SHOTGUN mods",
                             "Pistol": "SECONDARY mods", "Melee": "MELEE mods", "Glaive": "MELEE (thrown) mods",
                             "Claws (Beast)": "Claws (companion) mods"},
        "weapons": weapons,
        "missing_from_app": [e["name"] for e in weapons if not e["in_weapons_json_as"]],
    })
    return comp


# ============================================================================
# SYSTEM 5: COMPANION MODS
# ============================================================================

STAT_PATTERNS = [  # text fragment -> engine stat key, for linear per-rank mods
    (r"Critical Chance", "CRIT_CHANCE"), (r"Critical Damage", "CRIT_DAMAGE"), (r"Melee Damage", "DAMAGE"),
    (r"Status Chance", "STATUS_CHANCE"), (r"Status Duration", "STATUS_DURATION"), (r"Status Damage", "STATUS_DAMAGE"),
    (r"Heat", "HEAT"), (r"Cold", "COLD"), (r"Electricity", "ELECTRICITY"), (r"Toxin", "TOXIN"),
    (r"Radiation", "RADIATION"), (r"Magnetic", "MAGNETIC"), (r"Impact Damage", "IMPACT"),
    (r"Health", "HEALTH"), (r"Shield Capacity", "SHIELD"), (r"Armor", "ARMOR"),
]
COMPANION_MOD_TYPES = {"Companion", "Beast", "Robotic", "Sentinel", "MOA", "Hound", "Claws", "Kavat", "Kubrow",
                       "Predasite", "Vulpaphyla", "Kavat Claws", "Kubrow Claws", "Helminth Claws"}


def mod_record(name, mod, wfcd_by_name, companions):
    levels = (wfcd_by_name.get(name) or {}).get("levelStats") or []
    texts = [clean("; ".join(level["stats"])) for level in levels]
    max_rank = mod.get("MaxRank")
    record = {
        "name": name, "class": mod.get("Type"), "max_rank": max_rank, "polarity": mod.get("Polarity"),
        "rarity": mod.get("Rarity"), "base_drain": mod.get("BaseDrain"), "set": mod.get("Set"),
        "effect_at_max_rank": clean(mod.get("Description")),
        "per_rank_text": texts,
    }
    stats = []
    lines_by_rank = [[clean(s) for s in level["stats"]] for level in levels]
    if lines_by_rank and len({len(l) for l in lines_by_rank}) == 1:
        for i in range(len(lines_by_rank[0])):
            column = [l[i] for l in lines_by_rank]
            numbers = [NUMBER.search(c) for c in column]
            if not all(numbers):
                continue
            values = [float(n.group(0).replace(",", "")) for n in numbers]
            is_pct = "%" in column[-1]
            key = next((k for pattern, k in STAT_PATTERNS if re.search(pattern, column[-1])), None)
            # the game rounds displayed values, so allow each rank to be off by one unit
            step = values[-1] / len(values)
            linear = all(abs(values[r] - step * (r + 1)) <= 1.0 for r in range(len(values)))
            stat = {"text_at_max_rank": column[-1], "per_rank": [int(v) if v == int(v) else v for v in values]}
            varying = rank_values(column)
            if len(varying) > 1:
                stat["all_per_rank_values"] = varying  # every number in the line that changes with rank
            # only plain "+X% Stat Name" lines map onto an engine stat
            if key and re.match(r"^[+-][\d.,]+%? (" + "|".join(p for p, _ in STAT_PATTERNS) + ")$", column[-1]):
                stat["stat"] = key
            if linear and len(values) > 1:
                stat["increment"] = round(values[-1] / len(values) / (100 if is_pct else 1), 6)
                stat["maxRank"] = len(values) - 1
            stats.append(stat)
    record["stats"] = stats
    if mod.get("Type") in companions or any(mod.get("Type") == c.split()[0] for c in companions):
        record["precept_of"] = mod.get("Type")
    return {k: v for k, v in record.items() if v not in (None, [], "")}


def build_companion_mods(mods_data, companions):
    all_mods = mods_data["Mods"]
    wfcd_mods = {m["name"]: m for m in wfcd("Mods") if m.get("levelStats")}
    base_names = {c.replace(" Prime", "").replace("Prisma ", "") for c in companions}
    records = {}
    for name, mod in all_mods.items():
        ty = mod.get("Type")
        if ty in COMPANION_MOD_TYPES or ty in base_names:
            records[name] = mod_record(name, mod, wfcd_mods, base_names)

    def pick(pred):
        return [r for _, r in sorted(records.items()) if pred(r)]

    precept_classes = base_names | {"MOA", "Hound", "Kavat", "Predasite", "Vulpaphyla", "Sentinel", "Robotic", "Beast"}
    damage_words = re.compile(r"Damage|Critical|Status|Heat|Cold|Toxin|Electricity|Radiation|Magnetic|armor", re.I)
    by_owner = {}
    for r in pick(lambda r: r["class"] in base_names):
        by_owner.setdefault(r["class"], []).append(r)
    write("companion_mods/precept_mods.json", {
        "source": "wiki.warframe.com Module:Mods/data + WFCD Mods.json (per-rank text)",
        "priority_rule": "Precepts are tried in slot order: top-left is highest priority, bottom-right lowest. A companion keeps using "
                         "the highest-priority precept whose conditions are met and interrupts lower ones for it.",
        "per_companion": by_owner,
        "class_wide": pick(lambda r: r["class"] in ("MOA", "Hound", "Kavat", "Predasite", "Vulpaphyla", "Sentinel", "Robotic", "Beast")
                           and not r.get("stats", [{}])[0].get("stat")),
        "damage_relevant": COMPANION_DAMAGE_PRECEPTS,
    })
    link_names = ("Link Vitality", "Link Redirection", "Link Fiber", "Enhanced Vitality", "Calculated Redirection", "Metal Fiber")
    write("companion_mods/link_mods.json", {
        "source": "wiki.warframe.com Module:Mods/data + WFCD Mods.json",
        "note": "In-game names are Link Vitality / Link Redirection / Link Fiber (health / shield / armor). "
                "Each shares that fraction of the Warframe's stat; value = increment x (rank + 1).",
        "mods": [records[n] for n in link_names if n in records],
    })
    write("companion_mods/beast_damage_mods.json", {
        "source": "wiki.warframe.com Module:Mods/data + WFCD Mods.json",
        "note": "Claws mods go on a beast's innate claws weapon. 'increment' follows core_mods.json: value = increment x (rank + 1). "
                "Stance-like posture mods change behaviour and add one bonus each.",
        "mods": pick(lambda r: r["class"] in ("Claws", "Kavat Claws", "Kubrow Claws", "Helminth Claws")),
    })
    write("companion_mods/robotic_damage_mods.json", {
        "source": "wiki.warframe.com Sentinel / MOA (Companion) pages; Module:Mods/data",
        "answer": "Robotic weapons do NOT have their own damage mod pool. They use the player's ordinary Rifle / Shotgun / Pistol / "
                  "Melee mods by weapon class, so every damage mod already in backend/data/processed/core_mods.json applies.",
        "weapon_class_to_core_mod_type": {"Rifle": "PRIMARY", "Sniper": "PRIMARY", "Shotgun": "SHOTGUN", "Pistol": "SECONDARY", "Melee": "MELEE"},
        "robotic_only_mods_touching_damage": pick(lambda r: r["class"] in ("Robotic", "Sentinel") and damage_words.search(r["effect_at_max_rank"])),
    })

    sets = {}
    wanted = ("Mecha Set", "Tek Set", "Hunter Set", "Synth Set", "Strain Set", "Gladiator Set", "Vigilante Set", "Augur Set")
    for set_name in wanted:
        info = mods_data["Sets"].get(set_name, {})
        page = sections(fetch(set_name))
        members = sorted(n for n, m in all_mods.items() if m.get("Set") == set_name)
        sets[set_name] = {
            "pieces": info.get("NumUpgradesInSet"),
            "bonus_with_one_piece": clean(info.get("Description")),
            "bonus_per_pieces_equipped": wikitable(page.get("Set Bonus", "")),
            "members": [{"name": n, "class": all_mods[n].get("Type"),
                         "effect_at_max_rank": clean(all_mods[n].get("Description"))} for n in members],
            "wiki_notes": bullets(page.get("Notes", ""))[:10],
        }
    damage_note = {
        "Mecha Set": "Companion marks a target; killing it spreads its status effects. Mecha Empowered (aura): squad deals +150% damage to the marked enemy.",
        "Tek Set": "Kavat marks a zone that deals damage per second; no change to weapon damage.",
        "Hunter Set": "+25% companion damage per piece against enemies with a Slash status. Hunter Munitions (weapon) gives Slash procs on crits.",
        "Gladiator Set": "+10% critical chance per combo multiplier per piece (Blood Rush-style, step 7) for the Warframe's melee. Pieces can sit on the companion.",
        "Vigilante Set": "5% chance per piece to raise a primary weapon critical hit by one tier (step 14).",
        "Synth Set": "Reloads holstered weapons; sustained DPS only.",
        "Strain Set": "Helminth Charger cysts and maggots; Strain Fever gives the Charger +40% damage per cyst.",
        "Augur Set": "Energy spent converts to shields; no damage effect.",
    }
    for k, v in damage_note.items():
        sets[k]["damage_effect"] = v
    write("companion_mods/set_mods.json", {
        "source": "wiki.warframe.com Module:Mods/data (Sets, members) + set pages (per-piece tables)",
        "rule": "Set bonuses count every equipped piece across Warframe, weapons, companion and companion weapon.",
        "sets": sets,
    })
    write("companion_mods/companion_mod_list.json", {
        "source": "wiki.warframe.com Module:Mods/data + WFCD Mods.json",
        "count": len(records),
        "classes": {c: sorted(n for n, r in records.items() if r["class"] == c) for c in sorted({r["class"] for r in records.values()})},
        "mods": [r for _, r in sorted(records.items())],
    })
    return records


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    print("Operator / Focus"); build_focus(); build_operator_stats()
    print("Amps"); build_amps()
    mods_data = mods_module()
    print("Companions"); companions = build_companions(mods_data)
    print("Companion mods"); build_companion_mods(mods_data, companions)


if __name__ == "__main__":
    main()
