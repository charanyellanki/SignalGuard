export type Severity = "low" | "medium" | "high";

export type AnomalyStatus =
  | "open"
  | "acknowledged"
  | "dispatched"
  | "snoozed"
  | "resolved"
  | "false_positive";

export type AnomalyAction =
  | "acknowledge"
  | "dispatch"
  | "snooze"
  | "resolve"
  | "false_positive"
  | "reopen";

export interface TelemetryPoint {
  device_id: string;
  customer_id: string | null;
  customer_name: string | null;
  site_id: string | null;
  site_name: string | null;
  gateway_id: string | null;
  building: string | null;
  unit_id: string | null;
  timestamp: string;
  battery_voltage: number;
  lock_events_count: number;
  signal_strength_dbm: number;
  temperature_c: number;
}

export interface AnomalyRecord {
  id: number;
  device_id: string;
  customer_id: string | null;
  customer_name: string | null;
  site_id: string | null;
  site_name: string | null;
  gateway_id: string | null;
  building: string | null;
  unit_id: string | null;
  timestamp: string;
  anomaly_type: string;
  detected_by_model: string;
  severity: Severity;
  raw_payload: Record<string, unknown>;
  reason: string | null;
  status: AnomalyStatus;
  assignee: string | null;
  acted_at: string | null;
  action_note: string | null;
}

export interface AnomalyActionRequest {
  action: AnomalyAction;
  assignee?: string;
  note?: string;
}

export interface DeviceSummary {
  device_id: string;
  customer_id: string | null;
  customer_name: string | null;
  site_id: string | null;
  site_name: string | null;
  building: string | null;
  unit_id: string | null;
  latest: TelemetryPoint | null;
  anomaly_count: number;
  last_anomaly_at: string | null;
  online: boolean;
}

export interface DeviceDetail {
  device_id: string;
  customer_id: string | null;
  customer_name: string | null;
  site_id: string | null;
  site_name: string | null;
  building: string | null;
  unit_id: string | null;
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
  customer_id: string | null;
  customer_name: string | null;
  gateway_id: string | null;
  device_count: number;
  devices_online: number;
  anomalies_24h: number;
  open_incidents: number;
  low_battery_count: number;
}

export interface CustomerSummary {
  customer_id: string;
  customer_name: string;
  facility_count: number;
  device_count: number;
  devices_online: number;
  anomalies_24h: number;
  open_incidents: number;
  p0_incidents: number;
  tenants_impacted: number;
}

export interface UnitsStats {
  customers_count: number;
  sites_count: number;
  devices_total: number;
  devices_online: number;
  anomalies_24h: number;
  open_incidents: number;
  p0_incidents: number;
  tenants_impacted: number;
  low_battery_count: number;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  db: boolean;
}
