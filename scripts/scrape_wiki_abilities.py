#!/usr/bin/env python3
"""Scrape Warframe ability mechanics from the wiki into data/raw/wiki_abilities/.

One JSON file per frame in backend/data/processed/warframes.json (archwings
skipped). Prime/Umbra variants get their own file: abilities are scraped from
the same ability pages (the game shares ability objects between a frame and
its Prime) and the variant's own stats come from the game export.

Source: wiki.warframe.com raw wikitext (`?action=raw`), which is structured:
  - Module:Ability/data   -> owner, slot, energy cost, augments, subsumable
  - Module:Warframes/data -> passive text
  - <Ability> page        -> the {{Ability...}} template: strength/duration/range/misc/info
  - <Augment> page        -> per-rank stats table

wiki.warframe.com is the maintained wiki (warframe.fandom.com stopped updating
around the start of 2025 and was the source of the first version of this data).
An ability with no template on the wiki falls back to the hand-collected entry
in data/raw/wiki_manual_abilities.json and is marked with a "_notes" field.

Usage: python scripts/scrape_wiki_abilities.py [--refresh] [Frame Name ...]
"""

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WARFRAMES = ROOT / "backend" / "data" / "processed" / "warframes.json"
OUT_DIR = ROOT / "data" / "raw" / "wiki_abilities"
CACHE_DIR = ROOT / "data" / "raw" / "wiki_cache_current"
WIKI = "https://wiki.warframe.com/w/"
UA = "warframe-calc-data/1.0 (personal damage calculator; one-off data pull)"

# Resolve through PATH: on Windows a bare "curl" would pick System32's build,
# which the wiki refuses; the Git for Windows build is accepted.
CURL = shutil.which("curl") or "curl"

NECRAMECHS = {"Bonewidow", "Voidrig"}
STAT_FIELDS = {
    "strength": "Ability Strength",
    "duration": "Ability Duration",
    "range": "Ability Range",
}

REFRESH = False

MANUAL_FILE = ROOT / "data" / "raw" / "wiki_manual_abilities.json"
WFCD_WARFRAMES = ROOT / "data" / "raw" / "wfcd_warframes.json"
WFCD_WARFRAMES_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/Warframes.json"
NEWER_THAN_WIKI = set()  # frames the wiki has no ability templates for; none at present

MANUAL = {}
WFCD_PASSIVES = {}
WFCD_FRAMES = {}  # export-shaped entries, for frames newer than warframes.json


def load_fallbacks():
    if MANUAL_FILE.exists():
        MANUAL.update(json.loads(MANUAL_FILE.read_text(encoding="utf-8")))
    if not WFCD_WARFRAMES.exists():
        subprocess.run([CURL, "-sL", "-o", str(WFCD_WARFRAMES), WFCD_WARFRAMES_URL], check=True, timeout=120)
    for frame in json.loads(WFCD_WARFRAMES.read_text(encoding="utf-8")):
        if frame.get("passiveDescription"):
            WFCD_PASSIVES[frame["name"]] = frame["passiveDescription"]
        if frame.get("productCategory") == "Suits":
            WFCD_FRAMES[frame["name"]] = {
                "health": frame.get("health"), "shield": frame.get("shield"), "armor": frame.get("armor"),
                "energy": frame.get("power"), "sprintSpeed": frame.get("sprintSpeed"),
                "abilities": [{"name": a["name"], "description": a.get("description", "")} for a in frame.get("abilities", [])],
            }


# ============================================================================
# FETCHING
# ============================================================================

