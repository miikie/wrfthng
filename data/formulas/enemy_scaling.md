# Enemy Level Scaling Formulas
# Source: https://wiki.warframe.com/w/Enemy_Level_Scaling

## General Structure
# Each stat uses: f_i(x) = 1 + C_i * q^E_i
# q = Current_Level - Base_Level (for most stats)
# q = Current_Level - 1 (for Overguard)
# All intermediate math uses IEEE 754 binary32 (float32)
# Current_Value = f32(f32(Base_Value) * f32(Multiplier))

## Smoothstep Interpolation (for stats with two curves)
# t = clamp(f32((q - L) / (U - L)), 0, 1)
# s = f32(f32(t*t) * f32(3 - f32(2*t)))
# Multiplier = f32(f1(x) + f32(f32(f2(x) - f1(x)) * s))
# DO NOT rearrange as f1*(1-s) + f2*s (different float32 result)

## HEALTH SCALING
# Transition bounds: L=70, U=80

### Grineer & Scaldra Health
# f1(x) = 1 + 0.015 * (x - BaseLevel)^2.12
# f2(x) = 1 + 10.7332 * (x - BaseLevel)^0.72

### Corpus Health
# f1(x) = 1 + 0.015 * (x - BaseLevel)^2.12
# f2(x) = 1 + 13.4165 * (x - BaseLevel)^0.55

### Infested Health
# f1(x) = 1 + 0.0225 * (x - BaseLevel)^2.12
# f2(x) = 1 + 16.0998 * (x - BaseLevel)^0.72

### Corrupted Health
# f1(x) = 1 + 0.015 * (x - BaseLevel)^2.1
# f2(x) = 1 + 10.7332 * (x - BaseLevel)^0.685

### Murmur, Sentient, Anarchs, Unaffiliated Health
# f1(x) = 1 + 0.015 * (x - BaseLevel)^2
# f2(x) = 1 + 10.7332 * (x - BaseLevel)^0.5

### Techrot Health
# f1(x) = 1 + 0.02 * (x - BaseLevel)^2.12
# f2(x) = 1 + 15.0998 * (x - BaseLevel)^0.7

### Eximus Health (with Shields or Armor)
# Uses faction's normal health scaling, but base health is replaced:
# x = current level
# x <= 15: max(BaseHP * 1.1, 0.25 * (BaseHP + 900))
# 15 < x <= 25: max(BaseHP * 1.1, 0.25 * (BaseHP + 900) * [1 + 0.025*(x-15)])
# 25 < x <= 35: max(BaseHP * 1.1, 0.25 * (BaseHP + 900) * [1.25 + 0.125*(x-25)])
# 35 < x <= 50: max(BaseHP * 1.1, 0.25 * (BaseHP + 900) * [2.5 + (2/15)*(x-35)])
# 50 < x <= 100: max(BaseHP * 1.1, 0.25 * (BaseHP + 900) * [4.5 + 0.03*(x-50)])
# x > 100: max(BaseHP * 1.1, 0.25 * (BaseHP + 900) * 6)

### Eximus Health (NO Shields or Armor) - same breakpoints, 0.375 instead of 0.25

## SHIELD SCALING
# Transition bounds: L=70, U=80

### Corpus Shields
# f1(x) = 1 + 0.02 * (x - BaseLevel)^1.76
# f2(x) = 1 + 2 * (x - BaseLevel)^0.76

### Corrupted Shields
# f1(x) = 1 + 0.02 * (x - BaseLevel)^1.75
# f2(x) = 1 + 2 * (x - BaseLevel)^0.75

### Grineer & Sentient Shields
# f1(x) = 1 + 0.02 * (x - BaseLevel)^1.75
# f2(x) = 1 + 1.6 * (x - BaseLevel)^0.75

### Techrot Shields
# f1(x) = 1 + 0.02 * (x - BaseLevel)^1.76
# f2(x) = 1 + 3.5 * (x - BaseLevel)^0.76

### Eximus Shield base increase (same piecewise as health but uses BaseShield * multiplier, no +900)

## ARMOR SCALING
# Transition bounds: L=70, U=80
# HARD CAP: 2700 armor (90% DR)
# MINIMUM CAP: 200 armor (initial value only; can be stripped below)
# Steel Path does NOT increase armor (as of Update 36.0)

# f1(x) = 1 + 0.005 * (x - BaseLevel)^1.75
# f2(x) = 1 + 0.4 * (x - BaseLevel)^0.75

# Armor DR formula (post-Update 36):
# DM = 1 - 0.9 * sqrt(AR / 2700)
# where AR = min(scaled_armor, 2700) after debuffs

## OVERGUARD SCALING
# Transition bounds: L=45, U=50
# q = Current_Level - 1 (NOT base level)
# All Eximus base Overguard = 12

# f1(x) = 1 + 0.0015 * (x - 1)^4
# f2(x) = 1 + 260 * (x - 1)^0.9

## DAMAGE SCALING (enemy damage output)

### Default (Infested, Murmur, Sentient, etc.)
# Damage_Multiplier = 1 + 0.015 * (Current_Level - Base_Level)^1.55

### Corpus, Grineer, Techrot (modified, uses smoothstep L=1, U=25)
# f1(x) = 1 + 0.015 * (x - BaseLevel)^1.75
# f2(x) = 1 + 0.0075 * (x - BaseLevel)^1.55

### Faction base damage multipliers (flat, on top of scaling):
# Corpus: 2x
# Grineer: 2x
# Techrot: 2x
# Infested: 3x

## AFFINITY SCALING
# Affinity_Multiplier = 1 + 0.1425 * Current_Level^0.5
# Eximus_Affinity_Multiplier = 3 + 0.1425 * Current_Level^0.5
# NOTE: does NOT subtract base level. Result is floored to integer.

## STEEL PATH MODIFIERS (as of Update 36.0)
# +100 to enemy base level
# Shields multiplied by 2.5x (was 6.25x before fix)
# Armor: NO additional multiplier (removed in Update 36.0)
# Health: uses normal scaling from the +100 level boost

## EHP FORMULAS
# Health only: EHP = Health
# Health + Shields: EHP = Health + Shields (simplified, Toxin complicates)
# Health + Armor: EHP = Health * (1 + (BaseArmor * ArmorMult) / 300)
# Health + Shields + Armor: EHP = Health * (1 + (BaseArmor * ArmorMult) / 300) + Shields * (BaseShields/BaseHealth)

## ENEMY LEVEL CAP
# Normal cap: 9999
# Can be exceeded in Void Fissure missions
# Regular enemy stats don't scale with squad size
# Exceptions: Demolishers, Acolytes, Archons

## ENDLESS MISSION LEVEL SCALING
# Disruption: Level_Increase_Per_Round = 2.59 * e^(0.139 * Round_Number)
# Spawn_Level = Starting_Level + sum(L(x) for x=1 to Round_Number)
# Survival/Defense: approximately exponential until level 5000 (~4 hours), then linear
# Max spawn level 9999 reached around 8+ hours
