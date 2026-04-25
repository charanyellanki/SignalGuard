export type Severity = "low" | "medium" | "high";

export interface TelemetryPoint {
  device_id: string;
  site_id: string | null;
  site_name: string | null;
  timestamp: string;
  battery_voltage: number;
  lock_events_count: number;
  signal_strength_dbm: number;
  temperature_c: number;
}

export interface AnomalyRecord {
  id: number;
  device_id: string;
  site_id: string | null;
  site_name: string | null;
  timestamp: string;
  anomaly_type: string;
  detected_by_model: string;
  severity: Severity;
  raw_payload: Record<string, unknown>;
  reason: string | null;
}

export interface DeviceSummary {
  device_id: string;
  site_id: string | null;
  site_name: string | null;
  latest: TelemetryPoint | null;
  anomaly_count: number;
  last_anomaly_at: string | null;
  online: boolean;
}

export interface DeviceDetail {
  device_id: string;
  site_id: string | null;
  site_name: string | null;
  telemetry: TelemetryPoint[];
  anomalies: AnomalyRecord[];
}

export interface AnomalyPage {
  items: AnomalyRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface SiteSummary {
  site_id: string;
  site_name: string;
  device_count: number;
  devices_online: number;
  anomalies_24h: number;
  low_battery_count: number;
}

export interface FleetStats {
  sites_count: number;
  devices_total: number;
  devices_online: number;
  anomalies_24h: number;
  low_battery_count: number;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  db: boolean;
}