def fetch_raw(title: str):
    """Raw wikitext of a page (following redirects), or None if it doesn't exist."""
    for _ in range(4):
        # "/" maps to "~" so "Ash Prime" and its redirect target "Ash/Prime" don't collide.
        cache = CACHE_DIR / (re.sub(r"[^A-Za-z0-9_.~-]", "_", title.replace("/", "~")) + ".wiki")
        if cache.exists() and not REFRESH:
            text = cache.read_text(encoding="utf-8")
        else:
            url = WIKI + urllib.parse.quote(title.replace(" ", "_"), safe="/:") + "?action=raw"
            # The wiki rejects Python's HTTP client outright, so go through curl.
            for attempt in range(5):
                try:
                    result = subprocess.run(
                        [CURL, "-sL", "-A", UA, "-w", "\n%{http_code}", url],
                        capture_output=True, timeout=60,
                    )
                except subprocess.TimeoutExpired:
                    code = "timeout"
                    time.sleep(10)
                    continue
                body, _, code = result.stdout.decode("utf-8", errors="replace").rpartition("\n")
                if code in ("200", "404"):
                    break
                # 403/429 here means we are going too fast: wait and try again.
                time.sleep(30 * (attempt + 1))
            else:
                raise RuntimeError(f"HTTP {code} for {url}")
            text = body if code == "200" else ""
            cache.write_text(text, encoding="utf-8", newline="\n")
            time.sleep(1.5)  # be polite
        redirect = re.match(r"\s*#REDIRECT\s*\[\[([^\]#|]+)", text, re.I)
        if not redirect:
            return text or None
        title = redirect.group(1).strip()
    return None


# ============================================================================
# LUA DATA MODULES (only the flat fields we need)
# ============================================================================

def lua_entries(text: str, indent: str):
    """Yield (name, body) for each `Name = {` / `["Name"] = {` table at the given indent."""
    pattern = re.compile(r"^%s(?:\[\"([^\"]+)\"\]|([\w-]+)) = \{\n(.*?)^%s\}" % (indent, indent), re.M | re.S)
    for m in pattern.finditer(text):
        yield m.group(1) or m.group(2), m.group(3)


def lua_field(body: str, key: str):
    m = re.search(r'^\s*%s = (.+?),?\s*$' % key, body, re.M)
    if not m:
        return None
    value = m.group(1).strip().rstrip(",")
    if value.startswith('"'):
        return json.loads(value)
    if value.startswith("{"):
        return re.findall(r'"((?:[^"\\]|\\.)*)"', value)
    if value in ("true", "false"):
        return value == "true"
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def load_ability_index():
    text = fetch_raw("Module:Ability/data") or ""
    index = {}
    for name, body in lua_entries(text, "\t\t"):
        if lua_field(body, "Powersuit") is None:
            continue
        index[name] = {
            "powersuit": lua_field(body, "Powersuit"),
            "slot": lua_field(body, "Key"),
            "cost": lua_field(body, "Cost"),
            "cost_type": lua_field(body, "CostType"),
            "augments": lua_field(body, "Augments") or [],
            "subsumable": bool(lua_field(body, "Subsumable")),
            "link": lua_field(body, "Link"),
            "internal": lua_field(body, "InternalName"),
        }
    return index


def load_passives():
    text = fetch_raw("Module:Warframes/data") or ""
    return {name: lua_field(body, "Passive") for name, body in lua_entries(text, "\t\t")}


# ============================================================================
# WIKITEXT
# ============================================================================

def strip_markup(text: str) -> str:
    """Wikitext -> plain text."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", text, flags=re.S)
    text = re.sub(r"\{\{(?:mul)\}\}", "×", text)
    text = re.sub(r"\{\{(?:eql)\}\}", "=", text)
    text = re.sub(r"\{\{Stat\|([^|}]+)\|icon=only\}\}", "", text)
    for _ in range(4):  # innermost templates first
        text = re.sub(r"\{\{(?:D|A|M|WF|Weapon|Stat|Icon|Companion|Faction|Enemy|Arcane|Resource|Pol|ver|sc|Math|MathText)\|([^{}|]*)(?:\|[^{}]*)?\}\}", r"\1", text)
        text = re.sub(r"\{\{[^{}|]*\|([^{}|]*)(?:\|[^{}]*)?\}\}", r"\1", text)
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:File|Category):[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)
    text = text.replace("&nbsp;", " ").replace(" ", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def template_fields(wikitext: str):
    """Fields of the page's {{Ability...}} template as {key: raw value}."""
    start = re.search(r"\{\{Ability[\w. ]*\s*\n?\s*\|", wikitext)
    if not start:
        return {}
    depth, i, end = 0, start.start(), len(wikitext)
    while i < len(wikitext) - 1:
        pair = wikitext[i:i + 2]
        if pair == "{{":
            depth += 1
            i += 2
        elif pair == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                end = i - 2
                break
        else:
            i += 1
    body = wikitext[start.end() - 1:end]
    fields = {}
    parts = re.split(r"\n\s*\|\s*([a-zA-Z_][\w ]*?)\s*=", "\n" + body)
    for key, value in zip(parts[1::2], parts[2::2]):
        fields[key.strip().lower()] = value.strip()
    return fields


