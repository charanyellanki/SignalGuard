import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AnomalyPage, AnomalyStatus, Severity } from "@/lib/types";

export interface AnomalyFilter {
  device_id?: string;
  customer_id?: string;
  site_id?: string;
  anomaly_type?: string;
  severity?: Severity;
  status?: AnomalyStatus;
  detected_by_model?: string;
  limit?: number;
  offset?: number;
}

export function useAnomalies(filter: AnomalyFilter = {}) {
  return useQuery<AnomalyPage>({
    queryKey: ["anomalies", filter],
    queryFn: () => api.listAnomalies(filter),
    refetchInterval: 10_000,
  });
}
