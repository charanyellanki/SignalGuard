import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FleetStats, SiteSummary } from "@/lib/types";

export function useSites() {
  return useQuery<SiteSummary[]>({
    queryKey: ["sites"],
    queryFn: api.listSites,
    refetchInterval: 5_000,
  });
}

export function useFleetStats() {
  return useQuery<FleetStats>({
    queryKey: ["stats"],
    queryFn: api.fleetStats,
    refetchInterval: 5_000,
  });
}
