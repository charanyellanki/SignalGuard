import type {
  AnomalyPage,
  DeviceDetail,
  DeviceSummary,
  HealthResponse,
  Severity,
} from "./types";

const API_BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const WS_BASE: string = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: (): Promise<HealthResponse> => getJSON("/health"),

  listDevices: (): Promise<DeviceSummary[]> => getJSON("/devices"),

  getDevice: (deviceId: string): Promise<DeviceDetail> =>
    getJSON(`/devices/${encodeURIComponent(deviceId)}`),

  listAnomalies: (params: {
    device_id?: string;
    anomaly_type?: string;
    severity?: Severity;
    detected_by_model?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<AnomalyPage> => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    }
    const query = qs.toString();
    return getJSON(`/anomalies${query ? `?${query}` : ""}`);
  },
};
