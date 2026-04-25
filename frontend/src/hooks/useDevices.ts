import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DeviceDetail, DeviceSummary } from "@/lib/types";

export function useDevices(siteId?: string) {
  return useQuery<DeviceSummary[]>({
    queryKey: ["devices", siteId ?? "all"],
    queryFn: () => api.listDevices(siteId),
    refetchInterval: 5_000,
  });
}

export function useDevice(deviceId: string | null) {
  return useQuery<DeviceDetail>({
    queryKey: ["device", deviceId],
    queryFn: () => api.getDevice(deviceId as string),
    enabled: !!deviceId,
    refetchInterval: deviceId ? 3_000 : false,
  });
}