def slug(label: str) -> str:
    label = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return label[:60] or "value"


NUMBER = r"-?\d[\d,]*\.?\d*"


def parse_value_line(line: str, default_key: str):
    """'100 / 250 / 350 / 500 (Slash damage on hit)' -> (key, value dict)."""
    plain = strip_markup(line)
    if not plain.strip("{}| "):  # stray template punctuation
        return None
    label_match = re.search(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$", plain)
    label = label_match.group(1).strip() if label_match else ""
    head = plain[:label_match.start()].strip() if label_match else plain
    numbers = [float(n.replace(",", "")) for n in re.findall(NUMBER, head)]
    numbers = [int(n) if n == int(n) else n for n in numbers]
    unit_match = re.search(r"(?:%s)\s*(%%(?:/\w+)?|m/s|m|s|x|°)(?:\s|$|/)" % NUMBER, head + " ")
    value = {"text": plain}
    ranked = "/" in head and len(numbers) >= 2
    if numbers:
        value["base"] = numbers[-1] if ranked else numbers[0]
        if ranked:
            value["per_rank"] = numbers
    if unit_match:
        value["unit"] = unit_match.group(1)
    if label:
        value["label"] = label
    return slug(label) if label else default_key, value


def parse_values(fields: dict):
    values = {}
    damage_types = []
    for field in ("strength", "duration", "range", "misc"):
        raw = fields.get(field, "")
        if not raw:
            continue
        damage_types += re.findall(r"\{\{D\|([^}|]+)", raw)
        for n, line in enumerate(re.split(r"<br\s*/?>|\n", raw, flags=re.I)):
            parsed = parse_value_line(line, field if n == 0 else f"{field}_{n + 1}")
            if not parsed:
                continue
            key, value = parsed
            value["scales_with"] = STAT_FIELDS.get(field)
            if value["scales_with"] is None:
                del value["scales_with"]
            while key in values:
                key += "_"
            values[key] = value
    if damage_types:
        values["damage_type"] = list(dict.fromkeys(damage_types))
    return values


def bullets(raw: str):
    """Top-level bullets of a wikitext list, each with its sub-bullets folded in."""
    items, current = [], None
    for line in raw.split("\n"):
        m = re.match(r"^(\*+|:+\**)\s*(.*)$", line.strip())
        if not m:
            continue
        text = strip_markup(m.group(2))
        if not text:
            continue
        if m.group(1) == "*":
            current = text
            items.append(current)
        elif current is not None:
            items[-1] = items[-1] + " " + text
    return items


WEAPON_WORDS = re.compile(r"\b(weapons?|melee|primary|secondary|rifle|shotgun|pistol|gun|exalted|mod(?:s|ded)?\b|critical|status chance|multishot|fire rate|headshot)", re.I)

# Heuristic tags for abilities that touch the weapon damage pipeline.
DAMAGE_TAGS = [
    ("armor_strip", r"(armor[^.]{0,60}(reduc|remov|strip)|(reduc|remov|strip)[^.]{0,40}armor|defense reduction)"),
    ("shield_strip", r"((reduc|remov|strip)[^.]{0,40}shields?)"),
    ("damage_buff", r"(increas|bonus|buff|multipl|additional)[^.]{0,50}(weapon |base |all |final |faction |elemental )?damage|damage (bonus|buff|multiplier)"),
    ("damage_vulnerability", r"(damage vulnerab|takes? [^.]{0,30}(more|increased|additional) damage|amplif)"),
    ("crit_buff", r"critical (chance|damage|multiplier)"),
    ("status_buff", r"status chance"),
    ("fire_rate_buff", r"(fire rate|attack speed|reload speed)"),
    ("multishot_buff", r"multishot"),
    ("elemental_damage", r"(adds?|grants?|convert|imbue|additional)[^.]{0,60}\b(heat|cold|electricity|toxin|viral|corrosive|radiation|blast|gas|magnetic|void)\b"),
    ("applies_status", r"(status effect|proc)\b"),
    ("exalted_weapon", r"exalted"),
    ("invisibility_or_stealth", r"(invisib|stealth)"),
]


def damage_tags(text: str):
    return [tag for tag, pattern in DAMAGE_TAGS if re.search(pattern, text, re.I)]


def parse_augment(name: str):
    raw = fetch_raw(name)
    if not raw:
        return {"name": name, "_notes": ["augment page not found on wiki"]}
    intro = re.search(r"<section begin=intro\s*/>(.*?)<section end=intro\s*/>", raw, re.S)
    augment = {"name": name, "description": strip_markup(intro.group(1)) if intro else ""}

    table = re.search(r"==\s*Stats\s*==\s*(\{\|.*?\|\})", raw, re.S)
    values = {}
    if table:
        rows = [r.strip() for r in re.split(r"\n\|-", table.group(1))]
        headers = []
        data = []
        for row in rows:
            if row.startswith("!") or "\n!" in row:
                headers = [strip_markup(h) for h in re.split(r"\n!|!!", "\n" + row) if h.strip() and not h.strip().startswith("{|")]
            elif row.startswith("|") and "||" in row:
                data.append([strip_markup(c) for c in row.lstrip("|").split("||")])
        for col, header in enumerate(headers):
            if header.lower() in ("rank", "cost", "conclave") or not data:
                continue
            cells = [r[col] for r in data if col < len(r)]
            nums = [re.search(NUMBER, c) for c in cells]
            entry = {"text_per_rank": cells}
            if nums and all(nums):
                per_rank = [float(n.group(0).replace(",", "")) for n in nums]
                entry["per_rank"] = [int(n) if n == int(n) else n for n in per_rank]
                unit = re.search(r"%s\s*(%%|m|s|x)" % NUMBER, cells[-1])
                if unit:
                    entry["unit"] = unit.group(1)
            values[slug(header)] = entry
    augment["values"] = values
    if values:
        augment["effect"] = ", ".join(
            f"{k.replace('_', ' ')} {v['text_per_rank'][-1]}" for k, v in values.items())
    notes = re.search(r"==\s*Notes\s*==\s*(.*?)(?:\n==[^=]|\Z)", raw, re.S)
    if notes:
        augment["notes"] = bullets(notes.group(1))[:12]
    return augment


def parse_ability(name: str, slot: int, export: dict, index: dict):
    meta = index.get(name, {})
    ability = {
        "name": name,
        "slot": slot,
        "energy_cost": export.get("energyCost"),
        "description": export.get("description", ""),
        "values": {},
        "augments": [],
        "scaling": {"affected_by": [], "damage_scales_with": None, "notes": []},
        "special_mechanics": [],
        "weapon_interactions": [],
        "damage_system_tags": [],
        "subsumable": meta.get("subsumable", False),
    }
    if export.get("energyDrain"):
        ability["energy_drain"] = export["energyDrain"]
    if meta.get("cost_type"):
        ability["cost_type"] = meta["cost_type"]

    title = meta.get("link") or name
    raw = fetch_raw(title)
    fields = template_fields(raw) if raw else {}
    if not fields and raw is not None:
        # Name shared with another article ("Roar (Ability)" style pages).
        alt = fetch_raw(f"{name} (Ability)")
        fields = template_fields(alt) if alt else {}
        if fields:
            title = f"{name} (Ability)"
    manual = None
    if not fields:
        manual = MANUAL.get(name)
        if not manual:
            ability["_notes"] = ["incomplete - no ability page with an ability template on wiki.warframe.com"]
            return ability
        # Hand-collected from the current wiki; reuse the same field parser.
        fields = {k: "<br>".join(manual.get(k, [])) for k in ("strength", "duration", "range", "misc")}
        fields["energy"] = str(manual.get("energy", ""))
        fields["info"] = "\n".join(f"*{line}" for line in manual.get("info", []))
        ability["subsumable"] = manual.get("subsumable")
        if ability["energy_cost"] is None:
            ability["energy_cost"] = manual.get("energy")
        ability["_notes"] = [
            "transcribed from wiki.warframe.com by a summarising fetch, not parsed from wikitext - verify numbers",
            "info limited to five bullets; subsumable is null where the page did not say",
        ]
        ability["augments"] = [dict(a) for a in manual.get("augments", [])]

    if manual:
        ability["wiki_url"] = "https://wiki.warframe.com/w/" + urllib.parse.quote(name.replace(" ", "_"))
    else:
        ability["wiki_url"] = WIKI + urllib.parse.quote(title.replace(" ", "_"))
    wiki_energy = re.search(NUMBER, strip_markup(fields.get("energy", "") or fields.get("cost", "")))
    if wiki_energy:
        ability["wiki_energy_cost"] = float(wiki_energy.group(0)) if "." in wiki_energy.group(0) else int(wiki_energy.group(0))
    ability["values"] = parse_values(fields)

    info = fields.get("info", "")
    affected = [stat for field, stat in STAT_FIELDS.items() if fields.get(field)]
    for stat in ("Ability Strength", "Ability Duration", "Ability Range", "Ability Efficiency"):
        if stat not in affected and re.search(r"\{\{Stat\|%s" % stat, info):
            affected.append(stat)
    if manual and "Ability Efficiency" not in affected and ability["energy_cost"]:
        affected.append("Ability Efficiency")
    ability["scaling"]["affected_by"] = affected
    strength = fields.get("strength", "")
    if re.search(r"damage|\{\{D\|", strength, re.I):
        ability["scaling"]["damage_scales_with"] = "Ability Strength"

    mechanics = bullets(info)
    ability["special_mechanics"] = mechanics
    ability["scaling"]["notes"] = [
        m for m in mechanics
        if re.search(r"(not affected|unaffected|is affected|are affected|affected by|scales? with|capped|cap of)", m, re.I)
    ]
    ability["weapon_interactions"] = [m for m in mechanics if WEAPON_WORDS.search(m)]
    ability["damage_system_tags"] = damage_tags(
        " ".join([ability["description"], strip_markup(strength), strip_markup(fields.get("misc", ""))] + mechanics[:6]))

    for augment in meta.get("augments", []):
        ability["augments"].append(parse_augment(augment))
    return ability


# ============================================================================
# FRAMES
# ============================================================================

def file_name(frame: str) -> str:
    name = frame.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_") + ".json"


def variant_of(frame: str):
    if frame in NECRAMECHS:
        return "necramech", frame
    if frame.endswith(" Prime"):
        return "prime", frame[:-len(" Prime")]
    if frame.endswith(" Umbra"):
        return "umbra", frame[:-len(" Umbra")]
    return "base", frame


def prime_notes(frame: str, base: str):
    """The wiki's own 'compared to the base frame' bullets from the variant page."""
    raw = fetch_raw(frame) or fetch_raw(f"{base}/Prime")
    if not raw:
        return []
    section = re.search(r"==\s*Notes\s*==\s*(.*?)(?:\n==[^=]|\Z)", raw, re.S)
    return bullets(section.group(1)) if section else []


def build_frame(frame: str, export: dict, all_export: dict, index: dict, passives: dict):
    variant, base = variant_of(frame)
    notes = []
    data = {
        "name": frame,
        "variant": variant,
        "wiki_url": WIKI + urllib.parse.quote(frame.replace(" ", "_")),
        "base_stats": {k: export.get(k) for k in ("health", "shield", "armor", "energy", "sprintSpeed")},
    }

    passive_text = passives.get(frame) or passives.get(base)
    manual_passive = MANUAL.get("_passives", {}).get(frame) or MANUAL.get("_passives", {}).get(base)
    if manual_passive and not passive_text:
        data["passive"] = {"description": manual_passive, "source": "wiki.warframe.com (transcribed)"}
    elif passive_text:
        data["passive"] = {"description": strip_markup(passive_text)}
    elif WFCD_PASSIVES.get(frame) or WFCD_PASSIVES.get(base):
        # Game export text; numbers are |PLACEHOLDER| tokens the game fills in at runtime.
        data["passive"] = {
            "description": strip_markup(re.sub(r"<DT_\w+>", "", WFCD_PASSIVES.get(frame) or WFCD_PASSIVES[base])),
            "source": "game export (WFCD warframe-items)",
        }
    else:
        data["passive"] = None
        if variant == "necramech":
            data["passive_note"] = "Necramechs have no passive ability."
        else:
            notes.append("incomplete - passive not found")
    if frame in NEWER_THAN_WIKI or base in NEWER_THAN_WIKI:
        data["wiki_url"] = "https://wiki.warframe.com/w/" + urllib.parse.quote(frame.replace(" ", "_"))
        notes.append("released after warframe.fandom.com stopped updating; abilities transcribed from wiki.warframe.com (see ability _notes)")

    abilities = []
    for i, ab in enumerate(export.get("abilities", [])):
        slot = index.get(ab["name"], {}).get("slot") or i + 1
        abilities.append(parse_ability(ab["name"], slot, ab, index))
    data["abilities"] = abilities
    missing = [a["name"] for a in abilities if not a["values"]]
    if missing:
        notes.append("incomplete - wiki page missing ability data for: " + ", ".join(missing))

    if variant in ("prime", "umbra") and base in all_export:
        base_export = all_export[base]
        stat_diff = {}
        for key in ("health", "shield", "armor", "energy", "sprintSpeed"):
            if export.get(key) != base_export.get(key):
                stat_diff[key] = {"base": base_export.get(key), variant: export.get(key)}
        base_abilities = {a["name"]: a for a in base_export.get("abilities", [])}
        ability_diff = []
        for ab in export.get("abilities", []):
            other = base_abilities.get(ab["name"])
            if other is None:
                ability_diff.append({"ability": ab["name"], "difference": f"not on {base}"})
            elif (ab.get("energyCost"), ab.get("energyDrain")) != (other.get("energyCost"), other.get("energyDrain")):
                ability_diff.append({
                    "ability": ab["name"],
                    "difference": "energy",
                    "base": {"energyCost": other.get("energyCost"), "energyDrain": other.get("energyDrain")},
                    variant: {"energyCost": ab.get("energyCost"), "energyDrain": ab.get("energyDrain")},
                })
        for name in base_abilities:
            if name not in {a["name"] for a in export.get("abilities", [])}:
                ability_diff.append({"ability": name, "difference": f"only on {base}"})
        data["differences_from_base"] = {
            "stats": stat_diff,
            "abilities": ability_diff,
            "wiki_notes": prime_notes(frame, base),
        }

    if notes:
        data["_notes"] = notes
    return data


def main():
    global REFRESH
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    REFRESH = "--refresh" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    with open(WARFRAMES, encoding="utf-8") as f:
        export = json.load(f)
    load_fallbacks()
    index = load_ability_index()
    passives = load_passives()
    print(f"ability index: {len(index)} abilities, {len(passives)} passives")

    # Frames released after warframes.json was exported: take stats from WFCD and,
    # for variants, energy costs from the base frame (the game shares ability objects).
    for name, entry in WFCD_FRAMES.items():
        if name in export:
            continue
        costs = {a["name"]: a for a in export.get(variant_of(name)[1], {}).get("abilities", [])}
        for ab in entry["abilities"]:
            for key in ("energyCost", "energyDrain"):
                ab[key] = costs.get(ab["name"], {}).get(key)
        export[name] = entry

    frames = [n for n in sorted(export) if not n.startswith("<ARCHWING>")]
    if args:
        frames = [n for n in frames if n in args]

    for n, frame in enumerate(frames, 1):
        data = build_frame(frame, export[frame], export, index, passives)
        path = OUT_DIR / file_name(frame)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        status = "INCOMPLETE" if data.get("_notes") else "ok"
        filled = sum(1 for a in data["abilities"] if a["values"])
        print(f"[{n}/{len(frames)}] {frame}: {filled}/{len(data['abilities'])} abilities with values  {status}")


if __name__ == "__main__":
    main()
