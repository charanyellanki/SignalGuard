import { useCallback, useMemo } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { WS_BASE } from "@/lib/api";
import { useAnomalies } from "@/hooks/useAnomalies";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnomalyRecord, Severity } from "@/lib/types";

interface Props {
  onStatusChange?: (connected: boolean) => void;
}

function severityVariant(s: Severity): "destructive" | "warning" | "secondary" {
  return s === "high" ? "destructive" : s === "medium" ? "warning" : "secondary";
}

const parseAnomaly = (raw: string): AnomalyRecord | null => {
  try {
    return JSON.parse(raw) as AnomalyRecord;
  } catch {
    return null;
  }
};

export function AnomalyFeed({ onStatusChange }: Props) {
  // Seed with the most recent anomalies already in the DB so the feed isn't
  // empty on first paint. The WS stream then layers fresh events on top.
  const seed = useAnomalies({ limit: 25 });

  const { status, messages } = useWebSocket<AnomalyRecord>({
    url: `${WS_BASE}/ws/anomalies`,
    parse: parseAnomaly,
    maxBuffer: 50,
    onMessage: useCallback(() => onStatusChange?.(true), [onStatusChange]),
  });

  // Notify parent about status flips (open vs not).
  onStatusChange?.(status === "open");

  const combined: AnomalyRecord[] = useMemo(() => {
    const byId = new Map<number, AnomalyRecord>();
    for (const a of messages) byId.set(a.id, a);
    for (const a of seed.data?.items ?? []) if (!byId.has(a.id)) byId.set(a.id, a);
    return [...byId.values()]
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
      .slice(0, 50);
  }, [messages, seed.data]);

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="shrink-0 pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Live anomaly feed</CardTitle>
          <Badge variant={status === "open" ? "success" : "warning"}>{status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-0">
        {combined.length === 0 ? (
          <p className="p-4 text-xs text-muted-foreground">
            No anomalies yet. They'll stream in here as the detector flags them.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {combined.map((a) => (
              <li key={a.id} className="px-4 py-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-foreground">{a.device_id}</span>
                  <Badge variant={severityVariant(a.severity)}>{a.severity}</Badge>
                </div>
                <div className="mt-1 flex items-center justify-between text-muted-foreground">
                  <span>{a.anomaly_type}</span>
                  <span className="font-mono">{a.detected_by_model}</span>
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground/80">
                  {new Date(a.timestamp).toLocaleTimeString()}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
