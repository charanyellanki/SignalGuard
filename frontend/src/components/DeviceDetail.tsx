import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDevice } from "@/hooks/useDevices";
import type { Severity, TelemetryPoint } from "@/lib/types";

interface Props {
  deviceId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function severityVariant(s: Severity): "destructive" | "warning" | "secondary" {
  return s === "high" ? "destructive" : s === "medium" ? "warning" : "secondary";
}

interface ChartRow {
  t: string;
  battery: number;
  signal: number;
  events: number;
  temp: number;
}

function toChartRows(points: TelemetryPoint[]): ChartRow[] {
  return points.map((p) => ({
    t: new Date(p.timestamp).toLocaleTimeString(),
    battery: p.battery_voltage,
    signal: p.signal_strength_dbm,
    events: p.lock_events_count,
    temp: p.temperature_c,
  }));
}

export function DeviceDetail({ deviceId, open, onOpenChange }: Props) {
  const { data, isLoading } = useDevice(deviceId);
  const rows: ChartRow[] = data ? toChartRows(data.telemetry) : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-base">{deviceId ?? ""}</DialogTitle>
          <DialogDescription>
            Last 100 telemetry samples and recent anomalies.
          </DialogDescription>
        </DialogHeader>

        {isLoading || !data ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <Tabs defaultValue="charts">
            <TabsList>
              <TabsTrigger value="charts">Charts</TabsTrigger>
              <TabsTrigger value="anomalies">
                Anomalies ({data.anomalies.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="charts" className="space-y-4">
              {([
                { title: "Battery (V)", dataKey: "battery" as const, color: "#10b981" },
                { title: "Signal (dBm)", dataKey: "signal" as const, color: "#6366f1" },
                { title: "Lock events", dataKey: "events" as const, color: "#f59e0b" },
                { title: "Temperature (°C)", dataKey: "temp" as const, color: "#ef4444" },
              ]).map((cfg) => (
                <div key={cfg.dataKey}>
                  <p className="mb-1 text-xs text-muted-foreground">{cfg.title}</p>
                  <ResponsiveContainer width="100%" height={120}>
                    <LineChart data={rows}>
                      <XAxis dataKey="t" hide />
                      <YAxis
                        width={40}
                        tick={{ fontSize: 10, fill: "currentColor" }}
                        domain={["auto", "auto"]}
                      />
                      <Tooltip
                        contentStyle={{
                          fontSize: 12,
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey={cfg.dataKey}
                        stroke={cfg.color}
                        dot={false}
                        strokeWidth={2}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ))}
            </TabsContent>

            <TabsContent value="anomalies">
              {data.anomalies.length === 0 ? (
                <p className="text-sm text-muted-foreground">No anomalies recorded.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Severity</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.anomalies.map((a) => (
                      <TableRow key={a.id}>
                        <TableCell className="font-mono text-xs">
                          {new Date(a.timestamp).toLocaleString()}
                        </TableCell>
                        <TableCell>{a.anomaly_type}</TableCell>
                        <TableCell className="font-mono text-xs">
                          {a.detected_by_model}
                        </TableCell>
                        <TableCell>
                          <Badge variant={severityVariant(a.severity)}>{a.severity}</Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}
