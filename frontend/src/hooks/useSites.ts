import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SiteSummary, UnitsStats } from "@/lib/types";

export function useSites() {
  return useQuery<SiteSummary[]>({
    queryKey: ["sites"],
    queryFn: api.listSites,
    refetchInterval: 5_000,
  });
}

export function useUnitsStats() {
  return useQuery<UnitsStats>({
    queryKey: ["stats"],
    queryFn: api.unitsStats,
    refetchInterval: 5_000,
  });
}
