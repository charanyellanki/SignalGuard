import { useCallback, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Flame,
  Hammer,
  Moon,
  RefreshCw,
  Truck,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAnomalies } from "@/hooks/useAnomalies";
import { useAnomalyAction } from "@/hooks/useCustomers";
import { useWebSocket } from "@/hooks/useWebSocket";
import { WS_BASE } from "@/lib/api";
import type {
  AnomalyAction,
  AnomalyRecord,
  AnomalyStatus,
  Severity,
} from "@/lib/types";

interface Props {
  onStatusChange?: (connected: boolean) => void;
  onSelectDevice?: (deviceId: string) => void;
}

function severityVariant(s: Severity): "destructive" | "warning" | "secondary" {
  return s === "high" ? "destructive" : s === "medium" ? "warning" : "secondary";
}

function severityLabel(s: Severity): string {
  return s === "high" ? "P0" : s === "medium" ? "P1" : "P2";
}

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  const now = Date.now();
  const diffSec = Math.max(0, Math.round((now - t) / 1000));
  if (diffSec < 60) return `${diffSec}s ago`;
  const m = Math.round(diffSec / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

const ANOMALY_LABELS: Record<string, string> = {
  lock_battery_critical: "Lock battery critical",
  gateway_disconnect: "Gateway disconnect",
  tenant_access_anomaly: "Unusual tenant access",
  behavioral_drift: "Behavioral drift",
  telemetry_anomaly: "Telemetry anomaly",
};

const STATUS_VARIANT: Record<AnomalyStatus, "destructive" | "warning" | "secondary" | "success"> = {
  open: "destructive",
  acknowledged: "warning",
  dispatched: "warning",
  snoozed: "secondary",
  resolved: "success",
  false_positive: "secondary",
};

const parseAnomaly = (raw: string): AnomalyRecord | null => {
  try {
    return JSON.parse(raw) as AnomalyRecord;
  } catch {
    return null;
  }
};

export function IncidentsQueue({ onStatusChange, onSelectDevice }: Props) {
  // Fetch a healthy slice of recent anomalies — we'll filter to open ones in
  // memory so an analyst can flip filters without round-tripping.
  const seed = useAnomalies({ limit: 100 });
  const action = useAnomalyAction();
  const [statusFilter, setStatusFilter] = useState<"open" | "all">("open");

  const { status, messages } = useWebSocket<AnomalyRecord>({
    url: `${WS_BASE}/ws/anomalies`,
    parse: parseAnomaly,
    maxBuffer: 100,
    onMessage: useCallback(() => onStatusChange?.(true), [onStatusChange]),
  });
  onStatusChange?.(status === "open");

  const merged: AnomalyRecord[] = useMemo(() => {
    const byId = new Map<number, AnomalyRecord>();
    for (const a of seed.data?.items ?? []) byId.set(a.id, a);
    // WS messages are newer; let them override seeded copies.
    for (const a of messages) byId.set(a.id, a);
    let arr = [...byId.values()];
    if (statusFilter === "open") arr = arr.filter((a) => a.status === "open");
    return arr.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }, [messages, seed.data, statusFilter]);

  const openCount = useMemo(
    () => (seed.data?.items ?? []).filter((a) => a.status === "open").length,
    [seed.data],
  );

  const handleAction = (id: number, verb: AnomalyAction) => {
    action.mutate({ id, body: { action: verb, assignee: "noc-engineer" } });
  };

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="shrink-0 pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Active incidents</CardTitle>
          <div className="flex items-center gap-1.5">
            <Badge variant={status === "open" ? "success" : "warning"}>
              {status === "open" ? "live" : status}
            </Badge>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-1 text-[11px]">
          <button
            onClick={() => setStatusFilter("open")}
            className={`rounded-md px-2 py-0.5 ${
              statusFilter === "open"
                ? "bg-foreground text-background"
                : "bg-muted text-muted-foreground hover:bg-muted/70"
            }`}
          >
            Open ({openCount})
          </button>
          <button
            onClick={() => setStatusFilter("all")}
            className={`rounded-md px-2 py-0.5 ${
              statusFilter === "all"
                ? "bg-foreground text-background"
                : "bg-muted text-muted-foreground hover:bg-muted/70"
            }`}
          >
            All recent
          </button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-0">
        {merged.length === 0 ? (
          <p className="p-4 text-xs text-muted-foreground">
            {statusFilter === "open"
              ? "No open incidents — all units healthy."
              : "No recent anomalies."}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {merged.map((a) => (
              <IncidentRow
                key={a.id}
                a={a}
                onAction={handleAction}
                pending={action.isPending && action.variables?.id === a.id}
                onSelectDevice={onSelectDevice}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

interface RowProps {
  a: AnomalyRecord;
  pending: boolean;
  onAction: (id: number, verb: AnomalyAction) => void;
  onSelectDevice?: (deviceId: string) => void;
}

function IncidentRow({ a, onAction, pending, onSelectDevice }: RowProps) {
  const isOpen = a.status === "open";
  const isHigh = a.severity === "high";
  const label = ANOMALY_LABELS[a.anomaly_type] ?? a.anomaly_type;

  return (
    <li className={`p-3 text-xs ${isHigh && isOpen ? "bg-destructive/5" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          {isHigh ? <Flame className="h-3.5 w-3.5 shrink-0 text-destructive" /> : <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-500" />}
          <Badge variant={severityVariant(a.severity)} className="shrink-0">
            {severityLabel(a.severity)}
          </Badge>
          <span className="truncate font-medium">{label}</span>
        </div>
        <Badge variant={STATUS_VARIANT[a.status]} className="shrink-0 text-[10px]">
          {a.status}
        </Badge>
      </div>

      <div className="mt-1.5 space-y-0.5 text-[11px] text-muted-foreground">
        {a.customer_name ? (
          <div className="truncate">
            <span className="text-foreground">{a.customer_name}</span>
            {a.site_name ? <span> · {a.site_name}</span> : null}
          </div>
        ) : null}
        <div className="flex items-center justify-between">
          <button
            className="font-mono hover:underline"
            onClick={() => onSelectDevice?.(a.device_id)}
            title="Open device detail"
          >
            {a.device_id}
            {a.unit_id ? <span className="ml-1 text-foreground">unit {a.unit_id}</span> : null}
          </button>
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {relativeTime(a.timestamp)}
          </span>
        </div>
      </div>

      {isOpen ? (
        <div className="mt-2 flex flex-wrap items-center gap-1">
          <Button
            size="sm"
            variant="outline"
            className="h-7 gap-1 px-2 text-[11px]"
            disabled={pending}
            onClick={() => onAction(a.id, "acknowledge")}
          >
            <CheckCircle2 className="h-3 w-3" /> Ack
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 gap-1 px-2 text-[11px]"
            disabled={pending}
            onClick={() => onAction(a.id, "dispatch")}
          >
            <Truck className="h-3 w-3" /> Dispatch
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 gap-1 px-2 text-[11px]"
            disabled={pending}
            onClick={() => onAction(a.id, "snooze")}
          >
            <Moon className="h-3 w-3" /> Snooze
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 gap-1 px-2 text-[11px] text-muted-foreground"
            disabled={pending}
            onClick={() => onAction(a.id, "false_positive")}
          >
            <Hammer className="h-3 w-3" /> False
          </Button>
        </div>
      ) : (
        <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
          {a.assignee ? <span>by {a.assignee}</span> : null}
          {a.acted_at ? <span>· {relativeTime(a.acted_at)}</span> : null}
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto h-6 gap-1 px-2 text-[10px]"
            disabled={pending}
            onClick={() => onAction(a.id, "reopen")}
          >
            <RefreshCw className="h-3 w-3" /> Reopen
          </Button>
        </div>
      )}
    </li>
  );
}
