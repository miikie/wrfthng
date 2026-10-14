import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { effectiveBuild, toRequest, toSurvivabilityRequest, useBuildStore } from '../stores/buildStore'
import type { BuildIndex } from '../stores/buildStore'
import { useDebounced } from '../utils/hooks'
import {
  calculate, getAllWeapons, getAmpParts, getBuffs, getCompanions, getEnemies, getEnemyScaled, getMod, getMods,
  getHelminth, getWarframes, getWeapon, getWeaponArcanes, getWeapons, survivability,
} from './client'

// The three catalogues are small and never change while the server runs, so
// they are fetched once and searched in the browser.
const STATIC = { staleTime: Infinity, gcTime: Infinity }

export const useWeapons = () =>
  useQuery({ queryKey: ['weapons'], queryFn: () => getWeapons(), ...STATIC })

export const useEnemies = () =>
  useQuery({ queryKey: ['enemies'], queryFn: () => getEnemies(), ...STATIC })

export const useMods = () =>
  useQuery({ queryKey: ['mods'], queryFn: () => getMods(), ...STATIC })

export const useAllWeapons = () =>
  useQuery({ queryKey: ['weapons', 'all'], queryFn: getAllWeapons, ...STATIC })

export const useCompanions = () =>
  useQuery({ queryKey: ['companions'], queryFn: getCompanions, ...STATIC })

export const useAmpParts = () =>
  useQuery({ queryKey: ['amps'], queryFn: getAmpParts, ...STATIC })

export const useBuffs = () =>
  useQuery({ queryKey: ['buffs'], queryFn: getBuffs, ...STATIC })

export const useWeapon = (name: string) =>
  useQuery({
    queryKey: ['weapon', name],
    queryFn: () => getWeapon(name),
    enabled: name !== '',
    ...STATIC,
    retry: false,
  })

/** A mod's stats at a specific rank, resolved by the server. */
export const useMod = (name: string, rank: number) =>
  useQuery({
    queryKey: ['mod', name, rank],
    queryFn: () => getMod(name, rank),
    enabled: name !== '',
    ...STATIC,
    placeholderData: (prev) => (prev?.name === name ? prev : undefined),
    retry: false,
  })

/** The build as the calculator sees it (Build B may borrow Build A's enemy). */
export function useEffectiveBuild(i: BuildIndex) {
  return useBuildStore(useShallow((s) => effectiveBuild(s, i)))
}

export function useScaledEnemy(i: BuildIndex) {
  const b = useDebounced(useEffectiveBuild(i), 150)
  const args = [b.enemyKey, b.enemyLevel, b.steelPath, b.eximus, b.armorStripPct] as const
  return useQuery({
    queryKey: ['scaled', ...args],
    queryFn: () => getEnemyScaled(...args),
    placeholderData: keepPreviousData,
    retry: false,
  })
}

/** Recalculates 300 ms after the build last changed. */
export function useCalculation(i: BuildIndex) {
  const build = useDebounced(useEffectiveBuild(i), 300)
  const request = useMemo(() => toRequest(build), [build])
  return useQuery({
    queryKey: ['calculate', request],
    queryFn: () => calculate(request),
    placeholderData: keepPreviousData,
    retry: false,
  })
}

export const useWeaponArcanes = () =>
  useQuery({ queryKey: ['weapon-arcanes'], queryFn: getWeaponArcanes, ...STATIC })

export const useWarframes = () =>
  useQuery({ queryKey: ['warframes'], queryFn: getWarframes, ...STATIC })

export const useHelminth = () =>
  useQuery({ queryKey: ['helminth'], queryFn: getHelminth, ...STATIC })

/** Damage taken by the build's Warframe; recalculates 300 ms after the last change. */
export function useSurvivability(i: BuildIndex) {
  const build = useDebounced(useEffectiveBuild(i), 300)
  const request = useMemo(() => toSurvivabilityRequest(build), [build])
  return useQuery({
    queryKey: ['survivability', request],
    queryFn: () => survivability(request),
    placeholderData: keepPreviousData,
    retry: false,
  })
}
