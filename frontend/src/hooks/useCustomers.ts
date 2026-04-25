import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AnomalyActionRequest, AnomalyRecord, CustomerSummary } from "@/lib/types";

export function useCustomers() {
  return useQuery<CustomerSummary[]>({
    queryKey: ["customers"],
    queryFn: api.listCustomers,
    refetchInterval: 5_000,
  });
}

export function useAnomalyAction() {
  const qc = useQueryClient();
  return useMutation<AnomalyRecord, Error, { id: number; body: AnomalyActionRequest }>({
    mutationFn: ({ id, body }) => api.actOnAnomaly(id, body),
    onSuccess: () => {
      // Refresh anything driven by status/open-incident counts.
      qc.invalidateQueries({ queryKey: ["anomalies"] });
      qc.invalidateQueries({ queryKey: ["customers"] });
      qc.invalidateQueries({ queryKey: ["sites"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}
