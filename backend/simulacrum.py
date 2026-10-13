#!/usr/bin/env python3
"""Warframe Damage Simulacrum - Interactive Calculator.

Usage:
    python simulacrum.py                    # Interactive mode
    python simulacrum.py calc <weapon> <enemy> [options]
    python simulacrum.py lookup weapon <name>
    python simulacrum.py lookup enemy <name>
    python simulacrum.py lookup mod <name>
    python simulacrum.py scale <enemy> --level <N> [--steel-path] [--eximus]
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.constants import f32, VIRAL_MAX_STACKS
from engine.damage import DamageCalculator, CalculationResult
from engine.enemies import EnemyScaler, ScaledEnemy
from engine.modding import ModResolver, ModdedStats, build_modded_stats
from engine.weapons import WeaponLoader, WeaponData


# ============================================================================
# FORMATTING
# ============================================================================

def fmt(n: float, decimals: int = 1) -> str:
    """Format a number with commas and specified decimals."""
    if n == float('inf'):
        return "inf"
    if abs(n) >= 1_000_000:
        return f"{n:,.0f}"
    elif abs(n) >= 1000:
        return f"{n:,.{decimals}f}"
    elif abs(n) >= 1:
        return f"{n:.{decimals}f}"
    else:
        return f"{n:.{max(decimals, 3)}f}"


def pct(n: float) -> str:
    """Format as percentage."""
    return f"{n * 100:.1f}%"


def print_separator(char: str = "=", width: int = 70):
    print(char * width)


def print_header(title: str, width: int = 70):
    print_separator()
    print(f" {title}")
    print_separator()


# ============================================================================
# RESULT DISPLAY
# ============================================================================

def display_weapon(w: WeaponData):
    """Display weapon stats."""
    print_header(f"WEAPON: {w.name}")
    print(f"  Category:     {w.category} ({w.mod_type})")
    print(f"  Trigger:      {w.trigger or 'N/A'}")
    print(f"  Base Damage:  {fmt(w.base_damage)}")

    # Damage breakdown
    for dtype, val in sorted(w.damage.items(), key=lambda x: -x[1]):
        bar = "#" * min(30, int(val / w.base_damage * 30)) if w.base_damage > 0 else ""
        print(f"    {dtype:12s}  {fmt(val):>8s}  ({pct(val/w.base_damage):>6s})  {bar}")

    print(f"  Crit Chance:  {pct(w.crit_chance)}")
    print(f"  Crit Mult:    {w.crit_mult:.1f}x")
    print(f"  Status:       {pct(w.status_chance)}")
    print(f"  Fire Rate:    {w.fire_rate:.2f}")
    print(f"  Multishot:    {w.multishot}")
    if w.mag_size > 0:
        print(f"  Magazine:     {w.mag_size}")
        print(f"  Reload:       {w.reload_time:.2f}s")
    print(f"  Mastery:      MR{w.mastery_req}")
    print()


def display_enemy(e: ScaledEnemy):
    """Display scaled enemy stats."""
    sp = " [STEEL PATH]" if e.is_steel_path else ""
    ex = " [EXIMUS]" if e.is_eximus else ""
    print_header(f"ENEMY: {e.name} (Lv.{e.current_level}){sp}{ex}")
    print(f"  Faction:      {e.faction}")
    print(f"  Health:       {fmt(e.health, 0)}")
    if e.shield > 0:
        print(f"  Shields:      {fmt(e.shield, 0)}")
    if e.armor > 0:
        print(f"  Armor:        {fmt(e.armor, 0)}  (DR: {pct(e.armor_dr)}, DM: {e.armor_dm:.4f})")
    if e.overguard > 0:
        print(f"  Overguard:    {fmt(e.overguard, 0)}")
    print(f"  EHP (neutral):{fmt(e.ehp_vs_neutral, 0)}")

    if e.faction_modifiers:
        print(f"  Vulnerabilities / Resistances:")
        for dtype, mod in sorted(e.faction_modifiers.items()):
            label = "WEAK" if mod > 1.0 else "RESIST"
            print(f"    {dtype:12s}  {mod:.1f}x  ({label})")
    print()


def display_result(r: CalculationResult):
    """Display full calculation result."""
    print_header(f"DAMAGE: {r.weapon_name} vs {r.enemy_name} (Lv.{r.enemy_level})")

    # Modded stats
    print("  MODDED WEAPON STATS:")
    print(f"    Base Damage:  {fmt(r.modded_base_damage)}")
    print(f"    Multishot:    {r.modded_multishot:.2f}")
    print(f"    Fire Rate:    {r.modded_fire_rate:.2f}")
    print(f"    Crit Chance:  {pct(r.modded_crit_chance)}")
    print(f"    Crit Mult:    {r.modded_crit_mult:.2f}x")
    print(f"    Status:       {pct(r.modded_status_chance)}")
    if r.modded_mag_size > 0:
        print(f"    Magazine:     {r.modded_mag_size}")
        print(f"    Reload:       {r.modded_reload_time:.2f}s")
    print()

    # Damage breakdown (pre-enemy)
    print("  DAMAGE PER SHOT (before enemy modifiers):")
    for dtype, val in sorted(r.damage.per_type.items(), key=lambda x: -x[1]):
        if val > 0.01:
            print(f"    {dtype:12s}  {fmt(val):>10s}")
    print(f"    {'TOTAL':12s}  {fmt(r.damage.total):>10s}")
    print()

    # Inflicted damage
    print("  INFLICTED PER SHOT (after armor/faction):")
    for dtype, val in sorted(r.damage.per_type_inflicted.items(), key=lambda x: -x[1]):
        if val > 0.01:
            modifier = ""
            type_mod = r.damage.per_type_inflicted.get(dtype, 0)
            base_mod = r.damage.per_type.get(dtype, 0)
            if base_mod > 0 and abs(type_mod / base_mod - 1.0) > 0.01:
                ratio = type_mod / base_mod
                modifier = f"  (x{ratio:.2f})"
            print(f"    {dtype:12s}  {fmt(val):>10s}{modifier}")
    print(f"    {'TOTAL':12s}  {fmt(r.damage.total_inflicted):>10s}")
    print()

    # Crit
    print("  CRITICAL HITS:")
    tier_names = {0: "No crit", 1: "Yellow", 2: "Orange", 3: "Red", 4: "Red+"}
    tier = r.crit.guaranteed_tier
    print(f"    Guaranteed:   {tier_names.get(tier, f'Tier {tier}')} crit "
          f"(x{r.crit.normal_shot_mult:.2f})")
    if r.crit.next_tier_chance > 0:
        next_tier = tier + 1
        print(f"    Next tier:    {pct(r.crit.next_tier_chance)} chance of "
              f"{tier_names.get(next_tier, f'Tier {next_tier}')} "
              f"(x{r.crit.crit_shot_mult:.2f})")
    print(f"    Avg Mult:     x{r.crit.average_mult:.3f}")
    print()

    # Status effects
    if r.viral_damage_bonus > 0:
        print(f"  VIRAL BONUS:    +{pct(r.viral_damage_bonus)} damage to health")
    if r.condition_overload_mult > 1.0:
        print(f"  COND. OVERLOAD: x{r.condition_overload_mult:.2f}")

    # DPS
    print("  DPS:")
    print(f"    Avg Shot:     {fmt(r.dps.average_shot)}")
    print(f"    Eff. FR:      {r.dps.effective_fire_rate:.2f}/s")
    print(f"    Burst DPS:    {fmt(r.dps.burst_dps)}")
    if r.dps.shoot_ratio < 1.0:
        print(f"    Shoot Ratio:  {pct(r.dps.shoot_ratio)}")
    print(f"    Sustained DPS:{fmt(r.dps.sustained_dps)}")
    print()

    # DoTs
    if r.dots:
        print("  STATUS DoT (per proc):")
        for dot in r.dots:
            armor_note = " [IGNORES ARMOR]" if dot.ignores_armor else ""
            print(f"    {dot.dot_type:12s}  {fmt(dot.damage_per_tick)}/tick x{dot.ticks} "
                  f"= {fmt(dot.total_damage)} over {dot.duration:.1f}s{armor_note}")
        print()

    # Kill estimates
    print("  KILL ESTIMATES (approximate):")
    print(f"    Enemy EHP:    {fmt(r.enemy_ehp, 0)}")
    if r.shots_to_kill < float('inf'):
        print(f"    Shots to kill:{fmt(r.shots_to_kill)}")
        if r.time_to_kill > 0:
            print(f"    Time to kill: {r.time_to_kill:.2f}s (sustained)")

    # Arsenal
    print(f"    Arsenal Total:{fmt(r.arsenal_total_damage)}")
    print()


# ============================================================================
# INTERACTIVE MODE
# ============================================================================

class Simulacrum:
    """Interactive damage calculation shell."""

    def __init__(self):
        print("Loading databases...")
        self.weapons = WeaponLoader()
        self.enemies = EnemyScaler()
        self.mods = ModResolver()
        self.calc = DamageCalculator(self.mods)
        print(f"  {len(self.weapons.weapons)} weapons")
        print(f"  {len(self.enemies.enemies)} enemies")
        print(f"  {len(self.mods.mods)} mods")
        print()

    def cmd_weapon(self, args: List[str]):
        """Look up a weapon. Usage: weapon <name>"""
        if not args:
            print("Usage: weapon <name>")
            return
        query = " ".join(args)
        matches = self.weapons.find(query)
        if not matches:
            print(f"No weapons found matching '{query}'")
            return
        if len(matches) > 20:
            print(f"Found {len(matches)} matches. Showing first 20:")
            matches = matches[:20]
        if len(matches) > 1:
            print(f"Found {len(matches)} matches:")
            for m in matches:
                w = self.weapons.get(m)
                print(f"  {m:30s}  {w.category:12s}  DMG:{fmt(w.total_damage)}")
            if len(matches) <= 5:
                # Show details for first match
                w = self.weapons.get(matches[0])
                print()
                display_weapon(w)
        else:
            w = self.weapons.get(matches[0])
            display_weapon(w)

    def cmd_enemy(self, args: List[str]):
        """Look up and scale an enemy. Usage: enemy <name> [level] [--sp] [--eximus]"""
        if not args:
            print("Usage: enemy <name> [level] [--sp] [--eximus]")
            return

        # Parse flags
        level = 100
        steel_path = False
        eximus = False
        name_parts = []

        i = 0
        while i < len(args):
            a = args[i]
            if a == "--sp" or a == "--steel-path" or a == "-sp":
                steel_path = True
            elif a == "--eximus" or a == "-ex":
                eximus = True
            elif a.isdigit():
                level = int(a)
            else:
                name_parts.append(a)
            i += 1

        query = " ".join(name_parts)
        key = self.enemies.find_enemy(query)

        if key is None:
            # Try listing matches
            matches = self.enemies.list_enemies(name_filter=query)
            if matches:
                print(f"Multiple matches for '{query}':")
                for m in matches[:20]:
                    d = self.enemies.enemies[m]
                    print(f"  {d.get('name','?'):30s}  {d.get('faction','?'):15s}  "
                          f"HP:{d.get('health',0)}  AR:{d.get('armor',0)}")
            else:
                print(f"No enemies found matching '{query}'")
            return

        scaled = self.enemies.scale_enemy(key, level, eximus, steel_path)
        display_enemy(scaled)

    def cmd_mod(self, args: List[str]):
        """Look up a mod. Usage: mod <name> [rank]"""
        if not args:
            print("Usage: mod <name> [rank]")
            return

        rank = None
        name_parts = []
        for a in args:
            if a.isdigit():
                rank = int(a)
            else:
                name_parts.append(a)

        query = " ".join(name_parts)
        matches = self.mods.find_mod(query)

        if not matches:
            print(f"No mods found matching '{query}'")
            return

        for m in matches[:10]:
            try:
                resolved = self.mods.resolve(m, rank)
                stats_str = ", ".join(f"{s.stat}: +{pct(s.value)}" if abs(s.value) < 10
                                     else f"{s.stat}: +{s.value}" for s in resolved.stats)
                print(f"  {resolved.name:30s}  R{resolved.rank}/{resolved.max_rank}  "
                      f"{resolved.mod_type:10s}  {stats_str}")
                if resolved.conditional:
                    print(f"    Conditional: {resolved.conditional}")
                if resolved.note:
                    print(f"    Note: {resolved.note}")
            except Exception as e:
                print(f"  {m}: Error - {e}")
        print()

    def cmd_calc(self, args: List[str]):
        """Calculate damage. Usage: calc <weapon> vs <enemy> [level] [--sp] [--mods mod1,mod2,...] [--headshot] [--viral N]"""
        if not args:
            print("Usage: calc <weapon> vs <enemy> [level] [--sp] [--mods mod1,mod2,...] "
                  "[--headshot] [--viral N] [--eximus] [--co N]")
            return

        # Parse the command
        weapon_parts = []
        enemy_parts = []
        level = 100
        steel_path = False
        eximus = False
        headshot = False
        viral_stacks = 0
        status_types = 0
        mod_names: List[str] = []
        extra_elem: Dict[str, float] = {}

        parsing = "weapon"  # weapon or enemy
        i = 0
        while i < len(args):
            a = args[i]
            if a.lower() == "vs":
                parsing = "enemy"
            elif a == "--sp" or a == "--steel-path":
                steel_path = True
            elif a == "--eximus":
                eximus = True
            elif a == "--headshot" or a == "--hs":
                headshot = True
            elif a == "--viral" and i + 1 < len(args):
                i += 1
                viral_stacks = int(args[i])
            elif a == "--co" and i + 1 < len(args):
                i += 1
                status_types = int(args[i])
            elif a == "--mods" and i + 1 < len(args):
                i += 1
                mod_names = [m.strip() for m in args[i].split(",")]
            elif a == "--elem" and i + 2 < len(args):
                # --elem Void 0.25
                i += 1
                elem_type = args[i]
                i += 1
                elem_val = float(args[i])
                extra_elem[elem_type] = elem_val
            elif a.isdigit():
                level = int(a)
            else:
                if parsing == "weapon":
                    weapon_parts.append(a)
                else:
                    enemy_parts.append(a)
            i += 1

        # Find weapon
        weapon_query = " ".join(weapon_parts)
        weapon_matches = self.weapons.find(weapon_query)
        if not weapon_matches:
            print(f"No weapon found matching '{weapon_query}'")
            return
        weapon = self.weapons.get(weapon_matches[0])

        # Find enemy
        enemy_query = " ".join(enemy_parts) if enemy_parts else "Lancer"
        enemy_key = self.enemies.find_enemy(enemy_query)
        if enemy_key is None:
            print(f"No enemy found matching '{enemy_query}'")
            return

        scaled_enemy = self.enemies.scale_enemy(enemy_key, level, eximus, steel_path)

        # Resolve mods
        resolved_mods = []
        for mod_name in mod_names:
            try:
                resolved = self.mods.resolve(mod_name)
                resolved_mods.append(resolved)
            except ValueError as e:
                print(f"Warning: {e}")

        # Calculate
        result = self.calc.calculate(
            weapon=weapon,
            enemy=scaled_enemy,
            mods=resolved_mods if resolved_mods else None,
            headshot=headshot,
            viral_stacks=viral_stacks,
            status_types_on_target=status_types,
            extra_elemental=extra_elem if extra_elem else None,
        )

        # Display
        display_weapon(weapon)
        display_enemy(scaled_enemy)
        display_result(result)

    def cmd_compare(self, args: List[str]):
        """Compare weapons. Usage: compare <weapon1> , <weapon2> vs <enemy> [level]"""
        if not args:
            print("Usage: compare <weapon1> , <weapon2> [, weapon3] vs <enemy> [level]")
            return

        # Split on "vs"
        full = " ".join(args)
        if " vs " not in full.lower():
            print("Need 'vs <enemy>' in command")
            return

        weapons_part, enemy_part = full.lower().split(" vs ", 1)
        weapon_queries = [w.strip() for w in weapons_part.split(",")]

        # Parse enemy
        enemy_args = enemy_part.strip().split()
        enemy_name_parts = []
        level = 100
        steel_path = False
        for a in enemy_args:
            if a == "--sp":
                steel_path = True
            elif a.isdigit():
                level = int(a)
            else:
                enemy_name_parts.append(a)

        enemy_query = " ".join(enemy_name_parts)
        enemy_key = self.enemies.find_enemy(enemy_query)
        if not enemy_key:
            print(f"Enemy not found: {enemy_query}")
            return

        scaled = self.enemies.scale_enemy(enemy_key, level, is_steel_path=steel_path)
        display_enemy(scaled)

        # Calculate for each weapon
        print_header("COMPARISON")
        print(f"  {'Weapon':25s} {'Burst DPS':>12s} {'Sust DPS':>12s} "
              f"{'Avg Shot':>10s} {'STK':>6s} {'TTK':>8s}")
        print("-" * 80)

        for wq in weapon_queries:
            matches = self.weapons.find(wq.strip())
            if not matches:
                print(f"  {wq:25s}  -- not found --")
                continue
            weapon = self.weapons.get(matches[0])
            r = self.calc.calculate(weapon=weapon, enemy=scaled)

            stk = f"{r.shots_to_kill:.1f}" if r.shots_to_kill < 9999 else "N/A"
            ttk = f"{r.time_to_kill:.2f}s" if r.time_to_kill < 9999 else "N/A"
            print(f"  {weapon.name:25s} {fmt(r.dps.burst_dps):>12s} "
                  f"{fmt(r.dps.sustained_dps):>12s} {fmt(r.dps.average_shot):>10s} "
                  f"{stk:>6s} {ttk:>8s}")
        print()

    def cmd_help(self, args: List[str] = None):
        """Show help."""
        print_header("WARFRAME DAMAGE SIMULACRUM")
        print("""
  Commands:
    weapon <name>           Look up weapon stats
    enemy <name> [lv] [flags]  Scale enemy to level
    mod <name> [rank]       Look up mod stats

    calc <weapon> vs <enemy> [level] [options]
      Options:
        --sp / --steel-path   Steel Path (+100 level, 2.5x shields)
        --eximus              Apply Eximus stat bonuses
        --headshot / --hs     Headshot multiplier
        --viral N             N Viral stacks on target (0-10)
        --co N                N unique status types on target
        --mods mod1,mod2,...  Apply these mods (max rank)
        --elem Type Value     Add elemental (e.g. --elem Void 0.25)

    compare <w1> , <w2> vs <enemy> [level] [--sp]
      Quick DPS comparison of multiple weapons

    armor <value>           Show DR at a given armor value

    help                    This message
    quit / exit             Exit

  Examples:
    weapon braton prime
    enemy heavy gunner 200 --sp
    mod serration
    calc soma prime vs heavy gunner 300 --sp --mods Serration,Split Chamber,Point Strike,Vital Sense
    compare soma prime , boltor prime , ignis wraith vs bombard 200
