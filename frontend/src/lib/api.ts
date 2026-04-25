import type {
  AnomalyActionRequest,
  AnomalyPage,
  AnomalyRecord,
  AnomalyStatus,
  CustomerSummary,
  DeviceDetail,
  DeviceSummary,
  HealthResponse,
  Severity,
  SiteSummary,
  UnitsStats,
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

async function postJSON<T, B>(path: string, body: B): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: (): Promise<HealthResponse> => getJSON("/health"),

  unitsStats: (): Promise<UnitsStats> => getJSON("/stats"),

  listCustomers: (): Promise<CustomerSummary[]> => getJSON("/customers"),

  listSites: (): Promise<SiteSummary[]> => getJSON("/sites"),

  listDevices: (params: { customer_id?: string; site_id?: string } = {}):
    Promise<DeviceSummary[]> => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v) qs.set(k, String(v));
    }
    const query = qs.toString();
    return getJSON(`/devices${query ? `?${query}` : ""}`);
  },

  getDevice: (deviceId: string): Promise<DeviceDetail> =>
    getJSON(`/devices/${encodeURIComponent(deviceId)}`),

  listAnomalies: (params: {
    device_id?: string;
    customer_id?: string;
    site_id?: string;
    anomaly_type?: string;
    severity?: Severity;
    status?: AnomalyStatus;
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

  actOnAnomaly: (id: number, body: AnomalyActionRequest): Promise<AnomalyRecord> =>
    postJSON(`/anomalies/${id}/action`, body),

  // Demo control plane — pause/resume the simulator firehose.
  getSimulationState: (): Promise<{ running: boolean }> => getJSON("/admin/simulation"),

  setSimulationRunning: (running: boolean): Promise<{ running: boolean }> =>
    postJSON(`/admin/simulation/${running ? "resume" : "pause"}`, {}),
};
