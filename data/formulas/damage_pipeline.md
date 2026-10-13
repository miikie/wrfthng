# Warframe Damage Calculation Pipeline
# Source: https://wiki.warframe.com/w/Damage/Calculation

## 1. Quantization
# Damage is quantized to nearest 1/32 of modded base damage

Scale = Modded_Base_Damage / 32

# For each damage type:
x = Total_Damage_Type_Value / Modded_Base_Damage
Quantized(x) = sign(x) * floor(abs(x) * 32 + 0.5) / 32
Quantized_Damage_Type_Value = Quantized(x) * Modded_Base_Damage

# Physical mods (e.g. Maim +120% Slash) apply BEFORE quantization:
# Modded_Slash = Base_Slash * (1 + Slash_Bonus)
# Then quantize that result

# Elemental mods calculate from FULL base damage, quantize their sum per combined element:
# e.g. 90% Cold + 60% Toxin = 150% Viral
# Viral_Damage = round((Base_Damage * 1.50) / Scale) * Scale

# +Damage mods (Serration, Hornet Strike) and Faction mods are simple multipliers
# applied AFTER quantization (they scale both numerator and denominator equally)

## 2. Unarmored Enemies
Inflicted_Damage = Starting_Damage * (1 + Health_Type_Modifier)
# Health_Type_Modifier from damage type vs health type table

## 3. Armored Enemies
# NEW formula (post-armor-rework):
DM = 1 - 0.9 * sqrt(AR / 2700)
# AR = target armor after all reductions (Corrosive Projection, Corrosive procs, Terrify, etc.)
# Enemy armor is HARD CAPPED at 2700 (= 90% DR)
# Shields are NOT mitigated by armor
# Toxin damage bypasses shields (hits health directly) for most enemies

## 4. Modded Stats (General)
Modded_Stat = Base_Stat * (1 + Stat_Bonuses)
# Exception for reload/charge time:
Modded_Time = Base_Time / (1 + Speed_Bonuses)

## 5. Arsenal Total Damage
Arsenal_Total_Damage = Base_Damage \
    * (1 + Elemental_Bonuses
       + Unmodded_Impact_Distribution * Impact_Bonuses
       + Unmodded_Puncture_Distribution * Puncture_Bonuses
       + Unmodded_Slash_Distribution * Slash_Bonuses) \
    * (1 + Damage_Bonuses) \
    * (Base_Multishot * (1 + Multishot_Bonuses))
# For melee: remove multishot. Does not include Stance multipliers.

## 6. Total Inflicted Damage (vs enemy)
Total_Inflicted_Damage = sum(SD_i * DM_i for each damage type i)
# SD_i = modded damage of type i
# DM_i = damage modifier for type i (from health/armor type interaction)

## 7. Critical Hits
# Normal shot (guaranteed crit tier):
Normal_Shot = Total_Damage * (1 + floor(Modded_Crit_Chance) * (Modded_Crit_Mult - 1))
# Critical shot (next tier up):
Critical_Shot = Total_Damage * (1 + ceil(Modded_Crit_Chance) * (Modded_Crit_Mult - 1))
# Average shot:
Average_Shot = Total_Damage * (1 + Modded_Crit_Chance * (Modded_Crit_Mult - 1))

# Crit tiers: yellow (1x mult), orange (2x mult), red (3x mult), etc.
# At 250% crit chance: guaranteed orange crit, 50% chance red crit

## 8. AoE Direct Hits
Average_Shot_DirectAoE = Average_Shot_Direct + Average_Shot_AoE
# Direct and AoE have separate stat pools
# Condition Overload only affects direct hit, not AoE

## 9. Weak Point (Headshot) Hits
Average_Shot_WeakPoint = Average_Shot * (Weak_Point_Multiplier + Weak_Point_Damage_Bonus)
# Weak Point Damage Bonus: Target Acquired, Primary Acuity, Pistol Acuity
# Some weapons cannot headshot (Arca Plasmor). AoE damage cannot headshot.

## 10. Gun DPS

### Effective Fire Rate by Trigger Type
# Auto, Auto-Spool, Semi, Duplex, Held:
Effective_FR = Modded_Fire_Rate

# Charge:
Effective_FR_Charge = 1 / (Modded_Charge_Time + 1/Modded_Fire_Rate)

# Burst:
Effective_FR_Burst = Burst_Count / (1/Modded_Fire_Rate + (Burst_Count - 1) * Burst_Delay)

### Burst DPS
Average_Burst_DPS = Average_Shot * Effective_Fire_Rate

### Shots Per Magazine
Shots_Per_Mag = Modded_Mag_Size / Ammo_Cost_Per_Shot
# Incarnon: Shots_Per_Mag = Max_Incarnon_Charge

### Sustained DPS
Shoot_Ratio = Shots_Per_Mag / (Effective_FR * Modded_Reload_Time + Shots_Per_Mag)
# Vectis/Vectis Prime: subtract 1 from denominator (no reload delay)
Average_Sustained_DPS = Average_Burst_DPS * Shoot_Ratio

## 11. Melee DPS
Average_Hit = Avg_Combo_Damage_Multiplier * Total_Damage * (1 + Modded_Crit_Chance * (Modded_Crit_Mult - 1))
Average_DPS = (Average_Hit * Modded_Attack_Speed) / Base_Combo_Length

## 12. Damage Over Time (Status Effects)
# DoT is NOT quantized. Uses binary32 (float32) arithmetic.
# DoT calculated from attack's modded base damage, not quantized values.

# General DoT tick formula:
Unrounded_Tick = (sum(Seeds_i) + 1) * C * M
# C = 0.5 for Heat, Electricity, Toxin, Gas
# C = 0.35 for Slash
# M = product of remaining multipliers (elemental, faction, status-damage bonuses)
# The "+1" is added ONCE per tick group, not per stack

# Specific DoT formulas:
# Avg_Slash_DoT = 0.35 * Base_Avg_DoT
# Avg_Electricity_DoT = 0.5 * (1 + Electricity_Bonuses) * Base_Avg_DoT
# Avg_Heat_DoT = 0.5 * (1 + Heat_Bonuses) * Base_Avg_DoT
# Avg_Toxin_DoT = 0.5 * (1 + Toxin_Bonuses) * Base_Avg_DoT
# Avg_Gas_DoT = 0.5 * (1 + Gas_Bonuses) * Base_Avg_DoT

# Slash DoT deals Cinematic (True) damage - ignores armor
# Faction bonus applies TWICE to DoT (once in base damage, once as multiplier)

# Base_Avg_DoT = Modded_Damage * (1 + Faction_Bonuses) * (1 + Status_Damage_Bonuses) * Total_Ticks * (1 + Status_Duration_Bonuses)
# Modded_Damage for DoT = Modded_Base_Damage * Modded_Multishot * (1 + Faction_Bonuses)
# NOTE: DoT modded damage IGNORES elemental and physical damage bonuses

# Heat: accumulates all active stacks into one tick
# Slash/Toxin: each stack ticks independently
# Electricity: instances keep own durations, but same-pulse contributions consolidated

## 13. Blast Status (Stack-and-Detonate, NOT DoT)
# Each proc adds 1 stack (max 10, bosses/eximus max 4), lasts 1.5s
# Stack expiry (1.5s timeout): deals max(1, 0.3 * H) Blast damage
# Detonation (cap reached or enemy dies): 3 * sum(all_active_stack_H), 5m radial, no falloff

## 14. Display Rounding
Displayed_Damage = floor(Raw_Damage + 0.5)
# This is display-only, does not affect actual health change
