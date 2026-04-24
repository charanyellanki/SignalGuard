export type Severity = "low" | "medium" | "high";

export interface TelemetryPoint {
  device_id: string;
  timestamp: string;
  battery_voltage: number;
  lock_events_count: number;
  signal_strength_dbm: number;
  temperature_c: number;
}

export interface AnomalyRecord {
  id: number;
  device_id: string;
  timestamp: string;
  anomaly_type: string;
  detected_by_model: string;
  severity: Severity;
  raw_payload: Record<string, unknown>;
  reason: string | null;
}

export interface DeviceSummary {
  device_id: string;
  latest: TelemetryPoint | null;
  anomaly_count: number;
  last_anomaly_at: string | null;
}

export interface DeviceDetail {
  device_id: string;
  telemetry: TelemetryPoint[];
  anomalies: AnomalyRecord[];
}

export interface AnomalyPage {
  items: AnomalyRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  db: boolean;
}
