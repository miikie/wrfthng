#!/usr/bin/env python3
"""Check data/raw/wiki_abilities against a previous copy and against the cached wikitext.

Writes data/raw/ability_verification_report.json:
  - energy cost differences between the game export and the wiki (kept as notes, not errors)
  - abilities whose numbers changed since the previous scrape
  - abilities still relying on hand-transcribed data, and augments without per-rank values
  - a spot-check: every per-rank number in sampled abilities must appear in the wiki page text

Usage: python scripts/verify_abilities.py [previous_dir] [--sample N]
"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_wiki_abilities as scraper  # noqa: E402

CUR = ROOT / "data" / "raw" / "wiki_abilities"


def numbers(ability):
    out = {}
    for key, v in ability["values"].items():
        if isinstance(v, dict):
            out[key] = v.get("per_rank") or ([v["base"]] if "base" in v else [])
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    previous = Path(args[0]) if args else None
    sample = int(sys.argv[sys.argv.index("--sample") + 1]) if "--sample" in sys.argv else 5
    report = {"frames": 0, "energy_cost_differences": [], "changed_since_previous": [],
              "hand_transcribed": [], "no_values": [], "augments_without_values": [], "spot_check": []}
    frames = sorted(CUR.glob("*.json"))
    report["frames"] = len(frames)
    for path in frames:
        d = json.loads(path.read_text(encoding="utf-8"))
        old = None
        if previous and (previous / path.name).exists():
            old = {a["name"]: a for a in json.loads((previous / path.name).read_text(encoding="utf-8"))["abilities"]}
        for a in d["abilities"]:
            if a.get("wiki_energy_cost") is not None and a["wiki_energy_cost"] != a["energy_cost"]:
                report["energy_cost_differences"].append({
                    "frame": d["name"], "ability": a["name"],
                    "game_export": a["energy_cost"], "wiki": a["wiki_energy_cost"]})
            if any("transcribed" in n for n in a.get("_notes", [])):
                report["hand_transcribed"].append(f"{d['name']}: {a['name']}")
            if not a["values"]:
                report["no_values"].append(f"{d['name']}: {a['name']}")
            for g in a["augments"]:
                if not g.get("values"):
                    report["augments_without_values"].append(f"{d['name']}: {g['name']}")
            if old and a["name"] in old:
                before = sorted(str(v) for v in numbers(old[a["name"]]).values())
                after = sorted(str(v) for v in numbers(a).values())
                if before != after:
                    report["changed_since_previous"].append({
                        "frame": d["name"], "ability": a["name"],
                        "previously": numbers(old[a["name"]]), "now": numbers(a)})

    # Spot-check against the wiki text the scraper cached
    random.seed(44)
    scraper.CACHE_DIR.mkdir(exist_ok=True)
    for path in random.sample(frames, min(sample, len(frames))):
        d = json.loads(path.read_text(encoding="utf-8"))
        for a in random.sample(d["abilities"], min(3, len(d["abilities"]))):
            title = urllib_title(a.get("wiki_url", "")) or a["name"]
            raw = scraper.fetch_raw(title) or ""
            text = re.sub(r"[',]", "", scraper.strip_markup(raw.replace("'''", "")))
            missing = []
            for key, values in numbers(a).items():
                for v in values:
                    if not re.search(r"(?<![\d.])%s(?![\d])" % re.escape(f"{v:g}" if isinstance(v, float) else str(v)), text):
                        missing.append(f"{key}={v}")
            report["spot_check"].append({"frame": d["name"], "ability": a["name"],
                                         "values_checked": sum(len(v) for v in numbers(a).values()),
                                         "not_found_on_page": missing})
    out = ROOT / "data" / "raw" / "ability_verification_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()})
    for s in report["spot_check"]:
        print(" ", s["frame"], "/", s["ability"], s["values_checked"], "values;", "missing:", s["not_found_on_page"] or "none")


def urllib_title(url):
    import urllib.parse
    return urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("_", " ") if url else ""


if __name__ == "__main__":
    main()
