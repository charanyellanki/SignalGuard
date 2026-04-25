import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSimulationState() {
  return useQuery<{ running: boolean }>({
    queryKey: ["simulation"],
    queryFn: api.getSimulationState,
    refetchInterval: 5_000,
    // Don't blow up the UI if the simulator is bouncing — treat unreachable
    // as "we don't know" rather than a hard error.
    retry: false,
  });
}

export function useSimulationToggle() {
  const qc = useQueryClient();
  return useMutation<{ running: boolean }, Error, boolean>({
    mutationFn: (running) => api.setSimulationRunning(running),
    onSuccess: (data) => {
      qc.setQueryData(["simulation"], data);
    },
  });
}