""")

    def cmd_armor(self, args: List[str]):
        """Show armor DR at a value. Usage: armor <value>"""
        if not args or not args[0].replace(".", "").isdigit():
            print("Usage: armor <value>")
            return
        armor = float(args[0])
        dr = self.enemies.armor_dr_at(armor)
        dm = 1.0 - dr
        print(f"  Armor:   {fmt(armor)}")
        print(f"  DR:      {pct(dr)}")
        print(f"  DM:      {dm:.4f}")
        print(f"  EHP mult:{1/dm:.2f}x")
        print()

    def run(self):
        """Run the interactive shell."""
        self.cmd_help()

        while True:
            try:
                line = input("simulacrum> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "help":
                self.cmd_help(args)
            elif cmd in ("weapon", "w"):
                self.cmd_weapon(args)
            elif cmd in ("enemy", "e"):
                self.cmd_enemy(args)
            elif cmd in ("mod", "m"):
                self.cmd_mod(args)
            elif cmd in ("calc", "c", "damage", "dmg"):
                self.cmd_calc(args)
            elif cmd in ("compare", "cmp"):
                self.cmd_compare(args)
            elif cmd == "armor":
                self.cmd_armor(args)
            else:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    argv = sys.argv[1:]
    if not argv:
        sim = Simulacrum()
        sim.run()
        return

    sim = Simulacrum()
    cmd = argv[0].lower()
    args = argv[1:]

    if cmd in ("weapon", "w"):
        sim.cmd_weapon(args)
    elif cmd in ("enemy", "e"):
        sim.cmd_enemy(args)
    elif cmd in ("mod", "m"):
        sim.cmd_mod(args)
    elif cmd in ("calc", "c"):
        sim.cmd_calc(args)
    elif cmd in ("compare", "cmp"):
        sim.cmd_compare(args)
    elif cmd == "armor":
        sim.cmd_armor(args)
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: weapon, enemy, mod, calc, compare, armor")


if __name__ == "__main__":
    main()
